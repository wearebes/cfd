#!/usr/bin/env python3
"""Generate case summaries from the runners' executable dry-run contracts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


CASES: dict[str, list[tuple[str, list[str]]]] = {
    "capwave": [
        ("official", ["--resolution", "64"]),
        ("clsvof", ["--resolution", "64", "--imax", "3"]),
        ("nn", ["--resolution", "64", "--imax", "3"]),
    ],
    "rising_bubble": [
        ("official", ["--case", "1", "--resolution", "64"]),
        ("clsvof", ["--case", "1", "--resolution", "64", "--imax", "3"]),
        ("nn", ["--case", "1", "--resolution", "64", "--imax", "3"]),
    ],
    "stationary_bubble": [
        ("official", ["--resolution", "64"]),
        ("clsvof", ["--resolution", "64", "--imax", "3"]),
        ("nn", ["--resolution", "64", "--imax", "3"]),
    ],
    "oscillating_droplet": [
        ("official", []),
        ("clsvof", ["--method", "clsvof", "--resolution", "64"]),
        ("nn", ["--method", "nn", "--resolution", "64"]),
    ],
}


def normalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(str(ROOT), "$REPO")
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    return value


def runner_contract(case: str, method: str, extra: list[str]) -> dict[str, Any]:
    if case == "oscillating_droplet" and method != "official":
        runner = ROOT / "generate/oscillating_droplet/nn/generate/run_row.py"
        prefix = [sys.executable, str(runner)]
    else:
        runner = ROOT / "generate" / case / f"{method}.sh"
        prefix = ["bash", str(runner)]
    output = ROOT / "tem" / "dry_run_contract" / case / method
    common = [
        "--formal",
        "--threads",
        "1",
        "--output",
        str(output),
        "--dry-run",
    ]
    completed = subprocess.run(
        [*prefix, *extra, *common],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{runner} dry-run failed:\n{completed.stdout}{completed.stderr}"
        )
    payload = json.loads(completed.stdout)
    help_result = subprocess.run(
        [*prefix, "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    plan = payload["plan"]
    return normalize(
        {
            "entrypoint": plan["generator"]["path"],
            "role": method,
            "usage": help_result.stdout.strip().splitlines(),
            "default_parameters": plan["parameters"],
            "commands": plan["commands"],
            "sources": plan["sources"],
        }
    )


def render(case: str) -> str:
    payload = {
        "schema_version": 2,
        "generated_by": "generate/_shared/render_summaries.py",
        "source_of_truth": "runner --dry-run",
        "case": case,
        "interfaces": {
            method: runner_contract(case, method, extra)
            for method, extra in CASES[case]
        },
    }
    # JSON is valid YAML 1.2 and avoids introducing a YAML runtime dependency.
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case", action="append", choices=sorted(CASES))
    args = parser.parse_args()
    selected = args.case or sorted(CASES)
    drift: list[str] = []
    for case in selected:
        path = ROOT / "generate" / case / "summary.yaml"
        expected = render(case)
        if args.check:
            if not path.is_file() or path.read_text() != expected:
                drift.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(expected, encoding="utf-8")
    if drift:
        raise SystemExit("generated summary drift: " + ", ".join(drift))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
