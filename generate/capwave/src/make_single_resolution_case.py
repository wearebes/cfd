#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TARGET = "for (N = 16; N <= 128; N *= 2) {"


def build_case_text(source: str, resolution: int) -> str:
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    if source.count(TARGET) != 1:
        raise ValueError("expected exactly one stock capwave resolution loop")
    replacement = f"for (N = {resolution}; N <= {resolution}; N *= 2) {{"
    return source.replace(TARGET, replacement, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resolution", type=int, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_case_text(args.source.read_text(encoding="utf-8"), args.resolution),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
