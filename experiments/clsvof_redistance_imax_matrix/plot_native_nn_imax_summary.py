#!/usr/bin/env python3
"""Compact native-versus-NN summary of the formal redistance imax matrix."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "work/.mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(__file__).resolve().parent / "work/.cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_formal_matrix import add_panel_label, apply_style, atomic_csv, number, read_csv, save_figure


HERE = Path(__file__).resolve().parent
WIDTH_IN = 180.0 / 25.4
METHOD_STYLE = {
    "clsvof_native": {"color": "#0F4D92", "marker": "o", "linestyle": "-", "label": "CLSVOF native"},
    "clsvof_nn": {"color": "#B64342", "marker": "s", "linestyle": "--", "label": "CLSVOF-NN"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = HERE / "results" / args.matrix_id
    audit = json.loads((root / "audit.json").read_text(encoding="utf-8"))
    if audit.get("passed") is not True or audit.get("state_counts") != {"completed": 96}:
        raise RuntimeError("summary plotting requires the passed 96-row strict audit")

    rows = read_csv(root / "metrics_wide.csv")
    figures = root / "figures"
    source = figures / "source_data"
    apply_style()
    fig, axes = plt.subplots(2, 4, figsize=(WIDTH_IN, 4.55), sharex=True, sharey="row")
    source_rows = []
    panel = 0
    for row_index, (benchmark, metric, ylabel) in enumerate(
        (
            ("capwave", "relative_rms", "Prosperetti relative RMS"),
            ("rising_case1", "velocity_reference_rmse", "MooNMD velocity RMSE"),
        )
    ):
        for column, n in enumerate((64, 128, 256, 512)):
            ax = axes[row_index, column]
            for method, style in METHOD_STYLE.items():
                selected = sorted(
                    (
                        row
                        for row in rows
                        if row["benchmark"] == benchmark
                        and row["method"] == method
                        and int(row["N"]) == n
                    ),
                    key=lambda row: int(row["imax"]),
                )
                ax.plot(
                    [int(row["imax"]) for row in selected],
                    [number(row, metric) for row in selected],
                    color=style["color"],
                    marker=style["marker"],
                    linestyle=style["linestyle"],
                    markerfacecolor="white" if method == "clsvof_nn" else style["color"],
                    markeredgewidth=1.0,
                    label=style["label"],
                )
                source_rows.extend(
                    {
                        "benchmark": benchmark,
                        "method": method,
                        "N": n,
                        "imax": int(row["imax"]),
                        "physical_metric": metric,
                        "physical_error": number(row, metric),
                    }
                    for row in selected
                )
            ax.axvline(3, color="#767676", linestyle=":", linewidth=1.0)
            ax.set_yscale("log")
            ax.set_xticks(range(6))
            ax.set_title(f"N={n}")
            ax.set_xlabel("imax")
            if column == 0:
                ax.set_ylabel(ylabel)
            add_panel_label(ax, chr(ord("a") + panel))
            panel += 1

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.015))
    fig.text(0.012, 0.72, "Capillary wave", rotation=90, ha="center", va="center", fontsize=8, fontweight="bold")
    fig.text(0.012, 0.28, "Rising bubble", rotation=90, ha="center", va="center", fontsize=8, fontweight="bold")
    fig.subplots_adjust(left=0.11, right=0.99, top=0.88, bottom=0.11, hspace=0.38, wspace=0.16)

    atomic_csv(
        source / "fig07_native_nn_imax_summary.csv",
        source_rows,
        ["benchmark", "method", "N", "imax", "physical_metric", "physical_error"],
    )
    outputs = save_figure(fig, figures / "fig07_native_nn_imax_summary")
    print(json.dumps({"outputs": [str(path) for path in outputs], "source_rows": len(source_rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
