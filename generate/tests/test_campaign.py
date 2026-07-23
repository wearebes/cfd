from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "generate/_shared/campaign.py"
SPEC = importlib.util.spec_from_file_location("generate_campaign", PATH)
CAMPAIGN = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = CAMPAIGN
SPEC.loader.exec_module(CAMPAIGN)


def test_formal_campaign_has_397_rows_with_uniform_oscillating_match() -> None:
    rows = CAMPAIGN.formal_rows()
    assert len(rows) == 397
    assert len({row.label for row in rows}) == 397
    assert {row.method for row in rows} == {"VOF-HF", "CLSVOF", "NN"}
    assert sum(row.method == "VOF-HF" for row in rows) == 29
    vof_hf = [row for row in rows if row.method == "VOF-HF"]
    assert sum(row.grid_role == "stock_native" for row in vof_hf) == 11
    assert sum(row.grid_role == "stock_compatible_extension" for row in vof_hf) == 13
    assert sum(row.grid_role == "uniform_matched" for row in vof_hf) == 5
    assert len(CAMPAIGN.matched_rows()) == 368


def test_every_method_uses_the_same_case_centered_path_shape() -> None:
    assert CAMPAIGN.VOFHFRow("capwave", None, 32).relative_output.as_posix() == (
        "capwave/N0032/VOF-HF"
    )
    assert CAMPAIGN.Row("capwave", None, 32, 3, "CLSVOF").relative_output.as_posix() == (
        "capwave/N0032/imax03/CLSVOF"
    )
    assert CAMPAIGN.VOFHFRow("rising_bubble", 2, 64).relative_output.as_posix() == (
        "rising_bubble/case2/N0064/VOF-HF"
    )
    assert CAMPAIGN.Row("rising_bubble", 2, 64, 3, "NN").relative_output.as_posix() == (
        "rising_bubble/case2/N0064/imax03/NN"
    )
    assert CAMPAIGN.VOFHFRow(
        "oscillating_droplet", None, 64
    ).relative_output.as_posix() == "oscillating_droplet/adaptive/N0064/VOF-HF"
    assert CAMPAIGN.VOFHFRow(
        "oscillating_droplet", None, 64, "uniform"
    ).relative_output.as_posix() == "oscillating_droplet/uniform/N0064/VOF-HF"
    assert CAMPAIGN.Row(
        "oscillating_droplet", None, 64, 20, "NN"
    ).relative_output.as_posix() == "oscillating_droplet/uniform/N0064/imax20/NN"


def test_reviewed_default_imax_roles_are_case_aware() -> None:
    rows = CAMPAIGN.formal_rows()
    assert sum(row.experiment_role == "default" for row in rows) == 48
    assert sum(row.experiment_role == "sensitivity" for row in rows) == 320
    assert sum(row.experiment_role == "official_reference" for row in rows) == 24
    assert sum(row.experiment_role == "matched_reference" for row in rows) == 5
    assert all(
        row.experiment_role == (
            ("matched_reference" if row.grid_role == "uniform_matched" else "official_reference")
            if isinstance(row, CAMPAIGN.VOFHFRow)
            else "default"
            if row.imax == (0 if row.case == "stationary_bubble" else 3)
            else "sensitivity"
        )
        for row in rows
    )


def test_case_row_counts_and_stationary_resolution_boundary() -> None:
    rows = CAMPAIGN.formal_rows()
    counts = {
        case: sum(row.case == case for row in rows)
        for case in {row.case for row in rows}
    }
    assert counts == {
        "capwave": 95,
        "rising_bubble": 190,
        "stationary_bubble": 12,
        "oscillating_droplet": 100,
    }
    assert {
        row.resolution for row in rows if row.case == "stationary_bubble"
    } == {32, 64, 128, 256}


