#!/usr/bin/env python3
"""Parse provider probe streams into auditable cell rows and local metrics."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path


PROBE = re.compile(r"^KAPPA_OFFSET_PROBE\s+(.*)$")
STAT = re.compile(r"^kappa_offset_provider_stats\s+(.*)$")
NAMES = (
    "time", "x", "y", "d_over_h", "grad_norm", "q_gamma", "q_cell",
    "q_native", "denominator", "clamped", "guard",
)


def parse_key_value(text: str) -> dict[str, float | int]:
    values: dict[str, float | int] = {}
    for token in text.split():
        key, value = token.split("=", 1)
        values[key] = int(value) if re.fullmatch(r"[+-]?\d+", value) else float(value)
    return values


def load_run(path: Path) -> tuple[list[dict], list[dict]]:
    manifest = json.loads((path/"run_manifest.json").read_text(encoding="utf-8"))
    rows, stats = [], []
    for raw_line in (path/"log").read_text(encoding="utf-8").splitlines():
        match = PROBE.match(raw_line)
        if match:
            tokens = match.group(1).split()
            if len(tokens) != len(NAMES):
                raise ValueError(f"{path}: expected {len(NAMES)} probe fields, got {len(tokens)}")
            row = {key: (int(value) if key in {"clamped", "guard"} else float(value))
                   for key, value in zip(NAMES, tokens, strict=True)}
            row.update({key: manifest[key] for key in ("benchmark", "case", "resolution", "model", "mode")})
            row["run_dir"] = str(path)
            rows.append(row)
            continue
        match = STAT.match(raw_line)
        if match:
            stat = parse_key_value(match.group(1))
            stat.update({key: manifest[key] for key in ("benchmark", "case", "resolution", "model", "mode")})
            stat["run_dir"] = str(path)
            stats.append(stat)
    return rows, stats


def summary(values: list[float]) -> dict[str, float]:
    return {
        "rmse": math.sqrt(sum(value*value for value in values)/len(values)),
        "mae": sum(abs(value) for value in values)/len(values),
        "bias": sum(values)/len(values),
        "max_abs_error": max(abs(value) for value in values),
    }


def local_metrics(rows: list[dict]) -> list[dict]:
    group_keys = ("benchmark", "case", "resolution", "model", "mode", "time")
    groups: dict[tuple, list[dict]] = defaultdict(list)
    aggregate_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in group_keys)].append(row)
        aggregate_groups[tuple(row[key] for key in group_keys[:-1])].append(row)
    output: list[dict] = []
    for key, samples in groups.items():
        common = dict(zip(group_keys, key, strict=True))
        for method in ("q_cell",):
            error = [float(row[method] - row["q_native"]) for row in samples]
            result = {**common, "reference": "q_native", "method": method,
                      "n": len(samples), **summary(error)}
            result["sign_consistency"] = sum(
                math.copysign(1., row[method]) == math.copysign(1., row["q_native"])
                for row in samples
            )/len(samples)
            result["clamp_hits"] = sum(int(row["clamped"]) for row in samples)
            result["denominator_guard_hits"] = sum(
                int(row["guard"]) for row in samples
            )
            output.append(result)
    for key, samples in aggregate_groups.items():
        common = dict(zip(group_keys[:-1], key, strict=True))
        common["time"] = "all"
        for method in ("q_cell",):
            error = [float(row[method] - row["q_native"]) for row in samples]
            result = {**common, "reference": "q_native", "method": method,
                      "n": len(samples), **summary(error)}
            result["sign_consistency"] = sum(
                math.copysign(1., row[method]) == math.copysign(1., row["q_native"])
                for row in samples
            )/len(samples)
            result["clamp_hits"] = sum(int(row["clamped"]) for row in samples)
            result["denominator_guard_hits"] = sum(
                int(row["guard"]) for row in samples
            )
            output.append(result)
    return output


def quantiles(rows: list[dict]) -> dict[str, list[float]]:
    probabilities = (0., .05, .25, .5, .75, .95, 1.)
    def selected(values: list[float]) -> list[float]:
        values = sorted(values)
        return [values[round((len(values) - 1)*probability)] for probability in probabilities]

    output: dict[str, list[float]] = {"probabilities": list(probabilities)}
    values = [float(row["d_over_h"]) for row in rows]
    output["all"] = selected(values) if values else []
    for benchmark in sorted({str(row["benchmark"]) for row in rows}):
        values = [float(row["d_over_h"]) for row in rows if row["benchmark"] == benchmark]
        output[benchmark] = selected(values) if values else []
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--cells-csv", type=Path, required=True)
    parser.add_argument("--metrics-csv", type=Path, required=True)
    parser.add_argument("--stats-csv", type=Path, required=True)
    parser.add_argument("--offset-quantiles-json", type=Path, required=True)
    args = parser.parse_args()

    rows, stats = [], []
    for run_dir in args.run_dir:
        run_rows, run_stats = load_run(run_dir)
        rows.extend(run_rows)
        stats.extend(run_stats)
    metrics = local_metrics(rows)
    for destination in (args.cells_csv, args.metrics_csv, args.stats_csv, args.offset_quantiles_json):
        destination.parent.mkdir(parents=True, exist_ok=True)
    write_csv(args.cells_csv, rows)
    write_csv(args.metrics_csv, metrics)
    write_csv(args.stats_csv, stats)
    args.offset_quantiles_json.write_text(json.dumps(quantiles(rows), indent=2) + "\n",
                                          encoding="utf-8")
    if not rows:
        raise SystemExit("no KAPPA_OFFSET_PROBE rows found")
    print(args.cells_csv)
    print(args.metrics_csv)
    return 0


if __name__ == "__main__":
    main()
