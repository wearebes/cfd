from __future__ import annotations

import importlib.util
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
RUNNER_PATH = CASE / "generate/run_imax_matrix.py"
SPEC = importlib.util.spec_from_file_location("oscillation_imax_runner", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


def test_matrix_has_48_unique_rows() -> None:
    rows = [
        RUNNER.row_id(level, imax, method)
        for level in RUNNER.LEVELS
        for imax in RUNNER.IMAX_VALUES
        for method in RUNNER.METHODS
    ]
    assert len(rows) == 48
    assert len(set(rows)) == 48


def test_matrix_covers_requested_resolutions_and_imax() -> None:
    assert tuple(1 << level for level in RUNNER.LEVELS) == (64, 128, 256, 512)
    assert RUNNER.IMAX_VALUES == (0, 1, 2, 3, 4, 5)
    assert RUNNER.METHODS == ("clsvof", "nn")


def test_row_outputs_are_isolated() -> None:
    root = Path("/tmp/result")
    outputs = {
        RUNNER.row_output(root, level, imax, method)
        for level in RUNNER.LEVELS
        for imax in RUNNER.IMAX_VALUES
        for method in RUNNER.METHODS
    }
    assert len(outputs) == 48
