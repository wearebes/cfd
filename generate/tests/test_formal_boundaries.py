from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    ROOT / "generate/capwave/clsvof.sh",
    ROOT / "generate/capwave/nn.sh",
]
STATIONARY = [
    ROOT / "generate/stationary_bubble/clsvof.sh",
    ROOT / "generate/stationary_bubble/nn.sh",
]


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash", str(script), *args, "--formal", "--dry-run", "--output",
            str(ROOT / f"tem/dry_run_contract/tests/{script.parent.name}_{script.stem}"),
        ],
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
@pytest.mark.parametrize("resolution", [64, 128, 256])
def test_stationary_accepts_only_retained_resolutions(script: Path, resolution: int) -> None:
    assert run(script, "--imax", "3", "--resolution", str(resolution)).returncode == 0


@pytest.mark.parametrize("script", STATIONARY)
def test_stationary_rejects_n512(script: Path) -> None:
    completed = run(script, "--imax", "3", "--resolution", "512")
    assert completed.returncode == 2
    assert "stationary N512 is outside the formal matrix" in completed.stderr
