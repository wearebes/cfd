#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tarfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.export_deployment import export_workspace  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_deployment_package(package: Path) -> Path:
    package = package.resolve()
    checksum = Path(str(package) + ".sha256")
    if package.exists() or checksum.exists():
        raise ValueError(f"refusing to overwrite deployment package: {package}")
    package.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    stage = package.parent / f".deployment-staging-{token}"
    staged_archive = package.parent / f".{package.name}.staging-{token}"
    exported = stage / "cfd-hpc-runner"
    try:
        export_workspace(exported)
        with tarfile.open(staged_archive, "w:gz") as archive:
            archive.add(exported, arcname="cfd-hpc-runner", recursive=True)
        with tarfile.open(staged_archive, "r:gz") as archive:
            for member in archive.getmembers():
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError(f"unsafe archive member: {member.name}")
        os.replace(staged_archive, package)
        checksum.write_text(
            f"{sha256_file(package)}  {package.name}\n", encoding="utf-8"
        )
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if staged_archive.exists():
            staged_archive.unlink()
    return checksum


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    try:
        checksum = build_deployment_package(args.package)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(args.package.resolve())
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
