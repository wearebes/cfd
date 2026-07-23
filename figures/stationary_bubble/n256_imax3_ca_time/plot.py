#!/usr/bin/env python3
"""Verified N256 stationary-bubble Ca(t) histories at imax=3."""

from __future__ import annotations

import csv
import hashlib
import math
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-stationary-mpl")
)

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


HERE = Path(__file__).resolve().parent
LAPLACE = 12000.0
RESOLUTION = 256
IMAX = 3
OUTPUT = HERE / "stationary_bubble_ca_time_N256_imax3.png"
SOURCE_DATA = HERE / "source_data.csv"

# These hashes are recorded by the completed formal HPC manifests.  Refuse to
# draw if the curated traces no longer match the archived source data.
EXPECTED_SHA256 = {
    "clsvof": "3deba3b5af3a359073fd55790bd5d16e5d719b23c7a1da5c33c2d95eb0706ee0",
    "nn": "849cd2a168fee7d1a6b4830b878b98f2331437ffdcd9e9161e066d7d294cc91d",
}

STYLES = {
    "clsvof": {
        "color": "#30343B",
        "linestyle": "-",
        "label": "CLSVOF",
    },
    "nn": {
        "color": "#0072B2",
        "linestyle": (0, (5.0, 2.0)),
        "label": "NN",
    },
}


def repository_root() -> Path:
    for parent in HERE.parents:
        if (parent / "generate").is_dir() and (parent / "dataset").is_dir():
            return parent
    raise RuntimeError("Could not locate repository root")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_trace(
    path: Path, expected_sha256: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    observed_sha256 = file_sha256(path)
    if observed_sha256 != expected_sha256:
        raise ValueError(
            f"Trace provenance mismatch for {path}: {observed_sha256}"
        )
    data = np.loadtxt(path)
    if data.ndim != 2 or data.shape[1] != 3:
        raise ValueError(f"Expected three columns in {path}, got {data.shape}")
    if not np.all(np.isfinite(data)):
        raise ValueError(f"Non-finite values in {path}")
    time = data[:, 0]
    u_star = data[:, 1]
    delta_fraction = data[:, 2]
    if np.any(np.diff(time) <= 0.0):
        raise ValueError(f"Time is not strictly increasing in {path}")
    if time[0] != 0.0 or time[-1] != 1.0:
        raise ValueError(f"Trace does not cover recorded time t=0..1 in {path}")
    if np.any(u_star < 0.0):
        raise ValueError(f"Negative velocity magnitude in {path}")
    return time, u_star / math.sqrt(LAPLACE), delta_fraction


def plotted_indices(size: int, traces: dict[str, tuple[np.ndarray, ...]]) -> np.ndarray:
    """Keep dense startup data and a deterministic exact sample thereafter."""
    startup_count = min(2500, size)
    remaining_budget = 10000
    stride = max(1, math.ceil((size - startup_count) / remaining_budget))
    indices = set(range(startup_count))
    indices.update(range(startup_count, size, stride))
    indices.add(size - 1)
    for _, ca, _ in traces.values():
        indices.add(int(np.argmax(ca)))
        positive = np.flatnonzero(ca > 0.0)
        if positive.size:
            indices.add(int(positive[np.argmin(ca[positive])]))
    return np.asarray(sorted(indices), dtype=int)


def write_source_data(
    traces: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    indices: np.ndarray,
) -> None:
    fields = (
        "method",
        "resolution",
        "imax",
        "laplace_number",
        "time",
        "u_star",
        "capillary_number",
        "delta_fraction",
        "raw_row_index",
    )
    with SOURCE_DATA.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for method in ("clsvof", "nn"):
            time, ca, delta_fraction = traces[method]
            for index in indices:
                writer.writerow({
                    "method": method,
                    "resolution": RESOLUTION,
                    "imax": IMAX,
                    "laplace_number": LAPLACE,
                    "time": f"{time[index]:.12g}",
                    "u_star": f"{ca[index] * math.sqrt(LAPLACE):.12g}",
                    "capillary_number": f"{ca[index]:.12g}",
                    "delta_fraction": f"{delta_fraction[index]:.12g}",
                    "raw_row_index": int(index),
                })


def main() -> None:
    root = repository_root()
    raw = root / f"dataset/stationary_bubble/N{RESOLUTION:04d}/imax{IMAX:02d}"
    traces = {
        method: load_trace(
            raw / method / "timeseries.dat", EXPECTED_SHA256[method]
        )
        for method in ("clsvof", "nn")
    }
    anchor_time = traces["clsvof"][0]
    if len(traces["nn"][0]) != len(anchor_time) or not np.array_equal(
        traces["nn"][0], anchor_time
    ):
        raise ValueError("CLSVOF and NN traces do not share the same time grid")

    indices = plotted_indices(len(anchor_time), traces)
    write_source_data(traces, indices)
    peak_time = max(
        time[int(np.argmax(ca))]
        for time, ca, _ in traces.values()
    )

    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7.0,
        "axes.labelsize": 7.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "axes.linewidth": 0.75,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "legend.frameon": False,
        "legend.fontsize": 7.0,
        "lines.solid_capstyle": "round",
        "savefig.facecolor": "white",
        "savefig.transparent": False,
    })

    fig, ax = plt.subplots(figsize=(89 / 25.4, 62 / 25.4))
    fig.subplots_adjust(left=0.18, right=0.97, bottom=0.20, top=0.83)

    for method in ("clsvof", "nn"):
        time, ca, _ = traces[method]
        style = STYLES[method]
        decay = indices[time[indices] >= peak_time]
        ax.plot(
            time[decay],
            ca[decay] * 1.0e5,
            color=style["color"],
            linestyle=style["linestyle"],
            linewidth=1.05,
            zorder=3 if method == "nn" else 2,
        )

    ax.set_xscale("log")
    ax.set_xlim(peak_time, 1.0)
    ax.set_ylim(0.0, 5.25)
    ax.set_yticks(np.arange(0.0, 5.1, 1.0))
    ax.set_xlabel(r"Dimensionless time, $t$ (log scale)")
    ax.set_ylabel(r"Capillary number, $Ca$ ($\times 10^{-5}$)")
    ax.tick_params(direction="out")
    ax.text(
        0.97, 0.96,
        r"$N=256$, $i_{\max}=3$",
        transform=ax.transAxes,
        ha="right",
        va="top",
        color="#4D4D4D",
    )
    handles = [
        Line2D(
            [0], [0], color=STYLES[method]["color"],
            linestyle=STYLES[method]["linestyle"], linewidth=1.15,
            label=STYLES[method]["label"],
        )
        for method in ("clsvof", "nn")
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.48, 1.18),
        ncol=2,
        handlelength=2.5,
        columnspacing=1.25,
    )

    fig.savefig(OUTPUT, dpi=600)
    plt.close(fig)


if __name__ == "__main__":
    main()