def test_canary_covers_defaults_and_every_new_high_imax_at_n32() -> None:
    rows = CAMPAIGN.canary_rows()
    assert len(rows) == 56
    assert {row.resolution for row in rows} == {32, 64}
    assert {row.imax for row in rows} == {None, 0, 3, 10, 15, 20}
    assert {row.experiment_role for row in rows} == {
        "default", "sensitivity", "official_reference", "matched_reference"
    }
    assert sum(row.method == "VOF-HF" for row in rows) == 12
    assert len({row.label for row in rows}) == 56
    high = [row for row in rows if row.imax in CAMPAIGN.HIGH_IMAX_VALUES]
    assert len(high) == 24
    assert {row.resolution for row in high} == {32}
    assert {row.method for row in high} == {"CLSVOF", "NN"}
    stationary_commands = [
        row.command(ROOT / "tem/test_canary", "smoke", 1)
        for row in rows
        if row.case == "stationary_bubble" and row.method != "VOF-HF"
    ]
    assert stationary_commands
    assert all("--imax" in command for command in stationary_commands)
    assert all(
        command[command.index("--imax") + 1] == "0"
        for command in stationary_commands
    )
    assert all(
        command[command.index("--tau-max") + 1] == "2.0"
        for command in stationary_commands
    )


def test_nn_model_identity_is_resolution_locked() -> None:
    for row in CAMPAIGN.formal_rows():
        expected = (
            f"baseline_{row.resolution}_hgradient" if row.method == "NN" else None
        )
        assert row.model == expected


def test_oscillating_reference_is_part_of_the_campaign_source_lock() -> None:
    lock = CAMPAIGN.source_lock()
    assert "basilisk/src/test/oscillation.ref" in lock
    assert len(lock["basilisk/src/test/oscillation.ref"]) == 64


def test_batch_execution_settings_are_recorded_in_source() -> None:
    source = PATH.read_text()
    assert '"cpu_slots": cpu_slots' in source
    assert '"resource_policy_sha256": policy_hash' in source
    assert '"row_count": len(rows)' in source
    assert '"purpose": purpose' in source
    assert '"git_commit": baseline_commit' in source


def test_resource_policy_keeps_vof_serial_and_scales_matched_rows() -> None:
    policy = CAMPAIGN.load_resource_policy()
    slots = CAMPAIGN.available_logical_cpus()
    assert policy["cpu_slots_config"] == "auto"
    assert policy["cpu_slots"] == slots
    assert CAMPAIGN.row_threads(CAMPAIGN.VOFHFRow("capwave", None, 512), policy) == 1
    assert CAMPAIGN.row_threads(
        CAMPAIGN.Row("capwave", None, 32, 3, "CLSVOF"), policy
    ) == min(2, slots)
    assert CAMPAIGN.row_threads(
        CAMPAIGN.Row("oscillating_droplet", None, 512, 3, "NN"), policy
    ) == min(16, slots)


def test_solver_campaign_requires_linux(monkeypatch) -> None:
    policy = CAMPAIGN.load_resource_policy()
    monkeypatch.setattr(CAMPAIGN.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(CAMPAIGN.platform, "release", lambda: "macOS")
    with pytest.raises(ValueError, match="requires Linux"):
        CAMPAIGN.verify_execution_host(policy)


def test_solver_campaign_accepts_generic_linux(monkeypatch) -> None:
    policy = CAMPAIGN.load_resource_policy()
    monkeypatch.setattr(CAMPAIGN.platform, "system", lambda: "Linux")
    monkeypatch.setattr(CAMPAIGN, "configured_qcc", lambda: ROOT / "generate/job.sh")
    CAMPAIGN.verify_execution_host(policy)


def test_formal_campaign_has_no_smoke_approval_gate() -> None:
    assert not hasattr(CAMPAIGN, "verify_run_approval")


def test_process_group_cleanup_stops_a_live_child() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
        text=True,
    )
    try:
        CAMPAIGN.terminate_process_groups([process], grace_seconds=0.2)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_vof_command_ignores_nonserial_thread_argument() -> None:
    command = CAMPAIGN.VOFHFRow("capwave", None, 32).command(
        ROOT / "tem/test_vof_threads", "smoke", 32
    )
    assert command[command.index("--threads") + 1] == "1"


def test_runner_paths_match_git_casing_for_linux() -> None:
    campaign_root = ROOT / "tem/test_runner_paths"
    capillary = CAMPAIGN.Row("capwave", None, 32, 3, "CLSVOF").command(
        campaign_root, "smoke", 4
    )
    oscillating = CAMPAIGN.Row(
        "oscillating_droplet", None, 32, 3, "NN"
    ).command(campaign_root, "smoke", 4)
    assert capillary[1].endswith("generate/capwave/CLSVOF.sh")
    assert oscillating[1].endswith("generate/oscillating_droplet/NN.sh")


