from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    ROOT / "cases/capwave/generate/native.sh",
    ROOT / "cases/capwave/generate/nn_cell_offset.sh",
]
STATIONARY = [
    ROOT / "cases/stationary_bubble/generate/native.sh",
    ROOT / "cases/stationary_bubble/generate/nn_cell_offset.sh",
]


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args, "--formal", "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("imax", [0, 5])
def test_capwave_accepts_imax_boundaries(script: Path, imax: int) -> None:
    assert run(script, "--imax", str(imax), "--resolution", "64").returncode == 0


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("imax", [-1, 6, 10])
def test_capwave_rejects_outside_imax_contract(script: Path, imax: int) -> None:
    completed = run(script, "--imax", str(imax), "--resolution", "64")
    assert completed.returncode == 2
    assert "0 through 5" in completed.stderr


@pytest.mark.parametrize("script", STATIONARY)
@pytest.mark.parametrize("level", [6, 7, 8])
def test_stationary_accepts_only_retained_levels(script: Path, level: int) -> None:
    assert run(script, "--imax", "3", "--level", str(level)).returncode == 0


@pytest.mark.parametrize("script", STATIONARY)
def test_stationary_rejects_n512(script: Path) -> None:
    completed = run(script, "--imax", "3", "--level", "9")
    assert completed.returncode == 2
    assert "stationary N512 is outside the formal matrix" in completed.stderr
