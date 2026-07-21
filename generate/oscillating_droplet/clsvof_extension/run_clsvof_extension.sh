#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
official="$repo_root/hpc/results/oscillating_droplet/official_reproduction"
output="$repo_root/hpc/results/oscillating_droplet/clsvof_extension"
figure_output="$repo_root/figures/oscillating_droplet/clsvof_extension"

for required in \
  "$official/manifest.json" \
  "$repo_root/basilisk/src/qcc" \
  "$script_dir/oscillation-clsvof.c"; do
  test -e "$required" || { printf 'missing required input: %s\n' "$required" >&2; exit 1; }
done
if [ -e "$output" ] || [ -e "$figure_output" ]; then
  printf 'error: extension output already exists\n' >&2
  exit 1
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
work="$repo_root/tem/oscillating_droplet/clsvof_extension_$stamp"
dataset_staging="$repo_root/hpc/results/oscillating_droplet/.clsvof_extension.staging.$$"
figure_staging="$repo_root/figures/oscillating_droplet/.clsvof_extension.staging.$$"
mkdir -p "$work" "$dataset_staging/clsvof" "$figure_staging"

cp "$script_dir/oscillation-clsvof.c" "$work/oscillation-clsvof.c"
export BASILISK="$repo_root/basilisk/src"
compile_command="$BASILISK/qcc -O2 -DMTRACE=3 -g -Wall -Wno-unused-function -pipe oscillation-clsvof.c -o oscillation-clsvof -lm"
printf '%s\n' "$compile_command" > "$work/command.txt"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
started_epoch="$(date +%s)"
(
  cd "$work"
  "$BASILISK/qcc" -O2 -DMTRACE=3 -g -Wall -Wno-unused-function -pipe \
    oscillation-clsvof.c -o oscillation-clsvof -lm \
    > compile.stdout.txt 2> compile.stderr.txt
  ./oscillation-clsvof > out 2> log
)
ended_epoch="$(date +%s)"
ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
wall_seconds="$((ended_epoch - started_epoch))"

for level in 4 5 6 7; do
  test -s "$work/k-$level"
  test -s "$work/fit-$level"
done
for artifact in error laplace out log; do
  test -s "$work/$artifact"
done
test "$(grep -c '^fit ' "$work/log")" -eq 4

cp -a "$work/." "$dataset_staging/clsvof/"
printf '%s\n' \
  "started_at=$started_at" \
  "ended_at=$ended_at" \
  "wall_seconds=$wall_seconds" \
  "run_exit_status=0" \
  > "$dataset_staging/execution_status.txt"

python3 "$script_dir/build_extension_report.py" \
  --repo "$repo_root" --dataset "$dataset_staging" --official "$official" \
  --command "$compile_command && ./oscillation-clsvof > out 2> log" \
  --started-at "$started_at" --ended-at "$ended_at" \
  --wall-seconds "$wall_seconds"

cp "$script_dir/plot_frequency_error_four_methods.gp" "$figure_staging/"
gnuplot \
  -e "output_file='$figure_staging/frequency_error_four_methods.png'" \
  -e "standard_file='$official/standard/error'" \
  -e "momentum_file='$official/momentum/error'" \
  -e "compressible_file='$official/compressible/error'" \
  -e "clsvof_file='$dataset_staging/clsvof/error'" \
  "$script_dir/plot_frequency_error_four_methods.gp" \
  > "$figure_staging/plot.stdout.txt" \
  2> "$figure_staging/plot.stderr.txt"
test -s "$figure_staging/frequency_error_four_methods.png"
printf '%s\n' \
  "gnuplot_version=$(gnuplot --version)" \
  "render_exit_status=0" \
  > "$figure_staging/render_status.txt"

mkdir -p "$(dirname "$output")" "$(dirname "$figure_output")"
mv "$dataset_staging" "$output"
mv "$figure_staging" "$figure_output"
printf '%s\n' "$output" "$figure_output"
printf 'work retained: %s\n' "$work" >&2