def test_scheduler_uses_vof_rows_as_early_backfill_not_serial_tail() -> None:
    policy = CAMPAIGN.load_resource_policy()
    indexed = list(enumerate(CAMPAIGN.formal_rows(), 1))
    ordered = CAMPAIGN.scheduler_order(indexed, policy)
    assert all(row.method == "VOF-HF" for _, row in ordered[:29])
    tail_threads = min(16, int(policy["cpu_slots"]))
    assert all(CAMPAIGN.row_threads(row, policy) == tail_threads for _, row in ordered[-10:])


def _two_stage_fixture(tmp_path: Path) -> tuple[object, Path, object]:
    row = CAMPAIGN.Row("capwave", None, 32, 3, "CLSVOF")
    campaign_root = tmp_path / "campaign"
    build_dir = CAMPAIGN.build_directory(campaign_root, row)
    build_dir.mkdir(parents=True)
    executable = build_dir / "executable"
    executable.write_bytes(b"reviewed campaign executable")
    source = {
        "path": "toolchain/qcc",
        "sha256": "1" * 64,
        "bytes": 1,
    }
    compile_record = {
        "argv": ["qcc", "source.c", "-o", "solver"],
        "cwd": "$WORK",
        "stdout": "compile.stdout",
        "stderr": "compile.stderr",
        "display": "qcc source.c -o solver",
    }
    parameters = {
        "resolution": 32,
        "imax": 3,
        "experiment_role": "default",
        "grid_strategy": "uniform",
        "model": None,
        "openmp_threads": 4,
        "compile_only": 1,
        "compile_reused": False,
    }
    build_plan = {
        "plan_sha256": "b" * 64,
        "output": str(build_dir.resolve()),
        "generator": {"path": "generate/capwave/CLSVOF.sh", "sha256": "2" * 64},
        "parameters": parameters,
        "environment": {"OMP_DYNAMIC": False, "OMP_NUM_THREADS": 4},
        "commands": {
            "compile": compile_record,
            "run": {"argv": [], "cwd": "$WORK", "stdout": "", "stderr": ""},
        },
        "sources": {"qcc": source},
    }
    CAMPAIGN.atomic_json(
        build_dir / "manifest.json",
        {
            "status": "completed",
            "case": row.case,
            "method": row.method,
            "purpose": "formal",
            "resolution": row.resolution,
            "imax": row.imax,
            "experiment_role": row.experiment_role,
            "grid_strategy": row.grid_strategy,
            "plan": build_plan,
        },
    )
    artifact = CAMPAIGN.verify_build_artifact(
        row, campaign_root, "formal", threads=4
    )
    row_dir = campaign_root / row.relative_output
    row_dir.mkdir(parents=True)
    result_parameters = dict(parameters)
    result_parameters.update(compile_only=0, compile_reused=True)
    result_plan = {
        **build_plan,
        "plan_sha256": "c" * 64,
        "output": str(row_dir.resolve()),
        "parameters": result_parameters,
        "commands": {
            "compile": compile_record,
            "run": {
                "argv": ["./solver"],
                "cwd": "$WORK",
                "stdout": "stdout.txt",
                "stderr": "stderr.txt",
            },
        },
        "sources": {
            "qcc": source,
            "precompiled_executable": {
                "path": "build/precompiled_executable",
                "sha256": artifact.executable_sha256,
                "bytes": executable.stat().st_size,
            },
        },
    }
    CAMPAIGN.atomic_json(row_dir / "manifest.json", {"plan": result_plan})
    return row, campaign_root, artifact


def test_two_stage_build_is_hash_bound_before_temporary_cleanup(tmp_path: Path) -> None:
    row, campaign_root, artifact = _two_stage_fixture(tmp_path)
    CAMPAIGN.bind_build_to_completed_row(row, campaign_root, artifact)
    manifest = json.loads(
        (campaign_root / row.relative_output / "manifest.json").read_text()
    )
    CAMPAIGN.verify_build_binding(manifest, row.label)
    assert manifest["build_binding"]["strategy"] == "campaign_two_stage"
    assert manifest["build_binding"]["executable_sha256"] == artifact.executable_sha256
    CAMPAIGN.remove_build_directory(campaign_root, row)
    assert not artifact.directory.exists()
    CAMPAIGN.verify_build_binding(manifest, row.label)


