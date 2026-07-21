from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from hpc.lib.integrity import sha256_file


def scientific_publish_products(source_dir: Path) -> dict[str, Path]:
    contract_path = source_dir / "scientific_artifacts.json"
    manifest_path = source_dir / "manifest.json"
    if not contract_path.is_file() or not manifest_path.is_file():
        raise RuntimeError(f"missing v2 scientific contract in {source_dir}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_contract_hash = manifest.get("scientific_artifacts_sha256")
    if expected_contract_hash and sha256_file(contract_path) != expected_contract_hash:
        raise RuntimeError(f"scientific contract hash mismatch in {source_dir}")
    if not contract.get("official_coverage_complete"):
        raise RuntimeError(f"official artifact coverage is incomplete in {source_dir}")
    products: dict[str, Path] = {}
    for record in contract.get("artifacts", []):
        if not record.get("publish"):
            continue
        name = str(record["publish_name"])
        relative_name = Path(name)
        if relative_name.is_absolute() or ".." in relative_name.parts:
            raise RuntimeError(f"unsafe publish name {name!r} in {contract_path}")
        source = source_dir / str(record["path"])
        if name in products:
            raise RuntimeError(f"duplicate publish name {name!r} in {contract_path}")
        if not source.is_file() or sha256_file(source) != record.get("sha256"):
            raise RuntimeError(f"scientific artifact hash mismatch: {source}")
        products[name] = source
    products["scientific_artifacts.json"] = contract_path
    products["manifest.json"] = manifest_path
    return products


def publish_scientific_row(source_dir: Path, target_dir: Path) -> str:
    """Publish one immutable v2 row; identical content is reusable, never replaced."""
    products = scientific_publish_products(source_dir)
    if target_dir.exists():
        if not target_dir.is_dir():
            raise RuntimeError(f"publish target is not a directory: {target_dir}")
        existing = {
            path.relative_to(target_dir).as_posix(): path
            for path in target_dir.rglob("*")
            if path.is_file()
        }
        if set(existing) != set(products):
            raise RuntimeError(f"existing v2 row has a different file set: {target_dir}")
        different = [
            name for name, source in products.items()
            if sha256_file(source) != sha256_file(existing[name])
        ]
        if different:
            raise RuntimeError(
                f"refusing to overwrite existing v2 row {target_dir}; changed: {different}"
            )
        return "reused"

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = target_dir.parent / f".{target_dir.name}.publish.{os.getpid()}"
    if staging.exists():
        raise RuntimeError(f"stale publish staging exists: {staging}")
    staging.mkdir()
    try:
        for name, source in products.items():
            destination = staging / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if sha256_file(source) != sha256_file(destination):
                raise RuntimeError(f"dataset publish hash mismatch: {source}")
        os.replace(staging, target_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return "published"
