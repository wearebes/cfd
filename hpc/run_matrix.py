#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.lib.integrity import atomic_json  # noqa: E402
from hpc.lib.matrix import BENCHMARKS, formal_rows, generator_path  # noqa: E402
from hpc.lib.scheduler import (  # noqa: E402
    available_cpu_ids,
    load_policy,
    phase_rows,
    release_cpus,
    take_cpus,
    threads_for,
)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--cpus", type=positive_int, default=128)
    parser.add_argument(
        "--policy", type=Path, default=ROOT / "hpc/config/thread_policy.json"
    )
    parser.add_argument("--phase", choices=["n64", "remaining", "all"], default="all")
    parser.add_argument(
        "--benchmark",
        action="append",
        choices=BENCHMARKS,
        help="limit the run to one or more benchmarks (repeatable)",
    )
    parser.add_argument(
        "--resolution",
        action="append",
        type=int,
        choices=(64, 128, 256, 512),
        help="limit the run to one or more resolutions (repeatable)",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-active-rows", type=positive_int, default=1)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    return parser.parse_args(argv)


def filter_benchmarks(rows: list[Any], benchmarks: list[str] | None) -> list[Any]:
    if not benchmarks:
        return rows
    selected = set(benchmarks)
    return [row for row in rows if row.benchmark in selected]


def filter_resolutions(rows: list[Any], resolutions: list[int] | None) -> list[Any]:
    if not resolutions:
        return rows
    selected = set(resolutions)
    return [row for row in rows if row.resolution in selected]


def preflight_sources(rows: list[Any]) -> None:
    qcc = ROOT / "basilisk/src/qcc"
    if not qcc.is_file() or not os.access(qcc, os.X_OK):
        raise RuntimeError("missing executable basilisk/src/qcc")
    for row in rows:
        generator = generator_path(ROOT, row)
        if not generator.is_file() or not os.access(generator, os.X_OK):
            raise RuntimeError(f"missing executable generator: {generator}")
        if row.model_name:
            weights = ROOT / f"dataset/model/c_exports/{row.model_name}/nn_weights.h"
            if not weights.is_file():
                raise RuntimeError(f"missing weights: {weights}")


def run_phase(args: argparse.Namespace, rows: list[Any]) -> int:
    policy, policy_hash = load_policy(args.policy)
    visible = available_cpu_ids()
    if args.cpus > len(visible):
        raise RuntimeError(
            f"requested {args.cpus} CPUs but only {len(visible)} are visible"
        )
    free_cpus = visible[: args.cpus]
    pinning_available = shutil.which("taskset") is not None
    queue = list(rows)
    active: dict[subprocess.Popen[str], tuple[Any, list[int], Any]] = {}
    records: list[dict[str, Any]] = []
    result_root = ROOT / "hpc/results" / args.matrix_id
    scheduler_log = result_root / f"scheduler_{args.phase}.log"
    scheduler_log.parent.mkdir(parents=True, exist_ok=True)

    with scheduler_log.open("a", encoding="utf-8") as log:
        while queue or active:
            finished: list[subprocess.Popen[str]] = []
            for process, (row, allocation, stream) in list(active.items()):
                returncode = process.poll()
                if returncode is None:
                    continue
                stream.close()
                release_cpus(free_cpus, allocation)
                record = {
                    "row_id": row.row_id,
                    "returncode": returncode,
                    "threads": len(allocation),
                    "cpu_list": allocation,
                }
                records.append(record)
                log.write(json.dumps({"event": "finished", **record}) + "\n")
                log.flush()
                finished.append(process)
            for process in finished:
                del active[process]

            launched = True
            while queue and launched and len(active) < args.max_active_rows:
                launched = False
                for index, row in enumerate(queue):
                    threads = threads_for(row, policy)
                    allocation = take_cpus(free_cpus, threads)
                    if allocation is None:
                        continue
                    queue.pop(index)
                    row_log = result_root / "launcher_logs" / f"{row.row_id}.log"
                    row_log.parent.mkdir(parents=True, exist_ok=True)
                    stream = row_log.open("a", encoding="utf-8")
                    command = [
                        sys.executable,
                        str(ROOT / "hpc/run_row.py"),
                        row.row_id,
                        "--matrix-id",
                        args.matrix_id,
                        "--threads",
                        str(threads),
                        "--policy-sha256",
                        policy_hash,
                    ]
                    if pinning_available:
                        command.extend(
                            ["--cpu-list", ",".join(map(str, allocation))]
                        )
                    if args.resume:
                        command.append("--resume")
                    process = subprocess.Popen(
                        command,
                        cwd=ROOT,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    active[process] = (row, allocation, stream)
                    log.write(
                        json.dumps(
                            {
                                "event": "launched",
                                "row_id": row.row_id,
                                "pid": process.pid,
                                "threads": threads,
                                "cpu_list": allocation,
                            }
                        )
                        + "\n"
                    )
                    log.flush()
                    launched = True
                    break

            atomic_json(
                result_root / f"scheduler_{args.phase}.json",
                {
                    "phase": args.phase,
                    "matrix_id": args.matrix_id,
                    "policy_sha256": policy_hash,
                    "cpu_pool": args.cpus,
                    "max_active_rows": args.max_active_rows,
                    "cpu_pinning": pinning_available,
                    "free_cpus": free_cpus,
                    "queued": [row.row_id for row in queue],
                    "active": [row.row_id for row, _, _ in active.values()],
                    "completed_records": records,
                    "updated_epoch": time.time(),
                },
            )
            if queue and not active:
                requested = min(threads_for(row, policy) for row in queue)
                raise RuntimeError(
                    f"scheduler deadlock: smallest queued row requests {requested} CPUs"
                )
            if queue or active:
                time.sleep(max(0.05, args.poll_seconds))
    return 1 if any(record["returncode"] != 0 for record in records) else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    all_rows = filter_benchmarks(formal_rows(), args.benchmark)
    all_rows = filter_resolutions(all_rows, args.resolution)
    selected = phase_rows(all_rows, args.phase)
    policy, policy_hash = load_policy(args.policy)
    preflight_sources(selected)
    if args.dry_run:
        for row in selected:
            print(
                json.dumps(
                    {
                        **row.to_dict(),
                        "threads": threads_for(row, policy),
                        "policy_sha256": policy_hash,
                    },
                    sort_keys=True,
                )
            )
        print(
            json.dumps(
                {
                    "matrix_id": args.matrix_id,
                    "phase": args.phase,
                    "benchmarks": sorted(set(args.benchmark or BENCHMARKS)),
                    "resolutions": sorted(set(args.resolution or (64, 128, 256, 512))),
                    "row_count": len(selected),
                    "cpu_pool": args.cpus,
                    "max_active_rows": args.max_active_rows,
                    "policy_sha256": policy_hash,
                },
                sort_keys=True,
            )
        )
        return 0
    return run_phase(args, selected)


if __name__ == "__main__":
    raise SystemExit(main())
