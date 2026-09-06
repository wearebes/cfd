#!/usr/bin/env python3
"""Plot representative Capwave amplitude histories from formal result rows."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
_CACHE_ROOT = Path(tempfile.gettempdir()) / "cfd-capwave-figures"
(_CACHE_ROOT / "matplotlib").mkdir(parents=True, exist_ok=True)
(_CACHE_ROOT / "fontconfig").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_CACHE_ROOT / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(_CACHE_ROOT / "fontconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
FIGURES_ROOT = HERE.parents[1]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (  # noqa: E402
    PANEL_LABEL_STYLE,
    apply_cfd_style,
    canonical_method_label,
    figure_size,
    save_manuscript_figure,
    style_time_series,
)
from data_paths import (  # noqa: E402
    canonical_run_dir,
    data_root,
    nn_inference_precision,
    nn_precision_output_suffix,
    repository_root as find_repository_root,
)

A0 = 0.01
SAMPLES = 738
TAU_FINAL = 24.9753
DEFAULT_IMAX = 3
ALL_RESOLUTIONS = (32, 64, 128, 256, 512)
SINGLE_GRID_VALUE = os.environ.get("CAPWAVE_RESOLUTION")
SINGLE_GRID_RESOLUTION = (
    int(SINGLE_GRID_VALUE) if SINGLE_GRID_VALUE is not None else None
)
if SINGLE_GRID_RESOLUTION is not None and SINGLE_GRID_RESOLUTION not in ALL_RESOLUTIONS:
    raise ValueError(f"unsupported Capwave resolution: {SINGLE_GRID_RESOLUTION}")
PANELS = (
    (("a", SINGLE_GRID_RESOLUTION),)
    if SINGLE_GRID_RESOLUTION is not None
    else (("a", 32), ("b", 128), ("c", 512))
)
METHOD_ORDER = ("Prosperetti", "VOF-HF", "CLSVOF", "NN")
NUMERICAL_LINE_ZORDER = 2
REFERENCE_ZORDER = 3
NUMERICAL_MARKER_ZORDER = 4
DATA_METHOD = {
    "VOF-HF": "VOF-HF",
    "CLSVOF": "CLSVOF-native-C2",
    "NN": "Cell-NN-C2",
}
MARKER_COUNT = {"VOF-HF": 8, "CLSVOF": 10, "NN": 12}
OUTPUT_SUFFIX = nn_precision_output_suffix()
NN_INFERENCE_PRECISION = nn_inference_precision()
if SINGLE_GRID_RESOLUTION is None:
    OUTPUT_STEM = HERE / f"capwave_amplitude_histories{OUTPUT_SUFFIX}"
    SOURCE_DATA_PATH = HERE / f"source_data{OUTPUT_SUFFIX}.csv"
else:
    SINGLE_GRID_DIR = HERE / f"single_grid_crossing_c2{OUTPUT_SUFFIX}"
    OUTPUT_STEM = (
        SINGLE_GRID_DIR
        / f"capwave_amplitude_time_history_N{SINGLE_GRID_RESOLUTION:04d}"
    )
    SOURCE_DATA_PATH = (
        SINGLE_GRID_DIR / f"source_data_N{SINGLE_GRID_RESOLUTION:04d}.csv"
    )


def repository_root() -> Path:
    return find_repository_root(HERE)


def run_directory(root: Path, resolution: int, method: str) -> Path:
    return canonical_run_dir(
        "capwave",
        DATA_METHOD[method],
        resolution,
        grid="uniform",
        imax=DEFAULT_IMAX if method == "CLSVOF" else None,
        steps=DEFAULT_IMAX if method == "NN" else None,
        repo_root=root,
    )


def load_run(
    root: Path, summary: pd.DataFrame, resolution: int, method: str
) -> tuple[pd.DataFrame, float]:
    directory = run_directory(root, resolution, method)
    series_path = directory / "timeseries.csv"
    manifest_path = directory / "manifest.json"
    if not series_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(f"missing formal artifacts under {directory}")

    series = pd.read_csv(series_path)
    required = {"tau", "amplitude", "reference_amplitude", "amplitude_error"}
    missing = required - set(series.columns)
    if missing:
        raise ValueError(f"missing timeseries columns in {series_path}: {sorted(missing)}")
    series = series[["tau", "amplitude", "reference_amplitude", "amplitude_error"]]
    values = series.to_numpy(dtype=float)
    if len(series) != SAMPLES or not np.isfinite(values).all():
        raise ValueError(f"invalid sample count or non-finite values in {series_path}")
    tau = series["tau"].to_numpy(dtype=float)
    if np.any(np.diff(tau) <= 0.0):
        raise ValueError(f"time is not strictly increasing in {series_path}")
    if not np.isclose(tau[0], 0.0, rtol=0.0, atol=1e-12) or not np.isclose(
        tau[-1], TAU_FINAL, rtol=0.0, atol=1e-12
    ):
        raise ValueError(f"unexpected Capwave time horizon in {series_path}")
    residual = series["amplitude"].to_numpy(dtype=float) - series[
        "reference_amplitude"
    ].to_numpy(dtype=float)
    if not np.allclose(
        residual,
        series["amplitude_error"].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-14,
    ):
        raise ValueError(f"amplitude_error is inconsistent in {series_path}")

    e2 = float(np.sqrt(np.mean(np.square(residual))) / A0)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed" or manifest.get("analysis_ready") is not True:
        raise ValueError(f"run is not completed and analysis-ready: {manifest_path}")
    metrics = {
        str(item["metric"]): float(item["value"])
        for item in manifest["analysis"]["metrics"]
        if item["metric"]
        in {"relative_rms_error", "relative_rms_error_recomputed"}
    }
    if set(metrics) != {"relative_rms_error", "relative_rms_error_recomputed"}:
        raise ValueError(f"missing RMS metrics in {manifest_path}")
    if abs(e2 - metrics["relative_rms_error_recomputed"]) > 1e-12:
        raise ValueError(f"recomputed E2 mismatch in {manifest_path}")
    if (
        abs(metrics["relative_rms_error"] - metrics["relative_rms_error_recomputed"])
        > 5e-7
    ):
        raise ValueError(f"official/recomputed E2 mismatch in {manifest_path}")
    return series, e2


def setup_style() -> None:
    apply_cfd_style()


def main() -> None:
    root = repository_root()
    summary = None
    panel_data: dict[int, dict[str, pd.DataFrame]] = {}
    source_rows: list[dict[str, object]] = []

    for panel, resolution in PANELS:
        runs: dict[str, pd.DataFrame] = {}
        for method in ("VOF-HF", "CLSVOF", "NN"):
            runs[method], _ = load_run(root, summary, resolution, method)
        anchor = runs["VOF-HF"]
        for method in ("CLSVOF", "NN"):
            if not np.array_equal(anchor["tau"].to_numpy(), runs[method]["tau"].to_numpy()):
                raise ValueError(f"time-grid mismatch at N={resolution}, method={method}")
            if not np.array_equal(
                anchor["reference_amplitude"].to_numpy(),
                runs[method]["reference_amplitude"].to_numpy(),
            ):
                raise ValueError(
                    f"Prosperetti reference mismatch at N={resolution}, method={method}"
                )
        runs["Prosperetti"] = pd.DataFrame(
            {
                "tau": anchor["tau"],
                "amplitude": anchor["reference_amplitude"],
            }
        )
        panel_data[resolution] = runs
        for method in METHOD_ORDER:
            series = runs[method]
            imax = str(DEFAULT_IMAX) if method == "CLSVOF" else ""
            steps = str(DEFAULT_IMAX) if method == "NN" else ""
            for tau, amplitude in zip(
                series["tau"].to_numpy(dtype=float),
                series["amplitude"].to_numpy(dtype=float),
                strict=True,
            ):
                source_rows.append(
                    {
                        "panel": panel,
                        "grid_resolution": resolution,
                        "N_lambda": resolution // 2,
                        "method": method,
                        "inference_precision": (
                            NN_INFERENCE_PRECISION if method == "NN" else ""
                        ),
                        "imax": imax,
                        "steps": steps,
                        "tau": tau,
                        "amplitude": amplitude,
                        "amplitude_over_A0": amplitude / A0,
                    }
                )

    source = pd.DataFrame(source_rows)
    expected_rows = len(PANELS) * len(METHOD_ORDER) * SAMPLES
    if len(source) != expected_rows:
        raise ValueError(
            f"expected {expected_rows} source-data rows, got {len(source)}"
        )
    SOURCE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)


    setup_style()
    is_single_grid = SINGLE_GRID_RESOLUTION is not None
    fig, axes_grid = plt.subplots(
        1,
        len(PANELS),
        figsize=figure_size("single" if is_single_grid else "double", 72.0 if is_single_grid else 65.0),
        sharey=True,
        squeeze=False,
    )
    axes = axes_grid[0]
    if is_single_grid:
        fig.subplots_adjust(left=0.205, right=0.965, bottom=0.19, top=0.68)
    else:
        fig.subplots_adjust(left=0.080, right=0.975, bottom=0.20, top=0.75, wspace=0.20)
    for ax, (panel, resolution) in zip(axes, PANELS, strict=True):
        for method in METHOD_ORDER:
            series = panel_data[resolution][method]
            display_method = (
                "Reference" if method == "Prosperetti" else canonical_method_label(method)
            )
            ax.plot(
                series["tau"],
                series["amplitude"] / A0,
                label=("Prosperetti" if method == "Prosperetti" else display_method),
                zorder=(
                    REFERENCE_ZORDER
                    if method == "Prosperetti"
                    else NUMERICAL_LINE_ZORDER
                ),
                **style_time_series(
                    display_method,
                    len(series),
                    marker_count=MARKER_COUNT.get(method, 10),
                ),
            )
        for method in METHOD_ORDER[1:]:
            series = panel_data[resolution][method]
            marker_style = style_time_series(
                canonical_method_label(method),
                len(series),
                marker_count=MARKER_COUNT[method],
                linestyle="none",
            )
            ax.plot(
                series["tau"],
                series["amplitude"] / A0,
                label="_nolegend_",
                zorder=NUMERICAL_MARKER_ZORDER,
                **marker_style,
            )
        ax.set_xlim(0.0, 25.0)
        ax.set_ylim(0.0, 1.05)
        ax.set_xticks([0, 5, 10, 15, 20, 25])
        ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xlabel(r"$\tau$")
        ax.set_title(rf"$N_\lambda={resolution // 2}$", pad=4)
        if not is_single_grid:
            ax.text(s=f"({panel})", transform=ax.transAxes, **PANEL_LABEL_STYLE)
    axes[0].set_ylabel(r"$\eta^{\max}/A_0$")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.95 if not is_single_grid else 0.975),
        ncol=4 if not is_single_grid else 2,
        handlelength=2.8,
        columnspacing=1.4,
    )
    paths = save_manuscript_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
