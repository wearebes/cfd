from __future__ import annotations

import json
import subprocess
from pathlib import Path

from hpc.lib.integrity import atomic_json, expected_identity, inventory
from hpc.lib.matrix import formal_rows, result_relative_path
from hpc.lib.scheduler import load_policy


ROOT = Path(__file__).resolve().parents[2]


def test_full_synthetic_matrix_passes_pair_and_integrity_gates(tmp_path: Path) -> None:
    matrix_id = "synthetic180"
    results_root = tmp_path / "results"
    policy_path = ROOT / "hpc/config/thread_policy.json"
    _, policy_hash = load_policy(policy_path)
    lock = json.loads(
        (ROOT / "hpc/config/provenance.lock.json").read_text(encoding="utf-8")
    )["files"]

    for row in formal_rows():
        path = results_root / matrix_id / result_relative_path(row)
        path.mkdir(parents=True)
        generated_hash = f"generated-{row.benchmark}-{row.resolution}-{row.imax}"
        (path / "redistance_overlay.json").write_text(
            json.dumps({"generated_sha256": generated_hash}) + "\n",
            encoding="utf-8",
        )
        (path / "compile.stderr").write_text("", encoding="utf-8")
        (path / "physical.out").write_text("0 0\n1 1\n", encoding="utf-8")
        artifacts = {
            "cell_curvature_sha256": None,
            "stats_header_sha256": None,
            "weights_sha256": None,
        }
        if row.method == "clsvof_nn_cell_offset":
            artifacts = {
                "cell_curvature_sha256": lock[
                    "cases/_shared/nn_cell_curvature/src/clsvof_nn_cell_curvature.h"
                ],
                "stats_header_sha256": lock[
                    "cases/_shared/nn_cell_curvature/src/kappa_offset_stats.h"
                ],
                "weights_sha256": lock[
                    f"dataset/model/c_exports/baseline_{row.resolution}_hgradient/nn_weights.h"
                ],
            }
        atomic_json(
            path / "manifest.json",
            {
                "schema_version": 1,
                "formal_identity": expected_identity(
                    row, matrix_id, policy_hash
                ),
                "execution": {
                    "elapsed_seconds": 1.0,
                    "threads": 1,
                    "cpu_list": [0],
                },
                "generator_manifest": {"artifacts": artifacts},
                "outputs": inventory(path),
            },
        )

    completed = subprocess.run(
        [
            "python3",
            str(ROOT / "hpc/verify_matrix.py"),
            "--matrix-id",
            matrix_id,
            "--results-root",
            str(results_root),
            "--phase",
            "all",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    root = results_root / matrix_id
    manifest = json.loads((root / "matrix_manifest.json").read_text())
    assert manifest["expected_rows"] == manifest["completed_rows"] == 180
    assert manifest["invalid_rows"] == manifest["pair_failure_count"] == 0
    assert (root / "matrix_status.csv").is_file()
    assert (root / "matrix_timing.csv").is_file()
    assert (root / "failure_ledger.csv").is_file()
    assert (root / "SHA256SUMS").is_file()
