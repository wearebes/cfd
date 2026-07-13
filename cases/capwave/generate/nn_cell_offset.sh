#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
case_root="$repo_root/cases/capwave"
shared_root="$repo_root/cases/_shared/nn_cell_curvature"
redistance_root="$repo_root/cases/_shared/nondefault_redistance"

imax=3
resolution=64
purpose=smoke
output=""
dry_run=0
threads="${OMP_NUM_THREADS:-1}"

usage() {
  printf '%s\n' \
    "usage: $0 [--imax 0..5] [--resolution 64|128|256|512]" \
    "          [--smoke|--formal] [--output PATH] [--dry-run]" \
    "" \
    "smoke output: tem/capwave/nn_cell_offset/try_*" \
    "formal imax=3: dataset/capwave/nn_cell_offset_matched/N####" \
    "formal other:  dataset/capwave/nondefault_redistance/imax_N/N####"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --imax) imax="${2:?missing value for --imax}"; shift 2 ;;
    --resolution) resolution="${2:?missing value for --resolution}"; shift 2 ;;
    --smoke) purpose=smoke; shift ;;
    --formal) purpose=formal; shift ;;
    --output) output="${2:?missing value for --output}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'error: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$imax" in 0|1|2|3|4|5) ;; *)
  printf 'error: --imax must be an integer from 0 through 5\n' >&2; exit 2;; esac
case "$resolution" in 64|128|256|512) ;; *)
  printf 'error: --resolution must be one of 64,128,256,512\n' >&2; exit 2;; esac
case "$threads" in ''|*[!0-9]*|0)
  printf 'error: OMP_NUM_THREADS must be a positive integer\n' >&2; exit 2;; esac
openmp_flags=()
if [ "$threads" -gt 1 ]; then openmp_flags+=("-fopenmp"); fi

model_name="baseline_${resolution}_hgradient"
model_dir="$repo_root/dataset/model/c_exports/$model_name"
if [ ! -f "$model_dir/nn_weights.h" ]; then
  printf 'error: missing model export %s\n' "$model_dir/nn_weights.h" >&2
  exit 1
fi

if [ -z "$output" ]; then
  if [ "$purpose" = smoke ]; then
    output="$repo_root/tem/capwave/nn_cell_offset/try_$(date -u +%Y%m%dT%H%M%SZ)_imax${imax}_N${resolution}"
  elif [ "$imax" -eq 3 ]; then
    output="$repo_root/dataset/capwave/nn_cell_offset_matched/N$(printf '%04d' "$resolution")"
  else
    output="$repo_root/dataset/capwave/nondefault_redistance/imax_${imax}/N$(printf '%04d' "$resolution")"
  fi
fi

if [ "$dry_run" -eq 1 ]; then printf '%s\n' "$output"; exit 0; fi
if [ -e "$output" ]; then printf 'error: output already exists: %s\n' "$output" >&2; exit 1; fi

output_parent="$(dirname "$output")"
output_name="$(basename "$output")"
staging="$output_parent/.${output_name}.staging.$$"
work="$repo_root/tem/capwave/_work/${output_name}.$$"
mkdir -p "$work" "$staging"

cleanup_failed() {
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'failed staging retained at %s; work retained at %s\n' "$staging" "$work" >&2
  fi
  exit "$status"
}
trap cleanup_failed EXIT

python3 "$case_root/src/make_single_resolution_case.py" \
  "$repo_root/basilisk/src/test/capwave-clsvof.c" "$work/capwave-clsvof.c" \
  --resolution "$resolution"
cp "$repo_root/basilisk/src/test/prosperetti.h" "$work/prosperetti.h"
cp "$shared_root/src/clsvof_nn_cell_curvature.h" "$work/"
cp "$shared_root/src/kappa_offset_stats.h" "$work/"
python3 "$shared_root/src/make_overlay_integral.py" \
  "$repo_root/basilisk/src/integral.h" "$work/integral.h"
python3 "$redistance_root/src/make_redistance_overlay.py" \
  "$repo_root/basilisk/src/two-phase-clsvof.h" "$work/two-phase-clsvof.h" \
  --imax "$imax" --no-metrics --provenance "$work/redistance_overlay.json"

(
  cd "$work"
  "$repo_root/basilisk/src/qcc" -O2 -DCLSVOF=1 \
    ${openmp_flags[@]+"${openmp_flags[@]}"} \
    -DKAPPA_OFFSET_CLAMP_FACTOR=1.0 -DKAPPA_OFFSET_PROBE_INTERVAL=0 \
    -disable-dimensions \
    -I"$shared_root/src" -I"$repo_root/tools/clsvof_model/include" -I"$model_dir" \
    capwave-clsvof.c -o capwave-clsvof -lm > compile.stdout 2> compile.stderr
  ./capwave-clsvof > stdout.txt 2> log
)

cp "$work/wave-$resolution" "$work/log" "$work/stdout.txt" \
  "$work/compile.stdout" "$work/compile.stderr" "$work/capwave-clsvof.c" \
  "$work/prosperetti.h" "$work/integral.h" "$work/two-phase-clsvof.h" \
  "$work/redistance_overlay.json" "$work/clsvof_nn_cell_curvature.h" \
  "$work/kappa_offset_stats.h" "$staging/"

python3 - "$staging/manifest.json" \
  "$repo_root/basilisk/src/test/capwave-clsvof.c" "$work/capwave-clsvof.c" \
  "$shared_root/src/clsvof_nn_cell_curvature.h" \
  "$shared_root/src/kappa_offset_stats.h" "$model_dir/nn_weights.h" \
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

manifest, stock_case, generated_case, cell_curvature, stats_header, weights, stock_integral, stock_two_phase = sys.argv[1:]
payload = {
    "schema_version": 1,
    "case": "capwave", "benchmark": "capwave",
    "method": "clsvof_nn_cell_offset", "purpose": "$purpose",
    "imax": int("$imax"), "resolution": int("$resolution"), "model": "$model_name",
    "generator": "cases/capwave/generate/nn_cell_offset.sh",
    "openmp_threads": int("$threads"),
    "artifacts": {
        "stock_case_sha256": sha256(stock_case),
        "generated_case_sha256": sha256(generated_case),
        "cell_curvature_sha256": sha256(cell_curvature),
        "stats_header_sha256": sha256(stats_header),
        "weights_sha256": sha256(weights),
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
