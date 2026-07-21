from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "figures/rising_bubble/build_source_data.py"
SPEC = importlib.util.spec_from_file_location("rising_build_source", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_reference_interface_is_deduplicated_into_nonzero_segments() -> None:
    segments = MODULE.reference_interface_segments(1)
    assert len(segments) == 325
    assert all(segment[:2] != segment[2:] for segment in segments)


def test_paired_metric_improvement_uses_lower_error_as_positive() -> None:
    common = {
        "benchmark": "rising_case1",
        "resolution": 64,
        "imax": 3,
        "terminal_time": 3.0,
        "circularity_min": 0.9,
        "time_at_circularity_min": 2.0,
    }
    rows = []
    for method, factor in (("clsvof", 1.0), ("nn", 0.75)):
        rows.append(
            {
                **common,
                "method_id": method,
                **{metric: factor for metric in MODULE.ERROR_METRICS},
            }
        )
    paired = MODULE.paired_metrics(rows)
    assert len(paired) == 1
    for metric in MODULE.ERROR_METRICS:
        assert paired[0][f"{metric}_nn_improvement_percent"] == 25.0


def test_metric_contract_keeps_chamfer_supplementary() -> None:
    contract = MODULE.metric_contract()
    assert set(contract["metrics"]) == {
        "relative_volume_error",
        "rise_velocity",
        "center_height",
        "circularity",
    }
    assert contract["chamfer_role"].startswith("supplementary")
    assert "every original solver iteration" in contract["metrics"]["circularity"]["sampling"]
