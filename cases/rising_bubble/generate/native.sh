#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
redistance_root="$repo_root/cases/_shared/nondefault_redistance"

imax=3
resolution=64
benchmark_case=1
purpose=smoke
output=""
dry_run=0
threads="${OMP_NUM_THREADS:-1}"

usage() {
  printf '%s\n' \
    "usage: $0 --case 1|2 [--imax 0..5] [--resolution 64|128|256|512]" \
    "          [--smoke|--formal] [--output PATH] [--dry-run]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --case) benchmark_case="${2:?missing value for --case}"; shift 2 ;;
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

case "$benchmark_case" in 1|2) ;; *)
  printf 'error: --case must be 1 or 2\n' >&2; exit 2;; esac
case "$imax" in 0|1|2|3|4|5) ;; *)
  printf 'error: --imax must be an integer from 0 through 5\n' >&2; exit 2;; esac
case "$resolution" in
  64) level=6 ;; 128) level=7 ;; 256) level=8 ;; 512) level=9 ;;
  *) printf 'error: --resolution must be one of 64,128,256,512\n' >&2; exit 2 ;;
esac
case "$threads" in ''|*[!0-9]*|0)
  printf 'error: OMP_NUM_THREADS must be a positive integer\n' >&2; exit 2;; esac

benchmark="rising_case${benchmark_case}"
benchmark_case_name="hysing_case_${benchmark_case}"
case_compile_flags=()
openmp_flags=()
if [ "$benchmark_case" -eq 2 ]; then
  case_compile_flags+=("-DCASE2=1")
fi
if [ "$threads" -gt 1 ]; then
  openmp_flags+=("-fopenmp")
fi

if [ -z "$output" ]; then
  if [ "$purpose" = smoke ]; then
    output="$repo_root/tem/rising_bubble/case${benchmark_case}/native/try_$(date -u +%Y%m%dT%H%M%SZ)_imax${imax}_N${resolution}"
  else
    output="$repo_root/dataset/rising_bubble/case${benchmark_case}/native_redistance/imax_${imax}/N$(printf '%04d' "$resolution")"
  fi
fi

if [ "$dry_run" -eq 1 ]; then
  printf '%s\n' "$output"
  printf 'benchmark=%s\n' "$benchmark"
  printf 'benchmark_case=%s\n' "$benchmark_case_name"
  printf 'case2_flag=%s\n' "$([ "$benchmark_case" -eq 2 ] && printf '%s' '-DCASE2=1' || true)"
  exit 0
fi
if [ -e "$output" ]; then printf 'error: output already exists: %s\n' "$output" >&2; exit 1; fi

output_parent="$(dirname "$output")"
output_name="$(basename "$output")"
staging="$output_parent/.${output_name}.staging.$$"
work="$repo_root/tem/rising_bubble/case${benchmark_case}/_work/${output_name}.$$"
mkdir -p "$work" "$staging"

cleanup_failed() {
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'failed staging retained at %s; work retained at %s\n' "$staging" "$work" >&2
  fi
  exit "$status"
}
trap cleanup_failed EXIT

cp "$repo_root/basilisk/src/test/rising.c" "$work/rising-clsvof.c"
cp "$repo_root/basilisk/src/integral.h" "$work/integral.h"
python3 "$redistance_root/src/make_redistance_overlay.py" \
  "$repo_root/basilisk/src/two-phase-clsvof.h" "$work/two-phase-clsvof.h" \
  --imax "$imax" --no-metrics --provenance "$work/redistance_overlay.json"

(
  cd "$work"
  "$repo_root/basilisk/src/qcc" -O2 -DLEVELSET=1 -DCLSVOF=1 -DLEVEL="$level" \
    ${case_compile_flags[@]+"${case_compile_flags[@]}"} \
    ${openmp_flags[@]+"${openmp_flags[@]}"} \
    rising-clsvof.c -o rising-clsvof -lm > compile.stdout 2> compile.stderr
  ./rising-clsvof > stdout.txt 2> log
)

python3 - "$work/stdout.txt" <<'PY'
import math
import sys
from pathlib import Path

rows = []
for line in Path(sys.argv[1]).read_text().splitlines():
    fields = line.split()
    if len(fields) < 5:
        continue
    try:
        values = [float(value) for value in fields[:5]]
    except ValueError:
        continue
    if all(math.isfinite(value) for value in values):
        rows.append(values)
if not rows or abs(rows[-1][0] - 3.0) > 1e-9:
    raise SystemExit("rising output did not reach t=3")
PY

cp "$work/log" "$work/stdout.txt" "$work/compile.stdout" "$work/compile.stderr" \
  "$work/rising-clsvof.c" "$work/integral.h" "$work/two-phase-clsvof.h" \
  "$work/redistance_overlay.json" "$staging/"

python3 - "$staging/manifest.json" \
  "$repo_root/basilisk/src/test/rising.c" \
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

manifest, stock_case, stock_integral, stock_two_phase = sys.argv[1:]
payload = {
    "schema_version": 1,
    "case": "rising_bubble", "benchmark": "$benchmark",
    "benchmark_case": "$benchmark_case_name",
    "method": "clsvof_native", "purpose": "$purpose", "imax": int("$imax"),
    "level": int("$level"), "resolution": int("$resolution"),
    "actual_grid": "${resolution}x$((resolution / 4))", "model": None,
    "generator": "cases/rising_bubble/generate/native.sh",
    "openmp_threads": int("$threads"),
    "compile_defines": ["LEVELSET=1", "CLSVOF=1", "LEVEL=$level"] +
        (["CASE2=1"] if int("$benchmark_case") == 2 else []),
    "artifacts": {
        "stock_case_sha256": sha256(stock_case),
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
