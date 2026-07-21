#!/usr/bin/env python3
"""Generate the stationary-bubble CLSVOF imax sweep."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _plot_common import draw_clsvof_imax_sweep, load_data, setup_style


def main() -> None:
    setup_style()
    draw_clsvof_imax_sweep(load_data(), HERE / "stationary_clsvof_imax_sweep.png")


if __name__ == "__main__":
    main()
