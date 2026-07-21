from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_provenance_lock_matches_active_generate_sources() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "hpc/update_provenance_lock.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
