#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
out_dir="$repo_root/dataset/official_data/capwave/figures/author_style"

mkdir -p "$out_dir"
gnuplot -e "ROOT='$repo_root'" "$script_dir/plot_capwave.gnuplot"

printf 'Wrote capwave author-style figures to %s\n' "$out_dir"
