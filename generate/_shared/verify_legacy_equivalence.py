#!/usr/bin/env python3
"""Verify the N64 legacy-to-generate migration without hiding runtime noise.

The gate compares solver/scientific streams exactly and treats only the known
stationary terminal-observable correction as an allowed difference. Runtime
performance text is inventoried but is not a numerical-equivalence field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric_rows(path: Path, minimum: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            values = [float(field) for field in line.split()]
        except ValueError:
            continue
        if len(values) >= minimum:
            rows.append(values)
    return rows


def provider_stats(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith("kappa_offset_provider_stats ")
    ]


def terminal_row(path: Path) -> list[float]:
    rows = [row for row in numeric_rows(path, 7) if len(row) == 7]
    if len(rows) != 1:
        raise ValueError(f"expected one seven-column terminal row: {path}")
    return rows[0]


def exact_file(
    checks: list[dict[str, Any]], name: str, legacy: Path, generated: Path
) -> None:
    legacy_hash = sha256(legacy)
    generated_hash = sha256(generated)
    checks.append(
        {
            "name": name,
            "status": "PASS" if legacy_hash == generated_hash else "FAIL",
            "comparison": "byte_exact",
            "legacy_sha256": legacy_hash,
            "generated_sha256": generated_hash,
            "legacy_bytes": legacy.stat().st_size,
            "generated_bytes": generated.stat().st_size,
        }
    )


def boolean_check(
    checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any
) -> None:
    checks.append(
        {"name": name, "status": "PASS" if passed else "FAIL", "evidence": evidence}
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy_root", type=Path)
    parser.add_argument("generated_root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    legacy = args.legacy_root.resolve()
    generated = args.generated_root.resolve()
    checks: list[dict[str, Any]] = []

    for method in ("clsvof", "nn"):
        row = f"capwave_{method}"
        exact_file(
            checks,
            f"{row}.trajectory",
            legacy / row / "wave-64",
            generated / row / "wave-64",
        )
        exact_file(
            checks,
            f"{row}.official_error_and_provider_log",
            legacy / row / "log",
            generated / row / "log",
        )

    for method in ("clsvof", "nn"):
        row = f"rising_{method}"
        legacy_history = numeric_rows(legacy / row / "stdout.txt", 6)
        generated_history = numeric_rows(generated / row / "stdout.txt", 6)
        scientific_equal = (
            len(legacy_history) == len(generated_history)
            and all(left[:6] == right[:6] for left, right in zip(legacy_history, generated_history))
        )
        boolean_check(
            checks,
            f"{row}.history_scientific_columns",
            scientific_equal,
            {
                "columns": ["time", "relative_volume", "phase_marker", "center", "velocity", "dt"],
                "legacy_rows": len(legacy_history),
                "generated_rows": len(generated_history),
                "excluded_columns": "Basilisk wall-time/performance diagnostics",
            },
        )
        exact_file(
            checks,
            f"{row}.terminal_interface_and_provider_log",
            legacy / row / "log",
            generated / row / "log",
        )

    stationary_layout = {
        "clsvof": ("clsvof_native", "clsvof"),
        "nn": ("nn_cell_offset", "nn"),
    }
    for method, (legacy_method, generated_method) in stationary_layout.items():
        row = f"stationary_{method}"
        legacy_dir = legacy / row / legacy_method
        generated_dir = generated / row / generated_method
        exact_file(
            checks,
            f"{row}.trajectory",
            legacy_dir / "La-12000-6",
            generated_dir / "La-12000-6",
        )
        legacy_log = legacy_dir / "log"
        generated_log = generated_dir / "log"
        boolean_check(
            checks,
            f"{row}.provider_stats",
            provider_stats(legacy_log) == provider_stats(generated_log),
            {
                "legacy": provider_stats(legacy_log),
                "generated": provider_stats(generated_log),
            },
        )
        old_terminal = terminal_row(legacy_log)
        new_terminal = terminal_row(generated_log)
        boolean_check(
            checks,
            f"{row}.terminal_identity_and_velocity",
            old_terminal[:3] == new_terminal[:3],
            {
                "fields": ["level", "laplace", "u_star"],
                "legacy": old_terminal[:3],
                "generated": new_terminal[:3],
            },
        )
        boolean_check(
            checks,
            f"{row}.termination_evidence",
            (generated_dir / "termination.csv").is_file(),
            str(generated_dir / "termination.csv"),
        )

    stationary_source = ROOT / "generate/stationary_bubble/src/stationary-clsvof.c"
    source_text = stationary_source.read_text(encoding="utf-8")
    correction_markers = [
        "bubble[] = 1. - f[];",
        "curvature (bubble, kappa);",
        "foreach (reduction(max:ekmax))",
        'fopen ("termination.csv", "w")',
    ]
    boolean_check(
        checks,
        "stationary.documented_terminal_observable_correction",
        all(marker in source_text for marker in correction_markers),
        {
            "source": str(stationary_source.relative_to(ROOT)),
            "source_sha256": sha256(stationary_source),
            "markers": correction_markers,
            "allowed_difference": "shape-error and curvature terminal fields only",
        },
    )

    failed = [check for check in checks if check["status"] != "PASS"]
    report = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "N64 imax=3 single-thread smoke migration gate",
        "status": "PASS_WITH_DOCUMENTED_DIAGNOSTIC_CORRECTION" if not failed else "FAIL",
        "physics_equivalence": not failed,
        "strict_all_output_byte_equivalence": False,
        "runtime_fields_excluded": True,
        "stationary_terminal_exception": {
            "reason": "known correction from outside-liquid f to official-compatible bubble=1-f diagnostics",
            "solver_trajectory_changed": False,
            "legacy_terminal_fields": "shape error and curvature values are known invalid",
        },
        "checks": checks,
        "failed_checks": [check["name"] for check in failed],
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
