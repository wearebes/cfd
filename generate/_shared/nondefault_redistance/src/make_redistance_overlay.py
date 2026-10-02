#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TARGET = "  redistance (d, imax = 3, phixxmin = HUGE);"
REDISTANCE_INCLUDE = '#include "redistance.h"'
METRICS_INCLUDE = '#include "redistance_matrix_metrics.h"'
STEPS_STATS_INCLUDE = '#include "redistance_steps_stats.h"'
ALLOWED_IMAX = (0, 1, 2, 3, 4, 5, 10, 15, 20)
ALLOWED_STEPS = (0, 1, 2, 3, 4, 5, 10)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_overlay_text(
    source: str,
    imax: int | None = None,
    metrics: bool = True,
    *,
    steps: int | None = None,
) -> str:
    if (imax is None) == (steps is None):
        raise ValueError("exactly one of imax or steps is required")
    if source.count(TARGET) != 1:
        raise ValueError("expected exactly one stock CLSVOF redistance call")
    if source.count(REDISTANCE_INCLUDE) != 1:
        raise ValueError("expected exactly one redistance.h include")

    if steps is not None:
        if steps not in ALLOWED_STEPS:
            raise ValueError(f"steps must be one of {ALLOWED_STEPS}")
        include_block = (
            f"{REDISTANCE_INCLUDE}\n"
            f"\n#define REDISTANCE_FIXED_STEPS {steps}\n"
            f"{STEPS_STATS_INCLUDE}"
        )
        replacement = f"""  int redistance_fixed_steps_returned =
    redistance (d, steps = {steps}, phixxmin = HUGE);
  redistance_fixed_steps_record (redistance_fixed_steps_returned);"""
        output = source.replace(REDISTANCE_INCLUDE, include_block, 1)
        return output.replace(TARGET, replacement, 1)

    assert imax is not None
    if imax not in ALLOWED_IMAX:
        raise ValueError(f"imax must be one of {ALLOWED_IMAX}")

    if not metrics:
        return source.replace(
            TARGET,
            f"  redistance (d, imax = {imax}, phixxmin = HUGE);",
            1,
        )

    include_block = (
        f"{REDISTANCE_INCLUDE}\n"
        f"\n#define REDIST_MATRIX_IMAX {imax}\n"
        f"{METRICS_INCLUDE}"
    )
    replacement = f"""  bool redistance_matrix_sample = redistance_matrix_should_sample (i, t);
  scalar redistance_matrix_before[];
  if (redistance_matrix_sample) {{
    foreach()
      redistance_matrix_before[] = d[];
    boundary ({{redistance_matrix_before}});
    redistance_matrix_measure ("pre", d, redistance_matrix_before,
                               0, -1, i, t, 1.5);
    redistance_matrix_measure ("pre", d, redistance_matrix_before,
                               0, -1, i, t, 3.0);
  }}

  int redistance_matrix_returned =
    redistance (d, imax = {imax}, phixxmin = HUGE);
  redistance_matrix_record_return (redistance_matrix_returned, i, t);

  if (redistance_matrix_sample) {{
    boundary ({{d}});
    redistance_matrix_measure ("post", d, redistance_matrix_before,
                               1, redistance_matrix_returned, i, t, 1.5);
    redistance_matrix_measure ("post", d, redistance_matrix_before,
                               1, redistance_matrix_returned, i, t, 3.0);
  }}"""

    output = source.replace(REDISTANCE_INCLUDE, include_block, 1)
    output = output.replace(TARGET, replacement, 1)
    return output


def build_provenance(
    source: str,
    output: str,
    imax: int | None = None,
    metrics: bool = True,
    *,
    steps: int | None = None,
) -> dict[str, object]:
    if (imax is None) == (steps is None):
        raise ValueError("exactly one of imax or steps is required")
    return {
        "imax": imax,
        "steps": steps,
        "redistance_policy": "fixed_steps" if steps is not None else "imax_limit",
        "target": TARGET.strip(),
        "target_count": source.count(TARGET),
        "source_sha256": sha256_text(source),
        "generated_sha256": sha256_text(output),
        "metrics_include": METRICS_INCLUDE,
        "metrics_enabled": metrics if steps is None else False,
        "steps_stats_include": STEPS_STATS_INCLUDE if steps is not None else None,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    policy = parser.add_mutually_exclusive_group(required=True)
    policy.add_argument("--imax", type=int)
    policy.add_argument("--steps", type=int)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--no-metrics", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source.read_text(encoding="utf-8")
    metrics = not args.no_metrics
    output = build_overlay_text(
        source, args.imax, metrics=metrics, steps=args.steps
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    if args.provenance:
        args.provenance.parent.mkdir(parents=True, exist_ok=True)
        args.provenance.write_text(
            json.dumps(
                build_provenance(
                    source,
                    output,
                    args.imax,
                    metrics=metrics,
                    steps=args.steps,
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
