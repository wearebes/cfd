from __future__ import annotations

import importlib.util
import re

from conftest import CASE, ROOT


MODULE_PATH = CASE / "generate/make_official_method_host.py"
SPEC = importlib.util.spec_from_file_location("official_method_host", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_single_level_host_preserves_frozen_physics() -> None:
    official = (ROOT / "basilisk/src/test/oscillation.c").read_text(encoding="utf-8")
    source = MODULE.build(official)
    for pattern in (
        r"#define D 0\.2",
        r"rho1 = 1, rho2 = 1e-3;",
        r"d\.sigmaf = sigma;",
        r"L0 = 0\.5 \[0\];",
        r"TOLERANCE = 1e-4 \[\*\];",
        r"0\.05\*cos\(2\.\*atan2\(y,x\)\)",
        r"t <= 1",
        r"fit k\(x\) 'k-%d' via a,b,c",
        r"event generated_termination_record \(t = end, last\)",
        r"adapt_wavelet \(\{f,u\}, \{5e-3,1e-3,1e-3\}, LEVEL\);",
    ):
        assert re.search(pattern, source), pattern

    for forbidden in (
        "KINETIC_ENERGY_FAILURE_LIMIT",
        "OSCILLATION_NUMERICAL_FAILURE",
        "ENABLE_SNAPSHOTS",
        "interface_snapshots",
        "ENABLE_FIT",
        "T_END",
    ):
        assert forbidden not in source


def test_official_fit_event_is_unchanged() -> None:
    official = (ROOT / "basilisk/src/test/oscillation.c").read_text(encoding="utf-8")
    source = MODULE.build(official)
    official_fit = official[official.index("event fit (t = end)"):official.index("#if TREE")]
    assert official_fit in source


def test_active_curvature_site_is_unique_and_curvature_mode_is_one() -> None:
    integral = (ROOT / "basilisk/src/integral.h").read_text(encoding="utf-8")
    assert integral.count("double ki = distance_curvature (point, d);") == 1
    assert re.search(r"#define CURVATURE 1\b", integral)


def test_case_sign_is_explicitly_minus_one() -> None:
    adapter = (CASE / "src/oscillation_raw27_adapter.h").read_text(encoding="utf-8")
    assert "#define KAPPA_OFFSET_MODEL_PHI_SIGN (-1.0)" in adapter
