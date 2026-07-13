#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

src_case="$repo_root/basilisk/src/test/capwave-clsvof.c"
src_prosperetti="$repo_root/basilisk/src/test/prosperetti.h"
src_integral="$repo_root/basilisk/src/integral.h"
baseline_root="$repo_root/dataset/official_data/capwave-clsvof"
qcc="$repo_root/basilisk/src/qcc"

work_root="$script_dir/work"
results_root="$script_dir/results/$(date -u +%Y%m%dT%H%M%SZ)"

copy_case() {
  local dst="$1"
  local resolution="${2:-}"
  mkdir -p "$dst"
  if [ -n "$resolution" ]; then
    /opt/anaconda3/envs/pinn/bin/python \
      "$repo_root/experiments/capwave_clsvof_kreplace/make_single_resolution_case.py" \
      "$src_case" \
      "$dst/capwave-clsvof.c" \
      --resolution "$resolution"
  else
    cp -L "$src_case" "$dst/capwave-clsvof.c"
  fi
  cp "$src_prosperetti" "$dst/prosperetti.h"
}

run_case() {
  local dst="$1"
  shift
  (
    cd "$dst"
    "$qcc" -autolink "$@" capwave-clsvof.c -o capwave-clsvof -lm
    ./capwave-clsvof > stdout.txt 2> log
  )
}

archive_case() {
  local label="$1"
  local dst="$2"
  mkdir -p "$results_root/$label"
  cp "$dst"/stdout.txt "$results_root/$label/stdout.txt"
  cp "$dst"/log "$results_root/$label/log"
  cp "$dst"/wave-* "$results_root/$label/"
}

generate_overlay() {
  local dst="$1"
  /opt/anaconda3/envs/pinn/bin/python \
    "$repo_root/experiments/capwave_clsvof_kreplace/make_overlay_integral.py" \
    "$src_integral" \
    "$dst/integral.h"
}

run_nn_mode() {
  local label="$1"
  local weights_dir="$2"
  local resolution="$3"
  local dst="$work_root/$label"

  copy_case "$dst" "$resolution"
  generate_overlay "$dst"
  run_case "$dst" \
    -DCLSVOF=1 \
    -DCAPWAVE_K_MODE=1 \
    -DCAPWAVE_K_CLAMP_FACTOR=1.0 \
    -I"$repo_root/experiments/capwave_clsvof_kreplace/include" \
    -I"$repo_root/tools/clsvof_model_export/include" \
    -I"$repo_root/dataset/model/c_exports/$weights_dir"
  archive_case "$label" "$dst"
}

rm -rf "$work_root"
mkdir -p "$work_root" "$results_root"

run_nn_mode nn_baseline_64_hgradient baseline_64_hgradient 64
run_nn_mode nn_baseline_128_hgradient baseline_128_hgradient 128
run_nn_mode nn_baseline_256_hgradient baseline_256_hgradient 256
run_nn_mode nn_baseline_512_hgradient baseline_512_hgradient 512

cat > "$results_root/manifest.json" <<JSON
{
  "source_case": "basilisk/src/test/capwave-clsvof.c",
  "source_integral": "basilisk/src/integral.h",
  "baseline": "dataset/official_data/capwave-clsvof",
  "case_resolution_patch": "for (N = 16; N <= 128; N *= 2) -> single target N per copied case",
  "replacement": "double ki = distance_curvature (point, d) -> double ki = capwave_k_provider (point, d)",
  "matched_resolutions": {
    "nn_baseline_64_hgradient": 64,
    "nn_baseline_128_hgradient": 128,
    "nn_baseline_256_hgradient": 256,
    "nn_baseline_512_hgradient": 512
  },
  "nn_weights": [
    "dataset/model/c_exports/baseline_64_hgradient/nn_weights.h",
    "dataset/model/c_exports/baseline_128_hgradient/nn_weights.h",
    "dataset/model/c_exports/baseline_256_hgradient/nn_weights.h",
    "dataset/model/c_exports/baseline_512_hgradient/nn_weights.h"
  ],
  "modes": [
    "nn_baseline_64_hgradient",
    "nn_baseline_128_hgradient",
    "nn_baseline_256_hgradient",
    "nn_baseline_512_hgradient"
  ],
  "clamp": "abs(kappa) <= 1/Delta"
}
JSON

echo "$results_root"
