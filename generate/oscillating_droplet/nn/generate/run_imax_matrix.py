#!/usr/bin/env python3
"""Run the paired oscillating-droplet redistance-imax matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]
RUN_ROW = HERE.parent / "run_row.py"
RESULT_BASE = ROOT / "hpc/results/oscillating_droplet/nn_redistance_imax"
LEVELS = (6, 7, 8, 9)
IMAX_VALUES = tuple(range(6))
METHODS = ("clsvof", "nn")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def row_id(level: int, imax: int, method: str) -> str:
    return f"N{1 << level:04d}__imax{imax:02d}__{method}"


def row_output(root: Path, level: int, imax: int, method: str) -> Path:
    method_dir = method
    return root / f"N{1 << level:04d}" / f"imax_{imax}" / method_dir


def estimated_cost(level: int, imax: int, method: str) -> float:
    n = 1 << level
    factor = {0: 0.65, 1: 0.77, 2: 0.88, 3: 1.0, 4: 1.12, 5: 1.23}[imax]
    if method == "nn":
        base = {64: 210.0, 128: 240.0, 256: 1900.0, 512: 18600.0}[n]
    else:
        base = {64: 11.0, 128: 26.0, 256: 210.0, 512: 1900.0}[n]
    return base * factor


def complete(path: Path) -> bool:
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return manifest["status"] == "completed" or (
            manifest["status"] == "failed" and bool(manifest.get("numerical_failure"))
        )
    except (KeyError, json.JSONDecodeError):
        return False


def compile_output(root: Path, level: int, method: str) -> Path:
    return root / "precompiled" / f"N{1 << level:04d}" / method


def compiled(path: Path) -> bool:
    manifest_path = path / "compile_manifest.json"
    if not manifest_path.is_file() or not (path / "oscillation").is_file():
        return False
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "compiled"
    except (KeyError, json.JSONDecodeError):
        return False


def compile_one(root: Path, level: int, method: str, resume: bool) -> dict[str, object]:
    output = compile_output(root, level, method)
    identifier = f"N{1 << level:04d}__{method}"
    if resume and compiled(output):
        return {"compile_id": identifier, "state": "reused", "returncode": 0}
    if output.exists():
        raise RuntimeError(f"incomplete compile output exists for {identifier}: {output}")
    command = [
        sys.executable,
        str(RUN_ROW),
        "--method",
        method,
        "--resolution",
        str(1 << level),
        "--formal",
        "--threads",
        "1",
        "--compile-only",
        "--output",
        str(output),
    ]
    log_path = root / "launcher_logs" / f"compile__{identifier}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with log_path.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
            text=True, check=False,
        )
    return {
        "compile_id": identifier,
        "state": "compiled" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "wall_seconds": time.time() - started,
        "log": str(log_path.relative_to(root)),
    }


def run_one(root: Path, level: int, imax: int, method: str, resume: bool) -> dict[str, object]:
    identifier = row_id(level, imax, method)
    output = row_output(root, level, imax, method)
    if resume and complete(output):
        return {"row_id": identifier, "state": "reused", "returncode": 0, "ended_at": utc_now()}
    if output.exists():
        raise RuntimeError(f"incomplete output exists for {identifier}: {output}")
    command = [
        sys.executable,
        str(RUN_ROW),
        "--method",
        method,
        "--resolution",
        str(1 << level),
        "--formal",
        "--threads",
        "1",
        "--imax",
        str(imax),
        "--precompiled",
        str(compile_output(root, level, method) / "oscillation"),
        "--output",
        str(output),
    ]
    log_path = root / "launcher_logs" / f"{identifier}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with log_path.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": "started", "row_id": identifier, "command": command}) + "\n")
        stream.flush()
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    return {
        "row_id": identifier,
        "state": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "wall_seconds": time.time() - started,
        "ended_at": utc_now(),
        "log": str(log_path.relative_to(root)),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.jobs < 1 or args.jobs > 4:
        raise SystemExit("--jobs must be from 1 through 4")
    result_root = RESULT_BASE / args.run_id
    if result_root.exists() and not args.resume:
        raise SystemExit(f"result root already exists: {result_root}")

    rows = [
        (level, imax, method)
        for level in LEVELS
        for imax in IMAX_VALUES
        for method in METHODS
    ]
    rows.sort(key=lambda item: (-estimated_cost(*item), row_id(*item)))
    contract = {
        "case_id": "oscillating_droplet",
        "matrix_id": args.run_id,
        "levels": list(LEVELS),
        "resolutions": [1 << level for level in LEVELS],
        "imax": list(IMAX_VALUES),
        "methods": ["CLSVOF_NATIVE", "CLSVOF_NN_CELL_OFFSET"],
        "expected_rows": len(rows),
        "max_active_rows": args.jobs,
        "row_isolation": True,
        "created_at": utc_now(),
        "run_row_sha256": sha256(RUN_ROW),
    }
    if args.dry_run:
        for level, imax, method in rows:
            print(json.dumps({
                "row_id": row_id(level, imax, method),
                "level": level,
                "N": 1 << level,
                "imax": imax,
                "method": method,
                "estimated_cost": estimated_cost(level, imax, method),
                "output": str(row_output(result_root, level, imax, method)),
            }, sort_keys=True))
        print(json.dumps(contract, sort_keys=True))
        return 0

    result_root.mkdir(parents=True, exist_ok=args.resume)
    atomic_json(result_root / "matrix_contract.json", contract)
    compile_records: list[dict[str, object]] = []
    compile_rows = [(level, method) for level in LEVELS for method in METHODS]
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {
            executor.submit(compile_one, result_root, level, method, args.resume):
            f"N{1 << level:04d}__{method}"
            for level, method in compile_rows
        }
        for future in as_completed(futures):
            identifier = futures[future]
            try:
                record = future.result()
            except Exception as error:
                record = {"compile_id": identifier, "state": "failed", "returncode": 1, "error": repr(error)}
            compile_records.append(record)
            atomic_json(result_root / "precompile_status.json", {
                "expected": len(compile_rows),
                "completed": sum(item["state"] in {"compiled", "reused"} for item in compile_records),
                "failed": sum(item["state"] == "failed" for item in compile_records),
                "records": sorted(compile_records, key=lambda item: str(item["compile_id"])),
                "updated_at": utc_now(),
            })
            print(json.dumps(record, sort_keys=True), flush=True)
    if any(record["state"] == "failed" for record in compile_records):
        return 1

    records: dict[str, dict[str, object]] = {}
    started_at = utc_now()
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {
            executor.submit(run_one, result_root, level, imax, method, args.resume):
            row_id(level, imax, method)
            for level, imax, method in rows
        }
        for future in as_completed(futures):
            identifier = futures[future]
            try:
                record = future.result()
            except Exception as error:  # keep the other isolated rows running
                record = {
                    "row_id": identifier,
                    "state": "failed",
                    "returncode": 1,
                    "error": repr(error),
                    "ended_at": utc_now(),
                }
            records[identifier] = record
            atomic_json(result_root / "matrix_status.json", {
                "matrix_id": args.run_id,
                "expected_rows": len(rows),
                "jobs": args.jobs,
                "started_at": started_at,
                "updated_at": utc_now(),
                "completed": sum(item["state"] in {"completed", "reused"} for item in records.values()),
                "failed": sum(item["state"] == "failed" for item in records.values()),
                "remaining": len(rows) - len(records),
                "records": [records[key] for key in sorted(records)],
            })
            print(json.dumps(record, sort_keys=True), flush=True)
    failures = [record for record in records.values() if record["state"] == "failed"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
