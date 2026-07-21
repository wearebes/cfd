#!/usr/bin/env python3
"""Plot the four required rising-bubble histories at N512."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _plot_common import draw_time_histories, load_time_sources, setup_style


def main() -> None:
    setup_style()
    dynamics, circularity = load_time_sources(512)
    draw_time_histories(
        dynamics, circularity, HERE / "rising_metrics_time_history_N512.png"
    )


if __name__ == "__main__":
    main()
