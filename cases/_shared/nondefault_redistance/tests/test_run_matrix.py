from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
COMPAT = ROOT / "cases/_shared/nondefault_redistance/run_matrix.py"


def test_compatibility_entrypoint_routes_to_180_row_hpc_runner() -> None:
    completed = subprocess.run(
        [
            "python3",
            str(COMPAT),
            "--matrix-id",
            "compat_dry",
            "--cpus",
            "2",
            "--phase",
            "all",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "authoritative hpc 180-row runner" in completed.stderr
    lines = completed.stdout.splitlines()
    assert len(lines) == 181
    assert '"row_count": 180' in lines[-1]
