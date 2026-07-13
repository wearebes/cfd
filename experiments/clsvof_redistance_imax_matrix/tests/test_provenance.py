from run_row import provenance_inputs


def test_nn_provenance_includes_resolution_matched_weights() -> None:
    row = {"benchmark": "capwave", "method": "clsvof_nn", "N": 256}
    inputs = provenance_inputs(row)
    assert inputs["weights"].name == "nn_weights.h"
    assert "baseline_256_hgradient" in str(inputs["weights"])
    assert "nn_cell_curvature" in inputs


def test_native_provenance_does_not_claim_weights() -> None:
    row = {"benchmark": "rising_case1", "method": "clsvof_native", "N": 64}
    assert "weights" not in provenance_inputs(row)
