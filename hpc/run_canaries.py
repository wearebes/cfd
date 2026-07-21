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
from hpc.lib.matrix import MatrixRow, generator_command  # noqa: E402
from hpc.lib.scheduler import available_cpu_ids, load_policy  # noqa: E402


CORRECTNESS_ROWS = (
    MatrixRow("capwave", "nn", 64, 3),
    MatrixRow("rising_case1", "nn", 64, 3),
    MatrixRow("rising_case2", "nn", 64, 3),
    MatrixRow("stationary_bubble", "nn", 64, 3),
)


def candidates(cpu_pool: int) -> list[int]:
    return sorted({1, *(min(value, cpu_pool) for value in (16, 32, 64, 128))})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--cpus", type=int, default=128)
    parser.add_argument(
        "--policy", type=Path, default=ROOT / "hpc/config/thread_policy.json"
    )
    return parser.parse_args(argv)


def safe_remove_generator_work(stderr: str) -> None:
    allowed = (ROOT / "tem").resolve()
    for line in stderr.splitlines():
        if not line.startswith("work: "):
            continue
        candidate = Path(line.removeprefix("work: ").strip()).resolve()
        if candidate != allowed and allowed in candidate.parents and candidate.is_dir():
            shutil.rmtree(candidate)


def run_one(
    row: MatrixRow,
    threads: int,
    cpu_ids: list[int],
    output: Path,
) -> dict[str, Any]:
    command = generator_command(
        ROOT, row, purpose="smoke", output=output, threads=threads
    )
    taskset = shutil.which("taskset")
    if taskset is None:
        raise RuntimeError("taskset is required for target-host canaries")
    launch = [taskset, "--cpu-list", ",".join(map(str, cpu_ids[:threads])), *command]
    environment = os.environ.copy()
    environment.update(
        {
            "OMP_NUM_THREADS": str(threads),
            "OMP_DYNAMIC": "FALSE",
            "OMP_PROC_BIND": "close",
            "OMP_PLACES": "cores",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    started = time.monotonic()
    completed = subprocess.run(
        launch, cwd=ROOT, env=environment, text=True, capture_output=True
    )
    elapsed = time.monotonic() - started
    record: dict[str, Any] = {
        "row_id": row.row_id,
        "threads": threads,
        "cpu_list": cpu_ids[:threads],
        "elapsed_seconds": elapsed,
        "returncode": completed.returncode,
        "command": launch,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode == 0:
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        compile_stderr = [
            path for path in output.rglob("compile.stderr") if path.stat().st_size
        ]
        if compile_stderr:
            record["returncode"] = 1
            record["compile_warnings"] = [
                {
                    "path": path.relative_to(output).as_posix(),
                    "text": path.read_text(encoding="utf-8", errors="replace"),
                }
                for path in compile_stderr
            ]
        record["generator_manifest"] = manifest
    safe_remove_generator_work(completed.stderr)
    if output.exists():
        shutil.rmtree(output)
    return record


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy_path = args.policy.resolve()
    try:
        policy_relative = policy_path.relative_to(ROOT)
    except ValueError as error:
        raise SystemExit("--policy must be a file inside the repository") from error
    if args.cpus < 1:
        raise SystemExit("--cpus must be positive")
    cpu_ids = available_cpu_ids()
    if args.cpus > len(cpu_ids):
        raise SystemExit(
            f"requested {args.cpus} CPUs but only {len(cpu_ids)} are visible"
        )
    cpu_ids = cpu_ids[: args.cpus]
    _, policy_hash = load_policy(policy_path)
    root = ROOT / "hpc/work" / args.matrix_id / "canaries"
    root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    correctness_threads = min(4, args.cpus)
    for row in CORRECTNESS_ROWS:
        records.append(
            run_one(
                row,
                correctness_threads,
                cpu_ids,
                root / f"correctness_{row.benchmark}",
            )
        )

    scaling_row = MatrixRow(
        "stationary_bubble", "nn", 64, 3
    )
    scaling_records = []
    for threads in candidates(args.cpus):
        record = run_one(
            scaling_row,
            threads,
            cpu_ids,
            root / f"scaling_stationary_t{threads}",
        )
        scaling_records.append(record)
        records.append(record)

    failures = [record for record in records if record["returncode"] != 0]
    successful_scaling = [
        record for record in scaling_records if record["returncode"] == 0
    ]
    for record in successful_scaling:
        concurrency = max(1, args.cpus // int(record["threads"]))
        record["aggregate_rows_per_second"] = concurrency / float(
            record["elapsed_seconds"]
        )

    # Observed single-row OpenMP speedup relative to the 1-thread baseline.
    # Recorded for operator review; deliberately NOT a hard gate, because the
    # scaling workload is the short stationary N64 smoke and thread-spawn
    # overhead makes strict monotonicity noisy. A best speedup <= 1.0 is a
    # signal the operator should investigate before trusting the policy.
    serial = next(
        (item for item in successful_scaling if int(item["threads"]) == 1), None
    )
    speedup_by_threads: dict[str, float] = {}
    best_speedup: float | None = None
    if serial is not None and float(serial["elapsed_seconds"]) > 0:
        for item in successful_scaling:
            speedup_by_threads[str(item["threads"])] = float(
                serial["elapsed_seconds"]
            ) / float(item["elapsed_seconds"])
        parallel = [
            value
            for key, value in speedup_by_threads.items()
            if int(key) > 1
        ]
        best_speedup = max(parallel) if parallel else None
    openmp_speedup_observed = best_speedup is not None and best_speedup > 1.0
    recommended_single_row = (
        min(
            successful_scaling,
            key=lambda item: float(item["elapsed_seconds"]),
        )["threads"]
        if successful_scaling
        else None
    )
    recommended_throughput = (
        max(
            successful_scaling,
            key=lambda item: float(item["aggregate_rows_per_second"]),
        )["threads"]
        if successful_scaling
        else None
    )
    capacity = {
        "schema_version": 1,
        "status": "PASS" if not failures else "FAIL",
        "matrix_id": args.matrix_id,
        "requested_cpus": args.cpus,
        "visible_cpu_count": len(available_cpu_ids()),
        "policy_path": str(policy_relative),
        "policy_sha256": policy_hash,
        "measured_openmp_scaling": not failures and len(successful_scaling) >= 2,
        "openmp_speedup_by_threads": speedup_by_threads,
        "openmp_best_speedup": best_speedup,
        "openmp_speedup_observed": openmp_speedup_observed,
        "stationary_n64_recommended_threads_for_single_row": recommended_single_row,
        "stationary_n64_recommended_threads_for_throughput": recommended_throughput,
        "records": records,
        "failures": failures,
    }
    platform_root = ROOT / "hpc/results" / args.matrix_id / "platform"
    platform_root.mkdir(parents=True, exist_ok=True)
    atomic_json(platform_root / "capacity.json", capacity)
    print(
        json.dumps(
            {
                "status": capacity["status"],
                "measured_openmp_scaling": capacity["measured_openmp_scaling"],
                "openmp_best_speedup": best_speedup,
                "openmp_speedup_observed": openmp_speedup_observed,
                "recommended_threads_for_single_row": recommended_single_row,
                "recommended_threads_for_throughput": recommended_throughput,
            }
        )
    )
    return 0 if capacity["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
