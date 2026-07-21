#!/usr/bin/env python3
"""Plot NN cell-offset improvement over CLSVOF for the imax matrix."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-oscillating-mpl")
)

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "font.size": 7,
    "axes.linewidth": 0.8,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "legend.frameon": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

RESOLUTIONS = (64, 128, 256, 512)
IMAX_VALUES = (0, 1, 2, 3, 4, 5)
COLOR_LIMIT = 100.0


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "generate").is_dir() and (parent / "dataset").is_dir():
            return parent
    raise RuntimeError("Could not locate the repository root")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fidelity_improvement(native: float, nn: float) -> float:
    """Percent improvement toward the zero-damping target."""
    if native == 0.0:
        return np.nan
    return 100.0 * (abs(native) - abs(nn)) / abs(native)


def error_reduction(native: float, nn: float) -> float:
    if native == 0.0:
        return np.nan
    return 100.0 * (native - nn) / native


def build_source_rows(result_root: Path) -> list[dict[str, object]]:
    curated = Path(__file__).resolve().parent / "source_data.csv"
    return read_csv(curated)  # type: ignore[return-value]


def write_source_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def matrix_for(rows: list[dict[str, object]], field: str) -> np.ndarray:
    by_key = {(int(row["N"]), int(row["imax"])): row for row in rows}
    matrix = np.full((len(RESOLUTIONS), len(IMAX_VALUES)), np.nan)
    for i, n in enumerate(RESOLUTIONS):
        for j, imax in enumerate(IMAX_VALUES):
            value = by_key[(n, imax)][field]
            if value != "":
                matrix[i, j] = float(value)
    return matrix


def annotation(value: float) -> str:
    if value <= -COLOR_LIMIT:
        return "≤−100"
    if value >= COLOR_LIMIT:
        return "≥100"
    if abs(value) < 10.0:
        label = f"{value:+.1f}"
    else:
        label = f"{value:+.0f}"
    return label.replace("-", "−")


def save_bundle(fig: plt.Figure, stem: Path) -> None:
    export = {"bbox_inches": "tight", "facecolor": "white", "transparent": False}
    fig.savefig(stem.with_suffix(".png"), dpi=600, **export)


def plot_heatmap(rows: list[dict[str, object]], output_stem: Path) -> None:
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "worse_neutral_better", ("#C15A5A", "#F7F7F5", "#3F7FB7")
    )
    cmap.set_bad("#EEEEEC")
    norm = mpl.colors.TwoSlopeNorm(vmin=-COLOR_LIMIT, vcenter=0.0, vmax=COLOR_LIMIT)
    fields = (
        ("damping_fit_fidelity_improvement_pct", "Fitted damping"),
        ("frequency_error_reduction_pct", "Frequency error"),
        ("envelope_fidelity_improvement_pct", "Peak-envelope damping"),
    )
    by_key = {(int(row["N"]), int(row["imax"])): row for row in rows}

    fig, axes = plt.subplots(1, 3, figsize=(183 / 25.4, 72 / 25.4), sharey=True)
    fig.patch.set_facecolor("white")
    image = None
    for panel_index, (ax, (field, title)) in enumerate(zip(axes, fields, strict=True)):
        matrix = matrix_for(rows, field)
        image = ax.imshow(np.ma.masked_invalid(matrix), cmap=cmap, norm=norm,
                          aspect="equal", interpolation="none")
        ax.set_title(title, fontsize=7.2, pad=6)
        ax.text(-0.08, 1.07, chr(ord("a") + panel_index), transform=ax.transAxes,
                fontsize=8, fontweight="bold", va="bottom", ha="left")
        ax.set_xticks(range(len(IMAX_VALUES)), [str(value) for value in IMAX_VALUES])
        ax.set_yticks(range(len(RESOLUTIONS)), [f"N{n}" for n in RESOLUTIONS])
        if panel_index == 0:
            ax.set_ylabel("Resolution")
        ax.tick_params(length=0)

        for i, n in enumerate(RESOLUTIONS):
            for j, imax in enumerate(IMAX_VALUES):
                row = by_key[(n, imax)]
                ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False,
                                       edgecolor="white", linewidth=0.8))
                value = matrix[i, j]
                if not np.isfinite(value):
                    ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1,
                                           facecolor="#EEEEEC", edgecolor="#A8A8A8",
                                           linewidth=0.55, hatch="////"))
                    ax.text(j, i, "—", ha="center", va="center", fontsize=6.0,
                            color="#4D4D4D")
                    continue
                clipped = float(np.clip(value, -COLOR_LIMIT, COLOR_LIMIT))
                red, green, blue, _ = cmap(norm(clipped))
                luminance = 0.299 * red + 0.587 * green + 0.114 * blue
                text_color = "white" if luminance < 0.55 else "#202020"
                ax.text(j, i, annotation(value), ha="center", va="center",
                        fontsize=5.4, color=text_color)
                if bool(row["nn_anti_damping"]):
                    ax.text(j + 0.30, i - 0.30, "×", ha="center", va="center",
                            fontsize=6.5, fontweight="bold", color="#241515")

        for spine in ax.spines.values():
            spine.set_visible(False)

    assert image is not None
    fig.text(0.075, 0.965, "CLSVOF NN cell-offset versus CLSVOF", ha="left", va="top",
             fontsize=7.2, fontweight="bold")
    legend_handles = [
        Line2D([0], [0], marker="x", color="#241515", linestyle="none",
               markersize=4.5, markeredgewidth=1.0, label="anti-damping"),
        Patch(facecolor="#EEEEEC", edgecolor="#A8A8A8", hatch="////",
              linewidth=0.55, label="failed pair"),
    ]
    fig.legend(handles=legend_handles, loc="upper right", bbox_to_anchor=(0.985, 0.982),
               ncol=2, handlelength=1.4, columnspacing=1.1, handletextpad=0.4,
               fontsize=6.2)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.79, bottom=0.285, wspace=0.10)
    fig.text(0.53, 0.205, r"Redistance iterations, $i_{\mathrm{max}}$", ha="center", va="center",
             fontsize=7.0)
    colorbar_axis = fig.add_axes((0.29, 0.075, 0.48, 0.034))
    colorbar = fig.colorbar(image, cax=colorbar_axis, orientation="horizontal",
                            ticks=(-100, -50, 0, 50, 100), extend="both")
    colorbar.ax.set_xticklabels(("≤−100", "−50", "0", "+50", "≥100"))
    colorbar.set_label(
        "CLSVOF NN cell-offset improvement over CLSVOF (%)", labelpad=2
    )
    save_bundle(fig, output_stem)
    plt.close(fig)


def main() -> int:
    repo = repository_root()
    default_result = repo / "dataset/oscillating_droplet"
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", type=Path, default=default_result)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result_root = args.result_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    rows = build_source_rows(result_root)
    plot_heatmap(rows, output / "oscillating_nn_offset_improvement_heatmap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
