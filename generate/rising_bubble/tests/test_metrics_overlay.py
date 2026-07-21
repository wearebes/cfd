from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src/make_metrics_overlay.py"
SPEC = importlib.util.spec_from_file_location("rising_metrics_overlay", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

ROOT = Path(__file__).resolve().parents[3]
STOCK = ROOT / "basilisk/src/test/rising.c"


def test_adds_separate_half_domain_circularity_history() -> None:
    source = STOCK.read_text(encoding="utf-8")
    output = MODULE.build_overlay_text(source)
    assert 'printf ("t sb -1 xb vb dt perf.t perf.speed\\n")' in output
    assert 'fopen ("circularity.csv", "w")' in output
    assert "event circularity_history" in output
    assert "event circularity_history (i++)" in output
    assert "event circularity_final (t = 3.)" in output
    assert "double perim = interface_area (f);" in output
    assert "sqrt (2.*pi*sb)/perim" in output
    assert output.count(MODULE.LOGFILE_END) == 1


def test_provenance_records_full_domain_reconstruction() -> None:
    source = STOCK.read_text(encoding="utf-8")
    output = MODULE.build_overlay_text(source)
    provenance = MODULE.build_provenance(source, output)
    assert provenance["source_sha256"] != provenance["generated_sha256"]
    assert provenance["diagnostic_file"] == "circularity.csv"
    reconstruction = provenance["half_domain_reconstruction"]
    assert reconstruction["area_full"] == "2*sb"
    assert reconstruction["perimeter_full"] == "2*interface_area(f)"


def test_rejects_nonstock_or_already_instrumented_source() -> None:
    source = STOCK.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        MODULE.build_overlay_text(MODULE.build_overlay_text(source))
