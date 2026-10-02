#!/usr/bin/env python3
"""Validate one grid-matched Standard VOF-HF oscillation row.

Writes the strict stock diff (fit_summary_vs_ref.diff) and prints the
verification record to stdout. Row finalization embeds that record in
manifest.json."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--resolution", type=int, required=True)
    parser.add_argument("--level", type=int, required=True)
    parser.add_argument("--cells-per-diameter", required=True)
    parser.add_argument(
        "--grid-role",
        choices=("stock_native", "stock_compatible_extension", "uniform_matched"),
        required=True,
    )
    parser.add_argument("--grid-strategy", choices=("adaptive", "uniform"), required=True)
    parser.add_argument(
        "--experiment-role",
        choices=("official_reference", "matched_reference"),
        required=True,
    )
    parser.add_argument("--compile-exit-status", type=int, required=True)
    parser.add_argument("--run-exit-status", type=int, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--ended-at", required=True)
    parser.add_argument("--wall-seconds", type=int, required=True)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    if args.grid_strategy == "uniform":
        if args.grid_role != "uniform_matched" or args.experiment_role != "matched_reference":
            parser.error("uniform VOF-HF requires uniform_matched/matched_reference")
    elif args.grid_role == "uniform_matched" or args.experiment_role != "official_reference":
        parser.error("adaptive VOF-HF requires a stock grid role and official_reference")

    dataset = args.dataset.resolve()
    log_path = dataset / "fit_summary.dat"
    required = [
        dataset / "timeseries.dat",
        dataset / "fit_curve.dat",
        dataset / "fit.log",
        dataset / "error.dat",
        dataset / "laplace.dat",
        dataset / "fit_summary.dat",
        dataset / "solver.stdout.txt",
        dataset / "termination.csv",
    ]
    complete = (
        args.compile_exit_status == 0
        and args.run_exit_status == 0
        and all(path.is_file() and path.stat().st_size > 0 for path in required)
    )

    actual = lines(log_path) if log_path.exists() else []
    reference = lines(dataset / "source_snapshot/oscillation.ref")
    expected = [
        line for line in reference
        if line.startswith(f"fit {args.cells_per_diameter} ")
    ]
    if args.grid_role == "stock_native" and len(expected) != 1:
        raise ValueError(
            f"missing unique stock reference at cells/D={args.cells_per_diameter}"
        )
    if args.grid_role in {"stock_compatible_extension", "uniform_matched"} and expected:
        if args.grid_role == "uniform_matched":
            expected = []
        else:
            raise ValueError("extension grid unexpectedly has a stock reference row")

    diff_lines = (
        list(
            difflib.unified_diff(
                expected,
                actual,
                fromfile="source_snapshot/oscillation.ref:selected-row",
                tofile="fit_summary.dat",
                lineterm="",
            )
        )
        if expected
        else []
    )
    (dataset / "fit_summary_vs_ref.diff").write_text(
        "\n".join(diff_lines) + ("\n" if diff_lines else ""), encoding="utf-8"
    )

    strict_match: bool | None = complete and not diff_lines if expected else None
    if not complete:
        status = "incomplete"
    elif args.grid_role == "stock_compatible_extension":
        status = "stock_compatible_extension"
    elif args.grid_role == "uniform_matched":
        status = "uniform_matched_complete"
    elif strict_match:
        status = "official_pass"
    else:
        status = "official_regression_mismatch"

    verification = {
        "schema_version": 3,
        "case": "basilisk_elliptical_droplet_oscillation",
        "method": "VOF-HF",
        "experiment_role": args.experiment_role,
        "solver_variant": "Standard",
        "excluded_solver_variants": ["Momentum", "Compressible"],
        "resolution": args.resolution,
        "level": args.level,
        "cells_per_diameter": float(args.cells_per_diameter),
        "grid_role": args.grid_role,
        "grid_strategy": args.grid_strategy,
        "source": "basilisk/src/test/oscillation.c",
        "grid_selection": (
            "qcc -grid=multigrid at one requested N"
            if args.grid_strategy == "uniform"
            else "VOF-HF_single_wrapper.c selects one adaptive stock loop level"
        ),
        "compile_exit_status": args.compile_exit_status,
        "run_exit_status": args.run_exit_status,
        "started_at": args.started_at,
        "ended_at": args.ended_at,
        "wall_seconds": args.wall_seconds,
        "status": status,
        "complete_artifacts": complete,
        "strict_log_ref_match": strict_match,
        "actual_log_sha256": sha256(log_path) if log_path.exists() else None,
        "official_ref_sha256": sha256(dataset / "source_snapshot/oscillation.ref"),
        "strict_diff_artifact": "fit_summary_vs_ref.diff",
    }
    if args.output_json:
        args.output_json.write_text(
            json.dumps(verification, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(verification, sort_keys=True))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
