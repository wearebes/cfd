#!/usr/bin/env python3
"""Plot combined and case-separated rising-bubble histories at imax=3."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-rising-mpl"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "cfd-rising-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIGURES_ROOT = HERE.parents[1]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (  # noqa: E402
    BODY_TEXT_PT,
    METHOD_STYLE,
    PANEL_LABEL_STYLE,
    apply_cfd_style,
    canonical_method_label,
    figure_size,
    save_figure,
    save_figure_pdf,
    save_figure_svg,
    style_time_series,
)
from data_paths import (  # noqa: E402
    canonical_run_dir,
    nn_precision_output_suffix,
    reference_file,
)

ALL_RESOLUTIONS = (32, 64, 128, 256, 512)
SINGLE_GRID_VALUE = os.environ.get("RISING_RESOLUTION")
RESOLUTION = int(SINGLE_GRID_VALUE) if SINGLE_GRID_VALUE is not None else 256
if RESOLUTION not in ALL_RESOLUTIONS:
    raise ValueError(f"unsupported rising-bubble resolution: {RESOLUTION}")

OUTPUT_SUFFIX = nn_precision_output_suffix()
OUTPUT_STEM = HERE / f"histories_imax3{OUTPUT_SUFFIX}"
if SINGLE_GRID_VALUE is None:
    CASE_OUTPUT_STEMS = {
        1: HERE / f"histories_imax3_case1{OUTPUT_SUFFIX}",
        2: HERE / f"histories_imax3_case2{OUTPUT_SUFFIX}",
    }
else:
    SINGLE_GRID_DIR = HERE / f"single_grid_crossing_c2{OUTPUT_SUFFIX}"
    CASE_OUTPUT_STEMS = {
        case: SINGLE_GRID_DIR
        / f"rising_bubble_case{case}_time_history_N{RESOLUTION:04d}"
        for case in (1, 2)
    }
COMBINED_FIGURE_HEIGHT_MM = 115.0
CASE_FIGURE_HEIGHT_MM = 65.0

TIME = np.arange(0.0, 3.0 + 0.0025, 0.005)
RESOLUTIONS = (RESOLUTION,)
METHODS = ("VOF-HF", "CLSVOF", "NN")
DATA_METHOD = {
    "VOF-HF": "VOF-HF",
    "CLSVOF": "CLSVOF-native-C2",
    "NN": "Cell-NN-C2",
}
MARKER_COUNT = {method: 8 for method in METHODS}
MARKER_PHASE = {"VOF-HF": 0, "CLSVOF": 24, "NN": 48}
NUMERICAL_LINEWIDTH_PT = 1.15
NUMERICAL_MARKER_SIZE_PT = 3.8
NUMERICAL_MARKER_EDGE_WIDTH_PT = 0.75
REFERENCE_LINEWIDTH_PT = 1.1
REFERENCE_ALPHA = 0.78
REFERENCE_ZORDER = 10
RESOLUTION_STYLE = {
    RESOLUTION: {"linewidth": NUMERICAL_LINEWIDTH_PT, "alpha": 1.0},
}
METRICS = (
    ("center_of_mass_x", r"Vertical centroid, $y_c$", r"$y_c$", (0.48, 1.16)),
    ("rise_velocity_x", r"Mean rise velocity, $v_c$", r"$v_c$", (-0.01, 0.27)),
    ("circularity", r"Circularity, $\mathcal{C}$", r"$\mathcal{C}$", (0.43, 1.02)),
)
CIRCULARITY_YLIM = {
    1: (0.88, 1.01),
    2: (0.43, 1.02),
}


def setup_style() -> None:
    apply_cfd_style()


def reference(case: int) -> dict[str, np.ndarray]:
    path = ROOT / f"dataset/rising_bubble/case{case}/reference/hysing/history.dat"
    raw = np.loadtxt(path)
    initial = np.asarray([[0.0, 0.0, 1.0, 0.5, 0.0]])
    raw = np.vstack((initial, raw))
    if np.any(np.diff(raw[:, 0]) <= 0.0) or raw[-1, 0] < 3.0:
        raise ValueError(f"reference does not bracket t=0..3: {path}")
    return {
        "center_of_mass_x": np.interp(TIME, raw[:, 0], raw[:, 3]),
        "rise_velocity_x": np.interp(TIME, raw[:, 0], raw[:, 4]),
        "circularity": np.interp(TIME, raw[:, 0], raw[:, 2]),
    }


def result_path(case: int, resolution: int, method: str) -> Path:
    return canonical_run_dir(
        "rising_bubble",
        DATA_METHOD[method],
        resolution,
        grid="uniform",
        imax=3 if method == "CLSVOF" else None,
        steps=3 if method == "NN" else None,
        benchmark_case=case,
        repo_root=ROOT,
    ) / "timeseries.csv"


def history(case: int, resolution: int, method: str) -> dict[str, np.ndarray]:
    path = result_path(case, resolution, method)
    frame = pd.read_csv(path)
    required = {"time", *(metric[0] for metric in METRICS)}
    if not required <= set(frame.columns):
        raise ValueError(f"missing columns in {path}")
    if frame.empty or np.any(np.diff(frame["time"].to_numpy()) <= 0.0):
        raise ValueError(f"invalid time series: {path}")
    if abs(float(frame["time"].iloc[0])) > 1e-12 or float(frame["time"].iloc[-1]) < 3.0:
        raise ValueError(f"time series does not span t=0..3: {path}")
    return {
        metric[0]: np.interp(TIME, frame["time"], frame[metric[0]])
        for metric in METRICS
    }


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(s=f"({label})", transform=ax.transAxes, **PANEL_LABEL_STYLE)


def legend_handles() -> list[Line2D]:
    reference_style = dict(METHOD_STYLE["Reference"])
    reference_style["linewidth"] = REFERENCE_LINEWIDTH_PT
    handles = [
        Line2D(
            [0],
            [0],
            label="Reference",
            **reference_style,
        )
    ]
    handles.extend(
        Line2D(
            [0],
            [0],
            label=canonical_method_label(method),
            markerfacecolor="white",
            markeredgecolor=METHOD_STYLE[canonical_method_label(method)]["color"],
            markeredgewidth=NUMERICAL_MARKER_EDGE_WIDTH_PT,
            markersize=NUMERICAL_MARKER_SIZE_PT,
            linewidth=NUMERICAL_LINEWIDTH_PT,
            **METHOD_STYLE[canonical_method_label(method)],
        )
        for method in METHODS
    )
    return handles


def add_legend(fig: plt.Figure, *, y: float = 0.965) -> None:
    fig.legend(
        handles=legend_handles(),
        loc="upper center",
        bbox_to_anchor=(0.54, y),
        ncol=4,
        handlelength=2.0,
        columnspacing=1.2,
        borderaxespad=0.0,
    )


def plot_case_panels(
    axes: np.ndarray,
    *,
    case: int,
    ref: dict[str, np.ndarray],
    curves: dict[tuple[str, int], dict[str, np.ndarray]],
    first_panel_index: int = 0,
    show_titles: bool = True,
) -> None:
    if case not in CASE_OUTPUT_STEMS:
        raise ValueError(f"case must be 1 or 2, received {case}")
    for column, (metric, title, ylabel, ylim) in enumerate(METRICS):
        ax = axes[column]
        for method in METHODS:
            for resolution in RESOLUTIONS:
                display_method = canonical_method_label(method)
                phase = MARKER_PHASE[method]
                markevery = np.rint(
                    np.linspace(phase, len(TIME) - 1 - phase, MARKER_COUNT[method])
                ).astype(int).tolist()
                ax.plot(
                    TIME,
                    curves[(method, resolution)][metric],
                    **style_time_series(
                        display_method,
                        len(TIME),
                        marker_count=MARKER_COUNT[method],
                        markersize=NUMERICAL_MARKER_SIZE_PT,
                        markeredgewidth=NUMERICAL_MARKER_EDGE_WIDTH_PT,
                        markevery=markevery,
                        **RESOLUTION_STYLE[resolution],
                    ),
                    zorder=2 + METHODS.index(method),
                )
        ax.plot(
            TIME,
            ref[metric],
            label="Reference",
            zorder=REFERENCE_ZORDER,
            **style_time_series(
                "Reference",
                len(TIME),
                linewidth=REFERENCE_LINEWIDTH_PT,
                alpha=REFERENCE_ALPHA,
            ),
        )
        ax.set_xlim(0.0, 3.0)
        panel_ylim = CIRCULARITY_YLIM[case] if metric == "circularity" else ylim
        ax.set_ylim(*panel_ylim)
        ax.set_xlabel(r"$t$")
        ax.set_ylabel(ylabel)
        if show_titles:
            ax.set_title(title, pad=4)
        panel_label(ax, chr(ord("a") + first_panel_index + column))


def build_combined_figure(
    case_data: dict[
        int,
        tuple[
            dict[str, np.ndarray],
            dict[tuple[str, int], dict[str, np.ndarray]],
        ],
    ],
) -> tuple[plt.Figure, np.ndarray]:
    fig, axes = plt.subplots(
        2,
        3,
        figsize=figure_size("double", COMBINED_FIGURE_HEIGHT_MM),
    )
    fig.subplots_adjust(
        left=0.08,
        right=0.992,
        bottom=0.12,
        top=0.84,
        hspace=0.38,
        wspace=0.30,
    )

    for row, case in enumerate((1, 2)):
        ref, curves = case_data[case]
        plot_case_panels(
            axes[row],
            case=case,
            ref=ref,
            curves=curves,
            first_panel_index=row * 3,
            show_titles=row == 0,
        )

    fig.text(
        0.012,
        0.57,
        "Case 1",
        rotation=90,
        ha="center",
        va="center",
        fontsize=BODY_TEXT_PT,
    )
    fig.text(
        0.012,
        0.255,
        "Case 2",
        rotation=90,
        ha="center",
        va="center",
        fontsize=BODY_TEXT_PT,
    )
    add_legend(fig)
    return fig, axes


def build_case_figure(
    case: int,
    ref: dict[str, np.ndarray],
    curves: dict[tuple[str, int], dict[str, np.ndarray]],
) -> tuple[plt.Figure, np.ndarray]:
    if case not in CASE_OUTPUT_STEMS:
        raise ValueError(f"case must be 1 or 2, received {case}")
    fig, axes = plt.subplots(
        1,
        3,
        figsize=figure_size("double", CASE_FIGURE_HEIGHT_MM),
    )
    fig.subplots_adjust(
        left=0.085,
        right=0.975,
        bottom=0.20,
        top=0.73,
        wspace=0.30,
    )
    plot_case_panels(axes, case=case, ref=ref, curves=curves)
    fig.text(
        0.025,
        0.46,
        f"Test Case {case}",
        rotation=90,
        ha="center",
        va="center",
        fontsize=BODY_TEXT_PT,
    )
    if SINGLE_GRID_VALUE is not None:
        fig.text(
            0.975,
            0.94,
            rf"$N={RESOLUTION}$",
            ha="right",
            va="top",
            fontsize=BODY_TEXT_PT,
        )
    add_legend(fig, y=0.94)
    return fig, axes


def load_case_data(
    case: int,
) -> tuple[
    dict[str, np.ndarray],
    dict[tuple[str, int], dict[str, np.ndarray]],
]:
    return reference(case), {
        (method, resolution): history(case, resolution, method)
        for method in METHODS
        for resolution in RESOLUTIONS
    }


def main() -> None:
    setup_style()
    cases = (1, 2)
    case_data = {case: load_case_data(case) for case in cases}

    paths = []
    if not OUTPUT_SUFFIX:
        fig, _ = build_combined_figure(case_data)
        paths.append(save_figure(fig, OUTPUT_STEM))
        plt.close(fig)

    for case in (1, 2):
        fig, _ = build_case_figure(case, *case_data[case])
        paths.append(save_figure(fig, CASE_OUTPUT_STEMS[case]))
        plt.close(fig)

    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
