#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result_root = HERE / "results" / args.matrix_id
    manifest = json.loads((result_root / "matrix_manifest.json").read_text(encoding="utf-8"))
    baseline = sorted(
        line
        for line in manifest.get("dirty_worktree_baseline", [])
        if line[3:].startswith("basilisk/src/")
    )
    completed = subprocess.run(
        ["git", "status", "--short", "--", "basilisk/src"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    current = sorted(line for line in completed.stdout.splitlines() if line)
    payload = {
        "schema_version": 1,
        "matrix_id": args.matrix_id,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "scope": "basilisk/src",
        "baseline": baseline,
        "current": current,
        "added_since_baseline": sorted(set(current) - set(baseline)),
        "removed_since_baseline": sorted(set(baseline) - set(current)),
        "passed": current == baseline,
    }
    temporary = result_root / "workspace_boundary_audit.json.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, result_root / "workspace_boundary_audit.json")
    print(json.dumps({"passed": payload["passed"], "entries": len(current)}))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
