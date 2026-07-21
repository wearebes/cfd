#!/usr/bin/env python3
"""Case-local plotting implementation shared by stationary-bubble figures."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-stationary-mpl")
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
SOURCE_DATA = HERE / "shared_data/imax_metrics.csv"
def repository_root() -> Path:
    for parent in HERE.parents:
        if (parent / "generate").is_dir() and (parent / "dataset").is_dir():
            return parent
    raise RuntimeError("Could not locate the repository root")


ROOT = repository_root()
# Legacy directory name retained on disk; these are Basilisk VOF--HF traces.
VOF_HF_DATA_ROOT = ROOT / "dataset/stationary_bubble/reference/csf_default"

RESOLUTIONS = (64, 128, 256)
IMAX_VALUES = (0, 1, 2, 3, 4, 5)
LAPLACE = 12000.0
NEGATIVE = "#D55E00"
POSITIVE = "#0072B2"
NEUTRAL = "#F7F7F4"
VOF_HF_COLOR = "#6F4C9B"
GRID_STYLES = (
    (64, "#E69F00", "o"),
    (128, "#009E73", "s"),
    (256, "#0072B2", "D"),
)
COMPARISON_IMAX = (
    (0, "#E69F00", "imax=0"),
    (1, "#009E73", "imax=1"),
    (3, "#0072B2", "imax=3"),
)
COMPARISON_METHODS = (
    ("clsvof", "CLSVOF", "-", "filled"),
    ("nn", "CLSVOF NN cell-offset", "--", "open"),
)


def build_vof_hf_source_data(output_path: Path) -> pd.DataFrame:
    """Derive VOF--HF Ca metrics from the archived Basilisk time series."""
    rows: list[dict[str, object]] = []
    ca_scale = np.sqrt(LAPLACE)
    for resolution in RESOLUTIONS:
        source_path = (
            VOF_HF_DATA_ROOT / f"N{resolution:04d}" / "timeseries.dat"
        )
        series = np.loadtxt(source_path, dtype=float)
        if series.ndim == 1:
            series = series.reshape(1, -1)
        if series.shape[1] != 3 or len(series) == 0:
            raise ValueError(
                f"expected a non-empty three-column VOF-HF trace: {source_path}"
            )
        if not np.isfinite(series).all():
            raise ValueError(f"non-finite VOF-HF value: {source_path}")
        if np.any(np.diff(series[:, 0]) < 0.0):
            raise ValueError(f"non-monotone VOF-HF time coordinate: {source_path}")

        ca = series[:, 1] / ca_scale
        rows.append(
            {
                "method_id": "vof_hf",
                "resolution": resolution,
                "laplace_number": LAPLACE,
                "samples": len(series),
                "terminal_tau": series[-1, 0],
                "u_star_max": np.max(series[:, 1]),
                "u_star_final": series[-1, 1],
                "delta_c_final": series[-1, 2],
                "ca_max": np.max(ca),
                "ca_final": ca[-1],
                "endpoint_basis": "last_recorded_sample",
                "source_file": str(source_path.relative_to(ROOT)),
            }
        )

    source_data = pd.DataFrame(rows)
    source_data.to_csv(output_path, index=False, float_format="%.17g")
    return source_data


def select_one(
    metrics: pd.DataFrame, resolution: int, imax: int, method: str
) -> pd.Series:
    selected = metrics[
        metrics["benchmark"].eq("stationary_bubble")
        & metrics["resolution"].eq(resolution)
        & metrics["imax"].eq(imax)
        & metrics["method_id"].eq(method)
    ]
    if len(selected) != 1:
        raise ValueError(
            f"expected one stationary row for N{resolution}, imax={imax}, {method}"
        )
    return selected.iloc[0]


def endpoint_state(row: pd.Series) -> str:
    """Classify a normal endpoint using the stationary case's stop contract."""
    if str(row["state"]) != "completed":
        return "invalid"
    if bool(row["terminal_complete"]):
        return "time_limit_reached"
    # The stationary case has one pre-TMAX stop path: change(f, fn) < 1e-10.
    return "converged_early"


