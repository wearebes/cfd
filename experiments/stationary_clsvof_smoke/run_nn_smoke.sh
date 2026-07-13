#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exp="$root/experiments/stationary_clsvof_smoke"
offset="$root/experiments/clsvof_kappa_offset_conversion"
controls="${STATIONARY_CONTROL_RESULT:-$exp/results/20260711T082337Z}"
out="$exp/results/$(date -u +%Y%m%dT%H%M%SZ)_nn_cell_offset"
mode="clsvof_nn_cell_offset_64"
work="$exp/work/$(basename "$out")/$mode"

mkdir -p "$work" "$out/$mode"
cp "$exp/stationary-clsvof.c" "$work/"
cp "$offset/include/clsvof_nn_cell_curvature.h" "$work/"
python3 "$offset/make_overlay_integral.py" \
  "$root/basilisk/src/integral.h" "$work/integral.h"

(
  cd "$work"
  "$root/basilisk/src/qcc" -disable-dimensions \
    -I"$root/tools/clsvof_model/include" \
    -I"$root/dataset/model/c_exports/baseline_64_hgradient" \
    stationary-clsvof.c -o stationary-clsvof -lm
  ./stationary-clsvof > stdout.txt 2> log
)

cp "$work/La-12000-6" "$work/log" "$work/stdout.txt" \
  "$work/integral.h" "$work/clsvof_nn_cell_curvature.h" \
  "$out/$mode/"
python3 "$exp/summarize_smoke.py" "$out"

python3 - "$controls/summary.csv" "$out/summary.csv" "$out/comparison_summary.csv" <<'PY'
import csv
import sys

rows = []
for path in sys.argv[1:3]:
    with open(path, newline="", encoding="utf-8") as handle:
        rows.extend(csv.DictReader(handle))
with open(sys.argv[3], "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
PY

echo "$out"
