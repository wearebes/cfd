#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
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


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_MATRIX = HERE / "config/matrix.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run_checked(command: list[str], cwd: Path, stdout: Path, stderr: Path) -> None:
    with stdout.open("w", encoding="utf-8") as out, stderr.open(
        "w", encoding="utf-8"
    ) as err:
        completed = subprocess.run(command, cwd=cwd, stdout=out, stderr=err)
    if completed.returncode:
        raise RuntimeError(
            f"command failed with exit {completed.returncode}: {' '.join(command)}"
        )


def load_row(matrix_path: Path, row_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matches = [row for row in matrix["rows"] if row["row_id"] == row_id]
    if len(matches) != 1:
        raise ValueError(f"expected one matrix row for {row_id}, got {len(matches)}")
    return matrix, matches[0]


def log_stride(row: dict[str, Any]) -> int:
    n = int(row["N"])
    if row["benchmark"] == "capwave":
        return {64: 10, 128: 20, 256: 50, 512: 100}[n]
    return {64: 5, 128: 10, 256: 20, 512: 40}[n]


def result_dir(base: Path, row: dict[str, Any]) -> Path:
    return (
        base
        / str(row["benchmark"])
        / f"N{int(row['N']):04d}"
        / f"imax{int(row['imax']):02d}"
        / str(row["method"])
    )


def provenance_inputs(row: dict[str, Any]) -> dict[str, Path]:
    inputs = {
        "stock_two_phase_clsvof": ROOT / "basilisk/src/two-phase-clsvof.h",
        "stock_redistance": ROOT / "basilisk/src/redistance.h",
        "stock_integral": ROOT / "basilisk/src/integral.h",
    }
    if row["benchmark"] == "capwave":
        inputs["source_prosperetti"] = ROOT / "basilisk/src/test/prosperetti.h"
    if row["method"] == "clsvof_nn":
        include = ROOT / "experiments/clsvof_kappa_offset_conversion/include"
        inputs.update(
            {
                "nn_cell_curvature": include / "clsvof_nn_cell_curvature.h",
                "offset_overlay_generator": ROOT
                / "experiments/clsvof_kappa_offset_conversion/make_overlay_integral.py",
                "mlp_inference": ROOT
                / "tools/clsvof_model/include/clsvof_mlp_infer.h",
            }
        )
        inputs["weights"] = (
            ROOT
            / f"dataset/model/c_exports/baseline_{row['N']}_hgradient/nn_weights.h"
        )
    return inputs


def prepare_row(row: dict[str, Any], work: Path) -> dict[str, Path]:
    work.mkdir(parents=True, exist_ok=False)
    metrics_header = HERE / "include/redistance_matrix_metrics.h"
    shutil.copy2(metrics_header, work / metrics_header.name)

    if row["benchmark"] == "capwave":
        source_case = ROOT / "basilisk/src/test/capwave-clsvof.c"
        case_name = "capwave-clsvof.c"
        run_checked(
            [
                "/opt/anaconda3/envs/pinn/bin/python",
                str(ROOT / "experiments/capwave_clsvof_kreplace/make_single_resolution_case.py"),
                str(source_case),
                case_name,
                "--resolution",
                str(row["N"]),
            ],
            work,
            work / "prepare_case.stdout",
            work / "prepare_case.stderr",
        )
        shutil.copy2(ROOT / "basilisk/src/test/prosperetti.h", work / "prosperetti.h")
    else:
        source_case = ROOT / "basilisk/src/test/rising.c"
        case_name = "rising-clsvof.c"
        shutil.copy2(source_case, work / case_name)

    run_checked(
        [
            "/opt/anaconda3/envs/pinn/bin/python",
            str(HERE / "make_redistance_overlay.py"),
            str(ROOT / "basilisk/src/two-phase-clsvof.h"),
            "two-phase-clsvof.h",
            "--imax",
            str(row["imax"]),
            "--provenance",
            "redistance_overlay.json",
        ],
        work,
        work / "prepare_redistance.stdout",
        work / "prepare_redistance.stderr",
    )
    if row["method"] == "clsvof_nn":
        run_checked(
            [
                "/opt/anaconda3/envs/pinn/bin/python",
                str(ROOT / "experiments/clsvof_kappa_offset_conversion/make_overlay_integral.py"),
                str(ROOT / "basilisk/src/integral.h"),
                "integral.h",
            ],
            work,
            work / "prepare_integral.stdout",
            work / "prepare_integral.stderr",
        )
    else:
        shutil.copy2(ROOT / "basilisk/src/integral.h", work / "integral.h")
    files = {
        "source_case": source_case,
        "case": work / case_name,
        "metrics_header": work / metrics_header.name,
        "redistance_header": work / "two-phase-clsvof.h",
        "redistance_provenance": work / "redistance_overlay.json",
        "integral": work / "integral.h",
    }
    files.update(provenance_inputs(row))
    return files


def compile_command(row: dict[str, Any], case_name: str, binary_name: str) -> list[str]:
    command = [str(ROOT / "tools/basilisk-cc")]
    stride = log_stride(row)
    final_time = 2.2426211256 if row["benchmark"] == "capwave" else 3.0
    command.extend(
        [
            f"-DREDIST_MATRIX_LOG_STRIDE={stride}",
            f"-DREDIST_MATRIX_FINAL_TIME={final_time}",
        ]
    )
    model_include = ROOT / f"dataset/model/c_exports/baseline_{row['N']}_hgradient"
    if row["benchmark"] == "capwave":
        command.append("-DCLSVOF=1")
    else:
        command.extend(
            ["-DLEVELSET=1", "-DCLSVOF=1", f"-DLEVEL={row['LEVEL']}"]
        )
    if row["method"] == "clsvof_nn":
        command.extend(
            [
                "-disable-dimensions",
                "-DKAPPA_OFFSET_CLAMP_FACTOR=1.0",
                f"-I{ROOT / 'experiments/clsvof_kappa_offset_conversion/include'}",
                f"-I{ROOT / 'tools/clsvof_model/include'}",
                f"-I{model_include}",
            ]
        )
    command.extend([case_name, "-o", binary_name, "-lm"])
    return command


def finite_float(value: str) -> bool:
    try:
        number = float(value)
    except ValueError:
        return False
    return number == number and abs(number) != float("inf")


def validate_capwave(work: Path, row: dict[str, Any]) -> dict[str, Any]:
    wave = work / f"wave-{row['N']}"
    if not wave.is_file():
        raise RuntimeError(f"missing {wave.name}")
    wave_rows = [line.split() for line in wave.read_text().splitlines() if line.strip()]
    if len(wave_rows) != 738:
        raise RuntimeError(f"expected 738 wave rows, got {len(wave_rows)}")
    if not all(len(values) == 2 and all(map(finite_float, values)) for values in wave_rows):
        raise RuntimeError("wave output contains non-finite or malformed values")

    log_lines = [line for line in (work / "log").read_text().splitlines() if line.strip()]
    rms_rows = [line.split() for line in log_lines if len(line.split()) == 2 and all(map(finite_float, line.split()))]
    if not rms_rows:
        raise RuntimeError("missing capwave RMS row")
    return {"wave_rows": len(wave_rows), "relative_rms": float(rms_rows[-1][1])}


def validate_rising(work: Path, row: dict[str, Any]) -> dict[str, Any]:
    out = work / "out"
    log = work / "log"
    if not out.is_file() or not log.is_file() or log.stat().st_size == 0:
        raise RuntimeError("missing rising out/log")
    data_rows = []
    for line in out.read_text().splitlines():
        values = line.split()
        if len(values) >= 5 and all(finite_float(value) for value in values[:5]):
            data_rows.append(values)
    if not data_rows or abs(float(data_rows[-1][0]) - 3.0) > 1e-9:
        raise RuntimeError("rising output did not reach t=3")
    return {
        "out_rows": len(data_rows),
        "final_time": float(data_rows[-1][0]),
        "final_volume_drift": float(data_rows[-1][1]),
        "final_center": float(data_rows[-1][3]),
        "final_velocity": float(data_rows[-1][4]),
    }


def numeric_prefix_rows(path: Path, columns: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        values = line.split()
        if len(values) < columns:
            continue
        try:
            prefix = [float(value) for value in values[:columns]]
        except ValueError:
            continue
        if all(value == value and abs(value) != float("inf") for value in prefix):
            rows.append(prefix)
    return rows


def compare_candidate_reuse(work: Path, row: dict[str, Any]) -> dict[str, Any] | None:
    if row["planning_status"] != "candidate_reuse":
        return None
    original = ROOT / str(row["existing_evidence"])
    if not original.is_file() or original.stat().st_size == 0:
        raise RuntimeError(f"candidate reuse evidence missing or empty: {original}")
    generated = (
        work / f"wave-{row['N']}" if row["benchmark"] == "capwave" else work / "out"
    )
    if row["benchmark"] == "capwave":
        exact = generated.read_bytes() == original.read_bytes()
        if not exact:
            raise RuntimeError("candidate capwave replay is not byte-identical to original")
        return {
            "original_path": str(original),
            "original_sha256": sha256_file(original),
            "generated_sha256": sha256_file(generated),
            "comparison": "byte_identical",
            "matched_rows": 738,
        }

    original_rows = numeric_prefix_rows(original, 5)
    generated_rows = numeric_prefix_rows(generated, 5)
    if len(original_rows) != len(generated_rows) or not original_rows:
        raise RuntimeError(
            "candidate rising replay row-count mismatch: "
            f"original={len(original_rows)} generated={len(generated_rows)}"
        )
    max_abs = max(
        abs(left - right)
        for original_row, generated_row in zip(original_rows, generated_rows)
        for left, right in zip(original_row, generated_row)
    )
    if max_abs > 1e-12:
        raise RuntimeError(f"candidate rising replay physical mismatch: max_abs={max_abs}")
    return {
        "original_path": str(original),
        "original_sha256": sha256_file(original),
        "generated_sha256": sha256_file(generated),
        "comparison": "first_five_physical_columns_abs_tol_1e-12",
        "matched_rows": len(original_rows),
        "max_abs_difference": max_abs,
    }


def copy_evidence(work: Path, destination: Path, row: dict[str, Any]) -> None:
    names = [
        "compile.stdout",
        "compile.stderr",
        "redistance_metrics.csv",
        "redistance_return_trace.csv",
        "redistance_overlay.json",
        "two-phase-clsvof.h",
        "redistance_matrix_metrics.h",
        "integral.h",
    ]
    if row["benchmark"] == "capwave":
        names.extend(["stdout.txt", "log", f"wave-{row['N']}", "capwave-clsvof.c"])
    else:
        names.extend(["out", "log", "rising-clsvof.c"])
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        source = work / name
        if source.exists():
            shutil.copy2(source, destination / name)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("row_id")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    matrix, row = load_row(args.matrix, args.row_id)
    results_base = HERE / "results" / args.matrix_id
    destination = result_dir(results_base, row)
    status_path = destination / "status.json"
    if status_path.exists() and not args.force:
        previous = json.loads(status_path.read_text(encoding="utf-8"))
        if previous.get("state") == "completed":
            print(f"skip completed row: {args.row_id}")
            return 0
        raise RuntimeError(f"row already has non-completed status: {status_path}")

    attempt = f"attempt_{int(time.time())}"
    work = HERE / "work" / args.matrix_id / args.row_id / attempt
    destination.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    status: dict[str, Any] = {
        "row_id": args.row_id,
        "state": "running",
        "started_at": started,
        "work_dir": str(work),
        "pid": os.getpid(),
    }
    atomic_json(status_path, status)

    files: dict[str, Path] = {}
    command: list[str] = []
    compile_seconds: float | None = None
    run_seconds: float | None = None
    try:
        files = prepare_row(row, work)
        case_name = files["case"].name
        binary_name = Path(case_name).stem
        command = compile_command(row, case_name, binary_name)
        compile_started = time.monotonic()
        run_checked(command, work, work / "compile.stdout", work / "compile.stderr")
        compile_seconds = time.monotonic() - compile_started

        run_stdout = work / ("stdout.txt" if row["benchmark"] == "capwave" else "out")
        run_stderr = work / "log"
        run_started = time.monotonic()
        with run_stdout.open("w", encoding="utf-8") as out, run_stderr.open(
            "w", encoding="utf-8"
        ) as err:
            process = subprocess.run([f"./{binary_name}"], cwd=work, stdout=out, stderr=err)
        run_seconds = time.monotonic() - run_started
        if process.returncode:
            raise RuntimeError(f"solver exited with {process.returncode}")

        for required in ("redistance_metrics.csv", "redistance_return_trace.csv"):
            if not (work / required).is_file():
                raise RuntimeError(f"missing diagnostic output {required}")
        physical = (
            validate_capwave(work, row)
            if row["benchmark"] == "capwave"
            else validate_rising(work, row)
        )
        reuse_validation = compare_candidate_reuse(work, row)
        copy_evidence(work, destination, row)

        hashed_files = {
            key: {"path": str(path), "sha256": sha256_file(path)}
            for key, path in files.items()
            if path.is_file()
        }
        manifest = {
            "schema_version": 1,
            "matrix_name": matrix["matrix_name"],
            "matrix_id": args.matrix_id,
            "row": row,
            "command": command,
            "started_at": started,
            "finished_at": utc_now(),
            "compile_seconds": compile_seconds,
            "run_seconds": run_seconds,
            "physical_validation": physical,
            "reuse_validation": reuse_validation,
            "files": hashed_files,
            "platform": {"machine": platform.machine(), "system": platform.system()},
        }
        atomic_json(destination / "manifest.json", manifest)
        status.update(
            {
                "state": "completed",
                "finished_at": manifest["finished_at"],
                "compile_seconds": compile_seconds,
                "run_seconds": run_seconds,
            }
        )
        atomic_json(status_path, status)
        print(json.dumps(status, sort_keys=True))
        return 0
    except Exception as error:
        if work.exists():
            copy_evidence(work, destination, row)
        binary = work / ("capwave-clsvof" if row["benchmark"] == "capwave" else "rising-clsvof")
        message = str(error).lower()
        if not binary.exists():
            state = "failed_compile"
        elif "non-finite" in message or "nonfinite" in message:
            state = "failed_nonfinite"
        elif "missing" in message or "expected 738" in message:
            state = "failed_missing_output"
        else:
            state = "failed_runtime"
        hashed_files = {
            key: {"path": str(path), "sha256": sha256_file(path)}
            for key, path in files.items()
            if path.is_file()
        }
        failure_manifest = {
            "schema_version": 1,
            "matrix_name": matrix["matrix_name"],
            "matrix_id": args.matrix_id,
            "row": row,
            "command": command,
            "started_at": started,
            "finished_at": utc_now(),
            "compile_seconds": compile_seconds,
            "run_seconds": run_seconds,
            "failure_state": state,
            "error": str(error),
            "files": hashed_files,
            "platform": {"machine": platform.machine(), "system": platform.system()},
        }
        atomic_json(destination / "manifest.json", failure_manifest)
        status.update(
            {
                "state": state,
                "finished_at": failure_manifest["finished_at"],
                "error": str(error),
                "compile_seconds": compile_seconds,
                "run_seconds": run_seconds,
            }
        )
        atomic_json(status_path, status)
        print(json.dumps(status, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
