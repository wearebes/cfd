#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
qcc="${BASILISK_QCC:-$repo_root/basilisk/src/qcc}"
shared_root="$repo_root/generate/_shared"
nn_root="$shared_root/nn_runtime"
redistance_root="$shared_root/nondefault_redistance"
manifest_tool="$shared_root/run_manifest.py"
field_overlay="$shared_root/append_field_snapshots.py"
field_header="$shared_root/field_snapshots.h"
finalizer="$shared_root/finalize_row.py"

imax=3
imax_explicit=0
steps=""
resolution=64
purpose=smoke
output=""
dry_run=0
compile_only=0
threads=1
model_name=""
feature_mode=phi9_full_normal
precompiled=""
curvature_mode=cell
inference_precision="${CFD_NN_INFERENCE_PRECISION:-float32}"

usage() {
  printf '%s\n' \
    "usage: $0 [--imax 0|1|2|3|4|5|10|15|20 | --steps 0|1|2|3|4|5|10]" \
    "          [--resolution 32|64|128|256|512]" \
    "          [--model NAME] [--curvature-mode cell|direct|interface]" \
    "          [--feature-mode phi9|phi9_full_normal|phi9_center_normal|phi9_cross_normal|phi9_local_normal]" \
    "          [--inference-precision float32|float64-forward]" \
    "          [--smoke|--formal] --output PATH" \
    "          [--threads N] [--dry-run] [--compile-only] [--precompiled PATH]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --imax) imax="${2:?missing value for --imax}"; imax_explicit=1; shift 2 ;;
    --steps) steps="${2:?missing value for --steps}"; shift 2 ;;
    --resolution) resolution="${2:?missing value for --resolution}"; shift 2 ;;
    --feature-mode) feature_mode="${2:?missing feature mode}"; shift 2 ;;
    --model) model_name="${2:?missing value for --model}"; shift 2 ;;
    --curvature-mode) curvature_mode="${2:?missing value for --curvature-mode}"; shift 2 ;;
    --inference-precision)
      inference_precision="${2:?missing value for --inference-precision}"
      shift 2
      ;;
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

if [ "$imax_explicit" -eq 1 ] && [ -n "$steps" ]; then
  printf 'error: --imax and --steps are mutually exclusive\n' >&2; exit 2
fi

case "$inference_precision" in
  float32) inference_double=0 ;;
  float64-forward|float64-accum)
    inference_precision=float64-forward
    inference_double=1
    ;;
  *)
    printf 'error: --inference-precision must be float32 or float64-forward\n' >&2
    exit 2
    ;;
esac

case "$curvature_mode" in
  cell)
    curvature_mode_define=1
    curvature_contract=cell_transform_c1
    nn_provider=cell_transform
    nn_provider_contract=cell_transform
    overlay_method=nn-cell
    ;;
  direct)
    curvature_mode_define=2
    curvature_contract=interface_direct_c1
    nn_provider=interface
    nn_provider_contract=q_gamma_over_delta
    overlay_method=nn-cell
    ;;
  interface)
    curvature_mode_define=2
    curvature_contract=interface_interpolation_c2
    nn_provider=interface
    nn_provider_contract=q_gamma_over_delta
    overlay_method=nn-c2
    ;;
  *) printf 'error: --curvature-mode must be cell, direct or interface\n' >&2; exit 2 ;;
esac

if [ -n "$steps" ]; then
  case "$steps" in 0|1|2|3|4|5|10) ;; *)
    printf 'error: --steps must be one of 0,1,2,3,4,5,10\n' >&2; exit 2;; esac
  if [ "$curvature_mode" != interface ] && [ "$curvature_mode" != direct ]; then
    printf 'error: --steps requires --curvature-mode interface or direct\n' >&2; exit 2
  fi
  experiment_role=fixed_steps_validation
  redistance_policy=fixed_steps
else
  case "$imax" in 0|1|2|3|4|5|10|15|20) ;; *)
    printf 'error: --imax must be one of 0,1,2,3,4,5,10,15,20\n' >&2; exit 2;; esac
  if [ "$imax" = 3 ]; then experiment_role=default; else experiment_role=sensitivity; fi
  redistance_policy=imax_limit
fi
case "$resolution" in 32|64|128|256|512) ;; *)
  printf 'error: --resolution must be one of 32,64,128,256,512\n' >&2; exit 2;; esac
