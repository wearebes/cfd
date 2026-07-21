#!/usr/bin/env python3
"""Aggregate and verify the 48-row oscillating-droplet imax matrix."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from hpc.lib.dataset_publish import publish_scientific_row
BASE_ANALYZER = HERE.parent / "summarize_rows.py"
SPEC = importlib.util.spec_from_file_location("oscillation_base_analyzer", BASE_ANALYZER)
BASE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BASE)

RUNTIME_FIELDS = [
    "case",
    "subcase",
    "resolution",
    "imax",
    "method",
    "model_resolution",
    "data_dir",
    "elapsed_seconds",
    "complete",
]


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def method_dir(method: str) -> str:
    return method


def publish_dataset(result_root: Path, contract: dict) -> None:
    dataset = ROOT / "dataset"
    plans: list[tuple[Path, Path]] = []
    runtime_rows: list[dict[str, object]] = []
    for level in contract["levels"]:
        level = int(level)
        resolution = 1 << level
        for imax in contract["imax"]:
            imax = int(imax)
            for source_method, target_method in (
                ("clsvof", "clsvof"),
                ("nn", "nn"),
            ):
                source_dir = (
                    result_root
                    / f"N{resolution:04d}"
                    / f"imax_{imax}"
                    / method_dir(source_method)
                )
                manifest = json.loads(
                    (source_dir / "manifest.json").read_text(encoding="utf-8")
                )
                target_dir = (
                    dataset
                    / "oscillating_droplet"
                    / "formal_v2"
                    / f"N{resolution:04d}"
                    / f"imax{imax:02d}"
                    / target_method
                )
                plans.append((source_dir, target_dir))
                runtime_rows.append(
                    {
                        "case": "oscillating_droplet",
                        "subcase": "",
                        "resolution": resolution,
                        "imax": imax,
                        "method": target_method,
                        "model_resolution": "",
                        "data_dir": target_dir.relative_to(dataset).as_posix(),
                        "elapsed_seconds": manifest["wall_seconds"],
                        "complete": (
                            "true" if manifest["status"] == "completed" else "false"
                        ),
                    }
                )

    for source_dir, target_dir in plans:
        publish_scientific_row(source_dir, target_dir)

    runtime_path = dataset / "runtime_v2.csv"
    if runtime_path.is_file():
        with runtime_path.open(newline="", encoding="utf-8") as handle:
            existing_runtime = list(csv.DictReader(handle))
    else:
        existing_runtime = []
    replaced = {
        (
            str(row["case"]),
            str(row["subcase"]),
            str(row["resolution"]),
            str(row["imax"]),
            str(row["method"]),
        )
        for row in runtime_rows
    }
    merged = [
        row
        for row in existing_runtime
        if (
            row["case"],
            row["subcase"],
            row["resolution"],
            row["imax"],
            row["method"],
        )
        not in replaced
    ] + runtime_rows
    merged.sort(
        key=lambda row: (
            str(row["case"]),
            str(row["subcase"]),
            -1 if row["resolution"] == "" else int(row["resolution"]),
            -1 if row["imax"] == "" else int(row["imax"]),
            str(row["method"]),
            -1
            if row["model_resolution"] == ""
            else int(row["model_resolution"]),
        )
    )
    temporary = runtime_path.with_name(f".runtime.csv.publish.{os.getpid()}")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RUNTIME_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(merged)
    os.replace(temporary, runtime_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_root", type=Path)
    parser.add_argument(
        "--publish-dataset",
        action="store_true",
        help="publish only verified time series and runtime rows to dataset/",
    )
    args = parser.parse_args(argv)
    result_root = args.result_root.resolve()
    contract = json.loads((result_root / "matrix_contract.json").read_text(encoding="utf-8"))
    rows: list[dict] = []
    failures: list[dict] = []
    checks: dict[str, object] = {"rows": {}, "all_execution_gates_passed": True}
    for level in contract["levels"]:
        n = 1 << int(level)
        for imax in contract["imax"]:
            pair: dict[str, dict] = {}
            for method in ("clsvof", "nn"):
                directory = result_root / f"N{n:04d}" / f"imax_{imax}" / method_dir(method)
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                if manifest["status"] != "completed":
                    failure = {
                        "N": n,
                        "level": level,
                        "imax": imax,
                        "method": method,
                        "status": manifest["status"],
                        "run_returncode": manifest.get("run_returncode"),
                        "numerical_failure": manifest.get("numerical_failure"),
                        "wall_seconds": manifest.get("wall_seconds"),
                    }
                    failures.append(failure)
                    pair[method] = failure
                    checks["rows"][f"N{n:04d}_imax{imax}_{method}"] = {
                        "status_completed": False,
                        "scientific_failure_recorded": bool(manifest.get("numerical_failure")),
                    }
                    checks["all_execution_gates_passed"] = False
                    continue
                metrics = BASE.row_metrics(directory, int(level))
                stats = manifest.get("provider_stats") or {}
                row = {
                    "N": n,
                    "level": level,
                    "imax": imax,
                    "method": method,
                    "a": metrics["a"],
                    "b_fit": metrics["b"],
                    "b_fit_se": metrics["b_stderr"],
                    "b_envelope": metrics["peak_envelope_b_diagnostic"],
                    "c": metrics["c"],
                    "frequency_error_abs_percent": metrics["frequency_error_abs_percent"],
                    "peak_first": metrics["peak_envelope_first"],
                    "peak_last": metrics["peak_envelope_last"],
                    "peak_growth_ratio": metrics["peak_envelope_last"] / metrics["peak_envelope_first"],
                    "max_kinetic_energy": metrics["max_kinetic_energy"],
                    "final_time": metrics["final_time"],
                    "samples": metrics["samples"],
                    "wall_seconds": manifest["wall_seconds"],
                    "provider_evaluations": stats.get("evaluations", 0),
                    "guard_hits": stats.get("denominator_guard_hits", 0),
                    "clamp_hits": stats.get("clamp_hits", 0),
                }
                rows.append(row)
                pair[method] = row
                row_checks = {
                    "status_completed": manifest["status"] == "completed",
                    "imax_exact": manifest["redistance_imax"] == imax,
                    "finite": bool(metrics["finite"]),
                    "nonnegative_energy": bool(metrics["nonnegative_energy"]),
                    "terminal_time": metrics["final_time"] >= 0.999,
                    "provider_evaluations_positive": method == "clsvof" or stats.get("evaluations", 0) > 0,
                }
                checks["rows"][f"N{n:04d}_imax{imax}_{method}"] = row_checks
                checks["all_execution_gates_passed"] = bool(checks["all_execution_gates_passed"]) and all(row_checks.values())
            if pair["clsvof"].get("status") != "failed" and pair["nn"].get("status") != "failed":
                checks["all_execution_gates_passed"] = bool(checks["all_execution_gates_passed"]) and pair["clsvof"]["final_time"] == pair["nn"]["final_time"]

    paired: list[dict] = []
    by_key = {(row["N"], row["imax"], row["method"]): row for row in rows}
    for n in contract["resolutions"]:
        for imax in contract["imax"]:
            native = by_key.get((n, imax, "clsvof"))
            nn = by_key.get((n, imax, "nn"))
            pair_status = "completed" if native and nn else "scientific_failure"
            paired.append({
                "N": n,
                "imax": imax,
                "pair_status": pair_status,
                "native_b_fit": native["b_fit"] if native else "",
                "nn_b_fit": nn["b_fit"] if nn else "",
                "delta_b_nn_minus_native": nn["b_fit"] - native["b_fit"] if native and nn else "",
                "native_frequency_error_abs_percent": native["frequency_error_abs_percent"] if native else "",
                "nn_frequency_error_abs_percent": nn["frequency_error_abs_percent"] if nn else "",
                "frequency_error_ratio_nn_over_native": nn["frequency_error_abs_percent"] / native["frequency_error_abs_percent"] if native and nn else "",
                "nn_peak_growth_ratio": nn["peak_growth_ratio"] if nn else "",
                "nn_anti_damping": nn["b_fit"] < 0.0 and nn["b_envelope"] < 0.0 if nn else "",
                "guard_hits": nn["guard_hits"] if nn else "",
                "clamp_hits": nn["clamp_hits"] if nn else "",
            })
    if rows:
        write_csv(result_root / "comparison_imax.csv", rows)
    write_csv(result_root / "paired_native_nn.csv", paired)
    if failures:
        write_csv(result_root / "failures.csv", failures)
    checks["expected_rows"] = int(contract["expected_rows"])
    checks["accounted_rows"] = len(rows) + len(failures)
    checks["scientific_failure_rows"] = sum(bool(row["numerical_failure"]) for row in failures)
    checks["infrastructure_failure_rows"] = sum(not bool(row["numerical_failure"]) for row in failures)
    checks["all_rows_accounted"] = checks["accounted_rows"] == checks["expected_rows"]
    checks["deliverable_complete"] = bool(checks["all_rows_accounted"]) and checks["infrastructure_failure_rows"] == 0
    (result_root / "verification.json").write_text(
        json.dumps(checks, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Oscillating droplet redistance-imax matrix",
        "",
        f"- Completed metric rows: {len(rows)}/48",
        f"- Scientific failure rows: {checks['scientific_failure_rows']}",
        f"- Infrastructure failure rows: {checks['infrastructure_failure_rows']}",
        f"- All rows accounted: `{str(checks['all_rows_accounted']).lower()}`",
        f"- Execution gates passed: `{str(checks['all_execution_gates_passed']).lower()}`",
        "- Primary causal comparison: NN versus native at identical `(N, imax)`.",
        "",
        "| N | imax | native b | NN b | NN envelope b | native freq err % | NN freq err % | NN peak last/first | judgment |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in paired:
        if row["pair_status"] != "completed":
            lines.append(f"| {row['N']} | {row['imax']} | — | — | — | — | — | — | numerical failure |")
        else:
            judgment = "anti-damping" if row["nn_anti_damping"] else "damped/stable"
            lines.append(
                f"| {row['N']} | {row['imax']} | {row['native_b_fit']:.6g} | {row['nn_b_fit']:.6g} | "
                f"{by_key[(row['N'], row['imax'], 'nn')]['b_envelope']:.6g} | "
                f"{row['native_frequency_error_abs_percent']:.6g} | {row['nn_frequency_error_abs_percent']:.6g} | "
                f"{row['nn_peak_growth_ratio']:.6g} | {judgment} |"
            )
    (result_root / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.publish_dataset:
        if not checks["deliverable_complete"]:
            raise RuntimeError("dataset publication blocked: matrix is incomplete")
        publish_dataset(result_root, contract)
    print(json.dumps({
        "result_root": str(result_root),
        "row_count": len(rows),
        "all_execution_gates_passed": checks["all_execution_gates_passed"],
        "deliverable_complete": checks["deliverable_complete"],
        "dataset_published": bool(args.publish_dataset),
    }, sort_keys=True))
    return 0 if checks["deliverable_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
