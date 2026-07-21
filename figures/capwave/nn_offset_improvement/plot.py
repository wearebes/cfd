#!/usr/bin/env python3
"""Publication heatmap of the NN cell-offset effect for capillary waves."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-capwave-mpl"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import Rectangle


HERE = Path(__file__).resolve().parent
SOURCE_DATA = HERE / "source_data.csv"
NEGATIVE = "#D55E00"
POSITIVE = "#0072B2"
NEUTRAL = "#F7F7F4"


def main() -> None:
    data = pd.read_csv(SOURCE_DATA)
    if len(data) != 24:
        raise ValueError(f"expected 24 capwave pairs, found {len(data)}")
    required = {"resolution", "imax", "native_primary", "nn_primary", "improvement_percent"}
    if not required.issubset(data.columns):
        raise ValueError(f"missing source-data columns: {sorted(required - set(data.columns))}")
    data = data.sort_values(["resolution", "imax"])

    resolutions = [64, 128, 256, 512]
    imax_values = list(range(6))
    matrix = (
        data.pivot(index="resolution", columns="imax", values="improvement_percent")
        .reindex(index=resolutions, columns=imax_values)
        .to_numpy()
    )
    if not np.isfinite(matrix).all():
        raise ValueError("non-finite heatmap value")

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7.0,
        "axes.labelsize": 7.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "axes.linewidth": 0.75,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "savefig.transparent": False,
    })

    fig, ax = plt.subplots(figsize=(183 / 25.4, 80 / 25.4))
    fig.subplots_adjust(left=0.11, right=0.87, bottom=0.23, top=0.91)

    limit = 5.0
    cmap = LinearSegmentedColormap.from_list(
        "worse_to_better", [NEGATIVE, NEUTRAL, POSITIVE]
    )
    image = ax.imshow(
        matrix,
        cmap=cmap,
        norm=TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit),
        aspect="auto",
        interpolation="nearest",
    )

    ax.set_xticks(range(6), ["0", "1", "2", "3\ndefault", "4", "5"])
    ax.set_yticks(range(4), [f"N{value}" for value in resolutions])
    ax.set_xlabel("Redistance iterations, imax")
    ax.set_ylabel("Grid")

    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            color = "white" if abs(value) >= 3.0 else "#222222"
            ax.text(
                column,
                row,
                f"{value:+.2f}",
                ha="center",
                va="center",
                color=color,
                fontsize=6.8,
            )

    for x in np.arange(-0.5, 6, 1):
        ax.axvline(x, color="white", linewidth=0.8)
    for y in np.arange(-0.5, 4, 1):
        ax.axhline(y, color="white", linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.75)
    ax.spines["bottom"].set_linewidth(0.75)
    ax.tick_params(direction="out", length=2.5, width=0.7)
    ax.add_patch(
        Rectangle(
            (2.52, -0.48),
            0.96,
            len(resolutions) - 0.04,
            fill=False,
            edgecolor="#222222",
            linewidth=0.8,
            clip_on=False,
        )
    )

    colorbar_ax = fig.add_axes([0.89, 0.23, 0.022, 0.68])
    colorbar = fig.colorbar(image, cax=colorbar_ax, ticks=[-5, -2.5, 0, 2.5, 5])
    colorbar.set_label(
        "CLSVOF NN cell-offset improvement over CLSVOF (%)",
        rotation=90,
        labelpad=6,
        fontsize=7.0,
    )
    colorbar.ax.tick_params(labelsize=6.8, length=2.5)

    fig.savefig(HERE / "capwave_nn_offset_improvement.png", dpi=600)
    plt.close(fig)


if __name__ == "__main__":
    main()
