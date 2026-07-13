#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


EXPECTED_IMAX_COUNTS = {value: 16 for value in range(6)}
EXPECTED_STATUS_COUNTS = {"candidate_reuse": 5, "planned_run": 91}


def load_and_validate(preview: Path) -> list[dict[str, object]]:
    with preview.open(newline="", encoding="utf-8") as stream:
        rows: list[dict[str, object]] = list(csv.DictReader(stream))

    if len(rows) != 96:
        raise ValueError(f"expected 96 rows, got {len(rows)}")
    row_ids = [str(row["row_id"]) for row in rows]
    if len(set(row_ids)) != 96:
        raise ValueError("row_id values must be unique")

    imax_counts = Counter(int(str(row["imax"])) for row in rows)
    if dict(imax_counts) != EXPECTED_IMAX_COUNTS:
        raise ValueError(f"unexpected imax counts: {dict(imax_counts)}")
    status_counts = Counter(str(row["planning_status"]) for row in rows)
    if dict(status_counts) != EXPECTED_STATUS_COUNTS:
        raise ValueError(f"unexpected planning status counts: {dict(status_counts)}")

    for row in rows:
        row["N"] = int(str(row["N"]))
        row["imax"] = int(str(row["imax"]))
        row["LEVEL"] = int(str(row["LEVEL"])) if str(row["LEVEL"]) else None
        if row["method"] == "clsvof_nn":
            expected = f"baseline_{row['N']}_hgradient"
            if row["checkpoint"] != expected:
                raise ValueError(f"{row['row_id']}: expected checkpoint {expected}")
    return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("preview", type=Path)
    parser.add_argument("output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_and_validate(args.preview)
    payload = {
        "schema_version": 1,
        "matrix_name": "clsvof_redistance_imax_formal_matrix",
        "expected_rows": 96,
        "max_concurrent": 4,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
