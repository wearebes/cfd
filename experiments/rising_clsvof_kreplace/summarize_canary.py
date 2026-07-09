#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path


MOONMD_RELATIVE_PATH = "dataset/official_data/rising_bubble/sources/c1g3l4s.txt"
EXPECTED_HEADER = "t sb -1 xb vb dt perf.t perf.speed"


def read_out(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0] if lines else ""
    rows = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        try:
            values = [float(x) for x in fields[:6]]
        except ValueError:
            values = None
        rows.append((values, fields))
    return header, rows


def read_facet_segments(path: Path):
    """Basilisk output_facets format: blank-line-separated groups of
    points; each consecutive pair within a group is one facet segment."""
    segments = []
    current = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            for i in range(len(current) - 1):
                segments.append((current[i], current[i + 1]))
            current = []
            continue
        parts = stripped.split()
        current.append((float(parts[0]), float(parts[1])))
    for i in range(len(current) - 1):
        segments.append((current[i], current[i + 1]))
    return segments


def point_segment_distance(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-300:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def min_distance_to_segments(p, segments) -> float:
    return min(point_segment_distance(p, a, b) for a, b in segments)


def read_moonmd_points(path: Path):
    # dataset/rising.c gnuplot convention: 'c1g3l4s.txt' u 2:($1-0.5) is
    # overlaid against 'log' u 1:2, so a raw (col1, col2) row maps to the
    # same (x, y) space as our facet log via (col2, col1 - 0.5).
    points = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        raw0, raw1 = (float(v) for v in stripped.split()[:2])
        points.append((raw1, raw0 - 0.5))
    return points


def run_health(header: str, rows, log_path: Path) -> list[str]:
    issues = []
    if header != EXPECTED_HEADER:
        issues.append(f"unexpected header: {header!r}")
    if not rows:
        issues.append("no data rows")
        return issues
    for values, fields in rows:
        if values is None or any(math.isnan(v) or math.isinf(v) for v in values):
            issues.append(f"non-finite value in row: {' '.join(fields)}")
    last_values, last_fields = rows[-1]
    if last_values is None or last_values[0] < 2.99:
        issues.append(f"did not complete to t=3 (last t={last_fields[0]})")
    if not log_path.exists() or log_path.stat().st_size == 0:
        issues.append("log is empty or missing")
    return issues


def hysing_metrics(rows) -> dict | None:
    finite = [values for values, _ in rows if values is not None]
    if not finite:
        return None
    max_vb_row = max(finite, key=lambda r: r[4])
    final = finite[-1]
    return {
        "max_vb": max_vb_row[4],
        "t_at_max_vb": max_vb_row[0],
        "final_vb": final[4],
        "final_xb": final[3],
        "max_volume_drift": max(abs(r[1]) for r in finite),
    }


def shape_deviation(segments, moonmd_points) -> dict | None:
    if not segments or not moonmd_points:
        return None
    distances = [min_distance_to_segments(p, segments) for p in moonmd_points]
    return {"mean": sum(distances) / len(distances), "max": max(distances)}


def discover_modes(result_dir: Path) -> list[str]:
    modes = []
    for child in sorted(result_dir.iterdir()):
        if child.is_dir() and (child / "out").exists() and (child / "log").exists():
            modes.append(child.name)
    if "original" in modes:
        modes.remove("original")
        modes = ["original"] + modes
    return modes


def fmt(value) -> str:
    return "n/a" if value is None else f"{value:.6g}"


def build_summary(result_dir: Path, repo_root: Path) -> str:
    modes = discover_modes(result_dir)
    moonmd_points = read_moonmd_points(repo_root / MOONMD_RELATIVE_PATH)

    per_mode = {}
    for mode in modes:
        mode_dir = result_dir / mode
        header, rows = read_out(mode_dir / "out")
        per_mode[mode] = {
            "health": run_health(header, rows, mode_dir / "log"),
            "metrics": hysing_metrics(rows),
            "shape": shape_deviation(read_facet_segments(mode_dir / "log"), moonmd_points),
        }

    lines = [f"# Rising CLSVOF K Replacement Canary Summary ({result_dir.name})", ""]

    lines.append("## Run health")
    lines.append("")
    lines.append("| mode | status | issues |")
    lines.append("| --- | --- | --- |")
    for mode in modes:
        health = per_mode[mode]["health"]
        status = "OK" if not health else "FAIL"
        lines.append(f"| {mode} | {status} | {'; '.join(health)} |")
    lines.append("")

    lines.append("## Hysing benchmark quantities")
    lines.append("")
    lines.append(
        "| mode | max(vb) | t at max(vb) | final vb | final xb "
        "| max volume drift | shape mean dist | shape max dist |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for mode in modes:
        m = per_mode[mode]["metrics"] or {}
        s = per_mode[mode]["shape"] or {}
        lines.append(
            f"| {mode} | {fmt(m.get('max_vb'))} | {fmt(m.get('t_at_max_vb'))} "
            f"| {fmt(m.get('final_vb'))} | {fmt(m.get('final_xb'))} "
            f"| {fmt(m.get('max_volume_drift'))} | {fmt(s.get('mean'))} | {fmt(s.get('max'))} |"
        )
    lines.append("")

    lines.append("## Delta vs original")
    lines.append("")
    baseline = per_mode.get("original", {}).get("metrics")
    baseline_shape = per_mode.get("original", {}).get("shape")
    lines.append(
        "| mode | d max(vb) | d final vb | d final xb | d max volume drift "
        "| d shape mean | d shape max |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for mode in modes:
        if mode == "original":
            continue
        m = per_mode[mode]["metrics"]
        s = per_mode[mode]["shape"]
        if not m or not baseline:
            lines.append(f"| {mode} | n/a | n/a | n/a | n/a | n/a | n/a |")
            continue
        d_smean = (s["mean"] - baseline_shape["mean"]) if s and baseline_shape else None
        d_smax = (s["max"] - baseline_shape["max"]) if s and baseline_shape else None
        lines.append(
            f"| {mode} | {fmt(m['max_vb'] - baseline['max_vb'])} "
            f"| {fmt(m['final_vb'] - baseline['final_vb'])} "
            f"| {fmt(m['final_xb'] - baseline['final_xb'])} "
            f"| {fmt(m['max_volume_drift'] - baseline['max_volume_drift'])} "
            f"| {fmt(d_smean)} | {fmt(d_smax)} |"
        )
    lines.append("")

    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    print(build_summary(args.result_dir.resolve(), repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
