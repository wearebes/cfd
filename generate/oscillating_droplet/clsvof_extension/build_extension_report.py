#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


METHODS = {
    "standard": ("Standard", "official"),
    "momentum": ("Momentum", "official"),
    "compressible": ("Compressible", "official"),
    "clsvof": ("CLSVOF", "nonofficial_extension"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def keyed(path: Path, prefix: str | None = None) -> dict[str, list[str]]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        if prefix is not None:
            if fields[0] != prefix:
                continue
            result[fields[1]] = fields[2:]
        else:
            result[fields[0]] = fields[1:]
    return result


def method_rows(directory: Path) -> list[dict[str, str]]:
    fits = keyed(directory / "log", "fit")
    errors = keyed(directory / "error")
    laplace = keyed(directory / "laplace")
    rows = []
    for cells in ("6.4", "12.8", "25.6", "51.2"):
        fit = fits[cells]
        signed_error = errors[cells][0]
        rows.append({
            "cells_per_diameter": cells,
            "a": fit[0],
            "b": fit[1],
            "c": fit[2],
            "frequency_rel_error": signed_error,
            "frequency_abs_error_percent": f"{abs(float(signed_error))*100.:.15g}",
            "equivalent_laplace": " ".join(laplace[cells][:-1]),
        })
    return rows


def power_fit(rows: list[dict[str, str]]) -> dict[str, float]:
    x = [math.log(float(row["cells_per_diameter"])) for row in rows]
    y = [math.log(float(row["frequency_abs_error_percent"])) for row in rows]
    xmean = sum(x)/len(x)
    ymean = sum(y)/len(y)
    exponent = sum((xi - xmean)*(yi - ymean) for xi, yi in zip(x, y))/sum(
        (xi - xmean)**2 for xi in x
    )
    intercept = ymean - exponent*xmean
    return {"coefficient": math.exp(intercept), "exponent": exponent}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--official", type=Path, required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--ended-at", required=True)
    parser.add_argument("--wall-seconds", type=int, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    dataset = args.dataset.resolve()
    official = args.official.resolve()
    clsvof = dataset / "clsvof"
    source = repo / "generate/oscillating_droplet/clsvof_extension/oscillation-clsvof.c"

    directories = {
        "standard": official / "standard",
        "momentum": official / "momentum",
        "compressible": official / "compressible",
        "clsvof": clsvof,
    }
    all_rows: list[dict[str, str]] = []
    by_method: dict[str, list[dict[str, str]]] = {}
    for method, directory in directories.items():
        rows = method_rows(directory)
        by_method[method] = rows
        title, evidence = METHODS[method]
        for row in rows:
            all_rows.append({"method": title, "evidence": evidence, **row})
    power_fits = {method: power_fit(rows) for method, rows in by_method.items()}

    columns = [
        "method", "evidence", "cells_per_diameter", "a", "b", "c",
        "frequency_rel_error", "frequency_abs_error_percent",
        "equivalent_laplace",
    ]
    with (dataset / "four_method_comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_rows)

    manifest = {
        "schema_version": 1,
        "case": "elliptical_droplet_oscillation",
        "status": "completed_nonofficial_extension",
        "method": "CLSVOF",
        "method_identity": "nonofficial_component_matched_extension",
        "official_clsvof_case_exists": False,
        "official_baselines_immutable": True,
        "levels": [4, 5, 6, 7],
        "grid_sizes": [16, 32, 64, 128],
        "cells_per_diameter": ["6.4", "12.8", "25.6", "51.2"],
        "command": args.command,
        "started_at": args.started_at,
        "ended_at": args.ended_at,
        "wall_seconds": args.wall_seconds,
        "source_sha256": sha256(source),
        "component_sha256": {
            "basilisk/src/two-phase-clsvof.h": sha256(
                repo / "basilisk/src/two-phase-clsvof.h"
            ),
            "basilisk/src/integral.h": sha256(repo / "basilisk/src/integral.h"),
        },
        "official_manifest_sha256": sha256(official / "manifest.json"),
        "frequency_error_power_fits_percent": power_fits,
        "artifacts_complete": all(
            (clsvof / name).is_file() and (clsvof / name).stat().st_size > 0
            for name in ["log", "error", "laplace", "out"]
            + [f"k-{level}" for level in range(4, 8)]
            + [f"fit-{level}" for level in range(4, 8)]
        ),
    }
    (dataset / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report = [
        "# CLSVOF extension of official elliptical-droplet oscillation",
        "",
        "This is a non-official extension. Basilisk provides no CLSVOF branch or `.ref` for this oscillation case.",
        "The three official baselines remain unchanged in `official_reproduction/`.",
        "",
        "The CLSVOF case keeps the official LEVEL 4--7 loop, kinetic-energy measurement,",
        "fit function, output precision, frequency error and equivalent-Laplace definitions.",
        "The method substitution is `two-phase-clsvof.h + integral.h`, with the initial",
        "shape supplied through the signed-distance field `d` and surface tension through `d.sigmaf`.",
        "",
        "## CLSVOF results",
        "",
        "| cells/D | a | b | c | signed frequency error (%) | equivalent Laplace |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in by_method["clsvof"]:
        report.append(
            f"| {row['cells_per_diameter']} | {row['a']} | {row['b']} | "
            f"{row['c']} | {float(row['frequency_rel_error'])*100.:.15g} | "
            f"{row['equivalent_laplace']} |"
        )
    finest = sorted(
        (
            float(rows[-1]["frequency_abs_error_percent"]),
            METHODS[method][0],
        )
        for method, rows in by_method.items()
    )
    clsvof_fit = power_fits["clsvof"]
    report += [
        "",
        "## Four-method frequency comparison",
        "",
        "The plot fits absolute frequency error (%) as `A*x^p`, where `x` is cells/D.",
        "",
        "| Method | A | p | Interpretation over these four points |",
        "|---|---:|---:|---|",
    ]
    for method in ("standard", "momentum", "compressible", "clsvof"):
        fit = power_fits[method]
        interpretation = (
            "error decreases with refinement" if fit["exponent"] < 0.
            else "error increases with refinement; no convergence claim"
        )
        report.append(
            f"| {METHODS[method][0]} | {fit['coefficient']:.6g} | "
            f"{fit['exponent']:+.6f} | {interpretation} |"
        )
    report += [
        "",
        f"CLSVOF stays below {max(float(row['frequency_abs_error_percent']) for row in by_method['clsvof']):.6g}% absolute frequency error, "
        f"but its fitted exponent is positive (`p={clsvof_fit['exponent']:+.3f}`). "
        "The coarse-grid agreement is therefore not evidence of frequency convergence.",
        "At 51.2 cells/D the absolute-error ordering is: "
        + " < ".join(f"{name} ({value:.6g}%)" for value, name in finest)
        + ".",
        "The CLSVOF damping coefficient is non-monotone across LEVEL 4--7; in particular, "
        "the LEVEL 5 fit reports `b=0.0203646 +/- 0.02922`, so its near-zero damping is unresolved.",
        "",
        "## Evidence boundary",
        "",
        "- Standard, Momentum and Compressible values in the comparison CSV are official reproduction outputs.",
        "- CLSVOF values are produced by this repository's non-official matched extension.",
        "- There is no CLSVOF `.ref`; no `official_pass` claim is made for this method.",
        "- The comparison changes interface maintenance, curvature evaluation and surface-tension discretisation together; it is not a curvature-only ablation.",
        "",
    ]
    (dataset / "RESULTS.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0 if manifest["artifacts_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
