from __future__ import annotations

import json
from pathlib import Path

from hpc.lib.integrity import (
    atomic_json,
    expected_identity,
    inventory,
    validate_completed_result,
)
from hpc.lib.matrix import MatrixRow


ROW = MatrixRow("rising_case2", "clsvof_nn_cell_offset", 128, 5)


def make_result(path: Path, policy: str = "policy") -> None:
    path.mkdir(parents=True)
    (path / "out").write_text("0 1 2\n3 4 5\n", encoding="utf-8")
    (path / "nested").mkdir()
    (path / "nested/log").write_text("done\n", encoding="utf-8")
    atomic_json(
        path / "manifest.json",
        {
            "schema_version": 1,
            "formal_identity": expected_identity(ROW, "matrix", policy),
            "outputs": inventory(path),
        },
    )


def test_valid_result_is_accepted(tmp_path: Path) -> None:
    result = tmp_path / "result"
    make_result(result)
    assert validate_completed_result(result, ROW, "matrix", "policy")[0]


def test_one_byte_corruption_is_rejected(tmp_path: Path) -> None:
    result = tmp_path / "result"
    make_result(result)
    (result / "out").write_text("0 1 9\n3 4 5\n", encoding="utf-8")
    valid, reason = validate_completed_result(result, ROW, "matrix", "policy")
    assert not valid
    assert "integrity mismatch" in reason


def test_missing_and_extra_outputs_are_rejected(tmp_path: Path) -> None:
    result = tmp_path / "result"
    make_result(result)
    (result / "out").unlink()
    assert not validate_completed_result(result, ROW, "matrix", "policy")[0]

    result = tmp_path / "result2"
    make_result(result)
    (result / "undeclared").write_text("x", encoding="utf-8")
    assert not validate_completed_result(result, ROW, "matrix", "policy")[0]


def test_identity_and_policy_mismatch_are_rejected(tmp_path: Path) -> None:
    result = tmp_path / "result"
    make_result(result)
    wrong_row = MatrixRow("rising_case1", "clsvof_nn_cell_offset", 128, 5)
    assert not validate_completed_result(result, wrong_row, "matrix", "policy")[0]
    assert not validate_completed_result(result, ROW, "matrix", "other")[0]


def test_stale_staging_is_rejected(tmp_path: Path) -> None:
    result = tmp_path / "result"
    make_result(result)
    (tmp_path / ".result.staging.123").mkdir()
    valid, reason = validate_completed_result(result, ROW, "matrix", "policy")
    assert not valid
    assert "stale staging" in reason
