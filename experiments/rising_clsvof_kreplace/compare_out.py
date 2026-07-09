#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path


IGNORED_FIELDS_1INDEXED = (7, 8)  # perf.t, perf.speed: wall-clock, never equal across runs


def _fields_equal(a: str, b: str, tol: float | None) -> bool:
    if a == b:
        return True
    if tol is None:
        return False
    try:
        return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tol)
    except ValueError:
        return False


def _compare_data_line(line_no: int, line_a: str, line_b: str, tol: float | None) -> list[str]:
    fields_a = line_a.split()
    fields_b = line_b.split()
    if len(fields_a) != len(fields_b):
        return [
            f"line {line_no}: field count mismatch "
            f"({len(fields_a)} vs {len(fields_b)})"
        ]

    issues = []
    for idx, (fa, fb) in enumerate(zip(fields_a, fields_b), start=1):
        if idx in IGNORED_FIELDS_1INDEXED:
            continue
        if not _fields_equal(fa, fb, tol):
            issues.append(f"line {line_no}: field {idx} differs: {fa!r} != {fb!r}")
    return issues


def compare_out(text_a: str, text_b: str, tol: float | None = None) -> list[str]:
    """Compare two rising-clsvof `out` contents.

    Ignores 1-indexed fields 7/8 (perf.t, perf.speed) on data rows and any
    line starting with '#' (the trailing Multigrid summary, which also
    embeds wall-clock CPU/real/throughput numbers). The first line is the
    header and must match exactly. Returns a list of human-readable
    mismatch descriptions; empty means the files are equivalent.
    """
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    if not lines_a or not lines_b:
        return ["one or both inputs are empty"]

    issues: list[str] = []
    if lines_a[0] != lines_b[0]:
        issues.append(f"header differs: {lines_a[0]!r} != {lines_b[0]!r}")

    if len(lines_a) != len(lines_b):
        issues.append(f"line count differs: {len(lines_a)} vs {len(lines_b)}")
        return issues

    for line_no, (line_a, line_b) in enumerate(zip(lines_a[1:], lines_b[1:]), start=2):
        stripped_a = line_a.strip()
        stripped_b = line_b.strip()
        if not stripped_a and not stripped_b:
            continue
        if stripped_a.startswith("#") and stripped_b.startswith("#"):
            continue
        if not stripped_a or not stripped_b:
            issues.append(f"line {line_no}: blank/comment in one file only")
            continue
        issues.extend(_compare_data_line(line_no, line_a, line_b, tol))

    return issues


def compare_files(path_a: Path, path_b: Path, tol: float | None = None) -> list[str]:
    text_a = path_a.read_text(encoding="utf-8")
    text_b = path_b.read_text(encoding="utf-8")
    return compare_out(text_a, text_b, tol=tol)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument(
        "--tol",
        type=float,
        default=None,
        help="absolute tolerance for numeric field comparison "
        "(soft cross-toolchain check only; never used for the equivalence gate)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    issues = compare_files(args.a, args.b, tol=args.tol)
    if issues:
        print(f"MISMATCH: {args.a} vs {args.b}")
        for issue in issues:
            print(f"  {issue}")
        return 1
    print(f"MATCH: {args.a} vs {args.b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
