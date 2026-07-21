from __future__ import annotations

import importlib.util

from conftest import ROOT, SHARED


def test_overlay_changes_only_include_and_one_assignment() -> None:
    module_path = SHARED / "make_overlay_integral.py"
    spec = importlib.util.spec_from_file_location("overlay", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (ROOT / "basilisk/src/integral.h").read_text(encoding="utf-8")
    overlay = module.build_overlay_text(source)
    assert source.count(module.TARGET) == 1
    assert overlay.count(module.REPLACEMENT) == 1
    assert overlay.count('#include "clsvof_nn_cell_curvature.h"') == 1
    restored = overlay.replace(module.REPLACEMENT, module.TARGET, 1).replace(
        '#endif // CURVATURE\n\n#include "clsvof_nn_cell_curvature.h"\n',
        "#endif // CURVATURE\n",
        1,
    )
    assert restored == source
