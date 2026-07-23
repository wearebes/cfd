from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
CASE = ROOT / "generate/oscillating_droplet/nn"
SHARED = ROOT / "generate/_shared/nn_runtime/src"
FIXTURE = CASE / "tests/fixtures/raw27_golden_vector.json"
