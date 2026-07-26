from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "generate/_shared/build_scientific_artifacts.py"
SPEC = importlib.util.spec_from_file_location("scientific_artifacts", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_gnuplot_uncertainty_pair_uses_central_value(tmp_path: Path) -> None:
    path = tmp_path / "laplace.dat"
    path.write_text("25.6 {559641.20252078, 1.3707256146761e-10} 0.2\n")
    assert MODULE.numeric_rows(path, 3) == [[25.6, 559641.20252078, 0.2]]


def test_provider_stats_are_extracted_once_and_runtime_log_is_purified(
    tmp_path: Path,
) -> None:
    stats_line = (
        "kappa_offset_provider_stats evaluations=12 clamp_hits=1 "
        "denominator_guard_hits=2 min_abs_denominator=0.2 "
        "max_abs_d_over_h=0.4 grad_samples=12 grad_min=0.9 "
        "grad_mean=1 grad_std=0.1 grad_max=1.1\n"
    )
    runtime = tmp_path / "runtime_and_terminal.log"
    runtime.write_text("benchmark row\n" + stats_line, encoding="utf-8")

    metrics, record = MODULE.provider_runtime_metrics(tmp_path, {"method": "NN"})
    assert record is not None
    assert record["path"] == "provider_stats.csv"
    assert metrics == []
    assert runtime.read_text(encoding="utf-8") == "benchmark row\n"

    first_csv = (tmp_path / "provider_stats.csv").read_text(encoding="utf-8")
    second_metrics, second_record = MODULE.provider_runtime_metrics(
        tmp_path, {"method": "NN"}
    )
    assert second_record == record
    assert second_metrics == metrics
    assert (tmp_path / "provider_stats.csv").read_text(encoding="utf-8") == first_csv


def test_native_row_rejects_provider_stats(tmp_path: Path) -> None:
    (tmp_path / "runtime.stderr.txt").write_text(
        "kappa_offset_provider_stats evaluations=1\n", encoding="utf-8"
    )
    try:
        MODULE.provider_runtime_metrics(tmp_path, {"method": "CLSVOF"})
    except ValueError as error:
        assert "non-NN row" in str(error)
    else:
        raise AssertionError("native row accepted NN provider stats")


def test_vof_hf_capwave_has_complete_plot_and_metric_inputs(tmp_path: Path) -> None:
    samples = [(index / 737, 0.0) for index in range(738)]
    (tmp_path / "wave.dat").write_text(
        "".join(f"{time} {amplitude}\n" for time, amplitude in samples),
        encoding="utf-8",
    )
    (tmp_path / "prosperetti.h").write_text(
        "".join(f"{{{time}, {amplitude}}}\n" for time, amplitude in samples),
        encoding="utf-8",
    )
    (tmp_path / "official_error.dat").write_text("32 0\n", encoding="utf-8")
    metrics, artifacts = MODULE.capwave(tmp_path, {"resolution": 64})
    assert (tmp_path / "plot_data.csv").is_file()
    assert {item["path"] for item in artifacts} == {
        "wave.dat", "official_error.dat", "prosperetti.h"
    }
    assert {item["metric"] for item in metrics} >= {
        "relative_rms_error", "relative_rms_error_recomputed", "samples"
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "case": "capwave",
                "benchmark": "capwave",
                "method": "VOF-HF",
                "resolution": 64,
                "imax": None,
                "model": None,
                "experiment_role": "official_reference",
                "grid_role": "stock_native",
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(PATH), str(tmp_path)],
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    contract = json.loads((tmp_path / "scientific_artifacts.json").read_text())
    assert contract["analysis_ready"] is True
    assert contract["plot_columns"] == MODULE.REQUIRED_PLOT_COLUMNS["capwave"]
    assert set(contract["required_metric_names"]) == MODULE.REQUIRED_METRICS["capwave"]
    assert json.loads((tmp_path / "manifest.json").read_text())["analysis_ready"] is True


def test_vof_hf_rising_retains_shape_and_circularity_inputs(tmp_path: Path) -> None:
    (tmp_path / "history.dat").write_text(
        "0 0 0 0 0 0.1\n3 0.001 0 1.2 0.3 0.01\n", encoding="utf-8"
    )
    (tmp_path / "interface.dat").write_text("0 0\n1 1\n", encoding="utf-8")
    (tmp_path / "circularity.csv").write_text(
        "time,iteration,half_area,half_perimeter,circularity\n"
        "0,0,0.1,0.5,0.9\n3,10,0.1,0.6,0.8\n",
        encoding="utf-8",
    )
    metrics, artifacts = MODULE.rising(tmp_path, {})
    assert (tmp_path / "plot_data.csv").is_file()
    assert {item["path"] for item in artifacts} == {
        "history.dat", "interface.dat", "circularity.csv"
    }
    assert {item["metric"] for item in metrics} >= {
        "rise_velocity_x_max", "circularity_min", "circularity_final"
    }


def test_vof_hf_stationary_retains_tau1_tau2_and_curvature_inputs(
    tmp_path: Path,
) -> None:
    (tmp_path / "timeseries.dat").write_text(
        "0 0.2 0.01\n1 0.1 0.001\n2 0.05 0.0001\n", encoding="utf-8"
    )
    (tmp_path / "runtime_and_terminal.log").write_text(
        "6 12000 0.05 0.01 0.02 0.03 0.04\n", encoding="utf-8"
    )
    (tmp_path / "termination.csv").write_text(
        "reason,requested_terminal_tau,actual_terminal_tau,iteration\n"
        "fixed_tau_limit,2,2,20\n",
        encoding="utf-8",
    )
    header = (
        "milestone,tau,iteration,u_star,shape_error_avg,shape_error_rms,"
        "shape_error_max,official_style_ekmax,active_provider_ekmax,"
        "active_provider_samples\n"
    )
    (tmp_path / "milestones.csv").write_text(
        header
        + "tau_1,1,10,0.1,0.01,0.02,0.03,0.04,0.04,12\n"
        + "terminal,2,20,0.05,0.005,0.01,0.02,0.03,0.03,14\n",
        encoding="utf-8",
    )
    metrics, artifacts = MODULE.stationary(
        tmp_path,
        {"method": "VOF-HF", "tau_max": 2, "resolution": 64},
    )
    assert (tmp_path / "plot_data.csv").is_file()
    assert (tmp_path / "official_terminal.dat").is_file()
    metric_map = {item["metric"]: item for item in metrics}
    assert metric_map["u_star_tau_1"]["time"] == 1.0
    assert metric_map["actual_terminal_tau"]["value"] == 2.0
    assert metric_map["duplicate_tau_samples_removed"]["value"] == 0
    assert "VOF height-function" in metric_map["active_provider_ekmax"]["definition"]
    assert {item["path"] for item in artifacts} >= {
        "timeseries.dat", "milestones.csv", "termination.csv"
    }


def test_stationary_deduplicates_only_the_repeated_recorded_terminal(
    tmp_path: Path,
) -> None:
    (tmp_path / "timeseries.dat").write_text(
        "0 0.2 0.01\n1 0.1 0.001\n2 0.06 0.0002\n2 0.05 0.0001\n",
        encoding="utf-8",
    )
    (tmp_path / "runtime_and_terminal.log").write_text(
        "6 12000 0.05 0.01 0.02 0.03 0.04\n", encoding="utf-8"
    )
    (tmp_path / "termination.csv").write_text(
        "reason,requested_terminal_tau,actual_terminal_tau,iteration\n"
        "fixed_tau_limit,2,2,20\n",
        encoding="utf-8",
    )
    (tmp_path / "milestones.csv").write_text(
        "milestone,tau,iteration,u_star,shape_error_avg,shape_error_rms,"
        "shape_error_max,official_style_ekmax,active_provider_ekmax,"
        "active_provider_samples\n"
        "tau_1,1,10,0.1,0.01,0.02,0.03,0.04,0.04,12\n"
        "terminal,2,20,0.05,0.005,0.01,0.02,0.03,0.03,14\n",
        encoding="utf-8",
    )

    metrics, _ = MODULE.stationary(
        tmp_path, {"method": "CLSVOF", "tau_max": 2, "resolution": 64}
    )

    plot_rows = (tmp_path / "plot_data.csv").read_text(encoding="utf-8").splitlines()
    assert len(plot_rows) == 4
    assert plot_rows[-1].startswith("2.0,0.05,")
    assert {row["metric"]: row["value"] for row in metrics}[
        "duplicate_tau_samples_removed"
    ] == 1


def test_stationary_deduplicates_an_interior_duplicate() -> None:
    series, removed = MODULE.normalize_duplicate_stationary_samples(
        [[0.0, 0.2, 0.01], [1.0, 0.1, 0.001], [1.0, 0.09, 0.0009], [2.0, 0.05, 0.0001]],
    )
    assert [row[0] for row in series] == [0.0, 1.0, 2.0]
    assert series[1][1] == 0.09
    assert removed == 1


def test_stationary_rejects_a_decreasing_time() -> None:
    with pytest.raises(ValueError, match="stationary tau decreases"):
        MODULE.normalize_duplicate_stationary_samples(
            [[0.0, 0.2, 0.01], [1.0, 0.1, 0.001], [0.5, 0.09, 0.0009]],
        )


def test_vof_hf_oscillating_retains_fit_and_kinetic_inputs(tmp_path: Path) -> None:
    (tmp_path / "timeseries.dat").write_text(
        "0 0 1\n1 0.001 2\n", encoding="utf-8"
    )
    (tmp_path / "termination.csv").write_text(
        "reason,requested_terminal_time,actual_terminal_time,iteration\n"
        "fixed_time_limit,1,1,20\n",
        encoding="utf-8",
    )
    (tmp_path / "fit.log").write_text(
        "a = 0.001 +/- 0.0001\nb = 1 +/- 0.1\nc = 155 +/- 1\n",
        encoding="utf-8",
    )
    (tmp_path / "fit_curve.dat").write_text("0 0.001\n1 0\n", encoding="utf-8")
    (tmp_path / "error.dat").write_text("25.6 0.01 0.2\n", encoding="utf-8")
    (tmp_path / "laplace.dat").write_text("25.6 1000 0.2\n", encoding="utf-8")
    (tmp_path / "fit_summary.dat").write_text(
        "fit 25.6 0.001 1 155\n", encoding="utf-8"
    )
    metrics, artifacts = MODULE.oscillating(
        tmp_path, {"cells_per_diameter": 25.6, "fit_enabled": True}
    )
    assert (tmp_path / "plot_data.csv").is_file()
    assert {item["path"] for item in artifacts} >= {
        "timeseries.dat", "fit_curve.dat", "fit.log", "error.dat",
        "laplace.dat", "fit_summary.dat", "termination.csv"
    }
    assert {item["metric"] for item in metrics} >= {
        "max_kinetic_energy", "fit_b", "frequency_error_abs_percent",
        "equivalent_laplace"
    }
