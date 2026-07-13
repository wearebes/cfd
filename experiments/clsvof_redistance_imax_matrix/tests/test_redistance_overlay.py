from pathlib import Path

import pytest

from make_redistance_overlay import TARGET, build_overlay_text, build_provenance


ROOT = Path(__file__).resolve().parents[3]
STOCK = ROOT / "basilisk/src/two-phase-clsvof.h"


@pytest.mark.parametrize("imax", range(6))
def test_builds_each_approved_imax(imax: int) -> None:
    source = STOCK.read_text(encoding="utf-8")
    output = build_overlay_text(source, imax)
    assert TARGET not in output.splitlines()
    assert f"redistance (d, imax = {imax}, phixxmin = HUGE);" in output
    assert f"#define REDIST_MATRIX_IMAX {imax}" in output
    assert output.count('include "redistance_matrix_metrics.h"') == 1
    assert "redistance_matrix_should_sample (i, t)" in output


@pytest.mark.parametrize("imax", [-1, 6, 100])
def test_rejects_unapproved_imax(imax: int) -> None:
    with pytest.raises(ValueError, match="imax"):
        build_overlay_text(STOCK.read_text(encoding="utf-8"), imax)


def test_requires_exact_stock_target() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        build_overlay_text("not the stock header", 3)


def test_provenance_hashes_source_and_generated_text() -> None:
    source = STOCK.read_text(encoding="utf-8")
    output = build_overlay_text(source, 3)
    provenance = build_provenance(source, output, 3)
    assert provenance["imax"] == 3
    assert provenance["target_count"] == 1
    assert provenance["source_sha256"] != provenance["generated_sha256"]
