#!/usr/bin/env python3
"""Plot combined and case-separated rising-bubble interface comparisons."""

from __future__ import annotations

import csv
import gzip
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-rising-mpl"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "cfd-rising-cache"))

import contourpy
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIGURES_ROOT = HERE.parents[1]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (  # noqa: E402
    BODY_TEXT_PT,
    LEGEND_TEXT_PT,
    PANEL_LABEL_STYLE,
    apply_cfd_style,
    canonical_method_label,
    figure_size,
    save_figure,
    save_pdf_figure,
    save_figure_svg,
)
from data_paths import (  # noqa: E402
    canonical_run_dir,
    nn_precision_output_suffix,
    reference_file,
)

OUTPUT_SUFFIX = nn_precision_output_suffix()
OUTPUT_STEM = HERE / f"interfaces_imax3{OUTPUT_SUFFIX}"
CASE1_OUTPUT_STEM = HERE / f"interfaces_case1{OUTPUT_SUFFIX}"
CASE2_OUTPUT_STEM = HERE / f"interfaces_case2{OUTPUT_SUFFIX}"
FIGURE_HEIGHT_MM = 206.0
CASE1_FIGURE_HEIGHT_MM = 60.0
CASE2_FIGURE_HEIGHT_MM = 160.0

METHODS = ("VOF-HF", "CLSVOF", "NN")
DATA_METHOD = {
    "VOF-HF": "VOF-HF",
    "CLSVOF": "CLSVOF-native-C2",
    "NN": "Cell-NN-C2",
}
RESOLUTIONS = (32, 64, 128, 256, 512)
NUMERICAL_LINEWIDTH_PT = 1.4
REFERENCE_LINEWIDTH_PT = 1.5
REFERENCE_LINESTYLE = (0, (4.0, 2.5))
REFERENCE_ZORDER = 5.5
LEGEND_FONTSIZE_PT = LEGEND_TEXT_PT
RESOLUTION_COLORS = {
    32: "#E69F00",
    64: "#0072B2",
    128: "#D62728",
    256: "#009E73",
    512: "#7A3DB8",
}
RESOLUTION_LINESTYLES = {
    32: "-",
    64: "--",
    128: "-.",
    256: ":",
    512: (0, (5.0, 1.5)),
}
RESOLUTION_MARKERS = {32: "o", 64: "s", 128: "D", 256: "^", 512: "v"}

# Stored solver coordinates are mapped to manuscript x horizontally and y vertically.
CASE1_XLIM = (-0.40, 0.40)
CASE1_YLIM = (0.88, 1.38)
CASE2_XLIM = (-0.40, 0.40)
CASE2_YLIM = (0.58, 1.38)
ZOOM_XLIM = (0.18, 0.40)
ZOOM_YLIM = (0.60, 1.06)

CASE1_XTICKS = (-0.4, -0.2, 0.0, 0.2, 0.4)
CASE1_YTICKS = (0.9, 1.0, 1.1, 1.2, 1.3)
CASE2_XTICKS = (-0.4, -0.2, 0.0, 0.2, 0.4)
CASE2_YTICKS = (0.6, 0.8, 1.0, 1.2, 1.4)
ZOOM_XTICKS = (0.2, 0.3, 0.4)
ZOOM_YTICKS = (0.6, 0.8, 1.0)

OUTER_HEIGHT_RATIOS = (0.62, 1.0, 1.0, 1.0)
CASE2_WIDTH_RATIOS = (2.15, 1.0, 1.0, 1.0, 1.0, 1.0)
ZOOM_BOX_STYLE = {
    "fill": False,
    "edgecolor": "#666666",
    "linewidth": 0.8,
    "linestyle": (0, (2.5, 1.8)),
    "zorder": 10,
}


def setup_style() -> None:
    apply_cfd_style()


