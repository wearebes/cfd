#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.lib.integrity import atomic_json, inventory  # noqa: E402


COPY_ROOTS = (
    Path("basilisk/src"),
    Path("cases"),
    Path("dataset/model/c_exports"),
    Path("tools/clsvof_model"),
    Path("hpc"),
    Path(".github"),
)
COPY_FILES = (
    Path(".gitignore"),
    Path("docs/superpowers/plans/2026-07-13-ubuntu-hpc-180-row-openmp-implementation.md"),
    Path("docs/server/ubuntu22-hpc-operator-handoff.md"),
)
SKIP_NAMES = {".DS_Store", "__pycache__", ".pytest_cache", ".qcc"}
SKIP_SUFFIXES = {".o", ".a", ".so", ".dylib", ".pyc", ".dSYM"}
MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
}


def is_macho(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    with path.open("rb") as stream:
        return stream.read(4) in MACHO_MAGICS


def should_skip(relative: Path, source: Path) -> bool:
    if any(part in SKIP_NAMES for part in relative.parts):
        return True
    if relative.suffix in SKIP_SUFFIXES:
        return True
    if relative in {
        Path("basilisk/src/qcc"),
        Path("basilisk/src/config"),
        Path("basilisk/src/config.osx"),
    }:
        return True
    if relative.parts[:2] == ("hpc", "work"):
        return True
    if relative.parts[:2] == ("hpc", "results"):
        return True
    if relative.parts[:2] == ("hpc", "packages"):
        return True
    return is_macho(source)


def copy_tree(source: Path, destination: Path, relative: Path) -> None:
    if should_skip(relative, source):
        return
    if source.is_symlink():
        target = os.readlink(source)
        if os.path.isabs(target):
            raise ValueError(f"absolute symlink is forbidden: {relative} -> {target}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(target)
        return
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir(), key=lambda path: path.name):
            copy_tree(child, destination / child.name, relative / child.name)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    return parser.parse_args(argv)


def export_workspace(destination: Path) -> dict[str, object]:
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"destination must be absent or empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    for relative in COPY_ROOTS:
        source = ROOT / relative
        if not source.exists():
            raise SystemExit(f"required deployment root is missing: {relative}")
        copy_tree(source, destination / relative, relative)
    for relative in COPY_FILES:
        source = ROOT / relative
        if not source.is_file():
            raise SystemExit(f"required deployment file is missing: {relative}")
        copy_tree(source, destination / relative, relative)

    config = destination / "basilisk/src/config"
    config.symlink_to("config.gcc")
    payload = {
        "schema_version": 1,
        "source_identity": "cfd-hpc-runner-export",
        "files": inventory(destination),
    }
    atomic_json(destination / "DEPLOYMENT_MANIFEST.json", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    destination = args.destination.resolve()
    try:
        payload = export_workspace(destination)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(destination)
    print(f"files={len(payload['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
