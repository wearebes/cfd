#!/usr/bin/env python3
"""Generate the stationary-bubble imax=0,1,3 and VOF-HF comparison."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _plot_common import (
    build_vof_hf_source_data,
    draw_imax0_1_3,
    load_data,
    setup_style,
)


def main() -> None:
    setup_style()
    vof_hf = build_vof_hf_source_data(HERE / "source_data.csv")
    draw_imax0_1_3(
        load_data(), vof_hf, HERE / "stationary_imax0_1_3_vof_hf.png"
    )


if __name__ == "__main__":
    main()
