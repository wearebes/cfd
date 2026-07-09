#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TARGET = "double ki = distance_curvature (point, d);"
REPLACEMENT = "double ki = rising_k_provider (point, d);"
INCLUDE_MARKER = "#endif // CURVATURE"
PROVIDER_INCLUDE = '#include "rising_k_provider.h"'


def build_overlay_text(source: str) -> str:
    if source.count(TARGET) != 1:
        raise ValueError("expected exactly one curvature assignment in integral.h")
    if INCLUDE_MARKER not in source:
        raise ValueError("expected integral.h to contain the CURVATURE endif marker")

    output = source.replace(TARGET, REPLACEMENT, 1)
    output = output.replace(
        INCLUDE_MARKER,
        f"{INCLUDE_MARKER}\n\n{PROVIDER_INCLUDE}",
        1,
    )
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source.read_text(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_overlay_text(source), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
