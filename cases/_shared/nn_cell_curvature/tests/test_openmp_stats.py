from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
INCLUDE = HERE.parent / "src"
HARNESS = HERE / "openmp_stats_smoke.c"
PROVIDER = INCLUDE / "clsvof_nn_cell_curvature.h"


def compile_harness(tmp_path: Path, openmp: bool) -> Path:
    compiler = os.environ.get("CC", "cc")
    output = tmp_path / ("stats_openmp" if openmp else "stats_serial")
    command = [compiler, "-std=c11", "-O2", f"-I{INCLUDE}"]
    if openmp:
        command.append("-fopenmp")
    command.extend([str(HARNESS), "-o", str(output), "-lm"])
    completed = subprocess.run(command, text=True, capture_output=True)
    if openmp and completed.returncode != 0:
        pytest.skip(f"compiler has no usable OpenMP runtime: {completed.stderr}")
    assert completed.returncode == 0, completed.stderr
    return output


def parse(line: str) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in (field.split("=", 1) for field in line.split())
    }


def run(binary: Path, threads: int) -> dict[str, float]:
    environment = os.environ.copy()
    environment["OMP_NUM_THREADS"] = str(threads)
    environment["OMP_DYNAMIC"] = "FALSE"
    completed = subprocess.run(
        [str(binary), "100003"],
        text=True,
        capture_output=True,
        env=environment,
        check=True,
    )
    return parse(completed.stdout)


def test_serial_statistics_contract(tmp_path: Path) -> None:
    values = run(compile_harness(tmp_path, openmp=False), 1)
    assert values["evaluations"] == values["grad_n"] == 100003
    assert values["clamp_hits"] > 0
    assert values["guard_hits"] > 0
    assert values["grad_min"] <= values["grad_max"]


def test_probe_openmp_critical_has_required_structured_block() -> None:
    source = PROVIDER.read_text(encoding="utf-8")
    assert re.search(
        r"# pragma omp critical\(kappa_offset_probe_output\)\s*"
        r"#endif\s*\{\s*fprintf",
        source,
    ), "OpenMP critical must be followed by a structured block"


@pytest.mark.parametrize("threads", [2, 4, 8])
def test_openmp_statistics_match_serial(tmp_path: Path, threads: int) -> None:
    serial = run(compile_harness(tmp_path, openmp=False), 1)
    parallel = run(compile_harness(tmp_path, openmp=True), threads)
    for field in (
        "evaluations",
        "clamp_hits",
        "guard_hits",
        "min_abs_denom",
        "max_abs_s",
        "grad_n",
        "grad_min",
        "grad_max",
    ):
        assert parallel[field] == serial[field]
    for field in ("grad_sum", "grad_sum_sq"):
        assert math.isclose(parallel[field], serial[field], rel_tol=1e-12)
