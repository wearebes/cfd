#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../../.." && pwd)"
run_id="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
root="$repo_root/hpc/results/oscillating_droplet/nn_matched/$run_id"
test ! -e "$root" || { printf 'output exists: %s\n' "$root" >&2; exit 1; }

for level in 6 7; do
  resolution="$((1 << level))"
  python3 "$script_dir/run_row.py" --method clsvof --resolution "$resolution" \
    --formal --threads 1 \
    --output "$root/level_${level}/clsvof"
  python3 "$script_dir/run_row.py" --method nn --resolution "$resolution" \
    --formal --threads 1 \
    --output "$root/level_${level}/nn"
done
printf '%s\n' "$root"
