from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest

from hpc.package_results import build_package


def test_package_is_safe_and_has_outer_checksum(tmp_path: Path) -> None:
    source = tmp_path / "matrix"
    source.mkdir()
    (source / "SHA256SUMS").write_text("placeholder\n", encoding="utf-8")
    (source / "result.txt").write_text("result\n", encoding="utf-8")
    package = tmp_path / "packages/result.tar.gz"
    checksum = build_package(source, package)
    expected = checksum.read_text().split()[0]
    assert hashlib.sha256(package.read_bytes()).hexdigest() == expected
    with tarfile.open(package, "r:gz") as archive:
        names = archive.getnames()
    assert names
    assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)


def test_package_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "matrix"
    source.mkdir()
    (source / "SHA256SUMS").write_text("placeholder\n", encoding="utf-8")
    package = tmp_path / "result.tar.gz"
    build_package(source, package)
    with pytest.raises(ValueError, match="refusing to overwrite"):
        build_package(source, package)
