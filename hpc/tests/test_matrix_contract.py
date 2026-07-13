from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from hpc.lib.matrix import (
    MatrixRow,
    formal_rows,
    generator_command,
    load_contract,
    result_relative_path,
)


ROOT = Path(__file__).resolve().parents[2]


def test_formal_matrix_has_exact_scientific_shape() -> None:
    rows = formal_rows()
    assert len(rows) == len({row.row_id for row in rows}) == 180
    assert Counter(row.benchmark for row in rows) == {
        "capwave": 48,
        "rising_case1": 48,
        "rising_case2": 48,
        "stationary_bubble": 36,
    }
    assert Counter(row.method for row in rows) == {
        "clsvof_native": 90,
        "clsvof_nn_cell_offset": 90,
    }
    assert Counter(row.imax for row in rows) == {imax: 30 for imax in range(6)}


def test_contract_file_matches_generated_matrix() -> None:
    contract = load_contract(ROOT / "hpc/config/matrix_180.json")
    assert contract["matrix_name"] == "clsvof_native_nn_cell_offset_imax_0_5"


def test_rising_cases_are_distinct_but_share_resolution_identity() -> None:
    case1 = MatrixRow("rising_case1", "clsvof_nn_cell_offset", 256, 3)
    case2 = MatrixRow("rising_case2", "clsvof_nn_cell_offset", 256, 3)
    assert case1.row_id != case2.row_id
    assert result_relative_path(case1) != result_relative_path(case2)
    assert case1.level == case2.level == 8
    assert case1.actual_grid == case2.actual_grid == "256x64"
    assert case1.model_name == case2.model_name == "baseline_256_hgradient"


def test_rising_generator_commands_select_the_official_case() -> None:
    output = Path("/tmp/result")
    case1 = generator_command(
        ROOT,
        MatrixRow("rising_case1", "clsvof_native", 64, 0),
        purpose="formal",
        output=output,
    )
    case2 = generator_command(
        ROOT,
        MatrixRow("rising_case2", "clsvof_nn_cell_offset", 64, 5),
        purpose="formal",
        output=output,
    )
    assert case1[case1.index("--case") + 1] == "1"
    assert case2[case2.index("--case") + 1] == "2"
    assert case1[0].endswith("cases/rising_bubble/generate/native.sh")
    assert case2[0].endswith("cases/rising_bubble/generate/nn_cell_offset.sh")


@pytest.mark.parametrize("imax", [-1, 6, 10])
def test_matrix_row_rejects_imax_outside_contract(imax: int) -> None:
    with pytest.raises(ValueError, match="imax"):
        MatrixRow("capwave", "clsvof_native", 64, imax)


def test_stationary_n512_is_a_hard_error() -> None:
    with pytest.raises(ValueError, match="stationary N512"):
        MatrixRow("stationary_bubble", "clsvof_native", 512, 3)


def test_all_result_paths_are_unique_and_relative() -> None:
    paths = [result_relative_path(row) for row in formal_rows()]
    assert len(paths) == len(set(paths)) == 180
    assert all(not path.is_absolute() and ".." not in path.parts for path in paths)
