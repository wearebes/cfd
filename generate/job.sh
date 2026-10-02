#!/usr/bin/env bash
set -euo pipefail

# Canonical entrypoint for the reviewed 397-row formal / 56-row smoke
# campaign.  The single matrix definition lives in _shared/campaign.py so
# plan, check, smoke, formal and verify cannot drift apart.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
python="${CFD_PYTHON:-python3}"
if [ -z "${BASILISK_QCC:-}" ] && \
   [ -x "$repo_root/build/linux-toolchain/basilisk/src/qcc" ]; then
  export BASILISK_QCC="$repo_root/build/linux-toolchain/basilisk/src/qcc"
fi
exec "$python" "$script_dir/_shared/campaign.py" "$@"
