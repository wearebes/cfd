#!/usr/bin/env python3
"""Three-method N128 oscillating-droplet comparison."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-oscillating-mpl")
)

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "font.size": 7,
    "axes.linewidth": 0.8,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "xtick.major.size": 3.0,
    "ytick.major.size": 3.0,
    "legend.frameon": False,
})

METHODS = ("clsvof", "nn", "vof_hf")
STYLES = {
    "clsvof": {
        "color": "#4D4D4D", "marker": "o", "linestyle": "-", "label": "CLSVOF"
    },
    "nn": {
        "color": "#0072B2", "marker": "s", "linestyle": "-", "label": "NN"
    },
    "vof_hf": {
        "color": "#D55E00", "marker": "^", "linestyle": "--", "label": "VOF-HF"
    },
}


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "generate").is_dir() and (parent / "dataset").is_dir():
            return parent
    raise RuntimeError("Could not locate repository root")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def theoretical_kinetic_frequency() -> float:
    diameter = 0.2
    mode = 2.0
    sigma = 1.0
    rho_liquid = 1.0
    rho_gas = 1.0e-3
    radius = diameter / 2.0
    omega0 = math.sqrt(
        (mode**3 - mode) * sigma / ((rho_liquid + rho_gas) * radius**3)
    )
    return 2.0 * omega0


def load_trace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, usecols=(0, 1))
    if data.ndim != 2 or data.shape[1] != 2:
        raise ValueError(f"Unexpected trace shape in {path}: {data.shape}")
    if not np.all(np.isfinite(data)) or np.any(data[:, 1] < 0.0):
        raise ValueError(f"Invalid kinetic-energy values in {path}")
    if not np.all(np.diff(data[:, 0]) > 0.0):
        raise ValueError(f"Time is not strictly increasing in {path}")
    if data[-1, 0] < 0.999:
        raise ValueError(f"Trace does not reach t=1 in {path}")
    return data[:, 0], data[:, 1]


def extract_peaks(
    time: np.ndarray, energy: np.ndarray, c0: float
) -> tuple[np.ndarray, np.ndarray]:
    period = 2.0 * math.pi / c0
    peak_times: list[float] = []
    peak_energies: list[float] = []
    index = 0
    while True:
        center = (math.pi + 2.0 * math.pi * index) / c0
        if center > 0.99:
            break
        mask = np.abs(time - center) <= 0.18 * period
        if np.any(mask):
            local_indices = np.flatnonzero(mask)
            peak_index = local_indices[int(np.argmax(energy[mask]))]
            peak_times.append(float(time[peak_index]))
            peak_energies.append(float(energy[peak_index]))
        index += 1
    if len(peak_times) < 4:
        raise ValueError("Too few peaks for phase diagnostics")
    return np.asarray(peak_times), np.asarray(peak_energies)


def cumulative_frequency_error(peak_times: np.ndarray, c0: float) -> np.ndarray:
    error = np.full(len(peak_times), np.nan)
    for count in range(2, len(peak_times) + 1):
        period = float(
            np.polyfit(np.arange(count, dtype=float), peak_times[:count], 1)[0]
        )
        c_estimate = 2.0 * math.pi / period
        error[count - 1] = abs(c_estimate / c0 - 1.0) * 100.0
    return error


def diagnostics_for(
    time: np.ndarray, energy: np.ndarray, c0: float
) -> dict[str, np.ndarray | float]:
    peak_time, peak_energy = extract_peaks(time, energy, c0)
    normalized = peak_energy / peak_energy[0]
    b_envelope = -float(np.polyfit(peak_time, np.log(peak_energy), 1)[0])
    frequency_error = cumulative_frequency_error(peak_time, c0)
    return {
        "peak_time": peak_time,
        "peak_energy": peak_energy,
        "normalized_peak_energy": normalized,
        "frequency_error": frequency_error,
        "b_envelope": b_envelope,
        "final_frequency_error": float(frequency_error[-1]),
        "final_peak_retention": float(normalized[-1]),
    }


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.10, 1.025, label, transform=ax.transAxes, fontsize=8,
        fontweight="bold", va="bottom", ha="left", clip_on=False,
    )


def write_source_data(
    output: Path,
    traces: dict[str, tuple[np.ndarray, np.ndarray]],
    diagnostics: dict[str, dict[str, np.ndarray | float]],
) -> None:
    with (output / "trace_source.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("method", "time", "kinetic_energy")
        )
        writer.writeheader()
        for method in METHODS:
            time, energy = traces[method]
            writer.writerows(
                {"method": method, "time": float(t), "kinetic_energy": float(k)}
                for t, k in zip(time, energy, strict=True)
            )

    cycle_fields = (
        "method", "peak_index", "peak_time", "peak_energy",
        "normalized_peak_energy", "cumulative_frequency_error_abs_percent",
    )
    with (output / "cycle_source.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=cycle_fields)
        writer.writeheader()
        for method in METHODS:
            values = diagnostics[method]
            peak_time = np.asarray(values["peak_time"])
            peak_energy = np.asarray(values["peak_energy"])
            normalized = np.asarray(values["normalized_peak_energy"])
            frequency = np.asarray(values["frequency_error"])
            for index in range(len(peak_time)):
                writer.writerow({
                    "method": method,
                    "peak_index": index + 1,
                    "peak_time": float(peak_time[index]),
                    "peak_energy": float(peak_energy[index]),
                    "normalized_peak_energy": float(normalized[index]),
                    "cumulative_frequency_error_abs_percent": (
                        "" if not np.isfinite(frequency[index])
                        else float(frequency[index])
                    ),
                })

    with (output / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "method", "peak_envelope_b", "final_peak_retention",
                "final_cumulative_frequency_error_abs_percent", "peak_count",
            ),
        )
        writer.writeheader()
        for method in METHODS:
            values = diagnostics[method]
            writer.writerow({
                "method": method,
                "peak_envelope_b": values["b_envelope"],
                "final_peak_retention": values["final_peak_retention"],
                "final_cumulative_frequency_error_abs_percent":
                    values["final_frequency_error"],
                "peak_count": len(np.asarray(values["peak_time"])),
            })


def plot(
    traces: dict[str, tuple[np.ndarray, np.ndarray]],
    diagnostics: dict[str, dict[str, np.ndarray | float]],
    output: Path,
) -> None:
    fig = plt.figure(figsize=(183 / 25.4, 104 / 25.4))
    grid = fig.add_gridspec(2, 2, height_ratios=(1.45, 1.0), hspace=0.40, wspace=0.34)
    ax_a = fig.add_subplot(grid[0, :])
    ax_b = fig.add_subplot(grid[1, 0])
    ax_c = fig.add_subplot(grid[1, 1])

    for method in METHODS:
        time, energy = traces[method]
        style = STYLES[method]
        ax_a.plot(
            time, energy * 1.0e4, color=style["color"],
            ls=style["linestyle"], lw=0.9, alpha=0.95,
        )
    ax_a.set_xlim(0.0, 1.0)
    ax_a.set_ylim(bottom=0.0)
    ax_a.set_yticks((0, 2, 4, 6))
    ax_a.set_ylabel(r"Kinetic energy, $K$ ($\times 10^{-4}$)")
    ax_a.set_xlabel(r"Dimensionless time, $t$")
    add_panel_label(ax_a, "a")

    ax_b.axhline(1.0, color="#777777", lw=0.8, ls=(0, (4, 2)), zorder=1)
    all_retention: list[float] = [1.0]
    for method in METHODS:
        values = diagnostics[method]
        style = STYLES[method]
        peak_time = np.asarray(values["peak_time"])
        normalized = np.asarray(values["normalized_peak_energy"])
        all_retention.extend(normalized.tolist())
        ax_b.plot(
            peak_time, normalized, color=style["color"], ls=style["linestyle"],
            lw=0.9, marker=style["marker"], ms=3.0, markerfacecolor="white",
            markeredgewidth=0.75,
        )
    ax_b.set_xlim(0.0, 1.0)
    ax_b.set_ylim(min(all_retention) - 0.025, max(all_retention) + 0.018)
    ax_b.set_ylabel(r"Peak retention, $K_{p,i}/K_{p,1}$")
    ax_b.set_xlabel(r"Dimensionless time, $t$")
    ax_b.annotate(
        "ideal = 1", xy=(0.61, 1.0), xytext=(0, -3), textcoords="offset points",
        ha="center", va="top", color="#555555",
    )
    add_panel_label(ax_b, "b")

    max_error = 0.0
    for method in METHODS:
        values = diagnostics[method]
        style = STYLES[method]
        peak_time = np.asarray(values["peak_time"])
        frequency = np.asarray(values["frequency_error"])
        valid = np.isfinite(frequency)
        max_error = max(max_error, float(np.nanmax(frequency)))
        ax_c.plot(
            peak_time[valid], frequency[valid], color=style["color"],
            ls=style["linestyle"], lw=0.9, marker=style["marker"], ms=3.0,
            markerfacecolor="white", markeredgewidth=0.75,
        )
    ax_c.set_xlim(0.0, 1.0)
    ax_c.set_ylim(0.0, max_error * 1.15)
    ax_c.set_ylabel("Cumulative absolute\nfrequency error (%)")
    ax_c.set_xlabel(r"Dimensionless time, $t$")
    add_panel_label(ax_c, "c")

    for ax in (ax_a, ax_b, ax_c):
        ax.tick_params(direction="out")

    handles = [
        Line2D(
            [0], [0], color=STYLES[method]["color"],
            ls=STYLES[method]["linestyle"], lw=1.0,
            marker=STYLES[method]["marker"], markerfacecolor="white",
            markersize=3.5, label=STYLES[method]["label"],
        )
        for method in METHODS
    ]
    fig.text(
        0.08, 0.975, "N128  |  CLSVOF and NN: imax = 3",
        ha="left", va="top", fontsize=7, fontweight="bold",
    )
    fig.legend(
        handles=handles, loc="upper right", bbox_to_anchor=(0.95, 0.987),
        ncol=3, handlelength=2.1, columnspacing=1.0,
    )
    fig.subplots_adjust(left=0.10, right=0.97, top=0.90, bottom=0.11)
    fig.savefig(
        output / "n128_imax3_three_method.png", dpi=600,
        facecolor="white", transparent=False,
    )
    plt.close(fig)


def main() -> int:
    root = repository_root()
    output = Path(__file__).resolve().parent
    paths = {
        "clsvof": root / "dataset/oscillating_droplet/N0128/imax03/clsvof/timeseries.dat",
        "nn": root / "dataset/oscillating_droplet/N0128/imax03/nn/timeseries.dat",
        "vof_hf": root / "dataset/oscillating_droplet/reference/standard/N0128.dat",
    }
    traces = {method: load_trace(path) for method, path in paths.items()}
    c0 = theoretical_kinetic_frequency()
    diagnostics = {
        method: diagnostics_for(*traces[method], c0) for method in METHODS
    }
    write_source_data(output, traces, diagnostics)
    plot(traces, diagnostics, output)
    qa = {
        "schema_version": 1,
        "figure": "n128_imax3_three_method.png",
        "backend": "Python/matplotlib",
        "final_width_mm": 183,
        "final_height_mm": 104,
        "dpi": 600,
        "methods": [STYLES[method]["label"] for method in METHODS],
        "condition_note": "imax=3 applies to CLSVOF and NN only; VOF-HF has no redistance parameter",
        "theoretical_kinetic_frequency": c0,
        "source_sha256": {method: sha256(path) for method, path in paths.items()},
    }
    (output / "qa_manifest.json").write_text(
        json.dumps(qa, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
