#!/usr/bin/env python3
"""Build a plot-ready, source-traceable scientific artifact contract for one row."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Iterable


METRIC_FIELDS = [
    "metric",
    "value",
    "unit",
    "scope",
    "time",
    "definition",
    "source_artifact",
    "origin",
]

EXPECTED_OFFICIAL_PUBLISH_NAMES = {
    "capwave": {"wave.dat", "official_error.dat", "prosperetti.h"},
    "rising_bubble": {"history.dat", "interface.dat"},
    "stationary_bubble": {
        "timeseries.dat",
        "runtime_and_terminal.log",
        "official_terminal.dat",
    },
    "oscillating_droplet": {
        "timeseries.dat",
        "fit_curve.dat",
        "fit.log",
        "error.dat",
        "laplace.dat",
        "fit_summary.dat",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric_rows(path: Path, minimum: int = 1) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split()
        if len(fields) < minimum:
            continue
        try:
            values = [float(value) for value in fields]
        except ValueError:
            continue
        if all(math.isfinite(value) for value in values):
            rows.append(values)
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def metric(
    name: str,
    value: float | int | str,
    unit: str,
    scope: str,
    definition: str,
    source: str,
    *,
    time: float | str = "",
    origin: str = "official",
) -> dict[str, object]:
    return {
        "metric": name,
        "value": value,
        "unit": unit,
        "scope": scope,
        "time": time,
        "definition": definition,
        "source_artifact": source,
        "origin": origin,
    }


def capwave(root: Path, identity: dict[str, object]) -> tuple[list[dict], list[dict]]:
    resolution = int(identity["resolution"])
    wave_path = root / f"wave-{resolution}"
    wave = numeric_rows(wave_path, 2)
    if not wave or any(len(row) != 2 for row in wave):
        raise ValueError(f"invalid capwave trajectory: {wave_path}")
    reference = [
        (float(left), float(right))
        for left, right in re.findall(
            r"\{\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*\}",
            (root / "prosperetti.h").read_text(encoding="utf-8"),
        )
    ]
    if len(reference) != len(wave):
        raise ValueError(
            f"capwave reference/sample mismatch: {len(reference)} != {len(wave)}"
        )
    official_rows = [row for row in numeric_rows(root / "log", 2) if len(row) == 2]
    if len(official_rows) != 1:
        raise ValueError(f"expected one official capwave error row, got {official_rows}")
    official_resolution, official_rms = official_rows[0]
    recomputed = math.sqrt(
        sum((row[1] - reference[index][1]) ** 2 for index, row in enumerate(wave))
        / len(wave)
    ) / 0.01
    plot_rows = [
        {
            "tau": row[0],
            "amplitude": row[1],
            "reference_amplitude": reference[index][1],
            "amplitude_error": row[1] - reference[index][1],
        }
        for index, row in enumerate(wave)
    ]
    write_csv(
        root / "plot_data.csv",
        ["tau", "amplitude", "reference_amplitude", "amplitude_error"],
        plot_rows,
    )
    metrics = [
        metric("grid_resolution", resolution, "cells", "identity", "N", "manifest.json", origin="benchmark_identity"),
        metric(
            "points_per_wavelength",
            official_resolution,
            "cells_per_wavelength",
            "official_resolution",
            "N/L0",
            "log",
        ),
        metric(
            "relative_rms_error",
            official_rms,
            "1",
            "global",
            "sqrt(mean((a_num-a_ref)^2))/0.01",
            "log",
        ),
        metric(
            "relative_rms_error_recomputed",
            recomputed,
            "1",
            "global",
            "sqrt(mean((a_num-a_ref)^2))/0.01",
            f"{wave_path.name}+prosperetti.h",
            origin="derived",
        ),
        metric(
            "relative_rms_recompute_delta",
            recomputed - official_rms,
            "1",
            "audit",
            "recomputed-official",
            "metrics.csv",
            origin="derived",
        ),
        metric("samples", len(wave), "count", "global", "number of amplitude samples", wave_path.name, origin="derived_from_official"),
    ]
    artifacts = [
        artifact(root, wave_path.name, "official_raw", "wave.dat", True,
                 ["tau", "amplitude"], ["1", "L0"]),
        artifact(root, "log", "official_raw", "official_error.dat", True,
                 ["points_per_wavelength", "relative_rms_error"],
                 ["cells_per_wavelength", "1"]),
        artifact(root, "prosperetti.h", "official_reference", "prosperetti.h", True),
    ]
    return metrics, artifacts


def rising(root: Path, _identity: dict[str, object]) -> tuple[list[dict], list[dict]]:
    history = [row for row in numeric_rows(root / "stdout.txt", 6) if len(row) >= 6]
    if not history or abs(history[-1][0] - 3.0) > 1e-9:
        raise ValueError("rising history does not reach t=3")
    facets = [row for row in numeric_rows(root / "log", 2) if len(row) == 2]
    if not facets:
        raise ValueError("rising final interface is empty")
    with (root / "circularity.csv").open(newline="", encoding="utf-8") as stream:
        circularity = list(csv.DictReader(stream))
    if not circularity:
        raise ValueError("rising circularity history is empty")
    plot_rows = [
        {
            "time": row[0],
            "relative_volume_change": row[1],
            "center_of_mass_x": row[3],
            "rise_velocity_x": row[4],
            "dt": row[5],
        }
        for row in history
    ]
    write_csv(
        root / "plot_data.csv",
        ["time", "relative_volume_change", "center_of_mass_x", "rise_velocity_x", "dt"],
        plot_rows,
    )
    circ_values = [float(row["circularity"]) for row in circularity]
    final = history[-1]
    metrics = [
        metric("actual_terminal_time", final[0], "T0", "terminal", "last official history time", "stdout.txt", time=final[0], origin="derived_from_official"),
        metric("relative_volume_change_final", final[1], "1", "terminal", "(V-V0)/V0", "stdout.txt", time=final[0], origin="derived_from_official"),
        metric("relative_volume_change_max_abs", max(abs(row[1]) for row in history), "1", "global", "max(abs((V-V0)/V0))", "stdout.txt", origin="derived_from_official"),
        metric("center_of_mass_x_final", final[3], "L0", "terminal", "integral(x dV)/V", "stdout.txt", time=final[0], origin="derived_from_official"),
        metric("rise_velocity_x_final", final[4], "L0/T0", "terminal", "integral(u_x dV)/V", "stdout.txt", time=final[0], origin="derived_from_official"),
        metric("rise_velocity_x_max", max(row[4] for row in history), "L0/T0", "global", "max center-of-mass rise velocity", "stdout.txt", origin="derived_from_official"),
        metric("interface_facets", len(facets), "segments", "terminal", "number of t=3 output_facets segments", "log", time=3.0, origin="derived_from_official"),
        metric("circularity_min", min(circ_values), "1", "global", "sqrt(4*pi*A_full)/P_full", "circularity.csv", origin="repo_extension"),
        metric("circularity_final", circ_values[-1], "1", "terminal", "sqrt(4*pi*A_full)/P_full", "circularity.csv", time=3.0, origin="repo_extension"),
    ]
    artifacts = [
        artifact(root, "stdout.txt", "official_raw", "history.dat", True),
        artifact(root, "log", "official_raw", "interface.dat", True),
        artifact(root, "circularity.csv", "extension_raw", "circularity.csv", True),
    ]
    return metrics, artifacts


def stationary(root: Path, identity: dict[str, object]) -> tuple[list[dict], list[dict]]:
    mode_dirs = [path for path in root.iterdir() if path.is_dir() and list(path.glob("La-*"))]
    if len(mode_dirs) != 1:
        raise ValueError(f"expected one stationary mode directory, got {mode_dirs}")
    mode = mode_dirs[0]
    series_path = next(mode.glob("La-*"))
    series = [row for row in numeric_rows(series_path, 3) if len(row) == 3]
    if not series:
        raise ValueError("stationary time series is empty")
    official_rows = [row for row in numeric_rows(mode / "log", 7) if len(row) == 7 and row[1] == 12000.0]
    if len(official_rows) != 1:
        raise ValueError(f"expected one stationary terminal row, got {official_rows}")
    official = official_rows[0]
    (root / "official_terminal.dat").write_text(
        " ".join(f"{value:.17g}" for value in official) + "\n", encoding="utf-8"
    )
    sqrt_la = math.sqrt(12000.0)
    plot_rows = [
        {
            "tau": row[0],
            "u_star": row[1],
            "delta_fraction": row[2],
            "capillary_number": row[1] / sqrt_la,
        }
        for row in series
    ]
    write_csv(
        root / "plot_data.csv",
        ["tau", "u_star", "delta_fraction", "capillary_number"],
        plot_rows,
    )
    termination_path = mode / "termination.csv"
    if not termination_path.is_file():
        raise ValueError("stationary termination.csv is missing")
    with termination_path.open(newline="", encoding="utf-8") as stream:
        termination_rows = list(csv.DictReader(stream))
    if len(termination_rows) != 1:
        raise ValueError("stationary termination.csv must contain exactly one row")
    terminal_tau = float(termination_rows[0]["actual_terminal_tau"])
    stop_reason = termination_rows[0]["reason"]
    metrics = [
        metric("actual_terminal_tau", terminal_tau, "1", "terminal", "mu*t/D^2", termination_path.relative_to(root).as_posix(), time=terminal_tau, origin="repo_extension"),
        metric("termination_reason", stop_reason, "category", "terminal", "solver stop condition", termination_path.relative_to(root).as_posix(), time=terminal_tau, origin="repo_extension"),
        metric("level", int(official[0]), "level", "official_resolution", "grid refinement level", "official_terminal.dat"),
        metric("diameter_cells", 0.8 * int(identity["resolution"]), "cells_per_diameter", "official_resolution", "D*N", "manifest.json", origin="derived_from_benchmark_identity"),
        metric("laplace_number", official[1], "1", "identity", "sigma*rho*D/mu^2", "official_terminal.dat"),
        metric("u_star_final", official[2], "1", "terminal", "max(|u|)*sqrt(D/sigma)", "official_terminal.dat", time=terminal_tau),
        metric("shape_error_avg", official[3], "1", "terminal", "normf(c-c_ref).avg", "official_terminal.dat", time=terminal_tau),
        metric("shape_error_rms", official[4], "1", "terminal", "normf(c-c_ref).rms", "official_terminal.dat", time=terminal_tau),
        metric("shape_error_max", official[5], "1", "terminal", "normf(c-c_ref).max", "official_terminal.dat", time=terminal_tau),
        metric("ekmax", official[6], "L0^-1", "terminal", "max(abs(kappa-1/R_equiv))", "official_terminal.dat", time=terminal_tau),
        metric("relative_curvature_error", official[6] / 2.5, "1", "terminal", "ekmax/(1/R), R=0.4", "official_terminal.dat", time=terminal_tau, origin="derived"),
        metric("relative_curvature_error_percent", 100.0 * official[6] / 2.5, "%", "terminal", "100*ekmax/2.5", "official_terminal.dat", time=terminal_tau, origin="derived"),
    ]
    artifacts = [
        artifact(root, series_path.relative_to(root).as_posix(), "official_raw", "timeseries.dat", True),
        artifact(root, (mode / "log").relative_to(root).as_posix(), "official_raw", "runtime_and_terminal.log", True),
        artifact(root, "official_terminal.dat", "official_raw", "official_terminal.dat", True),
        artifact(root, termination_path.relative_to(root).as_posix(), "extension_raw", "termination.csv", True),
    ]
    return metrics, artifacts


def oscillating(root: Path, identity: dict[str, object]) -> tuple[list[dict], list[dict]]:
    level = int(identity["level"])
    fit_enabled = bool(identity.get("fit_enabled", True))
    kinetic_name = f"k-{level}"
    kinetic = [row for row in numeric_rows(root / kinetic_name, 2) if len(row) >= 2]
    if not kinetic:
        raise ValueError("oscillating kinetic-energy series is empty")
    plot_rows = [
        {
            "time": row[0],
            "kinetic_energy": row[1],
            "pressure_iterations": int(row[2]) if len(row) > 2 else "",
        }
        for row in kinetic
    ]
    write_csv(root / "plot_data.csv", ["time", "kinetic_energy", "pressure_iterations"], plot_rows)
    last_sample_time = kinetic[-1][0]
    terminal = last_sample_time
    checkpoint_index = root / "checkpoint_index.csv"
    if checkpoint_index.is_file():
        with checkpoint_index.open(newline="", encoding="utf-8") as stream:
            checkpoint_rows = list(csv.DictReader(stream))
        terminal_rows = [row for row in checkpoint_rows if row["label"] == "terminal"]
        if len(terminal_rows) != 1 or terminal_rows[0]["status"] != "written":
            raise ValueError("oscillating terminal checkpoint row is incomplete")
        terminal = float(terminal_rows[0]["actual_time"])
    metrics: list[dict] = [
        metric("actual_terminal_time", terminal, "T0", "terminal", "terminal solver-state time", "checkpoint_index.csv", time=terminal, origin="repo_extension"),
        metric("last_kinetic_energy_sample_time", last_sample_time, "T0", "terminal_sampling", "last official kinetic-energy sample time", kinetic_name, time=last_sample_time, origin="derived_from_official"),
        metric("diameter_cells", identity["cells_per_diameter"], "cells_per_diameter", "official_resolution", "D/L0*N", "manifest.json", origin="benchmark_identity"),
        metric("max_kinetic_energy", max(row[1] for row in kinetic), "energy", "global", "max(K(t))", kinetic_name, origin="derived_from_official"),
    ]
    artifacts: list[dict] = [
        artifact(root, kinetic_name, "official_raw", "timeseries.dat", True),
    ]
    if fit_enabled:
        fit_text = (root / "fit.log").read_text(encoding="utf-8", errors="replace")
        fit_values: dict[str, float] = {}
        for name in ("a", "b", "c"):
            match = re.search(
                rf"^{name}\s+=\s*([-+0-9.eE]+)\s*\+/-\s*([-+0-9.eE]+)",
                fit_text,
                re.MULTILINE,
            )
            if not match:
                raise ValueError(f"missing {name} in fit.log")
            fit_values[name] = float(match.group(1))
            fit_values[f"{name}_stderr"] = float(match.group(2))
        error_rows = numeric_rows(root / "error", 3)
        laplace_rows = numeric_rows(root / "laplace", 3)
        if len(error_rows) != 1 or len(laplace_rows) != 1:
            raise ValueError("oscillating error/laplace rows are incomplete")
        metrics.extend(
            [
                metric("fit_a", fit_values["a"], "energy", "global", "a*exp(-b*t)*(1-cos(c*t))", "fit.log"),
                metric("fit_a_stderr", fit_values["a_stderr"], "energy", "fit_uncertainty", "gnuplot asymptotic standard error", "fit.log"),
                metric("fit_b", fit_values["b"], "T0^-1", "global", "a*exp(-b*t)*(1-cos(c*t))", "fit.log"),
                metric("fit_b_stderr", fit_values["b_stderr"], "T0^-1", "fit_uncertainty", "gnuplot asymptotic standard error", "fit.log"),
                metric("fit_c", fit_values["c"], "rad*T0^-1", "global", "a*exp(-b*t)*(1-cos(c*t))", "fit.log"),
                metric("fit_c_stderr", fit_values["c_stderr"], "rad*T0^-1", "fit_uncertainty", "gnuplot asymptotic standard error", "fit.log"),
                metric("frequency_error_signed", error_rows[0][1], "1", "global", "c/(2*omega0)-1", "error"),
                metric("frequency_error_abs_percent", abs(error_rows[0][1]) * 100.0, "%", "global", "100*abs(c/(2*omega0)-1)", "error", origin="derived"),
                metric("equivalent_laplace", laplace_rows[0][1], "1", "global", "30^2/(b^2*D^3)", "laplace"),
                metric("fit_damping_regime", "damped" if fit_values["b"] > 0. else "nonphysical_growth", "category", "fit_quality", "sign(b): b>0 is exponential damping", "fit.log", origin="derived"),
            ]
        )
        artifacts.extend(
            [
                artifact(root, f"fit-{level}", "official_raw", "fit_curve.dat", True),
                artifact(root, "fit.log", "official_raw", "fit.log", True),
                artifact(root, "error", "official_raw", "error.dat", True),
                artifact(root, "laplace", "official_raw", "laplace.dat", True),
                artifact(root, "log", "official_raw", "fit_summary.dat", True),
            ]
        )
    return metrics, artifacts


def artifact(
    root: Path,
    path: str,
    role: str,
    publish_name: str,
    publish: bool,
    columns: list[str] | None = None,
    units: list[str] | None = None,
) -> dict[str, object]:
    candidate = root / path
    if not candidate.is_file() or candidate.stat().st_size == 0:
        raise ValueError(f"missing scientific artifact: {candidate}")
    record: dict[str, object] = {
        "path": path,
        "role": role,
        "publish": publish,
        "publish_name": publish_name,
        "sha256": sha256(candidate),
        "bytes": candidate.stat().st_size,
    }
    if columns:
        record["columns"] = columns
    if units:
        record["units"] = units
    return record


def provider_runtime_metrics(
    root: Path, identity: dict[str, object]
) -> list[dict[str, object]]:
    stats = identity.get("provider_stats")
    source = "runtime.stderr.txt"
    if not isinstance(stats, dict):
        matches: list[tuple[Path, str]] = []
        for candidate in root.rglob("log"):
            for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("kappa_offset_provider_stats "):
                    matches.append((candidate, line))
        if not matches:
            return []
        if len(matches) != 1:
            raise ValueError(f"expected one provider stats row, found {len(matches)}")
        candidate, line = matches[0]
        source = candidate.relative_to(root).as_posix()
        stats = {}
        for item in line.split()[1:]:
            name, value = item.split("=", 1)
            stats[name] = int(value) if name in {
                "evaluations", "clamp_hits", "denominator_guard_hits", "grad_samples"
            } else float(value)
    rows: list[dict[str, object]] = []
    for name, value in stats.items():
        unit = "count" if name in {
            "evaluations", "clamp_hits", "denominator_guard_hits", "grad_samples"
        } else "1"
        rows.append(
            metric(
                f"provider_{name}",
                value,
                unit,
                "provider_runtime",
                f"kappa_offset_provider_stats {name}",
                source,
                origin="repo_extension",
            )
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("row_dir", type=Path)
    args = parser.parse_args()
    root = args.row_dir.resolve()
    manifest_path = root / "manifest.json"
    identity = json.loads(manifest_path.read_text(encoding="utf-8"))
    case = str(identity.get("case_id") or identity.get("case"))
    benchmark = str(identity.get("benchmark") or case)
    if case == "capwave":
        metrics, artifacts = capwave(root, identity)
    elif case == "rising_bubble":
        metrics, artifacts = rising(root, identity)
    elif case == "stationary_bubble":
        metrics, artifacts = stationary(root, identity)
    elif case == "oscillating_droplet":
        metrics, artifacts = oscillating(root, identity)
    else:
        raise SystemExit(f"unsupported scientific case: {case}")

    metrics.extend(provider_runtime_metrics(root, identity))

    write_csv(root / "metrics.csv", METRIC_FIELDS, metrics)
    artifacts.extend(
        [
            artifact(root, "metrics.csv", "derived_metrics", "metrics.csv", True),
            artifact(root, "plot_data.csv", "derived_plot", "plot_data.csv", True),
        ]
    )
    checkpoint_index = root / "checkpoint_index.csv"
    if checkpoint_index.is_file():
        artifacts.append(
            artifact(root, "checkpoint_index.csv", "checkpoint_index", "checkpoint_index.csv", True)
        )
    for checkpoint in sorted((root / "checkpoints").glob("*.dump")) if (root / "checkpoints").is_dir() else []:
        relative_checkpoint = checkpoint.relative_to(root).as_posix()
        artifacts.append(
            artifact(
                root,
                relative_checkpoint,
                "checkpoint",
                relative_checkpoint,
                True,
            )
        )

    official = [item for item in artifacts if item["role"] in {"official_raw", "official_reference"}]
    actual_official_names = {str(item["publish_name"]) for item in official}
    expected_official_names = EXPECTED_OFFICIAL_PUBLISH_NAMES[case]
    if case == "oscillating_droplet" and not identity.get("fit_enabled", True):
        expected_official_names = {"timeseries.dat"}
    missing_official_names = sorted(expected_official_names - actual_official_names)
    if missing_official_names:
        raise ValueError(
            f"official artifact coverage incomplete for {case}: {missing_official_names}"
        )
    contract = {
        "schema_version": 1,
        "case": case,
        "benchmark": benchmark,
        "method": identity.get("method_id") or identity.get("method"),
        "resolution": identity.get("N") or identity.get("resolution"),
        "imax": identity.get("redistance_imax") if "redistance_imax" in identity else identity.get("imax"),
        "model_id": identity.get("model_name") or identity.get("model"),
        "model_resolution": (
            identity.get("N") or identity.get("resolution")
            if (identity.get("model_name") or identity.get("model"))
            else None
        ),
        "checkpoint_sha256": identity.get("checkpoint_sha256"),
        "official_coverage_complete": not missing_official_names,
        "official_artifact_count": len(official),
        "expected_official_publish_names": sorted(expected_official_names),
        "missing_official_publish_names": missing_official_names,
        "artifacts": artifacts,
    }
    contract_path = root / "scientific_artifacts.json"
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity["scientific_artifacts_schema_version"] = 1
    identity["scientific_artifacts_sha256"] = sha256(contract_path)
    identity["official_coverage_complete"] = contract["official_coverage_complete"]
    manifest_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"case": case, "artifacts": len(artifacts), "metrics": len(metrics)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
