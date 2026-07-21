from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
FIGURE_DIR = ROOT / "figures/rising_bubble"
MODULE_PATH = FIGURE_DIR / "build_source_data_from_dataset.py"
sys.path.insert(0, str(FIGURE_DIR))
SPEC = importlib.util.spec_from_file_location("rising_dataset_source", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_formal_dataset_has_complete_96_row_metric_matrix() -> None:
    rows = MODULE.build_rows(MODULE.DEFAULT_DATASET)
    assert len(rows) == 96
    assert {
        (
            row["benchmark"],
            row["method_id"],
            row["resolution"],
            row["imax"],
        )
        for row in rows
    } == {
        (benchmark, method, resolution, imax)
        for benchmark in MODULE.BENCHMARKS
        for method in MODULE.METHODS
        for resolution in MODULE.RESOLUTIONS
        for imax in MODULE.IMAX_VALUES
    }
    assert all(math.isclose(float(row["terminal_time"]), 3.0) for row in rows)
    assert all(row["numerical_circularity_history_available"] is False for row in rows)


def test_formal_dataset_pairs_all_imax_and_uses_lower_error_as_positive() -> None:
    rows = MODULE.build_rows(MODULE.DEFAULT_DATASET)
    pairs = MODULE.paired_rows(rows)
    assert len(pairs) == 48
    assert {int(row["imax"]) for row in pairs} == {0, 1, 2, 3, 4, 5}
    for row in pairs:
        for metric in MODULE.ERROR_METRICS:
            clsvof = float(row[f"{metric}_clsvof"])
            nn = float(row[f"{metric}_nn"])
            expected = 100.0 * (clsvof - nn) / clsvof
            assert math.isclose(
                float(row[f"{metric}_nn_improvement_percent"]),
                expected,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )


def test_n512_curve_sources_limit_numerical_series_to_imax0_and_imax3() -> None:
    dynamics = pd.read_csv(MODULE.DEFAULT_OUTPUT / "dynamics_N512_imax0_vs3.csv")
    circularity = pd.read_csv(
        MODULE.DEFAULT_OUTPUT / "circularity_N512_imax0_vs3.csv"
    )
    for frame in (dynamics, circularity):
        numerical = frame[frame["method_id"].ne("reference")]
        assert set(numerical["imax"].astype(str)) == {"0", "3"}
    numerical_phi = circularity[circularity["method_id"].ne("reference")]
    assert set(numerical_phi["availability"]) == {"final_only"}
    assert set(numerical_phi["time"]) == {3.0}


def test_source_audit_proves_circularity_availability_boundary() -> None:
    audit = MODULE.source_audit(MODULE.DEFAULT_DATASET)
    assert audit["formal_matrix_groups"] == 96
    assert audit["formal_history_files"] == 96
    assert audit["formal_final_interface_files"] == 96
    assert audit["numerical_circularity_history_samples"] == 0
    assert audit["numerical_time_resolved_interface_files"] == 0
    assert audit["nonformal_recomputations_used"] is False
    recoverable = audit["recoverable_from_formal_dataset"]
    assert recoverable["circularity_at_t3"] is True
    assert recoverable["circularity_history"] is False
    assert recoverable["numerical_circularity_minimum"] is False
    for validation in audit["reference_t3_circularity_validation"].values():
        assert validation["absolute_difference"] < 5e-4
    closure = audit["minimum_new_data_for_full_numerical_circularity_curve"]
    assert closure["requires_new_solver_output"] is True
    assert closure["imax"] == [3, 0]
    assert closure["row_count"] == 8
    assert closure["executed"] is False


def test_metric_contract_separates_heatmap_and_curve_imax_scope() -> None:
    scope = MODULE.metric_contract()["display_scope"]
    assert scope["heatmap_imax"] == [0, 1, 2, 3, 4, 5]
    assert scope["curve_imax"] == [3, 0]
