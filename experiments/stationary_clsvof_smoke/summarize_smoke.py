#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path


LAPLACE = 12000.0


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


def main() -> int:
    result_root = Path(sys.argv[1])
    summary: list[dict[str, float | int | str]] = []
    for mode_dir in sorted(path for path in result_root.iterdir() if path.is_dir()):
        series = read_series(mode_dir / "La-12000-6")
        ca = [u_star / math.sqrt(LAPLACE) for _, u_star, _ in series]
        tail = ca[max(0, len(ca) - math.ceil(len(ca)*0.1)):]
        summary.append({
            "mode": mode_dir.name,
            "samples": len(series),
            "tau_final": series[-1][0],
            "u_star_max": max(row[1] for row in series),
            "delta_f_final": series[-1][2],
            "ca_max": max(ca),
            "ca_final": ca[-1],
            "ca_tail_max": max(tail),
        })
    with (result_root / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    (result_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
