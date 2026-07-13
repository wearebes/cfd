#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = Path("/opt/anaconda3/envs/pinn/bin/python")
GOLDEN_PYTHON = Path(os.environ.get("CLSVOF_GOLDEN_PYTHON", "/opt/anaconda3/envs/ai/bin/python"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], cwd: Path, log: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    content = completed.stdout + completed.stderr
    log.parent.mkdir(parents=True, exist_ok=True)
    temporary = log.with_suffix(log.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, log)
    match = re.search(r"(\d+) passed", content)
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "passed_tests": int(match.group(1)) if match else None,
        "log": str(log),
        "command": command,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result_root = HERE / "results" / args.matrix_id
    audit_path = result_root / "audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.is_file() else {}
    if audit.get("passed") is not True or audit.get("state_counts") != {"completed": 96}:
        raise RuntimeError("verification blocked until the strict 96-row audit passes")

    verification = result_root / "verification"
    matrix_tests = run(
        [str(PYTHON), "-m", "pytest", "-q"],
        HERE,
        verification / "matrix_pytest.log",
    )
    golden_test = ROOT / "tools/clsvof_model/tests/test_golden_vector_parity.py"
    golden_runner = HERE / "run_golden_vector_tests.py"
    golden = run(
        [str(GOLDEN_PYTHON), str(golden_runner), str(golden_test)],
        ROOT,
        verification / "nn_golden_vector.log",
    )
    inputs = [
        HERE / "config/matrix.json",
        HERE / "audit_matrix.py",
        HERE / "summarize_matrix.py",
        HERE / "analyze_matrix.py",
        HERE / "plot_formal_matrix.py",
        golden_runner,
        golden_test,
        ROOT / "tools/clsvof_model/tests/fixtures/raw27_golden_vector.json",
        ROOT / "experiments/clsvof_kappa_offset_conversion/include/clsvof_nn_cell_curvature.h",
        ROOT / "tools/clsvof_model/include/clsvof_mlp_infer.h",
    ]
    payload = {
        "schema_version": 1,
        "matrix_id": args.matrix_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "matrix_pytest": matrix_tests,
        "nn_golden_vector": golden,
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "passed": matrix_tests["passed"] and golden["passed"],
    }
    temporary = result_root / "verification_manifest.json.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, result_root / "verification_manifest.json")
    print(json.dumps({"passed": payload["passed"], "matrix_tests": matrix_tests["passed_tests"], "golden_tests": golden["passed_tests"]}))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
