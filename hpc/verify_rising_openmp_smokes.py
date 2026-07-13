#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.lib.integrity import atomic_json, sha256_file  # noqa: E402


EXPECTED = (
    ("case1_native", "rising_case1", "hysing_case_1", "clsvof_native", False),
    ("case1_nn", "rising_case1", "hysing_case_1", "clsvof_nn_cell_offset", False),
    ("case2_native", "rising_case2", "hysing_case_2", "clsvof_native", True),
    ("case2_nn", "rising_case2", "hysing_case_2", "clsvof_nn_cell_offset", True),
)


def valid_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        try:
            values = [float(value) for value in fields[:5]]
        except ValueError:
            continue
        if all(math.isfinite(value) for value in values):
            rows.append(values)
    return rows


def inspect(path: Path, expected: tuple[str, str, str, str, bool]) -> dict[str, Any]:
    label, benchmark, benchmark_case, method, case2 = expected
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    rows = valid_rows(path / "stdout.txt")
    compile_stderr_bytes = (path / "compile.stderr").stat().st_size
    stats = [
        line
        for line in (path / "log").read_text(encoding="utf-8").splitlines()
        if line.startswith("kappa_offset_provider_stats ")
    ]
    defines = manifest.get("compile_defines", [])
    failures = []
    for key, wanted in {
        "benchmark": benchmark,
        "benchmark_case": benchmark_case,
        "method": method,
        "resolution": 64,
        "imax": 3,
    }.items():
        if manifest.get(key) != wanted:
            failures.append(f"{key}={manifest.get(key)!r}, expected {wanted!r}")
    if int(manifest.get("openmp_threads", 0)) <= 1:
        failures.append("openmp_threads must exceed one")
    if not rows or rows[-1][0] != 3.0:
        failures.append("output did not reach t=3")
    if compile_stderr_bytes:
        failures.append("compile.stderr is nonempty")
    if ("CASE2=1" in defines) != case2:
        failures.append(f"CASE2 define mismatch: {defines}")
    expected_stats = 1 if method == "clsvof_nn_cell_offset" else 0
    if len(stats) != expected_stats:
        failures.append(f"stats line count={len(stats)}, expected {expected_stats}")
    return {
        "label": label,
        "path": str(path.resolve()),
        "benchmark": benchmark,
        "benchmark_case": benchmark_case,
        "method": method,
        "threads": manifest.get("openmp_threads"),
        "compile_defines": defines,
        "valid_rows": len(rows),
        "t_final": rows[-1][0] if rows else None,
        "compile_stderr_bytes": compile_stderr_bytes,
        "cell_curvature_sha256": manifest.get("artifacts", {}).get(
            "cell_curvature_sha256"
        ),
        "stats_lines": len(stats),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    for label, *_ in EXPECTED:
        parser.add_argument(f"--{label.replace('_', '-')}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [
        inspect(getattr(args, label), expected)
        for expected in EXPECTED
        for label in [expected[0]]
    ]
    failures = [failure for record in records for failure in record["failures"]]
    if records[0]["valid_rows"] != records[1]["valid_rows"]:
        failures.append("Case 1 native/NN row counts differ")
    if records[2]["valid_rows"] != records[3]["valid_rows"]:
        failures.append("Case 2 native/NN row counts differ")
    canonical = sha256_file(
        ROOT / "cases/_shared/nn_cell_curvature/src/clsvof_nn_cell_curvature.h"
    )
    for record in (records[1], records[3]):
        if record["cell_curvature_sha256"] != canonical:
            failures.append(f"{record['label']} canonical provider hash mismatch")
    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "FAIL",
        "canonical_cell_curvature_sha256": canonical,
        "records": records,
        "failures": failures,
    }
    atomic_json(args.output, payload)
    print(json.dumps({"status": payload["status"], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
