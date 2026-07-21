#!/usr/bin/env python3
"""Batch capillary-wave amplitude comparisons across four grid resolutions."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-capwave-mpl")
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
RESOLUTIONS = (64, 128, 256, 512)
IMAX = 3
A0 = 0.01
CLSVOF_LABEL = "CLSVOF"
NN_LABEL = "NN"


def repository_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "dataset").is_dir() and (parent / "figures").is_dir():
            return parent
    raise RuntimeError("Could not locate the repository root")


def read_series(path: Path) -> np.ndarray:
    data = np.loadtxt(path)
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"invalid capwave series: {path}")
    data = data[:, :2]
    if not np.isfinite(data).all():
        raise ValueError(f"non-finite capwave value: {path}")
    if np.any(np.diff(data[:, 0]) <= 0):
        raise ValueError(f"time is not strictly increasing: {path}")
    return data


def build_source_data(resolution: int) -> pd.DataFrame:
    data_root = repository_root() / "dataset/capwave"
    sources = (
        ("Prosperetti reference", data_root / "reference/prosperetti.dat"),
        ("VOF-HF", data_root / f"reference/vof/N{resolution:04d}.dat"),
        (
            CLSVOF_LABEL,
            data_root / f"N{resolution:04d}/imax{IMAX:02d}/clsvof/wave.dat",
        ),
        (
            NN_LABEL,
            data_root
            / f"N{resolution:04d}/imax{IMAX:02d}/nn/wave.dat",
        ),
    )

    frames: list[pd.DataFrame] = []
    expected_rows: int | None = None
    reference_time: np.ndarray | None = None
    for series, path in sources:
        values = read_series(path)
        if expected_rows is None:
            expected_rows = len(values)
            reference_time = values[:, 0]
        elif len(values) != expected_rows:
            raise ValueError(
                f"sample-count mismatch: {path} has {len(values)}, expected {expected_rows}"
            )
        elif not np.allclose(values[:, 0], reference_time, rtol=0.0, atol=1.1e-4):
            raise ValueError(f"time-grid mismatch: {path}")
        frames.append(
            pd.DataFrame(
                {
                    "series": series,
                    "tau": values[:, 0],
                    "amplitude": values[:, 1],
                }
            )
        )

    source_data = pd.concat(frames, ignore_index=True)
    source_data.to_csv(
        HERE / f"source_data_N{resolution}.csv",
        index=False,
        lineterminator="\n",
    )
    return source_data


def rms_error_percent(values: np.ndarray, reference: np.ndarray) -> float:
    """Return RMS amplitude error as a percentage of the initial amplitude."""
    return 100.0 * float(np.sqrt(np.mean((values - reference) ** 2))) / A0


def render_resolution(resolution: int, source_data: pd.DataFrame) -> None:
    reference = source_data.loc[
        source_data["series"] == "Prosperetti reference", "amplitude"
    ].to_numpy()
    rms_errors = {
        series: rms_error_percent(
            source_data.loc[source_data["series"] == series, "amplitude"].to_numpy(),
            reference,
        )
        for series in ("VOF-HF", CLSVOF_LABEL, NN_LABEL)
    }
    legend_labels = {
        "Prosperetti reference": "Prosperetti reference",
        **{
            series: rf"{series} (RMS error = {error:.3f}% $A_0$)"
            for series, error in rms_errors.items()
        },
    }

    styles = {
        "Prosperetti reference": {"color": "#222222", "lw": 1.25, "ls": "-"},
        "VOF-HF": {
            "color": "#0B6E69",
            "lw": 0.75,
            "marker": "o",
            "ms": 2.2,
            "markevery": 10,
        },
        CLSVOF_LABEL: {
            "color": "#3B5B92",
            "lw": 1.0,
            "ls": "--",
        },
        NN_LABEL: {
            "color": "#7A5C00",
            "lw": 1.0,
            "ls": (0, (4.0, 2.0, 1.0, 2.0)),
        },
    }

    fig, ax = plt.subplots(figsize=(183 / 25.4, 86 / 25.4))
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.18, top=0.78)
    for series, style in styles.items():
        values = source_data.loc[source_data["series"] == series]
        ax.plot(
            values["tau"],
            values["amplitude"],
            label=legend_labels[series],
            **style,
        )

    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=0.0)
    ax.set_xlabel(r"Dimensionless time, $\tau$")
    ax.set_ylabel(r"Wave amplitude, $A$")
    ax.text(
        0.985,
        0.955,
        rf"$N={resolution}$",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7.0,
    )
    ax.tick_params(direction="out", length=3.0, width=0.7)
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.07),
        ncol=2,
        handlelength=2.6,
        columnspacing=1.45,
    )

    fig.savefig(HERE / f"capwave_amplitude_N{resolution}.png", dpi=600)
    plt.close(fig)


def main() -> None:
    plt.rcParams.update(
        {
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
            "legend.fontsize": 6.6,
            "savefig.facecolor": "white",
            "savefig.transparent": False,
        }
    )

    for resolution in RESOLUTIONS:
        render_resolution(resolution, build_source_data(resolution))


if __name__ == "__main__":
    main()
