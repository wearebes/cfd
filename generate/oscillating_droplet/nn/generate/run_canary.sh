#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../../.." && pwd)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
root="$repo_root/tem/oscillating_droplet/nn_canary/$stamp"

python3 "$script_dir/run_row.py" --method clsvof --resolution 64 --smoke \
  --threads 1 --t-end 0.02 --no-fit \
  --output "$root/level_6_clsvof"
python3 "$script_dir/run_row.py" --method probe --resolution 64 --smoke \
  --threads 1 --t-end 0.02 --no-fit \
  --output "$root/level_6_probe"
python3 "$script_dir/run_row.py" --method nn --resolution 64 --smoke \
  --threads 1 --t-end 0.02 --no-fit \
  --output "$root/level_6_active"
printf '%s\n' "$root"
