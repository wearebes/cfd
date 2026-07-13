#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

if [ "$#" -gt 1 ]; then
  printf 'usage: %s [OUTPUT.tar.gz]\n' "$0" >&2
  exit 2
fi
package="${1:-$repo_root/hpc/packages/cfd-hpc-runner.tar.gz}"
python3 "$script_dir/package_deployment.py" "$package"
