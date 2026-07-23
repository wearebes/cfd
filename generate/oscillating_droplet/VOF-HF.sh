#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
qcc="${BASILISK_QCC:-$repo_root/basilisk/src/qcc}"
manifest_tool="$repo_root/generate/_shared/run_manifest.py"
artifact_builder="$repo_root/generate/_shared/build_scientific_artifacts.py"
report_builder="$script_dir/VOF-HF/build_official_report.py"
field_overlay="$repo_root/generate/_shared/append_field_snapshots.py"
field_header="$repo_root/generate/_shared/field_snapshots.h"
finalizer="$repo_root/generate/_shared/finalize_row.py"

resolution=64
purpose=smoke
output=""
threads=1
grid=adaptive
dry_run=0
compile_only=0
precompiled=""

usage() {
  printf '%s\n' \
    "usage: $0 --resolution 32|64|128|256|512 [--grid adaptive|uniform] [--smoke|--formal]" \
    "          --output PATH [--threads 1] [--dry-run] [--compile-only] [--precompiled PATH]" \
    "" \
    "Runs only the Standard centered-solver VOF-HF branch at one requested grid."
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --resolution) resolution="${2:?missing value for --resolution}"; shift 2 ;;
    --smoke) purpose=smoke; shift ;;
    --formal) purpose=formal; shift ;;
    --output) output="${2:?missing value for --output}"; shift 2 ;;
    --threads) threads="${2:?missing value for --threads}"; shift 2 ;;
    --grid) grid="${2:?missing value for --grid}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --compile-only) compile_only=1; shift ;;
    --precompiled) precompiled="${2:?missing value for --precompiled}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'error: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$resolution" in
  32) level=5; cells_per_diameter=12.8 ;;
  64) level=6; cells_per_diameter=25.6 ;;
  128) level=7; cells_per_diameter=51.2 ;;
  256) level=8; cells_per_diameter=102.4 ;;
  512) level=9; cells_per_diameter=204.8 ;;
  *) printf 'error: invalid --resolution\n' >&2; exit 2 ;;
esac
case "$grid" in
  adaptive)
    experiment_role=official_reference
    case "$resolution" in
      32|64|128) grid_role=stock_native ;;
      256|512) grid_role=stock_compatible_extension ;;
    esac
    ;;
  uniform)
    experiment_role=matched_reference
    grid_role=uniform_matched
    ;;
  *) printf 'error: --grid must be adaptive or uniform\n' >&2; exit 2 ;;
esac
if [ "$threads" != 1 ]; then
  printf 'error: VOF-HF reference rows are single-threaded; use --threads 1\n' >&2
  exit 2
fi
if [ -z "$output" ]; then printf 'error: --output is required\n' >&2; exit 2; fi
if [ "$purpose" = formal ] && [ "$compile_only" -eq 1 ] && [ "${CFD_CAMPAIGN_BUILD:-0}" != 1 ]; then
  printf 'error: --formal cannot be combined with --compile-only\n' >&2; exit 2
fi
if [ "$compile_only" -eq 1 ] && [ -n "$precompiled" ]; then printf 'error: incompatible build flags\n' >&2; exit 2; fi
if [ -n "$precompiled" ] && [ ! -f "$precompiled" ]; then printf 'error: missing precompiled executable\n' >&2; exit 2; fi
if [ -n "$precompiled" ] && [ "${CFD_CAMPAIGN_PRECOMPILED:-0}" != 1 ]; then printf 'error: --precompiled is reserved for the verified campaign scheduler\n' >&2; exit 2; fi

output_parent="$(dirname "$output")"
if [ "$dry_run" -eq 0 ]; then mkdir -p "$output_parent"; fi
if [ -d "$output_parent" ]; then
  output="$(cd "$output_parent" && pwd)/$(basename "$output")"
fi
if [ "$dry_run" -eq 0 ] && [ -e "$output" ]; then
  printf 'error: output already exists: %s\n' "$output" >&2
  exit 1
fi

