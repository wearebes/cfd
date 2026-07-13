#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "work/.mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(__file__).resolve().parent / "work/.cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


# Mandatory editable-text settings from the selected Python figure backend.
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WIDTH_IN = 180.0 / 25.4
METHOD_COLORS = {"clsvof_native": "#0F4D92", "clsvof_nn": "#B64342"}
METHOD_LABELS = {"clsvof_native": "CLSVOF native", "clsvof_nn": "CLSVOF-NN"}
N_COLORS = {64: "#B4C0E4", 128: "#7884B4", 256: "#3775BA", 512: "#0F4D92"}
IMAX_COLORS = {0: "#767676", 2: "#42949E", 3: "#272727", 5: "#B64342"}
SELECTED_IMAX = (0, 2, 3, 5)


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 7.5,
            "axes.linewidth": 0.8,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "legend.frameon": False,
            "lines.linewidth": 1.2,
            "lines.markersize": 3.5,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
        }
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def number(row: dict[str, str], key: str) -> float:
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f"non-finite {key} in {row.get('row_id', row)}")
    return value


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def add_panel_label(ax: mpl.axes.Axes, label: str) -> None:
    ax.text(
        -0.14,
        1.04,
        label,
        transform=ax.transAxes,
        fontsize=8,
        fontweight="bold",
        ha="left",
        va="bottom",
    )


def save_figure(fig: mpl.figure.Figure, base: Path) -> list[Path]:
    base.parent.mkdir(parents=True, exist_ok=True)
    outputs = []
    for suffix, kwargs in (
        (".svg", {}),
        (".pdf", {}),
        (".png", {"dpi": 600}),
    ):
        path = base.with_suffix(suffix)
        fig.savefig(path, bbox_inches="tight", facecolor="white", **kwargs)
        outputs.append(path)
    plt.close(fig)
    return outputs


def gate(root: Path) -> None:
    audit_path = root / "audit.json"
    if not audit_path.is_file():
        raise RuntimeError("plotting blocked: audit.json is missing")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("passed") is not True or audit.get("state_counts") != {"completed": 96}:
        raise RuntimeError(
            f"plotting blocked: strict 96-row audit has not passed ({audit.get('state_counts')})"
        )


def figure_physical_tradeoff(
    rows: list[dict[str, str]], figures: Path, source: Path
) -> list[Path]:
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH_IN, 4.9), sharex=True)
    panel = iter("abcd")
    source_rows = []
    for column, method in enumerate(("clsvof_native", "clsvof_nn")):
        for row_index, benchmark in enumerate(("capwave", "rising_case1")):
            ax = axes[row_index, column]
            metric = "relative_rms" if benchmark == "capwave" else "velocity_reference_rmse"
            for n in (64, 128, 256, 512):
                selected = sorted(
                    [
                        row
                        for row in rows
                        if row["benchmark"] == benchmark
                        and row["method"] == method
                        and int(row["N"]) == n
                    ],
                    key=lambda row: int(row["imax"]),
                )
                x = [int(row["imax"]) for row in selected]
                y = [number(row, metric) for row in selected]
                ax.plot(x, y, marker="o", color=N_COLORS[n], label=f"N={n}")
                source_rows.extend(
                    {
                        "benchmark": benchmark,
                        "method": method,
                        "N": n,
                        "imax": int(item["imax"]),
                        "physical_metric": metric,
                        "physical_error": number(item, metric),
                    }
                    for item in selected
                )
            ax.axvline(3, color="#767676", linestyle="--", linewidth=0.9)
            ax.set_yscale("log")
            ax.set_xticks(range(6))
            ax.set_xlabel("redistance imax")
            ax.set_ylabel("Prosperetti relative RMS" if benchmark == "capwave" else "MooNMD velocity RMSE")
            ax.set_title(METHOD_LABELS[method])
            add_panel_label(ax, next(panel))
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.015))
    fig.subplots_adjust(top=0.90, hspace=0.36, wspace=0.33)
    atomic_csv(
        source / "fig01_physical_tradeoff.csv",
        source_rows,
        ["benchmark", "method", "N", "imax", "physical_metric", "physical_error"],
    )
    return save_figure(fig, figures / "fig01_physical_tradeoff")


