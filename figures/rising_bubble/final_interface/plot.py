#!/usr/bin/env python3
"""Plot the final N512 interfaces against the Hysing reference."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _plot_common import SOURCE_DIR, draw_interfaces, setup_style


def main() -> None:
    setup_style()
    source = pd.read_csv(SOURCE_DIR / "interfaces_N512_imax0_vs3.csv")
    draw_interfaces(source, HERE / "rising_final_interface_N512.png", resolution=512)


if __name__ == "__main__":
    main()
