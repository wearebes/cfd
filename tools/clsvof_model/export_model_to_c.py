#!/usr/bin/env python3
"""Export a trusted local PyTorch MLP checkpoint to C-readable model data."""

from __future__ import annotations

import argparse
import csv
import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


EXPECTED_STATE_KEYS = (
    "net.0.weight",
    "net.0.bias",
    "net.2.weight",
    "net.2.bias",
    "net.4.weight",
    "net.4.bias",
    "net.6.weight",
    "net.6.bias",
    "net.8.weight",
    "net.8.bias",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--stats-csv", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--all-from", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--trust-local-checkpoint",
        action="store_true",
        default=True,
        help="Load the local checkpoint bundle with weights_only=False.",
    )
    return parser.parse_args()


def load_stats_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def c_identifier(name: str) -> str:
    chars = [ch if ch.isalnum() else "_" for ch in name]
    ident = "".join(chars).strip("_").lower()
    if not ident or ident[0].isdigit():
        ident = f"model_{ident}"
    return ident


def as_float_list(value: Any) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    if hasattr(value, "reshape"):
        value = value.reshape(-1)
    return [float(x) for x in value]


def to_float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def c_float32_literal(value: float) -> str:
    return f"{to_float32(value).hex()}f"


def format_values(values: list[float], per_line: int = 6) -> str:
    chunks = []
    for i in range(0, len(values), per_line):
        chunk = ", ".join(c_float32_literal(v) for v in values[i : i + per_line])
        chunks.append(f"  {chunk}")
    return ",\n".join(chunks)


def format_1d(name: str, values: list[float]) -> str:
    return f"static const float {name}[{len(values)}] = {{\n{format_values(values)}\n}};\n"


def format_2d(name: str, rows: int, cols: int, values: list[float]) -> str:
    lines = [f"static const float {name}[{rows}][{cols}] = {{"]
    for r in range(rows):
        row = values[r * cols : (r + 1) * cols]
        suffix = "," if r + 1 < rows else ""
        lines.append(f"  {{{', '.join(c_float32_literal(v) for v in row)}}}{suffix}")
    lines.append("};")
    return "\n".join(lines) + "\n"


def write_weights_header(out_path: Path, model_name: str, checkpoint: dict[str, Any]) -> None:
    state = checkpoint["state_dict"]
    missing = [key for key in EXPECTED_STATE_KEYS if key not in state]
    if missing:
        raise ValueError(f"Missing expected state_dict keys: {missing}")

    feature_transform = checkpoint["feature_transform"]
    model_config = checkpoint["model_config"]
    input_dim = int(feature_transform["output_dim"])
    raw_feature_dim = int(feature_transform["raw_feature_dim"])
    hidden_units = int(model_config["hidden_units"])

    if feature_transform["transform_kind"] != "standardize":
        raise ValueError(
            f"This C exporter only implements (raw - mean) / std; got "
            f"transform_kind={feature_transform['transform_kind']!r}."
        )
    if input_dim != raw_feature_dim:
        raise ValueError("This C exporter currently expects standardize-only 27D input.")
    if input_dim != int(model_config["input_dim"]):
        raise ValueError("Model input_dim does not match feature_transform output_dim.")

    guard = f"CLSVOF_NN_WEIGHTS_{c_identifier(model_name).upper()}_H"
    layers = [
        ("clsvof_nn_w0", "clsvof_nn_b0", "net.0.weight", "net.0.bias", hidden_units, input_dim),
        ("clsvof_nn_w1", "clsvof_nn_b1", "net.2.weight", "net.2.bias", hidden_units, hidden_units),
        ("clsvof_nn_w2", "clsvof_nn_b2", "net.4.weight", "net.4.bias", hidden_units, hidden_units),
        ("clsvof_nn_w3", "clsvof_nn_b3", "net.6.weight", "net.6.bias", hidden_units, hidden_units),
        ("clsvof_nn_w4", "clsvof_nn_b4", "net.8.weight", "net.8.bias", 1, hidden_units),
    ]

    parts = [
        f"#ifndef {guard}",
        f"#define {guard}",
        "",
        "/* Generated model data only. Do not edit by hand. */",
        f"#define CLSVOF_NN_INPUT_DIM {input_dim}",
        f"#define CLSVOF_NN_RAW_FEATURE_DIM {raw_feature_dim}",
        f"#define CLSVOF_NN_HIDDEN_UNITS {hidden_units}",
        '#define CLSVOF_NN_FEATURE_ORDER "phi9+nx9+ny9"',
        '#define CLSVOF_NN_OUTPUT_CONTRACT "h*kappa"',
        '#define CLSVOF_NN_NUMERIC_STORAGE "float32_hex"',
        '#define CLSVOF_NN_INFERENCE_DTYPE "float32"',
        "",
        format_1d("clsvof_nn_mean", as_float_list(feature_transform["mean"])),
        format_1d("clsvof_nn_std", as_float_list(feature_transform["std"])),
    ]

    for w_name, b_name, w_key, b_key, rows, cols in layers:
        values = as_float_list(state[w_key])
        if len(values) != rows * cols:
            raise ValueError(f"{w_key} shape does not match expected {rows}x{cols}")
        parts.append(format_2d(w_name, rows, cols, values))
        parts.append(format_1d(b_name, as_float_list(state[b_key])))

    parts.extend(["#endif", ""])
    out_path.write_text("\n".join(parts), encoding="utf-8")


