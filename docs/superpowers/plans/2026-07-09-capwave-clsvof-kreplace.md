# Capwave CLSVOF K Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce the stock `capwave-clsvof` experiment from outside the Basilisk source tree while changing only the cell-local curvature value `ki` used by `integral.h`.

**Architecture:** The implementation creates an external experiment workspace under `experiments/capwave_clsvof_kreplace/`. Each run copies the stock `basilisk/src/test/capwave-clsvof.c` and `prosperetti.h` into a temporary work directory, generates a local `integral.h` overlay from the stock `basilisk/src/integral.h`, and relies on C include precedence so the copied case uses the overlay. The overlay keeps the original surface-tension tensor and face-force path unchanged, replacing only `double ki = distance_curvature (point, d);` with `double ki = capwave_k_provider (point, d);`.

**Tech Stack:** Bash, Python 3 standard library, Basilisk `qcc` through `tools/basilisk-run`, C99 headers, generated float32 NN weights in `dataset/model/c_exports/`, and the existing `tools/clsvof_model_export/include/clsvof_mlp_infer.h`.

---

## Non-Negotiable Scope

- Do not create, modify, or delete files under `basilisk/`.
- Do not hand-write a new capwave case.
- The run source must be copied from `basilisk/src/test/capwave-clsvof.c` for each run.
- The surface-tension implementation must be copied from `basilisk/src/integral.h` for each run.
- The only semantic replacement in the generated `integral.h` overlay is the source of `ki`.
- First canary uses `dataset/model/c_exports/baseline_128_hgradient/nn_weights.h`.
- First canary keeps the original capwave sweep unless a compile/runtime failure requires a shorter debug run. If a shorter debug run is introduced, keep it in a separate debug script and do not call it the official canary.

## File Structure

Create these files:

```text
experiments/capwave_clsvof_kreplace/
  README.md
  make_overlay_integral.py
  run_canary.sh
  include/
    capwave_k_provider.h
    clsvof_nn_features.h
  tests/
    test_make_overlay_integral.py
    test_feature_header_compile.sh
  results/
    .gitkeep
```

Generated, untracked, or ignored run outputs:

```text
experiments/capwave_clsvof_kreplace/work/
  original/
    capwave-clsvof.c
    prosperetti.h
    capwave-clsvof
    log
    wave-16
    wave-32
    wave-64
    wave-128
  native_wrapper/
    capwave-clsvof.c
    prosperetti.h
    integral.h
    capwave-clsvof
    log
    wave-16
    wave-32
    wave-64
    wave-128
  nn_baseline_128_hgradient/
    capwave-clsvof.c
    prosperetti.h
    integral.h
    capwave-clsvof
    log
    wave-16
    wave-32
    wave-64
    wave-128
```

## Curvature Replacement Contract

Stock source location:

```c
double ki = distance_curvature (point, d);
```

Generated overlay replacement:

```c
double ki = capwave_k_provider (point, d);
```

Native wrapper mode:

```c
return distance_curvature (point, d);
```

NN mode:

```c
float raw[CLSVOF_NN_INPUT_DIM];
capwave_build_raw27 (point, d, raw);
float hkappa = clsvof_nn_predict_hkappa (raw);
double kappa = (double) hkappa/Delta;
double limit = CAPWAVE_K_CLAMP_FACTOR/Delta;
if (kappa > limit)
  kappa = limit;
else if (kappa < -limit)
  kappa = -limit;
return kappa;
```

The NN model output is `h*kappa`; the solver consumes `kappa`, so the conversion is `kappa = hkappa/Delta`.

---

### Task 1: Add Overlay Generator With Tests

**Files:**
- Create: `experiments/capwave_clsvof_kreplace/make_overlay_integral.py`
- Create: `experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py`

- [ ] **Step 1: Write the failing tests**

Create `experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py`:

