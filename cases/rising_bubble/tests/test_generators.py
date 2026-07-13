from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
NN = ROOT / "cases/rising_bubble/generate/nn_cell_offset.sh"
NATIVE = ROOT / "cases/rising_bubble/generate/native.sh"


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
    assert "/case1/" in case1.stdout
    assert "/case2/" in case2.stdout
    assert "benchmark=rising_case1" in case1.stdout
    assert "benchmark=rising_case2" in case2.stdout
    assert "case2_flag=\n" in case1.stdout
    assert "case2_flag=-DCASE2=1" in case2.stdout
    assert case1.stdout.splitlines()[0] != case2.stdout.splitlines()[0]


@pytest.mark.parametrize("script", [NN, NATIVE])
@pytest.mark.parametrize("imax", [0, 5])
def test_imax_boundaries_are_accepted(script: Path, imax: int) -> None:
    assert dry_run(script, 1, imax=imax).returncode == 0


@pytest.mark.parametrize("script", [NN, NATIVE])
@pytest.mark.parametrize("imax", [-1, 6, 10])
def test_imax_outside_formal_contract_is_rejected(script: Path, imax: int) -> None:
    completed = dry_run(script, 1, imax=imax)
    assert completed.returncode == 2
    assert "0 through 5" in completed.stderr


@pytest.mark.parametrize("script", [NN, NATIVE])
@pytest.mark.parametrize("case", [0, 3])
def test_invalid_hysing_case_is_rejected(script: Path, case: int) -> None:
    completed = dry_run(script, case)
    assert completed.returncode == 2
    assert "--case must be 1 or 2" in completed.stderr
