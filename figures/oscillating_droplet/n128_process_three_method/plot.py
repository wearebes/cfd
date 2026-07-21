#!/usr/bin/env python3
"""Render a three-method, phase-resolved oscillating-droplet contour plate."""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-oscillating-mpl")
)

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection


mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "font.size": 7,
    "axes.linewidth": 0.7,
})

METHODS = ("clsvof", "nn", "vof_hf")
METHOD_LABELS = {"clsvof": "CLSVOF", "nn": "NN", "vof_hf": "VOF-HF"}
METHOD_COLORS = {"clsvof": "#4D4D4D", "nn": "#0072B2", "vof_hf": "#D55E00"}
PHASE_LABELS = ("0", "T/4", "T/2", "3T/4", "T")


def read_source(path: Path):
    grouped: dict[tuple[str, int], list[list[tuple[float, float]]]] = defaultdict(list)
    times: dict[int, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            method = row["method"]
            phase = int(row["phase_index"])
            grouped[(method, phase)].append([
                (float(row["x1"]), float(row["y1"])),
                (float(row["x2"]), float(row["y2"])),
            ])
            times[phase] = float(row["actual_time"])
    expected = {(method, phase) for method in METHODS for phase in range(5)}
    if set(grouped) != expected:
        raise ValueError(f"incomplete process source: {set(grouped) ^ expected}")
    return grouped, times


def main() -> int:
    output = Path(__file__).resolve().parent
    source = output / "process_contours.csv"
    grouped, times = read_source(source)
    fig, axes = plt.subplots(
        3, 5, figsize=(183 / 25.4, 86 / 25.4),
        sharex=True, sharey=True,
    )
    for row_index, method in enumerate(METHODS):
        for phase_index in range(5):
            ax = axes[row_index, phase_index]
            collection = LineCollection(
                grouped[(method, phase_index)], colors=METHOD_COLORS[method],
                linewidths=0.85, capstyle="round", joinstyle="round",
            )
            ax.add_collection(collection)
            ax.set_xlim(-0.115, 0.115)
            ax.set_ylim(-0.115, 0.115)
            ax.set_aspect("equal", adjustable="box")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            if row_index == 0:
                ax.set_title(
                    rf"${PHASE_LABELS[phase_index]}$" + "\n" + rf"$t={times[phase_index]:.4f}$",
                    fontsize=6.8, pad=5,
                )
            if phase_index == 0:
                ax.text(
                    -0.20, 0.5, METHOD_LABELS[method], transform=ax.transAxes,
                    rotation=90, ha="center", va="center", fontsize=7,
                    fontweight="bold", color=METHOD_COLORS[method],
                )
    fig.text(
        0.055, 0.975, "N128 oscillating-droplet process",
        ha="left", va="top", fontsize=7.4, fontweight="bold",
    )
    fig.text(
        0.945, 0.975, "CLSVOF and NN: imax = 3",
        ha="right", va="top", fontsize=6.4, color="#444444",
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.85, bottom=0.04, wspace=0.08, hspace=0.12)
    figure_path = output / "n128_process_three_method.png"
    fig.savefig(
        figure_path, dpi=600,
        facecolor="white", transparent=False,
    )
    plt.close(fig)
    qa = {
        "schema_version": 1,
        "figure": figure_path.name,
        "backend": "Python/matplotlib",
        "final_width_mm": 183,
        "final_height_mm": 86,
        "dpi": 600,
        "layout": "three method rows by five theoretical phase columns",
        "source_data": source.name,
        "image_adjustments": "none",
    }
    (output / "qa_manifest.json").write_text(
        json.dumps(qa, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