```python
from pathlib import Path

from experiments.capwave_clsvof_kreplace.make_overlay_integral import build_overlay_text


def test_overlay_replaces_only_curvature_provider_line():
    source = """
static inline double distance_curvature (Point point, scalar d)
{
  return 0.;
}
#endif // CURVATURE

event acceleration (i++)
{
  double ki = distance_curvature (point, d);
}
"""
    output = build_overlay_text(source)

    assert "double ki = capwave_k_provider (point, d);" in output
    assert "double ki = distance_curvature (point, d);" not in output
    assert output.count('include "capwave_k_provider.h"') == 1
    assert output.index('include "capwave_k_provider.h"') > output.index("#endif // CURVATURE")


def test_overlay_rejects_missing_ki_line():
    source = "#endif // CURVATURE\n"
    try:
        build_overlay_text(source)
    except ValueError as exc:
        assert "expected exactly one curvature assignment" in str(exc)
    else:
        raise AssertionError("missing ki assignment was not rejected")


def test_overlay_rejects_ambiguous_ki_line():
    source = """
#endif // CURVATURE
double ki = distance_curvature (point, d);
double ki = distance_curvature (point, d);
"""
    try:
        build_overlay_text(source)
    except ValueError as exc:
        assert "expected exactly one curvature assignment" in str(exc)
    else:
        raise AssertionError("ambiguous ki assignment was not rejected")


def test_overlay_cli_writes_file(tmp_path: Path):
    src = tmp_path / "integral.h"
    dst = tmp_path / "generated_integral.h"
    src.write_text(
        "#endif // CURVATURE\n"
        "double ki = distance_curvature (point, d);\n",
        encoding="utf-8",
    )

    from experiments.capwave_clsvof_kreplace.make_overlay_integral import main

    assert main([str(src), str(dst)]) == 0
    assert dst.exists()
    assert "capwave_k_provider" in dst.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/pinn/bin/python -m pytest \
  experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py -q
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` because `make_overlay_integral.py` does not exist yet.

- [ ] **Step 3: Implement the overlay generator**

Create `experiments/capwave_clsvof_kreplace/make_overlay_integral.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TARGET = "double ki = distance_curvature (point, d);"
REPLACEMENT = "double ki = capwave_k_provider (point, d);"
INCLUDE_MARKER = "#endif // CURVATURE"
PROVIDER_INCLUDE = '#include "capwave_k_provider.h"'


def build_overlay_text(source: str) -> str:
    if source.count(TARGET) != 1:
        raise ValueError("expected exactly one curvature assignment in integral.h")
    if INCLUDE_MARKER not in source:
        raise ValueError("expected integral.h to contain the CURVATURE endif marker")

    output = source.replace(TARGET, REPLACEMENT, 1)
    output = output.replace(
        INCLUDE_MARKER,
        f"{INCLUDE_MARKER}\n\n{PROVIDER_INCLUDE}",
        1,
    )
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source.read_text(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_overlay_text(source), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
/opt/anaconda3/envs/pinn/bin/python -m pytest \
  experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add experiments/capwave_clsvof_kreplace/make_overlay_integral.py \
  experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py
git commit -m "test: add capwave integral overlay generator"
```

---

### Task 2: Add NN Feature and K Provider Headers

**Files:**
- Create: `experiments/capwave_clsvof_kreplace/include/clsvof_nn_features.h`
- Create: `experiments/capwave_clsvof_kreplace/include/capwave_k_provider.h`
- Create: `experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh`

- [ ] **Step 1: Write the compile smoke test**

Create `experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cat > "$tmpdir/header_smoke.c" <<'C'
#include "grid/multigrid.h"
#include "two-phase-clsvof.h"
#include "integral.h"

int main() {
  return 0;
}
C

/opt/anaconda3/envs/pinn/bin/python \
  "$repo_root/experiments/capwave_clsvof_kreplace/make_overlay_integral.py" \
  "$repo_root/basilisk/src/integral.h" \
  "$tmpdir/integral.h"

"$repo_root/tools/basilisk-cc" \
  -DCLSVOF=1 \
  -DCAPWAVE_K_MODE=CAPWAVE_K_NATIVE \
  -I"$tmpdir" \
  -I"$repo_root/experiments/capwave_clsvof_kreplace/include" \
  "$tmpdir/header_smoke.c" \
  -o "$tmpdir/header_smoke" \
  -lm

"$repo_root/tools/basilisk-cc" \
  -DCLSVOF=1 \
  -DCAPWAVE_K_MODE=CAPWAVE_K_NN_RAW \
  -I"$tmpdir" \
  -I"$repo_root/experiments/capwave_clsvof_kreplace/include" \
  -I"$repo_root/tools/clsvof_model_export/include" \
  -I"$repo_root/dataset/model/c_exports/baseline_128_hgradient" \
  "$tmpdir/header_smoke.c" \
  -o "$tmpdir/header_smoke_nn" \
  -lm
```

