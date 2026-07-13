#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_MATRIX = HERE / "config/matrix.json"
PYTHON = "/opt/anaconda3/envs/pinn/bin/python"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    shared = ["--matrix-id", args.matrix_id]
    subprocess.run(
        [PYTHON, str(HERE / "summarize_matrix.py"), "--matrix", str(args.matrix), *shared],
        cwd=HERE,
        check=True,
    )
    subprocess.run(
        [PYTHON, str(HERE / "audit_provenance.py"), "--matrix", str(args.matrix), *shared],
        cwd=HERE,
        check=True,
    )
    subprocess.run(
        [PYTHON, str(HERE / "audit_workspace_boundary.py"), *shared],
        cwd=HERE,
        check=True,
    )
    subprocess.run(
        [PYTHON, str(HERE / "extract_timeseries.py"), "--matrix", str(args.matrix), *shared],
        cwd=HERE,
        check=True,
    )
    subprocess.run(
        [
            PYTHON,
            str(HERE / "audit_matrix.py"),
            "--matrix",
            str(args.matrix),
            *shared,
            "--allow-incomplete",
        ],
        cwd=HERE,
        check=True,
    )
    subprocess.run([PYTHON, str(HERE / "analyze_matrix.py"), *shared], cwd=HERE, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
