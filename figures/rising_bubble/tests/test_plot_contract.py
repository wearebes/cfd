from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "figures/rising_bubble/_plot_common.py"
SPEC = importlib.util.spec_from_file_location("rising_plot_common", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_line_style_encodes_method_and_color_encodes_imax() -> None:
    assert MODULE.IMAX_VALUES == (0, 1, 2, 3, 4, 5)
    assert {item["imax"] for item in MODULE.SERIES} == {0, 3}
    clsvof = [item for item in MODULE.SERIES if item["method"] == "clsvof"]
    nn = [
        item
        for item in MODULE.SERIES
        if item["method"] == "nn"
    ]
    assert {item["linestyle"] for item in clsvof} == {"-"}
    assert {item["linestyle"] for item in nn} == {"--"}
    assert {item["color"] for item in MODULE.SERIES if item["imax"] == 3} == {
        MODULE.IMAX3
    }
    assert {item["color"] for item in MODULE.SERIES if item["imax"] == 0} == {
        MODULE.IMAX0
    }


def test_main_metric_set_has_exactly_four_required_errors() -> None:
    assert [spec["key"] for spec in MODULE.METRIC_SPECS] == [
        "max_abs_relative_volume_error",
        "velocity_reference_rmse",
        "center_reference_rmse",
        "circularity_final_abs_error",
    ]
