from summarize_matrix import (
    capwave_reference_summary,
    interpolate,
    make_failures,
    make_long,
    make_wide,
    performance_summary,
    percentile,
    point_segment_distance,
    write_summary,
)


def test_percentile_uses_linear_interpolation() -> None:
    assert percentile([0.0, 10.0], 0.95) == 9.5
    assert percentile([3.0], 0.95) == 3.0
    assert percentile([], 0.95) is None


def test_wide_pairs_native_and_nn_without_crossing_imax() -> None:
    rows = [
        {
            "row_id": "native",
            "benchmark": "capwave",
            "method": "clsvof_native",
            "N": 64,
            "LEVEL": None,
            "actual_grid": "64x64",
            "imax": 2,
            "relative_rms": 0.1,
        },
        {
            "row_id": "nn",
            "benchmark": "capwave",
            "method": "clsvof_nn",
            "N": 64,
            "LEVEL": None,
            "actual_grid": "64x64",
            "imax": 2,
            "relative_rms": 0.2,
        },
    ]
    wide = make_wide(rows)
    assert len(wide) == 1
    assert wide[0]["native_relative_rms"] == 0.1
    assert wide[0]["nn_relative_rms"] == 0.2


def test_point_segment_distance_projects_to_segment() -> None:
    assert point_segment_distance((0.5, 1.0), (0.0, 0.0), (1.0, 0.0)) == 1.0
    assert point_segment_distance((2.0, 0.0), (0.0, 0.0), (1.0, 0.0)) == 1.0


def test_long_metrics_have_one_row_per_metric() -> None:
    rows = [
        {
            "row_id": "row",
            "benchmark": "capwave",
            "method": "clsvof_native",
            "N": 64,
            "imax": 3,
            "execution_state": "completed",
            "relative_rms": 0.1,
            "run_seconds": 2.0,
        }
    ]
    long = make_long(rows)
    assert {(item["metric"], item["value"]) for item in long} == {
        ("relative_rms", 0.1),
        ("run_seconds", 2.0),
    }


def test_hysing_interpolation_is_linear() -> None:
    history = [(0.0, 1.0, 2.0), (2.0, 3.0, 6.0)]
    assert interpolate(history, 1.0, 1) == 2.0
    assert interpolate(history, 1.0, 2) == 4.0


def test_capwave_reference_metrics_use_stock_index_pairing(tmp_path) -> None:
    (tmp_path / "wave-64").write_text("0 0.01\n1 0.02\n", encoding="utf-8")
    (tmp_path / "prosperetti.h").write_text(
        "static double prosperetti[][2] = {{0, 0.01}, {1, 0.01}};\n",
        encoding="utf-8",
    )
    result = capwave_reference_summary(tmp_path, {"N": 64})
    assert result["reference_samples"] == 2
    assert result["amplitude_l2_error"] == (0.0001 / 2) ** 0.5
    assert result["relative_rms_recomputed"] == (0.5) ** 0.5
    assert result["max_abs_amplitude_error"] == 0.01


def test_stock_multigrid_performance_is_parsed_when_present(tmp_path) -> None:
    (tmp_path / "log").write_text(
        "# Multigrid, 1636 steps, 171.996 CPU, 178.2 real, 1.5e+05 points.step/s\n",
        encoding="utf-8",
    )
    assert performance_summary(tmp_path) == {
        "solver_steps": 1636,
        "stock_cpu_seconds": 171.996,
        "stock_real_seconds": 178.2,
    }


def test_failure_ledger_excludes_planned_and_running_rows() -> None:
    rows = [
        {"row_id": "planned", "execution_state": "planned"},
        {"row_id": "running", "execution_state": "running"},
        {"row_id": "failed", "execution_state": "failed_runtime", "error": "boom"},
    ]
    ledger = make_failures(rows)
    assert [row["row_id"] for row in ledger] == ["failed"]
    assert ledger[0]["error"] == "boom"


def test_complete_summary_does_not_claim_conclusions_are_withheld(tmp_path) -> None:
    rows = [
        {"execution_state": "completed", "N": n, "final_diagnostic_ok": True}
        for n in (64, 128, 256, 512)
        for _ in range(24)
    ]
    path = tmp_path / "summary.md"

    write_summary(path, "matrix", rows)

    text = path.read_text()
    assert "row-level matrix is complete" in text
    assert "conclusions are withheld" not in text
