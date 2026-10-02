#!/usr/bin/env python3
"""Compact validated intermediate solver outputs into the reviewed row schema."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
from typing import Iterable


FIELD_COLUMNS = [
    "snapshot",
    "target_solver_time",
    "actual_solver_time",
    "actual_benchmark_time",
    "iteration",
    "x",
    "y",
    "Delta",
    "level",
    "u_x",
    "u_y",
    "pressure",
    "vorticity",
    "phase_fraction",
    "common_curvature",
    "common_curvature_valid",
    "active_curvature",
    "active_curvature_valid",
]

# Basilisk's bounded VOF fraction can exceed [0, 1] by a few 1e-12 from
# floating-point roundoff.  Keep the scientific guard strict enough to reject
# material overshoots while accepting those representational residues.
PHASE_FRACTION_TOLERANCE = 1e-10

ROW_FILES = {
    "capwave": ["timeseries.csv", "fields.csv.gz", "run.log"],
    "rising_bubble": [
        "timeseries.csv",
        "interface_t3.csv.gz",
        "fields.csv.gz",
        "run.log",
    ],
    "stationary_bubble": [
        "timeseries.csv",
        "milestones.csv",
        "fields.csv.gz",
        "run.log",
    ],
    "oscillating_droplet": [
        "timeseries.csv",
        "fit.csv",
        "fields.csv.gz",
        "run.log",
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def deterministic_gzip(source: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    with source.open("rb") as input_stream, temporary.open("wb") as raw_output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as output:
            shutil.copyfileobj(input_stream, output, length=1024 * 1024)
    os.replace(temporary, target)


def write_gzip_csv(
    target: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]
) -> None:
    temporary_csv = target.with_name(f".{target.name}.csv.tmp.{os.getpid()}")
    with temporary_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    try:
        deterministic_gzip(temporary_csv, target)
    finally:
        temporary_csv.unlink(missing_ok=True)


def finite(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {label}: {value!r}") from error
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite {label}: {value!r}")
    return parsed


def compact_fields(root: Path) -> dict[str, object]:
    source = root / "fields.csv"
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("fields.csv is missing")
    summaries: dict[str, dict[str, object]] = {}
    with source.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELD_COLUMNS:
            raise ValueError(
                f"field columns mismatch: {reader.fieldnames!r} != {FIELD_COLUMNS!r}"
            )
        for row in reader:
            snapshot = str(row["snapshot"])
            if snapshot not in {"middle", "final"}:
                raise ValueError(f"unexpected field snapshot: {snapshot!r}")
            target = finite(row["target_solver_time"], "target_solver_time")
            actual = finite(row["actual_solver_time"], "actual_solver_time")
            benchmark = finite(row["actual_benchmark_time"], "actual_benchmark_time")
            iteration = int(row["iteration"])
            delta = finite(row["Delta"], "Delta")
            phase = finite(row["phase_fraction"], "phase_fraction")
            if delta <= 0.0 or not (
                -PHASE_FRACTION_TOLERANCE
                <= phase
                <= 1.0 + PHASE_FRACTION_TOLERANCE
            ):
                raise ValueError("invalid field geometry or phase fraction")
            for field in ("x", "y", "u_x", "u_y", "pressure", "vorticity"):
                finite(row[field], field)
            for value_field, valid_field in (
                ("common_curvature", "common_curvature_valid"),
                ("active_curvature", "active_curvature_valid"),
            ):
                valid = int(row[valid_field])
                if valid not in (0, 1):
                    raise ValueError(f"{valid_field} must be zero or one")
                if valid:
                    finite(row[value_field], value_field)
                elif row[value_field] != "":
                    raise ValueError(f"invalid {value_field} must be empty")
            summary = summaries.setdefault(
                snapshot,
                {
                    "target_solver_time": target,
                    "actual_solver_time": actual,
                    "actual_benchmark_time": benchmark,
                    "iteration": iteration,
                    "cell_records": 0,
                },
            )
            for key, value in (
                ("target_solver_time", target),
                ("actual_solver_time", actual),
                ("actual_benchmark_time", benchmark),
                ("iteration", iteration),
            ):
                if summary[key] != value:
                    raise ValueError(f"inconsistent {snapshot} field metadata: {key}")
            summary["cell_records"] = int(summary["cell_records"]) + 1
    if set(summaries) != {"middle", "final"}:
        raise ValueError(f"field snapshots incomplete: {sorted(summaries)}")
    if float(summaries["middle"]["actual_solver_time"]) + 1e-12 < float(
        summaries["middle"]["target_solver_time"]
    ):
        raise ValueError("middle snapshot precedes its target")
    target = root / "fields.csv.gz"
    deterministic_gzip(source, target)
    source.unlink()
    return {
        "schema_version": 1,
        "selection": {
            "middle": "first_native_solver_state_at_or_after_target",
            "final": "terminal_solver_state",
        },
        "columns": FIELD_COLUMNS,
        "snapshots": summaries,
        "compressed_bytes": target.stat().st_size,
    }


def compact_rising_interface(root: Path) -> None:
    points: list[tuple[float, float]] = []
    for line in (root / "interface.dat").read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            point = (float(fields[0]), float(fields[1]))
        except ValueError:
            continue
        if all(math.isfinite(value) for value in point):
            points.append(point)
    if not points or len(points) % 2:
        raise ValueError("rising interface does not contain endpoint pairs")
    rows = [
        {"segment_id": index, "x1": left[0], "y1": left[1], "x2": right[0], "y2": right[1]}
        for index, (left, right) in enumerate(zip(points[::2], points[1::2]))
    ]
    write_gzip_csv(
        root / "interface_t3.csv.gz",
        ["segment_id", "x1", "y1", "x2", "y2"],
        rows,
    )


def compact_stationary_milestones(root: Path, tau_max: float = 2.0) -> None:
    source = root / "milestones.csv"
    with source.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    expected_rows = 2 if tau_max >= 1.0 else 1
    if len(rows) != expected_rows:
        raise ValueError(
            "stationary milestone count does not match the requested horizon"
        )
    fieldnames = [
        "milestone",
        "tau",
        "iteration",
        "u_star",
        "capillary_number",
        "shape_error_avg",
        "shape_error_rms",
        "shape_error_max",
        "official_style_ekmax",
        "active_provider_ekmax",
        "active_provider_samples",
    ]
    normalized = []
    for row in rows:
        tau = finite(row["tau"], "milestone tau")
        label = (
            "tau_2"
            if row["milestone"] == "terminal" and abs(tau - 2.0) <= 1e-9
            else row["milestone"]
        )
        normalized.append(
            {
                **{field: row[field] for field in fieldnames if field not in {"milestone", "capillary_number"}},
                "milestone": label,
                "capillary_number": finite(row["u_star"], "u_star") / math.sqrt(12000.0),
                "tau": tau,
            }
        )
    expected_labels = (
        {"terminal"}
        if tau_max < 1.0
        else {"tau_1", "tau_2" if abs(tau_max - 2.0) <= 1e-9 else "terminal"}
    )
    if {row["milestone"] for row in normalized} != expected_labels:
        raise ValueError("stationary milestone labels are incomplete")
    temporary = source.with_name(f".{source.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(normalized)
    os.replace(temporary, source)


def compact_oscillating_fit(root: Path, metrics: list[dict[str, object]]) -> None:
    values = {str(row["metric"]): row["value"] for row in metrics}
    fields = [
        "cells_per_diameter",
        "fit_a",
        "fit_a_stderr",
        "fit_b",
        "fit_b_stderr",
        "fit_c",
        "fit_c_stderr",
        "frequency_error_signed",
        "frequency_error_abs_percent",
        "equivalent_laplace",
        "damping_regime",
    ]
    row = {}
    for field in fields:
        metric_name = {
            "cells_per_diameter": "diameter_cells",
            "damping_regime": "fit_damping_regime",
        }.get(field, field)
        row[field] = values[metric_name]
    with (root / "fit.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def write_run_log(root: Path, case: str) -> None:
    names = ["compile.stdout", "compile.stderr"]
    names.extend(
        {
            "capwave": ["solver.stdout.txt"],
            "rising_bubble": [],
            "stationary_bubble": ["runtime_and_terminal.log", "solver.stdout.txt"],
            "oscillating_droplet": [
                "command.txt",
                "runtime.stderr.txt",
                "solver.stdout.txt",
                "fit.log",
                "execution_status.txt",
            ],
        }[case]
    )
    with (root / "run.log").open("w", encoding="utf-8") as output:
        for name in names:
            candidate = root / name
            if not candidate.is_file():
                continue
            output.write(f"===== {name} =====\n")
            text = candidate.read_text(encoding="utf-8", errors="replace")
            output.write(text)
            if text and not text.endswith("\n"):
                output.write("\n")


def oscillating_vof_hf_record(root: Path) -> dict[str, object] | None:
    verification = root / "verification.json"
    execution = root / "execution_status.txt"
    if not verification.is_file() or not execution.is_file():
        return None
    payload = json.loads(verification.read_text(encoding="utf-8"))
    payload["execution_status"] = dict(
        line.split("=", 1)
        for line in execution.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    diff = root / "fit_summary_vs_ref.diff"
    if payload.get("strict_log_ref_match") is not None:
        payload["strict_log_ref_match"] = diff.is_file() and diff.stat().st_size == 0
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("row_dir", type=Path)
    args = parser.parse_args()
    root = args.row_dir.resolve()
    manifest_path = root / "manifest.json"
    contract_path = root / "scientific_artifacts.json"
    metrics_path = root / "metrics.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    with metrics_path.open(newline="", encoding="utf-8") as stream:
        metrics = list(csv.DictReader(stream))
    case = str(manifest.get("case_id") or manifest.get("case"))
    if case not in ROW_FILES:
        raise ValueError(f"unsupported row case: {case}")
    if not contract.get("analysis_ready") or not manifest.get("analysis_ready"):
        raise ValueError("row is not scientifically analysis-ready")

    field_summary = compact_fields(root)
    (root / "plot_data.csv").replace(root / "timeseries.csv")
    if case == "rising_bubble":
        compact_rising_interface(root)
    elif case == "stationary_bubble":
        compact_stationary_milestones(root, float(manifest["tau_max"]))
    elif case == "oscillating_droplet":
        compact_oscillating_fit(root, metrics)
    write_run_log(root, case)

    provider_stats = None
    provider_path = root / "provider_stats.csv"
    if provider_path.is_file():
        with provider_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 1:
            raise ValueError("provider_stats.csv must contain exactly one row")
        provider_stats = rows[0]
    c2_endpoint_stats = None
    c2_path = root / "c2_endpoint_stats.csv"
    if c2_path.is_file():
        with c2_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 1:
            raise ValueError("c2_endpoint_stats.csv must contain exactly one row")
        c2_endpoint_stats = rows[0]
    redistance_steps_stats = None
    redistance_steps_path = root / "redistance_steps.csv"
    if redistance_steps_path.is_file():
        with redistance_steps_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 1:
            raise ValueError("redistance_steps.csv must contain exactly one row")
        redistance_steps_stats = rows[0]
    if manifest.get("redistance_policy") == "fixed_steps":
        if redistance_steps_stats is None:
            raise ValueError("fixed-steps row is missing redistance_steps.csv")
    elif redistance_steps_stats is not None:
        raise ValueError("legacy imax row unexpectedly has redistance_steps.csv")
    vof_hf_record = (
        oscillating_vof_hf_record(root)
        if case == "oscillating_droplet" and manifest.get("method") == "VOF-HF"
        else None
    )

    row_files = list(ROW_FILES[case])
    if case == "stationary_bubble" and (
        root / "whole_domain_timeseries.csv"
    ).is_file():
        row_files.append("whole_domain_timeseries.csv")
    if redistance_steps_stats is not None:
        row_files.append("redistance_steps.csv")
    published = {}
    for name in row_files:
        path = root / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing compact row artifact: {name}")
        published[name] = {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
    manifest["row_schema_version"] = 1
    manifest["analysis"] = {
        "schema_version": 1,
        "benchmark_output_coverage_complete": contract[
            "benchmark_output_coverage_complete"
        ],
        "required_metric_names": contract["required_metric_names"],
        "metrics": metrics,
        "provider_stats": provider_stats,
        "c2_endpoint_stats": c2_endpoint_stats,
        "redistance_steps_stats": redistance_steps_stats,
    }
    manifest["field_snapshots"] = field_summary
    manifest["published_artifacts"] = published
    if vof_hf_record is not None:
        manifest["oscillating_vof_hf_verification"] = vof_hf_record
    for key in (
        "scientific_artifacts_schema_version",
        "scientific_artifacts_sha256",
    ):
        manifest.pop(key, None)
    atomic_json(manifest_path, manifest)

    keep = {"manifest.json", "source_snapshot", *row_files}
    for path in root.iterdir():
        if path.name in keep:
            continue
        if path.is_file() or path.is_symlink():
            path.unlink()
    print(
        json.dumps(
            {
                "case": case,
                "files": row_files,
                "field_snapshots": field_summary["snapshots"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
