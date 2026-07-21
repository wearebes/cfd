#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.lib.integrity import atomic_json, sha256_file  # noqa: E402
from hpc.lib.matrix import formal_rows  # noqa: E402
from hpc.lib.scheduler import load_policy, phase_rows, threads_for  # noqa: E402


REQUIRED = (
    "hpc/bootstrap_ubuntu.sh",
    "hpc/submit_matrix.sh",
    "hpc/preflight_hpc.py",
    "hpc/run_canaries.py",
    "hpc/run_matrix.py",
    "hpc/run_row.py",
    "hpc/verify_matrix.py",
    "hpc/verify_rising_openmp_smokes.py",
    "hpc/collect_results.sh",
    "hpc/prepare_deployment.sh",
    "hpc/package_results.py",
    "hpc/package_deployment.py",
    "hpc/export_deployment.py",
    "hpc/config/matrix_180.json",
    "hpc/config/thread_policy.json",
    "hpc/config/provenance.lock.json",
    ".github/workflows/ubuntu-hpc.yml",
    "docs/server/ubuntu22-hpc-operator-handoff.md",
    "generate/rising_bubble/clsvof.sh",
    "generate/rising_bubble/nn.sh",
    "generate/capwave/clsvof.sh",
    "generate/stationary_bubble/clsvof.sh",
)


def check(name: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"name": name, "status": "PASS" if passed else "FAIL", "evidence": evidence}


def main() -> int:
    checks: list[dict[str, Any]] = []
    missing = [relative for relative in REQUIRED if not (ROOT / relative).is_file()]
    checks.append(check("required_files", not missing, f"missing={missing}"))

    rows = formal_rows()
    counts = {
        benchmark: sum(row.benchmark == benchmark for row in rows)
        for benchmark in ("capwave", "rising_case1", "rising_case2", "stationary_bubble")
    }
    checks.append(
        check(
            "matrix_180",
            len(rows) == len({row.row_id for row in rows}) == 180,
            f"rows={len(rows)} counts={counts}",
        )
    )
    checks.append(
        check(
            "phase_counts",
            len(phase_rows(rows, "n64")) == 48
            and len(phase_rows(rows, "remaining")) == 132,
            "n64=48 remaining=132",
        )
    )
    checks.append(
        check(
            "stationary_n512_absent",
            not any(row.benchmark == "stationary_bubble" and row.resolution == 512 for row in rows),
            "generated matrix contains no stationary N512",
        )
    )

    lock_path = ROOT / "hpc/config/provenance.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    mismatches = []
    for relative, expected in lock["files"].items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else "missing"
        if actual != expected:
            mismatches.append((relative, expected, actual))
    checks.append(check("provenance_lock", not mismatches, f"mismatches={mismatches}"))

    policy, policy_hash = load_policy(ROOT / "hpc/config/thread_policy.json")
    max_threads = max(threads_for(row, policy) for row in rows)
    checks.append(
        check(
            "thread_policy",
            max_threads <= int(policy["cpu_pool"]) == 128,
            f"policy_sha256={policy_hash} max_threads={max_threads}",
        )
    )

    bash_files = [ROOT / relative for relative in REQUIRED if relative.endswith(".sh")]
    bash_files.extend((ROOT / "generate").glob("*/*.sh"))
    syntax = subprocess.run(
        ["bash", "-n", *map(str, bash_files)], text=True, capture_output=True
    )
    checks.append(check("bash_syntax", syntax.returncode == 0, syntax.stderr.strip()))

    scan_roots = [ROOT / "hpc", ROOT / "generate"]
    source_files = [
        path
        for root in scan_roots
        for path in root.rglob("*")
        if path.is_file()
        and path != Path(__file__).resolve()
        and path.suffix in {".py", ".sh", ".json", ".yaml", ".yml"}
    ]
    forbidden_patterns = {
        "linux_shasum_dependency": re.compile(r"\bshasum\b"),
        "absolute_conda_path": re.compile(r"/opt/anaconda"),
        "formal_imax_0_10": re.compile(r"0\.\.10|0 through 10|range\(11\)"),
    }
    findings: dict[str, list[str]] = {name: [] for name in forbidden_patterns}
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in forbidden_patterns.items():
            if pattern.search(text):
                findings[name].append(str(path.relative_to(ROOT)))
    checks.append(
        check(
            "forbidden_runtime_patterns",
            not any(findings.values()),
            json.dumps(findings, sort_keys=True),
        )
    )

    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "hpc/tests",
            "generate/_shared/nn_runtime/tests",
            "generate/rising_bubble/tests",
            "generate/tests",
            "generate/_shared/nondefault_redistance/tests",
            "-q",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    test_output = (tests.stdout + tests.stderr).strip().splitlines()
    test_summary = next(
        (line for line in reversed(test_output) if " passed" in line or " failed" in line),
        test_output[-1] if test_output else "no pytest output",
    )
    checks.append(
        check(
            "local_test_suite",
            tests.returncode == 0,
            test_summary,
        )
    )

    external_gates = [
        "Ubuntu 22.04 GitHub Actions has not been executed in this local-only repository",
        "real 128-CPU host preflight/capacity canary has not been executed",
        "formal 180-row matrix has not been launched",
    ]
    failed = [item for item in checks if item["status"] != "PASS"]
    status = "FAIL" if failed else "READY_FOR_UBUNTU_CI"
    report = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks": checks,
        "external_gates": external_gates,
    }
    report_root = ROOT / "reports/hpc_implementation_audit"
    report_root.mkdir(parents=True, exist_ok=True)
    atomic_json(report_root / "audit.json", report)
    lines = [
        "# HPC implementation audit",
        "",
        f"Status: **{status}**",
        "",
        "## Automated checks",
        "",
        "| Check | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for item in checks:
        evidence = str(item["evidence"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['name']} | {item['status']} | {evidence} |")
    lines.extend(["", "## External release gates", ""])
    lines.extend(f"- {gate}" for gate in external_gates)
    (report_root / "audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "failed_checks": len(failed)}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
