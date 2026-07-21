from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

import hpc.verify_matrix as verify_matrix
from hpc.lib.dataset_publish import publish_scientific_row
from hpc.lib.matrix import MatrixRow, result_relative_path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_contract(source: Path, products: dict[str, tuple[str, str]]) -> None:
    artifacts = []
    for path, (publish_name, role) in products.items():
        candidate = source / path
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(f"scientific data for {publish_name}\n", encoding="utf-8")
        artifacts.append(
            {
                "path": path,
                "publish_name": publish_name,
                "publish": True,
                "role": role,
                "sha256": sha256(candidate),
            }
        )
    (source / "manifest.json").write_text("{}\n", encoding="utf-8")
    (source / "scientific_artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "official_coverage_complete": True,
                "artifacts": artifacts,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_publish_verified_dataset_uses_complete_immutable_v2_contract(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(verify_matrix, "ROOT", tmp_path)
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    result_root = tmp_path / "results"
    rows = [
        MatrixRow("capwave", "clsvof", 64, 0),
        MatrixRow("rising_case1", "nn", 64, 1),
        MatrixRow("stationary_bubble", "clsvof", 64, 0),
    ]
    products = {
        "capwave": {
            "wave-64": ("wave.dat", "official_raw"),
            "log": ("official_error.dat", "official_raw"),
            "metrics.csv": ("metrics.csv", "derived_metrics"),
        },
        "rising_case1": {
            "stdout.txt": ("history.dat", "official_raw"),
            "log": ("interface.dat", "official_raw"),
            "circularity.csv": ("circularity.csv", "extension_raw"),
        },
        "stationary_bubble": {
            "clsvof/La-12000-6": ("timeseries.dat", "official_raw"),
            "official_terminal.dat": ("official_terminal.dat", "official_raw"),
            "metrics.csv": ("metrics.csv", "derived_metrics"),
        },
    }
    manifests: dict[str, dict[str, object]] = {}
    for index, row in enumerate(rows, start=1):
        source = result_root / result_relative_path(row)
        source.mkdir(parents=True)
        write_contract(source, products[row.benchmark])
        manifests[row.row_id] = {"execution": {"elapsed_seconds": index + 0.25}}

    verify_matrix.publish_verified_dataset(result_root, rows, manifests)

    assert (dataset / "capwave/formal_v2/N0064/imax00/clsvof/wave.dat").is_file()
    assert (
        dataset
        / "rising_bubble/formal_v2/case1/N0064/imax01/nn/history.dat"
    ).is_file()
    assert (
        dataset
        / "rising_bubble/formal_v2/case1/N0064/imax01/nn/circularity.csv"
    ).is_file()
    assert (
        dataset
        / "stationary_bubble/formal_v2/N0064/imax00/clsvof/official_terminal.dat"
    ).is_file()
    assert len(list(dataset.rglob("scientific_artifacts.json"))) == 3
    assert len(list(dataset.rglob("manifest.json"))) == 3

    with (dataset / "runtime_v2.csv").open(newline="", encoding="utf-8") as stream:
        runtime_rows = list(csv.DictReader(stream))
    assert len(runtime_rows) == 3
    stationary = next(row for row in runtime_rows if row["case"] == "stationary_bubble")
    assert stationary["complete"] == "true"


def test_identical_content_across_rows_is_allowed_but_overwrite_is_refused(
    tmp_path: Path,
) -> None:
    source_a = tmp_path / "source_a"
    source_b = tmp_path / "source_b"
    source_a.mkdir()
    source_b.mkdir()
    common = {"raw.dat": ("raw.dat", "official_raw")}
    write_contract(source_a, common)
    write_contract(source_b, common)
    target_a = tmp_path / "dataset/formal_v2/row_a"
    target_b = tmp_path / "dataset/formal_v2/row_b"
    assert publish_scientific_row(source_a, target_a) == "published"
    assert publish_scientific_row(source_b, target_b) == "published"
    assert publish_scientific_row(source_a, target_a) == "reused"

    (source_a / "raw.dat").write_text("changed\n", encoding="utf-8")
    contract = json.loads((source_a / "scientific_artifacts.json").read_text())
    contract["artifacts"][0]["sha256"] = sha256(source_a / "raw.dat")
    (source_a / "scientific_artifacts.json").write_text(json.dumps(contract) + "\n")
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        publish_scientific_row(source_a, target_a)
