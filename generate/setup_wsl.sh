#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
printf 'note: setup_wsl.sh is retained as a compatibility alias; using setup_linux.sh\n' >&2
exec "$script_dir/setup_linux.sh" "$@"
