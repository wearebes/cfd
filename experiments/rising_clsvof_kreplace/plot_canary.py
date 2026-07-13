#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from summarize_canary import (
    MOONMD_RELATIVE_PATH,
    discover_modes,
    read_facet_segments,
    read_moonmd_points,
    read_out,
)


def plot_shape(result_dir: Path, repo_root: Path, modes: list[str], out_path: Path, case: str = "case1") -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    moonmd = read_moonmd_points(repo_root / MOONMD_RELATIVE_PATH[case])
    all_x = [p[0] for p in moonmd]
    all_y = [p[1] for p in moonmd]
    ax.plot(all_x, all_y, "k-", linewidth=2, label="MooNMD")
    for mode in modes:
        segments = read_facet_segments(result_dir / mode / "log")
        first = True
        for a, b in segments:
            ax.plot(
                [a[0], b[0]],
                [a[1], b[1]],
                linewidth=1,
                label=mode if first else None,
            )
            all_x.extend([a[0], b[0]])
            all_y.extend([a[1], b[1]])
            first = False
    if all_x and all_y:
        x_pad = 0.05 * (max(all_x) - min(all_x) + 1e-9)
        y_pad = 0.05 * (max(all_y) - min(all_y) + 1e-9)
        ax.set_xlim(min(all_x) - x_pad, max(all_x) + x_pad)
        ax.set_ylim(min(0.0, min(all_y) - y_pad), max(all_y) + y_pad)
    ax.set_xlabel("x (rise direction)")
    ax.set_ylabel("y")
    ax.set_title("Bubble shape at t = 3")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_timeseries(result_dir: Path, modes: list[str], out_path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    for mode in modes:
        _, rows = read_out(result_dir / mode / "out")
        finite = [r for r, _ in rows if r is not None]
        t = [r[0] for r in finite]
        vb = [r[4] for r in finite]
        drift = [r[1] for r in finite]
        ax1.plot(t, vb, label=mode, linewidth=1)
        ax2.plot(t, drift, label=mode, linewidth=1)
    ax1.set_xlabel("t")
    ax1.set_ylabel("rise velocity vb")
    ax1.set_title("Rise velocity vs time")
    ax1.legend(fontsize=7)
    ax2.set_xlabel("t")
    ax2.set_ylabel("(sb - sb0)/sb0")
    ax2.set_title("Volume drift vs time")
    ax2.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    parser.add_argument(
        "--case2", action="store_true", help="use the case-2 (sigma 1.96) MooNMD reference"
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    result_dir = args.result_dir.resolve()
    repo_root = Path(__file__).resolve().parents[2]
    modes = discover_modes(result_dir)
    case = "case2" if args.case2 else "case1"

    plot_shape(result_dir, repo_root, modes, result_dir / "shape_t3.png", case=case)
    plot_timeseries(result_dir, modes, result_dir / "timeseries.png")
    print(f"wrote {result_dir / 'shape_t3.png'}")
    print(f"wrote {result_dir / 'timeseries.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