- [ ] **Step 2: Run smoke test to verify it fails**

Run:

```bash
bash experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh
```

Expected: FAIL because `capwave_k_provider.h` and `clsvof_nn_features.h` do not exist.

- [ ] **Step 3: Add the 27D feature builder**

Create `experiments/capwave_clsvof_kreplace/include/clsvof_nn_features.h`:

```c
#ifndef CLSVOF_NN_FEATURES_H
#define CLSVOF_NN_FEATURES_H

#include <math.h>

static inline void capwave_build_raw27 (Point point, scalar d, float raw[27])
{
  int p = 0;
  for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++)
      raw[p++] = (float) (d[i,j]/Delta);

  for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++) {
      double gx = (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double gn = sqrt (sq(gx) + sq(gy)) + 1e-30;
      raw[p++] = (float) (gx/gn);
    }

  for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++) {
      double gx = (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double gn = sqrt (sq(gx) + sq(gy)) + 1e-30;
      raw[p++] = (float) (gy/gn);
    }
}

#endif
```

- [ ] **Step 4: Add the k provider**

Create `experiments/capwave_clsvof_kreplace/include/capwave_k_provider.h`:

```c
#ifndef CAPWAVE_K_PROVIDER_H
#define CAPWAVE_K_PROVIDER_H

#ifndef CAPWAVE_K_NATIVE
#define CAPWAVE_K_NATIVE 0
#endif

#ifndef CAPWAVE_K_NN_RAW
#define CAPWAVE_K_NN_RAW 1
#endif

#ifndef CAPWAVE_K_MODE
#define CAPWAVE_K_MODE CAPWAVE_K_NATIVE
#endif

#ifndef CAPWAVE_K_CLAMP_FACTOR
#define CAPWAVE_K_CLAMP_FACTOR 1.0
#endif

#if CAPWAVE_K_MODE == CAPWAVE_K_NN_RAW
#include "nn_weights.h"
#include "clsvof_mlp_infer.h"
#include "clsvof_nn_features.h"
#endif

static inline double capwave_k_provider (Point point, scalar d)
{
#if CAPWAVE_K_MODE == CAPWAVE_K_NATIVE
  return distance_curvature (point, d);
#elif CAPWAVE_K_MODE == CAPWAVE_K_NN_RAW
  float raw[CLSVOF_NN_INPUT_DIM];
  capwave_build_raw27 (point, d, raw);
  double kappa = (double) clsvof_nn_predict_hkappa (raw)/Delta;
  double limit = CAPWAVE_K_CLAMP_FACTOR/Delta;
  if (kappa > limit)
    kappa = limit;
  else if (kappa < -limit)
    kappa = -limit;
  return kappa;
#else
#error "Unsupported CAPWAVE_K_MODE"
#endif
}

#endif
```

- [ ] **Step 5: Run compile smoke test**

Run:

```bash
bash experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add experiments/capwave_clsvof_kreplace/include/clsvof_nn_features.h \
  experiments/capwave_clsvof_kreplace/include/capwave_k_provider.h \
  experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh
git commit -m "feat: add capwave curvature provider headers"
```

---

### Task 3: Add External Canary Runner

**Files:**
- Create: `experiments/capwave_clsvof_kreplace/run_canary.sh`
- Create: `experiments/capwave_clsvof_kreplace/README.md`
- Create: `experiments/capwave_clsvof_kreplace/results/.gitkeep`

- [ ] **Step 1: Write the runner**

