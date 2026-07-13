#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
case_root="$repo_root/cases/stationary_bubble"
redistance_root="$repo_root/cases/_shared/nondefault_redistance"

imax=3
level=6
purpose=smoke
tau_max=0.01
output=""
dry_run=0
threads="${OMP_NUM_THREADS:-1}"

usage() {
  printf '%s\n' \
    "usage: $0 [--imax 0..5] [--level 6|7|8] [--smoke|--formal]" \
    "          [--tau-max VALUE] [--output PATH] [--dry-run]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --imax) imax="${2:?missing value for --imax}"; shift 2 ;;
    --level) level="${2:?missing value for --level}"; shift 2 ;;
    --smoke) purpose=smoke; shift ;;
    --formal) purpose=formal; tau_max=1.0; shift ;;
    --tau-max) tau_max="${2:?missing value for --tau-max}"; shift 2 ;;
    --output) output="${2:?missing value for --output}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'error: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$imax" in 0|1|2|3|4|5) ;; *)
  printf 'error: --imax must be an integer from 0 through 5\n' >&2; exit 2;; esac
case "$level" in 6|7|8) ;; *)
  printf 'error: --level must be one of 6,7,8; stationary N512 is outside the formal matrix\n' >&2
  exit 2;; esac
case "$threads" in ''|*[!0-9]*|0)
  printf 'error: OMP_NUM_THREADS must be a positive integer\n' >&2; exit 2;; esac
openmp_flags=()
if [ "$threads" -gt 1 ]; then openmp_flags+=("-fopenmp"); fi
if [ "$purpose" = formal ] && [ "$tau_max" != 1.0 ] && [ "$tau_max" != 1 ]; then
  printf 'error: formal stationary data must use --tau-max 1.0\n' >&2; exit 2
fi

resolution=$((1 << level))
if [ -z "$output" ]; then
  if [ "$purpose" = smoke ]; then
    output="$repo_root/tem/stationary_bubble/native/try_$(date -u +%Y%m%dT%H%M%SZ)_imax${imax}_N${resolution}"
  else
    output="$repo_root/dataset/stationary_bubble/native_redistance/imax_${imax}/N$(printf '%04d' "$resolution")"
  fi
fi

if [ "$dry_run" -eq 1 ]; then printf '%s\n' "$output"; exit 0; fi
if [ -e "$output" ]; then printf 'error: output already exists: %s\n' "$output" >&2; exit 1; fi

output_parent="$(dirname "$output")"
output_name="$(basename "$output")"
staging="$output_parent/.${output_name}.staging.$$"
work="$repo_root/tem/stationary_bubble/_work/${output_name}.$$"
result="$staging/clsvof_native"
mkdir -p "$work" "$result"

cleanup_failed() {
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'failed staging retained at %s; work retained at %s\n' "$staging" "$work" >&2
  fi
  exit "$status"
}
trap cleanup_failed EXIT

cp "$case_root/src/stationary-clsvof.c" "$work/stationary-clsvof.c"
cp "$repo_root/basilisk/src/integral.h" "$work/integral.h"
python3 "$redistance_root/src/make_redistance_overlay.py" \
  "$repo_root/basilisk/src/two-phase-clsvof.h" "$work/two-phase-clsvof.h" \
  --imax "$imax" --no-metrics --provenance "$work/redistance_overlay.json"

(
  cd "$work"
  "$repo_root/basilisk/src/qcc" \
    -O2 ${openmp_flags[@]+"${openmp_flags[@]}"} \
    "-DSTATIONARY_LEVEL=$level" "-DSTATIONARY_TAU_MAX=$tau_max" \
    stationary-clsvof.c -o stationary-clsvof -lm > compile.stdout 2> compile.stderr
  ./stationary-clsvof > stdout.txt 2> log
)

test -s "$work/La-12000-$level"
cp "$work/La-12000-$level" "$work/log" "$work/stdout.txt" \
  "$work/compile.stdout" "$work/compile.stderr" "$work/integral.h" \
  "$work/two-phase-clsvof.h" "$work/redistance_overlay.json" "$result/"
python3 "$case_root/src/summarize_smoke.py" "$staging"

python3 - "$staging/manifest.json" \
  "$case_root/src/stationary-clsvof.c" \
  "$repo_root/basilisk/src/integral.h" \
  "$repo_root/basilisk/src/two-phase-clsvof.h" <<PY
import hashlib
import json
import sys
from pathlib import Path

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

manifest, source_case, stock_integral, stock_two_phase = sys.argv[1:]
payload = {
    "schema_version": 1,
    "case": "stationary_bubble", "benchmark": "stationary_bubble",
    "method": "clsvof_native", "purpose": "$purpose", "imax": int("$imax"),
    "level": int("$level"), "resolution": int("$resolution"),
    "tau_max": float("$tau_max"), "model": None,
    "generator": "cases/stationary_bubble/generate/native.sh",
    "openmp_threads": int("$threads"),
    "artifacts": {
        "case_sha256": sha256(source_case),
        "cell_curvature_sha256": None,
        "weights_sha256": None,
        "stock_integral_sha256": sha256(stock_integral),
        "stock_two_phase_clsvof_sha256": sha256(stock_two_phase),
    },
}
Path(manifest).write_text(json.dumps(payload, indent=2) + "\n")
PY

mkdir -p "$output_parent"
mv "$staging" "$output"
trap - EXIT
printf '%s\n' "$output"
printf 'work: %s\n' "$work" >&2
