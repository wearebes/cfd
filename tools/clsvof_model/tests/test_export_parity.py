#!/usr/bin/env python3
"""Smoke parity check for the exported C model data."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import torch
import torch.nn as nn


ROOT = Path(__file__).resolve().parents[3]
MODEL_ROOT = ROOT / "dataset/model"
EXPORT_ROOT = MODEL_ROOT / "c_exports"
INCLUDE_DIR = ROOT / "tools/clsvof_model/include"
SMOKE_C = ROOT / "tools/clsvof_model/tests/smoke_infer.c"


class MLP(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(27, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def pytorch_zero_input_output(checkpoint_path: Path) -> float:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = MLP()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    transform = checkpoint["feature_transform"]
    raw = torch.zeros(1, 27, dtype=torch.float32)
    mean = torch.as_tensor(transform["mean"], dtype=torch.float32)
    std = torch.as_tensor(transform["std"], dtype=torch.float32)
    with torch.no_grad():
        return float(model((raw - mean) / std).item())


def c_zero_input_output(model_dir: Path) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "clsvof_smoke_infer"
        subprocess.run(
            [
                "cc",
                "-std=c99",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(model_dir),
                "-I",
                str(INCLUDE_DIR),
                str(SMOKE_C),
                "-o",
                str(exe),
            ],
            check=True,
            cwd=ROOT,
        )
        result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
        return float(result.stdout.strip())


def main() -> int:
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    max_diff = 0.0
    for checkpoint_path in sorted(MODEL_ROOT.glob("baseline_*_hgradient.pt")):
        name = checkpoint_path.stem
        expected = pytorch_zero_input_output(checkpoint_path)
        actual = c_zero_input_output(EXPORT_ROOT / name)
        diff = abs(expected - actual)
        max_diff = max(max_diff, diff)
        print(f"{name}: pytorch={expected:.9g} c={actual:.9g} abs_diff={diff:.3e}")
        if diff > 1e-6:
            raise SystemExit(f"C export parity check failed for {name}")
    print(f"max_abs_diff={max_diff:.3e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