if [ "$dry_run" -eq 1 ]; then
  work="$(mktemp -d "${TMPDIR:-/tmp}/cfd-oscillating-VOF-HF-plan.XXXXXX")"
else
  work="$repo_root/tem/oscillating_droplet/VOF-HF/_work/N${resolution}.$$.work"
  mkdir -p "$output/source_snapshot" "$work"
fi

cleanup() {
  status=$?
  trap - EXIT
  if [ "$dry_run" -eq 1 ]; then
    case "$work" in "${TMPDIR:-/tmp}"/cfd-oscillating-VOF-HF-plan.*) rm -rf "$work" ;; esac
  elif [ "$status" -ne 0 ] && [ -f "$output/manifest.json" ]; then
    python3 "$manifest_tool" fail --manifest "$output/manifest.json" \
      --error "runner exited with status $status" || true
    printf 'failed output retained at %s; work retained at %s\n' "$output" "$work" >&2
  fi
  exit "$status"
}
trap cleanup EXIT

cp "$repo_root/basilisk/src/test/oscillation.c" "$work/oscillation.c"
cp "$repo_root/basilisk/src/test/oscillation.ref" "$work/oscillation.ref"
cp "$script_dir/src/VOF-HF_single_wrapper.c" "$work/VOF-HF_single_wrapper.c"
python3 "$field_overlay" "$work/VOF-HF_single_wrapper.c" \
  --case oscillating_droplet
cp "$field_header" "$work/field_snapshots.h"

compile_cmd=(
  "$qcc" -O2 -DMTRACE=3 -Wall
  -Wno-unused-function -pipe "-DSINGLE_LEVEL=$level"
  VOF-HF_single_wrapper.c -o oscillating-VOF-HF -lm
)
if [ "$grid" = uniform ]; then
  compile_cmd=("${compile_cmd[@]:0:6}" -grid=multigrid "${compile_cmd[@]:6}")
fi
run_cmd=(./oscillating-VOF-HF)
if [ "$compile_only" -eq 1 ]; then run_cmd=(); fi
plan_args=(
  --repo-root "$repo_root" --case oscillating_droplet
  --benchmark oscillating_droplet --method VOF-HF --purpose "$purpose"
  --output "$output" --generator "$script_dir/VOF-HF.sh"
  --generator-logical generate/oscillating_droplet/VOF-HF.sh
  --parameter "resolution=$resolution" --parameter "level=$level"
  --parameter "grid_strategy=$grid"
  --parameter "cells_per_diameter=$cells_per_diameter"
  --parameter "grid_role=$grid_role"
  --parameter imax=null --parameter model=null
  --parameter openmp_threads=1 --parameter "experiment_role=$experiment_role"
  --parameter solver_variant=Standard --parameter source_mutation=false
  --parameter "compile_only=$compile_only"
  --parameter "compile_reused=$([ -n "$precompiled" ] && printf true || printf false)"
  --source "stock_case=source_snapshot/oscillation.c::$work/oscillation.c"
  --source "vof_hf_wrapper=source_snapshot/VOF-HF_single_wrapper.c::$work/VOF-HF_single_wrapper.c"
  --source "official_ref=source_snapshot/oscillation.ref::$work/oscillation.ref"
  --source "field_snapshots=source_snapshot/field_snapshots.h::$work/field_snapshots.h"
  --source "qcc=toolchain/qcc::$qcc"
  --compile-cwd '$WORK' --compile-stdout compile.stdout \
  --compile-stderr compile.stderr
  --run-cwd '$WORK' --run-stdout out --run-stderr runtime.stderr.txt
  --run-env OMP_NUM_THREADS=1 --run-env OMP_DYNAMIC=false
)
for arg in "${compile_cmd[@]}"; do plan_args+=("--compile-arg=$arg"); done
if [ -n "$precompiled" ]; then plan_args+=(--source "precompiled_executable=build/precompiled_executable::$precompiled"); fi
if [ "$compile_only" -eq 0 ]; then
  for arg in "${run_cmd[@]}"; do plan_args+=("--run-arg=$arg"); done