case "$threads" in ''|*[!0-9]*|0)
  printf 'error: --threads must be a positive integer\n' >&2; exit 2;; esac
if [ -z "$output" ]; then
  printf 'error: --output is required\n' >&2; usage >&2; exit 2
fi
if [ "$purpose" = formal ] && [ "$compile_only" -eq 1 ] && [ "${CFD_CAMPAIGN_BUILD:-0}" != 1 ]; then
  printf 'error: --formal cannot be combined with --compile-only\n' >&2; exit 2
fi
if [ "$compile_only" -eq 1 ] && [ -n "$precompiled" ]; then
  printf 'error: --compile-only and --precompiled are mutually exclusive\n' >&2; exit 2
fi
if [ -n "$precompiled" ] && [ ! -f "$precompiled" ]; then
  printf 'error: missing precompiled executable: %s\n' "$precompiled" >&2; exit 2
fi
if [ -n "$precompiled" ] && [ "${CFD_CAMPAIGN_PRECOMPILED:-0}" != 1 ]; then
  printf 'error: --precompiled is reserved for the verified campaign scheduler\n' >&2; exit 2
fi
case "$feature_mode" in
  phi9) feature_dim=9; model_suffix=phi9 ;;
  phi9_full_normal) feature_dim=27; model_suffix=hgradient ;;
  phi9_center_normal) feature_dim=11; model_suffix=hcenter_normal ;;
  phi9_local_normal) feature_dim=15; model_suffix=hlocal_normal ;;
  phi9_cross_normal) feature_dim=19; model_suffix=hcross_normal ;;
  *) printf 'error: unsupported --feature-mode %s\n' "$feature_mode" >&2; exit 2 ;;
esac
if [ -z "$model_name" ]; then
  if [ "$feature_dim" = 27 ]; then model_name="baseline_${resolution}_hgradient";
  else model_name="cell_${resolution}_${model_suffix}"; fi
fi
if [ "$purpose" = formal ] && [ "$model_name" != "cell_${resolution}_${model_suffix}" ] &&
   { [ "$feature_dim" != 27 ] || [ "$model_name" != "baseline_${resolution}_hgradient" ]; }; then
  printf 'error: formal model must match resolution and feature mode\n' >&2; exit 2
fi
model_dir="$repo_root/data/model/c_exports/$model_name"
if [ ! -f "$model_dir/nn_weights.h" ] || [ ! -f "$model_dir/export_manifest.json" ]; then
  model_dir="$repo_root/dataset/model/c_exports/$model_name"
fi
if [ ! -f "$model_dir/nn_weights.h" ] || [ ! -f "$model_dir/export_manifest.json" ]; then
  printf 'error: incomplete model export %s\n' "$model_dir" >&2; exit 1
fi
python3 "$shared_root/nn_runtime/feature_contract.py" --manifest "$model_dir/export_manifest.json" --feature-mode "$feature_mode"
recorded_model="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$model_dir/export_manifest.json")"
if [ "$recorded_model" != "$model_name" ]; then
  printf 'error: model export identity mismatch: %s != %s\n' "$recorded_model" "$model_name" >&2
  exit 1
fi

output_parent="$(dirname "$output")"
if [ ! -d "$output_parent" ]; then
  if [ "$dry_run" -eq 0 ]; then mkdir -p "$output_parent"; fi
fi
if [ -d "$output_parent" ]; then
  output="$(cd "$output_parent" && pwd)/$(basename "$output")"
fi
if [ "$dry_run" -eq 0 ] && [ -e "$output" ]; then
  printf 'error: output already exists: %s\n' "$output" >&2; exit 1
fi

output_name="$(basename "$output")"
if [ "$dry_run" -eq 1 ]; then
  work="$(mktemp -d "${TMPDIR:-/tmp}/cfd-capwave-nn-plan.XXXXXX")"
else
  work="$repo_root/tem/capwave/_work/${output_name}.$$"
  mkdir -p "$output/source_snapshot" "$work"
fi

cleanup() {
  status=$?
  trap - EXIT
  if [ "$dry_run" -eq 1 ]; then
    case "$work" in "${TMPDIR:-/tmp}"/cfd-capwave-nn-plan.*) rm -rf "$work" ;; esac
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
cp "$repo_root/basilisk/src/test/prosperetti.h" "$work/prosperetti.h"
cp "$nn_root/src/clsvof_nn_cell_curvature.h" "$work/"
cp "$nn_root/src/kappa_offset_stats.h" "$work/"
cp "$nn_root/src/clsvof_mlp_infer.h" "$work/"
cp "$model_dir/nn_weights.h" "$model_dir/export_manifest.json" "$work/"
python3 "$nn_root/src/make_overlay_integral.py" \
  "$repo_root/basilisk/src/integral.h" "$work/integral.h" \
  --method "$overlay_method"
