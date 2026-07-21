#!/usr/bin/env python3
"""Verify formal rows and aggregate causal and descriptive result tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
FULL_RESULT_ROOT = ROOT / "hpc/results/oscillating_droplet"
FROZEN_CLSVOF = FULL_RESULT_ROOT / "clsvof_extension/clsvof"
OFFICIAL = FULL_RESULT_ROOT / "official_reproduction"
CANONICAL_DATASET = ROOT / "dataset/oscillating_droplet"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_fit_log(path: Path) -> dict[int, dict[str, float]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    starts = list(re.finditer(r"FIT:\s+data read from 'k-(\d+)'", text))
    results: dict[int, dict[str, float]] = {}
    for index, match in enumerate(starts):
        level = int(match.group(1))
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.start():end]
        values: dict[str, float] = {}
        for name in ("a", "b", "c"):
            parameter = re.search(
                rf"^{name}\s+=\s*([-+0-9.eE]+)\s*\+/-\s*([-+0-9.eE]+)",
                block,
                re.MULTILINE,
            )
            if not parameter:
                raise ValueError(f"missing {name} fit in {path} level {level}")
            values[name] = float(parameter.group(1))
            values[f"{name}_stderr"] = float(parameter.group(2))
        results[level] = values
    if not results:
        raise ValueError(f"no fit blocks in {path}")
    return results


def parse_scalar_by_level(path: Path) -> dict[int, float]:
    result: dict[int, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = re.match(r"\s*(\S+)\s+(\{[^}]+\}|\S+)\s+(\S+)", line)
        if not match:
            raise ValueError(f"cannot parse scalar row in {path}: {line}")
        cells = float(match.group(1))
        value_text = match.group(2)
        value = float(value_text[1:-1].split(",", 1)[0]) if value_text.startswith("{") else float(value_text)
        level = round(math.log2(cells / 0.4))
        result[level] = value
    return result


def parse_ke(path: Path) -> dict[str, float | int | bool]:
    times: list[float] = []
    energies: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        times.append(float(fields[0]))
        energies.append(float(fields[1]))
    finite = bool(times) and all(math.isfinite(v) for v in times + energies)
    monotonic = all(right > left for left, right in zip(times, times[1:]))
    return {
        "samples": len(times),
        "final_time": times[-1] if times else math.nan,
        "max_kinetic_energy": max(energies) if energies else math.nan,
        "finite": finite,
        "strictly_monotonic_time": monotonic,
        "nonnegative_energy": all(value >= 0.0 for value in energies),
    }


def peak_envelope_diagnostic(path: Path, c: float) -> dict[str, float | int]:
    data = np.loadtxt(path, usecols=(0, 1))
    period = 2.0 * math.pi / c
    peak_times: list[float] = []
    peak_values: list[float] = []
    index = 0
    while True:
        center = (math.pi + 2.0 * math.pi * index) / c
        if center > 0.97:
            break
        if center >= 0.08:
            mask = np.abs(data[:, 0] - center) <= 0.18 * period
            if np.any(mask):
                window = data[mask]
                peak = window[np.argmax(window[:, 1])]
                peak_times.append(float(peak[0]))
                peak_values.append(float(peak[1]))
        index += 1
    slope, _intercept = np.polyfit(peak_times, np.log(peak_values), 1)
    return {
        "peak_envelope_b_diagnostic": float(-slope),
        "peak_envelope_n": len(peak_values),
        "peak_envelope_first": peak_values[0],
        "peak_envelope_last": peak_values[-1],
    }


def row_metrics(row: Path, level: int) -> dict[str, float | int | str]:
    fit = parse_fit_log(row / "fit.log")[level]
    error = parse_scalar_by_level(row / "error")[level]
    laplace = parse_scalar_by_level(row / "laplace")[level]
    manifest = json.loads((row / "manifest.json").read_text(encoding="utf-8"))
    kinetic_path = row / f"k-{level}"
    ke = parse_ke(kinetic_path)
    peak_diagnostic = peak_envelope_diagnostic(kinetic_path, fit["c"])
    return {
        "method_id": manifest["method_id"],
        "level": level,
        "N": 1 << level,
        "cells_per_diameter": 0.4 * (1 << level),
        **fit,
        "frequency_error_signed": error,
        "frequency_error_abs_percent": abs(error) * 100.0,
        "equivalent_laplace": laplace,
        **ke,
        **peak_diagnostic,
    }


def landscape_rows(result_root: Path) -> list[dict[str, float | int | str]]:
    sources = [
        ("Standard VOF-HF", "official", OFFICIAL / "standard"),
        ("Momentum", "official", OFFICIAL / "momentum"),
        ("Compressible", "official", OFFICIAL / "compressible"),
        ("CLSVOF native", "nonofficial_extension", FROZEN_CLSVOF),
    ]
    rows: list[dict[str, float | int | str]] = []
    for method, evidence, directory in sources:
        fits = parse_fit_log(directory / "fit.log")
        errors = parse_scalar_by_level(directory / "error")
        laplace = parse_scalar_by_level(directory / "laplace")
        for level in sorted(fits):
            rows.append({
                "method": method,
                "evidence": evidence,
                "level": level,
                "N": 1 << level,
                "cells_per_diameter": 0.4 * (1 << level),
                **fits[level],
                "frequency_error_signed": errors[level],
                "frequency_error_abs_percent": abs(errors[level]) * 100.0,
                "equivalent_laplace": laplace[level],
            })
    for level in (6, 7):
        row = result_root / f"level_{level}/nn"
        metrics = row_metrics(row, level)
        rows.append({
            "method": "CLSVOF NN cell-offset",
            "evidence": "nonofficial_extension",
            "level": level,
            "N": 1 << level,
            "cells_per_diameter": 0.4 * (1 << level),
            **{key: metrics[key] for key in (
                "a", "a_stderr", "b", "b_stderr", "c", "c_stderr",
                "frequency_error_signed", "frequency_error_abs_percent", "equivalent_laplace"
            )},
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_root", type=Path)
    args = parser.parse_args(argv)
    result_root = args.result_root.resolve()

    comparisons: list[dict] = []
    checks: dict[str, object] = {"rows": {}, "all_passed": True}
    for level in (6, 7):
        native_dir = result_root / f"level_{level}/clsvof"
        nn_dir = result_root / f"level_{level}/nn"
        native = row_metrics(native_dir, level)
        nn = row_metrics(nn_dir, level)
        comparisons += [native, nn]
        native_exact = (native_dir / f"k-{level}").read_bytes() == (
            CANONICAL_DATASET
            / f"N{1 << level:04d}/imax03/clsvof/timeseries.dat"
        ).read_bytes()
        nn_manifest = json.loads((nn_dir / "manifest.json").read_text(encoding="utf-8"))
        stats = nn_manifest["provider_stats"]
        row_checks = {
            "native_kinetic_energy_exact": native_exact,
            "native_finite": native["finite"],
            "nn_finite": nn["finite"],
            "native_terminal_sample_after_0p999": native["final_time"] >= 0.999,
            "nn_terminal_sample_after_0p999": nn["final_time"] >= 0.999,
            "paired_terminal_sample_exact": native["final_time"] == nn["final_time"],
            "nn_provider_evaluations_positive": stats["evaluations"] > 0,
            "nn_guard_hits_zero": stats["denominator_guard_hits"] == 0,
            "nn_clamp_hits_zero": stats["clamp_hits"] == 0,
            "nn_frequency_disaster_gate": nn["frequency_error_abs_percent"] < 5.0,
            "native_fit_and_peak_envelope_same_sign":
                native["b"] * native["peak_envelope_b_diagnostic"] > 0,
            "nn_fit_and_peak_envelope_same_sign":
                nn["b"] * nn["peak_envelope_b_diagnostic"] > 0,
        }
        checks["rows"][str(level)] = row_checks
        checks["all_passed"] = bool(checks["all_passed"]) and all(row_checks.values())

    write_csv(result_root / "comparison.csv", comparisons)
    landscape = landscape_rows(result_root)
    write_csv(result_root / "landscape_5method.csv", landscape)
    checks["artifacts"] = {
        "comparison_sha256": sha256(result_root / "comparison.csv"),
        "landscape_sha256": sha256(result_root / "landscape_5method.csv"),
    }
    canary_verification = result_root / "canary_verification.json"
    if canary_verification.is_file():
        canary = json.loads(canary_verification.read_text(encoding="utf-8"))
        checks["canary_all_passed"] = canary["all_passed"]
        checks["all_passed"] = bool(checks["all_passed"]) and canary["all_passed"]
        checks["artifacts"]["canary_verification_sha256"] = sha256(canary_verification)
    (result_root / "verification.json").write_text(
        json.dumps(checks, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    aggregate = {
        "case_id": "oscillating_droplet",
        "evidence_structure": {
            "L1_causal": "CLSVOF_NN_CELL_OFFSET vs CLSVOF_NATIVE",
            "L2_descriptive": "five-method landscape; no cross-solver causal ranking",
        },
        "levels": [6, 7],
        "verification": checks,
        "row_manifest_sha256": {
            str(path.relative_to(result_root)): sha256(path)
            for path in sorted(result_root.glob("level_*/**/manifest.json"))
        },
    }
    (result_root / "manifest.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result_root": str(result_root), "all_passed": checks["all_passed"]}, sort_keys=True))
    return 0 if checks["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
