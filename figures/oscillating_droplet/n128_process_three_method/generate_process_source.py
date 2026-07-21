#!/usr/bin/env python3
"""Run matched short simulations and publish phase-resolved contour source data."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PHASES = (
    (0, "0", 0.0),
    (1, "T/4", 0.02028903029296296),
    (2, "T/2", 0.04057806058592593),
    (3, "3T/4", 0.06086709087888889),
    (4, "T", 0.08115612117185185),
)
METHODS = ("clsvof", "nn", "vof_hf")


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "generate").is_dir() and (parent / "dataset").is_dir():
            return parent
    raise RuntimeError("Could not locate repository root")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        command, cwd=cwd, env=env, text=True, capture_output=True
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def parse_facets(path: Path) -> list[tuple[float, float, float, float]]:
    chunks = [chunk for chunk in path.read_text(encoding="utf-8").split("\n\n") if chunk.strip()]
    segments: list[tuple[float, float, float, float]] = []
    for chunk in chunks:
        points = [line.split() for line in chunk.splitlines() if line.strip()]
        if len(points) != 2 or any(len(point) != 2 for point in points):
            raise ValueError(f"unexpected facet block in {path}: {chunk!r}")
        (x1, y1), (x2, y2) = ([float(value) for value in point] for point in points)
        segments.append((x1, y1, x2, y2))
    if not segments:
        raise ValueError(f"no facets in {path}")
    return segments


def read_times(path: Path) -> dict[int, float]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = {int(row["snapshot_index"]): float(row["time"]) for row in rows}
    if set(times) != set(range(5)):
        raise ValueError(f"incomplete snapshot times in {path}: {times}")
    return times


def append_full_domain_rows(
    rows: list[dict[str, object]], method: str, directory: Path
) -> None:
    actual_times = read_times(directory / "snapshot_times.csv")
    for phase_index, phase_label, target_time in PHASES:
        segments = parse_facets(directory / f"interface-{phase_index:02d}.dat")
        segment_index = 0
        for x1, y1, x2, y2 in segments:
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                rows.append({
                    "method": method,
                    "phase_index": phase_index,
                    "phase_label": phase_label,
                    "target_time": target_time,
                    "actual_time": actual_times[phase_index],
                    "segment_id": segment_index,
                    "x1": sx * x1,
                    "y1": sy * y1,
                    "x2": sx * x2,
                    "y2": sy * y2,
                })
                segment_index += 1


def main() -> int:
    root = repository_root()
    output = Path(__file__).resolve().parent
    basilisk = root / "basilisk/src"
    run_row = root / "generate/oscillating_droplet/nn/generate/run_row.py"
    vof_source = root / "generate/oscillating_droplet/process_snapshots/oscillation-vof-hf-snapshots.c"
    clsvof_source = root / "generate/oscillating_droplet/nn/src/oscillation-nn-single-level.c"
    environment = os.environ.copy()
    environment["BASILISK"] = str(basilisk)
    commands: dict[str, list[str]] = {}

    with tempfile.TemporaryDirectory(prefix="oscillating-process-") as temporary:
        work = Path(temporary)
        method_dirs: dict[str, Path] = {}
        for method, runner_method in (("clsvof", "clsvof"), ("nn", "nn")):
            destination = work / method
            command = [
                sys.executable, str(run_row), "--method", runner_method,
                "--resolution", "128", "--imax", "3", "--smoke",
                "--threads", "1", "--output", str(destination),
                "--t-end", f"{PHASES[-1][2]:.17g}", "--no-fit", "--snapshots",
            ]
            commands[method] = command
            run_checked(command, root, environment)
            method_dirs[method] = destination

        vof_work = work / "vof_hf"
        vof_work.mkdir()
        shutil.copy2(vof_source, vof_work / "source.c")
        compile_command = [
            str(basilisk / "qcc"), "-O2", "-DMTRACE=3", "-Wall",
            "-Wno-unused-function", "-pipe", "-DLEVEL=7", "source.c",
            "-o", "oscillation-vof-hf", "-lm",
        ]
        run_command = ["./oscillation-vof-hf"]
        commands["vof_hf"] = compile_command + ["&&"] + run_command
        run_checked(compile_command, vof_work, environment)
        run_checked(run_command, vof_work, environment)
        method_dirs["vof_hf"] = vof_work

        rows: list[dict[str, object]] = []
        for method in METHODS:
            append_full_domain_rows(rows, method, method_dirs[method])

        source_path = output / "process_contours.csv"
        with source_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

        provenance = {
            "schema_version": 1,
            "case": "oscillating_droplet",
            "N": 128,
            "clsvof_nn_imax": 3,
            "phases": [
                {"index": index, "label": label, "target_time": time}
                for index, label, time in PHASES
            ],
            "methods": list(METHODS),
            "source_sha256": {
                "clsvof_host": sha256(clsvof_source),
                "vof_hf_host": sha256(vof_source),
                "process_contours": sha256(source_path),
            },
            "commands": commands,
            "note": "Matched output-instrumented short reruns; quantitative metrics use the archived full t=1 traces.",
        }
        (output / "process_provenance.json").write_text(
            json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