if [ "$curvature_mode" = interface ]; then
  cp "$nn_root/src/c2_interface_provider.h" "$work/"
fi
redistance_args=(--imax "$imax")
if [ -n "$steps" ]; then
  redistance_args=(--steps "$steps")
  cp "$redistance_root/src/redistance_steps_stats.h" "$work/"
  cp "$redistance_root/src/redistance_fixed_steps.h" "$work/redistance.h"
fi
python3 "$redistance_root/src/make_redistance_overlay.py" \
  "$repo_root/basilisk/src/two-phase-clsvof.h" "$work/two-phase-clsvof.h" \
  "${redistance_args[@]}" --no-metrics \
  --provenance "$work/redistance_overlay.json"
python3 "$field_overlay" "$work/capwave-clsvof.c" --case capwave --clsvof
cp "$field_header" "$work/field_snapshots.h"

if [ -n "$steps" ]; then
  cp "$work/redistance.h" "$work/redistance_fixed_steps.h"
  python3 - "$work/two-phase-clsvof.h" <<'PYOVERLAY'
import sys
from pathlib import Path
p=Path(sys.argv[1]);p.write_text(p.read_text().replace('#include "redistance.h"', '#include "redistance_fixed_steps.h"'))
PYOVERLAY
fi

compile_cmd=("$qcc" -O2 -DCLSVOF=1)
if [ "$threads" -gt 1 ]; then compile_cmd+=("-fopenmp"); fi
compile_cmd+=(
  "-DKAPPA_OFFSET_TRANSFORM_MODE=$curvature_mode_define"
  "-DKAPPA_OFFSET_INFERENCE_DOUBLE=$inference_double"
  -DKAPPA_OFFSET_CLAMP_FACTOR=1.0 -DKAPPA_OFFSET_PROBE_INTERVAL=0
  -disable-dimensions -I. capwave-clsvof.c -o capwave-clsvof -lm
)
run_cmd=(./capwave-clsvof)
if [ "$compile_only" -eq 1 ]; then run_cmd=(); fi

plan_args=(
  --repo-root "$repo_root"
  --case capwave --benchmark capwave --method NN --purpose "$purpose"
  --output "$output"
  --generator "$script_dir/NN.sh"
  --generator-logical generate/capwave/NN.sh
  --parameter "resolution=$resolution"
  --parameter "experiment_role=$experiment_role"
  --parameter "redistance_policy=$redistance_policy"
  --parameter grid_strategy=uniform
  --parameter "model=$model_name"
  --parameter "feature_mode=$feature_mode"
  --parameter "feature_dim_raw=$feature_dim"
  --parameter "curvature_mode=$curvature_mode"
  --parameter "inference_precision=$inference_precision"
  --parameter "curvature_contract=$curvature_contract"
  --parameter "curvature_consumer=$curvature_mode"
  --parameter "nn_provider=$nn_provider"
  --parameter "nn_provider_contract=$nn_provider_contract"
  --parameter "openmp_threads=$threads"
  --parameter "compile_only=$compile_only"
  --parameter "compile_reused=$([ -n "$precompiled" ] && printf true || printf false)"
  --run-env "OMP_NUM_THREADS=$threads" --run-env OMP_DYNAMIC=false
  --source "stock_case=basilisk/src/test/capwave-clsvof.c::$repo_root/basilisk/src/test/capwave-clsvof.c"
  --source "compiled_case=source_snapshot/capwave-clsvof.c::$work/capwave-clsvof.c"
  --source "compiled_integral=source_snapshot/integral.h::$work/integral.h"
  --source "compiled_two_phase=source_snapshot/two-phase-clsvof.h::$work/two-phase-clsvof.h"
  --source "nn_runtime=source_snapshot/clsvof_nn_cell_curvature.h::$work/clsvof_nn_cell_curvature.h"
  --source "nn_stats=source_snapshot/kappa_offset_stats.h::$work/kappa_offset_stats.h"
  --source "nn_inference=source_snapshot/clsvof_mlp_infer.h::$work/clsvof_mlp_infer.h"
  --source "nn_weights=source_snapshot/nn_weights.h::$work/nn_weights.h"
  --source "model_export=source_snapshot/export_manifest.json::$work/export_manifest.json"
  --source "redistance_overlay=source_snapshot/redistance_overlay.json::$work/redistance_overlay.json"
  --source "prosperetti=source_snapshot/prosperetti.h::$work/prosperetti.h"
  --source "field_snapshots=source_snapshot/field_snapshots.h::$work/field_snapshots.h"
  --source "qcc=toolchain/qcc::$qcc"
  --compile-cwd '$WORK' --run-cwd '$WORK'
  --run-stdout stdout.txt --run-stderr log
)
if [ -n "$steps" ]; then
  plan_args+=(
    --parameter imax=null --parameter "steps=$steps"
    --source "redistance_core=source_snapshot/redistance.h::$work/redistance.h"
    --source "redistance_steps_stats=source_snapshot/redistance_steps_stats.h::$work/redistance_steps_stats.h"
  )
