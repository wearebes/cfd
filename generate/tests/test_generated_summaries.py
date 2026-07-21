from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_case_summaries_match_runner_dry_runs() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "generate/_shared/render_summaries.py"),
            "--check",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
