#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_MATRIX = HERE / "config/matrix.json"
STOP_REQUESTED = False


def request_stop(signum: int, frame: object) -> None:
    del signum, frame
    global STOP_REQUESTED
    STOP_REQUESTED = True


def memory_free_percent() -> int | None:
    completed = subprocess.run(
        ["memory_pressure", "-Q"], capture_output=True, text=True
    )
    match = re.search(r"free percentage:\s*(\d+)%", completed.stdout)
    return int(match.group(1)) if match else None


def on_ac_power() -> bool:
    completed = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
    return "AC Power" in completed.stdout


def status_path(result_root: Path, row: dict[str, Any]) -> Path:
    return (
        result_root
        / str(row["benchmark"])
        / f"N{int(row['N']):04d}"
        / f"imax{int(row['imax']):02d}"
        / str(row["method"])
        / "status.json"
    )


def has_final_diagnostic(result_root: Path, row: dict[str, Any]) -> bool:
    metrics = status_path(result_root, row).parent / "redistance_metrics.csv"
    if not metrics.is_file():
        return False
    final_time = 2.2426211256 if row["benchmark"] == "capwave" else 3.0
    with metrics.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    final_records = {
        (item.get("stage"), item.get("band_cells"))
        for item in rows
        if abs(float(item["t"]) - final_time) <= 1e-8
    }
    return {
        ("pre", "1.5"),
        ("pre", "3.0"),
        ("post", "1.5"),
        ("post", "3.0"),
    }.issubset(final_records)


def estimate_cost(row: dict[str, Any]) -> float:
    n = int(row["N"])
    imax = int(row["imax"])
    imax_factor = {0: 0.55, 1: 0.72, 2: 0.88, 3: 1.0, 4: 1.12, 5: 1.24}[imax]
    if row["benchmark"] == "capwave":
        base = {
            "clsvof_native": {64: 5, 128: 27, 256: 342, 512: 2135},
            "clsvof_nn": {64: 23, 128: 204, 256: 1912, 512: 18580},
        }[row["method"]][n]
    else:
        base_n256 = 120 if row["method"] == "clsvof_native" else 232
        base = base_n256 * (n / 256.0) ** 3
    return base * imax_factor


