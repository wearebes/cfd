from __future__ import annotations

import json
import subprocess

import pytest

from conftest import FIXTURE, ROOT


@pytest.mark.parametrize("resolution", [64, 128])
def test_c_forward_matches_recorded_pytorch_golden(tmp_path, resolution: int) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = fixture["models"][f"baseline_{resolution}_hgradient"]["pytorch_hkappa"]
    raw = ",".join(f"{float(value):.9g}f" for value in fixture["raw27"])
    source = f"""
#include <stdio.h>
#include "nn_weights.h"
#include "clsvof_mlp_infer.h"
int main(void) {{
  const float raw[CLSVOF_NN_INPUT_DIM] = {{{raw}}};
  printf("%.9g\\n", (double) clsvof_nn_predict_hkappa(raw));
}}
"""
    c_file = tmp_path / "forward.c"
    binary = tmp_path / "forward"
    c_file.write_text(source, encoding="utf-8")
    model = ROOT / f"dataset/model/c_exports/baseline_{resolution}_hgradient"
    infer = ROOT / "generate/_shared/nn_runtime/src"
    subprocess.run(
        ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", f"-I{model}", f"-I{infer}",
         str(c_file), "-o", str(binary)],
        check=True,
    )
    observed = float(subprocess.run(
        [str(binary)], check=True, text=True, capture_output=True
    ).stdout.strip())
    assert abs(observed - expected) <= 1e-6
