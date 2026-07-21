from __future__ import annotations

from pathlib import Path

import pytest

from hpc.export_deployment import is_macho, should_skip


def test_export_skips_build_products_and_runtime_outputs(tmp_path: Path) -> None:
    ordinary = tmp_path / "file.c"
    ordinary.write_text("int x;\n", encoding="utf-8")
    assert not should_skip(Path("generate/file.c"), ordinary)
    assert should_skip(Path("basilisk/src/qcc"), ordinary)
    assert should_skip(Path("basilisk/src/config.osx"), ordinary)
    assert should_skip(Path("basilisk/src/qcc.dSYM"), tmp_path)
    assert should_skip(Path("hpc/results/run/out"), ordinary)
    assert should_skip(Path("hpc/work/run/out"), ordinary)
    assert should_skip(Path("hpc/packages/a.tar.gz"), ordinary)
    assert should_skip(Path("build.o"), ordinary)


def test_macho_magic_is_rejected(tmp_path: Path) -> None:
    binary = tmp_path / "binary"
    binary.write_bytes(b"\xcf\xfa\xed\xfe" + b"payload")
    assert is_macho(binary)
    assert should_skip(Path("basilisk/src/binary"), binary)
