#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

TARGET = "double ki = distance_curvature (point, d);"
REPLACEMENT = "double ki = kappa_offset_provider (point, d);"
MARKER_LINE = "#endif // CURVATURE\n"


def build_overlay_text(source: str) -> str:
    if source.count(TARGET) != 1:
        raise ValueError("expected exactly one active distance_curvature assignment")
    if source.count(MARKER_LINE) != 1:
        raise ValueError("expected exactly one CURVATURE closing marker")
    return source.replace(TARGET, REPLACEMENT, 1).replace(
        MARKER_LINE, '#endif // CURVATURE\n\n#include "clsvof_nn_cell_curvature.h"\n', 1
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_overlay_text(args.source.read_text(encoding="utf-8")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
