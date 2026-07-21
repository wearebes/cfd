#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.lib.integrity import (  # noqa: E402
    atomic_json,
    expected_identity,
    inventory,
    sha256_file,
    staging_conflicts,
    validate_completed_result,
)
from hpc.lib.matrix import (  # noqa: E402
    generator_command,
    result_relative_path,
    rows_by_id,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def toolchain_record() -> dict[str, Any]:
    """Capture the compiler identity used to build the row.

    Recorded for provenance only; it is not part of ``formal_identity`` and
    therefore does not affect resume validation.
    """
    qcc = ROOT / "basilisk/src/qcc"
    record: dict[str, Any] = {
        "qcc_sha256": sha256_file(qcc) if qcc.is_file() else None,
        "gcc_version": None,
    }
    gcc = shutil.which("gcc")
    if gcc is not None:
        completed = subprocess.run([gcc, "--version"], text=True, capture_output=True)
        if completed.returncode == 0 and completed.stdout:
            record["gcc_version"] = completed.stdout.splitlines()[0]
    return record


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_cpu_list(value: str | None) -> list[int]:
    if value is None or not value.strip():
        return []
    cpus = [int(item) for item in value.split(",")]
    if any(cpu < 0 for cpu in cpus) or len(cpus) != len(set(cpus)):
        raise argparse.ArgumentTypeError("CPU list must contain unique nonnegative IDs")
    return cpus


def validate_generator_manifest(path: Path, row: Any, threads: int) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("generator did not produce manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("status") != "completed":
        raise RuntimeError(
            f"generator manifest is not completed: {payload.get('status')}"
        )
    if not payload.get("plan", {}).get("plan_sha256"):
        raise RuntimeError("generator manifest has no resolved plan hash")
    expected = {
        "benchmark": row.benchmark,
        "method": row.method,
        "resolution": row.resolution,
        "imax": row.imax,
        "model": row.model_name,
        "openmp_threads": threads,
    }
    mismatches = {
        key: (payload.get(key), value)
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"generator manifest mismatch: {mismatches}")
    if row.rising_case is not None:
        expected_case = f"hysing_case_{row.rising_case}"
        if payload.get("benchmark_case") != expected_case:
            raise RuntimeError(
                f"generator benchmark_case mismatch: {payload.get('benchmark_case')}"
            )
    nonempty_compile_stderr = [
        candidate.relative_to(path).as_posix()
        for candidate in path.rglob("compile.stderr")
        if candidate.stat().st_size
    ]
    if nonempty_compile_stderr:
        raise RuntimeError(
            f"generator compile stderr is not empty: {nonempty_compile_stderr}"
        )
    return payload


def safe_remove_generator_work(stderr: str) -> None:
    for line in stderr.splitlines():
        if not line.startswith("work: "):
            continue
        candidate = Path(line.removeprefix("work: ").strip()).resolve()
        allowed = (ROOT / "tem").resolve()
        if candidate != allowed and allowed in candidate.parents and candidate.is_dir():
            shutil.rmtree(candidate)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("row_id")
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--threads", type=positive_int, required=True)
    parser.add_argument("--cpu-list")
    parser.add_argument("--policy-sha256")
    parser.add_argument("--results-root", type=Path, default=ROOT / "hpc/results")
    parser.add_argument("--work-root", type=Path, default=ROOT / "hpc/work")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-work", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    row_map = rows_by_id()
    if args.row_id not in row_map:
        raise SystemExit(f"unknown row_id: {args.row_id}")
    row = row_map[args.row_id]
    cpus = parse_cpu_list(args.cpu_list)
    if cpus and len(cpus) != args.threads:
        raise SystemExit("--cpu-list length must equal --threads")

    result_base = args.results_root / args.matrix_id
    final = result_base / result_relative_path(row)
    conflicts = staging_conflicts(final)
    if conflicts:
        raise SystemExit(f"stale staging blocks row: {conflicts}")
    if final.exists():
        if not args.resume:
            raise SystemExit(f"refusing to overwrite existing result: {final}")
        valid, reason = validate_completed_result(
            final, row, args.matrix_id, args.policy_sha256
        )
        if not valid:
            raise SystemExit(f"resume rejected existing result: {reason}")
        print(json.dumps({"row_id": row.row_id, "state": "skipped_existing"}))
        return 0

    attempt_id = f"attempt_{int(time.time())}_{os.getpid()}"
    work = args.work_root / args.matrix_id / row.row_id / attempt_id
    generated = work / "generated"
    work.mkdir(parents=True, exist_ok=False)
    command = generator_command(
        ROOT,
        row,
        purpose="formal",
        output=generated,
        threads=args.threads,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(
            json.dumps(
                {
                    **row.to_dict(),
                    "threads": args.threads,
                    "cpu_list": cpus,
                    "command": command,
                    "final": str(final),
                },
                sort_keys=True,
            )
        )
        shutil.rmtree(work)
        return 0

    environment = os.environ.copy()
    environment.update(
        {
            "OMP_NUM_THREADS": str(args.threads),
            "OMP_DYNAMIC": "FALSE",
            "OMP_PROC_BIND": "close",
            "OMP_PLACES": "cores",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
        }
    )
    launch = command
    if cpus:
        taskset = shutil.which("taskset")
        if taskset is None:
            raise SystemExit("taskset is required when --cpu-list is supplied")
        launch = [taskset, "--cpu-list", ",".join(map(str, cpus)), *command]

    status: dict[str, Any] = {
        "row_id": row.row_id,
        "state": "running",
        "started_utc": utc_now(),
        "command": launch,
        "threads": args.threads,
        "cpu_list": cpus,
    }
    atomic_json(work / "status.json", status)
    started = time.monotonic()
    completed = subprocess.run(
        launch,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )
    elapsed = time.monotonic() - started
    (work / "launcher.stdout").write_text(completed.stdout, encoding="utf-8")
    (work / "launcher.stderr").write_text(completed.stderr, encoding="utf-8")
    status.update(
        {
            "finished_utc": utc_now(),
            "elapsed_seconds": elapsed,
            "returncode": completed.returncode,
        }
    )
    if completed.returncode != 0:
        status["state"] = "failed_runtime"
        atomic_json(work / "status.json", status)
        print(json.dumps(status, sort_keys=True))
        return 1

    try:
        generator_manifest = validate_generator_manifest(generated, row, args.threads)
        final.parent.mkdir(parents=True, exist_ok=True)
        staging = final.parent / f".{final.name}.staging.{os.getpid()}"
        if staging.exists():
            raise RuntimeError(f"staging already exists: {staging}")
        shutil.copytree(generated, staging)
        (staging / "manifest.json").unlink()
        shutil.copy2(work / "launcher.stdout", staging / "launcher.stdout")
        shutil.copy2(work / "launcher.stderr", staging / "launcher.stderr")
        manifest = {
            "schema_version": 1,
            "formal_identity": expected_identity(
                row, args.matrix_id, args.policy_sha256
            ),
            "execution": {
                "started_utc": status["started_utc"],
                "finished_utc": status["finished_utc"],
                "elapsed_seconds": elapsed,
                "threads": args.threads,
                "cpu_list": cpus,
                "command": launch,
                "environment": {
                    key: environment[key]
                    for key in (
                        "OMP_NUM_THREADS",
                        "OMP_DYNAMIC",
                        "OMP_PROC_BIND",
                        "OMP_PLACES",
                        "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "VECLIB_MAXIMUM_THREADS",
                    )
                },
                "platform": {
                    "system": platform.system(),
                    "machine": platform.machine(),
                    "release": platform.release(),
                    "python": platform.python_version(),
                },
                "toolchain": toolchain_record(),
            },
            "generator_manifest": generator_manifest,
            "outputs": inventory(staging),
        }
        atomic_json(staging / "manifest.json", manifest)
        os.replace(staging, final)
        valid, reason = validate_completed_result(
            final, row, args.matrix_id, args.policy_sha256
        )
        if not valid:
            raise RuntimeError(f"post-publish validation failed: {reason}")
    except Exception as error:
        status["state"] = "failed_validation"
        status["error"] = str(error)
        atomic_json(work / "status.json", status)
        print(json.dumps(status, sort_keys=True))
        return 1

    status["state"] = "completed"
    status["result"] = str(final)
    atomic_json(work / "status.json", status)
    if not args.keep_work:
        safe_remove_generator_work(completed.stderr)
        shutil.rmtree(work)
        for parent in (work.parent, work.parent.parent):
            try:
                parent.rmdir()
            except OSError:
                pass
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
