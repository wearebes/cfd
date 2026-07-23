from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    ROOT / "generate/oscillating_droplet/VOF-HF/build_official_report.py"
)


def test_report_contract_contains_only_standard_variant(tmp_path: Path) -> None:
    dataset = tmp_path / "VOF-HF/oscillating_droplet"
    snapshot = dataset / "source_snapshot"
    dataset.mkdir(parents=True)
    snapshot.mkdir()

    cell = "25.6"
    level = 6
    log = f"fit {cell} 1 2 3\n"
    (dataset / "fit_summary.dat").write_text(log, encoding="utf-8")
    (snapshot / "oscillation.ref").write_text(
        "fit 6.4 1 2 3\nfit 12.8 1 2 3\n" + log + "fit 51.2 1 2 3\n",
        encoding="utf-8",
    )
    (dataset / "error.dat").write_text(
        f"{cell} 0.1 0.2\n",
        encoding="utf-8",
    )
    (dataset / "laplace.dat").write_text(
        f"{cell} 100 0.2\n",
        encoding="utf-8",
    )
    (dataset / "solver.stdout.txt").write_text(
        "gnuplot fit output\n", encoding="utf-8"
    )
    (dataset / "fit.log").write_text("fit details\n", encoding="utf-8")
    (dataset / "timeseries.dat").write_text("0 0 1\n", encoding="utf-8")
    (dataset / "fit_curve.dat").write_text("0 0\n", encoding="utf-8")
    (dataset / "termination.csv").write_text(
        "reason,requested_terminal_time,actual_terminal_time,iteration\n"
        "fixed_time_limit,1,1,10\n",
        encoding="utf-8",
    )

    common_args = [
        sys.executable,
        str(BUILDER),
        "--dataset",
        str(dataset),
        "--resolution",
        "64",
        "--level",
        str(level),
        "--cells-per-diameter",
        cell,
    ]
    completed = subprocess.run(
        [
            *common_args,
            "--grid-role",
            "stock_native",
            "--grid-strategy",
            "adaptive",
            "--experiment-role",
            "official_reference",
            "--compile-exit-status",
            "0",
            "--run-exit-status",
            "0",
            "--started-at",
            "2026-01-01T00:00:00Z",
            "--ended-at",
            "2026-01-01T00:00:01Z",
            "--wall-seconds",
            "1",
        ],
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr

    report = json.loads(completed.stdout)
    assert report["method"] == "VOF-HF"
    assert report["solver_variant"] == "Standard"
    assert report["resolution"] == 64
    assert report["grid_role"] == "stock_native"
    assert report["complete_artifacts"] is True
    assert report["status"] == "official_pass"
    assert report["strict_log_ref_match"] is True
    assert report["excluded_solver_variants"] == ["Momentum", "Compressible"]

    uniform_completed = subprocess.run(
        [
            *common_args,
            "--grid-role",
            "uniform_matched",
            "--grid-strategy",
            "uniform",
            "--experiment-role",
            "matched_reference",
            "--compile-exit-status",
            "0",
            "--run-exit-status",
            "0",
            "--started-at",
            "2026-01-01T00:00:00Z",
            "--ended-at",
            "2026-01-01T00:00:01Z",
            "--wall-seconds",
            "1",
        ],
        text=True,
        capture_output=True,
    )
    assert uniform_completed.returncode == 0, uniform_completed.stderr
    uniform_report = json.loads(uniform_completed.stdout)
    assert uniform_report["status"] == "uniform_matched_complete"
    assert uniform_report["strict_log_ref_match"] is None
    assert uniform_report["grid_strategy"] == "uniform"
    assert uniform_report["experiment_role"] == "matched_reference"

    diff = dataset / "fit_summary_vs_ref.diff"
    assert diff.is_file()
    assert diff.stat().st_size == 0

    # Per-row status files were removed by the 2026-07-23 smoke review; the
    # campaign-level rollup replaces them.
    for legacy in ("VOF-HF_report.json", "VOF-HF_RESULTS.md", "verification.json"):
        assert not (dataset / legacy).exists()
    assert not (dataset / "official_report.json").exists()
    assert not (dataset / "OFFICIAL_RESULTS.md").exists()
    assert not (dataset / "Momentum").exists()
    assert not (dataset / "Compressible").exists()
    assert not (dataset / "Standard").exists()
