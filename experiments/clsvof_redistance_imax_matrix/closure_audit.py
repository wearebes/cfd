#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def add(issues: list[dict[str, Any]], code: str, detail: Any = None) -> None:
    issue = {"code": code}
    if detail is not None:
        issue["detail"] = detail
    issues.append(issue)


def csv_rows(
    root: Path, name: str, expected: int, issues: list[dict[str, Any]]
) -> list[dict[str, str]]:
    path = root / name
    if not path.is_file():
        add(issues, "missing_csv", name)
        return []
    rows = read_csv(path)
    if len(rows) != expected:
        add(issues, "csv_row_count", {"file": name, "expected": expected, "actual": len(rows)})
    return rows


def audit(root: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    row_audit_path = root / "audit.json"
    if not row_audit_path.is_file():
        add(issues, "row_audit_missing")
        row_audit = {}
    else:
        row_audit = read_json(row_audit_path)
        if row_audit.get("passed") is not True:
            add(issues, "row_audit_not_passed", row_audit.get("state_counts"))

    status = csv_rows(root, "matrix_status.csv", 96, issues)
    if status and Counter(row["execution_state"] for row in status) != Counter({"completed": 96}):
        add(issues, "matrix_status_not_all_completed")
    metrics = csv_rows(root, "metrics_wide.csv", 96, issues)
    csv_rows(root, "paired_metrics_wide.csv", 48, issues)
    csv_rows(root, "delta_vs_imax3.csv", 96, issues)
    csv_rows(root, "paired_native_nn_deltas.csv", 48, issues)
    csv_rows(root, "aggregate_by_imax.csv", 24, issues)
    csv_rows(root, "convergence_by_imax.csv", 12, issues)
    csv_rows(root, "tradeoff_by_identity.csv", 16, issues)
    csv_rows(root, "sdf_physics_relationship.csv", 16, issues)
    csv_rows(root, "runtime.csv", 96, issues)
    csv_rows(root, "failures.csv", 0, issues)

    long_path = root / "metrics_long.csv"
    if not long_path.is_file():
        add(issues, "metrics_long_missing")
    else:
        long_ids = {row["row_id"] for row in read_csv(long_path)}
        if len(long_ids) != 96:
            add(issues, "metrics_long_identity_count", len(long_ids))

    capwave = csv_rows(root, "capwave_timeseries.csv", 48 * 738, issues)
    if capwave:
        groups = Counter(row["row_id"] for row in capwave)
        if len(groups) != 48 or set(groups.values()) != {738}:
            add(issues, "capwave_timeseries_group_contract")
    rising_path = root / "rising_timeseries.csv"
    if not rising_path.is_file():
        add(issues, "rising_timeseries_missing")
    else:
        rising = read_csv(rising_path)
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rising:
            grouped[row["row_id"]].append(row)
        if len(grouped) != 48:
            add(issues, "rising_timeseries_identity_count", len(grouped))
        bad_final = [row_id for row_id, rows in grouped.items() if abs(float(rows[-1]["time"]) - 3.0) > 1e-12]
        if bad_final:
            add(issues, "rising_timeseries_final_time", bad_final)

    if metrics:
        if any(int(float(row.get("provider_clamp_hits", "0") or 0)) != 0 for row in metrics):
            add(issues, "nonzero_clamp_hits")
        if any(row.get("return_contract_ok") != "True" for row in metrics):
            add(issues, "return_contract_not_universal")

    required_bases = (
        "fig01_physical_tradeoff",
        "fig02_capwave_heatmaps",
        "fig03_rising_heatmaps",
        "fig04_sdf_physics",
        "fig05_n512_histories",
        "fig06_rising_n512_shapes",
    )
    figures = root / "figures"
    for base in required_bases:
        for suffix in ("svg", "pdf", "png"):
            path = figures / f"{base}.{suffix}"
            if not path.is_file() or path.stat().st_size == 0:
                add(issues, "figure_missing", path.name)
        source = figures / "source_data" / f"{base}.csv"
        if not source.is_file() or source.stat().st_size == 0:
            add(issues, "figure_source_missing", source.name)

    figure_qa_path = figures / "figure_qa_manifest.json"
    if not figure_qa_path.is_file():
        add(issues, "figure_qa_missing")
    else:
        figure_qa = read_json(figure_qa_path)
        if figure_qa.get("visual_review") != "passed":
            add(issues, "figure_visual_review_not_passed", figure_qa.get("visual_review"))
        svg_records = [row for row in figure_qa.get("outputs", []) if row.get("file", "").endswith(".svg")]
        if len(svg_records) != 6 or not all(row.get("editable_text_ok") is True for row in svg_records):
            add(issues, "editable_svg_contract")

    verification_path = root / "verification_manifest.json"
    if not verification_path.is_file():
        add(issues, "verification_manifest_missing")
    else:
        verification = read_json(verification_path)
        if verification.get("passed") is not True:
            add(issues, "verification_manifest_not_passed")
        if verification.get("matrix_pytest", {}).get("passed") is not True:
            add(issues, "matrix_tests_not_passed")
        if verification.get("nn_golden_vector", {}).get("passed") is not True:
            add(issues, "nn_golden_vector_not_passed")

    analysis_path = root / "formal_analysis.md"
    if not analysis_path.is_file():
        add(issues, "formal_analysis_missing")
    else:
        analysis = analysis_path.read_text(encoding="utf-8")
        if "formal row audit passed" not in analysis or "(96/96 rows completed)" not in analysis:
            add(issues, "formal_analysis_not_final")

    for name in (
        "evidence_hashes.csv",
        "audit.md",
        "provenance_amendment.json",
        "resource_policy.md",
        "resource_accounting_amendment.json",
        "workspace_boundary_audit.json",
    ):
        path = root / name
        if not path.is_file() or path.stat().st_size == 0:
            add(issues, "closure_evidence_missing", name)

    return {
        "schema_version": 1,
        "matrix_id": root.name,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "row_audit_passed": row_audit.get("passed") is True,
    }


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Formal matrix closure audit",
        "",
        f"Matrix ID: `{result['matrix_id']}`",
        "",
        f"Verdict: **{'PASS' if result['passed'] else 'INCOMPLETE/FAIL'}**",
        "",
        f"Issues: **{result['issue_count']}**",
        "",
        "| Code | Detail |",
        "| --- | --- |",
    ]
    if result["issues"]:
        for issue in result["issues"]:
            lines.append(f"| {issue['code']} | {str(issue.get('detail', '')).replace('|', '/')} |")
    else:
        lines.append("| none | all closure checks passed |")
    lines.append("")
    return "\n".join(lines)


