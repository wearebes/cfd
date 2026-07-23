from __future__ import annotations

import subprocess
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
NN = ROOT / "generate/rising_bubble/NN.sh"
NATIVE = ROOT / "generate/rising_bubble/CLSVOF.sh"


def dry_run(script: Path, case: int, imax: int = 3, resolution: int = 64):
    return subprocess.run(
        [
            "bash",
            str(script),
            "--case",
            str(case),
            "--formal",
            "--imax",
            str(imax),
            "--resolution",
            str(resolution),
            "--output",
            str(ROOT / f"tem/dry_run_contract/tests/rising_case{case}_{script.stem}"),
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


@pytest.mark.parametrize("script", [NN, NATIVE])
def test_case1_and_case2_have_distinct_paths_and_flags(script: Path) -> None:
    case1 = dry_run(script, 1)
    case2 = dry_run(script, 2)
    assert case1.returncode == case2.returncode == 0
    plan1 = json.loads(case1.stdout)["plan"]
    plan2 = json.loads(case2.stdout)["plan"]
    assert plan1["benchmark"] == "rising_case1"
    assert plan2["benchmark"] == "rising_case2"
    assert "-DCASE2=1" not in plan1["commands"]["compile"]["argv"]
    assert "-DCASE2=1" in plan2["commands"]["compile"]["argv"]
    assert plan1["plan_sha256"] != plan2["plan_sha256"]


@pytest.mark.parametrize("script", [NN, NATIVE])
@pytest.mark.parametrize("imax", [0, 5, 10, 15, 20])
def test_imax_boundaries_are_accepted(script: Path, imax: int) -> None:
    assert dry_run(script, 1, imax=imax).returncode == 0


@pytest.mark.parametrize("script", [NN, NATIVE])
@pytest.mark.parametrize("imax", [-1, 6, 9, 11, 21])
def test_imax_outside_formal_contract_is_rejected(script: Path, imax: int) -> None:
    completed = dry_run(script, 1, imax=imax)
    assert completed.returncode == 2
    assert "must be one of" in completed.stderr


@pytest.mark.parametrize("script", [NN, NATIVE])
@pytest.mark.parametrize("case", [0, 3])
def test_invalid_hysing_case_is_rejected(script: Path, case: int) -> None:
    completed = dry_run(script, case)
    assert completed.returncode == 2
    assert "--case must be 1 or 2" in completed.stderr