def matrix_for(
    rows: list[dict[str, str]], benchmark: str, method: str, metric: str
) -> np.ndarray:
    lookup = {
        (int(row["N"]), int(row["imax"])): number(row, metric)
        for row in rows
        if row["benchmark"] == benchmark and row["method"] == method
    }
    return np.asarray([[lookup[(n, imax)] for imax in range(6)] for n in (64, 128, 256, 512)])


def figure_heatmaps(
    rows: list[dict[str, str]], benchmark: str, figures: Path, source: Path
) -> list[Path]:
    physical = "relative_rms" if benchmark == "capwave" else "velocity_reference_rmse"
    metrics = (
        (physical, "log10 physical error", "viridis"),
        ("post_b15_egrad_mean", "log10 mean Egrad (1.5D)", "magma_r"),
        ("post_b15_egrad_mean_p95", "log10 temporal p95 mean Egrad", "magma_r"),
        ("run_seconds", "runtime / matched imax=3", "coolwarm"),
    )
    fig, axes = plt.subplots(4, 2, figsize=(WIDTH_IN, 6.7), constrained_layout=True)
    source_rows = []
    label_index = 0
    for row_index, (metric, cbar_label, cmap) in enumerate(metrics):
        transformed = []
        for column, method in enumerate(("clsvof_native", "clsvof_nn")):
            raw = matrix_for(rows, benchmark, method, metric)
            values = raw / raw[:, [3]] if metric == "run_seconds" else np.log10(raw)
            transformed.append(values)
        vmin = min(value.min() for value in transformed)
        vmax = max(value.max() for value in transformed)
        if metric == "run_seconds":
            bound = max(abs(vmin - 1.0), abs(vmax - 1.0))
            vmin, vmax = 1.0 - bound, 1.0 + bound
        images = []
        for column, method in enumerate(("clsvof_native", "clsvof_nn")):
            ax = axes[row_index, column]
            image = ax.imshow(transformed[column], aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
            images.append(image)
            ax.set_xticks(range(6), range(6))
            ax.set_yticks(range(4), (64, 128, 256, 512))
            ax.set_xlabel("imax")
            ax.set_ylabel("source N")
            if row_index == 0:
                ax.set_title(METHOD_LABELS[method])
            add_panel_label(ax, chr(ord("a") + label_index))
            label_index += 1
            raw = matrix_for(rows, benchmark, method, metric)
            for ni, n in enumerate((64, 128, 256, 512)):
                for imax in range(6):
                    source_rows.append(
                        {
                            "benchmark": benchmark,
                            "method": method,
                            "N": n,
                            "imax": imax,
                            "metric": metric,
                            "raw_value": raw[ni, imax],
                            "plotted_value": transformed[column][ni, imax],
                        }
                    )
        cbar = fig.colorbar(images[-1], ax=list(axes[row_index, :]), shrink=0.83, pad=0.02)
        cbar.set_label(cbar_label)
    basename = "fig02_capwave_heatmaps" if benchmark == "capwave" else "fig03_rising_heatmaps"
    atomic_csv(
        source / f"{basename}.csv",
        source_rows,
        ["benchmark", "method", "N", "imax", "metric", "raw_value", "plotted_value"],
    )
    return save_figure(fig, figures / basename)


def figure_sdf_physics(
    rows: list[dict[str, str]], figures: Path, source: Path
) -> list[Path]:
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH_IN, 4.9))
    source_rows = []
    panel = iter("abcd")
    for row_index, benchmark in enumerate(("capwave", "rising_case1")):
        metric = "relative_rms" if benchmark == "capwave" else "velocity_reference_rmse"
        for column, method in enumerate(("clsvof_native", "clsvof_nn")):
            ax = axes[row_index, column]
            for imax in range(6):
                selected = [
                    row
                    for row in rows
                    if row["benchmark"] == benchmark
                    and row["method"] == method
                    and int(row["imax"]) == imax
                ]
                x = [number(row, "post_b15_egrad_mean") for row in selected]
                y = [number(row, metric) for row in selected]
                ax.scatter(x, y, label=f"imax={imax}", s=18, alpha=0.85)
                source_rows.extend(
                    {
                        "benchmark": benchmark,
                        "method": method,
                        "N": int(item["N"]),
                        "imax": imax,
                        "egrad_mean": number(item, "post_b15_egrad_mean"),
                        "physical_metric": metric,
                        "physical_error": number(item, metric),
                    }
                    for item in selected
                )
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlabel("mean Egrad (1.5D band)")
            ax.set_ylabel("Prosperetti relative RMS" if benchmark == "capwave" else "MooNMD velocity RMSE")
            ax.set_title(METHOD_LABELS[method])
            add_panel_label(ax, next(panel))
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=6, bbox_to_anchor=(0.5, 1.015))
    fig.subplots_adjust(top=0.90, hspace=0.36, wspace=0.33)
    atomic_csv(
        source / "fig04_sdf_physics.csv",
        source_rows,
        ["benchmark", "method", "N", "imax", "egrad_mean", "physical_metric", "physical_error"],
    )
    return save_figure(fig, figures / "fig04_sdf_physics")


