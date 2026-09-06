#!/usr/bin/env python3
"""Plot the stationary-bubble whole-domain Ca versus grid resolution.

The figure is a grid-resolution diagnostic, not a convergence-order claim.
It compares the VOF-HF reference with the native and learned crossing formulations.
The reported value is the maximum speed over the full computational domain
at tau=2, nondimensionalized as a capillary number.
"""

from __future__ import annotations

import csv
import gzip
import os
import sys
import tempfile
from math import hypot, isclose, isfinite, sqrt
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-stationary-ca-mpl")
)
os.environ.setdefault(
    "XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "cfd-stationary-ca-cache")
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
FIGURES_ROOT = HERE.parents[1]
REPOSITORY_ROOT = HERE.parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (  # noqa: E402
    MATH_TEXT_PT,
    apply_cfd_style,
    figure_size,
    save_manuscript_figure,
    style_discrete_series,
)
from data_paths import (  # noqa: E402
    canonical_run_dir,
    data_root,
    nn_inference_precision,
    nn_precision_output_suffix,
)


TERMINAL_TAU = 2.0
INTERFACE_RADIUS = 0.4
INTERFACE_BAND_CELLS = 4.0
VISCOSITY = sqrt(0.8 / 12000.0)
SURFACE_TENSION = 1.0
RESOLUTIONS = (32, 64, 128, 256)
DATA_ROOT = data_root(repo_root=REPOSITORY_ROOT)
OUTPUT_SUFFIX = nn_precision_output_suffix()
OUTPUT_STEM = HERE / f"stationary_bubble_summary-crossing{OUTPUT_SUFFIX}"
SOURCE_DATA_PATH = HERE / f"source_data{OUTPUT_SUFFIX}.csv"
FIGURE_HEIGHT_MM = 67.0


def endpoint_ca(path: Path, resolution: int) -> float:
    """Return Ca from the maximum speed over the full computational domain."""
    with gzip.open(path, "rt", newline="", encoding="utf-8") as stream:
        rows = [
            row for row in csv.DictReader(stream) if row["snapshot"] == "final"
        ]
    if len(rows) != resolution * resolution:
        raise ValueError(
            f"expected {resolution * resolution} final cells in {path}, "
            f"found {len(rows)}"
        )

    h = 1.0 / resolution
    speeds = []
    for row in rows:
        tau = float(row["actual_benchmark_time"])
        delta = float(row["Delta"])
        x = float(row["x"])
        y = float(row["y"])
        u_x = float(row["u_x"])
        u_y = float(row["u_y"])
        values = (tau, delta, x, y, u_x, u_y)
        if not all(isfinite(value) for value in values):
            raise ValueError(f"non-finite final field value: {path}")
        if not isclose(tau, TERMINAL_TAU, abs_tol=1e-12):
            raise ValueError(f"final field does not represent tau=2: {path}")
        if not isclose(delta, h, abs_tol=1e-14):
            raise ValueError(f"field is not uniform N={resolution}: {path}")
        speeds.append(hypot(u_x, u_y))

    if not speeds:
        raise ValueError(f"empty final field: {path}")
    ca = VISCOSITY * max(speeds) / SURFACE_TENSION
    if ca <= 0.0:
        raise ValueError(f"whole-domain Ca must be positive: {path}")
    return ca


def field_path(method: str, resolution: int) -> Path:
    """Return the matched reference or crossing field-snapshot path."""
    canonical_method = {
        "VOF-HF": "VOF-HF",
        "CLSVOF": "CLSVOF-native-C2",
        "CLSVOF-NN": "Cell-NN-C2",
    }[method]
    return (
        canonical_run_dir(
            "stationary_bubble",
            canonical_method,
            resolution,
            grid="uniform",
            imax=0 if method == "CLSVOF" else None,
            steps=0 if method == "CLSVOF-NN" else None,
            root=DATA_ROOT,
        )
        / "fields.csv.gz"
    )


def load_series() -> dict[str, tuple[float, ...]]:
    """Load tau=2 values from the existing matched field snapshots."""
    series: dict[str, tuple[float, ...]] = {}
    for method in ("VOF-HF", "CLSVOF", "CLSVOF-NN"):
        series[method] = tuple(
            endpoint_ca(field_path(method, resolution), resolution)
            for resolution in RESOLUTIONS
        )
    return series


def main() -> tuple[Path, Path, Path]:
    apply_cfd_style()

    series = load_series()
    fig, ax = plt.subplots(
        figsize=figure_size("single", height_mm=FIGURE_HEIGHT_MM),
    )
    fig.subplots_adjust(left=0.20, right=0.955, bottom=0.20, top=0.78)

    for method in ("VOF-HF", "CLSVOF", "CLSVOF-NN"):
        ax.plot(
            RESOLUTIONS,
            series[method],
            label=method,
            **style_discrete_series(
                method,
                linewidth=1.08,
                markersize=4.5,
                markeredgewidth=0.9,
            ),
        )

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.tick_params(axis="y", labelsize=MATH_TEXT_PT)
    ax.set_xlim(29.5, 278.0)
    ax.set_ylim(8.0e-18, 1.0e-14)
    ax.set_xticks(RESOLUTIONS)
    ax.set_xticklabels([str(value) for value in RESOLUTIONS])
    ax.tick_params(axis="x", which="minor", bottom=False, top=False)
    ax.set_xlabel(r"$N$")
    ax.set_ylabel(r"$\mathrm{Ca}_{\max}$")
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.48, 1.02),
        ncol=3,
        columnspacing=1.3,
        handlelength=1.8,
        handletextpad=0.4,
        frameon=False,
    )

    paths = save_manuscript_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)
    return paths


if __name__ == "__main__":
    main()
