from __future__ import annotations

import math
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_formula_roundtrip_and_sign_under_circle_and_ellipse_values() -> None:
    values = (4.0, 1.3, 8.1)
    maximum = 0.0
    for h in (1 / 64, 1 / 128, 1 / 256):
        for kappa in values:
            for sign in (-1.0, 1.0):
                q_gamma = sign * h * kappa
                for s in (-1.0, -.75, -.5, -.25, 0.0, .25, .5, .75, 1.0):
                    q_d = q_gamma / (1.0 + s * q_gamma)
                    recovered = q_d / (1.0 - s * q_d)
                    maximum = max(maximum, abs(recovered - q_gamma))
                    assert math.copysign(1.0, q_d) == math.copysign(1.0, q_gamma)
    assert maximum < 1e-12


def test_c_and_python_conversion_match(tmp_path: Path) -> None:
    executable = tmp_path / "offset_cli"
    subprocess.run(
        ["cc", "-std=c99", "-O2", "-I", str(ROOT / "include"),
         str(Path(__file__).with_name("offset_c_cli.c")), "-o",
         str(executable), "-lm"],
        check=True,
    )
    vectors = [(q, s) for q in (-.15, -.03, .03, .15)
               for s in (-1., -.5, 0., .5, 1.)]
    result = subprocess.run(
        [str(executable)],
        input="".join(f"{q} {s}\n" for q, s in vectors),
        text=True, capture_output=True, check=True,
    )
    for (q, s), line in zip(vectors, result.stdout.splitlines(), strict=True):
        q_cell, q_inverse, *_ = map(float, line.split())
        assert abs(q_cell - q / (1. + s*q)) < 1e-12
        assert abs(q_inverse - q) < 1e-12