def parse_prosperetti(path: Path) -> list[tuple[float, float]]:
    pattern = re.compile(r"\{\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*\}")
    return [
        (float(match.group(1)), float(match.group(2)))
        for match in pattern.finditer(path.read_text(encoding="utf-8"))
    ]


def read_hysing(path: Path) -> list[tuple[float, float, float]]:
    output = []
    for line in path.read_text(encoding="utf-8").splitlines():
        values = [float(value) for value in line.split()[:5]]
        if len(values) == 5:
            output.append((values[0], values[3], values[4]))
    return output


def figure_histories(
    root: Path, figures: Path, source: Path
) -> list[Path]:
    capwave = read_csv(root / "capwave_timeseries.csv")
    rising = read_csv(root / "rising_timeseries.csv")
    prosperetti = parse_prosperetti(ROOT / "basilisk/src/test/prosperetti.h")[:738]
    hysing = read_hysing(ROOT / "dataset/official_data/rising_bubble/sources/c1g3l4.txt")
    fig, axes = plt.subplots(3, 2, figsize=(WIDTH_IN, 6.2), sharex="row")
    source_rows = []
    for column, method in enumerate(("clsvof_native", "clsvof_nn")):
        ax = axes[0, column]
        ax.plot([x for x, _ in prosperetti], [y for _, y in prosperetti], color="#272727", linewidth=1.4, label="Prosperetti")
        for imax in SELECTED_IMAX:
            selected = [
                row for row in capwave
                if row["method"] == method and int(row["N"]) == 512 and int(row["imax"]) == imax
            ]
            ax.plot(
                [number(row, "tau") for row in selected],
                [number(row, "amplitude") for row in selected],
                color=IMAX_COLORS[imax],
                label=f"imax={imax}",
            )
            source_rows.extend({"panel": "capwave", **row} for row in selected)
        ax.set_ylabel("wave amplitude")
        ax.set_title(METHOD_LABELS[method])
        add_panel_label(ax, "a" if column == 0 else "b")

        ax = axes[1, column]
        ax.plot([x for x, _, _ in hysing], [v for _, _, v in hysing], color="#272727", linewidth=1.4, label="MooNMD")
        for imax in SELECTED_IMAX:
            selected = [
                row for row in rising
                if row["method"] == method and int(row["N"]) == 512 and int(row["imax"]) == imax
            ]
            ax.plot(
                [number(row, "time") for row in selected],
                [number(row, "velocity") for row in selected],
                color=IMAX_COLORS[imax],
                label=f"imax={imax}",
            )
            source_rows.extend({"panel": "rising_velocity", **row} for row in selected)
        ax.set_ylabel("rise velocity")
        add_panel_label(ax, "c" if column == 0 else "d")

        ax = axes[2, column]
        ax.axhline(0, color="#272727", linewidth=0.8)
        for imax in SELECTED_IMAX:
            selected = [
                row for row in rising
                if row["method"] == method and int(row["N"]) == 512 and int(row["imax"]) == imax
            ]
            ax.plot(
                [number(row, "time") for row in selected],
                [number(row, "volume_drift") for row in selected],
                color=IMAX_COLORS[imax],
                label=f"imax={imax}",
            )
            source_rows.extend({"panel": "rising_volume", **row} for row in selected)
        ax.set_xlabel("physical time")
        ax.set_ylabel("relative volume drift")
        add_panel_label(ax, "e" if column == 0 else "f")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, bbox_to_anchor=(0.5, 1.015))
    fig.subplots_adjust(top=0.91, hspace=0.28, wspace=0.30)
    fields = sorted({key for row in source_rows for key in row})
    atomic_csv(source / "fig05_n512_histories.csv", source_rows, fields)
    return save_figure(fig, figures / "fig05_n512_histories")


