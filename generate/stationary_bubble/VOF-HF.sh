#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
qcc="${BASILISK_QCC:-$repo_root/basilisk/src/qcc}"
manifest_tool="$repo_root/generate/_shared/run_manifest.py"
artifact_builder="$repo_root/generate/_shared/build_scientific_artifacts.py"
host_builder="$script_dir/src/make_fixed_horizon_vof_host.py"
field_overlay="$repo_root/generate/_shared/append_field_snapshots.py"
field_header="$repo_root/generate/_shared/field_snapshots.h"
finalizer="$repo_root/generate/_shared/finalize_row.py"

resolution=64
purpose=smoke
output=""
dry_run=0
compile_only=0
threads=1
precompiled=""

usage() {
  printf '%s\n' \
    "usage: $0 [--resolution 32|64|128|256|512] [--smoke|--formal]" \
    "          --output PATH [--threads 1] [--dry-run] [--compile-only] [--precompiled PATH]"
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --resolution) resolution="${2:?missing value for --resolution}"; shift 2 ;;
    --smoke) purpose=smoke; shift ;;
    --formal) purpose=formal; shift ;;
    --output) output="${2:?missing value for --output}"; shift 2 ;;
    --threads) threads="${2:?missing value for --threads}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --compile-only) compile_only=1; shift ;;
    --precompiled) precompiled="${2:?missing value for --precompiled}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'error: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done
case "$resolution" in
  32) level=5 ;; 64) level=6 ;; 128) level=7 ;; 256) level=8 ;; 512) level=9 ;;
  *) printf 'error: invalid --resolution\n' >&2; exit 2 ;;
esac
case "$resolution" in
  32|64|128) grid_role=stock_native ;;
  256|512) grid_role=stock_compatible_extension ;;
esac
if [ "$threads" != 1 ]; then printf 'error: official stock reference is single-threaded\n' >&2; exit 2; fi
if [ -z "$output" ]; then printf 'error: --output is required\n' >&2; exit 2; fi
if [ "$purpose" = formal ] && [ "$compile_only" -eq 1 ] && [ "${CFD_CAMPAIGN_BUILD:-0}" != 1 ]; then
  printf 'error: --formal cannot be combined with --compile-only\n' >&2; exit 2
fi
if [ "$compile_only" -eq 1 ] && [ -n "$precompiled" ]; then printf 'error: incompatible build flags\n' >&2; exit 2; fi
if [ -n "$precompiled" ] && [ ! -f "$precompiled" ]; then printf 'error: missing precompiled executable\n' >&2; exit 2; fi
if [ -n "$precompiled" ] && [ "${CFD_CAMPAIGN_PRECOMPILED:-0}" != 1 ]; then printf 'error: --precompiled is reserved for the verified campaign scheduler\n' >&2; exit 2; fi
output_parent="$(dirname "$output")"
if [ "$dry_run" -eq 0 ]; then mkdir -p "$output_parent"; fi
if [ -d "$output_parent" ]; then output="$(cd "$output_parent" && pwd)/$(basename "$output")"; fi
if [ "$dry_run" -eq 0 ] && [ -e "$output" ]; then printf 'error: output already exists: %s\n' "$output" >&2; exit 1; fi
if [ "$dry_run" -eq 1 ]; then
  work="$(mktemp -d "${TMPDIR:-/tmp}/cfd-stationary-official-plan.XXXXXX")"
else
  work="$repo_root/tem/stationary_bubble/VOF-HF/_work/$(basename "$output").$$"
  mkdir -p "$output/source_snapshot" "$work"
fi
cleanup() {
  status=$?; trap - EXIT
  if [ "$dry_run" -eq 1 ]; then
    case "$work" in "${TMPDIR:-/tmp}"/cfd-stationary-official-plan.*) rm -rf "$work" ;; esac
  elif [ "$status" -ne 0 ] && [ -f "$output/manifest.json" ]; then
    python3 "$manifest_tool" fail --manifest "$output/manifest.json" --error "runner exited with status $status" || true
  fi
  exit "$status"
}
trap cleanup EXIT
cp "$repo_root/basilisk/src/test/spurious.c" "$work/spurious.c"
python3 "$host_builder" "$work/spurious.c" "$work/stationary-VOF-HF.c" \
  --provenance "$work/vof_hf_host_overlay.json"
