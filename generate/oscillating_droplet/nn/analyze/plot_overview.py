#!/usr/bin/env python3
"""Create the Python-only publication overview and descriptive landscape."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams.update({
    "font.size": 7,
    "axes.linewidth": 0.8,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "legend.frameon": False,
})

NATIVE = "#4D4D4D"
NN = "#0F4D92"
STANDARD = "#B64342"
MOMENTUM = "#42949E"
COMPRESSIBLE = "#9A4D8E"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_ke(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, usecols=(0, 1))
    return data[:, 0], data[:, 1]


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.13, 1.04, label, transform=ax.transAxes, fontsize=8,
            fontweight="bold", ha="left", va="bottom")


def save_bundle(fig: plt.Figure, stem: Path) -> None:
    export = {"bbox_inches": "tight", "facecolor": "white", "transparent": False}
    fig.savefig(stem.with_suffix(".png"), dpi=600, **export)


def overview(result_root: Path, output: Path) -> None:
    comparison = read_csv(result_root / "comparison.csv")
    rows = {(int(row["level"]), row["method_id"]): row for row in comparison}
    landscape = read_csv(result_root / "landscape_5method.csv")
    standards = {
        int(row["level"]): row for row in landscape if row["method"] == "Standard VOF-HF"
    }

    width = 183 / 25.4
    fig = plt.figure(figsize=(width, 5.25))
    fig.patch.set_facecolor("white")
    grid = fig.add_gridspec(2, 2, height_ratios=(1.35, 1.0), hspace=0.38, wspace=0.32)
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1]),
            fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])]

    for ax, level, label in zip(axes[:2], (6, 7), ("a", "b"), strict=True):
        native_dir = result_root / f"level_{level}/clsvof"
        nn_dir = result_root / f"level_{level}/nn"
        tn, kn = read_ke(native_dir / f"k-{level}")
        tm, km = read_ke(nn_dir / f"k-{level}")
        ax.plot(tn, kn * 1e4, color=NATIVE, lw=1.05, label="CLSVOF native")
        ax.plot(tm, km * 1e4, color=NN, lw=1.05, label="CLSVOF NN cell-offset")
        ax.set_xlim(0, 1)
        ax.set_xlabel("Time")
        ax.set_ylabel(r"Kinetic energy ($\times 10^{-4}$)")
        ax.text(0.98, 0.95, f"N = {1 << level}", transform=ax.transAxes,
                ha="right", va="top", color="#272727",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 1.5})
        add_panel_label(ax, label)
    handles = [
        Line2D([0], [0], color=NATIVE, lw=1.4),
        Line2D([0], [0], color=NN, lw=1.4),
        Line2D([0], [0], marker="D", markerfacecolor="white", markeredgecolor=STANDARD,
               color="none", markersize=4.5),
    ]
    labels = ["CLSVOF native", "CLSVOF NN cell-offset", "Standard VOF-HF reference"]
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.995),
               ncol=3, handlelength=2.4, columnspacing=1.5)

    x = np.arange(2)
    native_b = np.array([float(rows[(level, "CLSVOF_NATIVE")]["b"]) for level in (6, 7)])
    nn_b = np.array([float(rows[(level, "CLSVOF_NN_CELL_OFFSET")]["b"]) for level in (6, 7)])
    native_b_se = np.array([float(rows[(level, "CLSVOF_NATIVE")]["b_stderr"]) for level in (6, 7)])
    nn_b_se = np.array([float(rows[(level, "CLSVOF_NN_CELL_OFFSET")]["b_stderr"]) for level in (6, 7)])
    standard_b = np.array([float(standards[level]["b"]) for level in (6, 7)])
    ax = axes[2]
    offset = 0.16
    ax.errorbar(x - offset, native_b, yerr=native_b_se, fmt="o", ms=5,
                color=NATIVE, capsize=2, lw=1, label="CLSVOF native")
    ax.errorbar(x + offset, nn_b, yerr=nn_b_se, fmt="o", ms=5,
                color=NN, capsize=2, lw=1, label="CLSVOF NN")
    ax.scatter(x, standard_b, marker="D", s=25, facecolors="white",
               edgecolors=STANDARD, linewidths=1, label="Standard VOF-HF reference", zorder=3)
    for index in range(2):
        ax.plot([x[index] - offset, x[index] + offset], [native_b[index], nn_b[index]],
                color="#C7C7C7", lw=0.7, zorder=0)
    ax.axhline(0, color="#A0A0A0", lw=0.7, ls="--")
    ax.set_xticks(x, ["N64", "N128"])
    ax.set_ylabel(r"Damping coefficient $b$")
    ymax = max(native_b.max(), nn_b.max(), standard_b.max())
    ax.set_ylim(min(-0.03, nn_b.min() - 0.12 * max(ymax, 0.1)), ymax * 1.22 + 0.01)
    add_panel_label(ax, "c")

    native_f = np.array([float(rows[(level, "CLSVOF_NATIVE")]["frequency_error_abs_percent"])
                         for level in (6, 7)])
    nn_f = np.array([float(rows[(level, "CLSVOF_NN_CELL_OFFSET")]["frequency_error_abs_percent"])
                     for level in (6, 7)])
    standard_f = np.array([float(standards[level]["frequency_error_abs_percent"])
                           for level in (6, 7)])
    ax = axes[3]
    ax.plot(x, native_f, color=NATIVE, marker="o", ms=5, lw=1.1, label="CLSVOF native")
    ax.plot(x, nn_f, color=NN, marker="o", ms=5, lw=1.1, label="CLSVOF NN")
    ax.scatter(x, standard_f, marker="D", s=25, facecolors="white",
               edgecolors=STANDARD, linewidths=1, label="Standard VOF-HF reference", zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(x, ["N64", "N128"])
    ax.set_ylabel("Absolute frequency error (%)")
    ax.grid(axis="y", which="both", color="#E5E5E5", lw=0.5)
    add_panel_label(ax, "d")

    fig.subplots_adjust(top=0.90, bottom=0.11, left=0.09, right=0.98)
    save_bundle(fig, output / "oscillating_droplet_nn_overview")
    plt.close(fig)

    kinetic_fig, kinetic_axes = plt.subplots(1, 2, figsize=(183 / 25.4, 2.8), sharey=True)
    kinetic_fig.patch.set_facecolor("white")
    for ax, level, label in zip(kinetic_axes, (6, 7), ("a", "b"), strict=True):
        for method_dir, color, method_label in (
            ("clsvof", NATIVE, "CLSVOF native"),
            ("nn", NN, "CLSVOF NN cell-offset"),
        ):
            time, energy = read_ke(result_root / f"level_{level}/{method_dir}/k-{level}")
            ax.plot(time, energy * 1e4, color=color, lw=1.05, label=method_label)
        ax.set_xlim(0, 1)
        ax.set_xlabel("Time")
        ax.set_title(f"N = {1 << level}", fontsize=7)
        add_panel_label(ax, label)
    kinetic_axes[0].set_ylabel(r"Kinetic energy ($\times 10^{-4}$)")
    kinetic_fig.legend(*kinetic_axes[0].get_legend_handles_labels(), loc="upper center",
                       bbox_to_anchor=(0.5, 1.01), ncol=2)
    kinetic_fig.tight_layout(rect=(0, 0, 1, 0.90))
    save_bundle(kinetic_fig, output / "kinetic_energy_native_vs_nn")
    plt.close(kinetic_fig)

    damping_fig, damping_ax = plt.subplots(figsize=(89 / 25.4, 2.8))
    damping_fig.patch.set_facecolor("white")
    damping_ax.errorbar(x - offset, native_b, yerr=native_b_se, fmt="o", ms=5,
                        color=NATIVE, capsize=2, lw=1, label="CLSVOF native")
    damping_ax.errorbar(x + offset, nn_b, yerr=nn_b_se, fmt="o", ms=5,
                        color=NN, capsize=2, lw=1, label="CLSVOF NN")
    damping_ax.scatter(x, standard_b, marker="D", s=25, facecolors="white",
                       edgecolors=STANDARD, linewidths=1, label="Standard VOF-HF ref.")
    damping_ax.axhline(0, color="#A0A0A0", lw=0.7, ls="--")
    damping_ax.set_xticks(x, ["N64", "N128"])
    damping_ax.set_ylabel(r"Damping coefficient $b$")
    damping_ax.legend(fontsize=5.5)
    damping_fig.tight_layout()
    save_bundle(damping_fig, output / "damping_native_vs_nn")
    plt.close(damping_fig)

    frequency_fig, frequency_ax = plt.subplots(figsize=(89 / 25.4, 2.8))
    frequency_fig.patch.set_facecolor("white")
    frequency_ax.plot(x, native_f, color=NATIVE, marker="o", ms=5, lw=1.1,
                      label="CLSVOF native")
    frequency_ax.plot(x, nn_f, color=NN, marker="o", ms=5, lw=1.1,
                      label="CLSVOF NN")
    frequency_ax.scatter(x, standard_f, marker="D", s=25, facecolors="white",
                         edgecolors=STANDARD, linewidths=1, label="Standard VOF-HF ref.")
    frequency_ax.set_yscale("log")
    frequency_ax.set_xticks(x, ["N64", "N128"])
    frequency_ax.set_ylabel("Absolute frequency error (%)")
    frequency_ax.grid(axis="y", which="both", color="#E5E5E5", lw=0.5)
    frequency_ax.legend(fontsize=5.5)
    frequency_fig.tight_layout()
    save_bundle(frequency_fig, output / "frequency_error_native_vs_nn")
    plt.close(frequency_fig)


def landscape_plot(result_root: Path, output: Path) -> None:
    rows = read_csv(result_root / "landscape_5method.csv")
    style = {
        "Standard VOF-HF": (STANDARD, "D"),
        "Momentum": (MOMENTUM, "s"),
        "Compressible": (COMPRESSIBLE, "^"),
        "CLSVOF native": (NATIVE, "o"),
        "CLSVOF NN cell-offset": (NN, "o"),
    }
    fig, ax = plt.subplots(figsize=(89 / 25.4, 3.1))
    fig.patch.set_facecolor("white")
    for method, (color, marker) in style.items():
        group = sorted((row for row in rows if row["method"] == method), key=lambda row: int(row["level"]))
        x = np.array([float(row["frequency_error_abs_percent"]) for row in group])
        y = np.array([float(row["b"]) for row in group])
        ax.plot(x, y, color=color, marker=marker, ms=4, lw=0.9, label=method)
        for row, xv, yv in zip(group, x, y, strict=True):
            ax.annotate(f"N{row['N']}", (xv, yv), xytext=(3, 2), textcoords="offset points",
                        fontsize=5.5, color=color)
    ax.set_xscale("log")
    ax.set_xlabel("Absolute frequency error (%)")
    ax.set_ylabel(r"Damping coefficient $b$")
    ax.axhline(0, color="#A0A0A0", lw=0.7, ls="--")
    ax.grid(which="both", color="#E8E8E8", lw=0.5)
    ax.legend(fontsize=5.5, loc="best")
    fig.tight_layout()
    save_bundle(fig, output / "landscape_b_vs_freq_5method")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    overview(args.result_root.resolve(), args.output.resolve())
    landscape_plot(args.result_root.resolve(), args.output.resolve())
    (args.output / "PLOT_NOTES.md").write_text(
        "# Plot notes\n\n"
        "- Backend: Python/matplotlib only.\n"
        "- Image delivery: one opaque-white 600-dpi PNG per figure; no PDF, SVG, or TIFF unless explicitly requested.\n"
        "- Error bars in damping are gnuplot asymptotic one-standard-error fit estimates, not run-to-run variability.\n"
        "- Standard VOF-HF points are descriptive matched-resolution references; causal claims use only native versus NN CLSVOF.\n"
        "- Only N64/N128 have matched NN checkpoints; no convergence order is inferred.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
