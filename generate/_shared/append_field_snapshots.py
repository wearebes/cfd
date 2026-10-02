#!/usr/bin/env python3
"""Append the shared observational field-snapshot events to a generated host."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional


SETTINGS = {
    "capwave": {
        "middle": "1.1213105628",
        "final": "2.2426211256",
        "benchmark": "(11.1366559937*(value))",
        "phase": "f[]",
    },
    "rising_bubble": {
        "middle": "1.5",
        "final": "3.",
        "benchmark": "(value)",
        "phase": "(1. - f[])",
    },
    "stationary_bubble": {
        "middle": "TAU_ONE_TIME",
        "final": "TMAX",
        "benchmark": "(MU*(value)/sq(DIAMETER))",
        "phase": "(1. - f[])",
        "vof_phase": "c[]",
    },
    "oscillating_droplet": {
        "middle": "0.5",
        "final": "1.",
        "benchmark": "(value)",
        "phase": "f[]",
    },
}


def append_overlay(
    source: str, case: str, clsvof: bool, middle: Optional[str] = None
) -> str:
    if "CFD_FIELD_SNAPSHOTS_H" in source or 'include "field_snapshots.h"' in source:
        raise ValueError("field snapshot overlay is already present")
    setting = SETTINGS[case]
    middle_time = middle or setting["middle"]
    block = f'''\n\n/* Repository-added observational field snapshots. */
#define CFD_SNAPSHOT_MIDDLE_SOLVER_TIME {middle_time}
#define CFD_SNAPSHOT_FINAL_SOLVER_TIME {setting["final"]}
#define CFD_SNAPSHOT_BENCHMARK_TIME(value) {setting["benchmark"]}
#define CFD_SNAPSHOT_PHASE_VALUE {setting["phase"] if clsvof else setting.get("vof_phase", setting["phase"])}
#define CFD_SNAPSHOT_CLSVOF {1 if clsvof else 0}
#include "field_snapshots.h"
'''
    return source.rstrip() + block


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--case", choices=tuple(SETTINGS), required=True)
    parser.add_argument("--clsvof", action="store_true")
    parser.add_argument("--middle")
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    args.source.write_text(
        append_overlay(source, args.case, args.clsvof, middle=args.middle),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
