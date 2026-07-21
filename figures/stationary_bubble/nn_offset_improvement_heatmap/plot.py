#!/usr/bin/env python3
"""Generate the stationary-bubble NN-improvement heatmap."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _plot_common import draw_heatmaps, load_data, setup_style


def main() -> None:
    setup_style()
    draw_heatmaps(load_data(), HERE / "stationary_nn_offset_improvement_heatmap.png")


if __name__ == "__main__":
    main()
