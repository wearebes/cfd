from __future__ import annotations

import csv
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FINALIZER = ROOT / "generate/_shared/finalize_row.py"


FIELD_HEADER = (
    "snapshot,target_solver_time,actual_solver_time,actual_benchmark_time,"
    "iteration,x,y,Delta,level,u_x,u_y,pressure,vorticity,phase_fraction,"
    "common_curvature,common_curvature_valid,active_curvature,"
    "active_curvature_valid\n"
)


def test_capwave_intermediates_compact_to_exact_reviewed_row_schema(
    tmp_path: Path,
) -> None:
    row = tmp_path / "row"
    (row / "source_snapshot").mkdir(parents=True)
    (row / "source_snapshot/source.c").write_text("source\n", encoding="utf-8")
    (row / "manifest.json").write_text(
        json.dumps({"case": "capwave", "method": "CLSVOF", "analysis_ready": True}),
        encoding="utf-8",
    )
    (row / "scientific_artifacts.json").write_text(
        json.dumps(
            {
                "analysis_ready": True,
                "benchmark_output_coverage_complete": True,
                "required_metric_names": ["relative_rms_error"],
            }
        ),
        encoding="utf-8",
    )
    with (row / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerow({"metric": "relative_rms_error", "value": "0.01"})
    (row / "plot_data.csv").write_text(
        "tau,amplitude,reference_amplitude,amplitude_error\n0,0,0,0\n",
        encoding="utf-8",
    )
    (row / "fields.csv").write_text(
        FIELD_HEADER
        + "middle,1,1.01,2,10,0,0,0.1,5,0,0,1,0,0.5,2,1,,0\n"
        + "final,2,2,4,20,0,0,0.1,5,0,0,1,0,1.0000000000016573,2,1,3,1\n",
        encoding="utf-8",
    )
    (row / "compile.stdout").write_text("compiled\n", encoding="utf-8")
    (row / "compile.stderr").write_text("", encoding="utf-8")
    (row / "solver.stdout.txt").write_text("solver\n", encoding="utf-8")
    (row / "wave.dat").write_text("intermediate\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(FINALIZER), str(row)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert {path.name for path in row.iterdir()} == {
        "manifest.json",
        "source_snapshot",
        "timeseries.csv",
        "fields.csv.gz",
        "run.log",
    }
    manifest = json.loads((row / "manifest.json").read_text())
    assert set(manifest["published_artifacts"]) == {
        "timeseries.csv", "fields.csv.gz", "run.log"
    }
    assert set(manifest["field_snapshots"]["snapshots"]) == {"middle", "final"}
    with gzip.open(row / "fields.csv.gz", "rt", encoding="utf-8") as stream:
        assert stream.readline() == FIELD_HEADER


def test_field_compaction_rejects_material_phase_fraction_overshoot(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(FINALIZER.parent))
    import finalize_row

    (tmp_path / "fields.csv").write_text(
        FIELD_HEADER
        + "middle,1,1,1,1,0,0,0.1,5,0,0,1,0,0.5,2,1,3,1\n"
        + "final,2,2,2,2,0,0,0.1,5,0,0,1,0,1.000001,2,1,3,1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid field geometry or phase fraction"):
        finalize_row.compact_fields(tmp_path)


def test_stationary_milestone_compaction_adds_tau2_and_capillary_number(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(FINALIZER.parent))
    import finalize_row

    path = tmp_path / "milestones.csv"
    path.write_text(
        "milestone,tau,iteration,u_star,shape_error_avg,shape_error_rms,"
        "shape_error_max,official_style_ekmax,active_provider_ekmax,"
        "active_provider_samples\n"
        "tau_1,1,10,0.1,0.01,0.02,0.03,0.04,0.05,12\n"
        "terminal,2,20,0.05,0.005,0.01,0.02,0.03,0.04,14\n",
        encoding="utf-8",
    )
    finalize_row.compact_stationary_milestones(tmp_path)
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    assert {row["milestone"] for row in rows} == {"tau_1", "tau_2"}
    assert all(float(row["capillary_number"]) > 0 for row in rows)
