#!/usr/bin/env python3
"""Render the N=32 and N=128 stationary-bubble crossing-C2 Ca histories."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-stationary-ca-pair-mpl")
)
os.environ.setdefault(
    "XDG_CACHE_HOME",
    str(Path(tempfile.gettempdir()) / "cfd-stationary-ca-pair-cache"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIGURES_ROOT = HERE.parents[1]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (  # noqa: E402
    MATH_TEXT_PT,
    PANEL_LABEL_STYLE,
    apply_cfd_style,
    figure_size,
    save_manuscript_figure,
    style_time_series,
)
from data_paths import (  # noqa: E402
    canonical_run_dir,
    data_root,
    logical_data_path,
    nn_inference_precision,
    nn_precision_output_suffix,
)


RESOLUTIONS = (32, 128)
METHODS = ("VOF-HF", "CLSVOF", "CLSVOF-NN")
TERMINAL_TAU = 2.0
TERMINAL_ATOL = 1e-12
DISPLAY_TAU = np.linspace(0.0, TERMINAL_TAU, 181)
OUTPUT_SUFFIX = nn_precision_output_suffix()
OUTPUT_STEM = HERE / f"stationary_ca_N32_N128_crossing{OUTPUT_SUFFIX}"
FIGURE_WIDTH_MM = 190.0
FIGURE_HEIGHT_MM = 82.0


def source_path(resolution: int, method: str) -> Path:
    root = data_root(repo_root=ROOT)
    canonical_method = {
        "VOF-HF": "VOF-HF",
        "CLSVOF": "CLSVOF-native-C2",
        "CLSVOF-NN": "Cell-NN-C2",
    }[method]
    return canonical_run_dir(
        "stationary_bubble",
        canonical_method,
        resolution,
        grid="uniform",
        imax=0 if method == "CLSVOF" else None,
        steps=0 if method == "CLSVOF-NN" else None,
        root=root,
    ) / ("whole_domain_timeseries.csv" if method == "CLSVOF-NN" else "timeseries.csv")


def load_display_samples(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read a raw trace and choose nearest native samples for display."""

    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    tau = np.asarray([float(row["tau"]) for row in rows], dtype=float)
    ca = np.asarray([float(row["capillary_number"]) for row in rows], dtype=float)

    if len(tau) == 0 or not np.isfinite(tau).all() or not np.isfinite(ca).all():
        raise ValueError(f"invalid or empty stationary trace: {path}")
    if np.any(np.diff(tau) <= 0.0):
        raise ValueError(f"time is not strictly increasing: {path}")
    if tau[0] != 0.0 or not np.isclose(tau[-1], TERMINAL_TAU, atol=TERMINAL_ATOL):
        raise ValueError(f"trace does not span tau=0..{TERMINAL_TAU:g}: {path}")
    if np.any(ca < 0.0):
        raise ValueError(f"negative capillary number: {path}")

    right = np.searchsorted(tau, DISPLAY_TAU, side="left")
    right = np.clip(right, 0, len(tau) - 1)
    left = np.maximum(right - 1, 0)
    choose_left = np.abs(tau[left] - DISPLAY_TAU) <= np.abs(
        tau[right] - DISPLAY_TAU
    )
    indices = np.where(choose_left, left, right)
    indices = np.unique(
        np.concatenate(
            (indices, np.asarray([int(np.argmax(ca)), len(tau) - 1], dtype=int))
        )
    )
    indices = indices[ca[indices] > 0.0]
    return tau[indices], ca[indices]


def main() -> None:
    apply_cfd_style()
    fig, axes = plt.subplots(
        1, 2, figsize=figure_size("double", FIGURE_HEIGHT_MM)
    )
    fig.subplots_adjust(left=0.095, right=0.97, bottom=0.20, top=0.76, wspace=0.24)

    all_paths: list[Path] = []
    legend_handles = None
    legend_labels = None
    for panel_index, (ax, resolution) in enumerate(zip(axes, RESOLUTIONS)):
        displayed_ca: list[np.ndarray] = []
        for method in METHODS:
            path = source_path(resolution, method)
            all_paths.append(path)
            tau, ca = load_display_samples(path)
            displayed_ca.append(ca)
            ax.plot(
                tau,
                ca,
                label=method,
                **style_time_series(method, len(tau), marker_count=10),
            )

        ax.set_xlim(0.0, TERMINAL_TAU)
        ax.set_yscale("log")
        ax.tick_params(axis="y", labelsize=MATH_TEXT_PT)
        positive_min = min(float(np.min(ca)) for ca in displayed_ca)
        positive_max = max(float(np.max(ca)) for ca in displayed_ca)
        ax.set_ylim(positive_min / 5.0, positive_max * 5.0)
        ax.set_xticks(np.arange(0.0, TERMINAL_TAU + 0.001, 0.25))
        ax.set_xlabel(r"$\tau$")
        if panel_index == 0:
            ax.set_ylabel(r"$\mathrm{Ca}_{\max}$")
            legend_handles, legend_labels = ax.get_legend_handles_labels()
        ax.set_title(rf"$N={resolution}$", pad=7.0)
        ax.text(
            s=f"({chr(ord('a') + panel_index)})",
            transform=ax.transAxes,
            **PANEL_LABEL_STYLE,
        )

    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.50, 0.950),
        ncol=3,
        columnspacing=1.8,
        handlelength=2.3,
        handletextpad=0.7,
        borderaxespad=0.0,
    )

    paths = save_manuscript_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)



if __name__ == "__main__":
    main()
