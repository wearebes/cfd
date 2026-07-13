#!/usr/bin/env python3
"""Run the repository's plain-function golden-vector tests without pytest."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("test_file", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    test_file = args.test_file.resolve()
    spec = importlib.util.spec_from_file_location("clsvof_golden_vector_tests", test_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {test_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests = [
        getattr(module, name)
        for name in sorted(dir(module))
        if name.startswith("test_") and callable(getattr(module, name))
    ]
    if not tests:
        raise RuntimeError(f"no test functions discovered: {test_file}")
    for test in tests:
        test()
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