def reference_curve(case: int) -> np.ndarray:
    path = ROOT / f"dataset/rising_bubble/case{case}/reference/hysing/interface.dat"
    points: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        transverse_raw, vertical = (float(value) for value in line.split()[:2])
        point = (transverse_raw - 0.5, vertical)
        if not points or point != points[-1]:
            points.append(point)
    curve = np.asarray(points, dtype=float)
    if curve.shape[0] < 3 or not np.isfinite(curve).all():
        raise ValueError(f"invalid Hysing interface: {path}")
    if not np.allclose(curve[0], curve[-1], rtol=0.0, atol=1e-12):
        raise ValueError(f"Hysing interface is not closed: {path}")
    return curve


def fields_path(case: int, resolution: int, method: str) -> Path:
    return canonical_run_dir(
        "rising_bubble",
        DATA_METHOD[method],
        resolution,
        grid="uniform",
        imax=3 if method == "CLSVOF" else None,
        steps=3 if method == "NN" else None,
        benchmark_case=case,
        repo_root=ROOT,
    ) / "fields.csv.gz"


def phase_fraction_contour(case: int, resolution: int, method: str) -> np.ndarray:
    path = fields_path(case, resolution, method)
    records: list[tuple[float, float, float, float]] = []
    actual_times: set[float] = set()
    target_times: set[float] = set()
    with gzip.open(path, "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["snapshot"] != "final":
                continue
            values = (
                float(row["x"]),
                float(row["y"]),
                float(row["Delta"]),
                float(row["phase_fraction"]),
            )
            if not np.isfinite(values).all():
                raise ValueError(f"non-finite final field value: {path}")
            records.append(values)
            actual_times.add(float(row["actual_solver_time"]))
            target_times.add(float(row["target_solver_time"]))
    if not records:
        raise ValueError(f"missing final field snapshot: {path}")
    if actual_times != {3.0} or target_times != {3.0}:
        raise ValueError(f"final field snapshot is not t=3: {path}")

    vertical = np.asarray(sorted({record[0] for record in records}), dtype=float)
    transverse_half = np.asarray(sorted({record[1] for record in records}), dtype=float)
    if (vertical.size, transverse_half.size) != (resolution, resolution // 4):
        raise ValueError(f"unexpected uniform grid shape: {path}")
    spacing = 2.0 / resolution
    if not np.allclose(np.diff(vertical), spacing, rtol=0.0, atol=1e-12):
        raise ValueError(f"nonuniform vertical grid: {path}")
    if not np.allclose(np.diff(transverse_half), spacing, rtol=0.0, atol=1e-12):
        raise ValueError(f"nonuniform transverse grid: {path}")
    if not np.allclose([record[2] for record in records], spacing, rtol=0.0, atol=1e-12):
        raise ValueError(f"unexpected cell width: {path}")

    vertical_index = {value: index for index, value in enumerate(vertical)}
    transverse_index = {value: index for index, value in enumerate(transverse_half)}
    fraction_half = np.full((vertical.size, transverse_half.size), np.nan, dtype=float)
    for x_value, y_value, _, fraction in records:
        index = (vertical_index[x_value], transverse_index[y_value])
        if np.isfinite(fraction_half[index]):
            raise ValueError(f"duplicate final field cell: {path}")
        fraction_half[index] = fraction
    if not np.isfinite(fraction_half).all():
        raise ValueError(f"incomplete final field grid: {path}")
    if fraction_half.min() < -1e-12 or fraction_half.max() > 1.0 + 1e-12:
        raise ValueError(f"phase fraction outside [0, 1]: {path}")

    transverse = np.concatenate((-transverse_half[::-1], transverse_half))
    fraction = np.concatenate((fraction_half[:, ::-1], fraction_half), axis=1)
    generator = contourpy.contour_generator(
        x=transverse,
        y=vertical,
        z=fraction,
        name="serial",
        line_type="Separate",
    )
    contours = generator.lines(0.5)
    if len(contours) != 1:
        raise ValueError(f"expected one f=0.5 contour, found {len(contours)}: {path}")
    curve = np.asarray(contours[0], dtype=float)
    if curve.shape[0] < 4 or not np.isfinite(curve).all():
        raise ValueError(f"invalid f=0.5 contour: {path}")
    if not np.allclose(curve[0], curve[-1], rtol=0.0, atol=1e-12):
        raise ValueError(f"f=0.5 contour is not closed: {path}")
    return curve


def style_axis(
    ax: plt.Axes,
    *,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    xticks: tuple[float, ...],
    yticks: tuple[float, ...],
    minor_ticks: bool = True,
) -> None:
    ax.set_xticks(xticks)
    ax.set_yticks(yticks)
    # Set limits after explicit ticks because Matplotlib otherwise expands the
    # view to include an out-of-range boundary tick (Case 2 uses 1.38, not 1.40).
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.tick_params(pad=1.3)
    if not minor_ticks:
        ax.minorticks_off()
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.8)
        spine.set_color("black")


def plot_reference(ax: plt.Axes, reference: np.ndarray) -> None:
    ax.plot(
        reference[:, 0],
        reference[:, 1],
        color="black",
        linestyle=REFERENCE_LINESTYLE,
        lw=REFERENCE_LINEWIDTH_PT,
        zorder=REFERENCE_ZORDER,
    )


def plot_numerical_curve(
    ax: plt.Axes,
    curve: np.ndarray,
    resolution: int,
) -> None:
    ax.plot(
        curve[:, 0],
        curve[:, 1],
        color=RESOLUTION_COLORS[resolution],
        linestyle=RESOLUTION_LINESTYLES[resolution],
        marker=RESOLUTION_MARKERS[resolution],
        markevery=max(1, len(curve) // 9),
        markerfacecolor="white",
        markeredgecolor=RESOLUTION_COLORS[resolution],
        markeredgewidth=0.75,
        markersize=3.6,
        lw=NUMERICAL_LINEWIDTH_PT,
        zorder=2 + RESOLUTIONS.index(resolution),
    )


def plot_overall(
    ax: plt.Axes,
    *,
    reference: np.ndarray,
    curves: dict[int, np.ndarray],
    case: int,
    show_zoom_box: bool,
) -> None:
    plot_reference(ax, reference)
    for resolution in RESOLUTIONS:
        plot_numerical_curve(ax, curves[resolution], resolution)

    if case == 1:
        style_axis(
            ax,
            xlim=CASE1_XLIM,
            ylim=CASE1_YLIM,
            xticks=CASE1_XTICKS,
            yticks=CASE1_YTICKS,
        )
    else:
        style_axis(
            ax,
            xlim=CASE2_XLIM,
            ylim=CASE2_YLIM,
            xticks=CASE2_XTICKS,
            yticks=CASE2_YTICKS,
        )
        if show_zoom_box:
            ax.add_patch(
                Rectangle(
                    (ZOOM_XLIM[0], ZOOM_YLIM[0]),
                    ZOOM_XLIM[1] - ZOOM_XLIM[0],
                    ZOOM_YLIM[1] - ZOOM_YLIM[0],
                    **ZOOM_BOX_STYLE,
                )
            )


def plot_zoom(
    ax: plt.Axes,
    *,
    reference: np.ndarray,
    curve: np.ndarray,
    resolution: int,
) -> None:
    plot_reference(ax, reference)
    plot_numerical_curve(ax, curve, resolution)
    style_axis(
        ax,
        xlim=ZOOM_XLIM,
        ylim=ZOOM_YLIM,
        xticks=ZOOM_XTICKS,
        yticks=ZOOM_YTICKS,
        minor_ticks=False,
    )


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(s=f"({label})", transform=ax.transAxes, **PANEL_LABEL_STYLE)


def add_shared_legend(fig: plt.Figure) -> None:
    reference_handle = Line2D(
        [0],
        [0],
        color="black",
        lw=REFERENCE_LINEWIDTH_PT,
        linestyle=REFERENCE_LINESTYLE,
        label="Reference",
    )
    resolution_handles = [
        Line2D(
            [0],
            [0],
            color=RESOLUTION_COLORS[resolution],
            linestyle=RESOLUTION_LINESTYLES[resolution],
            marker=RESOLUTION_MARKERS[resolution],
            markerfacecolor="white",
            markeredgecolor=RESOLUTION_COLORS[resolution],
            markeredgewidth=0.75,
            markersize=3.6,
            lw=NUMERICAL_LINEWIDTH_PT,
            label=str(resolution),
        )
        for resolution in RESOLUTIONS
    ]
    reference_legend = fig.legend(
        handles=[reference_handle],
        loc="upper center",
        bbox_to_anchor=(0.255, 0.94),
        handlelength=2.35,
        handletextpad=0.55,
    )
    resolution_legend = fig.legend(
        handles=resolution_handles,
        loc="upper center",
        bbox_to_anchor=(0.675, 0.94),
        ncol=5,
        handlelength=2.35,
        handletextpad=0.55,
        columnspacing=1.0,
    )
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    reference_box = reference_legend.get_window_extent(renderer).transformed(
        fig.transFigure.inverted()
    )
    resolution_box = resolution_legend.get_window_extent(renderer).transformed(
        fig.transFigure.inverted()
    )
    legend_center_y = 0.25 * (
        reference_box.y0
        + reference_box.y1
        + resolution_box.y0
        + resolution_box.y1
    )
    fig.text(
        0.350,
        legend_center_y,
        "Grid resolution:",
        ha="left",
        va="center",
        fontsize=LEGEND_FONTSIZE_PT,
    )


def draw_case1_panels(
    fig: plt.Figure,
    grid,
    curves: dict[tuple[int, str, int], np.ndarray],
    reference: np.ndarray,
    *,
    panel_labels: tuple[str, str, str],
    show_horizontal_labels: bool,
) -> list[plt.Axes]:
    case1_axes: list[plt.Axes] = []
    for method_column, method in enumerate(METHODS):
        ax = fig.add_subplot(grid[0, method_column])
        case1_axes.append(ax)
        plot_overall(
            ax,
            reference=reference,
            curves={
                resolution: curves[(1, method, resolution)]
                for resolution in RESOLUTIONS
            },
            case=1,
            show_zoom_box=False,
        )
        ax.set_title(canonical_method_label(method), pad=4)
        add_panel_label(ax, panel_labels[method_column])
        if not show_horizontal_labels:
            ax.tick_params(axis="x", labelbottom=False)
        if method_column == 0:
            ax.set_ylabel(r"$y$")
        else:
            ax.tick_params(axis="y", labelleft=False)
        if show_horizontal_labels and method_column == 1:
            ax.set_xlabel(r"$x$")
    return case1_axes


def draw_case2_panels(
    fig: plt.Figure,
    row_specs,
    curves: dict[tuple[int, str, int], np.ndarray],
    reference: np.ndarray,
    *,
    panel_labels: tuple[str, str, str],
) -> tuple[list[plt.Axes], list[list[plt.Axes]]]:

    case2_overall_axes: list[plt.Axes] = []
    case2_zoom_axes: list[list[plt.Axes]] = []
    for method_row, method in enumerate(METHODS):
        row_grid = row_specs[method_row].subgridspec(
            1,
            6,
            width_ratios=CASE2_WIDTH_RATIOS,
            wspace=0.10,
        )
        overall_ax = fig.add_subplot(row_grid[0, 0])
        zoom_axes = [fig.add_subplot(row_grid[0, column]) for column in range(1, 6)]
        case2_overall_axes.append(overall_ax)
        case2_zoom_axes.append(zoom_axes)

        method_curves = {
            resolution: curves[(2, method, resolution)]
            for resolution in RESOLUTIONS
        }
        plot_overall(
            overall_ax,
            reference=reference,
            curves=method_curves,
            case=2,
            show_zoom_box=True,
        )
        add_panel_label(overall_ax, panel_labels[method_row])
        overall_ax.text(
            0.02,
            1.035,
            canonical_method_label(method),
            transform=overall_ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=BODY_TEXT_PT,
        )
        overall_ax.set_ylabel(r"$y$")
        if method_row < len(METHODS) - 1:
            overall_ax.tick_params(axis="x", labelbottom=False)
        else:
            overall_ax.set_xlabel(r"$x$")

        for zoom_column, (resolution, zoom_ax) in enumerate(
            zip(RESOLUTIONS, zoom_axes, strict=True)
        ):
            plot_zoom(
                zoom_ax,
                reference=reference,
                curve=method_curves[resolution],
                resolution=resolution,
            )
            if method_row == 0:
                zoom_ax.set_title(rf"$N={resolution}$", pad=3)
            if zoom_column > 0:
                zoom_ax.tick_params(axis="y", labelleft=False)
            if method_row < len(METHODS) - 1:
                zoom_ax.tick_params(axis="x", labelbottom=False)
    return case2_overall_axes, case2_zoom_axes


def add_case2_layout_labels(
    fig: plt.Figure,
    overall_axes: list[plt.Axes],
    zoom_axes: list[list[plt.Axes]],
    *,
    case_label_x: float,
    shared_x_offset: float,
    shared_y_offset: float,
) -> None:
    fig.canvas.draw()
    case2_top = overall_axes[0].get_position().y1
    case2_bottom = overall_axes[-1].get_position().y0
    fig.text(
        case_label_x,
        0.5 * (case2_top + case2_bottom),
        "Test Case 2",
        rotation=90,
        ha="center",
        va="center",
        fontsize=BODY_TEXT_PT,
    )

    first_zoom_position = zoom_axes[0][0].get_position()
    bottom_first_zoom = zoom_axes[-1][0].get_position()
    bottom_last_zoom = zoom_axes[-1][-1].get_position()
    fig.text(
        first_zoom_position.x0 - shared_x_offset,
        0.5 * (case2_top + case2_bottom),
        r"$y$",
        rotation=90,
        ha="center",
        va="center",
    )
    fig.text(
        0.5 * (bottom_first_zoom.x0 + bottom_last_zoom.x1),
        bottom_first_zoom.y0 - shared_y_offset,
        r"$x$",
        ha="center",
        va="top",
    )


def build_figure(
    curves: dict[tuple[int, str, int], np.ndarray],
    references: dict[int, np.ndarray],
) -> tuple[plt.Figure, dict[str, list[plt.Axes] | list[list[plt.Axes]]]]:
    """Build the retained four-row combined figure."""
    fig = plt.figure(figsize=figure_size("double", FIGURE_HEIGHT_MM))
    outer = fig.add_gridspec(
        nrows=4,
        ncols=1,
        left=0.075,
        right=0.992,
        bottom=0.055,
        top=0.905,
        height_ratios=OUTER_HEIGHT_RATIOS,
        hspace=0.16,
    )

    case1_grid = outer[0].subgridspec(1, 3, wspace=0.18)
    case1_axes = draw_case1_panels(
        fig,
        case1_grid,
        curves,
        references[1],
        panel_labels=("a", "b", "c"),
        show_horizontal_labels=False,
    )
    case2_overall_axes, case2_zoom_axes = draw_case2_panels(
        fig,
        [outer[index] for index in range(1, 4)],
        curves,
        references[2],
        panel_labels=("d", "e", "f"),
    )

    fig.canvas.draw()
    case1_position = case1_axes[0].get_position()
    fig.text(
        0.020,
        case1_position.y0 + 0.5 * case1_position.height,
        "Test Case 1",
        rotation=90,
        ha="center",
        va="center",
        fontsize=BODY_TEXT_PT,
    )
    add_case2_layout_labels(
        fig,
        case2_overall_axes,
        case2_zoom_axes,
        case_label_x=0.012,
        shared_x_offset=0.016,
        shared_y_offset=0.030,
    )

    add_shared_legend(fig)
    return fig, {
        "case1_overall": case1_axes,
        "case2_overall": case2_overall_axes,
        "case2_zoom": case2_zoom_axes,
    }


def build_case1_figure(
    curves: dict[tuple[int, str, int], np.ndarray],
    reference: np.ndarray,
) -> tuple[plt.Figure, dict[str, list[plt.Axes]]]:
    """Build the standalone Case 1 grid-convergence figure."""
    fig = plt.figure(figsize=figure_size("double", CASE1_FIGURE_HEIGHT_MM))
    grid = fig.add_gridspec(
        1,
        3,
        left=0.075,
        right=0.965,
        bottom=0.120,
        top=0.720,
        wspace=0.18,
    )
    axes = draw_case1_panels(
        fig,
        grid,
        curves,
        reference,
        panel_labels=("a", "b", "c"),
        show_horizontal_labels=True,
    )
    for ax in axes:
        ax.set_anchor("N")
    fig.canvas.draw()
    position = axes[0].get_position()
    fig.text(
        0.030,
        position.y0 + 0.5 * position.height,
        "Test Case 1",
        rotation=90,
        ha="center",
        va="center",
        fontsize=BODY_TEXT_PT,
    )
    add_shared_legend(fig)
    return fig, {"case1_overall": axes}


def build_case2_figure(
    curves: dict[tuple[int, str, int], np.ndarray],
    reference: np.ndarray,
) -> tuple[plt.Figure, dict[str, list[plt.Axes] | list[list[plt.Axes]]]]:
    """Build the standalone Case 2 overall-plus-right-skirt figure."""
    fig = plt.figure(figsize=figure_size("double", CASE2_FIGURE_HEIGHT_MM))
    outer = fig.add_gridspec(
        3,
        1,
        left=0.065,
        right=0.975,
        bottom=0.065,
        top=0.880,
        hspace=0.18,
    )
    overall_axes, zoom_axes = draw_case2_panels(
        fig,
        [outer[index] for index in range(3)],
        curves,
        reference,
        panel_labels=("a", "b", "c"),
    )
    add_case2_layout_labels(
        fig,
        overall_axes,
        zoom_axes,
        case_label_x=0.025,
        shared_x_offset=0.012,
        shared_y_offset=0.025,
    )
    add_shared_legend(fig)
    return fig, {"case2_overall": overall_axes, "case2_zoom": zoom_axes}


def main() -> None:
    setup_style()
    curves = {
        (case, method, resolution): phase_fraction_contour(case, resolution, method)
        for case in (1, 2)
        for method in METHODS
        for resolution in RESOLUTIONS
    }
    references = {case: reference_curve(case) for case in (1, 2)}
    if OUTPUT_SUFFIX:
        figure_builders = (
            (CASE1_OUTPUT_STEM, lambda: build_case1_figure(curves, references[1])),
            (CASE2_OUTPUT_STEM, lambda: build_case2_figure(curves, references[2])),
        )
    else:
        figure_builders = (
            (OUTPUT_STEM, lambda: build_figure(curves, references)),
            (CASE1_OUTPUT_STEM, lambda: build_case1_figure(curves, references[1])),
            (CASE2_OUTPUT_STEM, lambda: build_case2_figure(curves, references[2])),
        )
    for output_stem, builder in figure_builders:
        fig, _ = builder()
        png_path = save_figure(fig, output_stem)
        plt.close(fig)
        print(png_path)
    print("validated 30 closed t=3 f=0.5 numerical contours")


if __name__ == "__main__":
    main()
