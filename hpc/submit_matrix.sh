#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

cpus=128
matrix_id="formal_180_$(date -u +%Y%m%dT%H%M%SZ)"
resume=0
max_active_rows=1
policy="$repo_root/hpc/config/thread_policy.json"

usage() {
  printf 'usage: %s [--cpus N] [--matrix-id ID] [--policy FILE] [--max-active-rows N] [--resume]\n' "$0"
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --cpus) cpus="${2:?missing value for --cpus}"; shift 2 ;;
    --matrix-id) matrix_id="${2:?missing value for --matrix-id}"; shift 2 ;;
    --policy) policy="${2:?missing value for --policy}"; shift 2 ;;
    --max-active-rows) max_active_rows="${2:?missing value for --max-active-rows}"; shift 2 ;;
    --resume) resume=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'error: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done
case "$cpus" in ''|*[!0-9]*|0)
  printf 'error: --cpus must be a positive integer\n' >&2; exit 2;; esac
case "$max_active_rows" in ''|*[!0-9]*|0)
  printf 'error: --max-active-rows must be a positive integer\n' >&2; exit 2;; esac
case "$matrix_id" in *[!A-Za-z0-9_.-]*|'')
  printf 'error: --matrix-id contains unsafe characters\n' >&2; exit 2;; esac

lock="$repo_root/hpc/work/.submit_${matrix_id}.lock"
mkdir -p "$(dirname "$lock")"
if ! mkdir "$lock" 2>/dev/null; then
  printf 'error: submit lock already exists: %s\n' "$lock" >&2
  exit 1
fi
trap 'rmdir "$lock" 2>/dev/null || true' EXIT

python3 "$script_dir/preflight_hpc.py" --matrix-id "$matrix_id" --cpus "$cpus" --policy "$policy"
python3 "$script_dir/run_canaries.py" --matrix-id "$matrix_id" --cpus "$cpus" --policy "$policy"
python3 - "$repo_root/hpc/results/$matrix_id/platform/capacity.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("status") != "PASS" or not payload.get("measured_openmp_scaling"):
    raise SystemExit("capacity canary did not produce a measured PASS")
PY
dry_run_file="$repo_root/hpc/results/$matrix_id/matrix_dry_run.jsonl"
python3 "$script_dir/run_matrix.py" --matrix-id "$matrix_id" --cpus "$cpus" --policy "$policy" \
  --max-active-rows "$max_active_rows" --phase all --dry-run \
  > "$dry_run_file"

# Gate on the dry-run inline: 180 row lines + 1 summary line, and a summary
# that reports the full 180-row contract. Fails loudly if the matrix drifts.
if [ "$(wc -l < "$dry_run_file")" -ne 181 ]; then
  printf 'error: 180-row dry-run did not produce 181 lines\n' >&2
  exit 1
fi
tail -n 1 "$dry_run_file" | jq -e '.row_count == 180' >/dev/null

resume_args=()
if [ "$resume" -eq 1 ]; then resume_args+=("--resume"); fi

python3 "$script_dir/run_matrix.py" --matrix-id "$matrix_id" --cpus "$cpus" --policy "$policy" \
  --max-active-rows "$max_active_rows" \
  --phase n64 ${resume_args[@]+"${resume_args[@]}"}
python3 "$script_dir/verify_matrix.py" --matrix-id "$matrix_id" --phase n64 --policy "$policy"
python3 "$script_dir/run_matrix.py" --matrix-id "$matrix_id" --cpus "$cpus" --policy "$policy" \
  --max-active-rows "$max_active_rows" \
  --phase remaining ${resume_args[@]+"${resume_args[@]}"}
python3 "$script_dir/verify_matrix.py" --matrix-id "$matrix_id" --phase all --policy "$policy"
bash "$script_dir/collect_results.sh" "$matrix_id" "$policy"
