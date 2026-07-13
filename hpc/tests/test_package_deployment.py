from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest

from hpc.package_deployment import build_deployment_package


def test_deployment_package_is_clean_safe_and_hashed(tmp_path: Path) -> None:
    package = tmp_path / "cfd-hpc-runner.tar.gz"
    checksum = build_deployment_package(package)
    assert hashlib.sha256(package.read_bytes()).hexdigest() == checksum.read_text().split()[0]
    with tarfile.open(package, "r:gz") as archive:
        names = archive.getnames()
    assert "cfd-hpc-runner/hpc/submit_matrix.sh" in names
    assert (
        "cfd-hpc-runner/docs/server/ubuntu22-hpc-operator-handoff.md" in names
    )
    assert "cfd-hpc-runner/basilisk/src/qcc" not in names
    assert "cfd-hpc-runner/basilisk/src/config.osx" not in names
    assert not any(".dSYM" in Path(name).parts for name in names)
    assert not any(name.endswith((".o", ".a")) for name in names)
    assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)


def test_deployment_package_refuses_overwrite(tmp_path: Path) -> None:
    package = tmp_path / "cfd-hpc-runner.tar.gz"
    build_deployment_package(package)
    with pytest.raises(ValueError, match="refusing to overwrite"):
        build_deployment_package(package)
