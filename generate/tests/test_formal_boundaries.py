from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    ROOT / "generate/capwave/CLSVOF.sh",
    ROOT / "generate/capwave/NN.sh",
]
STATIONARY = [
    ROOT / "generate/stationary_bubble/CLSVOF.sh",
    ROOT / "generate/stationary_bubble/NN.sh",
]
OFFICIAL = [
    (ROOT / "generate/capwave/VOF-HF.sh", ("--resolution", "32")),
    (
        ROOT / "generate/rising_bubble/VOF-HF.sh",
        ("--case", "1", "--resolution", "32"),
    ),
    (ROOT / "generate/stationary_bubble/VOF-HF.sh", ("--resolution", "32")),
    (
        ROOT / "generate/oscillating_droplet/VOF-HF.sh",
        ("--resolution", "32"),
    ),
]


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash", str(script), *args, "--formal", "--dry-run", "--output",
            str(ROOT / f"tem/dry_run_contract/tests/{script.parent.name}_{script.stem}"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("imax", [0, 5, 10, 15, 20])
def test_capwave_accepts_imax_boundaries(script: Path, imax: int) -> None:
    assert run(script, "--imax", str(imax), "--resolution", "64").returncode == 0


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("imax", [-1, 6, 9, 11, 21])
def test_capwave_rejects_outside_imax_contract(script: Path, imax: int) -> None:
    completed = run(script, "--imax", str(imax), "--resolution", "64")
    assert completed.returncode == 2
    assert "must be one of" in completed.stderr


@pytest.mark.parametrize("script", STATIONARY)
@pytest.mark.parametrize("resolution", [32, 64, 128, 256])
def test_stationary_accepts_only_retained_resolutions(script: Path, resolution: int) -> None:
    assert run(script, "--imax", "0", "--resolution", str(resolution)).returncode == 0


@pytest.mark.parametrize("script", STATIONARY)
def test_stationary_rejects_n512(script: Path) -> None:
    completed = run(script, "--imax", "0", "--resolution", "512")
    assert completed.returncode == 2
    assert "stationary N512 is outside the formal matrix" in completed.stderr


@pytest.mark.parametrize("script", STATIONARY)
def test_stationary_formal_plan_is_fixed_to_tau2_and_default_role(script: Path) -> None:
    completed = run(script, "--imax", "0", "--resolution", "64")
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["tau_max"] == 2.0
    assert plan["experiment_role"] == "default"
    assert "-DMETHOD_NN=" in plan["plan"]["commands"]["compile"]["display"]


def test_stationary_source_records_tau1_and_terminal_dual_curvature_metrics() -> None:
    source = (
        ROOT / "generate/stationary_bubble/src/stationary-clsvof.c"
    ).read_text(encoding="utf-8")
    assert 'stationary_write_milestone ("tau_1", 1., i)' in source
    assert '"terminal", stationary_stop_tau, stationary_stop_iteration' in source
    assert "official_style_ekmax" in source
    assert "active_provider_ekmax" in source
    assert "kappa_offset_provider_diagnostic (point, d)" in source


@pytest.mark.parametrize(
    "case,extra",
    [
        ("capwave", ("--resolution", "64")),
        ("rising_bubble", ("--case", "1", "--resolution", "64")),
        ("stationary_bubble", ("--resolution", "64")),
    ],
)
def test_matched_shell_runners_share_dimension_check_policy(
    case: str, extra: tuple[str, ...]
) -> None:
    commands = []
    for method in ("CLSVOF", "NN"):
        imax = "0" if case == "stationary_bubble" else "3"
        completed = run(ROOT / f"generate/{case}/{method}.sh", *extra, "--imax", imax)
        assert completed.returncode == 0, completed.stderr
        plan = json.loads(completed.stdout)
        commands.append(plan["plan"]["commands"]["compile"]["argv"])
    assert all("-disable-dimensions" in command for command in commands)


@pytest.mark.parametrize(
    "script,extra",
    [
        (ROOT / "generate/capwave/CLSVOF.sh", ()),
        (ROOT / "generate/capwave/NN.sh", ()),
        (ROOT / "generate/rising_bubble/CLSVOF.sh", ("--case", "1")),
        (ROOT / "generate/rising_bubble/NN.sh", ("--case", "1")),
        (ROOT / "generate/rising_bubble/CLSVOF.sh", ("--case", "2")),
        (ROOT / "generate/rising_bubble/NN.sh", ("--case", "2")),
        (ROOT / "generate/stationary_bubble/CLSVOF.sh", ()),
        (ROOT / "generate/stationary_bubble/NN.sh", ()),
        (ROOT / "generate/oscillating_droplet/CLSVOF.sh", ()),
        (ROOT / "generate/oscillating_droplet/NN.sh", ()),
    ],
)
def test_every_generated_case_branch_accepts_n32(
    script: Path, extra: tuple[str, ...]
) -> None:
    imax = "0" if script.parent.name == "stationary_bubble" else "3"
    completed = run(script, *extra, "--imax", imax, "--resolution", "32")
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["resolution"] == 32
    if plan["method"] == "NN":
        assert plan["model"] == "baseline_32_hgradient"


@pytest.mark.parametrize("script", STATIONARY)
@pytest.mark.parametrize("purpose", ["--smoke", "--formal"])
def test_stationary_rejects_nonzero_imax_for_every_purpose(
    script: Path, purpose: str
) -> None:
    completed = subprocess.run(
        [
            "bash", str(script), purpose, "--dry-run", "--imax", "3",
            "--resolution", "64", "--output",
            str(ROOT / f"tem/dry_run_contract/tests/{script.stem}_stationary"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 2
    assert "frozen to --imax 0" in completed.stderr


def test_direct_formal_compile_only_remains_forbidden() -> None:
    completed = run(
        ROOT / "generate/capwave/CLSVOF.sh",
        "--imax",
        "3",
        "--resolution",
        "32",
        "--compile-only",
    )
    assert completed.returncode == 2
    assert "formal cannot be combined" in completed.stderr


def test_campaign_can_plan_the_internal_formal_build_stage() -> None:
    environment = os.environ.copy()
    environment["CFD_CAMPAIGN_BUILD"] = "1"
    completed = subprocess.run(
        [
            "bash",
            str(ROOT / "generate/capwave/CLSVOF.sh"),
            "--formal",
            "--dry-run",
            "--compile-only",
            "--imax",
            "3",
            "--resolution",
            "32",
            "--threads",
            "4",
            "--output",
            str(ROOT / "tem/dry_run_contract/tests/internal_build"),
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["plan"]["parameters"]["compile_only"] == 1
    assert plan["plan"]["commands"]["run"]["argv"] == []


def test_precompiled_binary_is_campaign_internal_only(tmp_path: Path) -> None:
    executable = tmp_path / "solver"
    executable.write_bytes(b"not a reviewed campaign build")
    command = [
        "bash",
        str(ROOT / "generate/capwave/CLSVOF.sh"),
        "--formal",
        "--dry-run",
        "--imax",
        "3",
        "--resolution",
        "32",
        "--threads",
        "4",
        "--precompiled",
        str(executable),
        "--output",
        str(tmp_path / "row"),
    ]
    rejected = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True
    )
    assert rejected.returncode == 2
    assert "verified campaign scheduler" in rejected.stderr

    environment = os.environ.copy()
    environment["CFD_CAMPAIGN_PRECOMPILED"] = "1"
    accepted = subprocess.run(
        command, cwd=ROOT, env=environment, text=True, capture_output=True
    )
    assert accepted.returncode == 0, accepted.stderr
    plan = json.loads(accepted.stdout)
    assert plan["plan"]["parameters"]["compile_reused"] is True
    assert plan["plan"]["sources"]["precompiled_executable"]["sha256"]


@pytest.mark.parametrize("script,extra", OFFICIAL)
def test_vof_hf_plans_are_independent_official_references(
    script: Path, extra: tuple[str, ...]
) -> None:
    completed = subprocess.run(
        [
            "bash",
            str(script),
            *extra,
            "--formal",
            "--dry-run",
            "--output",
            str(ROOT / f"tem/dry_run_contract/tests/{script.parent.name}_VOF-HF"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["method"] == "VOF-HF"
    assert plan["experiment_role"] == "official_reference"
    assert plan["grid_role"] in {"stock_native", "stock_compatible_extension"}


def test_oscillating_vof_hf_selects_only_standard_solver_variant() -> None:
    completed = run(
        ROOT / "generate/oscillating_droplet/VOF-HF.sh", "--resolution", "32"
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["solver_variant"] == "Standard"
    assert plan["resolution"] == 32
    assert plan["grid_role"] == "stock_native"
    assert plan["plan"]["parameters"]["solver_variant"] == "Standard"
    serialized = json.dumps(plan).lower()
    assert "momentum" not in serialized
    assert "compressible" not in serialized
    assert set(plan["plan"]["sources"]) == {
        "field_snapshots",
        "official_ref",
        "qcc",
        "stock_case",
        "vof_hf_wrapper",
    }
    compile_argv = plan["plan"]["commands"]["compile"]["argv"]
    assert "-DSINGLE_LEVEL=5" in compile_argv


@pytest.mark.parametrize(
    "resolution,role",
    [(32, "stock_native"), (128, "stock_native"),
     (256, "stock_compatible_extension"), (512, "stock_compatible_extension")],
)
def test_oscillating_vof_hf_matches_campaign_grids(
    resolution: int, role: str
) -> None:
    completed = run(
        ROOT / "generate/oscillating_droplet/VOF-HF.sh",
        "--resolution",
        str(resolution),
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["resolution"] == resolution
    assert plan["grid_role"] == role
