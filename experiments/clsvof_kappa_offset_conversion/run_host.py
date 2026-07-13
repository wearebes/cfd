#!/usr/bin/env python3
"""Run one isolated stock-host replay with one curvature-provider mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = Path(__file__).resolve().parent
PYTHON = Path("/opt/anaconda3/envs/pinn/bin/python")
MODEL_NAMES = ("baseline_64_hgradient", "baseline_128_hgradient",
               "baseline_256_hgradient", "baseline_512_hgradient")
MODES = ("nn_cell_levelset",)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_t0_stop(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(text + "\n\nevent kappa_offset_t0_stop (i = 1)\n  return 1;\n",
                    encoding="utf-8")


def materialize_case(args: argparse.Namespace, work: Path) -> tuple[Path, list[str]]:
    if args.benchmark == "rising":
        source = ROOT/"basilisk/src/test/rising.c"
        target = work/"rising-clsvof.c"
        shutil.copyfile(source, target)
        flags = ["-DLEVELSET=1", "-DCLSVOF=1"]
        if args.case == "case2":
            flags.append("-DCASE2=1")
    else:
        source = ROOT/"basilisk/src/test/capwave-clsvof.c"
        target = work/"capwave-clsvof.c"
        subprocess.run(
            [str(PYTHON), str(ROOT/"experiments/capwave_clsvof_kreplace/make_single_resolution_case.py"),
             str(source), str(target), "--resolution", str(args.resolution)],
            check=True,
        )
        shutil.copyfile(ROOT/"basilisk/src/test/prosperetti.h", work/"prosperetti.h")
        flags = ["-DCLSVOF=1"]
    if args.t0_only:
        append_t0_stop(target)
    return target, flags


def add_overlay(args: argparse.Namespace, work: Path, flags: list[str]) -> list[str]:
    subprocess.run(
        [str(PYTHON), str(EXPERIMENT/"make_overlay_integral.py"),
         str(ROOT/"basilisk/src/integral.h"), str(work/"integral.h")],
        check=True,
    )
    flags.extend([
        "-DKAPPA_OFFSET_CLAMP_FACTOR=1.0",
        f"-DKAPPA_OFFSET_PROBE_INTERVAL={args.probe_interval:.17g}",
        f"-I{EXPERIMENT/'include'}",
        f"-I{ROOT/'tools/clsvof_model/include'}",
        f"-I{ROOT/'dataset/model/c_exports'/args.model}",
    ])
    flags.append("-disable-dimensions")
    return flags


def run_case(args: argparse.Namespace, work: Path, source: Path, flags: list[str]) -> None:
    stdout = (work/"stdout.txt").open("w", encoding="utf-8")
    stderr = (work/"log").open("w", encoding="utf-8")
    try:
        if args.benchmark == "rising":
            command = [str(ROOT/"tools/basilisk-run"), *flags, source.name]
            subprocess.run(command, cwd=work, stdout=stdout, stderr=stderr, check=True)
        else:
            executable = source.with_suffix("")
            command = [str(ROOT/"tools/basilisk-cc"), *flags, source.name,
                       "-o", executable.name, "-lm"]
            subprocess.run(command, cwd=work, stdout=stderr, stderr=stderr, check=True)
            subprocess.run([str(executable)], cwd=work, stdout=stdout, stderr=stderr, check=True)
    finally:
        stdout.close()
        stderr.close()


def metadata(args: argparse.Namespace, flags: list[str], source: Path) -> dict:
    tracked = [
        ROOT/"basilisk/src/integral.h",
        ROOT/"basilisk/src/test/rising.c" if args.benchmark == "rising" else ROOT/"basilisk/src/test/capwave-clsvof.c",
        ROOT/"basilisk/src/test/prosperetti.h",
        EXPERIMENT/"make_overlay_integral.py",
        EXPERIMENT/"include/clsvof_nn_cell_curvature.h",
        ROOT/"tools/clsvof_model/include/clsvof_mlp_infer.h",
        ROOT/"dataset/model/c_exports"/args.model/"nn_weights.h",
        ROOT/"dataset/model/c_exports"/args.model/"export_manifest.json",
    ]
    return {
        "benchmark": args.benchmark, "case": args.case, "resolution": args.resolution,
        "model": args.model, "mode": args.mode, "t0_only": args.t0_only,
        "probe_interval": args.probe_interval, "compile_flags": flags,
        "source_copy": source.name,
        "sha256": {str(path.relative_to(ROOT)): sha256(path) for path in tracked if path.exists()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", choices=("rising", "capwave"), required=True)
    parser.add_argument("--case", choices=("case1", "case2"), default="case1")
    parser.add_argument("--resolution", type=int, default=128)
    parser.add_argument("--model", choices=MODEL_NAMES, default="baseline_128_hgradient")
    parser.add_argument("--mode", choices=("original", *MODES), required=True)
    parser.add_argument("--t0-only", action="store_true")
    parser.add_argument("--probe-interval", type=float, default=0.0)
    parser.add_argument("--optimization", choices=("-O2", "-O3"), default="-O2")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.benchmark == "capwave" and args.resolution not in (64, 128, 256, 512):
        parser.error("capwave resolution must be one of N64/N128/N256/N512")
    if args.mode == "original" and (args.probe_interval > 0 or args.t0_only):
        parser.error("original mode has no provider probe; use nn_cell_levelset")

    work = args.output_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    source, flags = materialize_case(args, work)
    if args.mode != "original":
        flags = add_overlay(args, work, flags)
    run_flags = [args.optimization, *flags]
    run_case(args, work, source, run_flags)
    (work/"run_manifest.json").write_text(
        json.dumps(metadata(args, run_flags, source), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(work)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
