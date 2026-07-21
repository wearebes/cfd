from __future__ import annotations

import importlib.util
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[2]
MODULE_PATH = CASE / "generate/make_runtime_redistance_overlay.py"
SPEC = importlib.util.spec_from_file_location("runtime_redistance_overlay", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_runtime_overlay_replaces_only_stock_call() -> None:
    source = (ROOT / "basilisk/src/two-phase-clsvof.h").read_text(encoding="utf-8")
    output = MODULE.build(source)
    assert output.count(MODULE.REPLACEMENT) == 1
    assert MODULE.TARGET not in output
