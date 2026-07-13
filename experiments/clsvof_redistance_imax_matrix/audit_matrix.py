#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_row import DEFAULT_MATRIX, HERE, result_dir
from summarize_matrix import collect_row


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def required_evidence(row: dict[str, Any]) -> list[str]:
    shared = [
        "status.json",
        "manifest.json",
        "provenance_audit.json",
        "compile.stdout",
        "compile.stderr",
        "log",
        "redistance_metrics.csv",
        "redistance_return_trace.csv",
        "redistance_overlay.json",
        "two-phase-clsvof.h",
        "redistance_matrix_metrics.h",
        "integral.h",
    ]
    if row["benchmark"] == "capwave":
        shared.extend(["stdout.txt", f"wave-{row['N']}", "capwave-clsvof.c"])
    else:
        shared.extend(["out", "rising-clsvof.c"])
    return shared


def finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def logging_stride_valid(
    destination: Path, manifest: dict[str, Any], final_time: float
) -> bool:
    flags = [
        item for item in manifest.get("command", [])
        if str(item).startswith("-DREDIST_MATRIX_LOG_STRIDE=")
    ]
    if len(flags) != 1:
        return False
    try:
        stride = int(str(flags[0]).split("=", 1)[1])
    except ValueError:
        return False
    if stride <= 0:
        return False
    metrics_path = destination / "redistance_metrics.csv"
    if not metrics_path.is_file():
        return False
    with metrics_path.open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))
    if not records:
        return False
    return all(
        int(item["i"]) == 0
        or int(item["i"]) % stride == 0
        or abs(float(item["t"]) - final_time) <= 1e-8
        for item in records
    )


