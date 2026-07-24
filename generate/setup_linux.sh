#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
toolchain_root="$repo_root/build/linux-toolchain"
venv="$repo_root/build/linux-venv"
install=0

usage() {
  printf '%s\n' \
    "usage: $0 [--check|--install]" \
    "" \
    "--check    inspect the Linux host without changing it (default)" \
    "--install  install apt packages, Python requirements and a Linux qcc"
}

case "${1:---check}" in
  --check) ;;
  --install) install=1 ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

if [ "$(uname -s)" != Linux ]; then
  printf 'error: solver setup requires Linux\n' >&2
  exit 2
fi

packages=(bison build-essential diffutils flex gawk git gnuplot-nox procps python3 python3-pip python3-venv rsync sysstat time util-linux)
if [ "$install" -eq 1 ]; then
  apt_prefix=()
  if [ "$(id -u)" -ne 0 ]; then
    if ! command -v sudo >/dev/null 2>&1; then
      printf 'error: package installation requires root or sudo\n' >&2
      exit 1
    fi
    apt_prefix=(sudo)
  fi
  "${apt_prefix[@]}" apt-get update
  "${apt_prefix[@]}" apt-get install -y "${packages[@]}"
  python3 -m venv "$venv"
  "$venv/bin/python" -m pip install --upgrade pip
  "$venv/bin/python" -m pip install -r "$script_dir/requirements.txt"

  mkdir -p "$toolchain_root"
  rsync -a --delete --exclude qcc --exclude '*.o' --exclude '*.a' \
    "$repo_root/basilisk/" "$toolchain_root/basilisk/"
  # The source tree selects its macOS configuration through an absolute
  # symlink.  rsync preserves that link, which is dangling in a Linux clone;
  # replace it inside the ignored Linux-only toolchain before copying config.gcc.
  rm -f "$toolchain_root/basilisk/src/config"
  cp "$toolchain_root/basilisk/src/config.gcc" \
    "$toolchain_root/basilisk/src/config"
  # qcc links the AST archive, but the top-level Makefile deliberately does
  # not provide a rule that builds it.  Build the archive explicitly first.
  make -C "$toolchain_root/basilisk/src/ast"
  make -C "$toolchain_root/basilisk/src" -B qcc CC=gcc
fi

qcc="$toolchain_root/basilisk/src/qcc"
python="$venv/bin/python"
missing=0
for command in findmnt gcc gnuplot make rsync mpstat /usr/bin/time; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'missing command: %s\n' "$command" >&2
    missing=1
  fi
done
if [ ! -x "$python" ]; then
  printf 'missing Python environment: %s\n' "$python" >&2
  missing=1
fi
if [ ! -x "$qcc" ]; then
  printf 'missing Linux qcc: %s\n' "$qcc" >&2
  missing=1
fi
if [ "$missing" -ne 0 ]; then
  printf 'run: bash generate/setup_linux.sh --install\n' >&2
  exit 1
fi

repo_filesystem="$(findmnt -T "$repo_root" -n -o FSTYPE)"
case "$repo_filesystem" in
  9p|drvfs|fuseblk)
    printf 'error: repository filesystem %s is unsuitable for solver I/O\n' \
      "$repo_filesystem" >&2
    exit 2
    ;;
esac

logical_cpus="$(nproc)"
if [ "$logical_cpus" -lt 1 ]; then
  printf 'error: Linux reports no available CPUs\n' >&2
  exit 1
fi

probe_root="$(mktemp -d /tmp/cfd-linux-preflight.XXXXXX)"
case "$probe_root" in /tmp/cfd-linux-preflight.*) ;; *) exit 2 ;; esac
cleanup_probe() { rm -rf "$probe_root"; }
trap cleanup_probe EXIT
printf '%s\n' \
  '#include <omp.h>' \
  '#include <stdio.h>' \
  'int main(void) { int n = 0;' \
  '#pragma omp parallel reduction(+:n)' \
  '  n += 1;' \
  '  printf("%d\n", n); return 0; }' \
  > "$probe_root/openmp.c"
gcc -O2 -fopenmp "$probe_root/openmp.c" -o "$probe_root/openmp"
if [ "$(OMP_NUM_THREADS=2 "$probe_root/openmp")" != 2 ]; then
  printf 'error: GCC OpenMP runtime probe failed\n' >&2
  exit 1
fi
printf '%s\n' \
  '#include "grid/cartesian.h"' \
  'int main(void) { init_grid (8); return 0; }' \
  > "$probe_root/qcc_probe.c"
"$qcc" -O2 "$probe_root/qcc_probe.c" -o "$probe_root/qcc_probe" -lm
"$probe_root/qcc_probe"
"$python" -c 'import pytest'

distribution=Linux
if [ -r /etc/os-release ]; then
  . /etc/os-release
  distribution="${PRETTY_NAME:-Linux}"
fi
printf '%s\n' \
  "distribution=$distribution" \
  "kernel=$(uname -r)" \
  "repository=$repo_root" \
  "repository_filesystem=$repo_filesystem" \
  "logical_cpus=$logical_cpus" \
  "memory=$(free -h | awk '/^Mem:/ {print $2}')" \
  "gcc=$(gcc -dumpfullversion -dumpversion)" \
  "gnuplot=$(gnuplot --version)" \
  "python=$python" \
  "qcc=$qcc" \
  "qcc_sha256=$(sha256sum "$qcc" | awk '{print $1}')" \
  "openmp_probe=2_threads_ok" \
  "qcc_probe=ok" \
  "status=ready"

printf '\njob.sh will automatically use this Python environment and Linux qcc.\n'
