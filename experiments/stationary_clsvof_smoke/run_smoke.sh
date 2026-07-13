#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
qcc="$repo_root/basilisk/src/qcc"
source_case="$script_dir/stationary-clsvof.c"
source_integral="$repo_root/basilisk/src/integral.h"
result_root="$script_dir/results/$(date -u +%Y%m%dT%H%M%SZ)"
work_root="$script_dir/work/$(basename "$result_root")"

sha256_of() {
  shasum -a 256 "$1" | awk '{print $1}'
}

run_native() {
  local work="$work_root/clsvof_native"
  local out="$result_root/clsvof_native"
  mkdir -p "$work" "$out"
  cp "$source_case" "$work/stationary-clsvof.c"
  (
    cd "$work"
    "$qcc" stationary-clsvof.c -o stationary-clsvof -lm
    ./stationary-clsvof > stdout.txt 2> log
  )
  cp "$work/La-12000-6" "$work/log" "$work/stdout.txt" "$out/"
}

run_contour_analytic() {
  local work="$work_root/clsvof_contour_analytic"
  local out="$result_root/clsvof_contour_analytic"
  mkdir -p "$work" "$out"
  cp "$source_case" "$work/stationary-clsvof.c"
  cp "$script_dir/include/stationary_contour_curvature.h" "$work/"
  python3 "$script_dir/make_overlay_integral.py" "$source_integral" "$work/integral.h"
  (
    cd "$work"
    "$qcc" stationary-clsvof.c -o stationary-clsvof -lm
    ./stationary-clsvof > stdout.txt 2> log
  )
  cp "$work/La-12000-6" "$work/log" "$work/stdout.txt" "$work/integral.h" "$out/"
}

mkdir -p "$result_root" "$work_root"
run_native
run_contour_analytic
python3 "$script_dir/summarize_smoke.py" "$result_root"

cat > "$result_root/manifest.json" <<JSON
{
  "benchmark": "official-derived stationary bubble CLSVOF smoke",
  "resolution": 64,
  "laplace": 12000,
  "diameter": 0.8,
  "radius": 0.4,
  "signed_distance": "d = r - R",
  "redistance": "stock two-phase-clsvof.h: weight=0.1, imax=3, phixxmin=HUGE",
  "modes": {
    "clsvof_native": "stock integral.h and distance_curvature(point,d)",
    "clsvof_contour_analytic": "local integral.h overlay: ki = 1/(R + d)"
  },
  "output_contract": "official spurious.c time series: tau, Umax*sqrt(D), delta_f",
  "source_sha256": {
    "case": "$(sha256_of "$source_case")",
    "stock_integral": "$(sha256_of "$source_integral")",
    "two_phase_clsvof": "$(sha256_of "$repo_root/basilisk/src/two-phase-clsvof.h")"
  },
  "compile": "$(basename "$qcc") stationary-clsvof.c -o stationary-clsvof -lm"
}
JSON

echo "$result_root"
