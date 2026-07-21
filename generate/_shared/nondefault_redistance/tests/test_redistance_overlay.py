from pathlib import Path
import importlib.util

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src/make_redistance_overlay.py"
SPEC = importlib.util.spec_from_file_location("shared_redistance_overlay", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

ROOT = Path(__file__).resolve().parents[4]
STOCK = ROOT / "basilisk/src/two-phase-clsvof.h"


@pytest.mark.parametrize("imax", range(6))
def test_builds_cloud_matrix_imax_range(imax: int) -> None:
    source = STOCK.read_text(encoding="utf-8")
    output = MODULE.build_overlay_text(source, imax, metrics=False)
    assert f"redistance (d, imax = {imax}, phixxmin = HUGE);" in output


@pytest.mark.parametrize("imax", [-1, 6, 11, 100])
def test_rejects_values_outside_cloud_matrix(imax: int) -> None:
    with pytest.raises(ValueError, match="imax"):
        MODULE.build_overlay_text(STOCK.read_text(encoding="utf-8"), imax)