python3 "$field_overlay" "$work/stationary-VOF-HF.c" --case stationary_bubble
cp "$field_header" "$work/field_snapshots.h"
compile_cmd=(
  "$qcc" -O2 "-DSINGLE_LEVEL=$level"
  stationary-VOF-HF.c -o stationary-VOF-HF -lm
)
run_cmd=(./stationary-VOF-HF)
if [ "$compile_only" -eq 1 ]; then run_cmd=(); fi
plan_args=(
  --repo-root "$repo_root" --case stationary_bubble --benchmark stationary_bubble
  --method VOF-HF --purpose "$purpose" --output "$output"
  --generator "$script_dir/VOF-HF.sh" --generator-logical generate/stationary_bubble/VOF-HF.sh
  --parameter "resolution=$resolution" --parameter "level=$level"
  --parameter imax=null --parameter model=null --parameter openmp_threads=1
  --parameter experiment_role=official_reference
  --parameter grid_strategy=adaptive
  --parameter "grid_role=$grid_role"
  --parameter tau_max=2
  --parameter "compile_only=$compile_only"
  --parameter "compile_reused=$([ -n "$precompiled" ] && printf true || printf false)"
  --run-env OMP_NUM_THREADS=1 --run-env OMP_DYNAMIC=false
  --source "stock_case=basilisk/src/test/spurious.c::$work/spurious.c"
  --source "compiled_case=source_snapshot/stationary-VOF-HF.c::$work/stationary-VOF-HF.c"
  --source "host_overlay=source_snapshot/vof_hf_host_overlay.json::$work/vof_hf_host_overlay.json"
  --source "field_snapshots=source_snapshot/field_snapshots.h::$work/field_snapshots.h"
  --source "qcc=toolchain/qcc::$qcc"
  --compile-cwd '$WORK' --run-cwd '$WORK' --run-stdout stdout.txt --run-stderr log
)
for arg in "${compile_cmd[@]}"; do plan_args+=("--compile-arg=$arg"); done
if [ -n "$precompiled" ]; then plan_args+=(--source "precompiled_executable=build/precompiled_executable::$precompiled"); fi
if [ "$compile_only" -eq 0 ]; then
  for arg in "${run_cmd[@]}"; do plan_args+=("--run-arg=$arg"); done
fi
if [ "$dry_run" -eq 1 ]; then python3 "$manifest_tool" dry-run "${plan_args[@]}"; exit 0; fi
cp "$work/spurious.c" "$work/stationary-VOF-HF.c" \
  "$work/vof_hf_host_overlay.json" "$work/field_snapshots.h" \
  "$output/source_snapshot/"
python3 "$manifest_tool" start "${plan_args[@]}" --manifest "$output/manifest.json"
SECONDS=0
if [ -n "$precompiled" ]; then
  cp "$precompiled" "$work/stationary-VOF-HF"
  printf 'campaign-built executable reused\n' > "$work/compile.stdout"; : > "$work/compile.stderr"
else
  (cd "$work"; "${compile_cmd[@]}" > compile.stdout 2> compile.stderr)
fi
cp "$work/compile.stdout" "$work/compile.stderr" "$output/"
if [ "$compile_only" -eq 1 ]; then cp "$work/stationary-VOF-HF" "$output/executable"; fi
if [ "$compile_only" -eq 0 ]; then
  (cd "$work"; OMP_NUM_THREADS=1 OMP_DYNAMIC=false "${run_cmd[@]}" > stdout.txt 2> log)
  test -s "$work/La-12000-$level"
  test -s "$work/log"
  test -s "$work/termination.csv"
  test -s "$work/milestones.csv"
  cp "$work/La-12000-$level" "$output/timeseries.dat"
  cp "$work/log" "$output/runtime_and_terminal.log"
  cp "$work/stdout.txt" "$output/solver.stdout.txt"
  cp "$work/termination.csv" "$output/termination.csv"
  cp "$work/milestones.csv" "$output/milestones.csv"
  test -s "$work/fields.csv"
  cp "$work/fields.csv" "$output/fields.csv"
  python3 "$artifact_builder" "$output"
  python3 "$finalizer" "$output"
fi
python3 "$manifest_tool" complete "${plan_args[@]}" \
  --manifest "$output/manifest.json" --elapsed-seconds "$SECONDS"
trap - EXIT
printf '%s\n' "$output"
case "$work" in "$repo_root"/tem/stationary_bubble/VOF-HF/_work/*) rm -rf "$work" ;; esac
