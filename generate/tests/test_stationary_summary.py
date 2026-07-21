from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "generate/stationary_bubble/src/summarize_smoke.py"
SPEC = importlib.util.spec_from_file_location("stationary_summary", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
stationary_summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stationary_summary)


def test_summary_extracts_complete_official_terminal_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    result = tmp_path / "result"
    native = result / "clsvof"
    nn = result / "nn"
    native.mkdir(parents=True)
    nn.mkdir()
    for mode in (native, nn):
        (mode / "La-12000-6").write_text(
            "0 0.01 0.1\n1 0.001 1e-10\n", encoding="utf-8"
        )
    (native / "log").write_text(
        "6 12000 1e-8 1e-5 1e-4 1e-3 0.00134959\n",
        encoding="utf-8",
    )
    (nn / "log").write_text(
        "kappa_offset_provider_stats evaluations=42 clamp_hits=0\n"
        "6 12000 2e-8 2e-5 2e-4 2e-3 0.000528328\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", [str(SCRIPT), str(result)])
    assert stationary_summary.main() == 0

    with (result / "official_metrics.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert list(rows[0]) == [
        "mode",
        "level",
        "laplace_number",
        "u_star_final",
        "shape_error_avg",
        "shape_error_rms",
        "shape_error_max",
        "ekmax",
        "relative_curvature_error_percent",
    ]
    assert rows == [
        {
            "mode": "clsvof",
            "level": "6",
            "laplace_number": "12000.0",
            "u_star_final": "1e-08",
            "shape_error_avg": "1e-05",
            "shape_error_rms": "0.0001",
            "shape_error_max": "0.001",
            "ekmax": "0.00134959",
            "relative_curvature_error_percent": "0.0539836",
        },
        {
            "mode": "nn",
            "level": "6",
            "laplace_number": "12000.0",
            "u_star_final": "2e-08",
            "shape_error_avg": "2e-05",
            "shape_error_rms": "0.0002",
            "shape_error_max": "0.002",
            "ekmax": "0.000528328",
            "relative_curvature_error_percent": "0.02113312",
        },
    ]


def test_official_metrics_require_exactly_one_terminal_row(tmp_path: Path) -> None:
    log = tmp_path / "log"
    log.write_text("provider stats only\n", encoding="utf-8")
    try:
        stationary_summary.read_official_terminal_metrics(log)
    except ValueError as error:
        assert "expected one official seven-column terminal row" in str(error)
    else:
        raise AssertionError("missing official terminal row was accepted")
