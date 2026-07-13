#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.lib.integrity import (  # noqa: E402
    atomic_json,
    sha256_file,
    validate_completed_result,
)
from hpc.lib.matrix import formal_rows, result_relative_path  # noqa: E402
from hpc.lib.scheduler import load_policy, phase_rows  # noqa: E402


def overlay_provenance(result_path: Path) -> dict[str, object]:
    matches = list(result_path.rglob("redistance_overlay.json"))
    if len(matches) != 1:
        raise ValueError(
            f"expected one redistance_overlay.json in {result_path}, got {len(matches)}"
        )
    return json.loads(matches[0].read_text(encoding="utf-8"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument(
        "--results-root", type=Path, default=ROOT / "hpc/results"
    )
    parser.add_argument("--phase", choices=["n64", "remaining", "all"], default="all")
    parser.add_argument(
        "--policy", type=Path, default=ROOT / "hpc/config/thread_policy.json"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result_root = args.results_root / args.matrix_id
    selected = phase_rows(formal_rows(), args.phase)
    _, policy_hash = load_policy(args.policy)
    records = []
    manifests: dict[str, dict[str, object]] = {}
    for row in selected:
        path = result_root / result_relative_path(row)
        valid, reason = validate_completed_result(
            path, row, args.matrix_id, policy_hash
        )
        records.append(
            {
                "row_id": row.row_id,
                "benchmark": row.benchmark,
                "method": row.method,
                "resolution": row.resolution,
                "imax": row.imax,
                "state": "completed" if valid else "invalid",
                "reason": reason,
                "path": str(path.relative_to(result_root)),
            }
        )
        if valid:
            manifests[row.row_id] = json.loads(
                (path / "manifest.json").read_text(encoding="utf-8")
            )

    pair_failures: list[str] = []
    if args.phase == "all":
        lock = json.loads(
            (ROOT / "hpc/config/provenance.lock.json").read_text(encoding="utf-8")
        )["files"]
        rows_by_key = {
            (row.benchmark, row.resolution, row.imax, row.method): row
            for row in selected
        }
        for benchmark, resolution, imax, _ in sorted(rows_by_key):
            if _ != "clsvof_native":
                continue
            native = rows_by_key[(benchmark, resolution, imax, "clsvof_native")]
            nn = rows_by_key[
                (benchmark, resolution, imax, "clsvof_nn_cell_offset")
            ]
            if native.row_id not in manifests or nn.row_id not in manifests:
                continue
            native_path = result_root / result_relative_path(native)
            nn_path = result_root / result_relative_path(nn)
            try:
                native_overlay = overlay_provenance(native_path)
                nn_overlay = overlay_provenance(nn_path)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                pair_failures.append(str(error))
                continue
            if native_overlay.get("generated_sha256") != nn_overlay.get(
                "generated_sha256"
            ):
                pair_failures.append(
                    f"paired redistance header mismatch: {native.row_id} vs {nn.row_id}"
                )
            generator = manifests[nn.row_id].get("generator_manifest", {})
            artifacts = generator.get("artifacts", {})  # type: ignore[union-attr]
            expected_header = lock[
                "cases/_shared/nn_cell_curvature/src/clsvof_nn_cell_curvature.h"
            ]
            expected_stats = lock[
                "cases/_shared/nn_cell_curvature/src/kappa_offset_stats.h"
            ]
            expected_weights = lock[
                f"dataset/model/c_exports/baseline_{resolution}_hgradient/nn_weights.h"
            ]
            for field, expected in (
                ("cell_curvature_sha256", expected_header),
                ("stats_header_sha256", expected_stats),
                ("weights_sha256", expected_weights),
            ):
                if artifacts.get(field) != expected:  # type: ignore[union-attr]
                    pair_failures.append(f"{nn.row_id} has wrong {field}")

    status_path = result_root / f"matrix_status_{args.phase}.csv"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with status_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    failures = [record for record in records if record["state"] != "completed"]
    manifest = {
        "schema_version": 1,
        "matrix_id": args.matrix_id,
        "phase": args.phase,
        "expected_rows": len(selected),
        "completed_rows": len(records) - len(failures),
        "invalid_rows": len(failures),
        "pair_failure_count": len(pair_failures),
        "pair_failures": pair_failures,
        "policy_sha256": policy_hash,
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "rows": records,
    }
    atomic_json(result_root / f"matrix_manifest_{args.phase}.json", manifest)

    timing_path = result_root / f"matrix_timing_{args.phase}.csv"
    with timing_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["row_id", "elapsed_seconds", "threads", "cpu_list"],
        )
        writer.writeheader()
        for row in selected:
            payload = manifests.get(row.row_id, {})
            execution = payload.get("execution", {}) if payload else {}
            writer.writerow(
                {
                    "row_id": row.row_id,
                    "elapsed_seconds": execution.get("elapsed_seconds", ""),  # type: ignore[union-attr]
                    "threads": execution.get("threads", ""),  # type: ignore[union-attr]
                    "cpu_list": json.dumps(execution.get("cpu_list", [])),  # type: ignore[union-attr]
                }
            )
    failure_path = result_root / f"failure_ledger_{args.phase}.csv"
    with failure_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["row_id", "reason"])
        writer.writeheader()
        for record in failures:
            writer.writerow({"row_id": record["row_id"], "reason": record["reason"]})
        for reason in pair_failures:
            writer.writerow({"row_id": "PAIR_GATE", "reason": reason})

    if args.phase == "all":
        shutil_aliases = {
            "matrix_status_all.csv": "matrix_status.csv",
            "matrix_manifest_all.json": "matrix_manifest.json",
            "matrix_timing_all.csv": "matrix_timing.csv",
            "failure_ledger_all.csv": "failure_ledger.csv",
        }
        for source, destination in shutil_aliases.items():
            (result_root / destination).write_bytes((result_root / source).read_bytes())

    if args.phase == "all" and not failures and not pair_failures:
        checksums = []
        for path in sorted(result_root.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS":
                checksums.append(
                    f"{sha256_file(path)}  {path.relative_to(result_root).as_posix()}"
                )
        (result_root / "SHA256SUMS").write_text(
            "\n".join(checksums) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "phase": args.phase,
                "expected_rows": len(selected),
                "completed_rows": len(records) - len(failures),
                "invalid_rows": len(failures),
                "pair_failure_count": len(pair_failures),
            }
        )
    )
    return 1 if failures or pair_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
