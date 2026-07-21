#!/usr/bin/env python3
"""Build traceable rising-bubble figure source data from formal result bundles."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = ("rising_case1", "rising_case2")
METHODS = ("clsvof", "nn")
RESOLUTIONS = (64, 128, 256, 512)
IMAX_VALUES = tuple(range(6))

SUMMARY_FIELDS = (
    "benchmark",
    "method_id",
    "resolution",
    "imax",
    "terminal_time",
    "dynamics_samples",
    "circularity_samples",
    "circularity_sampling",
    "comparison_start",
    "comparison_end",
    "max_abs_relative_volume_error",
    "velocity_reference_rmse",
    "center_reference_rmse",
    "circularity_reference_rmse",
    "circularity_min",
    "time_at_circularity_min",
    "reference_circularity_min",
    "reference_time_at_circularity_min",
    "facet_segments",
    "result_dir",
    "stdout_sha256",
    "circularity_sha256",
    "log_sha256",
)

ERROR_METRICS = (
    "max_abs_relative_volume_error",
    "velocity_reference_rmse",
    "center_reference_rmse",
    "circularity_reference_rmse",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite value: {value}")
    return parsed


def read_numeric_history(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        try:
            values = [finite(value) for value in fields[:5]]
        except ValueError:
            continue
        rows.append(values)
    if not rows:
        raise ValueError(f"no numeric history rows: {path}")
    if any(right[0] <= left[0] for left, right in zip(rows, rows[1:])):
        raise ValueError(f"history time is not strictly increasing: {path}")
    return rows


def read_circularity(path: Path) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    with path.open(newline="", encoding="utf-8") as stream:
        for raw in csv.DictReader(stream):
            row = {
                "time": finite(raw["time"]),
                "iteration": int(raw["iteration"]),
                "half_area": finite(raw["half_area"]),
                "half_perimeter": finite(raw["half_perimeter"]),
                "circularity": finite(raw["circularity"]),
            }
            if float(row["circularity"]) <= 0.0:
                raise ValueError(f"nonpositive circularity in {path}: {row}")
            rows.append(row)
    if len(rows) < 2:
        raise ValueError(f"incomplete circularity history: {path}")
    times = [float(row["time"]) for row in rows]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError(f"circularity time is not strictly increasing: {path}")
    if abs(times[0]) > 1e-12 or abs(times[-1] - 3.0) > 1e-9:
        raise ValueError(f"circularity does not cover t=0 through t=3: {path}")
    return rows


def interpolate(history: list[list[float]], time: float, column: int) -> float:
    times = [row[0] for row in history]
    index = bisect.bisect_left(times, time)
    if index == 0:
        return history[0][column]
    if index == len(history):
        return history[-1][column]
    left, right = history[index - 1], history[index]
    fraction = (time - left[0]) / (right[0] - left[0])
    return left[column] * (1.0 - fraction) + right[column] * fraction


def rmse(values: Iterable[float]) -> float:
    selected = list(values)
    if not selected:
        raise ValueError("cannot compute RMSE from zero samples")
    return math.sqrt(sum(value * value for value in selected) / len(selected))


def facet_segments(path: Path) -> list[tuple[float, float, float, float]]:
    segments: list[tuple[float, float, float, float]] = []
    current: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("kappa_offset_provider_stats ")
        ):
            if len(current) == 2:
                segments.append((*current[0], *current[1]))
            current = []
            continue
        fields = stripped.split()
        if len(fields) != 2:
            if len(current) == 2:
                segments.append((*current[0], *current[1]))
            current = []
            continue
        try:
            point = (finite(fields[0]), finite(fields[1]))
        except ValueError:
            current = []
            continue
        current.append(point)
        if len(current) == 2:
            segments.append((*current[0], *current[1]))
            current = []
    if len(current) == 2:
        segments.append((*current[0], *current[1]))
    if not segments:
        raise ValueError(f"no final interface segments: {path}")
    return segments


def generator_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("generator_manifest")
    return nested if isinstance(nested, dict) else payload


def result_identity(manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    generator = generator_manifest(payload)
    return payload, generator


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def summarize_result(path: Path, generator: dict[str, Any]) -> dict[str, object]:
    benchmark = str(generator["benchmark"])
    case = 1 if benchmark == "rising_case1" else 2
    method = str(generator["method"])
    resolution = int(generator["resolution"])
    imax = int(generator["imax"])

    stdout = path / "stdout.txt"
    circularity_path = path / "circularity.csv"
    log = path / "log"
    dynamics = read_numeric_history(stdout)
    circularity = read_circularity(circularity_path)
    reference = read_numeric_history(
        ROOT / f"dataset/rising_bubble/case{case}/reference/hysing/history.dat"
    )
    comparison_start = max(dynamics[0][0], reference[0][0])
    comparison_end = min(dynamics[-1][0], reference[-1][0])
    selected_dynamics = [
        row for row in dynamics if comparison_start <= row[0] <= comparison_end
    ]
    selected_circularity = [
        row
        for row in circularity
        if comparison_start <= float(row["time"]) <= comparison_end
    ]
    if not selected_dynamics or not selected_circularity:
        raise ValueError(f"no samples overlap the Case {case} reference: {path}")
    circ_min_row = min(circularity, key=lambda row: float(row["circularity"]))
    terminal_time = dynamics[-1][0]
    reference_window = [row for row in reference if row[0] <= terminal_time + 1e-12]
    if not reference_window:
        raise ValueError(f"reference does not overlap terminal time: {path}")
    reference_min_row = min(reference_window, key=lambda row: row[2])
    segments = facet_segments(log)
    return {
        "benchmark": benchmark,
        "method_id": method,
        "resolution": resolution,
        "imax": imax,
        "terminal_time": terminal_time,
        "dynamics_samples": len(selected_dynamics),
        "circularity_samples": len(selected_circularity),
        "circularity_sampling": str(generator["circularity_sampling"]),
        "comparison_start": comparison_start,
        "comparison_end": comparison_end,
        "max_abs_relative_volume_error": max(abs(row[1]) for row in dynamics),
        "velocity_reference_rmse": rmse(
            row[4] - interpolate(reference, row[0], 4)
            for row in selected_dynamics
        ),
        "center_reference_rmse": rmse(
            row[3] - interpolate(reference, row[0], 3)
            for row in selected_dynamics
        ),
        "circularity_reference_rmse": rmse(
            float(row["circularity"])
            - interpolate(reference, float(row["time"]), 2)
            for row in selected_circularity
        ),
        "circularity_min": float(circ_min_row["circularity"]),
        "time_at_circularity_min": float(circ_min_row["time"]),
        "reference_circularity_min": reference_min_row[2],
        "reference_time_at_circularity_min": reference_min_row[0],
        "facet_segments": len(segments),
        "result_dir": display_path(path),
        "stdout_sha256": sha256_file(stdout),
        "circularity_sha256": sha256_file(circularity_path),
        "log_sha256": sha256_file(log),
    }


def atomic_csv(path: Path, rows: list[dict[str, object]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def paired_metrics(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    indexed = {
        (
            str(row["benchmark"]),
            int(row["resolution"]),
            int(row["imax"]),
            str(row["method_id"]),
        ): row
        for row in rows
    }
    paired: list[dict[str, object]] = []
    for benchmark in BENCHMARKS:
        for resolution in RESOLUTIONS:
            for imax in IMAX_VALUES:
                native = indexed.get(
                    (benchmark, resolution, imax, "clsvof")
                )
                nn = indexed.get(
                    (benchmark, resolution, imax, "nn")
                )
                if native is None and nn is None:
                    continue
                if native is None or nn is None:
                    raise ValueError(
                        f"unpaired rising result: {benchmark}, N{resolution}, imax={imax}"
                    )
                record: dict[str, object] = {
                    "benchmark": benchmark,
                    "resolution": resolution,
                    "imax": imax,
                    "terminal_time_clsvof": native["terminal_time"],
                    "terminal_time_nn": nn["terminal_time"],
                    "circularity_min_clsvof": native["circularity_min"],
                    "time_at_circularity_min_clsvof": native[
                        "time_at_circularity_min"
                    ],
                    "circularity_min_nn": nn["circularity_min"],
                    "time_at_circularity_min_nn": nn["time_at_circularity_min"],
                }
                for metric in ERROR_METRICS:
                    clsvof_value = float(native[metric])
                    nn_value = float(nn[metric])
                    record[f"{metric}_clsvof"] = clsvof_value
                    record[f"{metric}_nn"] = nn_value
                    record[f"{metric}_nn_improvement_percent"] = (
                        100.0 * (clsvof_value - nn_value) / clsvof_value
                    )
                paired.append(record)
    return paired


def paired_fields() -> tuple[str, ...]:
    fields = [
        "benchmark",
        "resolution",
        "imax",
        "terminal_time_clsvof",
        "terminal_time_nn",
        "circularity_min_clsvof",
        "time_at_circularity_min_clsvof",
        "circularity_min_nn",
        "time_at_circularity_min_nn",
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


def metric_contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "bubble_indicator": "1 - f",
        "time_window": "numerical/reference overlap, ending at t=3",
        "reference_interpolation": (
            "piecewise linear at each numerical sample time in the overlap window"
        ),
        "metrics": {
            "relative_volume_error": {
                "formula": "epsilon_V(t) = (V_b(t) - V_b(0)) / V_b(0)",
                "scalar": "max_abs_relative_volume_error = max_j |epsilon_V(t_j)|",
            },
            "rise_velocity": {
                "formula": "V_c(t) = integral((1-f) u_z dOmega) / integral((1-f) dOmega)",
                "scalar": "velocity_reference_rmse = sqrt(mean((V_c - V_c_ref)^2))",
            },
            "center_height": {
                "formula": "z_c(t) = integral((1-f) z dOmega) / integral((1-f) dOmega)",
                "scalar": "center_reference_rmse = sqrt(mean((z_c - z_c_ref)^2))",
            },
            "circularity": {
                "formula": "phi_c(t) = 2 sqrt(pi A_b) / P_b",
                "half_domain_reconstruction": "A_b=2*sb; P_b=2*interface_area(f)",
                "implemented_formula": "phi_c = sqrt(2*pi*sb) / interface_area(f)",
                "sampling": "every original solver iteration, plus exact t=3",
                "scalar_for_comparison": (
                    "circularity_reference_rmse = sqrt(mean((phi_c - phi_c_ref)^2))"
                ),
                "reported_minimum": (
                    "circularity_min and time_at_circularity_min over recorded samples"
                ),
            },
        },
        "heatmap": (
            "NN improvement (%) = 100*(E_CLSVOF - E_NN)/E_CLSVOF; positive is better"
        ),
        "chamfer_role": "supplementary only; excluded from the main four-metric figures",
    }


def discover(results_root: Path) -> dict[tuple[str, str, int, int], Path]:
    selected: dict[tuple[str, str, int, int], Path] = {}
    for manifest_path in results_root.rglob("manifest.json"):
        _, generator = result_identity(manifest_path)
        benchmark = str(generator.get("benchmark", ""))
        method = str(generator.get("method", ""))
        if benchmark not in BENCHMARKS or method not in METHODS:
            continue
        key = (
            benchmark,
            method,
            int(generator["resolution"]),
            int(generator["imax"]),
        )
        if key in selected:
            raise ValueError(f"duplicate result identity {key}: {selected[key]}, {manifest_path.parent}")
        selected[key] = manifest_path.parent
    return selected


def expected_keys() -> set[tuple[str, str, int, int]]:
    return {
        (benchmark, method, resolution, imax)
        for benchmark in BENCHMARKS
        for method in METHODS
        for resolution in RESOLUTIONS
        for imax in IMAX_VALUES
    }


def representative_keys(resolution: int) -> set[tuple[str, str, int, int]]:
    return {
        (benchmark, method, resolution, imax)
        for benchmark in BENCHMARKS
        for method in METHODS
        for imax in (0, 3)
    }


def reference_interface_segments(
    case: int,
) -> list[tuple[float, float, float, float]]:
    points: list[tuple[float, float]] = []
    path = ROOT / f"dataset/rising_bubble/case{case}/reference/hysing/interface.dat"
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        transverse_raw, vertical = (finite(value) for value in line.split()[:2])
        transverse = transverse_raw - 0.5
        point = (vertical, transverse)
        if not points or point != points[-1]:
            points.append(point)
    if len(points) < 2:
        raise ValueError(f"no reference interface points: {path}")
    return [(*left, *right) for left, right in zip(points, points[1:])]


def write_representative_sources(
    output_dir: Path,
    discovered: dict[tuple[str, str, int, int], Path],
    resolution: int,
) -> None:
    dynamics_rows: list[dict[str, object]] = []
    circularity_rows: list[dict[str, object]] = []
    interface_rows: list[dict[str, object]] = []
    for case, benchmark in enumerate(BENCHMARKS, start=1):
        reference = read_numeric_history(
            ROOT / f"dataset/rising_bubble/case{case}/reference/hysing/history.dat"
        )
        for row in reference:
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
                key = (benchmark, method, resolution, imax)
                if key not in discovered:
                    raise ValueError(f"missing representative result: {key}")
                path = discovered[key]
                for row in read_numeric_history(path / "stdout.txt"):
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
                for row in read_circularity(path / "circularity.csv"):
                    circularity_rows.append(
                        {
                            "benchmark": benchmark,
                            "method_id": method,
                            "imax": imax,
                            "time": row["time"],
                            "circularity": row["circularity"],
                        }
                    )
                for index, segment in enumerate(facet_segments(path / "log")):
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
            "benchmark", "method_id", "imax", "time",
            "relative_volume_error", "center_height", "rise_velocity",
        ),
    )
    atomic_csv(
        output_dir / f"circularity_N{resolution}_imax0_vs3.csv",
        circularity_rows,
        ("benchmark", "method_id", "imax", "time", "circularity"),
    )
    atomic_csv(
        output_dir / f"interfaces_N{resolution}_imax0_vs3.csv",
        interface_rows,
        (
            "benchmark", "method_id", "imax", "segment",
            "vertical0", "transverse0", "vertical1", "transverse1",
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "figures/rising_bubble/shared_data",
    )
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--representative-resolution", type=int, default=512)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    discovered = discover(args.results_root)
    expected = expected_keys()
    missing = expected - set(discovered)
    unexpected = set(discovered) - expected
    if unexpected:
        raise SystemExit(f"unexpected rising identities: {sorted(unexpected)}")
    if missing and not args.allow_partial:
        raise SystemExit(f"missing {len(missing)} of 96 rising results")
    rows: list[dict[str, object]] = []
    for key, path in discovered.items():
        _, generator = result_identity(path / "manifest.json")
        row = summarize_result(path, generator)
        if tuple(row[field] for field in ("benchmark", "method_id", "resolution", "imax")) != key:
            raise ValueError(f"summary identity mismatch: {key}, {row}")
        rows.append(row)
    rows.sort(key=lambda row: (
        str(row["benchmark"]), int(row["resolution"]), int(row["imax"]), str(row["method_id"])
    ))
    atomic_csv(args.output_dir / "benchmark_metrics.csv", rows, SUMMARY_FIELDS)
    paired = paired_metrics(rows)
    atomic_csv(args.output_dir / "imax_metrics.csv", paired, paired_fields())
    atomic_json(args.output_dir / "metric_contract.json", metric_contract())
    if representative_keys(args.representative_resolution) <= set(discovered):
        write_representative_sources(
            args.output_dir, discovered, args.representative_resolution
        )
    print(
        f"rows={len(rows)} pairs={len(paired)} missing={len(missing)} "
        f"output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
