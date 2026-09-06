#!/usr/bin/env python3
"""Plot formal Capwave E2 grid convergence."""

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
from matplotlib.ticker import FixedLocator, LogFormatterMathtext, LogLocator, NullFormatter


HERE = Path(__file__).resolve().parent
FIGURES_ROOT = HERE.parents[1]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (  # noqa: E402
    MATH_TEXT_PT,
    apply_cfd_style,
    canonical_method_label,
    figure_size,
    save_manuscript_figure,
    style_discrete_series,
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
RESOLUTIONS = (32, 64, 128, 256, 512)
METHODS = ("VOF-HF", "CLSVOF", "NN")
DATA_METHOD = {
    "VOF-HF": "VOF-HF",
    "CLSVOF": "CLSVOF-native-C2",
    "NN": "Cell-NN-C2",
}
MARKER_SIZE = {"VOF-HF": 5.0, "CLSVOF": 6.0, "NN": 4.5}
PLOT_ZORDER = {"VOF-HF": 3, "CLSVOF": 3, "NN": 4}
EXPECTED_E2_RANGE = (5e-4, 5e-2)
PLOT_Y_LIMITS = (3e-4, 1.4e-1)
OUTPUT_SUFFIX = nn_precision_output_suffix()
NN_INFERENCE_PRECISION = nn_inference_precision()
OUTPUT_STEM = HERE / f"capwave_e2_grid_convergence{OUTPUT_SUFFIX}"
SOURCE_DATA_PATH = HERE / f"source_data{OUTPUT_SUFFIX}.csv"


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


def load_e2(
    root: Path, summary: pd.DataFrame, resolution: int, method: str
) -> tuple[float, np.ndarray, np.ndarray]:
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
    reference = series["reference_amplitude"].to_numpy(dtype=float)
    residual = series["amplitude"].to_numpy(dtype=float) - reference
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
    return e2, tau, reference


def setup_style() -> None:
    apply_cfd_style()


def main() -> None:
    root = repository_root()
    summary = None
    source_rows: list[dict[str, object]] = []
    reference_tau: np.ndarray | None = None
    reference_amplitude: np.ndarray | None = None

    for resolution in RESOLUTIONS:
        for method in METHODS:
            e2, tau, reference = load_e2(root, summary, resolution, method)
            if reference_tau is None:
                reference_tau = tau
                reference_amplitude = reference
            elif not np.array_equal(reference_tau, tau) or not np.array_equal(
                reference_amplitude, reference
            ):
                raise ValueError(
                    f"time/reference mismatch at N={resolution}, method={method}"
                )
            source_rows.append(
                {
                    "grid_resolution": resolution,
                    "N_lambda": resolution // 2,
                    "method": method,
                    "inference_precision": (
                        NN_INFERENCE_PRECISION if method == "NN" else ""
                    ),
                    "imax": str(DEFAULT_IMAX) if method == "CLSVOF" else "",
                    "steps": str(DEFAULT_IMAX) if method == "NN" else "",
                    "E2": e2,
                }
            )

    source = pd.DataFrame(source_rows)
    if len(source) != 15:
        raise ValueError(f"expected 15 source-data rows, got {len(source)}")
    if (
        source["E2"].min() < EXPECTED_E2_RANGE[0]
        or source["E2"].max() > EXPECTED_E2_RANGE[1]
    ):
        raise ValueError("formal E2 data fall outside the expected convergence range")


    setup_style()
    fig, ax = plt.subplots(figsize=figure_size("single", 67.0))
    fig.subplots_adjust(left=0.205, right=0.960, bottom=0.19, top=0.94)
    for method in METHODS:
        selected = source.loc[source["method"].eq(method)].sort_values("N_lambda")
        ax.plot(
            selected["N_lambda"],
            selected["E2"],
            label=canonical_method_label(method),
            zorder=PLOT_ZORDER[method],
            **style_discrete_series(method, markersize=MARKER_SIZE[method]),
        )

    slope_one_x = np.array([18.0, 256.0])
    slope_one_y = 0.03 * (64.0 / slope_one_x)
    slope_two_x = np.array([16.0, 256.0])
    slope_two_y = 0.024 * np.square(32.0 / slope_two_x)
    ax.plot(slope_one_x, slope_one_y, color="#777777", lw=0.8, ls="--", zorder=1)
    ax.plot(slope_two_x, slope_two_y, color="#777777", lw=0.8, ls=":", zorder=1)
    ax.text(
        89,
        0.021,
        r"$O(N_\lambda^{-1})$",
        color="#666666",
        fontsize=MATH_TEXT_PT,
        rotation=-18,
        ha="left",
        va="bottom",
    )
    ax.text(
        22,
        0.044,
        r"$O(N_\lambda^{-2})$",
        color="#666666",
        fontsize=MATH_TEXT_PT,
        rotation=-31,
        ha="left",
        va="top",
    )

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.tick_params(axis="y", labelsize=MATH_TEXT_PT)
    ax.set_xlim(14, 290)
    ax.set_ylim(*PLOT_Y_LIMITS)

    major_x = np.array([16.0, 32.0, 64.0, 128.0, 256.0])
    minor_x = np.sqrt(major_x[:-1] * major_x[1:])
    ax.xaxis.set_major_locator(FixedLocator(major_x))
    ax.set_xticklabels(["16", "32", "64", "128", "256"])
    ax.xaxis.set_minor_locator(FixedLocator(minor_x))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_major_locator(LogLocator(base=10.0, subs=(1.0,)))
    ax.yaxis.set_major_formatter(LogFormatterMathtext(base=10.0))
    ax.yaxis.set_minor_locator(LogLocator(base=10.0, subs=(2.0, 5.0)))
    ax.yaxis.set_minor_formatter(NullFormatter())

    ax.set_xlabel(r"$N_\lambda$")
    ax.set_ylabel(r"$E_2$")
    ax.legend(loc="lower left", handlelength=2.4)
    paths = save_manuscript_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
