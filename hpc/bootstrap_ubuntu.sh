#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
  printf 'error: bootstrap requires Ubuntu 22.04 x86_64\n' >&2
  exit 2
fi
. /etc/os-release
if [ "${ID:-}" != ubuntu ] || [ "${VERSION_ID:-}" != 22.04 ]; then
  printf 'error: bootstrap requires Ubuntu 22.04, got %s %s\n' "${ID:-unknown}" "${VERSION_ID:-unknown}" >&2
  exit 2
fi

sudo_cmd=()
if [ "$(id -u)" -ne 0 ]; then
  if ! command -v sudo >/dev/null 2>&1; then
    printf 'error: bootstrap requires root or sudo\n' >&2
    exit 2
  fi
  sudo_cmd=(sudo)
fi

"${sudo_cmd[@]}" apt-get update
"${sudo_cmd[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git build-essential gawk bison python3 python3-pytest time jq \
  numactl util-linux ca-certificates file

cd "$repo_root/basilisk/src"
if [ -L config ] || [ -e config ]; then
  rm -f config
fi
ln -s config.gcc config
make -C ast clean
make -C ast
rm -f qcc include.o postproc.o
make qcc

file qcc
file qcc | grep -q 'ELF 64-bit.*x86-64'
./qcc --version >/dev/null 2>&1 || true
printf 'bootstrap PASS: %s\n' "$repo_root"