def test_two_stage_binding_rejects_compile_command_drift(tmp_path: Path) -> None:
    row, campaign_root, artifact = _two_stage_fixture(tmp_path)
    manifest_path = campaign_root / row.relative_output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plan"]["commands"]["compile"]["argv"].append("-DCHANGED=1")
    CAMPAIGN.atomic_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="compile command changed"):
        CAMPAIGN.bind_build_to_completed_row(row, campaign_root, artifact)


def test_resource_summary_reports_full_slot_solve_utilization(tmp_path: Path) -> None:
    metadata = tmp_path / "_meta"
    metadata.mkdir()
    (metadata / "resource_usage.csv").write_text(
        "timestamp,phase,active_rows,allocated_slots,cpu_utilization_percent,"
        "memory_available_bytes,swap_used_bytes\n"
        "t1,solve,4,32,96,1000,0\n"
        "t2,solve,4,32,94,900,0\n"
        "t3,solve,1,16,50,800,0\n",
        encoding="utf-8",
    )
    CAMPAIGN.write_resource_summary(tmp_path, 32)
    summary = json.loads((metadata / "resource_summary.json").read_text())
    assert summary["full_slot_solve_samples"] == 2
    assert summary["full_slot_mean_cpu_utilization_percent"] == 95


def test_clean_git_baseline_requires_a_committed_worktree(monkeypatch) -> None:
    def fake_run(command, **_kwargs):
        if command[-2:] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, "abc123\n", "")
        return subprocess.CompletedProcess(command, 0, " M generate/job.sh\n", "")

    monkeypatch.setattr(CAMPAIGN.subprocess, "run", fake_run)
    try:
        CAMPAIGN.clean_git_baseline()
    except ValueError as error:
        assert "clean committed worktree" in str(error)
    else:
        raise AssertionError("dirty worktree was accepted for formal")


def test_clean_git_baseline_returns_head(monkeypatch) -> None:
    def fake_run(command, **_kwargs):
        output = "abc123\n" if command[-2:] == ["rev-parse", "HEAD"] else ""
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(CAMPAIGN.subprocess, "run", fake_run)
    monkeypatch.setattr(CAMPAIGN, "verify_campaign_inputs_committed", lambda: None)
    assert CAMPAIGN.clean_git_baseline() == "abc123"


def test_formal_input_gate_rejects_untracked_model_exports(
    monkeypatch, tmp_path: Path
) -> None:
    model_export = tmp_path / "nn_weights.h"
    model_export.write_text("weights\n", encoding="utf-8")
    monkeypatch.setattr(CAMPAIGN, "ROOT", tmp_path)
    monkeypatch.setattr(CAMPAIGN, "configured_qcc", lambda: tmp_path / "qcc")
    monkeypatch.setattr(CAMPAIGN, "source_files", lambda: [model_export])

    def fake_run(command, **_kwargs):
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(CAMPAIGN.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="formal campaign inputs are not committed"):
        CAMPAIGN.verify_campaign_inputs_committed()


