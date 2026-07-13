#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_row import DEFAULT_MATRIX, HERE, ROOT, provenance_inputs, result_dir


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def audit_row(
    result_root: Path,
    row: dict[str, Any],
    matrix_hashes: dict[str, str],
) -> dict[str, Any] | None:
    destination = result_dir(result_root, row)
    status_path = destination / "status.json"
    manifest_path = destination / "manifest.json"
    if not status_path.is_file():
        return None
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("state") != "completed" or not manifest_path.is_file():
        return None

    inputs = provenance_inputs(row)
    source_case = (
        ROOT / "basilisk/src/test/capwave-clsvof.c"
        if row["benchmark"] == "capwave"
        else ROOT / "basilisk/src/test/rising.c"
    )
    inputs["source_case"] = source_case
    audited: dict[str, Any] = {}
    mismatches: list[str] = []
    for name, path in inputs.items():
        if not path.is_file():
            raise RuntimeError(f"missing provenance input for {row['row_id']}: {path}")
        rel = relative(path)
        actual = sha256_file(path)
        expected = matrix_hashes.get(rel)
        matches = actual == expected if expected is not None else None
        if matches is False:
            mismatches.append(rel)
        audited[name] = {
            "path": rel,
            "sha256": actual,
            "matrix_baseline_sha256": expected,
            "matches_matrix_baseline": matches,
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    embedded = manifest.get("files", {})
    payload = {
        "schema_version": 1,
        "matrix_id": result_root.name,
        "row_id": row["row_id"],
        "audited_at": utc_now(),
        "manifest_sha256_before_audit": sha256_file(manifest_path),
        "command": manifest.get("command"),
        "inputs": audited,
        "manifest_embedded_input_keys": sorted(embedded),
        "baseline_mismatches": mismatches,
        "passed": not mismatches,
        "note": (
            "Companion audit backfills per-row provider/features/weights provenance for "
            "rows whose immutable runtime manifest predates the expanded file list."
        ),
    }
    atomic_json(destination / "provenance_audit.json", payload)
    if mismatches:
        raise RuntimeError(f"matrix baseline mismatch in {row['row_id']}: {mismatches}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    result_root = HERE / "results" / args.matrix_id
    matrix_manifest = json.loads((result_root / "matrix_manifest.json").read_text(encoding="utf-8"))
    hashes = matrix_manifest["source_sha256"]
    audited = 0
    for row in matrix["rows"]:
        if audit_row(result_root, row, hashes) is not None:
            audited += 1
    mlp_path = ROOT / "tools/clsvof_model/include/clsvof_mlp_infer.h"
    amendment = {
        "schema_version": 1,
        "matrix_id": args.matrix_id,
        "created_at": utc_now(),
        "audited_completed_rows": audited,
        "additional_source_snapshot": {
            relative(mlp_path): sha256_file(mlp_path),
        },
        "reason": (
            "The central inference header was not listed in the initial matrix manifest; "
            "this append-only companion records it without rewriting the original manifest."
        ),
    }
    atomic_json(result_root / "provenance_amendment.json", amendment)
    print(json.dumps({"audited_completed_rows": audited}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