else
  plan_args+=(--parameter "imax=$imax")
fi
if [ "$curvature_mode" = interface ]; then
  plan_args+=(--source "c2_interface_provider=source_snapshot/c2_interface_provider.h::$work/c2_interface_provider.h")
fi
for arg in "${compile_cmd[@]}"; do plan_args+=("--compile-arg=$arg"); done
if [ -n "$precompiled" ]; then
  plan_args+=(--source "precompiled_executable=build/precompiled_executable::$precompiled")
fi
if [ "$compile_only" -eq 0 ]; then
  for arg in "${run_cmd[@]}"; do plan_args+=("--run-arg=$arg"); done
fi

if [ "$dry_run" -eq 1 ]; then
  python3 "$manifest_tool" dry-run "${plan_args[@]}"
  exit 0
fi

cp "$work/capwave-clsvof.c" "$work/integral.h" "$work/two-phase-clsvof.h" \
  "$work/clsvof_nn_cell_curvature.h" "$work/kappa_offset_stats.h" \
  "$work/clsvof_mlp_infer.h" "$work/nn_weights.h" "$work/export_manifest.json" \
  "$work/prosperetti.h" "$work/redistance_overlay.json" \
  "$work/field_snapshots.h" \
  "$output/source_snapshot/"
if [ -n "$steps" ]; then
  cp "$work/redistance.h" "$work/redistance_fixed_steps.h" "$output/source_snapshot/"
  cp "$work/redistance_steps_stats.h" "$output/source_snapshot/"
fi
if [ "$curvature_mode" = interface ]; then
  cp "$work/c2_interface_provider.h" "$output/source_snapshot/"
fi
python3 "$manifest_tool" start "${plan_args[@]}" --manifest "$output/manifest.json"

SECONDS=0
if [ -n "$precompiled" ]; then
  cp "$precompiled" "$work/capwave-clsvof"
  printf 'campaign-built executable reused\n' > "$work/compile.stdout"
  : > "$work/compile.stderr"
else
  (
    cd "$work"
    "${compile_cmd[@]}" > compile.stdout 2> compile.stderr
  )
fi
cp "$work/compile.stdout" "$work/compile.stderr" "$output/"
if [ "$compile_only" -eq 1 ]; then
  cp "$work/capwave-clsvof" "$output/executable"
fi
if [ "$compile_only" -eq 0 ]; then
  (
    cd "$work"
    OMP_NUM_THREADS="$threads" OMP_DYNAMIC=false "${run_cmd[@]}" > stdout.txt 2> log
  )
  test -s "$work/wave-$resolution"
  cp "$work/wave-$resolution" "$output/wave.dat"
  cp "$work/log" "$output/official_error.dat"
  cp "$work/stdout.txt" "$output/solver.stdout.txt"
  cp "$work/prosperetti.h" "$output/prosperetti.h"
  test -s "$work/fields.csv"
  cp "$work/fields.csv" "$output/fields.csv"
  python3 "$shared_root/build_scientific_artifacts.py" "$output"
  python3 "$finalizer" "$output"
fi
elapsed="$SECONDS"
python3 "$manifest_tool" complete "${plan_args[@]}" \
  --manifest "$output/manifest.json" --elapsed-seconds "$elapsed"

trap - EXIT
printf '%s\n' "$output"
case "$work" in "$repo_root"/tem/capwave/_work/*) rm -rf "$work" ;; esac
