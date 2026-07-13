#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  printf 'usage: %s MATRIX_ID [POLICY_FILE]\n' "$0" >&2
  exit 2
fi
matrix_id="$1"
policy="${2:-$repo_root/hpc/config/thread_policy.json}"
result_root="$repo_root/hpc/results/$matrix_id"
package_root="$repo_root/hpc/packages"
package="$package_root/cfd_hpc_180_${matrix_id}.tar.gz"

python3 "$script_dir/verify_matrix.py" --matrix-id "$matrix_id" --phase all --policy "$policy"
test -f "$result_root/SHA256SUMS"
mkdir -p "$package_root"
if [ -e "$package" ] || [ -e "$package.sha256" ]; then
  printf 'error: refusing to overwrite existing package %s\n' "$package" >&2
  exit 1
fi

python3 "$script_dir/package_results.py" "$result_root" "$package"
