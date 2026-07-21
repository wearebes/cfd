#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
shared_root="$repo_root/generate/_shared"
nn_root="$shared_root/nn_runtime"
redistance_root="$shared_root/nondefault_redistance"
manifest_tool="$shared_root/run_manifest.py"

benchmark_case=1
imax=3
resolution=64
purpose=smoke
output=""
dry_run=0
compile_only=0
threads=1
model_name=""

usage() {
  printf '%s\n' \
    "usage: $0 --case 1|2 [--imax 0..5] [--resolution 64|128|256|512]" \
    "          [--model NAME] [--smoke|--formal] --output PATH" \
    "          [--threads N] [--dry-run] [--compile-only]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --case) benchmark_case="${2:?missing value for --case}"; shift 2 ;;
    --imax) imax="${2:?missing value for --imax}"; shift 2 ;;
    --resolution) resolution="${2:?missing value for --resolution}"; shift 2 ;;
    --model) model_name="${2:?missing value for --model}"; shift 2 ;;
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

case "$benchmark_case" in 1|2) ;; *)
  printf 'error: --case must be 1 or 2\n' >&2; exit 2;; esac
case "$imax" in 0|1|2|3|4|5) ;; *)
  printf 'error: --imax must be an integer from 0 through 5\n' >&2; exit 2;; esac
case "$resolution" in
  64) level=6 ;;
  128) level=7 ;;
  256) level=8 ;;
  512) level=9 ;;
  *) printf 'error: --resolution must be one of 64,128,256,512\n' >&2; exit 2 ;;
esac
case "$threads" in ''|*[!0-9]*|0)
  printf 'error: --threads must be a positive integer\n' >&2; exit 2;; esac
if [ -z "$output" ]; then
  printf 'error: --output is required\n' >&2; usage >&2; exit 2
fi
if [ -z "$model_name" ]; then model_name="baseline_${resolution}_hgradient"; fi
model_dir="$repo_root/dataset/model/c_exports/$model_name"
if [ ! -f "$model_dir/nn_weights.h" ] || [ ! -f "$model_dir/export_manifest.json" ]; then
  printf 'error: incomplete model export %s\n' "$model_dir" >&2; exit 1
fi

benchmark="rising_case${benchmark_case}"
benchmark_case_name="hysing_case_${benchmark_case}"
actual_grid="${resolution}x$((resolution / 4))"
output_parent="$(dirname "$output")"
if [ "$dry_run" -eq 0 ]; then mkdir -p "$output_parent"; fi
if [ -d "$output_parent" ]; then output="$(cd "$output_parent" && pwd)/$(basename "$output")"; fi
if [ "$dry_run" -eq 0 ] && [ -e "$output" ]; then
  printf 'error: output already exists: %s\n' "$output" >&2; exit 1
fi

output_name="$(basename "$output")"
if [ "$dry_run" -eq 1 ]; then
  work="$(mktemp -d "${TMPDIR:-/tmp}/cfd-rising-nn-plan.XXXXXX")"
else
  work="$repo_root/tem/rising_bubble/case${benchmark_case}/_work/${output_name}.$$"
  mkdir -p "$output/source_snapshot" "$work/checkpoints"
fi

cleanup() {
  status=$?
  trap - EXIT
  if [ "$dry_run" -eq 1 ]; then
    case "$work" in "${TMPDIR:-/tmp}"/cfd-rising-nn-plan.*) rm -rf "$work" ;; esac
  elif [ "$status" -ne 0 ] && [ -f "$output/manifest.json" ]; then
    python3 "$manifest_tool" fail --manifest "$output/manifest.json" \
      --error "runner exited with status $status" || true
    printf 'failed output retained at %s; work retained at %s\n' "$output" "$work" >&2
  fi
  exit "$status"
}
trap cleanup EXIT

python3 "$script_dir/src/make_metrics_overlay.py" \
  "$repo_root/basilisk/src/test/rising.c" "$work/rising-clsvof.c" \
  --provenance "$work/rising_metrics_overlay.json"
python3 "$shared_root/make_checkpoint_overlay.py" \
  "$work/rising-clsvof.c" "$work/rising-clsvof.c" \
  --case rising_bubble --provenance "$work/checkpoint_overlay.json"
cp "$nn_root/src/clsvof_nn_cell_curvature.h" "$work/"
cp "$nn_root/src/kappa_offset_stats.h" "$work/"
cp "$nn_root/src/clsvof_mlp_infer.h" "$work/"
cp "$model_dir/nn_weights.h" "$model_dir/export_manifest.json" "$work/"
python3 "$nn_root/src/make_overlay_integral.py" \
  "$repo_root/basilisk/src/integral.h" "$work/integral.h"