def select_rows(matrix: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    if phase == "final_sample_backfill":
        return sorted(matrix["rows"], key=estimate_cost, reverse=True)
    if phase == "n512_all":
        rows = [row for row in matrix["rows"] if int(row["N"]) == 512]
        return sorted(rows, key=estimate_cost, reverse=True)
    if phase == "reuse_replay" or phase.startswith("reuse_n"):
        rows = [
            row for row in matrix["rows"] if row["planning_status"] == "candidate_reuse"
        ]
        if phase.startswith("reuse_n"):
            requested_n = int(phase.removeprefix("reuse_n"))
            if requested_n not in (64, 128, 256, 512):
                raise ValueError(f"unsupported reuse resolution phase {phase}")
            rows = [row for row in rows if int(row["N"]) == requested_n]
        return sorted(rows, key=estimate_cost, reverse=True)
    rows = [row for row in matrix["rows"] if row["planning_status"] == "planned_run"]
    if phase == "n64_extremes":
        rows = [row for row in rows if row["N"] == 64 and row["imax"] in (0, 5)]
    elif phase == "n64_remaining":
        rows = [row for row in rows if row["N"] == 64 and row["imax"] not in (0, 5)]
    elif phase.startswith("n") and phase[1:].isdigit():
        requested_n = int(phase[1:])
        if requested_n not in (128, 256, 512):
            raise ValueError(f"unsupported resolution phase {phase}")
        rows = [row for row in rows if row["N"] == requested_n]
    elif phase == "all_new":
        pass
    else:
        raise ValueError(f"unsupported phase {phase}")
    return sorted(rows, key=estimate_cost, reverse=True)


def atomic_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument(
        "--phase",
        choices=[
            "n64_extremes",
            "n64_remaining",
            "n128",
            "n256",
            "n512",
            "n512_all",
            "reuse_replay",
            "reuse_n64",
            "reuse_n128",
            "reuse_n256",
            "reuse_n512",
            "final_sample_backfill",
            "all_new",
        ],
        required=True,
    )
    parser.add_argument("--max-jobs", type=int, default=2)
    parser.add_argument(
        "--max-jobs-file",
        type=Path,
        help="optional JSON file with an integer max_jobs field, reread every poll",
    )
    parser.add_argument("--min-memory-percent", type=int, default=25)
    parser.add_argument("--poll-seconds", type=int, default=30)
    return parser.parse_args(argv)


def current_max_jobs(default: int, path: Path | None) -> int:
    value = default
    if path is not None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = int(payload["max_jobs"])
    if value < 1 or value > 5:
        raise ValueError("max-jobs must be between 1 and the user-approved ceiling 5")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    current_max_jobs(args.max_jobs, args.max_jobs_file)
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    result_root = HERE / "results" / args.matrix_id
    queue = []
    external_running: dict[str, tuple[dict[str, Any], Path]] = {}
    for row in select_rows(matrix, args.phase):
        path = status_path(result_root, row)
        if args.phase == "final_sample_backfill":
            if not path.exists():
                continue
            state = json.loads(path.read_text(encoding="utf-8")).get("state")
            if state != "completed" or has_final_diagnostic(result_root, row):
                continue
            queue.append(row)
            continue
        if path.exists():
            state = json.loads(path.read_text(encoding="utf-8")).get("state")
            if state == "completed":
                continue
            if state == "running":
                external_running[str(row["row_id"])] = (row, path)
                continue
            raise RuntimeError(f"row has terminal non-completed status: {path}")
        queue.append(row)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    active: dict[subprocess.Popen[str], tuple[dict[str, Any], Any]] = {}
    scheduler_log = result_root / f"scheduler_{args.phase}.log"
    scheduler_log.parent.mkdir(parents=True, exist_ok=True)

    with scheduler_log.open("a", encoding="utf-8") as log:
        while queue or active or external_running:
            external_finished = []
            for row_id, (row, path) in external_running.items():
                if not path.exists():
                    raise RuntimeError(f"external running row lost status file: {path}")
                state = json.loads(path.read_text(encoding="utf-8")).get("state")
                if state != "running":
                    log.write(f"external-finished row={row_id} state={state}\n")
                    log.flush()
                    external_finished.append(row_id)
            for row_id in external_finished:
                del external_running[row_id]

            finished = []
            for process, (row, stream) in active.items():
                returncode = process.poll()
                if returncode is not None:
                    stream.close()
                    log.write(f"finished row={row['row_id']} returncode={returncode}\n")
                    log.flush()
                    finished.append(process)
            for process in finished:
                del active[process]

            free = memory_free_percent()
            target_max_jobs = current_max_jobs(args.max_jobs, args.max_jobs_file)
            can_launch = (
                not STOP_REQUESTED
                and on_ac_power()
                and (free is None or free >= args.min_memory_percent)
            )
            while (
                queue
                and len(active) + len(external_running) < target_max_jobs
                and can_launch
            ):
                row = queue.pop(0)
                row_log = result_root / "launcher_logs" / f"{row['row_id']}.log"
                row_log.parent.mkdir(parents=True, exist_ok=True)
                stream = row_log.open("a", encoding="utf-8")
                command = [
                    "/opt/anaconda3/envs/pinn/bin/python",
                    str(HERE / "run_row.py"),
                    str(row["row_id"]),
                    "--matrix",
                    str(args.matrix),
                    "--matrix-id",
                    args.matrix_id,
                ]
                if args.phase == "final_sample_backfill":
                    command.append("--force")
                process = subprocess.Popen(
                    command, cwd=HERE, stdout=stream, stderr=subprocess.STDOUT, text=True
                )
                active[process] = (row, stream)
                log.write(
                    f"launched row={row['row_id']} pid={process.pid} "
                    f"estimated_seconds={estimate_cost(row):.1f} free_memory={free}\n"
                )
                log.flush()
            atomic_state(
                result_root / f"scheduler_{args.phase}.json",
                {
                    "phase": args.phase,
                    "stop_requested": STOP_REQUESTED,
                    "queued": [row["row_id"] for row in queue],
                    "active": [row["row_id"] for row, stream in active.values()],
                    "external_active": sorted(external_running),
                    "max_jobs": target_max_jobs,
                    "max_jobs_file": str(args.max_jobs_file) if args.max_jobs_file else None,
                    "memory_free_percent": free,
                    "on_ac_power": on_ac_power(),
                    "updated_epoch": time.time(),
                },
            )
            if STOP_REQUESTED and not active and not external_running:
                break
            time.sleep(max(1, args.poll_seconds))

    subprocess.run(
        [
            "/opt/anaconda3/envs/pinn/bin/python",
            str(HERE / "refresh_outputs.py"),
            "--matrix",
            str(args.matrix),
            "--matrix-id",
            args.matrix_id,
        ],
        cwd=HERE,
        check=False,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