def build_source_data(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for resolution in RESOLUTIONS:
        for imax in IMAX_VALUES:
            native = select_one(metrics, resolution, imax, "clsvof")
            nn = select_one(metrics, resolution, imax, "nn")
            native_endpoint = endpoint_state(native)
            nn_endpoint = endpoint_state(nn)
            endpoint_comparison_eligible = (
                native_endpoint != "invalid" and nn_endpoint != "invalid"
            )
            ca_max_native = float(native["ca_max"])
            ca_max_nn = float(nn["ca_max"])
            ca_final_native = float(native["ca_final"])
            ca_final_nn = float(nn["ca_final"])
            rows.append(
                {
                    "resolution": resolution,
                    "imax": imax,
                    "ca_max_clsvof": ca_max_native,
                    "ca_max_nn": ca_max_nn,
                    "ca_max_nn_improvement_percent": (
                        100.0 * (ca_max_native - ca_max_nn) / ca_max_native
                        if endpoint_comparison_eligible
                        else np.nan
                    ),
                    "ca_final_clsvof": ca_final_native,
                    "ca_final_nn": ca_final_nn,
                    "ca_final_nn_improvement_percent": (
                        100.0 * (ca_final_native - ca_final_nn) / ca_final_native
                        if endpoint_comparison_eligible
                        else np.nan
                    ),
                    "terminal_time_clsvof": float(native["terminal_time"]),
                    "terminal_time_nn": float(nn["terminal_time"]),
                    "last_delta_f_clsvof": float(native["delta_f_final"]),
                    "last_delta_f_nn": float(nn["delta_f_final"]),
                    "endpoint_state_clsvof": native_endpoint,
                    "endpoint_state_nn": nn_endpoint,
                    "audit_terminal_complete_pair": bool(
                        native["terminal_complete"]
                    )
                    and bool(nn["terminal_complete"]),
                    "audit_scientific_valid_pair": bool(native["scientific_valid"])
                    and bool(nn["scientific_valid"]),
                    "endpoint_comparison_eligible": endpoint_comparison_eligible,
                }
            )
    return pd.DataFrame(rows)


def setup_style() -> None:
    plt.rcParams.update(
        {
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
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
            "savefig.transparent": False,
        }
    )


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.10,
        1.04,
        label,
        transform=ax.transAxes,
        fontsize=8,
        fontweight="bold",
        ha="left",
        va="bottom",
    )


def heatmap_array(data: pd.DataFrame, column: str) -> np.ndarray:
    values = np.full((len(RESOLUTIONS), len(IMAX_VALUES)), np.nan)
    for i, resolution in enumerate(RESOLUTIONS):
        for j, imax in enumerate(IMAX_VALUES):
            row = data[
                data["resolution"].eq(resolution) & data["imax"].eq(imax)
            ]
            if len(row) != 1:
                raise ValueError(f"missing source row for N{resolution}, imax={imax}")
            values[i, j] = float(row.iloc[0][column])
    return values


def effect_label(value: float) -> str:
    magnitude = abs(value)
    if magnitude >= 10:
        return f"{value:+.0f}"
    if magnitude >= 1:
        return f"{value:+.1f}"
    if magnitude >= 0.1:
        return f"{value:+.2f}"
    return f"{value:+.3f}"


