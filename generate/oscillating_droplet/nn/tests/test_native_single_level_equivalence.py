from __future__ import annotations

import os

import pytest

from conftest import ROOT


@pytest.mark.parametrize("level", [6, 7])
def test_native_row_matches_frozen_when_result_root_is_given(level: int) -> None:
    result_root = os.environ.get("OSCILLATION_NN_RESULT_ROOT")
    if not result_root:
        pytest.skip("set OSCILLATION_NN_RESULT_ROOT after formal rows are generated")
    generated = ROOT / result_root / f"level_{level}/clsvof/k-{level}"
    frozen = (
        ROOT
        / f"dataset/oscillating_droplet/N{1 << level:04d}/imax03/clsvof/timeseries.dat"
    )
    assert generated.read_bytes() == frozen.read_bytes()
