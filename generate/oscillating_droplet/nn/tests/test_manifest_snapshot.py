from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RUNNER_PATH = ROOT / "generate/oscillating_droplet/nn/generate/run_row.py"
SPEC = importlib.util.spec_from_file_location("oscillating_run_row", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def test_manifest_completion_hashes_persistent_source_snapshot(tmp_path: Path) -> None:
    output = tmp_path / "row"
    snapshot = output / "source_snapshot"
    snapshot.mkdir(parents=True)
    for name in (
        "source.c",
        "method_host_overlay.json",
        RUNNER.ADAPTER.name,
        "integral.stock.h",
        "two-phase-clsvof.h",
        "redistance_overlay.json",
        RUNNER.FIELD_HEADER.name,
    ):
        (snapshot / name).write_text(f"{name}\n", encoding="utf-8")
    precompiled = tmp_path / "solver"
    precompiled.write_bytes(b"solver")
    args = argparse.Namespace(
        method="CLSVOF",
        formal=True,
        imax=3,
        grid="uniform",
        threads=2,
        compile_only=False,
        precompiled=precompiled,
        dry_run=False,
    )
    plan_args = RUNNER.plan_arguments(
        args=args,
        output=output,
        work=output,
        level=5,
        model_name=None,
        model_dir=None,
        checkpoint=None,
        compile_cmd=["qcc", "source.c", "-o", "oscillation"],
        run_cmd=["./oscillation"],
        method_nn=False,
    )
    manifest = output / "manifest.json"

    RUNNER.transition("start", plan_args, "--manifest", str(manifest))
    RUNNER.transition(
        "complete",
        plan_args,
        "--manifest",
        str(manifest),
        "--elapsed-seconds",
        "1.0",
    )

    assert '"status": "completed"' in manifest.read_text(encoding="utf-8")
