#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
manifest_tool="$repo_root/generate/_shared/run_manifest.py"

benchmark_case=1
resolution=64
purpose=smoke
output=""
dry_run=0
compile_only=0
threads=1

usage() {
  printf '%s\n' \
    "usage: $0 --case 1|2 [--resolution 64|128|256|512]" \
    "          [--smoke|--formal] --output PATH [--threads 1]" \
    "          [--dry-run] [--compile-only]"
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --case) benchmark_case="${2:?missing value for --case}"; shift 2 ;;
    --resolution) resolution="${2:?missing value for --resolution}"; shift 2 ;;
    --smoke) purpose=smoke; shift ;;
    --formal) purpose=formal; shift ;;
    --output) output="${2:?missing value for --output}"; shift 2 ;;
    --threads) threads="${2:?missing value for --threads}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --compile-only) compile_only=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'error: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done
case "$benchmark_case" in 1|2) ;; *) printf 'error: --case must be 1 or 2\n' >&2; exit 2;; esac
case "$resolution" in
  64) level=6 ;; 128) level=7 ;; 256) level=8 ;; 512) level=9 ;;
  *) printf 'error: invalid --resolution\n' >&2; exit 2 ;;
esac
if [ "$threads" != 1 ]; then printf 'error: official stock reference is single-threaded\n' >&2; exit 2; fi
if [ -z "$output" ]; then printf 'error: --output is required\n' >&2; exit 2; fi

benchmark="rising_case${benchmark_case}"
benchmark_case_name="hysing_case_${benchmark_case}"
actual_grid="${resolution}x$((resolution / 4))"
output_parent="$(dirname "$output")"
if [ "$dry_run" -eq 0 ]; then mkdir -p "$output_parent"; fi
if [ -d "$output_parent" ]; then output="$(cd "$output_parent" && pwd)/$(basename "$output")"; fi
if [ "$dry_run" -eq 0 ] && [ -e "$output" ]; then printf 'error: output already exists: %s\n' "$output" >&2; exit 1; fi
if [ "$dry_run" -eq 1 ]; then
  work="$(mktemp -d "${TMPDIR:-/tmp}/cfd-rising-official-plan.XXXXXX")"
else
  work="$repo_root/tem/rising_bubble/case${benchmark_case}/official/_work/$(basename "$output").$$"
  mkdir -p "$output/source_snapshot" "$work"
fi
cleanup() {
  status=$?; trap - EXIT
  if [ "$dry_run" -eq 1 ]; then
    case "$work" in "${TMPDIR:-/tmp}"/cfd-rising-official-plan.*) rm -rf "$work" ;; esac
  elif [ "$status" -ne 0 ] && [ -f "$output/manifest.json" ]; then
    python3 "$manifest_tool" fail --manifest "$output/manifest.json" --error "runner exited with status $status" || true
  fi
  exit "$status"
}
trap cleanup EXIT
cp "$repo_root/basilisk/src/test/rising.c" "$work/rising.c"
compile_cmd=("$repo_root/basilisk/src/qcc" -O2 "-DLEVEL=$level")
if [ "$benchmark_case" -eq 2 ]; then compile_cmd+=("-DCASE2=1"); fi
compile_cmd+=(rising.c -o rising-official -lm)
run_cmd=(./rising-official)
if [ "$compile_only" -eq 1 ]; then run_cmd=(); fi
plan_args=(
  --repo-root "$repo_root" --case rising_bubble --benchmark "$benchmark"
  --method official --purpose "$purpose" --output "$output"
  --generator "$script_dir/official.sh" --generator-logical generate/rising_bubble/official.sh
  --parameter "benchmark_case=$benchmark_case_name" --parameter "resolution=$resolution"
  --parameter "level=$level" --parameter "actual_grid=$actual_grid"
  --parameter imax=null --parameter model=null --parameter openmp_threads=1
  --parameter "compile_only=$compile_only"
  --source "stock_case=basilisk/src/test/rising.c::$work/rising.c"
  --source "qcc=basilisk/src/qcc::$repo_root/basilisk/src/qcc"
  --compile-cwd '$WORK' --run-cwd '$WORK' --run-stdout stdout.txt --run-stderr log
)
for arg in "${compile_cmd[@]}"; do plan_args+=("--compile-arg=$arg"); done
if [ "$compile_only" -eq 0 ]; then
  for arg in "${run_cmd[@]}"; do plan_args+=("--run-arg=$arg"); done
fi
if [ "$dry_run" -eq 1 ]; then python3 "$manifest_tool" dry-run "${plan_args[@]}"; exit 0; fi
cp "$work/rising.c" "$output/source_snapshot/"
python3 "$manifest_tool" start "${plan_args[@]}" --manifest "$output/manifest.json"
SECONDS=0
(cd "$work"; "${compile_cmd[@]}" > compile.stdout 2> compile.stderr)
cp "$work/compile.stdout" "$work/compile.stderr" "$output/"
if [ "$compile_only" -eq 0 ]; then
  (cd "$work"; "${run_cmd[@]}" > stdout.txt 2> log)
  python3 - "$work/stdout.txt" <<'PY'
import sys
from pathlib import Path
times = []
for line in Path(sys.argv[1]).read_text().splitlines():
    try:
        times.append(float(line.split()[0]))
    except (IndexError, ValueError):
        pass
if not times or abs(times[-1] - 3.0) > 1e-9:
    raise SystemExit("official rising output did not reach t=3")
PY
  test -s "$work/log"
  cp "$work/stdout.txt" "$work/log" "$output/"
fi
python3 "$manifest_tool" complete "${plan_args[@]}" \
  --manifest "$output/manifest.json" --elapsed-seconds "$SECONDS"
trap - EXIT
printf '%s\n' "$output"
printf 'work: %s\n' "$work" >&2
