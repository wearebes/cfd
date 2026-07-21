#!/usr/bin/env python3
"""Build the four-metric rising-bubble figure sources from the formal dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from build_source_data import (
    BENCHMARKS,
    IMAX_VALUES,
    METHODS,
    RESOLUTIONS,
    atomic_csv,
    atomic_json,
    facet_segments,
    interpolate,
    read_numeric_history,
    reference_interface_segments,
    rmse,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "dataset/rising_bubble"
DEFAULT_OUTPUT = ROOT / "figures/rising_bubble/shared_data"
INITIAL_RADIUS = 0.25
INITIAL_FULL_AREA = math.pi * INITIAL_RADIUS**2

ERROR_METRICS = (
    "max_abs_relative_volume_error",
    "velocity_reference_rmse",
    "center_reference_rmse",
    "circularity_final_abs_error",
)

SUMMARY_FIELDS = (
    "benchmark",
    "method_id",
    "resolution",
    "imax",
    "terminal_time",
    "dynamics_samples",
    "comparison_start",
    "comparison_end",
    "max_abs_relative_volume_error",
    "velocity_reference_rmse",
    "center_reference_rmse",
    "circularity_final",
    "reference_circularity_final",
    "circularity_final_abs_error",
    "reference_circularity_min_to_t3",
    "reference_time_at_circularity_min_to_t3",
    "numerical_circularity_history_available",
    "facet_segments",
    "result_dir",
    "history_sha256",
    "interface_sha256",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def dataset_path(
    dataset_root: Path,
    benchmark: str,
    method: str,
    resolution: int,
    imax: int,
) -> Path:
    case = 1 if benchmark == "rising_case1" else 2
    method_dir = method
    return (
        dataset_root
        / f"case{case}"
        / f"N{resolution:04d}"
        / f"imax{imax:02d}"
        / method_dir
    )


def half_perimeter(segments: list[tuple[float, float, float, float]]) -> float:
    value = sum(
        math.hypot(vertical1 - vertical0, transverse1 - transverse0)
        for vertical0, transverse0, vertical1, transverse1 in segments
    )
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"invalid half-interface perimeter: {value}")
    return value


def final_circularity(relative_volume_error: float, perimeter_half: float) -> float:
    full_area = INITIAL_FULL_AREA * (1.0 + relative_volume_error)
    if full_area <= 0.0:
        raise ValueError(f"invalid final bubble area: {full_area}")
    # P_full = 2*P_half, so 2*sqrt(pi*A_full)/P_full simplifies as below.
    return math.sqrt(math.pi * full_area) / perimeter_half


def summarize_one(
    dataset_root: Path,
    benchmark: str,
    method: str,
    resolution: int,
    imax: int,
) -> dict[str, object]:
    case = 1 if benchmark == "rising_case1" else 2
    path = dataset_path(dataset_root, benchmark, method, resolution, imax)
    history_path = path / "history.dat"
    interface_path = path / "interface.dat"
    history = read_numeric_history(history_path)
    if any(row[2] != -1.0 for row in history):
        raise ValueError(f"unexpected non-placeholder circularity column: {history_path}")
    reference = read_numeric_history(
        dataset_root / f"case{case}/reference/hysing/history.dat"
    )
    comparison_start = max(history[0][0], reference[0][0])
    comparison_end = min(history[-1][0], reference[-1][0], 3.0)
    selected = [
        row for row in history if comparison_start <= row[0] <= comparison_end
    ]
    if not selected or abs(history[-1][0] - 3.0) > 1e-9:
        raise ValueError(f"incomplete formal history: {history_path}")
    segments = facet_segments(interface_path)
    phi_final = final_circularity(history[-1][1], half_perimeter(segments))
    reference_phi_final = interpolate(reference, 3.0, 2)
    reference_to_t3 = [row for row in reference if row[0] <= 3.0]
    reference_minimum = min(reference_to_t3, key=lambda row: row[2])
    return {
        "benchmark": benchmark,
        "method_id": method,
        "resolution": resolution,
        "imax": imax,
        "terminal_time": history[-1][0],
        "dynamics_samples": len(selected),
        "comparison_start": comparison_start,
        "comparison_end": comparison_end,
        "max_abs_relative_volume_error": max(abs(row[1]) for row in history),
        "velocity_reference_rmse": rmse(
            row[4] - interpolate(reference, row[0], 4) for row in selected
        ),
        "center_reference_rmse": rmse(
            row[3] - interpolate(reference, row[0], 3) for row in selected
        ),
        "circularity_final": phi_final,
        "reference_circularity_final": reference_phi_final,
        "circularity_final_abs_error": abs(phi_final - reference_phi_final),
        "reference_circularity_min_to_t3": reference_minimum[2],
        "reference_time_at_circularity_min_to_t3": reference_minimum[0],
        "numerical_circularity_history_available": False,
        "facet_segments": len(segments),
        "result_dir": display_path(path),
        "history_sha256": sha256_file(history_path),
        "interface_sha256": sha256_file(interface_path),
    }


def build_rows(dataset_root: Path) -> list[dict[str, object]]:
    rows = [
        summarize_one(dataset_root, benchmark, method, resolution, imax)
        for benchmark in BENCHMARKS
        for resolution in RESOLUTIONS
        for imax in IMAX_VALUES
        for method in METHODS
    ]
    if len(rows) != 96:
        raise AssertionError(f"expected 96 rows, got {len(rows)}")
    return rows


def paired_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    indexed = {
        (
            str(row["benchmark"]),
            int(row["resolution"]),
            int(row["imax"]),
            str(row["method_id"]),
        ): row
        for row in rows
    }
    output: list[dict[str, object]] = []
    for benchmark in BENCHMARKS:
        for resolution in RESOLUTIONS:
            for imax in IMAX_VALUES:
                native = indexed[(benchmark, resolution, imax, "clsvof")]
                nn = indexed[
                    (benchmark, resolution, imax, "nn")
                ]
                record: dict[str, object] = {
                    "benchmark": benchmark,
                    "resolution": resolution,
                    "imax": imax,
                    "terminal_time_clsvof": native["terminal_time"],
                    "terminal_time_nn": nn["terminal_time"],
                    "circularity_final_clsvof": native["circularity_final"],
                    "circularity_final_nn": nn["circularity_final"],
                    "reference_circularity_final": native[
                        "reference_circularity_final"
                    ],
                }
                for metric in ERROR_METRICS:
                    clsvof = float(native[metric])
                    nn_value = float(nn[metric])
                    record[f"{metric}_clsvof"] = clsvof
                    record[f"{metric}_nn"] = nn_value
                    record[f"{metric}_nn_improvement_percent"] = (
                        100.0 * (clsvof - nn_value) / clsvof
                    )
                output.append(record)
    return output


def paired_fields() -> tuple[str, ...]:
    fields = [
        "benchmark",
        "resolution",
        "imax",
        "terminal_time_clsvof",
        "terminal_time_nn",
        "circularity_final_clsvof",
        "circularity_final_nn",
        "reference_circularity_final",
    ]
    for metric in ERROR_METRICS:
        fields.extend(
            (
                f"{metric}_clsvof",
                f"{metric}_nn",
                f"{metric}_nn_improvement_percent",
            )
        )
    return tuple(fields)


def write_representative_sources(
    dataset_root: Path, output_dir: Path, resolution: int
) -> None:
    dynamics_rows: list[dict[str, object]] = []
    circularity_rows: list[dict[str, object]] = []
    interface_rows: list[dict[str, object]] = []
    for case, benchmark in enumerate(BENCHMARKS, start=1):
        reference = read_numeric_history(
            dataset_root / f"case{case}/reference/hysing/history.dat"
        )
        for row in reference:
            if row[0] > 3.0:
                continue
            dynamics_rows.append(
                {
                    "benchmark": benchmark,
                    "method_id": "reference",
                    "imax": "reference",
                    "time": row[0],
                    "relative_volume_error": row[1],
                    "center_height": row[3],
                    "rise_velocity": row[4],
                }
            )
            circularity_rows.append(
                {
                    "benchmark": benchmark,
                    "method_id": "reference",
                    "imax": "reference",
                    "time": row[0],
                    "circularity": row[2],
                    "availability": "history",
                }
            )
        for index, segment in enumerate(reference_interface_segments(case)):
            interface_rows.append(
                {
                    "benchmark": benchmark,
                    "method_id": "reference",
                    "imax": "reference",
                    "segment": index,
                    "vertical0": segment[0],
                    "transverse0": segment[1],
                    "vertical1": segment[2],
                    "transverse1": segment[3],
                }
            )
        for imax in (0, 3):
            for method in METHODS:
                path = dataset_path(
                    dataset_root, benchmark, method, resolution, imax
                )
                history = read_numeric_history(path / "history.dat")
                for row in history:
                    dynamics_rows.append(
                        {
                            "benchmark": benchmark,
                            "method_id": method,
                            "imax": imax,
                            "time": row[0],
                            "relative_volume_error": row[1],
                            "center_height": row[3],
                            "rise_velocity": row[4],
                        }
                    )
                segments = facet_segments(path / "interface.dat")
                circularity_rows.append(
                    {
                        "benchmark": benchmark,
                        "method_id": method,
                        "imax": imax,
                        "time": 3.0,
                        "circularity": final_circularity(
                            history[-1][1], half_perimeter(segments)
                        ),
                        "availability": "final_only",
                    }
                )
                for index, segment in enumerate(segments):
                    interface_rows.append(
                        {
                            "benchmark": benchmark,
                            "method_id": method,
                            "imax": imax,
                            "segment": index,
                            "vertical0": segment[0],
                            "transverse0": segment[1],
                            "vertical1": segment[2],
                            "transverse1": segment[3],
                        }
                    )
    atomic_csv(
        output_dir / f"dynamics_N{resolution}_imax0_vs3.csv",
        dynamics_rows,
        (
            "benchmark",
            "method_id",
            "imax",
            "time",
            "relative_volume_error",
            "center_height",
            "rise_velocity",
        ),
    )
    atomic_csv(
        output_dir / f"circularity_N{resolution}_imax0_vs3.csv",
        circularity_rows,
        ("benchmark", "method_id", "imax", "time", "circularity", "availability"),
    )
    atomic_csv(
        output_dir / f"interfaces_N{resolution}_imax0_vs3.csv",
        interface_rows,
        (
            "benchmark",
            "method_id",
            "imax",
            "segment",
            "vertical0",
            "transverse0",
            "vertical1",
            "transverse1",
        ),
    )


def metric_contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": "dataset/rising_bubble formal history.dat and final interface.dat",
        "bubble_indicator": "1-f",
        "metrics": {
            "volume": "E_V,max = max_j |epsilon_V(t_j)|",
            "velocity": "RMSE of V_c against linearly interpolated Hysing reference",
            "center": "RMSE of z_c against linearly interpolated Hysing reference",
            "circularity": (
                "phi_c(3)=2*sqrt(pi*A_b(3))/P_b(3); main scalar is "
                "|phi_c(3)-phi_c_ref(3)|"
            ),
        },
        "circularity_availability": {
            "numerical": "t=3 only; history.dat column 3 is -1 placeholder",
            "reference": "full Hysing history through t=3",
            "phi_min_numerical": "not recoverable from the archived formal dataset",
        },
        "heatmap": (
            "NN improvement (%) = 100*(E_CLSVOF-E_NN)/E_CLSVOF; positive is better"
        ),
        "display_scope": {
            "heatmap_imax": list(IMAX_VALUES),
            "curve_imax": [3, 0],
            "method_encoding": "CLSVOF solid; NN dashed",
            "imax_encoding": "imax=3 blue; imax=0 orange",
        },
        "chamfer_role": "supplementary only and excluded from the main figure",
    }


def source_audit(dataset_root: Path) -> dict[str, object]:
    matrix_paths = [
        dataset_path(dataset_root, benchmark, method, resolution, imax)
        for benchmark in BENCHMARKS
        for resolution in RESOLUTIONS
        for imax in IMAX_VALUES
        for method in METHODS
    ]
    time_resolved_interfaces = [
        display_path(path)
        for matrix_path in matrix_paths
        for path in matrix_path.iterdir()
        if path.is_file()
        and path.name != "interface.dat"
        and any(
            token in path.name.lower()
            for token in ("interface", "facet", "snapshot")
        )
    ]
    reference_validation: dict[str, object] = {}
    for case, benchmark in enumerate(BENCHMARKS, start=1):
        segments = reference_interface_segments(case)
        perimeter = sum(
            math.hypot(vertical1 - vertical0, transverse1 - transverse0)
            for vertical0, transverse0, vertical1, transverse1 in segments
        )
        phi_from_interface = 2.0 * math.sqrt(
            math.pi * INITIAL_FULL_AREA
        ) / perimeter
        reference = read_numeric_history(
            dataset_root / f"case{case}/reference/hysing/history.dat"
        )
        phi_from_history = interpolate(reference, 3.0, 2)
        reference_validation[benchmark] = {
            "phi_from_t3_interface": phi_from_interface,
            "phi_from_history_at_t3": phi_from_history,
            "absolute_difference": abs(phi_from_interface - phi_from_history),
        }
    return {
        "schema_version": 1,
        "formal_matrix_groups": len(matrix_paths),
        "formal_history_files": sum(
            (path / "history.dat").is_file() for path in matrix_paths
        ),
        "formal_final_interface_files": sum(
            (path / "interface.dat").is_file() for path in matrix_paths
        ),
        "numerical_circularity_history_samples": 0,
        "history_circularity_column": "all numerical values are -1 placeholders",
        "numerical_time_resolved_interface_files": len(time_resolved_interfaces),
        "time_resolved_interface_candidates": time_resolved_interfaces,
        "recoverable_from_formal_dataset": {
            "relative_volume_error_history": True,
            "rise_velocity_history": True,
            "center_height_history": True,
            "circularity_history": False,
            "circularity_at_t3": True,
            "final_interface_at_t3": True,
            "numerical_circularity_minimum": False,
            "numerical_time_at_circularity_minimum": False,
        },
        "reference_t3_circularity_validation": reference_validation,
        "nonformal_recomputations_used": False,
        "minimum_new_data_for_full_numerical_circularity_curve": {
            "requires_new_solver_output": True,
            "representative_resolution": 512,
            "benchmarks": list(BENCHMARKS),
            "methods": list(METHODS),
            "imax": [3, 0],
            "row_count": len(BENCHMARKS) * len(METHODS) * 2,
            "required_artifact": "circularity.csv sampled every solver iteration from t=0 through t=3",
            "executed": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--representative-resolution", type=int, default=512)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = build_rows(args.dataset_root)
    pairs = paired_rows(rows)
    atomic_csv(args.output_dir / "benchmark_metrics.csv", rows, SUMMARY_FIELDS)
    atomic_csv(args.output_dir / "imax_metrics.csv", pairs, paired_fields())
    atomic_json(args.output_dir / "metric_contract.json", metric_contract())
    atomic_json(args.output_dir / "source_audit.json", source_audit(args.dataset_root))
    write_representative_sources(
        args.dataset_root, args.output_dir, args.representative_resolution
    )
    print(f"rows={len(rows)} pairs={len(pairs)} source={args.dataset_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
