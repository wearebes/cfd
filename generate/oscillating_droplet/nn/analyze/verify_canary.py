#!/usr/bin/env python3
"""Create durable evidence for probe-only and active N64 canary gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("canary_root", type=Path)
    parser.add_argument("formal_root", type=Path)
    args = parser.parse_args()
    canary = args.canary_root.resolve()
    formal = args.formal_root.resolve()
    probe = canary / "level_6_probe"
    active = canary / "level_6_active"
    clsvof = canary / "level_6_clsvof"

    probe_manifest = json.loads((probe / "manifest.json").read_text(encoding="utf-8"))
    active_manifest = json.loads((active / "manifest.json").read_text(encoding="utf-8"))
    samples: list[list[float]] = []
    for line in (probe / "runtime.stderr.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("KAPPA_OFFSET_PROBE "):
            samples.append([float(value) for value in line.split()[1:]])
    # t,x,y,s,grad,q_model,q_solver,q_cell,q_native,denominator,clamped,guard
    checks = {
        "probe_status_completed": probe_manifest["status"] == "completed",
        "active_status_completed": active_manifest["status"] == "completed",
        "probe_clsvof_kinetic_energy_byte_exact":
            (probe / "k-6").read_bytes() == (clsvof / "k-6").read_bytes(),
        "probe_sample_count_512": len(samples) == 512,
        "probe_all_finite": bool(samples) and all(math.isfinite(value) for row in samples for value in row),
        "model_q_positive": bool(samples) and all(row[5] > 0 for row in samples),
        "solver_q_negative": bool(samples) and all(row[6] < 0 for row in samples),
        "solver_q_native_same_sign": bool(samples) and all(row[6] * row[8] > 0 for row in samples),
        "cell_q_native_same_sign": bool(samples) and all(row[7] * row[8] > 0 for row in samples),
        "probe_guard_zero": bool(samples) and all(row[11] == 0 for row in samples),
        "probe_clamp_zero": bool(samples) and all(row[10] == 0 for row in samples),
        "active_guard_zero": active_manifest["provider_stats"]["denominator_guard_hits"] == 0,
        "active_clamp_zero": active_manifest["provider_stats"]["clamp_hits"] == 0,
    }
    payload = {
        "canary_root": str(canary),
        "all_passed": all(checks.values()),
        "checks": checks,
        "probe_stats": probe_manifest["provider_stats"],
        "active_stats": active_manifest["provider_stats"],
        "artifact_hashes": {
            "probe_manifest": sha256(probe / "manifest.json"),
            "active_manifest": sha256(active / "manifest.json"),
            "clsvof_manifest": sha256(clsvof / "manifest.json"),
            "probe_kinetic_energy": sha256(probe / "k-6"),
        },
    }
    (formal / "canary_verification.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"all_passed": payload["all_passed"]}, sort_keys=True))
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
