from __future__ import annotations

import json
from pathlib import Path

from hpc.verify_rising_openmp_smokes import EXPECTED, inspect


def make_smoke(path: Path, *, case2: bool, method: str) -> None:
    path.mkdir()
    manifest = {
        "benchmark": "rising_case2" if case2 else "rising_case1",
        "benchmark_case": "hysing_case_2" if case2 else "hysing_case_1",
        "method": method,
        "resolution": 64,
        "imax": 3,
        "openmp_threads": 4,
        "compile_defines": ["LEVELSET=1", "CLSVOF=1", "LEVEL=6"]
        + (["CASE2=1"] if case2 else []),
        "artifacts": {"cell_curvature_sha256": "synthetic"},
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "stdout.txt").write_text(
        "t sb x xb vb\n0 0 -1 0.5 0\n3 0 -1 1.0 0.2\n", encoding="utf-8"
    )
    (path / "compile.stderr").write_text("", encoding="utf-8")
    stats = (
        "kappa_offset_provider_stats evaluations=10\n"
        if method == "nn"
        else ""
    )
    (path / "log").write_text(stats, encoding="utf-8")


def test_inspect_accepts_case2_nn_openmp_contract(tmp_path: Path) -> None:
    smoke = tmp_path / "case2_nn"
    make_smoke(smoke, case2=True, method="nn")
    record = inspect(smoke, EXPECTED[3])
    assert record["failures"] == []
    assert record["t_final"] == 3.0
    assert record["stats_lines"] == 1


def test_inspect_rejects_case2_without_compile_define(tmp_path: Path) -> None:
    smoke = tmp_path / "case2_native"
    make_smoke(smoke, case2=True, method="clsvof")
    manifest_path = smoke / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compile_defines"].remove("CASE2=1")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    record = inspect(smoke, EXPECTED[2])
    assert any("CASE2 define mismatch" in failure for failure in record["failures"])
