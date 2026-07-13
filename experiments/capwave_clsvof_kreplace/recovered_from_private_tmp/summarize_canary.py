#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path


def read_log(path: Path) -> list[tuple[float, float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a, b = line.split()[:2]
        rows.append((float(a), float(b)))
    return rows


def read_wave(path: Path) -> list[tuple[float, float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a, b = line.split()[:2]
        rows.append((float(a), float(b)))
    return rows


def rms_delta(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    if len(a) != len(b):
        raise ValueError(f"wave length mismatch: {len(a)} != {len(b)}")
    if not a:
        raise ValueError("empty wave file")
    se = 0.0
    for (ta, ya), (tb, yb) in zip(a, b):
        if abs(ta - tb) > 1e-12:
            raise ValueError(f"time mismatch: {ta} != {tb}")
        se += (ya - yb)**2
    return math.sqrt(se/len(a))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("dataset/official_data/capwave-clsvof"),
    )
    args = parser.parse_args()

    matched = [
        (64, "nn_baseline_64_hgradient"),
        (128, "nn_baseline_128_hgradient"),
        (256, "nn_baseline_256_hgradient"),
        (512, "nn_baseline_512_hgradient"),
    ]

    print("# capwave clsvof matched-resolution k replacement canary")
    print("resolution,mode,N_over_L0,relative_rms_error")
    for resolution, nn_mode in matched:
        baseline_rows = {int(round(n_over_l0 * 2.0)): err for n_over_l0, err in read_log(args.baseline_dir / "log")}
        if resolution not in baseline_rows:
            raise ValueError(f"baseline log missing resolution {resolution}")
        print(f"{resolution},dataset_clsvof,{resolution/2:.17g},{baseline_rows[resolution]:.17g}")

        mode_dir = args.result_dir / nn_mode
        rows = read_log(mode_dir / "log")
        if len(rows) != 1:
            raise ValueError(f"expected one log row for {nn_mode}, got {len(rows)}")
        n_over_l0, err = rows[0]
        print(f"{resolution},{mode_dir.name},{n_over_l0:.17g},{err:.17g}")

    print("")
    print("resolution,mode,wave_file,rms_delta_vs_dataset_clsvof")
    for resolution, nn_mode in matched:
        mode_dir = args.result_dir / nn_mode
        delta = rms_delta(
            read_wave(args.baseline_dir / f"wave-{resolution}"),
            read_wave(mode_dir / f"wave-{resolution}"),
        )
        print(f"{resolution},{nn_mode},wave-{resolution},{delta:.17g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