Create `experiments/capwave_clsvof_kreplace/run_canary.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

src_case="$repo_root/basilisk/src/test/capwave-clsvof.c"
src_prosperetti="$repo_root/basilisk/src/test/prosperetti.h"
src_integral="$repo_root/basilisk/src/integral.h"

work_root="$script_dir/work"
results_root="$script_dir/results/$(date -u +%Y%m%dT%H%M%SZ)"

copy_case() {
  local dst="$1"
  mkdir -p "$dst"
  cp "$src_case" "$dst/capwave-clsvof.c"
  cp "$src_prosperetti" "$dst/prosperetti.h"
}

run_case() {
  local dst="$1"
  shift
  (
    cd "$dst"
    "$repo_root/tools/basilisk-run" "$@" capwave-clsvof.c > stdout.txt 2> log
  )
}

archive_case() {
  local label="$1"
  local dst="$2"
  mkdir -p "$results_root/$label"
  cp "$dst"/stdout.txt "$results_root/$label/stdout.txt"
  cp "$dst"/log "$results_root/$label/log"
  cp "$dst"/wave-* "$results_root/$label/"
}

rm -rf "$work_root"
mkdir -p "$work_root" "$results_root"

copy_case "$work_root/original"
run_case "$work_root/original" -DCLSVOF=1
archive_case original "$work_root/original"

copy_case "$work_root/native_wrapper"
/opt/anaconda3/envs/pinn/bin/python \
  "$repo_root/experiments/capwave_clsvof_kreplace/make_overlay_integral.py" \
  "$src_integral" \
  "$work_root/native_wrapper/integral.h"
run_case "$work_root/native_wrapper" \
  -DCLSVOF=1 \
  -DCAPWAVE_K_MODE=CAPWAVE_K_NATIVE \
  -I"$repo_root/experiments/capwave_clsvof_kreplace/include"
archive_case native_wrapper "$work_root/native_wrapper"

copy_case "$work_root/nn_baseline_128_hgradient"
/opt/anaconda3/envs/pinn/bin/python \
  "$repo_root/experiments/capwave_clsvof_kreplace/make_overlay_integral.py" \
  "$src_integral" \
  "$work_root/nn_baseline_128_hgradient/integral.h"
run_case "$work_root/nn_baseline_128_hgradient" \
  -DCLSVOF=1 \
  -DCAPWAVE_K_MODE=CAPWAVE_K_NN_RAW \
  -DCAPWAVE_K_CLAMP_FACTOR=1.0 \
  -I"$repo_root/experiments/capwave_clsvof_kreplace/include" \
  -I"$repo_root/tools/clsvof_model_export/include" \
  -I"$repo_root/dataset/model/c_exports/baseline_128_hgradient"
archive_case nn_baseline_128_hgradient "$work_root/nn_baseline_128_hgradient"

cat > "$results_root/manifest.json" <<JSON
{
  "source_case": "basilisk/src/test/capwave-clsvof.c",
  "source_integral": "basilisk/src/integral.h",
  "replacement": "double ki = distance_curvature (point, d) -> double ki = capwave_k_provider (point, d)",
  "nn_weights": "dataset/model/c_exports/baseline_128_hgradient/nn_weights.h",
  "modes": ["original", "native_wrapper", "nn_baseline_128_hgradient"],
  "clamp": "abs(kappa) <= 1/Delta"
}
JSON

echo "$results_root"
```

- [ ] **Step 2: Make the runner executable**

Run:

```bash
chmod +x experiments/capwave_clsvof_kreplace/run_canary.sh
```

- [ ] **Step 3: Add the README**

Create `experiments/capwave_clsvof_kreplace/README.md`:

````markdown
# Capwave CLSVOF K Replacement

This experiment reproduces the stock Basilisk `capwave-clsvof.c` run outside
the Basilisk source tree and changes only the cell-local curvature provider
used by `integral.h`.

It does not modify files under `basilisk/`.

Run:

```bash
experiments/capwave_clsvof_kreplace/run_canary.sh
```

The canary runs three modes:

- `original`: copied stock `capwave-clsvof.c` with stock `integral.h`.
- `native_wrapper`: copied stock case with a generated local `integral.h` where
  `ki` calls `capwave_k_provider(point, d)`, and the provider returns native
  `distance_curvature(point, d)`.
- `nn_baseline_128_hgradient`: same generated local `integral.h`, but the
  provider returns NN `hkappa / Delta` from
  `dataset/model/c_exports/baseline_128_hgradient/nn_weights.h`.

The NN path clamps `abs(kappa) <= 1/Delta` during the first canary.
```
````

- [ ] **Step 4: Add the results directory marker**

Run:

```bash
touch experiments/capwave_clsvof_kreplace/results/.gitkeep
```

- [ ] **Step 5: Commit**

Run:

```bash
git add experiments/capwave_clsvof_kreplace/run_canary.sh \
  experiments/capwave_clsvof_kreplace/README.md \
  experiments/capwave_clsvof_kreplace/results/.gitkeep
