#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from run_matrix import DEFAULT_MATRIX, HERE, has_final_diagnostic, status_path


def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--poll-seconds", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    result_root = HERE / "results" / args.matrix_id
    scheduler = result_root / "scheduler_final_sample_backfill.json"
    capacity = result_root / "n512_capacity.json"
    while True:
        if scheduler.is_file():
            state = json.loads(scheduler.read_text(encoding="utf-8"))
            if not state.get("queued") and not state.get("active"):
                break
        time.sleep(max(1, args.poll_seconds))

    failures = []
    for row in matrix["rows"]:
        if int(row["N"]) > 256:
            continue
        path = status_path(result_root, row)
        if not path.is_file():
            failures.append(f"{row['row_id']}:missing_status")
            continue
        state = json.loads(path.read_text(encoding="utf-8")).get("state")
        if state != "completed":
            failures.append(f"{row['row_id']}:{state}")
        elif not has_final_diagnostic(result_root, row):
            failures.append(f"{row['row_id']}:missing_final_diagnostic")
    if failures:
        atomic_json(
            result_root / "n512_capacity_promotion_failed.json",
            {
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "failures": failures,
                "max_jobs_remains": 3,
            },
        )
        raise RuntimeError(f"N<=256 closure failed for {len(failures)} rows")

    atomic_json(
        capacity,
        {
            "max_jobs": 5,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "reason": "N<=256 final-sample backfill passed for all 72 rows",
        },
    )
    print(json.dumps({"promoted": True, "max_jobs": 5, "verified_rows": 72}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