python3 "$redistance_root/src/make_redistance_overlay.py" \
  "$repo_root/basilisk/src/two-phase-clsvof.h" "$work/two-phase-clsvof.h" \
  --imax "$imax" --no-metrics --provenance "$work/redistance_overlay.json"

compile_cmd=(
  "$repo_root/basilisk/src/qcc" -O2 -DLEVELSET=1 -DCLSVOF=1 "-DLEVEL=$level"
)
if [ "$benchmark_case" -eq 2 ]; then compile_cmd+=("-DCASE2=1"); fi
if [ "$threads" -gt 1 ]; then compile_cmd+=("-fopenmp"); fi
compile_cmd+=(
  -DKAPPA_OFFSET_CLAMP_FACTOR=1.0 -DKAPPA_OFFSET_PROBE_INTERVAL=0
  -disable-dimensions -I. rising-clsvof.c -o rising-clsvof -lm
)
run_cmd=(./rising-clsvof)
if [ "$compile_only" -eq 1 ]; then run_cmd=(); fi

plan_args=(
  --repo-root "$repo_root"
  --case rising_bubble --benchmark "$benchmark" --method nn --purpose "$purpose"
  --output "$output"
  --generator "$script_dir/nn.sh"
  --generator-logical generate/rising_bubble/nn.sh
  --parameter "benchmark_case=$benchmark_case_name"
  --parameter "resolution=$resolution" --parameter "level=$level"
  --parameter "actual_grid=$actual_grid" --parameter "imax=$imax"
  --parameter "model=$model_name" --parameter "openmp_threads=$threads"
  --parameter "compile_only=$compile_only"
  --source "stock_case=basilisk/src/test/rising.c::$repo_root/basilisk/src/test/rising.c"
  --source "compiled_case=source_snapshot/rising-clsvof.c::$work/rising-clsvof.c"
  --source "compiled_integral=source_snapshot/integral.h::$work/integral.h"
  --source "compiled_two_phase=source_snapshot/two-phase-clsvof.h::$work/two-phase-clsvof.h"
  --source "nn_runtime=source_snapshot/clsvof_nn_cell_curvature.h::$work/clsvof_nn_cell_curvature.h"
  --source "nn_stats=source_snapshot/kappa_offset_stats.h::$work/kappa_offset_stats.h"
  --source "nn_inference=source_snapshot/clsvof_mlp_infer.h::$work/clsvof_mlp_infer.h"
  --source "nn_weights=source_snapshot/nn_weights.h::$work/nn_weights.h"
  --source "model_export=source_snapshot/export_manifest.json::$work/export_manifest.json"
  --source "metrics_overlay=source_snapshot/rising_metrics_overlay.json::$work/rising_metrics_overlay.json"
  --source "checkpoint_overlay=source_snapshot/checkpoint_overlay.json::$work/checkpoint_overlay.json"
  --source "redistance_overlay=source_snapshot/redistance_overlay.json::$work/redistance_overlay.json"
  --source "qcc=basilisk/src/qcc::$repo_root/basilisk/src/qcc"
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

cp "$work/rising-clsvof.c" "$work/integral.h" "$work/two-phase-clsvof.h" \
  "$work/clsvof_nn_cell_curvature.h" "$work/kappa_offset_stats.h" \
  "$work/clsvof_mlp_infer.h" "$work/nn_weights.h" "$work/export_manifest.json" \
  "$work/rising_metrics_overlay.json" "$work/checkpoint_overlay.json" \
  "$work/redistance_overlay.json" "$output/source_snapshot/"
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
  python3 - "$work/stdout.txt" "$work/circularity.csv" <<'PY'
import csv
import math
import sys
from pathlib import Path

history = []
for line in Path(sys.argv[1]).read_text().splitlines():
    fields = line.split()
    try:
        row = [float(value) for value in fields[:5]]
    except ValueError:
        continue
    if len(row) == 5 and all(math.isfinite(value) for value in row):
        history.append(row)
if not history or abs(history[-1][0] - 3.0) > 1e-9:
    raise SystemExit("rising output did not reach t=3")
rows = list(csv.DictReader(Path(sys.argv[2]).open(newline="")))
if len(rows) < 2 or abs(float(rows[-1]["time"]) - 3.0) > 1e-9:
    raise SystemExit("circularity history is incomplete")
PY
  cp "$work/log" "$work/stdout.txt" "$work/circularity.csv" \
    "$work/checkpoint_index.csv" "$output/"
  cp -R "$work/checkpoints" "$output/"
  python3 "$shared_root/build_scientific_artifacts.py" "$output"
fi
elapsed="$SECONDS"
python3 "$manifest_tool" complete "${plan_args[@]}" \
  --manifest "$output/manifest.json" --elapsed-seconds "$elapsed"

trap - EXIT
printf '%s\n' "$output"
printf 'work: %s\n' "$work" >&2
