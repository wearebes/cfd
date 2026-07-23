from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "generate/stationary_bubble/src/make_fixed_horizon_vof_host.py"
SPEC = importlib.util.spec_from_file_location("stationary_vof_host", BUILDER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_vof_host_preserves_method_and_adds_analysis_horizon() -> None:
    stock = (ROOT / "basilisk/src/test/spurious.c").read_text(encoding="utf-8")
    generated = MODULE.build(stock)
    assert '#include "vof.h"' in generated
    assert '#include "tension.h"' in generated
    assert "two-phase-clsvof.h" not in generated
    assert "distance_curvature" not in generated
    assert "#define TMAX (2.*sq(DIAMETER)/MU)" in generated
    assert "DC = -1.;" in generated
    assert "event tau_one_milestone (t = TAU_ONE_TIME)" in generated
    assert "event fixed_horizon (t = TMAX)" in generated
    assert '"tau_1"' in generated
    assert '"terminal"' in generated
    assert '"fixed_tau_limit,2' in generated
    assert "active_provider_ekmax" in generated


def test_vof_host_build_is_deterministic() -> None:
    stock = (ROOT / "basilisk/src/test/spurious.c").read_text(encoding="utf-8")
    assert MODULE.build(stock) == MODULE.build(stock)
