from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "generate/_shared/run_manifest.py"


def plan_args(tmp_path: Path, source: Path) -> list[str]:
    runner = tmp_path / "runner.sh"
    runner.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    return [
        "--repo-root",
        str(ROOT),
        "--case",
        "capwave",
        "--benchmark",
        "capwave",
        "--method",
        "NN",
        "--purpose",
        "smoke",
        "--output",
        str(tmp_path / "result"),
        "--generator",
        str(runner),
        "--generator-logical",
        "generate/capwave/NN.sh",
        "--parameter",
        "resolution=64",
        "--parameter",
        "imax=3",
        "--parameter",
        "experiment_role=default",
        "--parameter",
        "model=baseline_64_hgradient",
        "--parameter",
        "openmp_threads=1",
        "--source",
        f"compiled_case=source_snapshot/case.c::{source}",
        "--compile-arg=/repo/qcc",
        "--compile-arg=-O2",
        "--compile-arg=case.c",
        "--run-arg=./case",
    ]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        text=True,
        capture_output=True,
    )


def test_dry_run_and_started_manifest_share_one_plan(tmp_path: Path) -> None:
    source = tmp_path / "case.c"
    source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    args = plan_args(tmp_path, source)
    planned = run("dry-run", *args)
    assert planned.returncode == 0, planned.stderr
    planned_payload = json.loads(planned.stdout)

    manifest = tmp_path / "result/manifest.json"
    started = run("start", *args, "--manifest", str(manifest))
    assert started.returncode == 0, started.stderr
    running_payload = json.loads(manifest.read_text())
    assert running_payload["status"] == "running"
    assert running_payload["resolution"] == 64
    assert running_payload["model"] == "baseline_64_hgradient"
    assert running_payload["experiment_role"] == "default"
    assert (
        planned_payload["plan"]["plan_sha256"]
        == running_payload["plan"]["plan_sha256"]
    )

    completed = run(
        "complete",
        *args,
        "--manifest",
        str(manifest),
        "--elapsed-seconds",
        "1.25",
    )
    assert completed.returncode == 0, completed.stderr
    completed_payload = json.loads(manifest.read_text())
    assert completed_payload["status"] == "completed"
    assert completed_payload["elapsed_seconds"] == 1.25


def test_completion_rejects_source_drift(tmp_path: Path) -> None:
    source = tmp_path / "case.c"
    source.write_text("before\n", encoding="utf-8")
    args = plan_args(tmp_path, source)
    manifest = tmp_path / "result/manifest.json"
    started = run("start", *args, "--manifest", str(manifest))
    assert started.returncode == 0, started.stderr

    source.write_text("after\n", encoding="utf-8")
    completed = run(
        "complete",
        *args,
        "--manifest",
        str(manifest),
        "--elapsed-seconds",
        "0.1",
    )
    assert completed.returncode != 0
    assert "resolved run plan changed" in completed.stderr
    assert json.loads(manifest.read_text())["status"] == "running"