fi

if [ "$dry_run" -eq 1 ]; then
  python3 "$manifest_tool" dry-run "${plan_args[@]}"
  exit 0
fi

cp "$work/oscillation.c" "$work/oscillation.ref" \
  "$work/VOF-HF_single_wrapper.c" "$work/field_snapshots.h" \
  "$output/source_snapshot/"
printf '%s\n' "${compile_cmd[*]}" "${run_cmd[*]-}" > "$output/command.txt"
python3 "$manifest_tool" start "${plan_args[@]}" --manifest "$output/manifest.json"
manifest_started=1
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SECONDS=0

set +e
if [ -n "$precompiled" ]; then
  cp "$precompiled" "$work/oscillating-VOF-HF"
  printf 'campaign-built executable reused\n' > "$work/compile.stdout"; : > "$work/compile.stderr"
  compile_status=0
else
  (cd "$work"; "${compile_cmd[@]}" > compile.stdout 2> compile.stderr)
  compile_status=$?
fi
set -e
cp "$work/compile.stdout" "$work/compile.stderr" "$output/"

if [ "$compile_only" -eq 1 ]; then
  if [ "$compile_status" -ne 0 ]; then exit "$compile_status"; fi
  cp "$work/oscillating-VOF-HF" "$output/executable"
  python3 "$manifest_tool" complete "${plan_args[@]}" \
    --manifest "$output/manifest.json" --elapsed-seconds "$SECONDS"
  trap - EXIT
  printf '%s\n' "$output"
  case "$work" in "$repo_root"/tem/oscillating_droplet/VOF-HF/_work/*) rm -rf "$work" ;; esac
  exit 0
fi

run_status=125
if [ "$compile_status" -eq 0 ]; then
  set +e
  (cd "$work"; OMP_NUM_THREADS=1 OMP_DYNAMIC=false \
    "${run_cmd[@]}" > out 2> runtime.stderr.txt)
  run_status=$?
  set -e
fi

test -s "$work/k-$level"
test -s "$work/fit-$level"
test -s "$work/fit.log"
test -s "$work/error"
test -s "$work/laplace"
test -s "$work/log"
test -s "$work/out"
test -s "$work/termination.csv"
test -s "$work/fields.csv"
cp "$work/k-$level" "$output/timeseries.dat"
cp "$work/fit-$level" "$output/fit_curve.dat"
cp "$work/fit.log" "$output/fit.log"
cp "$work/error" "$output/error.dat"
cp "$work/laplace" "$output/laplace.dat"
cp "$work/log" "$output/fit_summary.dat"
cp "$work/out" "$output/solver.stdout.txt"
cp "$work/runtime.stderr.txt" "$output/runtime.stderr.txt"
cp "$work/termination.csv" "$output/termination.csv"
cp "$work/fields.csv" "$output/fields.csv"
ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' \
  "compile_exit_status=$compile_status" \
  "standard_run_exit_status=$run_status" \
  "started_at=$started_at" \
  "ended_at=$ended_at" \
  "wall_seconds=$SECONDS" \
  > "$output/execution_status.txt"

python3 "$report_builder" \
  --dataset "$output" --resolution "$resolution" --level "$level" \
  --cells-per-diameter "$cells_per_diameter" --grid-role "$grid_role" \
  --grid-strategy "$grid" --experiment-role "$experiment_role" \
  --compile-exit-status "$compile_status" --run-exit-status "$run_status" \
  --started-at "$started_at" --ended-at "$ended_at" --wall-seconds "$SECONDS" \
  --output-json "$output/verification.json"
python3 "$artifact_builder" "$output"
python3 "$finalizer" "$output"
python3 "$manifest_tool" complete "${plan_args[@]}" \
  --manifest "$output/manifest.json" --elapsed-seconds "$SECONDS"

trap - EXIT
printf '%s\n' "$output"
case "$work" in "$repo_root"/tem/oscillating_droplet/VOF-HF/_work/*) rm -rf "$work" ;; esac
