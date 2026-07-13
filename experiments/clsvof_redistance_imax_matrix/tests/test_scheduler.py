import csv

import pytest

from run_matrix import current_max_jobs, estimate_cost, has_final_diagnostic, select_rows


def test_extreme_phase_has_eight_formal_n64_rows() -> None:
    rows = []
    for benchmark in ("capwave", "rising_case1"):
        for method in ("clsvof_native", "clsvof_nn"):
            for imax in range(6):
                rows.append(
                    {
                        "row_id": f"{benchmark}-{method}-{imax}",
                        "benchmark": benchmark,
                        "method": method,
                        "N": 64,
                        "imax": imax,
                        "planning_status": "planned_run",
                    }
                )
    selected = select_rows({"rows": rows}, "n64_extremes")
    assert len(selected) == 8
    assert {row["imax"] for row in selected} == {0, 5}


def test_n64_remaining_excludes_extremes_and_reuse_rows() -> None:
    rows = []
    for benchmark in ("capwave", "rising_case1"):
        for method in ("clsvof_native", "clsvof_nn"):
            for imax in range(6):
                rows.append(
                    {
                        "row_id": f"{benchmark}-{method}-{imax}",
                        "benchmark": benchmark,
                        "method": method,
                        "N": 64,
                        "imax": imax,
                        "planning_status": (
                            "candidate_reuse"
                            if benchmark == "capwave" and imax == 3
                            else "planned_run"
                        ),
                    }
                )
    selected = select_rows({"rows": rows}, "n64_remaining")
    assert len(selected) == 14
    assert {row["imax"] for row in selected} == {1, 2, 3, 4}
    assert not any(row["benchmark"] == "capwave" and row["imax"] == 3 for row in selected)


@pytest.mark.parametrize("n", [128, 256, 512])
def test_resolution_phase_selects_only_requested_n(n: int) -> None:
    rows = [
        {
            "row_id": f"row-{candidate}",
            "benchmark": "rising_case1",
            "method": "clsvof_native",
            "N": candidate,
            "imax": 2,
            "planning_status": "planned_run",
        }
        for candidate in (64, 128, 256, 512)
    ]
    selected = select_rows({"rows": rows}, f"n{n}")
    assert [row["N"] for row in selected] == [n]


def test_longest_processing_time_order() -> None:
    slow = {
        "row_id": "slow",
        "benchmark": "capwave",
        "method": "clsvof_nn",
        "N": 512,
        "imax": 5,
        "planning_status": "planned_run",
    }
    fast = {
        "row_id": "fast",
        "benchmark": "rising_case1",
        "method": "clsvof_native",
        "N": 64,
        "imax": 0,
        "planning_status": "planned_run",
    }
    selected = select_rows({"rows": [fast, slow]}, "all_new")
    assert selected == [slow, fast]
    assert estimate_cost(slow) > estimate_cost(fast)


def test_reuse_replay_selects_only_candidate_rows() -> None:
    candidate = {
        "row_id": "candidate",
        "benchmark": "capwave",
        "method": "clsvof_native",
        "N": 64,
        "imax": 3,
        "planning_status": "candidate_reuse",
    }
    planned = {**candidate, "row_id": "planned", "planning_status": "planned_run"}
    assert select_rows({"rows": [planned, candidate]}, "reuse_replay") == [candidate]


def test_reuse_resolution_phase_does_not_cross_n() -> None:
    rows = [
        {
            "row_id": f"candidate-{n}",
            "benchmark": "capwave",
            "method": "clsvof_native",
            "N": n,
            "imax": 3,
            "planning_status": "candidate_reuse",
        }
        for n in (64, 128, 256, 512)
    ]
    assert [row["N"] for row in select_rows({"rows": rows}, "reuse_n128")] == [128]


def test_final_diagnostic_requires_pre_and_post_for_both_bands(tmp_path) -> None:
    row = {"benchmark": "rising_case1", "N": 64, "imax": 3, "method": "clsvof_native"}
    metrics = (
        tmp_path
        / "rising_case1"
        / "N0064"
        / "imax03"
        / "clsvof_native"
        / "redistance_metrics.csv"
    )
    metrics.parent.mkdir(parents=True)
    with metrics.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["t", "stage", "band_cells"])
        writer.writeheader()
        for stage in ("pre", "post"):
            for band in ("1.5", "3.0"):
                writer.writerow({"t": "3", "stage": stage, "band_cells": band})
    assert has_final_diagnostic(tmp_path, row)


def test_n512_all_includes_planned_and_reuse() -> None:
    base = {
        "benchmark": "capwave",
        "method": "clsvof_native",
        "N": 512,
        "imax": 3,
    }
    rows = [
        {**base, "row_id": "reuse", "planning_status": "candidate_reuse"},
        {**base, "row_id": "planned", "imax": 2, "planning_status": "planned_run"},
        {**base, "row_id": "wrong-n", "N": 256, "planning_status": "planned_run"},
    ]
    assert {row["row_id"] for row in select_rows({"rows": rows}, "n512_all")} == {
        "reuse",
        "planned",
    }


def test_dynamic_max_jobs_file(tmp_path) -> None:
    path = tmp_path / "capacity.json"
    path.write_text('{"max_jobs": 3}\n', encoding="utf-8")
    assert current_max_jobs(5, path) == 3
    path.write_text('{"max_jobs": 5}\n', encoding="utf-8")
    assert current_max_jobs(3, path) == 5


def test_dynamic_max_jobs_rejects_above_approved_ceiling(tmp_path) -> None:
    path = tmp_path / "capacity.json"
    path.write_text('{"max_jobs": 6}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="ceiling 5"):
        current_max_jobs(3, path)
