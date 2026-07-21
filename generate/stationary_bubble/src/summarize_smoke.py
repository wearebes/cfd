#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path


LAPLACE = 12000.0
EXACT_CURVATURE = 2.5


def read_series(path: Path) -> list[tuple[float, float, float]]:
    rows: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"expected three columns in {path}: {line!r}")
        row = tuple(float(value) for value in parts)
        if not all(math.isfinite(value) for value in row):
            raise ValueError(f"non-finite value in {path}: {line!r}")
        rows.append(row)
    if not rows:
        raise ValueError(f"empty time series: {path}")
    return rows


def read_official_terminal_metrics(path: Path) -> dict[str, float | int]:
    """Read every field in the official seven-column terminal row."""
    candidates: list[tuple[float, ...]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 7:
            continue
        try:
            row = tuple(float(value) for value in parts)
        except ValueError:
            continue
        if row[1] != LAPLACE or not all(math.isfinite(value) for value in row):
            continue
        candidates.append(row)
    if len(candidates) != 1:
        raise ValueError(
            f"expected one official seven-column terminal row in {path}, "
            f"found {len(candidates)}"
        )
    row = candidates[0]
    level = int(row[0])
    if float(level) != row[0]:
        raise ValueError(f"non-integral level in {path}: {row[0]}")
    metric_values = row[2:]
    if any(value < 0.0 for value in metric_values):
        raise ValueError(f"negative official terminal metric in {path}: {row}")
    return {
        "level": level,
        "laplace_number": row[1],
        "u_star_final": row[2],
        "shape_error_avg": row[3],
        "shape_error_rms": row[4],
        "shape_error_max": row[5],
        "ekmax": row[6],
        "relative_curvature_error_percent": round(
            100.0*row[6]/EXACT_CURVATURE, 12
        ),
    }


def main() -> int:
    result_root = Path(sys.argv[1])
    summary: list[dict[str, float | int | str]] = []
    mode_dirs = sorted(
        path for path in result_root.iterdir()
        if path.is_dir() and any(path.glob("La-12000-*"))
    )
    if not mode_dirs:
        raise ValueError(f"no stationary method directory found in {result_root}")
    for mode_dir in mode_dirs:
        series_paths = sorted(mode_dir.glob("La-12000-*"))
        if len(series_paths) != 1:
            raise ValueError(
                f"expected one La-12000-* time series in {mode_dir}, "
                f"found {len(series_paths)}"
            )
        series = read_series(series_paths[0])
        official = read_official_terminal_metrics(mode_dir / "log")
        termination_path = mode_dir / "termination.csv"
        if termination_path.is_file():
            with termination_path.open(newline="", encoding="utf-8") as handle:
                termination = list(csv.DictReader(handle))
            if len(termination) != 1:
                raise ValueError(f"expected one termination row in {mode_dir}")
            actual_terminal_tau = float(termination[0]["actual_terminal_tau"])
            termination_reason = termination[0]["reason"]
        else:
            # Backward-compatible summary for legacy rows. New generators
            # always write termination.csv and the v2 builder requires it.
            actual_terminal_tau = series[-1][0]
            termination_reason = "legacy_unrecorded"
        ca = [u_star / math.sqrt(LAPLACE) for _, u_star, _ in series]
        tail = ca[max(0, len(ca) - math.ceil(len(ca)*0.1)):]
        summary.append({
            "mode": mode_dir.name,
            "samples": len(series),
            "tau_final": actual_terminal_tau,
            "termination_reason": termination_reason,
            "u_star_max": max(row[1] for row in series),
            "delta_f_final": series[-1][2],
            "ca_max": max(ca),
            "ca_final": ca[-1],
            "ca_tail_max": max(tail),
            **official,
        })
    with (result_root / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    official_fields = [
        "mode",
        "level",
        "laplace_number",
        "u_star_final",
        "shape_error_avg",
        "shape_error_rms",
        "shape_error_max",
        "ekmax",
        "relative_curvature_error_percent",
    ]
    with (result_root / "official_metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=official_fields)
        writer.writeheader()
        writer.writerows(
            {field: row[field] for field in official_fields} for row in summary
        )
    (result_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