def test_layout_is_a_read_only_case_centered_contract(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())
    completed = subprocess.run(
        ["bash", str(ROOT / "generate/job.sh"), "layout", "--root", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "status=implementation_ready_for_review" in completed.stdout
    assert "data/" in completed.stdout
    assert "capwave/{summary.csv,Nxxxx/{VOF-HF,imaxNN/{CLSVOF,NN}}}/" in completed.stdout
    assert "formal_items=397 smoke_items=56" in completed.stdout
    assert set(tmp_path.iterdir()) == before


def test_compaction_moves_sources_to_shared_provenance(
    tmp_path: Path,
) -> None:
    campaign_root = tmp_path / "campaign"
    row_dir = campaign_root / "capwave/N0032/imax03/CLSVOF"
    snapshot = row_dir / "source_snapshot"
    snapshot.mkdir(parents=True)
    overlay = snapshot / "redistance_overlay.json"
    overlay.write_text('{"imax": 3}\n')

    official_reference = ROOT / "basilisk/src/test/prosperetti.h"
    object_path = CAMPAIGN.ensure_provenance_object(official_reference, campaign_root)
    shared_reference = campaign_root / "_meta/references/prosperetti.h"
    CAMPAIGN.ensure_named_hardlink(object_path, shared_reference)

    manifest_path = row_dir / "manifest.json"
    CAMPAIGN.atomic_json(
        manifest_path,
        {
            "case": "capwave",
            "plan": {
                "sources": {
                    "redistance_overlay": {
                        "path": "source_snapshot/redistance_overlay.json",
                        "sha256": CAMPAIGN.sha256(overlay),
                        "bytes": overlay.stat().st_size,
                    }
                }
            },
        },
    )

    CAMPAIGN.compact_row_provenance(row_dir, campaign_root)

    manifest = json.loads(manifest_path.read_text())
    record = manifest["provenance"]["sources"]["redistance_overlay"]
    assert not snapshot.exists()
    assert (campaign_root / record["object"]).is_file()
    CAMPAIGN.verify_source_references(manifest, row_dir, campaign_root)
    assert shared_reference.is_file()
    assert json.loads((campaign_root / "_meta/object_index.json").read_text())[
        "object_count"
    ] == 2


def test_smoke_is_the_public_alias_and_canary_remains_compatible() -> None:
    source = PATH.read_text(encoding="utf-8")
    assert '"smoke", "canary"' in source
    assert 'args.action in {"smoke", "canary"}' in source


def test_oscillating_vof_hf_campaign_report_replaces_row_status_files(
    tmp_path: Path,
) -> None:
    native = CAMPAIGN.VOFHFRow("oscillating_droplet", None, 64)
    rows = [native]
    row_dir = tmp_path / native.relative_output
    row_dir.mkdir(parents=True)
    (row_dir / "manifest.json").write_text(
        json.dumps(
            {
                "oscillating_vof_hf_verification": {
                    "compile_exit_status": 0,
                    "run_exit_status": 0,
                    "started_at": "2026-01-01T00:00:00Z",
                    "ended_at": "2026-01-01T00:10:00Z",
                    "wall_seconds": 600,
                    "strict_log_ref_match": True,
                    "actual_log_sha256": "fit-digest",
                    "official_ref_sha256": "ref-digest",
                    "execution_status": {},
                }
            }
        ),
        encoding="utf-8",
    )

    CAMPAIGN.write_oscillating_vof_hf_report(rows, tmp_path)

    payload = json.loads(
        (tmp_path / "_meta/oscillating_vof_hf_official.json").read_text()
    )
    assert payload["replaces_row_files"] == [
        "VOF-HF_report.json",
        "VOF-HF_RESULTS.md",
        "verification.json",
    ]
    (entry,) = payload["rows"]
    assert entry["row"] == "oscillating_droplet/adaptive/N0064/VOF-HF"
    assert entry["grid_role"] == "stock_native"
    assert entry["status"] == "official_pass"
    assert entry["strict_log_ref_match"] is True
    assert entry["official_ref_sha256"] == "ref-digest"
    assert entry["wall_seconds"] == 600

    # A non-empty strict diff on a stock-native grid is a recorded regression
    # mismatch, and non-oscillating rows never produce a rollup.
    manifest = json.loads((row_dir / "manifest.json").read_text())
    manifest["oscillating_vof_hf_verification"]["strict_log_ref_match"] = False
    (row_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    CAMPAIGN.write_oscillating_vof_hf_report(rows, tmp_path)
    payload = json.loads(
        (tmp_path / "_meta/oscillating_vof_hf_official.json").read_text()
    )
    assert payload["rows"][0]["status"] == "official_regression_mismatch"
    other_root = tmp_path / "other"
    other_root.mkdir()
    CAMPAIGN.write_oscillating_vof_hf_report(
        [CAMPAIGN.VOFHFRow("capwave", None, 32)], other_root
    )
    assert not (other_root / "_meta/oscillating_vof_hf_official.json").exists()
