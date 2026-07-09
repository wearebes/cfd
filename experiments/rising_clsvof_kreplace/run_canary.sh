#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
python_bin="/opt/anaconda3/envs/pinn/bin/python"

src_case="$repo_root/basilisk/src/test/rising.c"
src_integral="$repo_root/basilisk/src/integral.h"
include_dir="$script_dir/include"
model_include_dir="$repo_root/tools/clsvof_model/include"

# Placeholder model dir used by control modes (original excepted). qcc's
# include scanner resolves #include lines textually, not via #if, so
# nn_weights.h/clsvof_mlp_infer.h must be resolvable even though
# RISING_K_NATIVE/RISING_K_NATIVE_PERTURBED never reach the NN branch.
# See tools/basilisk-cc and include/rising_k_provider.h.
placeholder_model_dir="$repo_root/dataset/model/c_exports/baseline_128_hgradient"

# NN model names for this canary (dataset/model/c_exports/<name>/nn_weights.h).
# Task 4/5 run only the baseline canary; Task 8 extends this list.
nn_models=(
  baseline_128_hgradient
)

work_root="$script_dir/work"
results_dir_base="$script_dir/results"
common_flags=(-DLEVELSET=1 -DCLSVOF=1)

nn_only=0
for arg in "$@"; do
  case "$arg" in
    --nn-only) nn_only=1 ;;
    *)
      printf 'usage: %s [--nn-only]\n' "$0" >&2
      exit 2
      ;;
  esac
done

sha256_of() {
  shasum -a 256 "$1" | awk '{print $1}'
}

rising_c_sha256="$(sha256_of "$src_case")"
integral_h_sha256="$(sha256_of "$src_integral")"
common_flags_str="${common_flags[*]}"
source_fingerprint="rising_v1:${rising_c_sha256}:${integral_h_sha256}:${common_flags_str}"

copy_case() {
  local dst="$1"
  mkdir -p "$dst"
  cp "$src_case" "$dst/rising-clsvof.c"
}

generate_overlay() {
  local dst="$1"
  "$python_bin" "$script_dir/make_overlay_integral.py" "$src_integral" "$dst/integral.h"
}

run_case() {
  local dst="$1"
  shift
  (
    cd "$dst"
    "$repo_root/tools/basilisk-run" "$@" rising-clsvof.c > out 2> log
  )
}

archive_case() {
  local label="$1"
  local work_dir="$2"
  local dest_root="$3"
  mkdir -p "$dest_root/$label"
  cp "$work_dir/out" "$dest_root/$label/out"
  cp "$work_dir/log" "$dest_root/$label/log"
  if [ -f "$work_dir/integral.h" ]; then
    cp "$work_dir/integral.h" "$dest_root/$label/integral.h"
  fi
}

write_manifest() {
  local dest_root="$1"
  shift
  local modes_json
  modes_json="$(printf '"%s",' "$@" | sed 's/,$//')"
  cat > "$dest_root/manifest.json" <<JSON
{
  "source_case": "basilisk/src/test/rising.c",
  "source_integral": "basilisk/src/integral.h",
  "replacement": "double ki = distance_curvature (point, d) -> double ki = rising_k_provider (point, d)",
  "nn_weights_root": "dataset/model/c_exports/",
  "modes": [${modes_json}],
  "clamp": "abs(kappa) <= RISING_K_CLAMP_FACTOR/Delta (default factor 1.0)",
  "compile_flags_common": "${common_flags_str}",
  "source_fingerprint": "${source_fingerprint}",
  "source_fingerprint_detail": {
    "rising_c_sha256": "${rising_c_sha256}",
    "integral_h_sha256": "${integral_h_sha256}"
  }
}
JSON
}

find_latest_gated_controls() {
  local candidate candidate_fp passed
  [ -d "$results_dir_base" ] || return 1
  for candidate in $(find "$results_dir_base" -mindepth 1 -maxdepth 1 -type d | sort -r); do
    [ -f "$candidate/manifest.json" ] || continue
    [ -f "$candidate/gate_verdict.json" ] || continue
    candidate_fp="$("$python_bin" -c "import json,sys; print(json.load(open(sys.argv[1])).get('source_fingerprint',''))" "$candidate/manifest.json" 2>/dev/null || true)"
    passed="$("$python_bin" -c "import json,sys; print(bool(json.load(open(sys.argv[1])).get('all_passed', False)))" "$candidate/gate_verdict.json" 2>/dev/null || true)"
    if [ "$candidate_fp" = "$source_fingerprint" ] && [ "$passed" = "True" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [ "$nn_only" -eq 1 ]; then
  results_root="$(find_latest_gated_controls)" || {
    printf 'error: --nn-only requires a previously gate-passed control set with a matching source fingerprint.\n' >&2
    printf '       Run %s once without --nn-only first.\n' "$0" >&2
    exit 1
  }
  printf 'reusing gated controls: %s\n' "$results_root" >&2
else
  results_root="$results_dir_base/$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$results_root"
  rm -rf "$work_root"
  mkdir -p "$work_root"

  printf '== original ==\n' >&2
  copy_case "$work_root/original"
  run_case "$work_root/original" "${common_flags[@]}"
  archive_case original "$work_root/original" "$results_root"

  printf '== native_wrapper ==\n' >&2
  copy_case "$work_root/native_wrapper"
  generate_overlay "$work_root/native_wrapper"
  run_case "$work_root/native_wrapper" "${common_flags[@]}" \
    -DRISING_K_MODE=RISING_K_NATIVE \
    -I"$include_dir" -I"$model_include_dir" -I"$placeholder_model_dir"
  archive_case native_wrapper "$work_root/native_wrapper" "$results_root"

  printf '== native_perturbed ==\n' >&2
  copy_case "$work_root/native_perturbed"
  generate_overlay "$work_root/native_perturbed"
  run_case "$work_root/native_perturbed" "${common_flags[@]}" \
    -DRISING_K_MODE=RISING_K_NATIVE_PERTURBED \
    -I"$include_dir" -I"$model_include_dir" -I"$placeholder_model_dir"
  archive_case native_perturbed "$work_root/native_perturbed" "$results_root"

  write_manifest "$results_root" original native_wrapper native_perturbed
fi

for model in "${nn_models[@]}"; do
  label="nn_${model}"
  printf '== %s ==\n' "$label" >&2
  work_dir="$work_root/$label"
  copy_case "$work_dir"
  generate_overlay "$work_dir"
  run_case "$work_dir" "${common_flags[@]}" \
    -DRISING_K_MODE=RISING_K_NN_RAW \
    -DRISING_K_CLAMP_FACTOR=1.0 \
    -I"$include_dir" -I"$model_include_dir" \
    -I"$repo_root/dataset/model/c_exports/$model"
  archive_case "$label" "$work_dir" "$results_root"
done

if [ "$nn_only" -eq 1 ] && [ "${#nn_models[@]}" -gt 0 ]; then
  nn_labels=()
  for model in "${nn_models[@]}"; do
    nn_labels+=("nn_${model}")
  done
  addendum="$results_root/nn_only_run_$(date -u +%Y%m%dT%H%M%SZ).json"
  modes_json="$(printf '"%s",' "${nn_labels[@]}" | sed 's/,$//')"
  cat > "$addendum" <<JSON
{
  "nn_only": true,
  "modes_added": [${modes_json}],
  "source_fingerprint": "${source_fingerprint}"
}
JSON
fi

echo "$results_root"
