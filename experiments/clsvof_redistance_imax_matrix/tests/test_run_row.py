from pathlib import Path

import run_row


def test_capwave_candidate_requires_byte_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_row, "ROOT", tmp_path)
    original = tmp_path / "old-wave"
    original.write_text("0 1\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    (work / "wave-64").write_text("0 1\n", encoding="utf-8")
    row = {
        "benchmark": "capwave",
        "N": 64,
        "planning_status": "candidate_reuse",
        "existing_evidence": "old-wave",
    }
    result = run_row.compare_candidate_reuse(work, row)
    assert result is not None
    assert result["comparison"] == "byte_identical"


def test_rising_candidate_ignores_nondeterministic_tail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_row, "ROOT", tmp_path)
    original = tmp_path / "old-out"
    original.write_text("t header\n0 1 2 3 4 100 200\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    (work / "out").write_text("t header\n0 1 2 3 4 900 800\n", encoding="utf-8")
    row = {
        "benchmark": "rising_case1",
        "planning_status": "candidate_reuse",
        "existing_evidence": "old-out",
    }
    result = run_row.compare_candidate_reuse(work, row)
    assert result is not None
    assert result["matched_rows"] == 1
    assert result["max_abs_difference"] == 0.0


def test_compile_command_sets_benchmark_final_time() -> None:
    capwave = {
        "benchmark": "capwave",
        "method": "clsvof_native",
        "N": 64,
    }
    rising = {
        "benchmark": "rising_case1",
        "method": "clsvof_native",
        "N": 64,
        "LEVEL": 6,
    }
    assert "-DREDIST_MATRIX_FINAL_TIME=2.2426211256" in run_row.compile_command(
        capwave, "case.c", "case"
    )
    assert "-DREDIST_MATRIX_FINAL_TIME=3.0" in run_row.compile_command(
        rising, "case.c", "case"
    )


def test_nn_compile_command_uses_offset_conversion_contract() -> None:
    row = {"benchmark": "capwave", "method": "clsvof_nn", "N": 128}
    command = run_row.compile_command(row, "case.c", "case")
    joined = " ".join(command)
    assert "KAPPA_OFFSET_CLAMP_FACTOR=1.0" in joined
    assert "clsvof_kappa_offset_conversion/include" in joined
    assert "CAPWAVE_K_NN_RAW" not in joined
    assert "RISING_K_NN_RAW" not in joined


def test_native_compile_command_has_no_legacy_provider() -> None:
    row = {"benchmark": "rising_case1", "method": "clsvof_native", "N": 64, "LEVEL": 6}
    joined = " ".join(run_row.compile_command(row, "case.c", "case"))
    assert "K_MODE" not in joined
    assert "kreplace/include" not in joined
