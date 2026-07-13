from analyze_matrix import (
    convergence_rows,
    delta_rows,
    final_summary,
    paired_method_deltas,
    relationship_rows,
    tradeoff_rows,
)


def test_final_summary_replaces_stale_synthesis_and_links_full_analysis() -> None:
    summary = "# Status\n\n## Final scientific synthesis\n\nold\n"
    report = "# Analysis\n\n## Cross-resolution synthesis\n\n- new result\n"

    result = final_summary(summary, report)

    assert "old" not in result
    assert "- new result" in result
    assert "`formal_analysis.md`" in result


def test_deltas_are_same_identity_against_imax3() -> None:
    base = {
        "benchmark": "capwave",
        "method": "clsvof_native",
        "N": "64",
        "execution_state": "completed",
        "relative_rms": "0.2",
    }
    rows = [
        {**base, "row_id": "candidate", "imax": "2", "relative_rms": "0.1"},
        {**base, "row_id": "reference", "imax": "3"},
    ]
    result = delta_rows(rows)
    candidate = next(row for row in result if row["imax"] == 2)
    assert candidate["delta_relative_rms"] == -0.1
    assert candidate["ratio_relative_rms"] == 0.5


def test_paired_deltas_are_nn_minus_native_at_same_cell() -> None:
    base = {"benchmark": "capwave", "N": "64", "imax": "2", "execution_state": "completed"}
    rows = [
        {**base, "row_id": "native", "method": "clsvof_native", "relative_rms": "0.1"},
        {**base, "row_id": "nn", "method": "clsvof_nn", "relative_rms": "0.25"},
    ]
    paired = paired_method_deltas(rows)
    assert len(paired) == 1
    assert paired[0]["delta_nn_minus_native_relative_rms"] == 0.15
    assert paired[0]["ratio_nn_over_native_relative_rms"] == 2.5


def test_capwave_convergence_order_is_positive_for_decreasing_error() -> None:
    rows = [
        {
            "row_id": f"row{n}", "benchmark": "capwave", "method": "clsvof_native",
            "N": str(n), "imax": "3", "execution_state": "completed",
            "relative_rms": str(1 / n**2), "run_seconds": str(n**3),
        }
        for n in (64, 128, 256)
    ]
    result = convergence_rows(rows)[0]
    assert abs(result["observed_order_global"] - 2.0) < 1e-12
    assert abs(result["runtime_scaling_global"] - 3.0) < 1e-12


def test_tradeoff_separates_physics_sdf_and_cost_optima() -> None:
    rows = []
    for imax in range(6):
        rows.append(
            {
                "row_id": f"row{imax}", "benchmark": "capwave",
                "method": "clsvof_native", "N": "64", "imax": str(imax),
                "execution_state": "completed",
                "relative_rms": str(abs(imax - 2) + 1),
                "post_b15_egrad_mean": str(6 - imax),
                "run_seconds": str(imax + 1),
            }
        )
    result = tradeoff_rows(rows)[0]
    assert result["best_physics_imax"] == 2
    assert result["best_sdf_imax"] == 5
    assert result["lowest_cost_imax"] == 0


def test_relationship_reports_monotonicity_without_equating_it_to_physics() -> None:
    rows = []
    for imax in range(6):
        rows.append(
            {
                "row_id": f"row{imax}", "benchmark": "capwave",
                "method": "clsvof_native", "N": "64", "imax": str(imax),
                "execution_state": "completed", "relative_rms": str(imax + 1),
                "post_b15_egrad_mean": str(6 - imax),
            }
        )
    result = relationship_rows(rows)[0]
    assert result["egrad_monotone_nonincreasing_with_imax"] is True
    assert result["physics_monotone_nonincreasing_with_imax"] is False
    assert result["spearman_egrad_vs_physics"] == -1.0
