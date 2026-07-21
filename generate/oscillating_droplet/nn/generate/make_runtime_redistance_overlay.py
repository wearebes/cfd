#!/usr/bin/env python3
"""Generate a row-local CLSVOF header with runtime-selectable imax."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TARGET = "  redistance (d, imax = 3, phixxmin = HUGE);"
REPLACEMENT = "  redistance (d, imax = oscillation_redistance_imax, phixxmin = HUGE);"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(source: str) -> str:
    if source.count(TARGET) != 1:
        raise ValueError("expected exactly one stock CLSVOF redistance call")
    return source.replace(TARGET, REPLACEMENT, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args(argv)
    source = args.source.read_text(encoding="utf-8")
    output = build(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    args.provenance.write_text(json.dumps({
        "mode": "runtime_symbol",
        "runtime_symbol": "oscillation_redistance_imax",
        "allowed_values": [0, 1, 2, 3, 4, 5],
        "target": TARGET.strip(),
        "replacement": REPLACEMENT.strip(),
        "source_sha256": digest(source),
        "generated_sha256": digest(output),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
