#!/usr/bin/env python3
"""Build and transition reproducible row manifests from one resolved run plan.

The runner constructs its compile/run argument arrays once and passes the same
arguments to ``dry-run``, ``start`` and ``complete``.  ``complete`` refuses to
transition the manifest when any planned source, parameter or command changed
after ``start``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def parse_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_pairs(values: list[str], option: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"{option} expects KEY=VALUE, got: {value}")
        key, raw = value.split("=", 1)
        if not key or key in parsed:
            raise SystemExit(f"invalid or duplicate {option} key: {key!r}")
        parsed[key] = parse_value(raw)
    return dict(sorted(parsed.items()))


def parse_sources(values: list[str]) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--source expects LABEL=LOGICAL_PATH::ACTUAL_PATH: {value}")
        label, paths = value.split("=", 1)
        if not label or label in sources:
            raise SystemExit(f"invalid or duplicate source label: {label!r}")
        if "::" in paths:
            logical, actual_text = paths.split("::", 1)
        else:
            logical = actual_text = paths
        actual = Path(actual_text)
        if not actual.is_file():
            raise SystemExit(f"missing planned source {label}: {actual}")
        sources[label] = {
            "path": logical,
            "sha256": sha256_file(actual),
            "bytes": actual.stat().st_size,
        }
    return dict(sorted(sources.items()))


def command_record(
    argv: list[str], cwd: str, stdout_path: str, stderr_path: str
) -> dict[str, Any]:
    display = shlex.join(argv)
    if stdout_path:
        display += f" > {shlex.quote(stdout_path)}"
    if stderr_path:
        display += f" 2> {shlex.quote(stderr_path)}"
    return {
        "argv": argv,
        "cwd": cwd,
        "stdout": stdout_path,
        "stderr": stderr_path,
        "display": display,
    }


def git_record(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout.strip()

    try:
        commit = run("rev-parse", "HEAD")
        status = run("status", "--porcelain", "--untracked-files=normal")
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None, "changed_path_count": None}
    return {
        "commit": commit,
        "dirty": bool(status),
        "changed_path_count": len(status.splitlines()) if status else 0,
    }


def canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    generator = Path(args.generator)
    if not generator.is_file():
        raise SystemExit(f"missing generator: {generator}")
    compile_record = command_record(
        args.compile_arg,
        args.compile_cwd,
        args.compile_stdout,
        args.compile_stderr,
    )
    run_record = command_record(
        args.run_arg,
        args.run_cwd,
        args.run_stdout,
        args.run_stderr,
    )
    core = {
        "case": args.case,
        "benchmark": args.benchmark,
        "method": args.method,
        "purpose": args.purpose,
        "output": str(Path(args.output).resolve()),
        "generator": {
            "path": args.generator_logical,
            "sha256": sha256_file(generator),
        },
        "parameters": parse_pairs(args.parameter, "--parameter"),
        "environment": parse_pairs(args.run_env, "--run-env"),
        "commands": {"compile": compile_record, "run": run_record},
        "sources": parse_sources(args.source),
    }
    return {**core, "plan_sha256": canonical_sha256(core)}


def payload_for(plan: dict[str, Any], status: str, root: Path) -> dict[str, Any]:
    parameters = plan["parameters"]
    sources = plan["sources"]
    artifact_sources = {
        "cell_curvature_sha256": "nn_runtime",
        "stats_header_sha256": "nn_stats",
        "inference_header_sha256": "nn_inference",
        "weights_sha256": "nn_weights",
        "integral_sha256": "compiled_integral",
        "two_phase_clsvof_sha256": "compiled_two_phase",
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "plan": plan,
        "git": git_record(root),
        "created_at": utc_now(),
        "artifacts": {
            field: sources[label]["sha256"]
            for field, label in artifact_sources.items()
            if label in sources
        },
    }
    # Keep the row identity at the top level so campaign verification does not
    # need to reinterpret the richer resolved-plan schema.
    for key in (
        "resolution",
        "level",
        "imax",
        "model",
        "openmp_threads",
        "benchmark_case",
        "actual_grid",
        "tau_max",
        "experiment_role",
        "solver_variant",
        "grid_strategy",
        "grid_role",
        "cells_per_diameter",
    ):
        if key in parameters:
            payload[key] = parameters[key]
    payload.update(
        {
            "case": plan["case"],
            "benchmark": plan["benchmark"],
            "method": plan["method"],
            "purpose": plan["purpose"],
            "generator": plan["generator"]["path"],
        }
    )
    return payload


def add_plan_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--method", choices=("VOF-HF", "CLSVOF", "NN"), required=True)
    parser.add_argument("--purpose", choices=("smoke", "formal"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--generator", required=True)
    parser.add_argument("--generator-logical", required=True)
    parser.add_argument("--parameter", action="append", default=[])
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--compile-arg", action="append", default=[])
    parser.add_argument("--compile-cwd", default="$WORK")
    parser.add_argument("--compile-stdout", default="compile.stdout")
    parser.add_argument("--compile-stderr", default="compile.stderr")
    parser.add_argument("--run-arg", action="append", default=[])
    parser.add_argument("--run-cwd", default="$WORK")
    parser.add_argument("--run-stdout", default="stdout.txt")
    parser.add_argument("--run-stderr", default="stderr.txt")
    parser.add_argument("--run-env", action="append", default=[])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    dry_run = subparsers.add_parser("dry-run")
    add_plan_arguments(dry_run)
    start = subparsers.add_parser("start")
    add_plan_arguments(start)
    start.add_argument("--manifest", type=Path, required=True)
    complete = subparsers.add_parser("complete")
    add_plan_arguments(complete)
    complete.add_argument("--manifest", type=Path, required=True)
    complete.add_argument("--elapsed-seconds", type=float, required=True)
    fail = subparsers.add_parser("fail")
    fail.add_argument("--manifest", type=Path, required=True)
    fail.add_argument("--error", required=True)
    args = parser.parse_args(argv)

    if args.action == "dry-run":
        payload = payload_for(build_plan(args), "planned", args.repo_root)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.action == "fail":
        if not args.manifest.is_file():
            return 0
        payload = json.loads(args.manifest.read_text())
        if payload.get("status") == "completed":
            raise SystemExit("cannot fail a completed manifest")
        payload["status"] = "failed"
        payload["failed_at"] = utc_now()
        payload["error"] = args.error
        atomic_json(args.manifest, payload)
        return 0

    plan = build_plan(args)
    if args.action == "start":
        if args.manifest.exists():
            raise SystemExit(f"manifest already exists: {args.manifest}")
        payload = payload_for(plan, "running", args.repo_root)
        payload["started_at"] = utc_now()
        atomic_json(args.manifest, payload)
        return 0

    payload = json.loads(args.manifest.read_text())
    if payload.get("status") != "running":
        raise SystemExit(f"manifest is not running: {payload.get('status')}")
    before = payload.get("plan", {}).get("plan_sha256")
    after = plan["plan_sha256"]
    if before != after:
        raise SystemExit(
            f"resolved run plan changed after start: before={before} after={after}"
        )
    payload["plan"] = plan
    payload["status"] = "completed"
    payload["completed_at"] = utc_now()
    payload["elapsed_seconds"] = args.elapsed_seconds
    atomic_json(args.manifest, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
