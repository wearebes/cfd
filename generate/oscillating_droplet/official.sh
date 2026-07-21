#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
manifest_tool="$repo_root/generate/_shared/run_manifest.py"
report_builder="$script_dir/official/build_official_report.py"

output=""
purpose=smoke
threads=1
dry_run=0

usage() {
  printf '%s\n' \
    "usage: $0 [--smoke|--formal] --output PATH [--threads 1] [--dry-run]" \
    "" \
    "Runs the immutable official Basilisk oscillation suite at its native" \
    "LEVEL 4..7 grid set. Resolution and numerical parameters are intentionally" \
    "not exposed because that would no longer be the official reference."
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --smoke) purpose=smoke; shift ;;
    --formal) purpose=formal; shift ;;
    --output) output="${2:?missing value for --output}"; shift 2 ;;
    --threads) threads="${2:?missing value for --threads}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'error: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$output" ]; then
  printf 'error: --output is required\n' >&2; usage >&2; exit 2
fi
if [ "$threads" != 1 ]; then
  printf 'error: the official oscillation reference is locked to --threads 1\n' >&2
  exit 2
fi
output_parent="$(dirname "$output")"
if [ ! -d "$output_parent" ] && [ "$dry_run" -eq 0 ]; then mkdir -p "$output_parent"; fi
if [ -d "$output_parent" ]; then
  output="$(cd "$output_parent" && pwd)/$(basename "$output")"
fi
if [ "$dry_run" -eq 0 ] && [ -e "$output" ]; then
  printf 'error: output already exists: %s\n' "$output" >&2; exit 1
fi

source_files=(
  basilisk/src/test/oscillation.c
  basilisk/src/test/Makefile
  basilisk/src/test/oscillation.ref
  basilisk/src/test/oscillation-momentum.ref
  basilisk/src/test/oscillation-compressible.ref
)
compile_cmd=(make -o Makefile.deps oscillation.tst)
recovery_contract=(
  "make -o Makefile.deps oscillation-momentum.tst if incomplete"
  "make -o Makefile.deps oscillation-compressible.tst if incomplete"
  "make -o Makefile.deps oscillation.s and official runtest if standard is incomplete"
)

plan_args=(
  --repo-root "$repo_root"
  --case oscillating_droplet --benchmark oscillating_droplet_official
  --method official --purpose "$purpose" --output "$output"
  --generator "$script_dir/official.sh"
  --generator-logical generate/oscillating_droplet/official.sh
  --parameter 'levels=[4,5,6,7]'
  --parameter 'resolutions=[16,32,64,128]'
  --parameter 'openmp_threads=1'
  --parameter 'source_mutation=false'
  --parameter 'recovery_contract=["make momentum if incomplete","make compressible if incomplete","official runtest standard if incomplete"]'
  --compile-cwd '$MIRROR/basilisk/src/test'
  --compile-stdout make.stdout.txt --compile-stderr make.stderr.txt
  --run-cwd '$MIRROR/basilisk/src/test'
  --run-stdout recovery.stdout.txt --run-stderr recovery.stderr.txt
)
for relative in "${source_files[@]}"; do
  label="$(basename "$relative" | tr '.-' '__')"
  plan_args+=(--source "$label=source_snapshot/$(basename "$relative")::$repo_root/$relative")
done
for arg in "${compile_cmd[@]}"; do plan_args+=("--compile-arg=$arg"); done
for arg in "${recovery_contract[@]}"; do plan_args+=("--run-arg=$arg"); done

if [ "$dry_run" -eq 1 ]; then
  python3 "$manifest_tool" dry-run "${plan_args[@]}"
  exit 0
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
work_root="$repo_root/tem/oscillating_droplet/official_mirror_$stamp.$$"
mirror_basilisk="$work_root/basilisk"
mirror_src="$mirror_basilisk/src"
mirror_test="$mirror_src/test"
mkdir -p "$output/source_snapshot" "$work_root"
cp -a "$repo_root/basilisk" "$mirror_basilisk"
chmod +x "$mirror_src/runtest"
printf '%s\n' \
  "restored executable bit on mirror src/runtest; official bytes unchanged" \
  > "$output/mirror_setup.txt"
for relative in "${source_files[@]}"; do
  cp "$repo_root/$relative" "$output/source_snapshot/"