def write_manifest(out_path: Path, model_name: str, checkpoint_path: Path, stats_path: Path, checkpoint: dict[str, Any]) -> None:
    feature_transform = checkpoint["feature_transform"]
    manifest = {
        "name": model_name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_checkpoint": str(checkpoint_path),
        "source_stats_csv": str(stats_path),
        "output_contract": "h*kappa",
        "numeric_storage": "C float arrays with C99 hexadecimal float literals",
        "inference_dtype": "float32",
        "solver_scale_note": "The model predicts q_gamma=Delta*kappa_gamma on the zero level set. At the cell-local Basilisk integral.h insertion site use q_cell=q_gamma/(1+(d/Delta)*q_gamma), then kappa_cell=q_cell/Delta.",
        "feature_transform": {
            "transform_kind": feature_transform["transform_kind"],
            "feature_version": int(feature_transform["feature_version"]),
            "raw_feature_dim": int(feature_transform["raw_feature_dim"]),
            "output_dim": int(feature_transform["output_dim"]),
            "feature_order": feature_transform["feature_order"],
            "source_split": feature_transform["source_split"],
            "dataset_path": feature_transform["dataset_path"],
        },
        "model_config": checkpoint["model_config"],
        "files": {
            "weights_header": "nn_weights.h",
        },
    }
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export_one(checkpoint_path: Path, stats_path: Path, model_name: str, output_root: Path) -> Path:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint.get("model_type") != "mlp":
        raise ValueError(f"Unsupported model_type: {checkpoint.get('model_type')}")

    stats_rows = load_stats_csv(stats_path)
    if len(stats_rows) != int(checkpoint["feature_transform"]["raw_feature_dim"]):
        raise ValueError("stats CSV row count does not match raw feature dimension")

    out_dir = output_root / model_name
    out_dir.mkdir(parents=True, exist_ok=True)
    write_weights_header(out_dir / "nn_weights.h", model_name, checkpoint)
    write_manifest(out_dir / "export_manifest.json", model_name, checkpoint_path, stats_path, checkpoint)
    return out_dir


def iter_models(model_dir: Path) -> list[tuple[Path, Path, str]]:
    models = []
    for checkpoint in sorted(model_dir.glob("*.pt")):
        name = checkpoint.stem
        stats = checkpoint.with_suffix(".csv")
        if not stats.exists():
            raise FileNotFoundError(f"Missing stats CSV for {checkpoint}: {stats}")
        models.append((checkpoint, stats, name))
    return models


def main() -> int:
    args = parse_args()
    if args.all_from:
        for checkpoint_path, stats_path, model_name in iter_models(args.all_from):
            print(export_one(checkpoint_path, stats_path, model_name, args.output_root))
        return 0

    if not (args.checkpoint and args.stats_csv and args.name):
        raise SystemExit("--checkpoint, --stats-csv, and --name are required unless --all-from is used")

    out_dir = export_one(args.checkpoint, args.stats_csv, args.name, args.output_root)
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
