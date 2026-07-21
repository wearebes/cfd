from __future__ import annotations

import json
import os

import pytest

from conftest import ROOT


REQUIRED = {
    "case_id", "method_id", "evidence_level", "level", "N", "cells_per_diameter",
    "model_name", "checkpoint_sha256", "weights_sha256", "export_manifest_sha256",
    "host_source_sha256", "two_phase_clsvof_sha256", "stock_integral_sha256",
    "generated_integral_sha256", "shared_provider_sha256", "oscillation_adapter_sha256",
    "feature_order", "raw27_order", "model_phi_sign", "solver_d_sign",
    "solver_to_model_sign", "model_output", "solver_output", "nn_provider",
    "denominator_guard", "clamp_factor", "redistance_imax", "compile_command",
    "started_at", "ended_at", "wall_seconds", "provider_stats",
}


def test_formal_manifests_when_result_root_is_given() -> None:
    result_root = os.environ.get("OSCILLATION_NN_RESULT_ROOT")
    if not result_root:
        pytest.skip("set OSCILLATION_NN_RESULT_ROOT after formal rows are generated")
    for level in (6, 7):
        for method in ("clsvof", "nn"):
            path = ROOT / result_root / f"level_{level}/{method}/manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            assert REQUIRED <= manifest.keys()
            assert manifest["status"] == "completed"
            if method.endswith("nn"):
                stats = manifest["provider_stats"]
                assert stats["evaluations"] > 0
                assert stats["clamp_hits"] == 0
                assert stats["denominator_guard_hits"] == 0