git commit -m "feat: add capwave k replacement canary runner"
```

---

### Task 4: Run Native Wrapper Equivalence Gate

**Files:**
- Modify: `experiments/capwave_clsvof_kreplace/run_canary.sh` only if this task finds a runner bug.

- [ ] **Step 1: Run the canary script**

Run:

```bash
experiments/capwave_clsvof_kreplace/run_canary.sh
```

Expected: prints a result directory such as:

```text
experiments/capwave_clsvof_kreplace/results/20260709T120000Z
```

- [ ] **Step 2: Verify original and native wrapper logs are byte-identical or numerically identical**

Run:

```bash
latest="$(find experiments/capwave_clsvof_kreplace/results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
diff -u "$latest/original/log" "$latest/native_wrapper/log"
```

Expected: no diff. If whitespace or roundoff differs, inspect numeric values manually:

```bash
cat "$latest/original/log"
cat "$latest/native_wrapper/log"
```

The `N/L0` and relative RMS error pairs must match to at least `1e-12` absolute difference.

- [ ] **Step 3: Verify wave files match for native wrapper**

Run:

```bash
latest="$(find experiments/capwave_clsvof_kreplace/results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
for n in 16 32 64 128; do
  diff -u "$latest/original/wave-$n" "$latest/native_wrapper/wave-$n"
done
```

Expected: no diff. If this fails, stop before interpreting NN results because the wrapper changed more than `ki` dispatch.

- [ ] **Step 4: Commit runner fixes if any were required**

If Task 4 required a fix, run:

```bash
git add experiments/capwave_clsvof_kreplace/run_canary.sh
git commit -m "fix: preserve capwave native wrapper equivalence"
```

If no fix was required, do not create an empty commit.

---

### Task 5: Evaluate NN Canary Against The Stock Capwave Outputs

**Files:**
- Create: `experiments/capwave_clsvof_kreplace/summarize_canary.py`

- [ ] **Step 1: Write the summarizer**

Create `experiments/capwave_clsvof_kreplace/summarize_canary.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path


