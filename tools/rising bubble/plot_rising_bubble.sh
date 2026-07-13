#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
out_dir="$repo_root/dataset/official_data/rising_bubble/figures/author_style"

mkdir -p "$out_dir"
gnuplot -e "ROOT='$repo_root'" "$script_dir/plot_rising_bubble.gnuplot"

printf 'Wrote rising-bubble author-style figures to %s\n' "$out_dir"
