#!/usr/bin/env python3
"""Analytic circle/ellipse matrix using the deployed raw27 and checkpoints."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn


ROOT = Path(__file__).resolve().parents[2]
MODELS = ("baseline_64_hgradient", "baseline_128_hgradient",
          "baseline_256_hgradient", "baseline_512_hgradient")
FIXED_OFFSETS = (-1., -.75, -.5, -.25, 0., .25, .5, .75, 1.)
ANGLES = tuple(2.*math.pi*(index + .371)/96. for index in range(96))
GUARD = .25


class MLP(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(27, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU(),
            nn.Linear(128, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU(),
            nn.Linear(128, 1),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.net(value)


class Circle:
    name = "circle"

    def __init__(self, radius: float = .25) -> None:
        self.radius = radius

    def interface(self, theta: float) -> tuple[float, float, float, float, float]:
        return (self.radius*math.cos(theta), self.radius*math.sin(theta),
                math.cos(theta), math.sin(theta), 1./self.radius)

    def sdf(self, x: float, y: float) -> float:
        return math.hypot(x, y) - self.radius


class Ellipse:
    name = "ellipse"

    def __init__(self, a: float = .37, b: float = .21) -> None:
        self.a, self.b = a, b

    def interface(self, theta: float) -> tuple[float, float, float, float, float]:
        x, y = self.a*math.cos(theta), self.b*math.sin(theta)
        nx, ny = x/(self.a*self.a), y/(self.b*self.b)
        normal = math.hypot(nx, ny)
        kappa = self.a*self.b/(self.a*self.a*math.sin(theta)**2 +
                               self.b*self.b*math.cos(theta)**2)**1.5
        return x, y, nx/normal, ny/normal, kappa

    def sdf(self, x: float, y: float) -> float:
        """Euclidean signed distance; samples remain inside the tubular region."""
        a2, b2 = self.a*self.a, self.b*self.b
        outside = (x/self.a)**2 + (y/self.b)**2 >= 1.

        def residual(lam: float) -> float:
            return (self.a*x/(a2 + lam))**2 + (self.b*y/(b2 + lam))**2 - 1.

        if outside:
            lo, hi = 0., max(a2, b2)
            while residual(hi) > 0.:
                hi *= 2.
        else:
            lo, hi = -b2 + 1e-14, 0.
        for _ in range(100):
            mid = (lo + hi)/2.
            if residual(mid) > 0.:
                lo = mid
            else:
                hi = mid
        lam = (lo + hi)/2.
        qx, qy = a2*x/(a2 + lam), b2*y/(b2 + lam)
        distance = math.hypot(x - qx, y - qy)
        return distance if outside else -distance


def raw27_and_native(shape: Circle | Ellipse, point: tuple[float, float],
                     h: float, levelset_sign: int) -> tuple[np.ndarray, float, float, float]:
    x0, y0 = point
    patch = np.empty((5, 5), dtype=float)
    for i in range(5):
        for j in range(5):
            patch[i, j] = levelset_sign*shape.sdf(x0 + (i - 2)*h, y0 + (j - 2)*h)
    raw: list[float] = []
    for j in (3, 2, 1):
        for i in (1, 2, 3):
            raw.append(float(patch[i, j]/h))
    normals: list[tuple[float, float]] = []
    for j in (3, 2, 1):
        for i in (1, 2, 3):
            gx = (patch[i + 1, j] - patch[i - 1, j])/(2.*h)
            gy = (patch[i, j + 1] - patch[i, j - 1])/(2.*h)
            norm = math.hypot(gx, gy) + 1e-30
            normals.append((gx/norm, gy/norm))
            raw.append(float(gx/norm))
    raw.extend(float(gy) for _, gy in normals)
    dx = (patch[3, 2] - patch[1, 2])/2.
    dy = (patch[2, 3] - patch[2, 1])/2.
    dxx = patch[3, 2] - 2.*patch[2, 2] + patch[1, 2]
    dyy = patch[2, 3] - 2.*patch[2, 2] + patch[2, 1]
    dxy = (patch[3, 3] - patch[1, 3] - patch[3, 1] + patch[1, 1])/4.
    norm = math.hypot(dx, dy) + 1e-30
    q_native = (dx*dx*dyy - 2.*dx*dy*dxy + dy*dy*dxx)/(norm**3)
    return np.asarray(raw, dtype=np.float32), patch[2, 2]/h, q_native, norm/h


def predict(model_name: str, values: np.ndarray) -> np.ndarray:
    checkpoint = torch.load(ROOT/"dataset/model"/f"{model_name}.pt",
                            map_location="cpu", weights_only=False)
    model = MLP()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    transform = checkpoint["feature_transform"]
    mean = torch.as_tensor(transform["mean"], dtype=torch.float32)
    std = torch.as_tensor(transform["std"], dtype=torch.float32)
    with torch.no_grad():
        output = model((torch.as_tensor(values, dtype=torch.float32) - mean)/std)
    return output.reshape(-1).numpy().astype(float)


def conversion(q_gamma: float, s: float) -> tuple[float, float, int]:
    denominator = 1. + s*q_gamma
    guard = int(abs(denominator) < GUARD)
    safe = (math.copysign(GUARD, denominator if denominator else 1.)
            if guard else denominator)
    return q_gamma/safe, abs(denominator), guard


def add_metrics(samples: list[dict], result: list[dict], shape: str,
                sign: int, model: str, offset_bin: str) -> None:
    for method in ("nn_cell_levelset", "native_fd"):
        for reference in ("analytic_levelset", "native_fd"):
            error = np.asarray([row[method] - row[reference] for row in samples])
            actual = np.asarray([row[method] for row in samples])
            expected = np.asarray([row[reference] for row in samples])
            metrics = {
                "rmse": math.sqrt(float(np.mean(error*error))),
                "mae": float(np.mean(np.abs(error))),
                "bias": float(np.mean(error)),
                "max_abs_error": float(np.max(np.abs(error))),
                "sign_consistency": float(np.mean(np.signbit(actual) == np.signbit(expected))),
            }
            for metric, value in metrics.items():
                result.append({"geometry": shape, "levelset_sign": sign,
                               "model": model, "offset_bin": offset_bin,
                               "method": method, "reference": reference,
                               "metric": metric, "n": len(samples), "value": value})


def formula_gate() -> dict:
    maximum = 0.
    sign_consistent = True
    for h in (1/64, 1/128, 1/256):
        for kappa in (4., 1.3, 8.1):
            for sign in (-1., 1.):
                q_gamma = sign*h*kappa
                for s in FIXED_OFFSETS:
                    q_d = q_gamma/(1. + s*q_gamma)
                    maximum = max(maximum, abs(q_d/(1. - s*q_d) - q_gamma))
                    sign_consistent = sign_consistent and math.copysign(1., q_d) == math.copysign(1., q_gamma)
    return {"roundtrip_max_abs_error": maximum, "sign_flip_consistent": sign_consistent,
            "passed": maximum < 1e-12 and sign_consistent}


def c_parity_gate() -> dict:
    source = Path(__file__).with_name("tests")/"offset_c_cli.c"
    include = Path(__file__).with_name("include")
    vectors = [(q, s) for q in (-.15, -.03, .03, .15)
               for s in FIXED_OFFSETS]
    with tempfile.TemporaryDirectory() as temporary:
        executable = Path(temporary)/"offset_cli"
        subprocess.run(["cc", "-std=c99", "-O2", "-I", str(include),
                        str(source), "-o", str(executable), "-lm"], check=True)
        command = subprocess.run(
            [str(executable)], input="".join(f"{q} {s}\n" for q, s in vectors),
            text=True, capture_output=True, check=True,
        )
    maximum = 0.
    for (q, s), line in zip(vectors, command.stdout.splitlines(), strict=True):
        c_cell, c_inverse, *_ = map(float, line.split())
        p_cell = q/(1. + s*q)
        maximum = max(maximum, abs(c_cell - p_cell),
                      abs(c_inverse - p_cell/(1. - s*p_cell)))
    return {"max_abs_difference": maximum, "passed": maximum < 1e-7}


def h_for_model(model_name: str) -> float:
    return 1./int(model_name.split("_")[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--extra-offsets-json", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    extra_offsets: list[float] = []
    if args.extra_offsets_json:
        extra_offsets = [float(value) for value in json.loads(args.extra_offsets_json.read_text()).get("all", [])]

    all_metrics: list[dict] = []
    guard_hits, min_abs_denominator = 0, math.inf
    for model_name in MODELS:
        h = h_for_model(model_name)
        for shape in (Circle(), Ellipse()):
            for sign in (-1, 1):
                features, records = [], []
                for offset in (*FIXED_OFFSETS, *extra_offsets):
                    for theta in ANGLES:
                        x0, y0, nx, ny, kappa_gamma = shape.interface(theta)
                        point = (x0 + sign*offset*h*nx, y0 + sign*offset*h*ny)
                        raw, s, q_native, _ = raw27_and_native(shape, point, h, sign)
                        q_interface = sign*h*kappa_gamma
                        records.append({"offset": offset, "s": s, "native_fd": q_native,
                                        "analytic_levelset": q_interface/(1. + s*q_interface)})
                        features.append(raw)
                predictions = predict(model_name, np.stack(features))
                total: list[dict] = []
                by_offset: dict[float, list[dict]] = defaultdict(list)
                for prediction, record in zip(predictions, records, strict=True):
                    q_cell, minimum, count = conversion(float(prediction), record["s"])
                    guard_hits += count
                    min_abs_denominator = min(min_abs_denominator, minimum)
                    row = {**record, "nn_cell_levelset": q_cell}
                    total.append(row)
                    by_offset[record["offset"]].append(row)
                add_metrics(total, all_metrics, shape.name, sign, model_name, "all")
                for offset, values in by_offset.items():
                    add_metrics(values, all_metrics, shape.name, sign, model_name,
                                f"{offset:.12g}")

    path = args.output_dir/"offline_cell_metrics.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        columns = ["geometry", "levelset_sign", "model", "offset_bin", "method",
                   "reference", "metric", "n", "value"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_metrics)
    gates = {"formula": formula_gate(), "python_c_conversion": c_parity_gate(),
             "denominator_guard_hits": guard_hits,
             "min_abs_denominator": min_abs_denominator}
    gates["passed"] = bool(gates["formula"]["passed"] and
                           gates["python_c_conversion"]["passed"] and guard_hits == 0)
    (args.output_dir/"offline_gates.json").write_text(json.dumps(gates, indent=2) + "\n")
    print(path)
    print(args.output_dir/"offline_gates.json")
    return 0 if gates["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
