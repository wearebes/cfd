#!/usr/bin/env python3
"""Audit row contracts, plot CSVs and field-checkpoint restoreability."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QCC = ROOT / "basilisk/src/qcc"
RESTORE_SOURCE = Path(__file__).with_name("checkpoint_restore_probe.c")


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def assert_plot_ready(path: Path) -> int:
    rows = csv_rows(path)
    if not rows:
        raise ValueError(f"empty plot CSV: {path}")
    for row in rows:
        for value in row.values():
            if value == "":
                continue
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"non-finite plot value in {path}: {value}")
    return len(rows)


def compile_restore_probe(directory: Path, *, tree: bool) -> Path:
    executable = directory / ("restore-tree" if tree else "restore-multigrid")
    local_source = directory / "checkpoint_restore_probe.c"
    if not local_source.exists():
        shutil.copyfile(RESTORE_SOURCE, local_source)
    command = [
        str(QCC),
        "-O2",
        f"-DCHECKPOINT_TREE={1 if tree else 0}",
        local_source.name,
        "-o",
        str(executable),
        "-lm",
    ]
    subprocess.run(command, cwd=directory, check=True, capture_output=True, text=True)
    return executable


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("smoke_root", type=Path)
    args = parser.parse_args()
    smoke_root = args.smoke_root.resolve()
    contracts = sorted(smoke_root.rglob("scientific_artifacts.json"))
    if not contracts:
        raise SystemExit(f"no scientific artifact contracts below {smoke_root}")

    audit_rows: list[dict[str, object]] = []
    restore_rows: list[dict[str, object]] = []
    metrics_long: list[dict[str, object]] = []
    checkpoints_long: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="cfd-restore-audit-") as temporary:
        temp = Path(temporary)
        probes = {
            False: compile_restore_probe(temp, tree=False),
            True: compile_restore_probe(temp, tree=True),
        }
        for contract_path in contracts:
            row_dir = contract_path.parent
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            if not contract.get("official_coverage_complete"):
                raise ValueError(f"official coverage failed: {row_dir}")
            if contract.get("missing_official_publish_names"):
                raise ValueError(f"missing official artifacts: {row_dir}")
            metrics = csv_rows(row_dir / "metrics.csv")
            if not metrics or not all(row.get("unit") and row.get("definition") for row in metrics):
                raise ValueError(f"incomplete metric registry: {row_dir}")
            plot_rows = assert_plot_ready(row_dir / "plot_data.csv")
            checkpoints = csv_rows(row_dir / "checkpoint_index.csv")
            if not checkpoints:
                raise ValueError(f"empty checkpoint index: {row_dir}")
            written = [row for row in checkpoints if row["status"] == "written"]
            missing = [row for row in checkpoints if row["status"] == "not_reached"]
            unexpected = [
                row for row in checkpoints if row["status"] not in {"written", "not_reached"}
            ]
            if unexpected:
                raise ValueError(f"invalid checkpoint status: {row_dir}")
            identity = {
                "row": row_dir.relative_to(smoke_root).as_posix(),
                "case": contract["case"],
                "benchmark": contract["benchmark"],
                "method": contract["method"],
                "resolution": contract["resolution"],
                "imax": contract["imax"],
                "model_id": contract.get("model_id") or "",
                "model_resolution": contract.get("model_resolution") or "",
            }
            metrics_long.extend({**identity, **row} for row in metrics)
            checkpoints_long.extend({**identity, **row} for row in checkpoints)
            is_tree = contract["case"] == "oscillating_droplet"
            for checkpoint in written:
                dump_path = row_dir / checkpoint["dump_path"]
                if not dump_path.is_file() or dump_path.stat().st_size == 0:
                    raise ValueError(f"missing checkpoint dump: {dump_path}")
                completed = subprocess.run(
                    [str(probes[is_tree]), str(dump_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                values = completed.stdout.strip().split(",")
                if len(values) != 8:
                    raise ValueError(f"invalid restore probe output: {completed.stdout}")
                restore_rows.append(
                    {
                        "row": row_dir.relative_to(smoke_root).as_posix(),
                        "label": checkpoint["label"],
                        "grid": "quadtree" if is_tree else "multigrid",
                        "restored_time": values[0],
                        "restored_iteration": values[1],
                        "depth": values[2],
                        "leaf_cells": values[3],
                        "interface_cells": values[7],
                        "status": "PASS",
                    }
                )
            audit_rows.append(
                {
                    "row": row_dir.relative_to(smoke_root).as_posix(),
                    "case": contract["case"],
                    "benchmark": contract["benchmark"],
                    "method": contract["method"],
                    "resolution": contract["resolution"],
                    "imax": contract["imax"],
                    "official_artifacts": contract["official_artifact_count"],
                    "metrics": len(metrics),
                    "plot_rows": plot_rows,
                    "checkpoints_written": len(written),
                    "checkpoints_not_reached": len(missing),
                    "restore_checks": len(written),
                    "status": "PASS",
                }
            )

    write_csv(smoke_root / "smoke_audit.csv", audit_rows)
    write_csv(smoke_root / "checkpoint_restore_audit.csv", restore_rows)
    write_csv(smoke_root / "metrics_long.csv", metrics_long)
    write_csv(smoke_root / "checkpoint_index_long.csv", checkpoints_long)
    markdown = [
        "# Scientific artifact smoke audit",
        "",
        f"All {len(audit_rows)} rows passed official-coverage, plot-CSV and checkpoint-restore checks.",
        "",
        "| row | official | metrics | plot rows | dumps restored | not reached | status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in audit_rows:
        markdown.append(
            f"| {row['row']} | {row['official_artifacts']} | {row['metrics']} | "
            f"{row['plot_rows']} | {row['restore_checks']} | "
            f"{row['checkpoints_not_reached']} | {row['status']} |"
        )
    (smoke_root / "smoke_audit.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(audit_rows), "restores": len(restore_rows), "status": "PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
