from pathlib import Path

from experiments.rising_clsvof_kreplace.summarize_canary import parse_provider_stats, read_facet_segments


def test_parse_provider_stats_from_log_text():
    log = """
some solver line
rising_k_provider_stats evaluations=12345 clamp_hits=0
"""

    assert parse_provider_stats(log) == {"evaluations": 12345, "clamp_hits": 0}


def test_parse_provider_stats_returns_none_when_missing():
    assert parse_provider_stats("solver log without provider footer") is None


def test_read_facet_segments_ignores_provider_stats_footer(tmp_path: Path):
    log = tmp_path / "log"
    log.write_text(
        "0 0\n"
        "1 0\n"
        "\n"
        "rising_k_provider_stats evaluations=12 clamp_hits=0\\n",
        encoding="utf-8",
    )

    assert read_facet_segments(log) == [((0.0, 0.0), (1.0, 0.0))]