done
printf '%s\n' "${compile_cmd[*]}" > "$output/command.txt"
printf '%s\n' "${recovery_contract[@]}" > "$output/recovery_plan.txt"
printf '%s\n' "$work_root" > "$output/mirror_path.txt"

hash_inputs() {
  local relative
  for relative in "${source_files[@]}"; do
    printf '%s  %s\n' \
      "$(openssl dgst -sha256 "$repo_root/$relative" | awk '{print $NF}')" \
      "$repo_root/$relative"
  done
}

hash_inputs > "$output/source_hashes_before.txt"
python3 "$manifest_tool" start "${plan_args[@]}" --manifest "$output/manifest.json"
manifest_started=1
cleanup() {
  status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "${manifest_started:-0}" -eq 1 ]; then
    python3 "$manifest_tool" fail --manifest "$output/manifest.json" \
      --error "runner exited with status $status" || true
    printf 'failed output retained at %s; mirror retained at %s\n' "$output" "$work_root" >&2
  fi
  exit "$status"
}
trap cleanup EXIT

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
started_epoch="$(date +%s)"
set +e
(
  cd "$mirror_test"
  "${compile_cmd[@]}"
) > "$output/make.stdout.txt" 2> "$output/make.stderr.txt"
make_status=$?
set -e

method_complete() {
  local directory="$1"
  local level
  for level in 4 5 6 7; do
    test -s "$directory/k-$level" || return 1
    test -s "$directory/fit-$level" || return 1
  done
  test -f "$directory/error" -a -f "$directory/laplace" \
    -a -f "$directory/out" -a -f "$directory/log"
}

recovery_log="$output/recovery_commands.txt"
: > "$recovery_log"
: > "$output/recovery_status.txt"
run_make_recovery() {
  local target="$1"
  printf 'make -o Makefile.deps %s\n' "$target" >> "$recovery_log"
  set +e
  (
    cd "$mirror_test"
    make -o Makefile.deps "$target"
  ) >> "$output/make.stdout.txt" 2>> "$output/make.stderr.txt"
  local status=$?
  set -e
  printf '%s=%s\n' "$target" "$status" >> "$output/recovery_status.txt"
}

if ! method_complete "$mirror_test/oscillation-momentum"; then
  run_make_recovery oscillation-momentum.tst
fi
if ! method_complete "$mirror_test/oscillation-compressible"; then
  run_make_recovery oscillation-compressible.tst
fi
if ! method_complete "$mirror_test/oscillation"; then
  printf '%s\n' \
    "official aggregate target did not reach the standard branch; using the official qcc/runtest recipe" \
    >> "$recovery_log"
  set +e
  (
    cd "$mirror_test"
    make -o Makefile.deps oscillation.s
    BASILISK="$mirror_src" \
      CFLAGS="-O2 -DMTRACE=3 -g -Wall -Wno-unused-function -pipe" \
      PNG=pngcairo LIBS="" OPENGLIBS="-lfb_tiny" GDB="" \
      "$mirror_src/runtest" oscillation.tst
  ) >> "$output/make.stdout.txt" 2>> "$output/make.stderr.txt"
  recovery_standard_status=$?
  set -e
  printf 'oscillation-official-runtest=%s\n' "$recovery_standard_status" \
    >> "$output/recovery_status.txt"
fi

ended_epoch="$(date +%s)"
ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
wall_seconds="$((ended_epoch - started_epoch))"
for spec in standard:oscillation momentum:oscillation-momentum compressible:oscillation-compressible; do
  name="${spec%%:*}"
  source_name="${spec#*:}"
  if [ -d "$mirror_test/$source_name" ]; then cp -a "$mirror_test/$source_name" "$output/$name"; fi
done
hash_inputs > "$output/source_hashes_after.txt"
printf '%s\n' \
  "aggregate_make_exit_status=$make_status" \
  "started_at=$started_at" \
  "ended_at=$ended_at" \
  "wall_seconds=$wall_seconds" \
  > "$output/execution_status.txt"

python3 "$report_builder" \
  --repo "$repo_root" --dataset "$output" --mirror "$work_root" \
  --make-exit-status "$make_status" --started-at "$started_at" \
  --ended-at "$ended_at" --wall-seconds "$wall_seconds"
python3 "$manifest_tool" complete "${plan_args[@]}" \
  --manifest "$output/manifest.json" --elapsed-seconds "$wall_seconds"

trap - EXIT
printf '%s\n' "$output"
printf 'mirror retained: %s\n' "$work_root" >&2
