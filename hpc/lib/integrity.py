from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from hpc.lib.matrix import MatrixRow


MANIFEST_NAME = "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_count(path: Path) -> int:
    count = 0
    last = b""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
            last = chunk[-1:] or last
    if path.stat().st_size and last != b"\n":
        count += 1
    return count


def file_record(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe result path: {relative}")
    return {
        "path": relative.as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "lines": line_count(path),
    }


def inventory(root: Path) -> list[dict[str, Any]]:
    return [
        file_record(root, path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != MANIFEST_NAME
    ]


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def expected_identity(
    row: MatrixRow, matrix_id: str, policy_sha256: str | None
) -> dict[str, Any]:
    return {
        "matrix_id": matrix_id,
        "row_id": row.row_id,
        "benchmark": row.benchmark,
        "method": row.method,
        "resolution": row.resolution,
        "level": row.level,
        "actual_grid": row.actual_grid,
        "imax": row.imax,
        "model_name": row.model_name,
        "policy_sha256": policy_sha256,
    }


def staging_conflicts(final: Path) -> list[Path]:
    if not final.parent.exists():
        return []
    return sorted(final.parent.glob(f".{final.name}.staging.*"))


def validate_completed_result(
    path: Path,
    row: MatrixRow,
    matrix_id: str,
    policy_sha256: str | None,
) -> tuple[bool, str]:
    if staging_conflicts(path):
        return False, "stale staging directory exists"
    manifest_path = path / MANIFEST_NAME
    if not path.is_dir():
        return False, "result directory is missing"
    if not manifest_path.is_file():
        return False, "manifest.json is missing"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return False, f"invalid manifest: {error}"

    expected = expected_identity(row, matrix_id, policy_sha256)
    identity = manifest.get("formal_identity")
    if identity != expected:
        return False, f"formal identity mismatch: expected {expected}, got {identity}"

    declared = manifest.get("outputs")
    if not isinstance(declared, list):
        return False, "manifest outputs is not a list"
    actual_files = {
        path_.relative_to(path).as_posix()
        for path_ in path.rglob("*")
        if path_.is_file() and path_.name != MANIFEST_NAME
    }
    declared_paths = {
        item.get("path") for item in declared if isinstance(item, dict)
    }
    if None in declared_paths or actual_files != declared_paths:
        return False, (
            f"output path set mismatch: declared={sorted(map(str, declared_paths))} "
            f"actual={sorted(actual_files)}"
        )

    for item in declared:
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            return False, f"unsafe declared output path: {relative}"
        candidate = path / relative
        if not candidate.is_file():
            return False, f"missing declared output: {relative}"
        actual = file_record(path, candidate)
        if actual != item:
            return False, f"output integrity mismatch for {relative}"
    return True, "validated completed formal result"
