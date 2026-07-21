#!/usr/bin/env python3
"""Golden-vector parity checks for CLSVOF NN C deployment."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import torch
import torch.nn as nn


ROOT = Path(__file__).resolve().parents[3]
MODEL_ROOT = ROOT / "dataset/model"
EXPORT_ROOT = MODEL_ROOT / "c_exports"
INFER_INCLUDE_DIR = ROOT / "generate/_shared/nn_runtime/src"
SHARED_INCLUDE_DIR = INFER_INCLUDE_DIR
FIXTURE = ROOT / "tools/clsvof_model/tests/fixtures/raw27_golden_vector.json"
FORMAL_RESOLUTIONS = (64, 128, 256, 512)


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


def load_fixture() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


def pytorch_output(checkpoint_path: Path, raw27: list[float]) -> float:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = MLP()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    transform = checkpoint["feature_transform"]
    raw = torch.as_tensor([raw27], dtype=torch.float32)
    mean = torch.as_tensor(transform["mean"], dtype=torch.float32)
    std = torch.as_tensor(transform["std"], dtype=torch.float32)
    with torch.no_grad():
        return float(model((raw - mean) / std).item())


def compile_and_run(
    source: str,
    *,
    model_dir: Path | None = None,
    include_dir: Path = SHARED_INCLUDE_DIR,
) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "golden.c"
        exe = Path(tmp) / "golden"
        src.write_text(source, encoding="utf-8")
        cmd = [
            "cc",
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(include_dir),
            "-I",
            str(INFER_INCLUDE_DIR),
        ]
        if model_dir is not None:
            cmd.extend(["-I", str(model_dir)])
        cmd.extend([str(src), "-o", str(exe), "-lm"])
        subprocess.run(cmd, check=True, cwd=ROOT)
        return subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout


def test_shared_c_raw27_array_builder_matches_training_golden_vector():
    fixture = load_fixture()
    patch_rows = [
        "{" + ", ".join(f"{float(v):.9g}" for v in row) + "}"
        for row in fixture["phi_patch_5x5"]
    ]
    patch_literal = ", ".join(patch_rows)
    expected = fixture["raw27"]
    source = f"""
#include <math.h>
#include <stdio.h>
#define CLSVOF_NN_CELL_ARRAY_ONLY 1
#include "clsvof_nn_cell_curvature.h"

int main(void)
{{
  const double patch[5][5] = {{{patch_literal}}};
  float raw[27];
  clsvof_nn_cell_build_raw27_from_patch5(patch, {float(fixture["delta"]):.17g}, raw);
  for (int i = 0; i < 27; ++i)
    printf("%.9g\\n", (double) raw[i]);
  return 0;
}}
"""
    actual = [float(x) for x in compile_and_run(source).splitlines()]

    assert len(actual) == 27
    for idx, (a, e) in enumerate(zip(actual, expected, strict=True)):
        assert abs(a - float(e)) <= 2e-7, f"raw27[{idx}] C={a} training={e}"
def test_exported_c_forward_matches_pytorch_for_golden_vector_all_checkpoints():
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    fixture = load_fixture()
    raw_literal = ", ".join(f"{float(v):.9g}f" for v in fixture["raw27"])

    for resolution in FORMAL_RESOLUTIONS:
        checkpoint_path = MODEL_ROOT / f"baseline_{resolution}_hgradient.pt"
        model_name = checkpoint_path.stem
        expected = pytorch_output(checkpoint_path, fixture["raw27"])
        source = f"""
#include <stdio.h>
#include "nn_weights.h"
#include "clsvof_mlp_infer.h"

int main(void)
{{
  const float raw[CLSVOF_NN_INPUT_DIM] = {{{raw_literal}}};
  printf("%.9g\\n", (double) clsvof_nn_predict_hkappa(raw));
  return 0;
}}
"""
        actual = float(compile_and_run(source, model_dir=EXPORT_ROOT / model_name).strip())
        assert abs(actual - expected) <= 1e-6, (
            f"{model_name}: C forward {actual} != PyTorch {expected}"
        )
