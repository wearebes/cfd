from __future__ import annotations

import re

from conftest import CASE, ROOT


def test_single_level_host_preserves_frozen_physics() -> None:
    source = (CASE / "src/oscillation-nn-single-level.c").read_text(encoding="utf-8")
    for pattern in (
        r"#define D 0\.2",
        r"rho1 = 1, rho2 = 1e-3;",
        r"d\.sigmaf = sigma;",
        r"L0 = 0\.5 \[0\];",
        r"TOLERANCE = 1e-4 \[\*\];",
        r"0\.05\*cos\(2\.\*atan2\(y,x\)\)",
        r"t <= T_END",
        r"KINETIC_ENERGY_FAILURE_LIMIT 1e-2",
        r"OSCILLATION_NUMERICAL_FAILURE",
        r"adapt_wavelet \(\{f,u\}, \{5e-3,1e-3,1e-3\}, LEVEL\);",
    ):
        assert re.search(pattern, source), pattern


def test_active_curvature_site_is_unique_and_curvature_mode_is_one() -> None:
    integral = (ROOT / "basilisk/src/integral.h").read_text(encoding="utf-8")
    assert integral.count("double ki = distance_curvature (point, d);") == 1
    assert re.search(r"#define CURVATURE 1\b", integral)


def test_case_sign_is_explicitly_minus_one() -> None:
    adapter = (CASE / "src/oscillation_raw27_adapter.h").read_text(encoding="utf-8")
    assert "#define KAPPA_OFFSET_MODEL_PHI_SIGN (-1.0)" in adapter
