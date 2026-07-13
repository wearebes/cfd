#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from bisect import bisect_left
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_MATRIX = HERE / "config/matrix.json"


def percentile(values: Iterable[float], probability: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def result_dir(base: Path, row: dict[str, Any]) -> Path:
    return (
        base
        / str(row["benchmark"])
        / f"N{int(row['N']):04d}"
        / f"imax{int(row['imax']):02d}"
        / str(row["method"])
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def finite(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return value


def diagnostic_summary(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    metrics_path = path / "redistance_metrics.csv"
    trace_path = path / "redistance_return_trace.csv"
    if not metrics_path.is_file() or not trace_path.is_file():
        return {}

    with metrics_path.open(newline="", encoding="utf-8") as stream:
        metrics = list(csv.DictReader(stream))
    with trace_path.open(newline="", encoding="utf-8") as stream:
        trace = list(csv.DictReader(stream))

    imax = int(row["imax"])
    returned = [int(item["returned_steps"]) for item in trace]
    distribution = Counter(returned)
    expected_final = 2.2426211256 if row["benchmark"] == "capwave" else 3.0
    final_metric_records = {
        (item["stage"], item["band_cells"])
        for item in metrics
        if abs(float(item["t"]) - expected_final) <= 1e-8
    }
    initial_metric_records = {
        (item["stage"], item["band_cells"])
        for item in metrics
        if abs(float(item["t"])) <= 1e-12
    }
    summary: dict[str, Any] = {
        "return_calls": len(returned),
        "returned_min": min(returned) if returned else None,
        "returned_max": max(returned) if returned else None,
        "returned_mean": sum(returned) / len(returned) if returned else None,
        "returned_distribution": json.dumps(dict(sorted(distribution.items()))),
        "return_contract_ok": bool(returned)
        and (
            all(value == 0 for value in returned)
            if imax == 0
            else all(1 <= value <= imax for value in returned)
        ),
        "initial_diagnostic_ok": {
            ("pre", "1.5"), ("pre", "3.0"), ("post", "1.5"), ("post", "3.0")
        }.issubset(initial_metric_records),
        "final_diagnostic_ok": {
            ("pre", "1.5"), ("pre", "3.0"), ("post", "1.5"), ("post", "3.0")
        }.issubset(final_metric_records),
        "final_metric_time": max(float(item["t"]) for item in metrics),
        "final_trace_time": float(trace[-1]["t"]) if trace else None,
        "final_trace_ok": bool(trace) and abs(float(trace[-1]["t"]) - expected_final) <= 1e-8,
    }
    for band, label in ((1.5, "b15"), (3.0, "b30")):
        selected = [
            item
            for item in metrics
            if item["stage"] == "post" and abs(float(item["band_cells"]) - band) < 1e-12
        ]
        if not selected:
            continue
        egrad_means = [float(item["Egrad_mean"]) for item in selected]
        egrad_rms = [float(item["Egrad_rms"]) for item in selected]
        summary.update(
            {
                f"post_{label}_samples": len(selected),
                f"post_{label}_egrad_mean": sum(egrad_means) / len(egrad_means),
                f"post_{label}_egrad_rms": math.sqrt(
                    sum(value * value for value in egrad_rms) / len(egrad_rms)
                ),
                f"post_{label}_egrad_mean_p95": percentile(egrad_means, 0.95),
                f"post_{label}_egrad_linf": max(float(item["Egrad_linf"]) for item in selected),
                f"post_{label}_grad_min": min(float(item["grad_min"]) for item in selected),
                f"post_{label}_grad_max": max(float(item["grad_max"]) for item in selected),
                f"post_{label}_phi_change_mean": sum(
                    float(item["phi_change_mean"]) for item in selected
                )
                / len(selected),
                f"post_{label}_phi_change_linf": max(
                    float(item["phi_change_linf"]) for item in selected
                ),
                f"post_{label}_sign_mismatch_sum": sum(
                    int(item["sign_mismatch"]) for item in selected
                ),
                f"post_{label}_volume_rel_diff_linf": max(
                    abs(float(item["volume_rel_diff"])) for item in selected
                ),
            }
        )
    return summary


def provider_summary(path: Path) -> dict[str, int | None]:
    log = path / "log"
    if not log.is_file():
        return {"provider_evaluations": None, "provider_clamp_hits": None}
    matches = re.findall(
        r"kappa_offset_provider_stats evaluations=(\d+) clamp_hits=(\d+)",
        log.read_text(encoding="utf-8"),
    )
    if not matches:
        return {"provider_evaluations": None, "provider_clamp_hits": None}
    evaluations, clamp_hits = matches[-1]
    return {
        "provider_evaluations": int(evaluations),
        "provider_clamp_hits": int(clamp_hits),
    }


def performance_summary(path: Path) -> dict[str, float | int]:
    pattern = re.compile(
        r"# Multigrid,\s*(\d+) steps,\s*([-+0-9.eE]+) CPU,\s*([-+0-9.eE]+) real,"
    )
    for name in ("out", "log"):
        source = path / name
        if not source.is_file():
            continue
        match = pattern.search(source.read_text(encoding="utf-8"))
        if match:
            return {
                "solver_steps": int(match.group(1)),
                "stock_cpu_seconds": float(match.group(2)),
                "stock_real_seconds": float(match.group(3)),
            }
    return {}


def read_facet_segments(path: Path) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    current: list[tuple[float, float]] = []

    def flush() -> None:
        for index in range(len(current) - 1):
            segments.append((current[index], current[index + 1]))
        current.clear()

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("kappa_offset_provider_stats ")
        ):
            flush()
            continue
        parts = stripped.split()
        try:
            current.append((float(parts[0]), float(parts[1])))
        except (ValueError, IndexError):
            flush()
    flush()
    return segments


def read_moonmd_points(path: Path) -> list[tuple[float, float]]:
    points = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        raw0, raw1 = (float(value) for value in stripped.split()[:2])
        points.append((raw1, raw0 - 0.5))
    return points


def point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-300:
        return math.hypot(px - ax, py - ay)
    projection = ((px - ax) * dx + (py - ay) * dy) / length_sq
    projection = max(0.0, min(1.0, projection))
    closest = (ax + projection * dx, ay + projection * dy)
    return math.hypot(px - closest[0], py - closest[1])


def shape_summary(path: Path) -> dict[str, float]:
    segments = read_facet_segments(path / "log")
    reference = read_moonmd_points(
        ROOT / "dataset/official_data/rising_bubble/sources/c1g3l4s.txt"
    )
    if not segments or not reference:
        return {}
    distances = [
        min(point_segment_distance(point, start, end) for start, end in segments)
        for point in reference
    ]
    return {
        "shape_mean_distance": sum(distances) / len(distances),
        "shape_max_distance": max(distances),
        "shape_reference_points": len(reference),
        "shape_facets": len(segments),
    }


def read_hysing_history(path: Path) -> list[tuple[float, float, float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        values = [float(value) for value in line.split()[:5]]
        if len(values) == 5 and all(math.isfinite(value) for value in values):
            rows.append((values[0], values[3], values[4]))
    return rows


def interpolate(history: list[tuple[float, float, float]], time: float, column: int) -> float:
    times = [row[0] for row in history]
    index = bisect_left(times, time)
    if index == 0:
        return history[0][column]
    if index == len(history):
        return history[-1][column]
    left, right = history[index - 1], history[index]
    fraction = (time - left[0]) / (right[0] - left[0])
    return left[column] * (1.0 - fraction) + right[column] * fraction


def hysing_reference_summary(samples: list[list[float]]) -> dict[str, float | int]:
    history = read_hysing_history(
        ROOT / "dataset/official_data/rising_bubble/sources/c1g3l4.txt"
    )
    selected = [sample for sample in samples if history[0][0] <= sample[0] <= history[-1][0]]
    if not selected:
        return {}
    center_errors = [
        sample[3] - interpolate(history, sample[0], 1) for sample in selected
    ]
    velocity_errors = [
        sample[4] - interpolate(history, sample[0], 2) for sample in selected
    ]
    final_center_reference = interpolate(history, 3.0, 1)
    final_velocity_reference = interpolate(history, 3.0, 2)
    return {
        "reference_history_samples": len(selected),
        "center_reference_rmse": math.sqrt(
            sum(value * value for value in center_errors) / len(center_errors)
        ),
        "velocity_reference_rmse": math.sqrt(
            sum(value * value for value in velocity_errors) / len(velocity_errors)
        ),
        "center_reference_linf": max(abs(value) for value in center_errors),
        "velocity_reference_linf": max(abs(value) for value in velocity_errors),
        "final_center_reference": final_center_reference,
        "final_velocity_reference": final_velocity_reference,
        "final_center_reference_error": samples[-1][3] - final_center_reference,
        "final_velocity_reference_error": samples[-1][4] - final_velocity_reference,
    }


def read_prosperetti(path: Path) -> list[tuple[float, float]]:
    points = []
    pattern = re.compile(
        r"\{\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*\}"
    )
    for match in pattern.finditer(path.read_text(encoding="utf-8")):
        points.append((float(match.group(1)), float(match.group(2))))
    return points


def capwave_reference_summary(path: Path, row: dict[str, Any]) -> dict[str, float | int]:
    samples = []
    for line in (path / f"wave-{row['N']}").read_text(encoding="utf-8").splitlines():
        values = [float(value) for value in line.split()[:2]]
        if len(values) == 2 and all(math.isfinite(value) for value in values):
            samples.append((values[0], values[1]))
    reference_path = path / "prosperetti.h"
    if not reference_path.is_file():
        reference_path = ROOT / "basilisk/src/test/prosperetti.h"
    reference = read_prosperetti(reference_path)
    if not samples or len(samples) > len(reference):
        return {}
    errors = [sample[1] - reference[index][1] for index, sample in enumerate(samples)]
    l2 = math.sqrt(sum(value * value for value in errors) / len(errors))
    return {
        "reference_samples": len(errors),
        "amplitude_l2_error": l2,
        "relative_rms_recomputed": l2 / 0.01,
        "max_abs_amplitude_error": max(abs(value) for value in errors),
        "final_amplitude_error": errors[-1],
        "amplitude_error_bias": sum(errors) / len(errors),
    }


def physical_summary(path: Path, row: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    physical = dict(manifest.get("physical_validation", {}))
    if row["benchmark"] == "capwave":
        physical.update(capwave_reference_summary(path, row))
        return physical

    samples: list[list[float]] = []
    for line in (path / "out").read_text(encoding="utf-8").splitlines():
        try:
            values = [float(value) for value in line.split()[:5]]
        except ValueError:
            continue
        if len(values) == 5 and all(math.isfinite(value) for value in values):
            samples.append(values)
    if samples:
        peak = max(samples, key=lambda values: values[4])
        physical.update(
            {
                "max_abs_volume_drift": max(abs(values[1]) for values in samples),
                "peak_velocity": peak[4],
                "time_at_peak_velocity": peak[0],
            }
        )
        physical.update(hysing_reference_summary(samples))
    physical.update(shape_summary(path))
    return physical


def execution_state(path: Path, row: dict[str, Any]) -> str:
    status = path / "status.json"
    if status.is_file():
        return str(read_json(status).get("state", "invalid_status"))
    return "reuse_pending" if row["planning_status"] == "candidate_reuse" else "planned"


def collect_row(result_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    path = result_dir(result_root, row)
    state = execution_state(path, row)
    record: dict[str, Any] = {
        "row_id": row["row_id"],
        "benchmark": row["benchmark"],
        "method": row["method"],
        "N": row["N"],
        "LEVEL": row.get("LEVEL"),
        "actual_grid": row["actual_grid"],
        "imax": row["imax"],
        "planning_status": row["planning_status"],
        "execution_state": state,
    }
    status_path = path / "status.json"
    if status_path.is_file():
        status = read_json(status_path)
        record.update(
            {
                "compile_seconds": finite(status.get("compile_seconds")),
                "run_seconds": finite(status.get("run_seconds")),
                "error": status.get("error"),
            }
        )
    if state != "completed":
        return record

    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        record["execution_state"] = "invalid_missing_manifest"
        return record
    manifest = read_json(manifest_path)
    record.update(physical_summary(path, row, manifest))
    record.update(performance_summary(path))
    record.update(provider_summary(path))
    record.update(diagnostic_summary(path, row))
    return record


def atomic_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def ordered_fields(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "row_id", "benchmark", "method", "N", "LEVEL", "actual_grid", "imax",
        "planning_status", "execution_state", "compile_seconds", "run_seconds",
        "solver_steps", "stock_cpu_seconds", "stock_real_seconds",
        "relative_rms", "relative_rms_recomputed", "amplitude_l2_error",
        "max_abs_amplitude_error", "final_amplitude_error", "amplitude_error_bias",
        "reference_samples", "wave_rows", "out_rows", "final_time", "final_volume_drift",
        "max_abs_volume_drift", "final_center", "final_velocity", "peak_velocity",
        "time_at_peak_velocity", "shape_mean_distance", "shape_max_distance",
        "shape_reference_points", "shape_facets",
        "center_reference_rmse", "velocity_reference_rmse", "center_reference_linf",
        "velocity_reference_linf", "final_center_reference",
        "final_velocity_reference", "final_center_reference_error",
        "final_velocity_reference_error", "reference_history_samples",
        "provider_evaluations", "provider_clamp_hits", "return_calls", "returned_min",
        "returned_max", "returned_mean", "returned_distribution", "return_contract_ok",
        "initial_diagnostic_ok", "final_diagnostic_ok", "final_metric_time",
        "final_trace_time", "final_trace_ok",
    ]
    discovered = {key for row in rows for key in row}
    return [key for key in preferred if key in discovered] + sorted(discovered - set(preferred))


def make_wide(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, int], dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((str(row["benchmark"]), int(row["N"]), int(row["imax"])), {})[
            str(row["method"])
        ] = row
    output = []
    for (benchmark, n, imax), methods in sorted(grouped.items()):
        record: dict[str, Any] = {"benchmark": benchmark, "N": n, "imax": imax}
        for method in ("clsvof_native", "clsvof_nn"):
            source = methods.get(method, {})
            prefix = "native" if method == "clsvof_native" else "nn"
            for key, value in source.items():
                if key not in {"row_id", "benchmark", "method", "N", "LEVEL", "actual_grid", "imax"}:
                    record[f"{prefix}_{key}"] = value
        output.append(record)
    return output


def make_long(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    identity = {
        "row_id",
        "benchmark",
        "method",
        "N",
        "LEVEL",
        "actual_grid",
        "imax",
        "planning_status",
        "execution_state",
        "error",
    }
    output: list[dict[str, Any]] = []
    for row in rows:
        base = {key: row.get(key) for key in ("row_id", "benchmark", "method", "N", "imax")}
        for key in sorted(set(row) - identity):
            value = row.get(key)
            if value is not None and value != "":
                output.append({**base, "metric": key, "value": value})
    return output


def make_runtime(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "row_id", "benchmark", "method", "N", "imax", "execution_state",
        "compile_seconds", "run_seconds", "solver_steps", "stock_cpu_seconds",
        "stock_real_seconds", "return_calls", "provider_evaluations",
    )
    return [{key: row.get(key) for key in fields} for row in rows]


def make_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terminal_failures = {
        "failed_compile",
        "failed_runtime",
        "failed_nonfinite",
        "failed_missing_output",
        "blocked_resource",
    }
    return [
        {
            "row_id": row.get("row_id"),
            "benchmark": row.get("benchmark"),
            "method": row.get("method"),
            "N": row.get("N"),
            "imax": row.get("imax"),
            "execution_state": row.get("execution_state"),
            "error": row.get("error"),
            "final_time": row.get("final_time"),
            "final_trace_time": row.get("final_trace_time"),
            "run_seconds": row.get("run_seconds"),
        }
        for row in rows
        if row.get("execution_state") in terminal_failures
    ]


def write_summary(path: Path, matrix_id: str, rows: list[dict[str, Any]]) -> None:
    states = Counter(str(row["execution_state"]) for row in rows)
    lines = [
        "# CLSVOF redistance imax matrix status",
        "",
        f"Matrix ID: `{matrix_id}`",
        "",
        f"Completed: **{states.get('completed', 0)}/96**",
        "",
        "Final E-grad records: "
        f"**{sum(row.get('final_diagnostic_ok') is True for row in rows)}/"
        f"{states.get('completed', 0)} completed rows**",
        "",
        "## State counts",
        "",
        "| State | Rows |",
        "| --- | ---: |",
    ]
    for state, count in sorted(states.items()):
        lines.append(f"| {state} | {count} |")
    lines.extend(
        [
            "",
            "## Completion by resolution",
            "",
            "| N | Completed | Total |",
            "| ---: | ---: | ---: |",
        ]
    )
    for n in (64, 128, 256, 512):
        selected = [row for row in rows if int(row["N"]) == n]
        completed = sum(row["execution_state"] == "completed" for row in selected)
        lines.append(f"| {n} | {completed} | {len(selected)} |")
    if states == Counter({"completed": 96}):
        lines.extend(
            [
                "",
                "The row-level matrix is complete. Final scientific synthesis is appended by",
                "`analyze_matrix.py` after the strict audit passes. Metrics are recomputed from row-level raw data.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "This is an incremental evidence report. Scientific conclusions are withheld until all",
                "96 rows have terminal, audited states. Metrics are recomputed from row-level raw data.",
                "",
            ]
        )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = read_json(args.matrix)
    result_root = HERE / "results" / args.matrix_id
    rows = [collect_row(result_root, row) for row in matrix["rows"]]
    status_fields = [
        "row_id", "benchmark", "method", "N", "LEVEL", "actual_grid", "imax",
        "planning_status", "execution_state", "error",
    ]
    atomic_csv(result_root / "matrix_status.csv", rows, status_fields)
    atomic_csv(result_root / "metrics_wide.csv", rows, ordered_fields(rows))
    long_rows = make_long(rows)
    atomic_csv(
        result_root / "metrics_long.csv",
        long_rows,
        ["row_id", "benchmark", "method", "N", "imax", "metric", "value"],
    )
    paired = make_wide(rows)
    atomic_csv(
        result_root / "paired_metrics_wide.csv", paired, ordered_fields(paired)
    )
    runtime = make_runtime(rows)
    atomic_csv(
        result_root / "runtime.csv",
        runtime,
        [
            "row_id", "benchmark", "method", "N", "imax", "execution_state",
            "compile_seconds", "run_seconds", "solver_steps", "stock_cpu_seconds",
            "stock_real_seconds", "return_calls", "provider_evaluations",
        ],
    )
    failures = make_failures(rows)
    atomic_csv(
        result_root / "failures.csv",
        failures,
        [
            "row_id", "benchmark", "method", "N", "imax", "execution_state",
            "error", "final_time", "final_trace_time", "run_seconds",
        ],
    )
    write_summary(result_root / "summary.md", args.matrix_id, rows)
    print(json.dumps(Counter(row["execution_state"] for row in rows), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
