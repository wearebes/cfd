#!/usr/bin/env python3
"""Generate or verify the formal runner provenance lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "hpc/config/provenance.lock.json"


LOCKED_FILES = (
    "basilisk/src/test/capwave.c",
    "basilisk/src/test/capwave-clsvof.c",
    "basilisk/src/test/rising.c",
    "basilisk/src/test/spurious.c",
    "basilisk/src/two-phase-clsvof.h",
    "basilisk/src/integral.h",
    "basilisk/src/redistance.h",
    "generate/_shared/run_manifest.py",
    "generate/_shared/build_scientific_artifacts.py",
    "generate/_shared/make_checkpoint_overlay.py",
    "generate/_shared/checkpoint_restore_probe.c",
    "generate/_shared/nn_runtime/src/clsvof_nn_cell_curvature.h",
    "generate/_shared/nn_runtime/src/kappa_offset_stats.h",
    "generate/_shared/nn_runtime/src/make_overlay_integral.py",
    "generate/_shared/nn_runtime/src/clsvof_mlp_infer.h",
    "generate/_shared/nondefault_redistance/src/make_redistance_overlay.py",
    "generate/capwave/src/make_single_resolution_case.py",
    "generate/capwave/src/official_single_wrapper.c",
    "generate/capwave/official.sh",
    "generate/capwave/clsvof.sh",
    "generate/capwave/nn.sh",
    "generate/rising_bubble/src/make_metrics_overlay.py",
    "generate/rising_bubble/official.sh",
    "generate/rising_bubble/clsvof.sh",
    "generate/rising_bubble/nn.sh",
    "generate/stationary_bubble/src/stationary-clsvof.c",
    "generate/stationary_bubble/src/summarize_smoke.py",
    "generate/stationary_bubble/src/official_single_wrapper.c",
    "generate/stationary_bubble/official.sh",
    "generate/stationary_bubble/clsvof.sh",
    "generate/stationary_bubble/nn.sh",
    "generate/oscillating_droplet/clsvof_extension/oscillation-clsvof.c",
    "generate/oscillating_droplet/official.sh",
    "generate/oscillating_droplet/official/build_official_report.py",
    "generate/oscillating_droplet/nn/src/oscillation-nn-single-level.c",
    "generate/oscillating_droplet/nn/src/oscillation_raw27_adapter.h",
    "generate/oscillating_droplet/nn/generate/make_runtime_redistance_overlay.py",
    "generate/oscillating_droplet/nn/generate/run_row.py",
    "hpc/lib/dataset_publish.py",
    "dataset/model/c_exports/baseline_64_hgradient/nn_weights.h",
    "dataset/model/c_exports/baseline_128_hgradient/nn_weights.h",
    "dataset/model/c_exports/baseline_256_hgradient/nn_weights.h",
    "dataset/model/c_exports/baseline_512_hgradient/nn_weights.h",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_files() -> dict[str, str]:
    missing = [relative for relative in LOCKED_FILES if not (ROOT / relative).is_file()]
    if missing:
        raise SystemExit("missing provenance inputs: " + ", ".join(missing))
    formal_exports = sorted((ROOT / "dataset/model/c_exports").glob("baseline_*_hgradient"))
    expected_names = [f"baseline_{resolution}_hgradient" for resolution in (64, 128, 256, 512)]
    actual_names = sorted(path.name for path in formal_exports if path.is_dir())
    if actual_names != sorted(expected_names):
        raise SystemExit(
            f"formal c_exports scope mismatch: expected={expected_names}, actual={actual_names}"
        )
    return {relative: sha256(ROOT / relative) for relative in LOCKED_FILES}


def write(payload: object) -> None:
    temporary = LOCK.with_name(f".{LOCK.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, LOCK)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = expected_files()
    if args.check:
        payload = json.loads(LOCK.read_text(encoding="utf-8"))
        if payload.get("files") != files:
            raise SystemExit("provenance lock drift")
        return 0
    write({"schema_version": 2, "generated_date": date.today().isoformat(), "files": files})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
