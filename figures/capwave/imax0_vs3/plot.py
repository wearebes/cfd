#!/usr/bin/env python3
"""Capillary-wave residual histories for CLSVOF redistance settings."""

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
from matplotlib.lines import Line2D


HERE = Path(__file__).resolve().parent
def repository_root() -> Path:
    for parent in HERE.parents:
        if (parent / "generate").is_dir() and (parent / "dataset").is_dir():
            return parent
    raise RuntimeError("Could not locate the repository root")


ROOT = repository_root()
RAW = ROOT / "dataset/capwave"
REFERENCE_DATA = RAW / "reference/prosperetti.dat"
A0 = 0.01
NATIVE = "#30343B"
NN_BLUE = "#0072B2"
REFERENCE = "#CC79A7"


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.08,
        1.03,
        label,
        transform=ax.transAxes,
        fontsize=8,
        fontweight="bold",
        ha="left",
        va="bottom",
    )


def read_wave(path: Path) -> np.ndarray:
    data = np.loadtxt(path)
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"invalid wave data: {path}")
    return data[:, :2]


def read_reference(path: Path) -> np.ndarray:
    data = np.loadtxt(path)
    if data.ndim != 2 or data.shape[1] != 2:
        raise ValueError(f"invalid reference data: {path}")
    return data


def main() -> None:
    resolutions = [64, 128, 256, 512]
    sources = []
    panels = {}

    for resolution in resolutions:
        waves = {}
        for imax in (0, 3):
            row = RAW / f"N{resolution:04d}/imax{imax:02d}/clsvof"
            waves[imax] = read_wave(row / "wave.dat")
        nn0 = read_wave(
            RAW / f"N{resolution:04d}/imax00/nn/wave.dat"
        )

        anchor = waves[3]
        reference = read_reference(REFERENCE_DATA)[: len(anchor)]
        if reference.shape != anchor.shape or nn0.shape != anchor.shape or any(wave.shape != anchor.shape for wave in waves.values()):
            raise ValueError(f"sample-count mismatch at N{resolution}")
        for wave in (*waves.values(), nn0):
            if not np.allclose(wave[:, 0], anchor[:, 0], rtol=0, atol=2e-6):
                raise ValueError(f"time-grid mismatch at N{resolution}")

        panels[resolution] = (waves, nn0, reference)

        for index in range(len(anchor)):
            sources.append({
                "resolution": resolution,
                "tau": anchor[index, 0],
                "A_reference": reference[index, 1],
                "residual_clsvof_imax0_percent_A0": 100.0 * (waves[0][index, 1] - reference[index, 1]) / A0,
                "residual_clsvof_imax3_percent_A0": 100.0 * (waves[3][index, 1] - reference[index, 1]) / A0,
                "residual_nn_imax0_percent_A0": 100.0 * (nn0[index, 1] - reference[index, 1]) / A0,
            })

    pd.DataFrame(sources).to_csv(HERE / "source_data.csv", index=False, lineterminator="\n")

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7.0,
        "axes.labelsize": 7.0,
        "axes.titlesize": 7.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "axes.linewidth": 0.75,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "legend.fontsize": 7.0,
        "lines.solid_capstyle": "round",
        "savefig.facecolor": "white",
        "savefig.transparent": False,
    })

    fig, axes = plt.subplots(2, 2, figsize=(183 / 25.4, 116 / 25.4), sharex=True)
    fig.subplots_adjust(left=0.105, right=0.985, bottom=0.14, top=0.84, wspace=0.20, hspace=0.30)

    for panel_index, (ax, resolution) in enumerate(zip(axes.flat, resolutions, strict=True)):
        waves, nn0, reference = panels[resolution]
        tau = waves[3][:, 0]
        for imax, linestyle, marker, zorder in (
            (3, "-", "o", 2),
            (0, "--", "s", 3),
        ):
            residual = 100.0 * (waves[imax][:, 1] - reference[:, 1]) / A0
            ax.plot(
                tau,
                residual,
                color=NATIVE,
                lw=1.05,
                ls=linestyle,
                marker=marker,
                markevery=70,
                ms=2.5,
                mfc="white",
                mec=NATIVE,
                mew=0.65,
                zorder=zorder,
            )
        nn0_residual = 100.0 * (nn0[:, 1] - reference[:, 1]) / A0
        ax.plot(
            tau,
            nn0_residual,
            color=NN_BLUE,
            lw=1.0,
            ls=(0, (4.0, 1.8, 1.0, 1.8)),
            marker="D",
            markevery=70,
            ms=2.4,
            mfc="white",
            mec=NN_BLUE,
            mew=0.65,
            zorder=4,
        )
        ax.axhline(0, color=REFERENCE, lw=0.75, zorder=0)
        ax.set_title(f"N{resolution}", loc="left", x=0.04, pad=3)
        add_panel_label(ax, chr(ord("a") + panel_index))
        ax.margins(x=0.01)
        ax.tick_params(direction="out", length=3, width=0.7)

    handles = [
        Line2D([0], [0], color=NATIVE, lw=1.05, marker="o", ms=3.1,
               markerfacecolor="white", label="CLSVOF, imax=3"),
        Line2D([0], [0], color=NATIVE, lw=1.05, ls="--", marker="s", ms=3.1,
               markerfacecolor="white", label="CLSVOF, imax=0"),
        Line2D([0], [0], color=NN_BLUE, lw=1.0, ls=(0, (4.0, 1.8, 1.0, 1.8)),
               marker="D", ms=3.0, markerfacecolor="white",
               label="CLSVOF NN cell-offset, imax=0"),
        Line2D([0], [0], color=REFERENCE, lw=0.75, label="Prosperetti"),
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.55, 0.975),
        ncol=4,
        handlelength=2.4,
        columnspacing=1.45,
    )
    fig.supxlabel(r"Dimensionless time, $\tau$", y=0.045, fontsize=7.0)
    fig.supylabel(r"Amplitude residual (% $A_0$)", x=0.02, fontsize=7.0)
    fig.savefig(HERE / "capwave_imax0_vs3.png", dpi=600)
    plt.close(fig)


if __name__ == "__main__":
    main()
