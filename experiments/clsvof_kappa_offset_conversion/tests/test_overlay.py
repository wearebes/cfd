from __future__ import annotations

import pytest
from experiments.clsvof_kappa_offset_conversion.make_overlay_integral import build_overlay_text


def test_overlay_changes_only_active_provider_line() -> None:
    source = "#endif // CURVATURE\nvoid f() { double ki = distance_curvature (point, d); }\n"
    output = build_overlay_text(source)
    assert 'include "clsvof_nn_cell_curvature.h"' in output
    assert "double ki = kappa_offset_provider (point, d);" in output
    assert "double ki = distance_curvature (point, d);" not in output


def test_overlay_rejects_missing_target() -> None:
    with pytest.raises(ValueError):
        build_overlay_text("#endif // CURVATURE\n")
