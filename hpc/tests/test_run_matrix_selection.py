from __future__ import annotations

from hpc.lib.matrix import formal_rows
from hpc.run_matrix import filter_benchmarks, filter_resolutions, parse_args


def test_repeatable_benchmark_filter_selects_only_rising_rows() -> None:
    args = parse_args(
        [
            "--matrix-id",
            "selection-test",
            "--benchmark",
            "rising_case1",
            "--benchmark",
            "rising_case2",
        ]
    )
    selected = filter_benchmarks(formal_rows(), args.benchmark)
    assert len(selected) == 96
    assert {row.benchmark for row in selected} == {"rising_case1", "rising_case2"}


def test_missing_benchmark_filter_preserves_the_full_matrix() -> None:
    assert len(filter_benchmarks(formal_rows(), None)) == 180


def test_resolution_filter_can_stage_one_rising_grid() -> None:
    rising = filter_benchmarks(
        formal_rows(), ["rising_case1", "rising_case2"]
    )
    selected = filter_resolutions(rising, [128])
    assert len(selected) == 24
    assert {row.resolution for row in selected} == {128}