def evidence_map(result: dict[str, Any]) -> str:
    status = "PASS" if result["passed"] else "PENDING"
    return f"""# Acceptance-contract completion evidence

Matrix ID: `{result['matrix_id']}`  
Overall closure: **{status}**

| Contract section | Evidence |
| --- | --- |
| A. Matrix identity | `matrix_manifest.json`, `matrix_status.csv`, `metrics_wide.csv` |
| B. Treatment isolation | row `manifest.json` commands and hashes; `audit.json` |
| C. Implementation gate | matrix pytest record in `verification_manifest.json`; provenance audits |
| D. imax=3 reuse | per-row `reuse_validation` and `provenance_audit.json` |
| E. Per-row execution | 96 row directories, status/manifests, `evidence_hashes.csv` |
| F. Physical gates | `metrics_wide.csv`, independent capwave RMS, rising reference/shape metrics |
| G. SDF gates | `redistance_metrics.csv`, `redistance_return_trace.csv`, row audit |
| H. NN gates | weight/feature/provider hashes, provider counts, golden-vector verification |
| I. Failure evidence | `matrix_status.csv`; no hidden rows; failure ledger implicit when zero failures |
| J. Matrix analysis | aggregate/delta/tradeoff/relationship/time-series CSVs and six figure families |
| K. Closure test | `audit.json`, `closure_audit.json`, `formal_analysis.md`, figure QA |
| L. User approval | approved plan and acceptance contract under `docs/superpowers/plans/` |
| M. Resource scheduler | `resource_policy.md`, `resource_policy_amendment.json`, scheduler state/log |
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = HERE / "results" / args.matrix_id
    result = audit(root)
    atomic_text(root / "closure_audit.json", json.dumps(result, indent=2) + "\n")
    atomic_text(root / "closure_audit.md", markdown(result))
    atomic_text(root / "completion_evidence.md", evidence_map(result))
    print(json.dumps({"passed": result["passed"], "issues": result["issue_count"]}))
    return 0 if result["passed"] or args.allow_incomplete else 1


if __name__ == "__main__":
    raise SystemExit(main())
