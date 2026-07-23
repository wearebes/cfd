#!/usr/bin/env bash
set -euo pipefail

# Canonical entrypoint for the reviewed 397-row formal / 56-row smoke
# campaign.  The single matrix definition lives in _shared/campaign.py so
# plan, check, smoke, formal and verify cannot drift apart.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
if [ -n "${CFD_PYTHON:-}" ]; then
  python="$CFD_PYTHON"
elif [ -x "$repo_root/build/wsl-venv/bin/python" ]; then
  python="$repo_root/build/wsl-venv/bin/python"
else
  python=python3
fi
if [ -z "${BASILISK_QCC:-}" ] && \
   [ -x "$repo_root/build/wsl-toolchain/basilisk/src/qcc" ]; then
  export BASILISK_QCC="$repo_root/build/wsl-toolchain/basilisk/src/qcc"
fi
exec "$python" "$script_dir/_shared/campaign.py" "$@"
