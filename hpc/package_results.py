#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import tarfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_package(source: Path, package: Path) -> Path:
    if not source.is_dir():
        raise ValueError(f"result root is missing: {source}")
    if not (source / "SHA256SUMS").is_file():
        raise ValueError("verified result root must contain SHA256SUMS")
    if package.exists() or Path(str(package) + ".sha256").exists():
        raise ValueError(f"refusing to overwrite package: {package}")
    package.parent.mkdir(parents=True, exist_ok=True)
    arcname = f"cfd_hpc_180_{source.name}"
    with tarfile.open(package, "w:gz") as archive:
        archive.add(source, arcname=arcname, recursive=True)
    with tarfile.open(package, "r:gz") as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe archive member: {member.name}")
    checksum = Path(str(package) + ".sha256")
    checksum.write_text(
        f"{sha256_file(package)}  {package.name}\n", encoding="utf-8"
    )
    return checksum


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    checksum = build_package(args.source, args.package)
    print(args.package)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
