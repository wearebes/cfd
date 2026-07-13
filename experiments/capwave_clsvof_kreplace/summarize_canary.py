#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path


PROVIDER_STATS_RE = re.compile(
    r"capwave_k_provider_stats\s+evaluations=(?P<evaluations>\d+)\s+clamp_hits=(?P<clamp_hits>\d+)"
)


def parse_provider_stats(log_text: str) -> dict[str, int] | None:
    matches = list(PROVIDER_STATS_RE.finditer(log_text))
    if not matches:
        return None
    match = matches[-1]
    return {
        "evaluations": int(match.group("evaluations")),
        "clamp_hits": int(match.group("clamp_hits")),
    }


def _read_two_float_rows(path: Path, *, skip_prefix: str) -> list[tuple[float, float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(skip_prefix):
            continue
        a, b = stripped.split()[:2]
        rows.append((float(a), float(b)))
    return rows


def read_log(path: Path) -> list[tuple[float, float]]:
    return _read_two_float_rows(path, skip_prefix="capwave_k_provider_stats ")


def read_wave(path: Path) -> list[tuple[float, float]]:
    return _read_two_float_rows(path, skip_prefix="capwave_k_provider_stats ")


def rms_delta(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    if len(a) != len(b):
        raise ValueError(f"wave length mismatch: {len(a)} != {len(b)}")
    if not a:
        raise ValueError("empty wave file")
    se = 0.0
    for (ta, ya), (tb, yb) in zip(a, b, strict=True):
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
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="emit missing rows instead of failing when selected modes were not run",
    )
    args = parser.parse_args()

    matched = [
        (64, "nn_baseline_64_hgradient"),
        (128, "nn_baseline_128_hgradient"),
        (256, "nn_baseline_256_hgradient"),
        (512, "nn_baseline_512_hgradient"),
    ]

    print("# capwave clsvof matched-resolution k replacement canary")
    print("resolution,mode,N_over_L0,relative_rms_error,provider_evals,clamp_hits")
    for resolution, nn_mode in matched:
        baseline_rows = {int(round(n_over_l0 * 2.0)): err for n_over_l0, err in read_log(args.baseline_dir / "log")}
        if resolution not in baseline_rows:
            raise ValueError(f"baseline log missing resolution {resolution}")
        print(f"{resolution},dataset_clsvof,{resolution/2:.17g},{baseline_rows[resolution]:.17g},n/a,n/a")

        mode_dir = args.result_dir / nn_mode
        if not mode_dir.exists():
            if args.allow_missing:
                print(f"{resolution},{nn_mode},n/a,missing,n/a,n/a")
                continue
            raise FileNotFoundError(mode_dir)
        rows = read_log(mode_dir / "log")
        if len(rows) != 1:
            raise ValueError(f"expected one log row for {nn_mode}, got {len(rows)}")
        stats = parse_provider_stats((mode_dir / "log").read_text(encoding="utf-8")) or {}
        n_over_l0, err = rows[0]
        print(
            f"{resolution},{mode_dir.name},{n_over_l0:.17g},{err:.17g},"
            f"{stats.get('evaluations', 'n/a')},{stats.get('clamp_hits', 'n/a')}"
        )

    print("")
    print("resolution,mode,wave_file,rms_delta_vs_dataset_clsvof")
    for resolution, nn_mode in matched:
        mode_dir = args.result_dir / nn_mode
        if not mode_dir.exists():
            if args.allow_missing:
                print(f"{resolution},{nn_mode},wave-{resolution},missing")
                continue
            raise FileNotFoundError(mode_dir)
        delta = rms_delta(
            read_wave(args.baseline_dir / f"wave-{resolution}"),
            read_wave(mode_dir / f"wave-{resolution}"),
        )
        print(f"{resolution},{nn_mode},wave-{resolution},{delta:.17g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
