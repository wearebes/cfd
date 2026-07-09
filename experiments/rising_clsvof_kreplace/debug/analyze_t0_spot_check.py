#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path


ANALYTIC_KAPPA = 4.0  # 1/radius, radius = 0.25, exact for the initial circle
SIGN_AGREEMENT_MIN = 0.95
MAGNITUDE_FACTOR = 2.0


def read_rows(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 6 or parts[0] != "T0SPOT":
            continue
        _, x, y, ki_native, ki_nn, clamped = parts
        rows.append(
            {
                "x": float(x),
                "y": float(y),
                "ki_native": float(ki_native),
                "ki_nn": float(ki_nn),
                "clamped": clamped == "1",
            }
        )
    return rows


def analyze(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0, "pass": False, "reason": "no T0SPOT rows found"}

    def sign(v: float) -> int:
        return (v > 0) - (v < 0)

    agree = sum(1 for r in rows if sign(r["ki_native"]) == sign(r["ki_nn"]))
    sign_agreement = agree / n

    abs_nn = [abs(r["ki_nn"]) for r in rows]
    median_abs_nn = statistics.median(abs_nn)
    magnitude_ratio = median_abs_nn / ANALYTIC_KAPPA

    clamp_hits = sum(1 for r in rows if r["clamped"])

    checks = {
        "sign_agreement": {
            "value": sign_agreement,
            "threshold": f">= {SIGN_AGREEMENT_MIN}",
            "passed": sign_agreement >= SIGN_AGREEMENT_MIN,
        },
        "magnitude": {
            "value": median_abs_nn,
            "threshold": f"within factor {MAGNITUDE_FACTOR} of analytic kappa={ANALYTIC_KAPPA} "
            f"(i.e. in [{ANALYTIC_KAPPA / MAGNITUDE_FACTOR}, {ANALYTIC_KAPPA * MAGNITUDE_FACTOR}])",
            "passed": (ANALYTIC_KAPPA / MAGNITUDE_FACTOR) <= median_abs_nn <= (ANALYTIC_KAPPA * MAGNITUDE_FACTOR),
        },
        "zero_clamp_hits": {
            "value": clamp_hits,
            "threshold": "== 0",
            "passed": clamp_hits == 0,
        },
    }

    return {
        "n": n,
        "sign_agreement": sign_agreement,
        "median_abs_ki_nn": median_abs_nn,
        "magnitude_ratio_to_analytic": magnitude_ratio,
        "clamp_hits": clamp_hits,
        "checks": checks,
        "pass": all(c["passed"] for c in checks.values()),
    }


def format_report(result: dict) -> str:
    if result["n"] == 0:
        return f"T0 SPOT CHECK: FAIL ({result['reason']})"

    lines = [
        f"T0 SPOT CHECK ({result['n']} interfacial-cell samples at t=0)",
        f"  sign agreement:      {result['sign_agreement']:.4f} "
        f"({'PASS' if result['checks']['sign_agreement']['passed'] else 'FAIL'}, need >= {SIGN_AGREEMENT_MIN})",
        f"  median |ki_nn|:      {result['median_abs_ki_nn']:.6g} "
        f"({'PASS' if result['checks']['magnitude']['passed'] else 'FAIL'}, "
        f"ratio to analytic kappa=4 is {result['magnitude_ratio_to_analytic']:.4f}, need in [0.5, 2.0])",
        f"  clamp hits:          {result['clamp_hits']} "
        f"({'PASS' if result['checks']['zero_clamp_hits']['passed'] else 'FAIL'}, need 0)",
        f"OVERALL: {'PASS' if result['pass'] else 'FAIL'}",
    ]
    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("t0_spot_check_txt", type=Path)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    rows = read_rows(args.t0_spot_check_txt)
    result = analyze(rows)
    print(format_report(result))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