def audit(
    matrix: dict[str, Any], result_root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    hashes: list[dict[str, Any]] = []
    rows = matrix.get("rows", [])
    amendment_path = result_root / "instrumentation_amendment.json"
    if not amendment_path.is_file():
        issues.append({"scope": "matrix", "code": "instrumentation_amendment_missing"})
        expected_metrics_hash = None
    else:
        amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
        expected_metrics_hash = amendment.get("new_metrics_header_sha256")
    boundary_path = result_root / "workspace_boundary_audit.json"
    if not boundary_path.is_file():
        issues.append({"scope": "matrix", "code": "workspace_boundary_audit_missing"})
    elif json.loads(boundary_path.read_text(encoding="utf-8")).get("passed") is not True:
        issues.append({"scope": "matrix", "code": "workspace_boundary_changed"})
    ids = [row.get("row_id") for row in rows]
    if len(rows) != 96:
        issues.append({"scope": "matrix", "code": "row_count", "detail": len(rows)})
    if len(set(ids)) != len(ids):
        issues.append({"scope": "matrix", "code": "duplicate_row_id"})

    collected = []
    for row in rows:
        row_id = str(row["row_id"])
        destination = result_dir(result_root, row)
        metrics = collect_row(result_root, row)
        collected.append(metrics)
        if metrics["execution_state"] != "completed":
            issues.append(
                {
                    "scope": row_id,
                    "code": "not_completed",
                    "detail": metrics["execution_state"],
                }
            )
            continue

        for name in required_evidence(row):
            path = destination / name
            if not path.is_file() or path.stat().st_size == 0 and name not in {
                "compile.stdout",
                "compile.stderr",
                "stdout.txt",
            }:
                issues.append({"scope": row_id, "code": "missing_evidence", "detail": name})
                continue
            if path.is_file():
                hashes.append(
                    {
                        "row_id": row_id,
                        "file": name,
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )

        manifest_path = destination / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("row", {}).get("row_id") != row_id:
                issues.append({"scope": row_id, "code": "manifest_identity"})
            if row["planning_status"] == "candidate_reuse":
                reuse = manifest.get("reuse_validation")
                if not reuse or reuse.get("comparison") not in {
                    "byte_identical",
                    "first_five_physical_columns_abs_tol_1e-12",
                }:
                    issues.append({"scope": row_id, "code": "reuse_not_validated"})
            embedded_metrics_hash = (
                manifest.get("files", {}).get("metrics_header", {}).get("sha256")
            )
            if expected_metrics_hash and embedded_metrics_hash != expected_metrics_hash:
                issues.append(
                    {
                        "scope": row_id,
                        "code": "obsolete_metrics_header",
                        "detail": embedded_metrics_hash,
                    }
                )
            final_flag = (
                "-DREDIST_MATRIX_FINAL_TIME=2.2426211256"
                if row["benchmark"] == "capwave"
                else "-DREDIST_MATRIX_FINAL_TIME=3.0"
            )
            if final_flag not in manifest.get("command", []):
                issues.append({"scope": row_id, "code": "final_time_compile_flag_missing"})
            final_time = 2.2426211256 if row["benchmark"] == "capwave" else 3.0
            if not logging_stride_valid(destination, manifest, final_time):
                issues.append({"scope": row_id, "code": "diagnostic_logging_stride_invalid"})

        provenance_path = destination / "provenance_audit.json"
        if provenance_path.is_file():
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            if not provenance.get("passed"):
                issues.append({"scope": row_id, "code": "provenance_failed"})
            if row["method"] == "clsvof_nn" and "weights" not in provenance.get("inputs", {}):
                issues.append({"scope": row_id, "code": "weights_provenance_missing"})

        for flag in (
            "return_contract_ok",
            "initial_diagnostic_ok",
            "final_diagnostic_ok",
            "final_trace_ok",
        ):
            if metrics.get(flag) is not True:
                issues.append({"scope": row_id, "code": flag, "detail": metrics.get(flag)})
        for key in (
            "post_b15_egrad_mean",
            "post_b15_egrad_rms",
            "post_b15_egrad_mean_p95",
            "post_b15_egrad_linf",
            "post_b30_egrad_mean",
            "post_b30_egrad_rms",
            "post_b30_egrad_mean_p95",
            "post_b30_egrad_linf",
        ):
            if not finite_number(metrics.get(key)):
                issues.append({"scope": row_id, "code": "nonfinite_metric", "detail": key})
        if row["method"] == "clsvof_nn":
            if not finite_number(metrics.get("provider_evaluations")):
                issues.append({"scope": row_id, "code": "provider_stats_missing"})
            if not finite_number(metrics.get("provider_clamp_hits")):
                issues.append({"scope": row_id, "code": "provider_clamp_stats_missing"})
            elif int(metrics["provider_clamp_hits"]) != 0:
                issues.append(
                    {
                        "scope": row_id,
                        "code": "provider_clamp_hits_nonzero",
                        "detail": int(metrics["provider_clamp_hits"]),
                    }
                )
        if row["benchmark"] == "capwave":
            capwave_metrics = (
                "relative_rms",
                "relative_rms_recomputed",
                "amplitude_l2_error",
                "max_abs_amplitude_error",
                "final_amplitude_error",
                "amplitude_error_bias",
            )
            if metrics.get("wave_rows") != 738 or not all(
                finite_number(metrics.get(key)) for key in capwave_metrics
            ):
                issues.append({"scope": row_id, "code": "capwave_physical_invalid"})
            elif not math.isclose(
                float(metrics["relative_rms"]),
                float(metrics["relative_rms_recomputed"]),
                rel_tol=3e-5,
                abs_tol=3e-8,
            ):
                issues.append(
                    {
                        "scope": row_id,
                        "code": "capwave_rms_reproduction_mismatch",
                        "detail": {
                            "logged": metrics["relative_rms"],
                            "recomputed": metrics["relative_rms_recomputed"],
                        },
                    }
                )
        else:
            if metrics.get("final_time") != 3.0 or not all(
                finite_number(metrics.get(key))
                for key in (
                    "solver_steps",
                    "stock_cpu_seconds",
                    "stock_real_seconds",
                    "final_volume_drift",
                    "final_center",
                    "final_velocity",
                    "peak_velocity",
                    "time_at_peak_velocity",
                    "max_abs_volume_drift",
                    "shape_mean_distance",
                    "shape_max_distance",
                    "center_reference_rmse",
                    "velocity_reference_rmse",
                    "center_reference_linf",
                    "velocity_reference_linf",
                    "final_center_reference_error",
                    "final_velocity_reference_error",
                )
            ):
                issues.append({"scope": row_id, "code": "rising_physical_invalid"})

    states = Counter(str(item["execution_state"]) for item in collected)
    result = {
        "schema_version": 1,
        "matrix_id": result_root.name,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "expected_rows": 96,
        "state_counts": dict(sorted(states.items())),
        "issue_count": len(issues),
        "passed": len(issues) == 0 and states == Counter({"completed": 96}),
        "issues": issues,
    }
    return result, hashes


def write_hashes(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["row_id", "file", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def write_markdown(path: Path, audit_result: dict[str, Any]) -> None:
    lines = [
        "# Formal matrix audit",
        "",
        f"Matrix ID: `{audit_result['matrix_id']}`",
        "",
        f"Verdict: **{'PASS' if audit_result['passed'] else 'INCOMPLETE/FAIL'}**",
        "",
        f"Issues: **{audit_result['issue_count']}**",
        "",
        "## State counts",
        "",
        "| State | Rows |",
        "| --- | ---: |",
    ]
    for state, count in audit_result["state_counts"].items():
        lines.append(f"| {state} | {count} |")
    lines.extend(["", "## Issues", ""])
    if not audit_result["issues"]:
        lines.append("None.")
    else:
        lines.extend(["| Scope | Code | Detail |", "| --- | --- | --- |"])
        for issue in audit_result["issues"]:
            lines.append(
                f"| {issue.get('scope', '')} | {issue.get('code', '')} | "
                f"{str(issue.get('detail', '')).replace('|', '/')} |"
            )
    lines.append("")
    atomic_text(path, "\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    result_root = HERE / "results" / args.matrix_id
    result, hashes = audit(matrix, result_root)
    atomic_text(result_root / "audit.json", json.dumps(result, indent=2) + "\n")
    write_hashes(result_root / "evidence_hashes.csv", hashes)
    write_markdown(result_root / "audit.md", result)
    print(json.dumps({"passed": result["passed"], "issues": result["issue_count"]}))
    return 0 if result["passed"] or args.allow_incomplete else 1


if __name__ == "__main__":
    raise SystemExit(main())