def draw_heatmaps(data: pd.DataFrame, output_path: Path) -> None:
    cmap = LinearSegmentedColormap.from_list(
        "worse_to_better", [NEGATIVE, NEUTRAL, POSITIVE]
    )
    cmap.set_bad("#E4E4E0")
    norm = SymLogNorm(
        linthresh=0.1,
        linscale=0.75,
        vmin=-100.0,
        vmax=100.0,
        base=10,
    )

    panels = (
        ("ca_max_nn_improvement_percent", r"$Ca_{\max}$"),
        ("ca_final_nn_improvement_percent", r"$Ca_{\mathrm{final}}$"),
    )
    fig = plt.figure(figsize=(183 / 25.4, 76 / 25.4))
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=(1.0, 1.0, 0.045),
        left=0.085,
        right=0.91,
        bottom=0.22,
        top=0.90,
        wspace=0.21,
    )
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])]
    colorbar_ax = fig.add_subplot(grid[0, 2])

    image = None
    for panel_index, (ax, (column, title)) in enumerate(zip(axes, panels)):
        values = heatmap_array(data, column)
        image = ax.imshow(values, cmap=cmap, norm=norm, aspect="auto")
        ax.set_title(title, pad=6)
        ax.set_xticks(
            np.arange(len(IMAX_VALUES)),
            ["0", "1", "2", "3\ndefault", "4", "5"],
        )
        ax.set_yticks(
            np.arange(len(RESOLUTIONS)), [f"N{value}" for value in RESOLUTIONS]
        )
        if panel_index:
            ax.set_yticklabels([])
            ax.tick_params(axis="y", length=0)
        ax.set_xticks(np.arange(-0.5, len(IMAX_VALUES), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(RESOLUTIONS), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.1)
        ax.tick_params(which="minor", bottom=False, left=False)
        ax.tick_params(which="major", direction="out", length=2.5, width=0.7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_linewidth(0.75)
        ax.spines["bottom"].set_linewidth(0.75)
        ax.add_patch(
            Rectangle(
                (2.52, -0.48),
                0.96,
                len(RESOLUTIONS) - 0.04,
                fill=False,
                edgecolor="#222222",
                linewidth=0.8,
                clip_on=False,
            )
        )

        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                value = values[i, j]
                if np.isnan(value):
                    label = "—"
                    color = "#737373"
                else:
                    label = effect_label(value)
                    color = "white" if abs(value) >= 4.0 else "#222222"
                ax.text(j, i, label, ha="center", va="center", fontsize=6.6, color=color)

        add_panel_label(ax, chr(ord("a") + panel_index))

    assert image is not None
    colorbar = fig.colorbar(image, cax=colorbar_ax)
    ticks = [-100, -10, -1, 0, 1, 10, 100]
    colorbar.set_ticks(ticks)
    colorbar.set_ticklabels(["-100", "-10", "-1", "0", "+1", "+10", "+100"])
    colorbar.set_label(
        "CLSVOF NN cell-offset improvement over CLSVOF (%)",
        fontsize=7.0,
        labelpad=4,
    )
    colorbar.ax.tick_params(labelsize=6.7, length=2.5)

    axes[0].set_ylabel("Grid")
    fig.supxlabel("Redistance iterations, imax", y=0.055, fontsize=7.0)
    fig.savefig(output_path, dpi=600)
    plt.close(fig)


def draw_clsvof_imax_sweep(data: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(183 / 25.4, 72 / 25.4))
    fig.subplots_adjust(left=0.105, right=0.985, bottom=0.23, top=0.81, wspace=0.28)
    x = np.asarray(IMAX_VALUES, dtype=float)

    panels = (
        ("ca_max_clsvof", r"$Ca_{\max}$"),
        ("ca_final_clsvof", r"$Ca_{\mathrm{final}}$"),
    )

    for panel_index, (ax, (column, title)) in enumerate(zip(axes, panels)):
        for resolution, color, marker in GRID_STYLES:
            selected = data[data["resolution"].eq(resolution)].set_index("imax")
            values = np.array(
                [selected.loc[imax, column] for imax in IMAX_VALUES], dtype=float
            )
            ax.plot(
                x,
                values,
                color=color,
                marker=marker,
                linestyle="-",
                lw=1.15,
                ms=4.2,
                markerfacecolor=color,
                markeredgecolor="white",
                markeredgewidth=0.45,
            )
        ax.set_yscale("log")
        ax.set_xticks(x, ["0", "1", "2", "3\ndefault", "4", "5"])
        ax.set_title(title, pad=6)
        ax.axvline(3, color="#D4D4D4", lw=0.8, zorder=0)
        ax.tick_params(direction="out", length=3, width=0.7)
        ax.set_xlim(-0.2, 5.2)
        add_panel_label(ax, chr(ord("a") + panel_index))

    axes[0].set_ylabel("Capillary number")
    handles = [
        Line2D(
            [0], [0], color=color, marker=marker, lw=1.15, ms=4.2,
            markerfacecolor=color, markeredgecolor="white", markeredgewidth=0.45,
            label=f"N{resolution}"
        )
        for resolution, color, marker in GRID_STYLES
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.55, 0.98),
        ncol=3,
        handlelength=1.8,
        columnspacing=1.8,
    )
    fig.supxlabel("Redistance iterations, imax", y=0.055, fontsize=7.0)
    fig.savefig(output_path, dpi=600)
    plt.close(fig)


def draw_imax0_1_3(
    data: pd.DataFrame, vof_hf: pd.DataFrame, output_path: Path
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(183 / 25.4, 72 / 25.4))
    fig.subplots_adjust(
        left=0.105,
        right=0.985,
        bottom=0.23,
        top=0.77,
        wspace=0.28,
    )
    x = np.arange(len(RESOLUTIONS), dtype=float)
    panels = (
        ("ca_max", r"$Ca_{\max}$"),
        ("ca_final", r"$Ca_{\mathrm{final}}$"),
    )
    vof_hf_by_resolution = vof_hf.set_index("resolution")
    if set(vof_hf_by_resolution.index) != set(RESOLUTIONS):
        raise ValueError("VOF-HF source data do not contain N64, N128, and N256")

    for panel_index, (ax, (metric, title)) in enumerate(zip(axes, panels)):
        for imax, color, _ in COMPARISON_IMAX:
            for method_column, _, linestyle, marker_fill in COMPARISON_METHODS:
                values = []
                for resolution in RESOLUTIONS:
                    selected = data[
                        data["resolution"].eq(resolution) & data["imax"].eq(imax)
                    ]
                    if len(selected) != 1:
                        raise ValueError(
                            f"missing stationary comparison row: N{resolution}, imax={imax}"
                        )
                    values.append(
                        float(selected.iloc[0][f"{metric}_{method_column}"])
                    )
                ax.plot(
                    x,
                    values,
                    color=color,
                    marker="o",
                    linestyle=linestyle,
                    lw=1.1,
                    ms=4.0,
                    markerfacecolor=color if marker_fill == "filled" else "white",
                    markeredgecolor=color,
                    markeredgewidth=0.75,
                )

        ax.plot(
            x,
            [
                float(vof_hf_by_resolution.loc[resolution, metric])
                for resolution in RESOLUTIONS
            ],
            color=VOF_HF_COLOR,
            marker="D",
            linestyle="-.",
            lw=1.25,
            ms=4.0,
            markerfacecolor="white",
            markeredgecolor=VOF_HF_COLOR,
            markeredgewidth=0.85,
            zorder=5,
        )

        ax.set_yscale("log")
        ax.set_xticks(x, [f"N{resolution}" for resolution in RESOLUTIONS])
        ax.set_title(title, pad=6)
        ax.tick_params(direction="out", length=3, width=0.7)
        ax.set_xlim(-0.18, len(RESOLUTIONS) - 0.82)
        add_panel_label(ax, chr(ord("a") + panel_index))

    axes[0].set_ylabel("Capillary number")
    method_handles = [
        Line2D(
            [0],
            [0],
            color="#303030",
            marker="o",
            linestyle=linestyle,
            lw=1.1,
            ms=4.0,
            markerfacecolor="#303030" if marker_fill == "filled" else "white",
            markeredgecolor="#303030",
            markeredgewidth=0.75,
            label=label,
        )
        for _, label, linestyle, marker_fill in COMPARISON_METHODS
    ]
    method_handles.append(
        Line2D(
            [0],
            [0],
            color=VOF_HF_COLOR,
            marker="D",
            linestyle="-.",
            lw=1.25,
            ms=4.0,
            markerfacecolor="white",
            markeredgecolor=VOF_HF_COLOR,
            markeredgewidth=0.85,
            label="VOF–HF",
        )
    )
    imax_handles = [
        Line2D([0], [0], color=color, lw=1.8, label=label)
        for _, color, label in COMPARISON_IMAX
    ]
    fig.legend(
        handles=method_handles + imax_handles,
        loc="upper center",
        bbox_to_anchor=(0.55, 0.98),
        ncol=6,
        handlelength=2.0,
        columnspacing=1.05,
    )
    fig.supxlabel("Grid", y=0.055, fontsize=7.0)
    fig.savefig(output_path, dpi=600)
    plt.close(fig)


def load_data() -> pd.DataFrame:
    data = pd.read_csv(SOURCE_DATA)
    if len(data) != 18:
        raise ValueError(f"expected 18 curated stationary rows, found {len(data)}")

    imax0 = data[data["imax"].eq(0)]
    if set(imax0["endpoint_state_clsvof"]) != {"converged_early"} or set(
        imax0["endpoint_state_nn"]
    ) != {"converged_early"}:
        raise ValueError("stationary imax=0 rows are not consistently converged early")
    complete = data[data["imax"].ne(0)]
    if set(complete["endpoint_state_clsvof"]) != {"time_limit_reached"} or set(
        complete["endpoint_state_nn"]
    ) != {"time_limit_reached"}:
        raise ValueError("stationary imax=1..5 rows did not reach the time limit")
    if not data["endpoint_comparison_eligible"].all():
        raise ValueError("a stationary endpoint pair is not comparison-eligible")
    return data
