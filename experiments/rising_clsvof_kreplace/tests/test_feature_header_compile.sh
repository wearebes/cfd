#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cp "$repo_root/basilisk/src/test/rising.c" "$tmpdir/rising-clsvof.c"

/opt/anaconda3/envs/pinn/bin/python \
  "$repo_root/experiments/rising_clsvof_kreplace/make_overlay_integral.py" \
  "$repo_root/basilisk/src/integral.h" \
  "$tmpdir/integral.h"

include_dir="$repo_root/experiments/rising_clsvof_kreplace/include"
model_dir="$repo_root/dataset/model/c_exports/baseline_128_hgradient"
model_include_dir="$repo_root/tools/clsvof_model/include"

# qcc resolves #include lines by scanning source text, not by evaluating
# #if, so nn_weights.h/clsvof_mlp_infer.h must be resolvable even for
# modes whose RISING_K_MODE never selects the NN branch. See README.md.
echo "== compiling native mode =="
(
  cd "$tmpdir"
  "$repo_root/tools/basilisk-cc" \
    -DLEVELSET=1 -DCLSVOF=1 \
    -DRISING_K_MODE=RISING_K_NATIVE \
    -I"$include_dir" \
    -I"$model_include_dir" \
    -I"$model_dir" \
    rising-clsvof.c \
    -o "$tmpdir/smoke_native" \
    -lm
)

echo "== compiling NN mode =="
(
  cd "$tmpdir"
  "$repo_root/tools/basilisk-cc" \
    -DLEVELSET=1 -DCLSVOF=1 \
    -DRISING_K_MODE=RISING_K_NN_RAW \
    -I"$include_dir" \
    -I"$model_include_dir" \
    -I"$model_dir" \
    rising-clsvof.c \
    -o "$tmpdir/smoke_nn" \
    -lm
)

echo "== negative control: compiling without -I<include dir> must FAIL =="
set +e
(
  cd "$tmpdir"
  "$repo_root/tools/basilisk-cc" \
    -DLEVELSET=1 -DCLSVOF=1 \
    -DRISING_K_MODE=RISING_K_NATIVE \
    -I"$model_include_dir" \
    -I"$model_dir" \
    rising-clsvof.c \
    -o "$tmpdir/smoke_negative" \
    -lm
) >"$tmpdir/negative.log" 2>&1
negative_status=$?
set -e

if [ "$negative_status" -eq 0 ]; then
  echo "NEGATIVE CONTROL FAIL: compile succeeded without -I<include dir>; overlay include precedence is broken" >&2
  cat "$tmpdir/negative.log" >&2
  exit 1
fi
if ! grep -q "rising_k_provider.h" "$tmpdir/negative.log"; then
  echo "NEGATIVE CONTROL FAIL: compile failed but not due to missing rising_k_provider.h" >&2
  cat "$tmpdir/negative.log" >&2
  exit 1
fi
echo "negative control OK: $(grep -m1 "rising_k_provider.h" "$tmpdir/negative.log")"

echo "ALL SMOKE CHECKS PASSED"
