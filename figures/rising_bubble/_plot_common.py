#!/usr/bin/env python3
"""Shared, source-backed plotting for the rising-bubble benchmark."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-rising-mpl")
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, SymLogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


HERE = Path(__file__).resolve().parent
SOURCE_DIR = HERE / "shared_data"
PAIRED_SOURCE = SOURCE_DIR / "imax_metrics.csv"

BENCHMARKS = ("rising_case1", "rising_case2")
RESOLUTIONS = (64, 128, 256, 512)
IMAX_VALUES = (0, 1, 2, 3, 4, 5)

IMAX3 = "#0072B2"
IMAX0 = "#D55E00"
REFERENCE = "#5F6368"
NEGATIVE = "#D55E00"
POSITIVE = "#0072B2"
NEUTRAL = "#F7F7F4"

METRIC_SPECS = (
    {
        "key": "max_abs_relative_volume_error",
        "title": r"Maximum volume error",
        "ylabel": r"$E_{V,\max}$",
    },
    {
        "key": "velocity_reference_rmse",
        "title": r"Rise-velocity RMSE",
        "ylabel": r"RMSE($V_c$)",
    },
    {
        "key": "center_reference_rmse",
        "title": r"Center-height RMSE",
        "ylabel": r"RMSE($z_c$)",
    },
    {
        "key": "circularity_final_abs_error",
        "title": r"Final circularity error",
        "ylabel": r"$|\phi_c(3)-\phi_c^{ref}(3)|$",
    },
)

SERIES = (
    {
        "method": "clsvof",
        "column": "clsvof",
        "imax": 3,
        "color": IMAX3,
        "marker": "o",
        "linestyle": "-",
        "face": IMAX3,
        "label": "CLSVOF, imax=3",
    },
    {
        "method": "nn",
        "column": "nn",
        "imax": 3,
        "color": IMAX3,
        "marker": "D",
        "linestyle": "--",
        "face": "white",
        "label": "NN, imax=3",
    },
    {
        "method": "clsvof",
        "column": "clsvof",
        "imax": 0,
        "color": IMAX0,
        "marker": "o",
        "linestyle": "-",
        "face": IMAX0,
        "label": "CLSVOF, imax=0",
    },
    {
        "method": "nn",
        "column": "nn",
        "imax": 0,
        "color": IMAX0,
        "marker": "D",
        "linestyle": "--",
        "face": "white",
        "label": "NN, imax=0",
    },
)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7.0,
            "axes.labelsize": 7.0,
            "axes.titlesize": 7.2,
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 6.8,
            "axes.linewidth": 0.75,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "legend.frameon": False,
            "legend.fontsize": 6.8,
            "lines.solid_capstyle": "round",
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
            "savefig.transparent": False,
        }
    )


def save_figure(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=600)
    fig.savefig(output_path.with_suffix(".svg"))
    plt.close(fig)


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.12,
        1.04,
        label,
        transform=ax.transAxes,
        fontsize=8.2,
        fontweight="bold",
        ha="left",
        va="bottom",
    )


def series_handles(include_reference: bool = False) -> list[Line2D]:
    handles: list[Line2D] = []
    if include_reference:
        handles.append(
            Line2D([0], [0], color=REFERENCE, lw=1.15, label="Hysing reference")
        )
    for item in SERIES:
        handles.append(
            Line2D(
                [0],
                [0],
                color=str(item["color"]),
                marker=str(item["marker"]),
                linestyle=str(item["linestyle"]),
                lw=1.0,
                ms=3.5,
                markerfacecolor=str(item["face"]),
                markeredgecolor=str(item["color"]),
                markeredgewidth=0.75,
                label=str(item["label"]),
            )
        )
    return handles


def load_data() -> pd.DataFrame:
    data = pd.read_csv(PAIRED_SOURCE)
    if len(data) != 48:
        raise ValueError(f"expected 48 paired rising rows, got {len(data)}")
    expected = {
        (benchmark, resolution, imax)
        for benchmark in BENCHMARKS
        for resolution in RESOLUTIONS
        for imax in IMAX_VALUES
    }
    actual = {
        (str(row.benchmark), int(row.resolution), int(row.imax))
        for row in data.itertuples()
    }
    if actual != expected:
        raise ValueError("paired source identities do not match the 48-row contract")
    return data


def heatmap_array(data: pd.DataFrame, column: str) -> np.ndarray:
    values = np.empty((len(BENCHMARKS) * len(RESOLUTIONS), len(IMAX_VALUES)))
    row_index = 0
    for benchmark in BENCHMARKS:
        for resolution in RESOLUTIONS:
            for column_index, imax in enumerate(IMAX_VALUES):
                selected = data[
                    data["benchmark"].eq(benchmark)
                    & data["resolution"].eq(resolution)
                    & data["imax"].eq(imax)
                ]
                if len(selected) != 1:
                    raise ValueError(
                        f"missing heatmap row for {benchmark}, N{resolution}, imax={imax}"
                    )
                values[row_index, column_index] = float(selected.iloc[0][column])
            row_index += 1
    return values


def effect_label(value: float) -> str:
    if abs(value) >= 10:
        return f"{value:+.0f}"
    if abs(value) >= 1:
        return f"{value:+.1f}"
    if abs(value) >= 0.1:
        return f"{value:+.2f}"
    if abs(value) >= 0.001:
        return f"{value:+.3f}"
    return f"{value:+.0e}"


def draw_heatmap(data: pd.DataFrame, output_path: Path) -> None:
    cmap = LinearSegmentedColormap.from_list(
        "worse_to_better", [NEGATIVE, NEUTRAL, POSITIVE]
    )
    norm = SymLogNorm(
        linthresh=0.1, linscale=0.75, vmin=-100.0, vmax=100.0, base=10
    )
    fig = plt.figure(figsize=(183 / 25.4, 116 / 25.4))
    grid = fig.add_gridspec(
        2,
        3,
        width_ratios=(1.0, 1.0, 0.045),
        left=0.105,
        right=0.91,
        bottom=0.13,
        top=0.93,
        hspace=0.29,
        wspace=0.18,
    )
    axes = [
        fig.add_subplot(grid[row, column])
        for row in range(2)
        for column in range(2)
    ]
    colorbar_ax = fig.add_subplot(grid[:, 2])
    row_labels = [
        f"C{case}  N{resolution}"
        for case in (1, 2)
        for resolution in RESOLUTIONS
    ]
    image = None
    for panel_index, (ax, spec) in enumerate(zip(axes, METRIC_SPECS)):
        column = f"{spec['key']}_nn_improvement_percent"
        values = heatmap_array(data, column)
        image = ax.imshow(values, cmap=cmap, norm=norm, aspect="auto")
        ax.set_title(str(spec["title"]), pad=5)
        ax.set_xticks(
            np.arange(len(IMAX_VALUES)), ["0", "1", "2", "3\ndefault", "4", "5"]
        )
        ax.set_yticks(np.arange(len(row_labels)))
        if panel_index % 2 == 0:
            ax.set_yticklabels(row_labels)
            ax.set_ylabel("Case and grid")
        else:
            ax.set_yticklabels([])
            ax.tick_params(axis="y", length=0)
        ax.axhline(3.5, color="white", lw=1.8)
        ax.set_xticks(np.arange(-0.5, len(IMAX_VALUES), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(row_labels), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=0.85)
        ax.tick_params(which="minor", bottom=False, left=False)
        ax.tick_params(which="major", direction="out", length=2.5, width=0.7)
        ax.add_patch(
            Rectangle(
                (2.52, -0.48),
                0.96,
                len(row_labels) - 0.04,
                fill=False,
                edgecolor="#222222",
                linewidth=0.8,
                clip_on=False,
            )
        )
        for row in range(values.shape[0]):
            for column_index in range(values.shape[1]):
                value = values[row, column_index]
                red, green, blue, _ = cmap(norm(value))
                luminance = 0.299 * red + 0.587 * green + 0.114 * blue
                ax.text(
                    column_index,
                    row,
                    effect_label(value),
                    ha="center",
                    va="center",
                    fontsize=5.0,
                    color="white" if luminance < 0.48 else "#202020",
                )
        add_panel_label(ax, chr(ord("a") + panel_index))
    assert image is not None
    colorbar = fig.colorbar(image, cax=colorbar_ax)
    ticks = [-100, -10, -1, 0, 1, 10, 100]
    colorbar.set_ticks(ticks)
    colorbar.set_ticklabels(["-100", "-10", "-1", "0", "+1", "+10", "+100"])
    colorbar.set_label(
        "NN improvement over CLSVOF (%)\npositive = lower error; color clipped at ±100",
        labelpad=4,
    )
    colorbar.ax.tick_params(labelsize=6.6, length=2.5)
    fig.supxlabel("Redistance iterations, imax", y=0.035)
    save_figure(fig, output_path)


def absolute_values(
    data: pd.DataFrame,
    benchmark: str,
    metric: str,
    method_column: str,
    imax: int,
) -> np.ndarray:
    values: list[float] = []
    for resolution in RESOLUTIONS:
        selected = data[
            data["benchmark"].eq(benchmark)
            & data["resolution"].eq(resolution)
            & data["imax"].eq(imax)
        ]
        if len(selected) != 1:
            raise ValueError("missing raw comparison row")
        value = float(selected.iloc[0][f"{metric}_{method_column}"])
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError(f"invalid positive error for log plot: {value}")
        values.append(value)
    return np.asarray(values)


def draw_imax0_vs3(data: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(183 / 25.4, 96 / 25.4))
    fig.subplots_adjust(
        left=0.085, right=0.992, bottom=0.14, top=0.82, hspace=0.39, wspace=0.34
    )
    x = np.arange(len(RESOLUTIONS), dtype=float)
    for row_index, benchmark in enumerate(BENCHMARKS):
        for column_index, spec in enumerate(METRIC_SPECS):
            ax = axes[row_index, column_index]
            metric = str(spec["key"])
            for item in SERIES:
                values = absolute_values(
                    data,
                    benchmark,
                    metric,
                    str(item["column"]),
                    int(item["imax"]),
                )
                ax.plot(
                    x,
                    values,
                    color=str(item["color"]),
                    marker=str(item["marker"]),
                    linestyle=str(item["linestyle"]),
                    lw=1.0,
                    ms=3.7,
                    markerfacecolor=str(item["face"]),
                    markeredgecolor=str(item["color"]),
                    markeredgewidth=0.75,
                )
            ax.set_yscale("log")
            ax.set_xticks(x, [f"N{value}" for value in RESOLUTIONS])
            ax.tick_params(direction="out", length=3, width=0.7)
            if row_index == 0:
                ax.set_title(str(spec["title"]), pad=5)
            ax.set_ylabel(str(spec["ylabel"]))
            add_panel_label(ax, chr(ord("a") + row_index * 4 + column_index))
    fig.text(0.012, 0.585, "Case 1", rotation=90, ha="center", va="center")
    fig.text(0.012, 0.245, "Case 2", rotation=90, ha="center", va="center")
    fig.legend(
        handles=series_handles(),
        loc="upper center",
        bbox_to_anchor=(0.54, 0.975),
        ncol=4,
        handlelength=2.2,
        columnspacing=1.35,
    )
    save_figure(fig, output_path)


def load_time_sources(resolution: int = 512) -> tuple[pd.DataFrame, pd.DataFrame]:
    dynamics = pd.read_csv(SOURCE_DIR / f"dynamics_N{resolution}_imax0_vs3.csv")
    circularity = pd.read_csv(
        SOURCE_DIR / f"circularity_N{resolution}_imax0_vs3.csv"
    )
    return dynamics, circularity


def select_curve(
    data: pd.DataFrame, benchmark: str, method: str, imax: str | int
) -> pd.DataFrame:
    selected = data[
        data["benchmark"].eq(benchmark)
        & data["method_id"].eq(method)
        & data["imax"].astype(str).eq(str(imax))
    ]
    order_column = "time" if "time" in selected.columns else "segment"
    selected = selected.sort_values(order_column)
    if selected.empty:
        raise ValueError(f"missing curve: {benchmark}, {method}, imax={imax}")
    return selected


def draw_time_histories(
    dynamics: pd.DataFrame,
    circularity: pd.DataFrame,
    output_path: Path,
) -> None:
    history_specs = (
        (dynamics, "relative_volume_error", r"Relative volume error", r"$\varepsilon_V$"),
        (dynamics, "rise_velocity", r"Mean rise velocity", r"$V_c$"),
        (dynamics, "center_height", r"Center height", r"$z_c$"),
        (
            circularity,
            "circularity",
            r"Circularity (numerical: $t=3$ only)",
            r"$\phi_c$",
        ),
    )
    fig, axes = plt.subplots(2, 4, figsize=(183 / 25.4, 96 / 25.4))
    fig.subplots_adjust(
        left=0.075, right=0.992, bottom=0.14, top=0.82, hspace=0.39, wspace=0.30
    )
    for row_index, benchmark in enumerate(BENCHMARKS):
        for column_index, (frame, column, title, ylabel) in enumerate(history_specs):
            ax = axes[row_index, column_index]
            reference = select_curve(frame, benchmark, "reference", "reference")
            reference = reference[reference["time"].le(3.0 + 1e-12)]
            ax.plot(
                reference["time"],
                reference[column],
                color=REFERENCE,
                lw=1.15,
                zorder=1,
            )
            for item in SERIES:
                curve = select_curve(
                    frame, benchmark, str(item["method"]), int(item["imax"])
                )
                markevery = max(1, len(curve) // 8)
                ax.plot(
                    curve["time"],
                    curve[column],
                    color=str(item["color"]),
                    linestyle=str(item["linestyle"]),
                    marker=str(item["marker"]),
                    markevery=markevery,
                    lw=0.9,
                    ms=2.5,
                    markerfacecolor=str(item["face"]),
                    markeredgecolor=str(item["color"]),
                    markeredgewidth=0.6,
                    zorder=2,
                )
                if column == "circularity":
                    minimum = curve.loc[curve[column].idxmin()]
                    ax.plot(
                        float(minimum["time"]),
                        float(minimum[column]),
                        marker=str(item["marker"]),
                        color=str(item["color"]),
                        markerfacecolor=str(item["face"]),
                        ms=3.2,
                        linestyle="none",
                        zorder=3,
                    )
            ax.set_xlim(0.0, 3.05)
            ax.set_xlabel("Time")
            ax.set_ylabel(ylabel)
            ax.tick_params(direction="out", length=3, width=0.7)
            if row_index == 0:
                ax.set_title(title, pad=5)
            if column == "relative_volume_error":
                ax.ticklabel_format(axis="y", style="sci", scilimits=(-2, 2))
            add_panel_label(ax, chr(ord("a") + row_index * 4 + column_index))
    fig.text(0.012, 0.585, "Case 1", rotation=90, ha="center", va="center")
    fig.text(0.012, 0.245, "Case 2", rotation=90, ha="center", va="center")
    fig.legend(
        handles=series_handles(include_reference=True),
        loc="upper center",
        bbox_to_anchor=(0.54, 0.975),
        ncol=5,
        handlelength=2.1,
        columnspacing=1.2,
    )
    save_figure(fig, output_path)


def interface_chains(frame: pd.DataFrame, mirror_half: bool) -> list[np.ndarray]:
    remaining: list[np.ndarray] = []
    for row in frame.itertuples():
        remaining.append(
            np.asarray(
            [
                [float(row.transverse0), float(row.vertical0)],
                [float(row.transverse1), float(row.vertical1)],
            ]
            )
        )
    chains: list[np.ndarray] = []
    # output_facets() prints neighbouring endpoints independently, so the
    # archived coordinates differ by up to O(1e-3) despite representing one
    # vertex. The tolerance remains below the N512 cell size (1/512).
    tolerance = 1.8e-3
    while remaining:
        first = remaining.pop()
        points = [first[0], first[1]]
        extended = True
        while extended and remaining:
            extended = False
            for index, segment in enumerate(remaining):
                if np.linalg.norm(segment[0] - points[-1]) <= tolerance:
                    points.append(segment[1])
                elif np.linalg.norm(segment[1] - points[-1]) <= tolerance:
                    points.append(segment[0])
                elif np.linalg.norm(segment[1] - points[0]) <= tolerance:
                    points.insert(0, segment[0])
                elif np.linalg.norm(segment[0] - points[0]) <= tolerance:
                    points.insert(0, segment[1])
                else:
                    continue
                remaining.pop(index)
                extended = True
                break
        chains.append(np.asarray(points))
    if mirror_half:
        mirrored = []
        for chain in chains:
            copy = chain.copy()
            copy[:, 0] *= -1.0
            mirrored.append(copy)
        chains.extend(mirrored)
    return chains


def draw_interfaces(
    interfaces: pd.DataFrame,
    output_path: Path,
    resolution: int = 512,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(183 / 25.4, 86 / 25.4))
    fig.subplots_adjust(left=0.09, right=0.985, bottom=0.16, top=0.80, wspace=0.24)
    for panel_index, (ax, benchmark) in enumerate(zip(axes, BENCHMARKS)):
        reference = select_curve(interfaces, benchmark, "reference", "reference")
        for chain in interface_chains(reference, mirror_half=False):
            ax.plot(
                chain[:, 0],
                chain[:, 1],
                color=REFERENCE,
                linewidth=1.4,
                zorder=1,
            )
        for item in SERIES:
            curve = select_curve(
                interfaces, benchmark, str(item["method"]), int(item["imax"])
            )
            for chain in interface_chains(curve, mirror_half=True):
                ax.plot(
                    chain[:, 0],
                    chain[:, 1],
                    color=str(item["color"]),
                    linewidth=0.95,
                    linestyle=str(item["linestyle"]),
                    zorder=2,
                )
        ax.set_xlim(-0.43, 0.43)
        ax.set_ylim(0.58, 1.43)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("Transverse coordinate")
        ax.set_ylabel("Vertical coordinate, z")
        ax.set_title(f"Case {panel_index + 1}, N{resolution}, t=3", pad=5)
        ax.tick_params(direction="out", length=3, width=0.7)
        add_panel_label(ax, chr(ord("a") + panel_index))
    fig.legend(
        handles=series_handles(include_reference=True),
        loc="upper center",
        bbox_to_anchor=(0.54, 0.975),
        ncol=5,
        handlelength=2.1,
        columnspacing=1.2,
    )
    save_figure(fig, output_path)
