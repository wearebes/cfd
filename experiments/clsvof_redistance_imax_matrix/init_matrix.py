#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=HERE / "config/matrix.json")
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    result_root = HERE / "results" / args.matrix_id
    result_root.mkdir(parents=True, exist_ok=False)

    source_paths = [
        ROOT / "basilisk/src/test/capwave-clsvof.c",
        ROOT / "basilisk/src/test/rising.c",
        ROOT / "basilisk/src/test/prosperetti.h",
        ROOT / "basilisk/src/two-phase-clsvof.h",
        ROOT / "basilisk/src/redistance.h",
        ROOT / "basilisk/src/integral.h",
        ROOT / "experiments/clsvof_kappa_offset_conversion/include/clsvof_nn_cell_curvature.h",
        ROOT / "experiments/clsvof_kappa_offset_conversion/make_overlay_integral.py",
        ROOT / "experiments/clsvof_kappa_offset_conversion/SOLVER_K_SEMANTICS.md",
        ROOT / "tools/clsvof_model/include/clsvof_mlp_infer.h",
        HERE / "include/redistance_matrix_metrics.h",
    ]
    source_paths.extend(
        ROOT / f"dataset/model/c_exports/baseline_{n}_hgradient/nn_weights.h"
        for n in (64, 128, 256, 512)
    )
    hashes = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in source_paths
    }
    git_status = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True
    ).stdout.splitlines()

    manifest = {
        "schema_version": 1,
        "matrix_id": args.matrix_id,
        "matrix_name": matrix["matrix_name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_scope_confirmed": True,
        "expected_rows": len(matrix["rows"]),
        "candidate_reuse_rows": sum(
            row["planning_status"] == "candidate_reuse" for row in matrix["rows"]
        ),
        "planned_run_rows": sum(
            row["planning_status"] == "planned_run" for row in matrix["rows"]
        ),
        "scheduler": {
            "user_approved_ceiling": 4,
            "initial_max_jobs_without_background_qos": 2,
            "background_qos_available": False,
            "reason": "managed environment rejected taskpolicy/nice; use adaptive plain-priority concurrency",
        },
        "platform": {
            "machine": platform.machine(),
            "system": platform.system(),
            "cpu_cores": 8,
            "memory_gb": 24,
        },
        "source_sha256": hashes,
        "dirty_worktree_baseline": git_status,
        "matrix_config_sha256": sha256_file(args.matrix),
    }
    (result_root / "matrix_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    with (result_root / "matrix_status.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["row_id", "benchmark", "method", "N", "imax", "planning_status", "execution_state"]
        )
        for row in matrix["rows"]:
            writer.writerow(
                [
                    row["row_id"],
                    row["benchmark"],
                    row["method"],
                    row["N"],
                    row["imax"],
                    row["planning_status"],
                    "reuse_pending" if row["planning_status"] == "candidate_reuse" else "planned",
                ]
            )
    print(result_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
