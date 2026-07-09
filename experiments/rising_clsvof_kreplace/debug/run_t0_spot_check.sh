#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exp_dir="$(cd "$script_dir/.." && pwd)"
repo_root="$(cd "$exp_dir/../.." && pwd)"
python_bin="/opt/anaconda3/envs/pinn/bin/python"

src_case="$repo_root/basilisk/src/test/rising.c"
src_integral="$repo_root/basilisk/src/integral.h"
debug_include_dir="$script_dir/include"
model_include_dir="$repo_root/tools/clsvof_model/include"
model_name="${1:-baseline_128_hgradient}"
model_dir="$repo_root/dataset/model/c_exports/$model_name"

work_dir="$script_dir/work_t0"
rm -rf "$work_dir"
mkdir -p "$work_dir"

cp "$src_case" "$work_dir/rising-clsvof.c"
"$python_bin" "$exp_dir/make_overlay_integral.py" "$src_integral" "$work_dir/integral.h"

printf 'compiling+running t=0 spot check against %s (this reuses the NN-mode nn_weights.h, expect several CPU-minutes to compile)\n' "$model_name" >&2

(
  cd "$work_dir"
  "$repo_root/tools/basilisk-run" \
    -DLEVELSET=1 -DCLSVOF=1 \
    -DRISING_K_MODE=RISING_K_NN_RAW \
    -DRISING_K_CLAMP_FACTOR=1.0 \
    -I"$debug_include_dir" -I"$exp_dir/include" -I"$model_include_dir" -I"$model_dir" \
    rising-clsvof.c > out 2> log_full
)

grep '^T0SPOT ' "$work_dir/log_full" > "$work_dir/t0_spot_check.txt" || true
echo "$work_dir/t0_spot_check.txt"
