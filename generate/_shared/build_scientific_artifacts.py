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

EXPECTED_BENCHMARK_OUTPUT_NAMES = {
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

REQUIRED_PLOT_COLUMNS = {
    "capwave": ["tau", "amplitude", "reference_amplitude", "amplitude_error"],
    "rising_bubble": [
        "time", "iteration", "relative_volume_change", "center_of_mass_x",
        "rise_velocity_x", "dt", "circularity", "half_area", "half_perimeter",
    ],
    "stationary_bubble": ["tau", "u_star", "delta_fraction", "capillary_number"],
    "oscillating_droplet": ["time", "kinetic_energy", "pressure_iterations"],
}

REQUIRED_METRICS = {
    "capwave": {
        "grid_resolution", "points_per_wavelength", "relative_rms_error",
        "relative_rms_error_recomputed", "relative_rms_recompute_delta", "samples",
    },
    "rising_bubble": {
        "actual_terminal_time", "relative_volume_change_final",
        "relative_volume_change_max_abs", "center_of_mass_x_final",
        "rise_velocity_x_final", "rise_velocity_x_max", "interface_facets",
        "circularity_min", "circularity_final",
    },
    "stationary_bubble": {
        "actual_terminal_tau", "termination_reason", "level", "diameter_cells",
        "laplace_number", "u_star_final", "shape_error_avg", "shape_error_rms",
        "shape_error_max", "official_style_ekmax", "active_provider_ekmax",
        "active_provider_samples", "official_style_relative_curvature_error",
        "active_provider_relative_curvature_error",
        "duplicate_tau_samples_removed", "u_star_tau_1",
        "shape_error_avg_tau_1", "shape_error_rms_tau_1", "shape_error_max_tau_1",
        "official_style_ekmax_tau_1", "active_provider_ekmax_tau_1",
        "active_provider_samples_tau_1",
    },
    "oscillating_droplet": {
        "actual_terminal_time", "last_kinetic_energy_sample_time",
        "diameter_cells", "max_kinetic_energy", "fit_a", "fit_a_stderr",
        "fit_b", "fit_b_stderr", "fit_c", "fit_c_stderr",
        "frequency_error_signed", "frequency_error_abs_percent",
        "equivalent_laplace", "fit_damping_regime",
    },
}

PROVIDER_STATS_FIELDS = [
    "evaluations",
    "clamp_hits",
    "denominator_guard_hits",
    "min_abs_denominator",
    "max_abs_d_over_h",
    "grad_samples",
    "grad_min",
    "grad_mean",
    "grad_std",
    "grad_max",
]
PROVIDER_INTEGER_FIELDS = {
    "evaluations",
    "clamp_hits",
    "denominator_guard_hits",
    "grad_samples",
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
        # Gnuplot 6 can print a propagated value as ``{center, uncertainty}``
        # (notably b**2 after a negative-damping fit).  Preserve the raw file
        # and use its central value for the benchmark metric.
        normalized = re.sub(
            r"\{\s*([-+0-9.eE]+)\s*,\s*[-+0-9.eE]+\s*\}", r"\1", line
        )
        fields = normalized.split()
        if len(fields) < minimum:
            continue
        try:
            values = [float(value) for value in fields]
        except ValueError:
            continue
        if all(math.isfinite(value) for value in values):
            rows.append(values)
    return rows


def require_strictly_increasing(values: list[float], label: str) -> None:
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError(f"{label} is not strictly increasing")


def normalize_duplicate_stationary_samples(
    series: list[list[float]],
) -> tuple[list[list[float]], int]:
    """Collapse repeated logfile samples while preserving the latest state.

    The stationary logger is intended to record each solver time once.  Older
    hosts can schedule it more than once at a time event (including the fixed
    endpoint), yielding adjacent duplicate ``tau`` values.  Such records are
    output artifacts, so retain their final state and count every removal for
    the manifest.  A decrease remains invalid solver output rather than a
    candidate for normalization.
    """
    normalized: list[list[float]] = []
    duplicate_samples_removed = 0
    tolerance = 1e-9
    for sample in series:
        if not normalized:
            normalized.append(sample)
            continue
        previous_tau = normalized[-1][0]
        tau = sample[0]
        if tau > previous_tau + tolerance:
            normalized.append(sample)
        elif abs(tau - previous_tau) <= tolerance:
            normalized[-1] = sample
            duplicate_samples_removed += 1
        else:
            raise ValueError(
                "stationary tau decreases; refusing to normalize solver output"
            )
    return normalized, duplicate_samples_removed


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
    origin: str = "official_benchmark_definition",
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
    wave_path = root / "wave.dat"
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
    official_rows = [
        row for row in numeric_rows(root / "official_error.dat", 2)
        if len(row) == 2
    ]
    if len(official_rows) != 1:
        raise ValueError(f"expected one official capwave error row, got {official_rows}")
    official_resolution, official_rms = official_rows[0]
    # The official diagnostic reports points per unit wavelength.  The
    # generated grid resolution N spans the stock L0=2 domain.
    if int(official_resolution) != resolution // 2:
        raise ValueError(
            "capwave points-per-wavelength mismatch: "
            f"output={official_resolution} expected={resolution // 2}"
        )
    recomputed = math.sqrt(
        sum((row[1] - reference[index][1]) ** 2 for index, row in enumerate(wave))
        / len(wave)
    ) / 0.01
    if abs(recomputed - official_rms) > 5e-7:
        raise ValueError(
            "capwave official/recomputed RMS mismatch: "
            f"official={official_rms} recomputed={recomputed}"
        )
    require_strictly_increasing([row[0] for row in wave], "capwave time")
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
            "official_error.dat",
        ),
        metric(
            "relative_rms_error",
            official_rms,
            "1",
            "global",
            "sqrt(mean((a_num-a_ref)^2))/0.01",
            "official_error.dat",
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
        metric("samples", len(wave), "count", "global", "number of amplitude samples", wave_path.name, origin="derived_from_benchmark_output"),
    ]
    artifacts = [
        artifact(root, "wave.dat", "benchmark_raw", "wave.dat", True,
                 ["tau", "amplitude"], ["1", "L0"]),
        artifact(root, "official_error.dat", "benchmark_raw", "official_error.dat", True,
                 ["points_per_wavelength", "relative_rms_error"],
                 ["cells_per_wavelength", "1"]),
        artifact(root, "prosperetti.h", "official_reference", "prosperetti.h", True),
    ]
    return metrics, artifacts


def rising(root: Path, _identity: dict[str, object]) -> tuple[list[dict], list[dict]]:
    history = [row for row in numeric_rows(root / "history.dat", 6) if len(row) >= 6]
    if (
        not history
        or abs(history[0][0]) > 1e-12
        or abs(history[-1][0] - 3.0) > 1e-9
    ):
        raise ValueError("rising history does not reach t=3")
    require_strictly_increasing([row[0] for row in history], "rising history time")
    facets = [row for row in numeric_rows(root / "interface.dat", 2) if len(row) == 2]
    if not facets:
        raise ValueError("rising final interface is empty")
    with (root / "circularity.csv").open(newline="", encoding="utf-8") as stream:
        circularity = list(csv.DictReader(stream))
    if not circularity:
        raise ValueError("rising circularity history is empty")
    circularity_times: list[float] = []
    circ_values: list[float] = []
    circularity_samples: list[dict[str, float]] = []
    for row in circularity:
        try:
            values = [
                float(row[field])
                for field in ("time", "half_area", "half_perimeter", "circularity")
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid rising circularity row: {row}") from error
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"non-finite rising circularity row: {row}")
        if values[1] <= 0. or values[2] <= 0. or values[3] <= 0.:
            raise ValueError(f"non-positive rising circularity geometry: {row}")
        circularity_times.append(values[0])
        circ_values.append(values[3])
        circularity_samples.append(
            {
                "time": values[0],
                "iteration": int(row["iteration"]),
                "half_area": values[1],
                "half_perimeter": values[2],
                "circularity": values[3],
            }
        )
    if abs(circularity_times[0]) > 1e-12 or abs(circularity_times[-1] - 3.) > 1e-9:
        raise ValueError("rising circularity does not span t=0..3")
    require_strictly_increasing(circularity_times, "rising circularity time")
    plot_rows = []
    for row in history:
        sample = min(
            circularity_samples, key=lambda candidate: abs(candidate["time"] - row[0])
        )
        if abs(sample["time"] - row[0]) > 1e-9:
            raise ValueError(
                f"rising history/circularity time mismatch at t={row[0]}"
            )
        plot_rows.append(
            {
                "time": row[0],
                "iteration": sample["iteration"],
                "relative_volume_change": row[1],
                "center_of_mass_x": row[3],
                "rise_velocity_x": row[4],
                "dt": row[5],
                "circularity": sample["circularity"],
                "half_area": sample["half_area"],
                "half_perimeter": sample["half_perimeter"],
            }
        )
    write_csv(
        root / "plot_data.csv",
        REQUIRED_PLOT_COLUMNS["rising_bubble"],
        plot_rows,
    )
    final = history[-1]
    metrics = [
        metric("actual_terminal_time", final[0], "T0", "terminal", "last benchmark history time", "history.dat", time=final[0], origin="derived_from_benchmark_output"),
        metric("relative_volume_change_final", final[1], "1", "terminal", "(V-V0)/V0", "history.dat", time=final[0], origin="derived_from_benchmark_output"),
        metric("relative_volume_change_max_abs", max(abs(row[1]) for row in history), "1", "global", "max(abs((V-V0)/V0))", "history.dat", origin="derived_from_benchmark_output"),
        metric("center_of_mass_x_final", final[3], "L0", "terminal", "integral(x dV)/V", "history.dat", time=final[0], origin="derived_from_benchmark_output"),
        metric("rise_velocity_x_final", final[4], "L0/T0", "terminal", "integral(u_x dV)/V", "history.dat", time=final[0], origin="derived_from_benchmark_output"),
        metric("rise_velocity_x_max", max(row[4] for row in history), "L0/T0", "global", "max center-of-mass rise velocity", "history.dat", origin="derived_from_benchmark_output"),
        metric("interface_facets", len(facets), "segments", "terminal", "number of t=3 output_facets segments", "interface.dat", time=3.0, origin="derived_from_benchmark_output"),
        metric("circularity_min", min(circ_values), "1", "global", "sqrt(4*pi*A_full)/P_full", "circularity.csv", origin="repo_extension"),
        metric("circularity_final", circ_values[-1], "1", "terminal", "sqrt(4*pi*A_full)/P_full", "circularity.csv", time=3.0, origin="repo_extension"),
    ]
    artifacts = [
        artifact(root, "history.dat", "benchmark_raw", "history.dat", True),
        artifact(root, "interface.dat", "benchmark_raw", "interface.dat", True),
        artifact(root, "circularity.csv", "extension_raw", "circularity.csv", True),
    ]
    return metrics, artifacts


def stationary(root: Path, identity: dict[str, object]) -> tuple[list[dict], list[dict]]:
    series_path = root / "timeseries.dat"
    series = [row for row in numeric_rows(series_path, 3) if len(row) == 3]
    if not series:
        raise ValueError("stationary time series is empty")
    termination_path = root / "termination.csv"
    if not termination_path.is_file():
        raise ValueError("stationary termination.csv is missing")
    with termination_path.open(newline="", encoding="utf-8") as stream:
        termination_rows = list(csv.DictReader(stream))
    if len(termination_rows) != 1:
        raise ValueError("stationary termination.csv must contain exactly one row")
    terminal_tau = float(termination_rows[0]["actual_terminal_tau"])
    requested_tau = float(termination_rows[0]["requested_terminal_tau"])
    stop_reason = termination_rows[0]["reason"]
    if not math.isfinite(terminal_tau) or not math.isfinite(requested_tau):
        raise ValueError("stationary terminal tau is non-finite")
    series, duplicate_tau_samples_removed = normalize_duplicate_stationary_samples(series)
    require_strictly_increasing([row[0] for row in series], "stationary tau")
    official_rows = [
        row for row in numeric_rows(root / "runtime_and_terminal.log", 7)
        if len(row) == 7 and row[1] == 12000.0
    ]
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
    if stop_reason != "fixed_tau_limit":
        raise ValueError(f"stationary row did not use the fixed horizon: {stop_reason}")
    if abs(terminal_tau - requested_tau) > 1e-9:
        raise ValueError(
            "stationary row ended before its requested horizon: "
            f"requested={requested_tau} actual={terminal_tau}"
        )
    planned_tau = float(identity["tau_max"])
    if abs(requested_tau - planned_tau) > 1e-12:
        raise ValueError(
            "stationary termination/manifest horizon mismatch: "
            f"manifest={planned_tau} termination={requested_tau}"
        )
    if abs(series[-1][0] - terminal_tau) > 1e-9:
        raise ValueError(
            "stationary final sample/termination mismatch: "
            f"sample={series[-1][0]} termination={terminal_tau}"
        )
    milestones_path = root / "milestones.csv"
    if not milestones_path.is_file():
        raise ValueError("stationary milestones.csv is missing")
    with milestones_path.open(newline="", encoding="utf-8") as stream:
        milestone_rows = list(csv.DictReader(stream))
    milestones = {row.get("milestone"): row for row in milestone_rows}
    required_milestones = {"terminal"}
    if planned_tau >= 1.0:
        required_milestones.add("tau_1")
    if not required_milestones.issubset(milestones):
        raise ValueError(
            "stationary milestones are incomplete: "
            f"required={sorted(required_milestones)} actual={sorted(milestones)}"
        )

    milestone_fields = (
        "tau",
        "u_star",
        "shape_error_avg",
        "shape_error_rms",
        "shape_error_max",
        "official_style_ekmax",
        "active_provider_ekmax",
        "active_provider_samples",
    )
    parsed_milestones: dict[str, dict[str, float]] = {}
    for label in required_milestones:
        try:
            parsed = {
                field: float(milestones[label][field]) for field in milestone_fields
            }
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid stationary milestone {label}") from error
        if not all(math.isfinite(value) for value in parsed.values()):
            raise ValueError(f"non-finite stationary milestone {label}")
        if parsed["active_provider_samples"] <= 0:
            raise ValueError(f"stationary milestone {label} has no active provider cells")
        parsed_milestones[label] = parsed
    terminal_milestone = parsed_milestones["terminal"]
    if abs(terminal_milestone["tau"] - terminal_tau) > 1e-9:
        raise ValueError("stationary terminal milestone/termination mismatch")
    if "tau_1" in parsed_milestones and abs(parsed_milestones["tau_1"]["tau"] - 1.0) > 1e-9:
        raise ValueError("stationary tau=1 milestone has the wrong time")
    if identity.get("method") == "VOF-HF":
        active_definition = (
            "max(abs(active VOF height-function kappa-1/R_equiv)) "
            "over valid curvature cells"
        )
        active_samples_definition = "valid VOF height-function curvature cells"
        active_origin = "benchmark_diagnostic"
    else:
        active_definition = (
            "max(abs(active_integral_provider_kappa-1/R_equiv)) "
            "on integral.h insertion-site cells"
        )
        active_samples_definition = (
            "cells satisfying an integral.h diagonal-stress provider condition"
        )
        active_origin = "repo_extension"
    metrics = [
        metric("actual_terminal_tau", terminal_tau, "1", "terminal", "mu*t/D^2", termination_path.relative_to(root).as_posix(), time=terminal_tau, origin="repo_extension"),
        metric("termination_reason", stop_reason, "category", "terminal", "solver stop condition", termination_path.relative_to(root).as_posix(), time=terminal_tau, origin="repo_extension"),
        metric("duplicate_tau_samples_removed", duplicate_tau_samples_removed, "samples", "postprocess", "adjacent repeated logfile samples removed before strict time validation", series_path.name, origin="postprocess"),
        metric("level", int(official[0]), "level", "official_resolution", "grid refinement level", "official_terminal.dat"),
        metric("diameter_cells", 0.8 * int(identity["resolution"]), "cells_per_diameter", "official_resolution", "D*N", "manifest.json", origin="derived_from_benchmark_identity"),
        metric("laplace_number", official[1], "1", "identity", "sigma*rho*D/mu^2", "official_terminal.dat"),
        metric("u_star_final", terminal_milestone["u_star"], "1", "terminal", "max(|u|)*sqrt(D/sigma)", "milestones.csv", time=terminal_tau),
        metric("shape_error_avg", terminal_milestone["shape_error_avg"], "1", "terminal", "normf(c-c_ref).avg", "milestones.csv", time=terminal_tau),
        metric("shape_error_rms", terminal_milestone["shape_error_rms"], "1", "terminal", "normf(c-c_ref).rms", "milestones.csv", time=terminal_tau),
        metric("shape_error_max", terminal_milestone["shape_error_max"], "1", "terminal", "normf(c-c_ref).max", "milestones.csv", time=terminal_tau),
        metric("official_style_ekmax", terminal_milestone["official_style_ekmax"], "L0^-1", "terminal", "max(abs(height_function_kappa-1/R_equiv))", "milestones.csv", time=terminal_tau),
        metric("active_provider_ekmax", terminal_milestone["active_provider_ekmax"], "L0^-1", "terminal", active_definition, "milestones.csv", time=terminal_tau, origin=active_origin),
        metric("active_provider_samples", int(terminal_milestone["active_provider_samples"]), "cells", "terminal", active_samples_definition, "milestones.csv", time=terminal_tau, origin=active_origin),
        metric("official_style_relative_curvature_error", terminal_milestone["official_style_ekmax"] / 2.5, "1", "terminal", "official_style_ekmax/(1/R), R=0.4", "milestones.csv", time=terminal_tau, origin="derived"),
        metric("active_provider_relative_curvature_error", terminal_milestone["active_provider_ekmax"] / 2.5, "1", "terminal", "active_provider_ekmax/(1/R), R=0.4", "milestones.csv", time=terminal_tau, origin="derived"),
    ]
    if "tau_1" in parsed_milestones:
        tau_one = parsed_milestones["tau_1"]
        metrics.extend(
            [
                metric("u_star_tau_1", tau_one["u_star"], "1", "milestone", "max(|u|)*sqrt(D/sigma)", "milestones.csv", time=1.0),
                metric("shape_error_avg_tau_1", tau_one["shape_error_avg"], "1", "milestone", "normf(c-c_ref).avg", "milestones.csv", time=1.0),
                metric("shape_error_rms_tau_1", tau_one["shape_error_rms"], "1", "milestone", "normf(c-c_ref).rms", "milestones.csv", time=1.0),
                metric("shape_error_max_tau_1", tau_one["shape_error_max"], "1", "milestone", "normf(c-c_ref).max", "milestones.csv", time=1.0),
                metric("official_style_ekmax_tau_1", tau_one["official_style_ekmax"], "L0^-1", "milestone", "max(abs(height_function_kappa-1/R_equiv))", "milestones.csv", time=1.0),
                metric("active_provider_ekmax_tau_1", tau_one["active_provider_ekmax"], "L0^-1", "milestone", active_definition, "milestones.csv", time=1.0, origin=active_origin),
                metric("active_provider_samples_tau_1", int(tau_one["active_provider_samples"]), "cells", "milestone", active_samples_definition, "milestones.csv", time=1.0, origin=active_origin),
            ]
        )
    artifacts = [
        artifact(root, "timeseries.dat", "benchmark_raw", "timeseries.dat", True),
        artifact(root, "runtime_and_terminal.log", "benchmark_raw", "runtime_and_terminal.log", True),
        artifact(root, "official_terminal.dat", "benchmark_raw", "official_terminal.dat", True),
        artifact(root, termination_path.relative_to(root).as_posix(), "extension_raw", "termination.csv", True),
        artifact(root, milestones_path.relative_to(root).as_posix(), "extension_raw", "milestones.csv", True),
    ]
    return metrics, artifacts


def oscillating(root: Path, identity: dict[str, object]) -> tuple[list[dict], list[dict]]:
    fit_enabled = bool(identity.get("fit_enabled", True))
    kinetic_name = "timeseries.dat"
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
    require_strictly_increasing([row[0] for row in kinetic], "oscillating sample time")
    if any(row[1] < 0. for row in kinetic):
        raise ValueError("oscillating kinetic energy contains a negative value")
    last_sample_time = kinetic[-1][0]
    termination_path = root / "termination.csv"
    if not termination_path.is_file():
        raise ValueError("oscillating termination.csv is missing")
    with termination_path.open(newline="", encoding="utf-8") as stream:
        termination_rows = list(csv.DictReader(stream))
    if len(termination_rows) != 1:
        raise ValueError("oscillating termination.csv must contain exactly one row")
    terminal = float(termination_rows[0]["actual_terminal_time"])
    requested_terminal = float(termination_rows[0]["requested_terminal_time"])
    if termination_rows[0]["reason"] != "fixed_time_limit":
        raise ValueError("oscillating row has the wrong termination reason")
    if (
        not math.isfinite(terminal)
        or requested_terminal != 1.0
        or terminal < requested_terminal
        or terminal - requested_terminal > 0.01
        or last_sample_time < 0.999
        or last_sample_time > requested_terminal
    ):
        raise ValueError(
            "oscillating row did not reach its official horizon: "
            f"requested={requested_terminal} terminal={terminal} "
            f"last_sample={last_sample_time}"
        )
    metrics: list[dict] = [
        metric("actual_terminal_time", terminal, "T0", "terminal", "terminal solver-state time", "termination.csv", time=terminal, origin="repo_extension"),
        metric("last_kinetic_energy_sample_time", last_sample_time, "T0", "terminal_sampling", "last benchmark kinetic-energy sample time", kinetic_name, time=last_sample_time, origin="derived_from_benchmark_output"),
        metric("diameter_cells", identity["cells_per_diameter"], "cells_per_diameter", "official_resolution", "D/L0*N", "manifest.json", origin="benchmark_identity"),
        metric("max_kinetic_energy", max(row[1] for row in kinetic), "energy", "global", "max(K(t))", kinetic_name, origin="derived_from_benchmark_output"),
    ]
    artifacts: list[dict] = [
        artifact(root, kinetic_name, "benchmark_raw", "timeseries.dat", True),
        artifact(root, "termination.csv", "extension_raw", "termination.csv", True),
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
        error_rows = numeric_rows(root / "error.dat", 3)
        laplace_rows = numeric_rows(root / "laplace.dat", 3)
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
                metric("frequency_error_signed", error_rows[0][1], "1", "global", "c/(2*omega0)-1", "error.dat"),
                metric("frequency_error_abs_percent", abs(error_rows[0][1]) * 100.0, "%", "global", "100*abs(c/(2*omega0)-1)", "error.dat", origin="derived"),
                metric("equivalent_laplace", laplace_rows[0][1], "1", "global", "30^2/(b^2*D^3)", "laplace.dat"),
                metric("fit_damping_regime", "damped" if fit_values["b"] > 0. else "nonphysical_growth", "category", "fit_quality", "sign(b): b>0 is exponential damping", "fit.log", origin="derived"),
            ]
        )
        artifacts.extend(
            [
                artifact(root, "fit_curve.dat", "benchmark_raw", "fit_curve.dat", True),
                artifact(root, "fit.log", "benchmark_raw", "fit.log", True),
                artifact(root, "error.dat", "benchmark_raw", "error.dat", True),
                artifact(root, "laplace.dat", "benchmark_raw", "laplace.dat", True),
                artifact(root, "fit_summary.dat", "benchmark_raw", "fit_summary.dat", True),
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


def parse_provider_stats(values: dict[str, object]) -> dict[str, int | float]:
    if set(values) != set(PROVIDER_STATS_FIELDS):
        raise ValueError(
            "provider stats fields mismatch: "
            f"expected={PROVIDER_STATS_FIELDS} actual={sorted(values)}"
        )
    parsed: dict[str, int | float] = {}
    for name in PROVIDER_STATS_FIELDS:
        try:
            value = int(values[name]) if name in PROVIDER_INTEGER_FIELDS else float(values[name])
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid provider stat {name}={values[name]!r}") from error
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"non-finite provider stat {name}")
        parsed[name] = value
    return parsed


def parse_provider_stats_line(line: str) -> dict[str, int | float]:
    values: dict[str, object] = {}
    for item in line.split()[1:]:
        name, value = item.split("=", 1)
        values[name] = value
    return parse_provider_stats(values)


def provider_runtime_metrics(
    root: Path, identity: dict[str, object]
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    runtime_names = (
        "official_error.dat",
        "interface.dat",
        "runtime_and_terminal.log",
        "runtime.stderr.txt",
    )
    matches: list[tuple[Path, str]] = []
    for name in runtime_names:
        candidate = root / name
        if not candidate.is_file():
            continue
        for line in candidate.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith("kappa_offset_provider_stats "):
                matches.append((candidate, line))

    stats_path = root / "provider_stats.csv"
    existing_stats: dict[str, int | float] | None = None
    if stats_path.is_file():
        with stats_path.open(newline="", encoding="utf-8") as stream:
            existing_rows = list(csv.DictReader(stream))
        if len(existing_rows) != 1:
            raise ValueError("provider_stats.csv must contain exactly one row")
        existing_stats = parse_provider_stats(existing_rows[0])

    manifest_stats = identity.get("provider_stats")
    parsed_manifest_stats = (
        parse_provider_stats(manifest_stats)
        if isinstance(manifest_stats, dict)
        else None
    )
    method = identity.get("method")
    if method != "NN":
        if matches or existing_stats is not None or parsed_manifest_stats is not None:
            raise ValueError("non-NN row unexpectedly emitted provider runtime stats")
        return [], None
    if len(matches) > 1:
        raise ValueError(f"expected one provider stats row, found {len(matches)}")

    parsed_line_stats = parse_provider_stats_line(matches[0][1]) if matches else None
    candidates = [
        values
        for values in (existing_stats, parsed_manifest_stats, parsed_line_stats)
        if values is not None
    ]
    if not candidates:
        raise ValueError("NN row is missing kappa_offset_provider_stats")
    stats = candidates[0]
    if any(values != stats for values in candidates[1:]):
        raise ValueError("provider stats disagree across runtime, manifest, and CSV")
    if int(stats["evaluations"]) <= 0:
        raise ValueError("NN provider was compiled but never evaluated")

    # Keep benchmark/runtime channels scientifically pure.  The provider line
    # is metadata and lives in exactly one row artifact after this extraction.
    if matches:
        candidate, matched_line = matches[0]
        original = candidate.read_text(encoding="utf-8", errors="replace")
        kept = [
            line
            for line in original.splitlines(keepends=True)
            if line.rstrip("\r\n") != matched_line
        ]
        candidate.write_text("".join(kept), encoding="utf-8")
    write_csv(stats_path, PROVIDER_STATS_FIELDS, [stats])

    return [], artifact(
        root,
        "provider_stats.csv",
        "extension_raw",
        "provider_stats.csv",
        True,
        PROVIDER_STATS_FIELDS,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("row_dir", type=Path)
    args = parser.parse_args()
    root = args.row_dir.resolve()
    manifest_path = root / "manifest.json"
    identity = json.loads(manifest_path.read_text(encoding="utf-8"))
    case = str(identity.get("case_id") or identity.get("case"))
    benchmark = str(identity.get("benchmark") or case)
    provider_metrics, provider_artifact = provider_runtime_metrics(root, identity)
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

    metrics.extend(provider_metrics)
    if provider_artifact is not None:
        artifacts.append(provider_artifact)

    write_csv(root / "metrics.csv", METRIC_FIELDS, metrics)
    artifacts.extend(
        [
            artifact(root, "metrics.csv", "derived_metrics", "metrics.csv", True),
            artifact(root, "plot_data.csv", "derived_plot", "plot_data.csv", True),
        ]
    )
    benchmark_outputs = [
        item
        for item in artifacts
        if item["role"] in {"benchmark_raw", "official_reference"}
    ]
    actual_output_names = {str(item["publish_name"]) for item in benchmark_outputs}
    expected_output_names = EXPECTED_BENCHMARK_OUTPUT_NAMES[case]
    if case == "oscillating_droplet" and not identity.get("fit_enabled", True):
        expected_output_names = {"timeseries.dat"}
    missing_output_names = sorted(expected_output_names - actual_output_names)
    if missing_output_names:
        raise ValueError(
            f"benchmark output coverage incomplete for {case}: {missing_output_names}"
        )
    metric_names = {str(item["metric"]) for item in metrics}
    missing_metrics = sorted(REQUIRED_METRICS[case] - metric_names)
    with (root / "plot_data.csv").open(newline="", encoding="utf-8") as stream:
        plot_columns = list(csv.DictReader(stream).fieldnames or [])
    if missing_metrics or plot_columns != REQUIRED_PLOT_COLUMNS[case]:
        raise ValueError(
            f"analysis coverage incomplete for {case}: "
            f"missing_metrics={missing_metrics} plot_columns={plot_columns}"
        )
    contract = {
        "schema_version": 1,
        "case": case,
        "benchmark": benchmark,
        "method": identity.get("method"),
        "resolution": identity.get("N") or identity.get("resolution"),
        "imax": identity.get("redistance_imax") if "redistance_imax" in identity else identity.get("imax"),
        "model_id": identity.get("model_name") or identity.get("model"),
        "experiment_role": identity.get("experiment_role"),
        "grid_role": identity.get("grid_role"),
        "model_resolution": (
            identity.get("N") or identity.get("resolution")
            if (identity.get("model_name") or identity.get("model"))
            else None
        ),
        "checkpoint_sha256": identity.get("checkpoint_sha256"),
        "benchmark_output_coverage_complete": not missing_output_names,
        "benchmark_output_count": len(benchmark_outputs),
        "expected_benchmark_output_names": sorted(expected_output_names),
        "missing_benchmark_output_names": missing_output_names,
        "analysis_ready": True,
        "required_metric_names": sorted(REQUIRED_METRICS[case]),
        "metric_names": sorted(metric_names),
        "plot_columns": plot_columns,
        "artifacts": artifacts,
    }
    contract_path = root / "scientific_artifacts.json"
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity["scientific_artifacts_schema_version"] = 1
    identity["scientific_artifacts_sha256"] = sha256(contract_path)
    identity["benchmark_output_coverage_complete"] = contract[
        "benchmark_output_coverage_complete"
    ]
    identity["analysis_ready"] = True
    manifest_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"case": case, "artifacts": len(artifacts), "metrics": len(metrics)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
