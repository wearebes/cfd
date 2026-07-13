#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Any

from run_row import DEFAULT_MATRIX, HERE, result_dir


def atomic_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def completed(path: Path) -> bool:
    status = path / "status.json"
    return status.is_file() and json.loads(status.read_text(encoding="utf-8")).get("state") == "completed"


def finite(values: list[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    root = HERE / "results" / args.matrix_id
    capwave: list[dict[str, Any]] = []
    rising: list[dict[str, Any]] = []
    for row in matrix["rows"]:
        path = result_dir(root, row)
        if not completed(path):
            continue
        identity = {
            "row_id": row["row_id"],
            "method": row["method"],
            "N": row["N"],
            "imax": row["imax"],
        }
        if row["benchmark"] == "capwave":
            for index, line in enumerate((path / f"wave-{row['N']}").read_text(encoding="utf-8").splitlines()):
                values = [float(value) for value in line.split()[:2]]
                if len(values) == 2 and finite(values):
                    capwave.append({**identity, "sample": index, "tau": values[0], "amplitude": values[1]})
        else:
            sample = 0
            for line in (path / "out").read_text(encoding="utf-8").splitlines():
                try:
                    values = [float(value) for value in line.split()[:5]]
                except ValueError:
                    continue
                if len(values) == 5 and finite(values):
                    rising.append(
                        {
                            **identity,
                            "sample": sample,
                            "time": values[0],
                            "volume_drift": values[1],
                            "center": values[3],
                            "velocity": values[4],
                        }
                    )
                    sample += 1
    atomic_csv(
        root / "capwave_timeseries.csv",
        ["row_id", "method", "N", "imax", "sample", "tau", "amplitude"],
        capwave,
    )
    atomic_csv(
        root / "rising_timeseries.csv",
        ["row_id", "method", "N", "imax", "sample", "time", "volume_drift", "center", "velocity"],
        rising,
    )
    print(json.dumps({"capwave_rows": len(capwave), "rising_rows": len(rising)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
