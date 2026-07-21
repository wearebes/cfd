from __future__ import annotations

import json
import math
import subprocess

from conftest import FIXTURE, SHARED


def compile_and_run(tmp_path, source: str) -> list[float]:
    c_file = tmp_path / "sign.c"
    binary = tmp_path / "sign"
    c_file.write_text(source, encoding="utf-8")
    subprocess.run(
        ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", f"-I{SHARED}",
         str(c_file), "-o", str(binary), "-lm"],
        check=True,
    )
    return [float(value) for value in subprocess.run(
        [str(binary)], check=True, text=True, capture_output=True
    ).stdout.splitlines()]


def test_solver_minus_d_builds_training_raw27(tmp_path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    solver_patch = [[-float(value) for value in row] for row in fixture["phi_patch_5x5"]]
    rows = ["{" + ",".join(f"{value:.17g}" for value in row) + "}" for row in solver_patch]
    source = f"""
#include <stdio.h>
#define CLSVOF_NN_CELL_ARRAY_ONLY 1
#include "clsvof_nn_cell_curvature.h"
int main(void) {{
  const double patch[5][5] = {{{','.join(rows)}}};
  float raw[27];
  clsvof_nn_cell_build_raw27_signed_from_patch5(patch, {fixture['delta']:.17g}, -1., raw);
  for (int i = 0; i < 27; i++) printf("%.9g\\n", (double) raw[i]);
}}
"""
    actual = compile_and_run(tmp_path, source)
    assert len(actual) == 27
    for index, (observed, expected) in enumerate(zip(actual, fixture["raw27"], strict=True)):
        assert abs(observed - expected) <= 2e-7, (index, observed, expected)


def test_default_plus_one_path_is_bitwise_equivalent(tmp_path) -> None:
    source = """
#include <stdio.h>
#define CLSVOF_NN_CELL_ARRAY_ONLY 1
#include "clsvof_nn_cell_curvature.h"
int main(void) {
  double patch[5][5];
  for (int row = 0; row < 5; row++)
    for (int col = 0; col < 5; col++) patch[row][col] = row*row + 0.3*col;
  float old_path[27], signed_path[27];
  clsvof_nn_cell_build_raw27_from_patch5(patch, 0.125, old_path);
  clsvof_nn_cell_build_raw27_signed_from_patch5(patch, 0.125, 1., signed_path);
  for (int i = 0; i < 27; i++) printf("%.1f\\n", (double)(old_path[i] - signed_path[i]));
}
"""
    assert compile_and_run(tmp_path, source) == [0.0] * 27


def test_solver_offset_matches_circle_contour() -> None:
    radius = 0.1
    delta = 0.5 / 64
    q_gamma_solver = -delta / radius
    for s in (-0.9, -0.4, 0.0, 0.4, 0.9):
        d = s * delta
        q_cell = q_gamma_solver / (1.0 + s * q_gamma_solver)
        kappa = q_cell / delta
        assert math.isclose(kappa, -1.0 / (radius - d), rel_tol=1e-14)
