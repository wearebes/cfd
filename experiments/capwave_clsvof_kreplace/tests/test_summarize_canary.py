from pathlib import Path

import pytest

from experiments.capwave_clsvof_kreplace.summarize_canary import parse_provider_stats, read_log, read_wave


def test_parse_provider_stats_from_log_text():
    log = "capwave_k_provider_stats evaluations=123 clamp_hits=0\n"

    assert parse_provider_stats(log) == {"evaluations": 123, "clamp_hits": 0}


def test_read_wave_ignores_provider_stats_footer(tmp_path: Path):
    path = tmp_path / "wave-64"
    path.write_text("0 0.01\n1 0.02\ncapwave_k_provider_stats evaluations=2 clamp_hits=0\n", encoding="utf-8")

    assert read_wave(path) == [(0.0, 0.01), (1.0, 0.02)]


def test_read_log_ignores_provider_stats_footer(tmp_path: Path):
    path = tmp_path / "log"
    path.write_text("32 0.001\ncapwave_k_provider_stats evaluations=2 clamp_hits=0\n", encoding="utf-8")

    assert read_log(path) == [(32.0, 0.001)]


def test_missing_mode_requires_explicit_partial_summary(tmp_path: Path):
    from experiments.capwave_clsvof_kreplace.summarize_canary import main

    baseline = tmp_path / "baseline"
    baseline.mkdir()
    baseline.joinpath("log").write_text("32 0.1\n64 0.2\n128 0.3\n256 0.4\n", encoding="utf-8")
    for resolution in (64, 128, 256, 512):
        baseline.joinpath(f"wave-{resolution}").write_text("0 0.0\n1 1.0\n", encoding="utf-8")

    result = tmp_path / "result"
    result.mkdir()

    with pytest.raises(FileNotFoundError):
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["summarize_canary.py", str(result), "--baseline-dir", str(baseline)]
            main()
        finally:
            sys.argv = old_argv
