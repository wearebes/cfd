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
resolution=64
purpose=smoke
output=""
dry_run=0
compile_only=0
threads=1
model_name=""
precompiled=""
inference_precision="${CFD_NN_INFERENCE_PRECISION:-float32}"

usage() {
  printf '%s\n' \
    "usage: $0 [--imax 0|1|2|3|4|5|10|15|20] [--resolution 32|64|128|256|512]" \
    "          [--model NAME] [--inference-precision float32|float64-forward]" \
    "          [--smoke|--formal] --output PATH" \
    "          [--threads N] [--dry-run] [--compile-only] [--precompiled PATH]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --imax) imax="${2:?missing value for --imax}"; shift 2 ;;
    --resolution) resolution="${2:?missing value for --resolution}"; shift 2 ;;
    --model) model_name="${2:?missing value for --model}"; shift 2 ;;
    --inference-precision) inference_precision="${2:?missing value for --inference-precision}"; shift 2 ;;
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

case "$imax" in 0|1|2|3|4|5|10|15|20) ;; *)
  printf 'error: --imax must be one of 0,1,2,3,4,5,10,15,20\n' >&2; exit 2;; esac
if [ "$imax" = 3 ]; then experiment_role=default; else experiment_role=sensitivity; fi
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
if [ -z "$model_name" ]; then model_name="baseline_${resolution}_hgradient"; fi
if [ "$purpose" = formal ] && [ "$model_name" != "baseline_${resolution}_hgradient" ]; then
  printf 'error: formal NN rows require model baseline_%s_hgradient\n' "$resolution" >&2
  exit 2
fi
model_dir="$repo_root/dataset/model/c_exports/$model_name"
if [ ! -f "$model_dir/nn_weights.h" ] || [ ! -f "$model_dir/export_manifest.json" ]; then
  printf 'error: incomplete model export %s\n' "$model_dir" >&2; exit 1
fi
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
  "$repo_root/basilisk/src/integral.h" "$work/integral.h"
python3 "$redistance_root/src/make_redistance_overlay.py" \
  "$repo_root/basilisk/src/two-phase-clsvof.h" "$work/two-phase-clsvof.h" \
  --imax "$imax" --no-metrics --provenance "$work/redistance_overlay.json"
python3 "$field_overlay" "$work/capwave-clsvof.c" --case capwave --clsvof
cp "$field_header" "$work/field_snapshots.h"

compile_cmd=("$qcc" -O2 -DCLSVOF=1)
if [ "$threads" -gt 1 ]; then compile_cmd+=("-fopenmp"); fi
compile_cmd+=(
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
  --parameter "imax=$imax"
  --parameter "experiment_role=$experiment_role"
  --parameter grid_strategy=uniform
  --parameter "model=$model_name"
  --parameter "inference_precision=$inference_precision"
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
