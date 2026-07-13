#!/usr/bin/env python3
"""Compatibility entrypoint for the accepted 180-row HPC matrix.

The former NN-only imax 0-10 scheduler is retired. Keep this path so old notes
resolve, but route every invocation to the authoritative hpc runner.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.run_matrix import main  # noqa: E402


if __name__ == "__main__":
    print(
        "notice: cases/_shared/nondefault_redistance/run_matrix.py now uses "
        "the authoritative hpc 180-row runner",
        file=sys.stderr,
    )
    raise SystemExit(main())