def read_log(path: Path) -> list[tuple[float, float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a, b = line.split()[:2]
        rows.append((float(a), float(b)))
    return rows


def read_wave(path: Path) -> list[tuple[float, float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a, b = line.split()[:2]
        rows.append((float(a), float(b)))
    return rows


def rms_delta(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    if len(a) != len(b):
        raise ValueError(f"wave length mismatch: {len(a)} != {len(b)}")
    if not a:
        raise ValueError("empty wave file")
    se = 0.0
    for (ta, ya), (tb, yb) in zip(a, b):
        if abs(ta - tb) > 1e-12:
            raise ValueError(f"time mismatch: {ta} != {tb}")
        se += (ya - yb)**2
    return math.sqrt(se/len(a))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()

    original = args.result_dir / "original"
    native = args.result_dir / "native_wrapper"
    nn = args.result_dir / "nn_baseline_128_hgradient"

    print("# capwave clsvof k replacement canary")
    print("mode,N_over_L0,relative_rms_error")
    for mode_dir in [original, native, nn]:
        for n_over_l0, err in read_log(mode_dir / "log"):
            print(f"{mode_dir.name},{n_over_l0:.17g},{err:.17g}")

    print("")
    print("wave_delta,N,rms_delta_vs_original")
    for n in [16, 32, 64, 128]:
        d_native = rms_delta(read_wave(original / f"wave-{n}"), read_wave(native / f"wave-{n}"))
        d_nn = rms_delta(read_wave(original / f"wave-{n}"), read_wave(nn / f"wave-{n}"))
        print(f"native_wrapper,{n},{d_native:.17g}")
        print(f"nn_baseline_128_hgradient,{n},{d_nn:.17g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the summarizer**

Run:

```bash
latest="$(find experiments/capwave_clsvof_kreplace/results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
/opt/anaconda3/envs/pinn/bin/python \
  experiments/capwave_clsvof_kreplace/summarize_canary.py "$latest" \
  > "$latest/summary.md"
cat "$latest/summary.md"
```

Expected:

- `native_wrapper` wave deltas are zero or near machine zero.
- `nn_baseline_128_hgradient` has finite RMS errors and finite wave deltas.
- If the NN run crashes, emits NaN, or produces missing `wave-*`, stop and inspect `log` and `stdout.txt`.

- [ ] **Step 3: Commit the summarizer**

Run:

```bash
git add experiments/capwave_clsvof_kreplace/summarize_canary.py
git commit -m "feat: summarize capwave k replacement canary"
```

---

### Task 6: Decide Whether To Expand Beyond Baseline 128

**Files:**
- Modify: `experiments/capwave_clsvof_kreplace/run_canary.sh`
- Modify: `experiments/capwave_clsvof_kreplace/summarize_canary.py`

- [ ] **Step 1: Check the canary gate**

Use the latest `summary.md`. Continue only if all are true:

```text
native_wrapper matches original log and wave files.
nn_baseline_128_hgradient compiles.
nn_baseline_128_hgradient runs to completion.
nn_baseline_128_hgradient emits wave-16, wave-32, wave-64, and wave-128.
nn_baseline_128_hgradient log contains four finite relative RMS error rows.
```

- [ ] **Step 2: Add all exported model modes**

Extend `run_canary.sh` with these additional NN modes:

```bash
nn_baseline_64_hgradient
nn_baseline_256_hgradient
nn_baseline_512_hgradient
```

Each mode uses the same copied stock case and generated overlay, changing only the include directory:

```bash
-I"$repo_root/dataset/model/c_exports/baseline_64_hgradient"
-I"$repo_root/dataset/model/c_exports/baseline_256_hgradient"
-I"$repo_root/dataset/model/c_exports/baseline_512_hgradient"
```

- [ ] **Step 3: Extend the summarizer modes**

Update `summarize_canary.py` so the mode list is:

```python
mode_names = [
    "original",
    "native_wrapper",
    "nn_baseline_64_hgradient",
    "nn_baseline_128_hgradient",
    "nn_baseline_256_hgradient",
    "nn_baseline_512_hgradient",
]
```

Use this list in both the log table and the wave-delta table.

- [ ] **Step 4: Run the expanded matrix**

Run:

```bash
experiments/capwave_clsvof_kreplace/run_canary.sh
latest="$(find experiments/capwave_clsvof_kreplace/results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
/opt/anaconda3/envs/pinn/bin/python \
  experiments/capwave_clsvof_kreplace/summarize_canary.py "$latest" \
  > "$latest/summary.md"
cat "$latest/summary.md"
```

Expected: all modes complete and produce finite RMS errors.

- [ ] **Step 5: Commit the expanded matrix**

Run:

```bash
git add experiments/capwave_clsvof_kreplace/run_canary.sh \
  experiments/capwave_clsvof_kreplace/summarize_canary.py
git commit -m "feat: expand capwave k replacement model matrix"
```

---

## Completion Criteria

The capwave implementation is complete only when the following evidence exists:

```text
experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py passes.
experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh passes.
experiments/capwave_clsvof_kreplace/run_canary.sh completes.
The latest result manifest says the source case is basilisk/src/test/capwave-clsvof.c.
The latest result manifest says the source integral is basilisk/src/integral.h.
The native_wrapper mode matches original mode.
The NN mode changes only the provider for ki.
The NN mode produces finite log and wave outputs.
No file under basilisk/ is modified.
```

Verification commands:

```bash
/opt/anaconda3/envs/pinn/bin/python -m pytest \
  experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py -q

bash experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh

experiments/capwave_clsvof_kreplace/run_canary.sh

latest="$(find experiments/capwave_clsvof_kreplace/results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
/opt/anaconda3/envs/pinn/bin/python \
  experiments/capwave_clsvof_kreplace/summarize_canary.py "$latest" \
  > "$latest/summary.md"

git status --short -- basilisk
```

Expected final `git status --short -- basilisk` output: empty.

## Self-Review

- Spec coverage: The plan keeps files outside `basilisk/`, copies the stock `capwave-clsvof.c`, generates an overlay from stock `integral.h`, and replaces only the `ki` provider.
- Placeholder scan: No task relies on an unspecified implementation detail; each created file has concrete content.
- Type consistency: `capwave_k_provider()` returns `double` because stock `integral.h` uses `double ki`; the NN inference path uses `float` raw features and `float` model inference, then converts `hkappa` to `double kappa` for the solver.
