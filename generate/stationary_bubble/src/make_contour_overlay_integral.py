#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TARGET = "double ki = distance_curvature (point, d);"
REPLACEMENT = "double ki = stationary_contour_curvature (point, d);"
MARKER = "#endif // CURVATURE"
INCLUDE = '#include "stationary_contour_curvature.h"'


def build_overlay_text(source: str) -> str:
    if source.count(TARGET) != 1:
        raise ValueError("expected exactly one active ki assignment")
    if MARKER not in source:
        raise ValueError("expected integral.h to contain the CURVATURE marker")
    result = source.replace(TARGET, REPLACEMENT, 1)
    return result.replace(MARKER, f"{MARKER}\n\n{INCLUDE}", 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_overlay_text(args.source.read_text()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
