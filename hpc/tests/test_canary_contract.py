from hpc.run_canaries import CORRECTNESS_ROWS, candidates


def test_correctness_canaries_cover_all_benchmarks() -> None:
    assert {row.benchmark for row in CORRECTNESS_ROWS} == {
        "capwave",
        "rising_case1",
        "rising_case2",
        "stationary_bubble",
    }
    assert all(row.resolution == 64 and row.imax == 3 for row in CORRECTNESS_ROWS)
    assert all(row.method == "clsvof_nn_cell_offset" for row in CORRECTNESS_ROWS)


def test_scaling_candidates_are_bounded_and_unique() -> None:
    assert candidates(128) == [1, 16, 32, 64, 128]
    assert candidates(64) == [1, 16, 32, 64]
    assert candidates(2) == [1, 2]
