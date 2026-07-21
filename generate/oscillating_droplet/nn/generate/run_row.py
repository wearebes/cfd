#!/usr/bin/env python3
"""Prepare, audit, compile and run one oscillating-droplet row.

This benchmark keeps its Python orchestration because its scientific artifact
contract is richer than the shell runners.  It nevertheless exposes the same
resolved-plan interface: explicit output, resolution, model, purpose, thread
count, dry-run and a manifest written before compilation starts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve()
CASE = HERE.parents[1]
ROOT = HERE.parents[4]
BASILISK = ROOT / "basilisk/src"
SOURCE = CASE / "src/oscillation-nn-single-level.c"
ADAPTER = CASE / "src/oscillation_raw27_adapter.h"
SHARED = ROOT / "generate/_shared/nn_runtime/src"
MANIFEST_TOOL = ROOT / "generate/_shared/run_manifest.py"
RUNTIME_REDISTANCE_OVERLAY = HERE.parent / "make_runtime_redistance_overlay.py"
CHECKPOINT_OVERLAY = ROOT / "generate/_shared/make_checkpoint_overlay.py"
SCIENTIFIC_BUILDER = ROOT / "generate/_shared/build_scientific_artifacts.py"
INFER = SHARED / "clsvof_mlp_infer.h"
HOST = ROOT / "generate/oscillating_droplet/clsvof_extension/oscillation-clsvof.c"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def parse_stats(stderr: str) -> dict[str, int | float] | None:
    lines = [
        line
        for line in stderr.splitlines()
        if line.startswith("kappa_offset_provider_stats ")
    ]
    if not lines:
        return None
    if len(lines) != 1:
        raise RuntimeError(f"expected one provider stats line, found {len(lines)}")
    values: dict[str, int | float] = {}
    integer_fields = {
        "evaluations",
        "clamp_hits",
        "denominator_guard_hits",
        "grad_samples",
    }
    for item in lines[0].split()[1:]:
        key, value = item.split("=", 1)
        values[key] = int(value) if key in integer_fields else float(value)
    return values


def required_files(level: int, fit: bool, snapshots: bool = False) -> list[str]:
    names = [
        f"k-{level}",
        "out",
        "runtime.stderr.txt",
        "command.txt",
        "checkpoint_index.csv",
    ]
    if fit:
        names.extend([f"fit-{level}", "fit.log", "error", "laplace", "log"])
    if snapshots:
        names.extend(
            ["snapshot_times.csv"]
            + [f"interface-{index:02d}.dat" for index in range(5)]
        )
    return names


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def prepare_sources(
    work: Path,
    *,
    method_nn: bool,
    model_dir: Path | None,
) -> None:
    (work / "checkpoints").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(CHECKPOINT_OVERLAY),
            str(SOURCE),
            str(work / "source.c"),
            "--case",
            "oscillating_droplet",
            "--provenance",
            str(work / "checkpoint_overlay.json"),
        ],
        check=True,
        cwd=ROOT,
    )
    shutil.copy2(ADAPTER, work / ADAPTER.name)
    shutil.copy2(BASILISK / "integral.h", work / "integral.stock.h")
    subprocess.run(
        [
            sys.executable,
            str(RUNTIME_REDISTANCE_OVERLAY),
            str(BASILISK / "two-phase-clsvof.h"),
            str(work / "two-phase-clsvof.h"),
            "--provenance",
            str(work / "redistance_overlay.json"),
        ],
        check=True,
        cwd=ROOT,
    )
    if method_nn:
        assert model_dir is not None
        for source in (
            SHARED / "clsvof_nn_cell_curvature.h",
            SHARED / "kappa_offset_stats.h",
            INFER,
            model_dir / "nn_weights.h",
            model_dir / "export_manifest.json",
        ):
            shutil.copy2(source, work / source.name)
        subprocess.run(
            [
                sys.executable,
                str(SHARED / "make_overlay_integral.py"),
                str(BASILISK / "integral.h"),
                str(work / "integral.h"),
            ],
            check=True,
            cwd=ROOT,
        )


def snapshot_sources(work: Path, method_nn: bool) -> None:
    snapshot = work / "source_snapshot"
    snapshot.mkdir()
    names = [
        "source.c",
        ADAPTER.name,
        "integral.stock.h",
        "two-phase-clsvof.h",
        "checkpoint_overlay.json",
        "redistance_overlay.json",
    ]
    if method_nn:
        names.extend(
            [
                "integral.h",
                "clsvof_nn_cell_curvature.h",
                "kappa_offset_stats.h",
                "clsvof_mlp_infer.h",
                "nn_weights.h",
                "export_manifest.json",
            ]
        )
    for name in names:
        shutil.copy2(work / name, snapshot / name)


def plan_arguments(
    *,
    args: argparse.Namespace,
    output: Path,
    work: Path,
    level: int,
    model_name: str | None,
    model_dir: Path | None,
    checkpoint: Path | None,
    compile_cmd: list[str],
    run_cmd: list[str],
    method_nn: bool,
) -> list[str]:
    purpose = "formal" if args.formal else "smoke"
    values = [
        "--repo-root",
        str(ROOT),
        "--case",
        "oscillating_droplet",
        "--benchmark",
        "oscillating_droplet",
        "--method",
        args.method,
        "--purpose",
        purpose,
        "--output",
        str(output),
        "--generator",
        str(HERE),
        "--generator-logical",
        "generate/oscillating_droplet/nn/generate/run_row.py",
    ]
    parameters: dict[str, object] = {
        "resolution": 1 << level,
        "level": level,
        "imax": args.imax,
        "model": model_name,
        "openmp_threads": args.threads,
        "compile_only": args.compile_only,
        "t_end": args.t_end,
        "fit_enabled": not args.no_fit,
        "snapshots_enabled": args.snapshots,
    }
    for key, value in parameters.items():
        values.extend(["--parameter", f"{key}={json.dumps(value)}"])
    sources: list[tuple[str, str, Path]] = [
        ("host_case", "generate/oscillating_droplet/clsvof_extension/oscillation-clsvof.c", HOST),
        ("single_level_case", "generate/oscillating_droplet/nn/src/oscillation-nn-single-level.c", SOURCE),
        ("compiled_case", "source_snapshot/source.c", work / "source.c"),
        ("oscillation_adapter", f"source_snapshot/{ADAPTER.name}", work / ADAPTER.name),
        ("stock_integral", "source_snapshot/integral.stock.h", work / "integral.stock.h"),
        ("compiled_two_phase", "source_snapshot/two-phase-clsvof.h", work / "two-phase-clsvof.h"),
        ("checkpoint_overlay", "source_snapshot/checkpoint_overlay.json", work / "checkpoint_overlay.json"),
        ("redistance_overlay", "source_snapshot/redistance_overlay.json", work / "redistance_overlay.json"),
        ("qcc", "basilisk/src/qcc", BASILISK / "qcc"),
    ]
    if method_nn:
        assert model_dir is not None and checkpoint is not None
        sources.extend(
            [
                ("compiled_integral", "source_snapshot/integral.h", work / "integral.h"),
                ("nn_runtime", "source_snapshot/clsvof_nn_cell_curvature.h", work / "clsvof_nn_cell_curvature.h"),
                ("nn_stats", "source_snapshot/kappa_offset_stats.h", work / "kappa_offset_stats.h"),
                ("nn_inference", "source_snapshot/clsvof_mlp_infer.h", work / "clsvof_mlp_infer.h"),
                ("nn_weights", "source_snapshot/nn_weights.h", work / "nn_weights.h"),
                ("model_export", "source_snapshot/export_manifest.json", work / "export_manifest.json"),
                ("training_checkpoint", str(checkpoint.relative_to(ROOT)), checkpoint),
            ]
        )
    if args.precompiled:
        sources.append(
            (
                "precompiled_executable",
                str(args.precompiled.resolve()),
                args.precompiled.resolve(),
            )
        )
    for label, logical, actual in sources:
        values.extend(["--source", f"{label}={logical}::{actual}"])
    values.extend(
        [
            "--compile-cwd",
            "$WORK",
            "--compile-stdout",
            "compile.stdout",
            "--compile-stderr",
            "compile.stderr",
            "--run-cwd",
            "$WORK",
            "--run-stdout",
            "out",
            "--run-stderr",
            "runtime.stderr.txt",
            "--run-env",
            f"OSCILLATION_REDISTANCE_IMAX={args.imax}",
            "--run-env",
            f"OMP_NUM_THREADS={args.threads}",
        ]
    )
    for item in compile_cmd:
        values.append(f"--compile-arg={item}")
    for item in run_cmd:
        values.append(f"--run-arg={item}")
    return values


def transition(action: str, plan_args: list[str], *extra: str) -> None:
    subprocess.run(
        [sys.executable, str(MANIFEST_TOOL), action, *plan_args, *extra],
        check=True,
        cwd=ROOT,
    )


def merge_manifest(path: Path, fields: dict[str, Any]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(fields)
    atomic_json(path, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("clsvof", "nn", "probe"), required=True)
    resolution = parser.add_mutually_exclusive_group(required=True)
    resolution.add_argument("--resolution", type=int, choices=(64, 128, 256, 512))
    resolution.add_argument("--level", type=int, choices=(6, 7, 8, 9), help=argparse.SUPPRESS)
    parser.add_argument("--imax", type=int, choices=range(6), default=3)
    parser.add_argument("--model")
    purpose = parser.add_mutually_exclusive_group()
    purpose.add_argument("--smoke", action="store_true")
    purpose.add_argument("--formal", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=positive_int, default=1)
    parser.add_argument("--t-end", type=float, default=1.0)
    parser.add_argument("--no-fit", action="store_true")
    parser.add_argument("--snapshots", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--precompiled", type=Path)
    args = parser.parse_args(argv)

    if args.compile_only and args.precompiled:
        parser.error("--compile-only and --precompiled are mutually exclusive")
    if args.formal and (args.method == "probe" or args.t_end != 1.0 or args.no_fit):
        parser.error("formal rows require method clsvof|nn, --t-end 1.0 and fitting")
    level = args.level if args.level is not None else args.resolution.bit_length() - 1
    resolution_value = 1 << level
    method_nn = args.method in {"nn", "probe"}
    if args.model and not method_nn:
        parser.error("--model is only valid for nn or probe")
    model_name = args.model or (
        f"baseline_{resolution_value}_hgradient" if method_nn else None
    )
    model_dir = ROOT / "dataset/model/c_exports" / model_name if model_name else None
    checkpoint = ROOT / "dataset/model" / f"{model_name}.pt" if model_name else None

    dependencies = [
        SOURCE,
        ADAPTER,
        HOST,
        BASILISK / "integral.h",
        BASILISK / "two-phase-clsvof.h",
        BASILISK / "redistance.h",
        BASILISK / "qcc",
        RUNTIME_REDISTANCE_OVERLAY,
        CHECKPOINT_OVERLAY,
        SCIENTIFIC_BUILDER,
        MANIFEST_TOOL,
    ]
    if method_nn:
        assert model_dir is not None and checkpoint is not None
        dependencies.extend(
            [
                SHARED / "clsvof_nn_cell_curvature.h",
                SHARED / "kappa_offset_stats.h",
                SHARED / "make_overlay_integral.py",
                INFER,
                model_dir / "nn_weights.h",
                model_dir / "export_manifest.json",
                checkpoint,
            ]
        )
    if args.precompiled:
        dependencies.append(args.precompiled.resolve())
    missing = [str(path) for path in dependencies if not path.is_file()]
    if missing:
        raise SystemExit("missing dependencies:\n" + "\n".join(missing))

    output = args.output.resolve()
    if not args.dry_run and output.exists():
        raise SystemExit(f"output already exists: {output}")

    fit = not args.no_fit
    defines = [
        f"-DLEVEL={level}",
        f"-DT_END={args.t_end:.17g}",
        f"-DENABLE_FIT={1 if fit else 0}",
        f"-DENABLE_SNAPSHOTS={1 if args.snapshots else 0}",
        f"-DMETHOD_NN={1 if method_nn else 0}",
    ]
    if args.method == "probe":
        defines.extend(
            ["-DKAPPA_OFFSET_PROBE_ONLY=1", "-DKAPPA_OFFSET_INITIAL_PROBE_SAMPLES=512"]
        )
    if args.precompiled:
        compile_cmd = ["cp", str(args.precompiled.resolve()), "oscillation"]
    else:
        compile_cmd = [
            str(BASILISK / "qcc"),
            "-O2",
            "-DMTRACE=3",
            "-Wall",
            "-Wno-unused-function",
            "-pipe",
        ]
        if args.threads > 1:
            compile_cmd.append("-fopenmp")
        compile_cmd.extend([*defines, "source.c", "-o", "oscillation", "-lm"])
    run_cmd = [] if args.compile_only else ["./oscillation"]

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.dry_run:
        temporary = tempfile.TemporaryDirectory(prefix="cfd-oscillation-plan-")
        work = Path(temporary.name)
    else:
        output.mkdir(parents=True)
        work = output

    manifest_path = output / "manifest.json"
    manifest_started = False
    try:
        prepare_sources(work, method_nn=method_nn, model_dir=model_dir)
        plan_args = plan_arguments(
            args=args,
            output=output,
            work=work,
            level=level,
            model_name=model_name,
            model_dir=model_dir,
            checkpoint=checkpoint,
            compile_cmd=compile_cmd,
            run_cmd=run_cmd,
            method_nn=method_nn,
        )
        if args.dry_run:
            transition("dry-run", plan_args)
            return 0

        snapshot_sources(work, method_nn)
        transition("start", plan_args, "--manifest", str(manifest_path))
        manifest_started = True
        (work / "command.txt").write_text(
            shlex.join(compile_cmd)
            + (" && " + shlex.join(run_cmd) if run_cmd else "")
            + "\n",
            encoding="utf-8",
        )
        started_at = utc_now()
        started_epoch = time.monotonic()
        environment = os.environ.copy()
        environment["BASILISK"] = str(BASILISK)
        environment["OSCILLATION_REDISTANCE_IMAX"] = str(args.imax)
        environment["OMP_NUM_THREADS"] = str(args.threads)
        if args.precompiled:
            shutil.copy2(args.precompiled.resolve(), work / "oscillation")
            compile_completed = subprocess.CompletedProcess(
                compile_cmd, 0, "precompiled executable reused\n", ""
            )
        else:
            compile_completed = subprocess.run(
                compile_cmd,
                cwd=work,
                env=environment,
                text=True,
                capture_output=True,
            )
        (work / "compile.stdout").write_text(compile_completed.stdout, encoding="utf-8")
        (work / "compile.stderr").write_text(compile_completed.stderr, encoding="utf-8")

        common_fields: dict[str, Any] = {
            "case_id": "oscillating_droplet",
            "method_id": "CLSVOF" if args.method == "clsvof" else (
                "CLSVOF_NN_PROBE_ONLY" if args.method == "probe" else "CLSVOF_NN_CELL_OFFSET"
            ),
            "evidence_level": "formal" if args.formal else "smoke",
            "level": level,
            "N": resolution_value,
            "cells_per_diameter": 0.2 / 0.5 * resolution_value,
            "t_end": args.t_end,
            "fit_enabled": fit,
            "snapshots_enabled": args.snapshots,
            "model_name": model_name,
            "checkpoint_sha256": sha256(checkpoint) if checkpoint else None,
            "weights_sha256": sha256(model_dir / "nn_weights.h") if model_dir else None,
            "export_manifest_sha256": sha256(model_dir / "export_manifest.json") if model_dir else None,
            "host_source_sha256": sha256(HOST),
            "single_level_source_sha256": sha256(SOURCE),
            "generated_single_level_source_sha256": sha256(work / "source.c"),
            "checkpoint_overlay_sha256": sha256(work / "checkpoint_overlay.json"),
            "two_phase_clsvof_sha256": sha256(BASILISK / "two-phase-clsvof.h"),
            "generated_two_phase_clsvof_sha256": sha256(work / "two-phase-clsvof.h"),
            "redistance_overlay_sha256": sha256(work / "redistance_overlay.json"),
            "stock_integral_sha256": sha256(BASILISK / "integral.h"),
            "generated_integral_sha256": sha256(work / "integral.h") if method_nn else None,
            "shared_provider_sha256": sha256(SHARED / "clsvof_nn_cell_curvature.h") if method_nn else None,
            "oscillation_adapter_sha256": sha256(ADAPTER),
            "feature_order": "phi9+nx9+ny9",
            "raw27_order": "j:+1..-1, i:-1..+1",
            "model_phi_sign": "outside_positive",
            "solver_d_sign": "inside_positive",
            "solver_to_model_sign": -1 if method_nn else None,
            "model_output": "Delta*kappa_gamma_model" if method_nn else None,
            "solver_output": "kappa_cell_solver" if method_nn else "distance_curvature(point,d)",
            "nn_provider": "cell_offset" if method_nn else None,
            "denominator_guard": 0.25 if method_nn else None,
            "clamp_factor": 1.0 if method_nn else None,
            "redistance_imax": args.imax,
            "compile_reused": bool(args.precompiled),
            "precompiled_executable_sha256": sha256(args.precompiled.resolve()) if args.precompiled else None,
            "compile_command": shlex.join(compile_cmd),
            "compile_returncode": compile_completed.returncode,
            "started_at": started_at,
            "dependency_hashes": {
                str(path.relative_to(ROOT)): sha256(path)
                for path in dependencies
                if ROOT in path.parents
            },
        }

        if args.compile_only:
            compiled = compile_completed.returncode == 0 and (work / "oscillation").is_file()
            compile_manifest = {
                "case_id": "oscillating_droplet",
                "status": "compiled" if compiled else "failed",
                "level": level,
                "N": resolution_value,
                "method": args.method,
                "model_name": model_name,
                "compile_command": shlex.join(compile_cmd),
                "compile_returncode": compile_completed.returncode,
                "executable_sha256": sha256(work / "oscillation") if compiled else None,
                "created_at": utc_now(),
            }
            atomic_json(work / "compile_manifest.json", compile_manifest)
            common_fields.update(
                {
                    "run_returncode": None,
                    "ended_at": utc_now(),
                    "wall_seconds": time.monotonic() - started_epoch,
                    "provider_stats": None,
                }
            )
            merge_manifest(manifest_path, common_fields)
            if not compiled:
                transition("fail", [], "--manifest", str(manifest_path), "--error", "compilation failed")
                return 1
            transition(
                "complete",
                plan_args,
                "--manifest",
                str(manifest_path),
                "--elapsed-seconds",
                str(common_fields["wall_seconds"]),
            )
            print(json.dumps({"output": str(output), "status": "compiled"}, sort_keys=True))
            return 0

        run_returncode: int | None = None
        if compile_completed.returncode == 0:
            with (work / "out").open("w", encoding="utf-8") as stdout, (
                work / "runtime.stderr.txt"
            ).open("w", encoding="utf-8") as stderr:
                run_returncode = subprocess.run(
                    run_cmd,
                    cwd=work,
                    env=environment,
                    text=True,
                    stdout=stdout,
                    stderr=stderr,
                ).returncode
        runtime_stderr = (
            (work / "runtime.stderr.txt").read_text(encoding="utf-8")
            if (work / "runtime.stderr.txt").is_file()
            else ""
        )
        numerical_failure_lines = [
            line
            for line in runtime_stderr.splitlines()
            if line.startswith("OSCILLATION_NUMERICAL_FAILURE ")
        ]
        stats = parse_stats(runtime_stderr) if method_nn and run_returncode == 0 else None
        artifacts_complete = all(
            (work / name).is_file()
            and (name == "runtime.stderr.txt" or (work / name).stat().st_size > 0)
            for name in required_files(level, fit, args.snapshots)
        ) and all(
            path.is_file() and path.stat().st_size > 0
            for path in [work / "checkpoints/terminal.dump", work / "checkpoint_overlay.json"]
        )
        completed = (
            compile_completed.returncode == 0
            and run_returncode == 0
            and artifacts_complete
        )
        elapsed = time.monotonic() - started_epoch
        common_fields.update(
            {
                "run_returncode": run_returncode,
                "ended_at": utc_now(),
                "wall_seconds": elapsed,
                "provider_stats": stats,
                "numerical_failure": numerical_failure_lines[-1] if numerical_failure_lines else None,
            }
        )
        merge_manifest(manifest_path, common_fields)
        if not completed:
            transition(
                "fail",
                [],
                "--manifest",
                str(manifest_path),
                "--error",
                "compile, runtime, or required-artifact validation failed",
            )
            print(json.dumps({"output": str(output), "status": "failed"}, sort_keys=True))
            return 1

        subprocess.run(
            [sys.executable, str(SCIENTIFIC_BUILDER), str(work)],
            check=True,
            cwd=ROOT,
        )
        transition(
            "complete",
            plan_args,
            "--manifest",
            str(manifest_path),
            "--elapsed-seconds",
            str(elapsed),
        )
        print(
            json.dumps(
                {
                    "output": str(output),
                    "status": "completed",
                    "wall_seconds": elapsed,
                    "provider_stats": stats,
                },
                sort_keys=True,
            )
        )
        return 0
    except BaseException as error:
        if manifest_started and manifest_path.is_file():
            subprocess.run(
                [
                    sys.executable,
                    str(MANIFEST_TOOL),
                    "fail",
                    "--manifest",
                    str(manifest_path),
                    "--error",
                    f"{type(error).__name__}: {error}",
                ],
                cwd=ROOT,
                check=False,
            )
        raise
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