def facet_segments(path: Path) -> list[tuple[float, float, float, float]]:
    segments = []
    current: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("kappa_offset_provider_stats"):
            segments.extend(
                (current[index][0], current[index][1], current[index + 1][0], current[index + 1][1])
                for index in range(len(current) - 1)
            )
            current = []
            continue
        try:
            x, y = (float(value) for value in stripped.split()[:2])
            current.append((x, y))
        except (ValueError, IndexError):
            current = []
    return segments


def moonmd_shape(path: Path) -> list[tuple[float, float]]:
    output = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            first, second = (float(value) for value in line.split()[:2])
            transverse_offset = first - 0.5
            if transverse_offset >= -1e-12:
                output.append((second, max(0.0, transverse_offset)))
    return output


def figure_shapes(root: Path, figures: Path, source: Path) -> list[Path]:
    fig, axes = plt.subplots(2, 4, figsize=(WIDTH_IN, 3.7), sharex=True, sharey=True)
    reference = moonmd_shape(ROOT / "dataset/official_data/rising_bubble/sources/c1g3l4s.txt")
    source_rows = [
        {"method": "MooNMD", "imax": "reference", "segment": index, "x0": x, "y0": y, "x1": "", "y1": ""}
        for index, (x, y) in enumerate(reference)
    ]
    panel = 0
    for row_index, method in enumerate(("clsvof_native", "clsvof_nn")):
        for column, imax in enumerate(SELECTED_IMAX):
            ax = axes[row_index, column]
            log = root / "rising_case1" / "N0512" / f"imax{imax:02d}" / method / "log"
            segments = facet_segments(log)
            ax.plot([x for x, _ in reference], [y for _, y in reference], color="#767676", linestyle="--", linewidth=1.0)
            for index, (x0, y0, x1, y1) in enumerate(segments):
                ax.plot((x0, x1), (y0, y1), color=METHOD_COLORS[method], linewidth=0.9)
                source_rows.append(
                    {"method": method, "imax": imax, "segment": index, "x0": x0, "y0": y0, "x1": x1, "y1": y1}
                )
            ax.set_aspect("equal", adjustable="box")
            ax.set_title(f"imax={imax}")
            if column == 0:
                ax.set_ylabel(METHOD_LABELS[method])
            add_panel_label(ax, chr(ord("a") + panel))
            panel += 1
    fig.supxlabel("vertical coordinate")
    fig.supylabel("transverse offset")
    fig.subplots_adjust(hspace=0.32, wspace=0.18)
    atomic_csv(
        source / "fig06_rising_n512_shapes.csv",
        source_rows,
        ["method", "imax", "segment", "x0", "y0", "x1", "y1"],
    )
    return save_figure(fig, figures / "fig06_rising_n512_shapes")


def qa_manifest(outputs: Iterable[Path], root: Path) -> dict[str, Any]:
    records = []
    for path in sorted(outputs):
        record: dict[str, Any] = {
            "file": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
        }
        if path.suffix == ".svg":
            content = path.read_text(encoding="utf-8")
            record["editable_text_nodes"] = content.count("<text")
            record["editable_text_ok"] = record["editable_text_nodes"] > 0
        records.append(record)
    return {
        "schema_version": 1,
        "backend": "Python/matplotlib",
        "final_width_mm": 180,
        "audit_gate_passed": True,
        "outputs": records,
        "visual_review": "pending_manual_render_review",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = HERE / "results" / args.matrix_id
    gate(root)
    rows = read_csv(root / "metrics_wide.csv")
    if len(rows) != 96 or any(row["execution_state"] != "completed" for row in rows):
        raise RuntimeError("plotting blocked: metrics_wide.csv is not a 96-row completed matrix")
    figures = root / "figures"
    source = figures / "source_data"
    apply_style()
    outputs: list[Path] = []
    outputs.extend(figure_physical_tradeoff(rows, figures, source))
    outputs.extend(figure_heatmaps(rows, "capwave", figures, source))
    outputs.extend(figure_heatmaps(rows, "rising_case1", figures, source))
    outputs.extend(figure_sdf_physics(rows, figures, source))
    outputs.extend(figure_histories(root, figures, source))
    outputs.extend(figure_shapes(root, figures, source))
    manifest = qa_manifest(outputs, root)
    temporary = figures / "figure_qa_manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, figures / "figure_qa_manifest.json")
    print(json.dumps({"figures": len(outputs), "source_files": len(list(source.glob("*.csv"))) }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
