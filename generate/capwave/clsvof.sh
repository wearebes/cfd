#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
shared_root="$repo_root/generate/_shared"
redistance_root="$shared_root/nondefault_redistance"
manifest_tool="$shared_root/run_manifest.py"

imax=3
resolution=64
purpose=smoke
output=""
dry_run=0
compile_only=0
threads=1

usage() {
  printf '%s\n' \
    "usage: $0 [--imax 0..5] [--resolution 64|128|256|512]" \
    "          [--smoke|--formal] --output PATH [--threads N]" \
    "          [--dry-run] [--compile-only]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --imax) imax="${2:?missing value for --imax}"; shift 2 ;;
    --resolution) resolution="${2:?missing value for --resolution}"; shift 2 ;;
    --smoke) purpose=smoke; shift ;;
    --formal) purpose=formal; shift ;;
    --output) output="${2:?missing value for --output}"; shift 2 ;;
    --threads) threads="${2:?missing value for --threads}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --compile-only) compile_only=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'error: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$imax" in 0|1|2|3|4|5) ;; *)
  printf 'error: --imax must be an integer from 0 through 5\n' >&2; exit 2;; esac
case "$resolution" in 64|128|256|512) ;; *)
  printf 'error: --resolution must be one of 64,128,256,512\n' >&2; exit 2;; esac
case "$threads" in ''|*[!0-9]*|0)
  printf 'error: --threads must be a positive integer\n' >&2; exit 2;; esac
if [ -z "$output" ]; then
  printf 'error: --output is required\n' >&2; usage >&2; exit 2
fi

output_parent="$(dirname "$output")"
if [ "$dry_run" -eq 0 ]; then mkdir -p "$output_parent"; fi
if [ -d "$output_parent" ]; then output="$(cd "$output_parent" && pwd)/$(basename "$output")"; fi
if [ "$dry_run" -eq 0 ] && [ -e "$output" ]; then
  printf 'error: output already exists: %s\n' "$output" >&2; exit 1
fi

output_name="$(basename "$output")"
if [ "$dry_run" -eq 1 ]; then
  work="$(mktemp -d "${TMPDIR:-/tmp}/cfd-capwave-clsvof-plan.XXXXXX")"
else
  work="$repo_root/tem/capwave/_work/${output_name}.$$"
  mkdir -p "$output/source_snapshot" "$work/checkpoints"
fi

cleanup() {
  status=$?
  trap - EXIT
  if [ "$dry_run" -eq 1 ]; then
    case "$work" in "${TMPDIR:-/tmp}"/cfd-capwave-clsvof-plan.*) rm -rf "$work" ;; esac
  elif [ "$status" -ne 0 ] && [ -f "$output/manifest.json" ]; then
    python3 "$manifest_tool" fail --manifest "$output/manifest.json" \
      --error "runner exited with status $status" || true
    printf 'failed output retained at %s; work retained at %s\n' "$output" "$work" >&2
  fi
  exit "$status"
}
trap cleanup EXIT

python3 "$script_dir/src/make_single_resolution_case.py" \
  "$repo_root/basilisk/src/test/capwave-clsvof.c" "$work/capwave-clsvof.c" \
  --resolution "$resolution"
python3 "$shared_root/make_checkpoint_overlay.py" \
  "$work/capwave-clsvof.c" "$work/capwave-clsvof.c" \
  --case capwave --provenance "$work/checkpoint_overlay.json"
cp "$repo_root/basilisk/src/test/prosperetti.h" "$work/prosperetti.h"
cp "$repo_root/basilisk/src/integral.h" "$work/integral.h"
python3 "$redistance_root/src/make_redistance_overlay.py" \
  "$repo_root/basilisk/src/two-phase-clsvof.h" "$work/two-phase-clsvof.h" \
  --imax "$imax" --no-metrics --provenance "$work/redistance_overlay.json"

compile_cmd=("$repo_root/basilisk/src/qcc" -O2 -DCLSVOF=1)
if [ "$threads" -gt 1 ]; then compile_cmd+=("-fopenmp"); fi
compile_cmd+=(capwave-clsvof.c -o capwave-clsvof -lm)
run_cmd=(./capwave-clsvof)
if [ "$compile_only" -eq 1 ]; then run_cmd=(); fi

plan_args=(
  --repo-root "$repo_root"
  --case capwave --benchmark capwave --method clsvof --purpose "$purpose"
  --output "$output"
  --generator "$script_dir/clsvof.sh"
  --generator-logical generate/capwave/clsvof.sh
  --parameter "resolution=$resolution"
  --parameter "imax=$imax"
  --parameter model=null
  --parameter "openmp_threads=$threads"
  --parameter "compile_only=$compile_only"
  --source "stock_case=basilisk/src/test/capwave-clsvof.c::$repo_root/basilisk/src/test/capwave-clsvof.c"
  --source "compiled_case=source_snapshot/capwave-clsvof.c::$work/capwave-clsvof.c"
  --source "compiled_integral=source_snapshot/integral.h::$work/integral.h"
  --source "compiled_two_phase=source_snapshot/two-phase-clsvof.h::$work/two-phase-clsvof.h"
  --source "prosperetti=source_snapshot/prosperetti.h::$work/prosperetti.h"
  --source "qcc=basilisk/src/qcc::$repo_root/basilisk/src/qcc"
  --source "checkpoint_overlay=source_snapshot/checkpoint_overlay.json::$work/checkpoint_overlay.json"
  --source "redistance_overlay=source_snapshot/redistance_overlay.json::$work/redistance_overlay.json"
  --compile-cwd '$WORK' --run-cwd '$WORK'
  --run-stdout stdout.txt --run-stderr log
)
for arg in "${compile_cmd[@]}"; do plan_args+=("--compile-arg=$arg"); done
if [ "$compile_only" -eq 0 ]; then
  for arg in "${run_cmd[@]}"; do plan_args+=("--run-arg=$arg"); done
fi

if [ "$dry_run" -eq 1 ]; then
  python3 "$manifest_tool" dry-run "${plan_args[@]}"
  exit 0
fi

cp "$work/capwave-clsvof.c" "$work/integral.h" "$work/two-phase-clsvof.h" \
  "$work/prosperetti.h" "$work/checkpoint_overlay.json" "$work/redistance_overlay.json" \
  "$output/source_snapshot/"
python3 "$manifest_tool" start "${plan_args[@]}" --manifest "$output/manifest.json"

SECONDS=0
(
  cd "$work"
  "${compile_cmd[@]}" > compile.stdout 2> compile.stderr
)
cp "$work/compile.stdout" "$work/compile.stderr" "$output/"
if [ "$compile_only" -eq 0 ]; then
  (
    cd "$work"
    "${run_cmd[@]}" > stdout.txt 2> log
  )
  test -s "$work/wave-$resolution"
  cp "$work/wave-$resolution" "$work/log" "$work/stdout.txt" \
    "$work/prosperetti.h" "$work/checkpoint_index.csv" "$output/"
  cp -R "$work/checkpoints" "$output/"
  python3 "$shared_root/build_scientific_artifacts.py" "$output"
fi
elapsed="$SECONDS"
python3 "$manifest_tool" complete "${plan_args[@]}" \
  --manifest "$output/manifest.json" --elapsed-seconds "$elapsed"

trap - EXIT
printf '%s\n' "$output"
printf 'work: %s\n' "$work" >&2
