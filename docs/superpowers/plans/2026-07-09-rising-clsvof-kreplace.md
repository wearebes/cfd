# Rising Bubble CLSVOF K Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce the stock `rising-clsvof` benchmark (Hysing et al. 2009, case 1) from outside the Basilisk source tree while changing only the cell-local curvature value `ki` used by `integral.h`, replacing it with the NN-predicted curvature.

**Architecture:** Same overlay strategy as `docs/superpowers/plans/2026-07-09-capwave-clsvof-kreplace.md`, applied to the rising-bubble case. The implementation creates an external experiment workspace under `experiments/rising_clsvof_kreplace/`. Each run copies the stock `basilisk/src/test/rising.c` into a temporary work directory as `rising-clsvof.c`, generates a local `integral.h` overlay from the stock `basilisk/src/integral.h`, and relies on C include precedence (compile with the work directory as cwd) so the copied case uses the overlay. The overlay keeps the surface-tension tensor and face-force path unchanged, replacing only `double ki = distance_curvature (point, d);` with `double ki = rising_k_provider (point, d);`.

**Tech Stack:** Bash, Python 3 (`/opt/anaconda3/envs/pinn/bin/python`), Basilisk `qcc` through `tools/basilisk-run`, C99 headers, generated float32 NN weights in `dataset/model/c_exports/`, and `tools/clsvof_model/include/clsvof_mlp_infer.h`.

**Independence:** This plan does not depend on the capwave k-replacement having been executed. The overlay generator and feature header are copied (with renames) from the capwave plan text; if `experiments/capwave_clsvof_kreplace/` already exists when this plan is implemented, reuse its tested code as the copy source and note the provenance in the README. Deduplicating the two experiments into a shared module is an explicit non-goal for now.

---

## Why the same approach transfers

Verified facts (2026-07-09):

- `basilisk/src/test/rising-clsvof.c` is a symlink to `rising.c`; the official build is `rising.c` compiled with `-DLEVELSET=1 -DCLSVOF=1` (see `basilisk/src/test/Makefile` lines 225-228).
- With those flags, `rising.c` includes `two-phase-clsvof.h` and `integral.h`, and sets surface tension via `d.sigmaf` — exactly the same surface-tension path as `capwave-clsvof`.
- The single curvature insertion point is `basilisk/src/integral.h` line 165: `double ki = distance_curvature (point, d);` (the line-138 call site is dead under the default `CURVATURE == 1`).
- The archived official reference run lives in `dataset/official_data/rising_bubble/raw/rising-clsvof/{out,log}`; MooNMD reference data is in `dataset/official_data/rising_bubble/sources/c1g3l4.txt` and `c1g3l4s.txt`.
- The official case-1 run costs ~14 s CPU (`perf.t` at end of `out`), so the full mode matrix is cheap.

Differences from capwave that this plan must handle:

1. **Outputs.** The case writes a time series to stdout (`out`: `t sb -1 xb vb dt perf.t perf.speed` + multigrid stats) and the final bubble interface facets at `t = 3` to stderr (`log`). There are no `wave-*` files.
2. **Non-deterministic columns.** `out` columns 7 (`perf.t`) and 8 (`perf.speed`) are wall-clock performance numbers and can never match across runs. The equivalence comparator must skip exactly these two fields and require the rest to match.
3. **Geometry.** Closed interface, both curvature signs, `kappa ≈ 4` at init (radius 0.25) vs `1/Delta = 128` at `LEVEL 8` — the safety clamp is far from the physical range, as intended.
4. **Two benchmark cases.** Case 1 (`-DLEVELSET=1 -DCLSVOF=1`, sigma 24.5) is the canary. Case 2 (`rising2-clsvof`, adds `-DCASE2=1`, sigma 1.96) enters only after the case-1 gates pass.

## Non-Negotiable Scope

- Do not create, modify, or delete files under `basilisk/`.
- Do not hand-write a new rising case. The run source must be copied from `basilisk/src/test/rising.c` for each run.
- The surface-tension implementation must be copied from `basilisk/src/integral.h` for each run, via the overlay generator.
- The only semantic replacement in the generated `integral.h` overlay is the source of `ki`.
- The native-wrapper equivalence gate must pass before any NN result is interpreted.
- First NN canary uses `dataset/model/c_exports/baseline_128_hgradient/nn_weights.h` with clamp factor `1.0`.
- Keep the official full run (`t = 3`, LEVEL 8, `dimensions (nx = 4)`). If a compile/runtime failure requires a shorter debug run, keep it in a separate debug script and do not call it the canary.
- Do not modify `tools/rising bubble/` or anything under `dataset/official_data/`.

## Run Economy and Data Placement (user request, 2026-07-09)

Recorded from user feedback: running the NN matrix must not re-run a native twin
alongside every NN run — the official baseline was already produced once, and
NN outputs must land in `dataset/` so nobody has to dig through `experiments/`
to find them.

**Controls run once, then are cached — never once per NN model.**

- `original`, `native_wrapper`, and `native_perturbed` are *harness-validation*
  runs, not scientific data. They are executed exactly once per state of
  (`basilisk/src/test/rising.c`, `basilisk/src/integral.h`, toolchain, case
  flags), and their gate verdicts recorded. Every later NN run — canary or
  matrix — reuses the cached control outputs by path; the runner must support
  running NN modes only (e.g. `run_canary.sh --nn-only`, which resolves the
  latest gated control set and refuses to run if none exists or if the
  source/toolchain fingerprint in its manifest no longer matches).
- The controls cannot be replaced by `dataset/official_data/` archives: the
  archive's toolchain/machine provenance is unknown, so it serves plotting and
  the soft cross-check (Task 6) only. The hard equivalence gate needs exactly
  one same-toolchain native run — one, not one per model.

**NN outputs are published into `dataset/`, mirroring the official layout.**

- After the Task 5 gates pass, each NN mode's `out`, `log`, and `manifest.json`
  are copied to `dataset/nn_data/rising-clsvof/<model_name>/` (e.g.
  `dataset/nn_data/rising-clsvof/baseline_128_hgradient/`), a sibling of
  `dataset/official_data/`, so official and NN data live under one root for
  plotting and lookup. `experiments/rising_clsvof_kreplace/results/<timestamp>/`
  remains the raw per-run archive and gate evidence; `dataset/nn_data/` is the
  curated surface and is only ever written from a gated run.
- `dataset/official_data/` stays read-only; NN data never goes there.

**Capwave back-port note (do not act on it yet).** The same two policies apply
to `2026-07-09-capwave-clsvof-kreplace.md` and the capwave matrix-run plan
(where the waste is worse: the sweep re-runs natives up to N = 512 per model).
Per user instruction on 2026-07-09 the capwave plans are not being revised now;
whoever next touches capwave must back-port: (a) one-time cached controls with
an NN-only matrix mode, (b) publication of NN outputs to
`dataset/nn_data/capwave-clsvof/<model_name>/`.

## File Structure

Create these files:

```text
experiments/rising_clsvof_kreplace/
  README.md
  make_overlay_integral.py
  compare_out.py
  summarize_canary.py
  run_canary.sh
  include/
    rising_k_provider.h
    clsvof_nn_features.h
  tests/
    test_make_overlay_integral.py
    test_compare_out.py
    test_feature_header_compile.sh
  results/
    .gitkeep
```

Generated, untracked run outputs (`work/` is recreated per run; `results/<UTC timestamp>/` archives each run):

```text
experiments/rising_clsvof_kreplace/work/
  original/                     rising-clsvof.c, rising-clsvof, out, log
  native_wrapper/               + integral.h (overlay)
  native_perturbed/             + integral.h (overlay), liveness control
  nn_baseline_128_hgradient/    + integral.h (overlay)
  ...
```

## Curvature Replacement Contract

Stock line in `basilisk/src/integral.h` (inside the `acceleration` event, `CURVATURE == 1` branch):

```c
double ki = distance_curvature (point, d);
```

Generated overlay replacement:

```c
double ki = rising_k_provider (point, d);
```

Provider modes (compile-time, mirroring the capwave contract):

- `RISING_K_NATIVE` (default, `0`): `return distance_curvature (point, d);` — must be bit-equivalent to stock.
- `RISING_K_NN_RAW` (`1`): build the 27-feature stencil (9 × `d/Delta`, 9 × unit-normal x, 9 × unit-normal y), call `clsvof_nn_predict_hkappa (raw)`, convert with `kappa = hkappa / Delta`, clamp `|kappa| <= RISING_K_CLAMP_FACTOR / Delta` (default factor `1.0`).
- `RISING_K_NATIVE_PERTURBED` (`2`): `return distance_curvature (point, d) * (1. + 1e-3);` — a deliberate, known perturbation used only as a liveness control (see Task 5). It has no scientific meaning; its only job is to prove the overlay dispatch actually reaches the solver.

The NN model output is `h*kappa`; the solver consumes `kappa`, so the conversion is `kappa = hkappa/Delta` at the insertion site.

### Why the liveness control is mandatory

The overlay depends on C include precedence (the work-dir `integral.h` shadowing `basilisk/src/integral.h`). If that shadowing silently fails, every overlay mode — including NN — compiles and runs successfully against the *stock* header: the NN weights are never referenced, no error is raised, and the NN run is byte-identical to `original`. The Task 5 native-equivalence gate cannot detect this (a dead overlay passes it trivially), and the resulting "NN has zero effect" is exactly the kind of plausible-but-wrong outcome this plan exists to prevent. Two controls close the hole:

1. **Compile-time negative control** (Task 2): compiling an overlay mode *without* `-I<include dir>` must FAIL with "rising_k_provider.h not found". Failure proves the overlay header is the one being compiled; silent success means the stock header won and the harness is broken.
2. **Runtime positive control** (Task 5): the `native_perturbed` mode must produce `out` that *differs* from `original`. If it matches, the `ki` dispatch never executed; stop and fix before looking at any NN result.

---

### Task 1: Overlay Generator With Tests

**Files:**
- Create: `experiments/rising_clsvof_kreplace/make_overlay_integral.py`
- Create: `experiments/rising_clsvof_kreplace/tests/test_make_overlay_integral.py`

- [ ] **Step 1:** Copy the overlay generator and its tests verbatim from the capwave plan (`docs/superpowers/plans/2026-07-09-capwave-clsvof-kreplace.md`, Task 1), renaming `capwave_k_provider` → `rising_k_provider` and `capwave_k_provider.h` → `rising_k_provider.h` in `TARGET`/`REPLACEMENT`/`PROVIDER_INCLUDE` and in the test assertions. The generator must: replace exactly one occurrence of the stock `ki` line (error otherwise), and inject `#include "rising_k_provider.h"` once after the `#endif // CURVATURE` marker (error if the marker is missing).
- [ ] **Step 2:** Run the tests; expected FAIL before implementation, PASS after:

```bash
/opt/anaconda3/envs/pinn/bin/python -m pytest \
  experiments/rising_clsvof_kreplace/tests/test_make_overlay_integral.py -q
```

- [ ] **Step 3:** Sanity-run the generator against the real header and confirm the output differs from stock only in the injected include and the `ki` line:

```bash
/opt/anaconda3/envs/pinn/bin/python \
  experiments/rising_clsvof_kreplace/make_overlay_integral.py \
  basilisk/src/integral.h /tmp/overlay_integral.h
diff basilisk/src/integral.h /tmp/overlay_integral.h
```

Expected diff: exactly two hunks (the include injection, the `ki` line).

- [ ] **Step 4:** Commit.

---

### Task 2: NN Feature and K Provider Headers

**Files:**
- Create: `experiments/rising_clsvof_kreplace/include/clsvof_nn_features.h`
- Create: `experiments/rising_clsvof_kreplace/include/rising_k_provider.h`
- Create: `experiments/rising_clsvof_kreplace/tests/test_feature_header_compile.sh`

- [ ] **Step 1:** Copy `clsvof_nn_features.h` from the capwave plan (Task 2 Step 3) unchanged except the function name — keep it case-neutral: `clsvof_build_raw27 (Point point, scalar d, float raw[27])`. Feature order must match the exporter: 9 × `d[i,j]/Delta`, then 9 × `gx/|g|`, then 9 × `gy/|g|` (central differences, `1e-30` guard).
- [ ] **Step 2:** Create `rising_k_provider.h` mirroring `capwave_k_provider.h` from the capwave plan (Task 2 Step 4) with macros `RISING_K_MODE`, `RISING_K_NATIVE` (0, default), `RISING_K_NN_RAW` (1), `RISING_K_NATIVE_PERTURBED` (2), `RISING_K_CLAMP_FACTOR` (default 1.0). NN mode includes `nn_weights.h`, `clsvof_mlp_infer.h`, `clsvof_nn_features.h`. The perturbed mode is `distance_curvature (point, d) * (1. + 1e-3)` and must not include any NN header.
- [ ] **Step 3:** Write the compile smoke test following the capwave plan (Task 2 Step 1), adapted to this case: the smoke source is a copy of the real `rising.c` copied into the tmp dir as `rising-clsvof.c`, compiled twice with `tools/basilisk-cc` from inside the tmp dir (so the overlay `integral.h` wins include precedence):
  - native: `-DLEVELSET=1 -DCLSVOF=1 -DRISING_K_MODE=RISING_K_NATIVE -I<include dir>`
  - NN: `-DLEVELSET=1 -DCLSVOF=1 -DRISING_K_MODE=RISING_K_NN_RAW -I<include dir> -I tools/clsvof_model/include -I dataset/model/c_exports/baseline_128_hgradient`

  Note: the model include path is `tools/clsvof_model/include` (the directory that exists in this repo), not the `tools/clsvof_model_export` name used in the capwave plan text.
- [ ] **Step 3b (include-precedence negative control):** In the same smoke script, compile the overlay work dir once *without* `-I<include dir>` and assert the compile FAILS (missing `rising_k_provider.h`). If it succeeds, the stock `basilisk/src/integral.h` was used instead of the overlay — the harness is broken; fix include precedence before proceeding. Note `tools/basilisk-cc` compiles external sources from the invoker's cwd, so the smoke script must `cd` into the tmp work dir (quoted-include resolution relative to the copied case file is what makes the overlay win).
- [ ] **Step 4:** Run the smoke test; expected FAIL before headers exist, PASS after.

```bash
bash experiments/rising_clsvof_kreplace/tests/test_feature_header_compile.sh
```

- [ ] **Step 5:** Commit.

---

### Task 3: Performance-Field-Aware Output Comparator

The `diff`-based gate from the capwave plan cannot work here because `out` embeds wall-clock fields. Build a comparator first, with tests, so the gate in Task 5 is trustworthy.

**Files:**
- Create: `experiments/rising_clsvof_kreplace/compare_out.py`
- Create: `experiments/rising_clsvof_kreplace/tests/test_compare_out.py`

- [ ] **Step 1:** Write failing tests covering: (a) identical files compare equal; (b) files differing only in fields 7/8 of data rows compare equal; (c) a difference in any other field is reported with line number and field index; (d) differing line counts fail; (e) the header line (`t sb -1 xb vb dt ...`) is compared as an exact string.
- [ ] **Step 2:** Implement `compare_out.py <a> <b>`: for each data line, split on whitespace; compare all fields as exact strings except 1-indexed fields 7 and 8, which are ignored. (Multigrid stats fields 9+ are deterministic and must match.) Exit 0 on match, 1 with a report on mismatch. Also support `--tol <abs>` to fall back to numeric comparison with absolute tolerance for the cross-toolchain check in Task 6 (never used for the equivalence gate).
- [ ] **Step 3:** Run the tests to green.

```bash
/opt/anaconda3/envs/pinn/bin/python -m pytest \
  experiments/rising_clsvof_kreplace/tests/test_compare_out.py -q
```

- [ ] **Step 4:** Commit.

---

### Task 4: External Canary Runner

**Files:**
- Create: `experiments/rising_clsvof_kreplace/run_canary.sh`
- Create: `experiments/rising_clsvof_kreplace/README.md`
- Create: `experiments/rising_clsvof_kreplace/results/.gitkeep`

- [ ] **Step 1:** Write `run_canary.sh` following the capwave plan's runner shape (Task 3), with these case-specific settings:
  - `src_case="$repo_root/basilisk/src/test/rising.c"` copied to `<work>/rising-clsvof.c`. No other case files are needed (`c1g3l4*.txt` are plot-only references, not runtime inputs).
  - Common flags for every mode: `-DLEVELSET=1 -DCLSVOF=1`.
  - Run as `cd <work dir> && "$repo_root"/tools/basilisk-run <flags> rising-clsvof.c > out 2> log` (absolute wrapper path — a relative `tools/basilisk-run` breaks after the `cd`) so stdout becomes `out` and the facets land in `log`, matching the official layout.
  - Modes: `original` (stock, no overlay), `native_wrapper` (overlay + `-DRISING_K_MODE=RISING_K_NATIVE -I<include>`), `native_perturbed` (overlay + `-DRISING_K_MODE=RISING_K_NATIVE_PERTURBED -I<include>`), `nn_baseline_128_hgradient` (overlay + `-DRISING_K_MODE=RISING_K_NN_RAW -DRISING_K_CLAMP_FACTOR=1.0 -I<include> -I tools/clsvof_model/include -I dataset/model/c_exports/baseline_128_hgradient`).
  - Archive `out`, `log`, and the generated `integral.h` (for the overlay modes) into `results/<UTC timestamp>/<mode>/`, and write `manifest.json` recording source case, source integral, the replacement contract line, weights path, modes, clamp, and a source fingerprint (SHA-256 of `basilisk/src/test/rising.c` and `basilisk/src/integral.h`, plus the compile flags).
  - Support `--nn-only`: skip the three control modes and instead resolve the most recent results dir whose manifest (a) has the same source fingerprint and (b) is marked gate-passed; symlink/record its controls as the comparison baseline. Refuse to run (with a clear message) if no such gated control set exists — per the Run Economy policy, controls run once and are reused, never re-run per NN model.
- [ ] **Step 2:** `chmod +x` the runner; write `README.md` describing the three modes, the gate order, and the no-`basilisk/`-modification rule.
- [ ] **Step 3:** Commit.

---

### Task 5: Native Wrapper Equivalence Gate (hard gate)

- [ ] **Step 1:** Run the canary:

```bash
experiments/rising_clsvof_kreplace/run_canary.sh
```

- [ ] **Step 2:** Gate on equivalence — both must pass before NN results mean anything:

```bash
latest="$(find experiments/rising_clsvof_kreplace/results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
/opt/anaconda3/envs/pinn/bin/python experiments/rising_clsvof_kreplace/compare_out.py \
  "$latest/original/out" "$latest/native_wrapper/out"
diff "$latest/original/log" "$latest/native_wrapper/log"
```

Expected: comparator exit 0 (only perf fields differ) and empty `log` diff. If this fails, the overlay changed more than the `ki` dispatch — stop, fix, rerun; do not proceed to Task 6/7.

- [ ] **Step 2b (overlay liveness gate):** The perturbed control must *differ* from original:

```bash
/opt/anaconda3/envs/pinn/bin/python experiments/rising_clsvof_kreplace/compare_out.py \
  "$latest/original/out" "$latest/native_perturbed/out" && { echo "LIVENESS FAIL: perturbation had no effect — overlay dispatch is dead"; exit 1; }
```

Expected: comparator exit 1 (differences found — the `&&` branch not taken). If the comparator exits 0, the `ki` replacement never reached the solver (dead overlay); every overlay-mode result including NN is then meaningless. Stop and fix before Task 6/7. Together with Step 2, this brackets the harness: NATIVE proves the wrapper adds nothing; PERTURBED proves the wrapper is actually in the loop.

- [ ] **Step 3:** Confirm no Basilisk sources changed:

```bash
git status --short -- basilisk
```

Expected: no entries beyond those already present before this experiment ran (the repo currently carries unrelated `.DS_Store` noise; the gate is *no new* entries).

- [ ] **Step 4:** Mark the results dir gate-passed (e.g. `gate_verdict.json` with the three verdicts) so `--nn-only` runs can find and reuse these controls.
- [ ] **Step 5:** Commit runner fixes if any were required; no empty commits.

---

### Task 6: Cross-Check Against Archived Official Data (soft gate)

- [ ] **Step 1:** Compare our external `original` run to the archived official reference:

```bash
latest="$(find experiments/rising_clsvof_kreplace/results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
/opt/anaconda3/envs/pinn/bin/python experiments/rising_clsvof_kreplace/compare_out.py --tol 1e-9 \
  "dataset/official_data/rising_bubble/raw/rising-clsvof/out" "$latest/original/out"
```

Expected: exact or near-exact match. If it mismatches beyond tolerance, record the deviation in the run's `notes.md` (toolchain/flag provenance of the archive may differ) but do not block: the hard baseline for NN evaluation is our own `original` mode from the same toolchain, not the archive.

---

### Task 7: Evaluate the NN Canary

**Files:**
- Create: `experiments/rising_clsvof_kreplace/summarize_canary.py`

- [ ] **Step 0 (t = 0 curvature spot-check, hard gate):** Before interpreting any NN dynamics, verify the NN curvature is sane where the answer is known. In a scratch copy (a `debug/` work dir, never the canary), instrument the provider to print, for every interfacial cell at the first `acceleration` call (`t = 0`, the initial circle of radius 0.25), `x y ki_native ki_nn`. Require: (a) sign agreement on ≥ 95% of cells, (b) median `|ki_nn|` within a factor of 2 of the analytic `kappa = 4`, (c) zero clamp hits. A failure here means feature-convention mismatch (stencil order, `d/Delta` scaling, normal orientation, or the `hkappa/Delta` conversion) — a harness bug to fix, not a model result to report. Record the check's output in the results dir.
- [ ] **Step 1:** Write the summarizer. For each mode directory, parse `out` and `log` and emit a Markdown summary with:
  - Run health: completed to `t = 3`, no NaN/inf in columns 1-6, `log` non-empty.
  - Hysing benchmark quantities from `out`: max rise velocity `max(vb)` and its time, final `vb`, final center of mass `xb`, and volume drift `max |(sb - sb0)/sb0|` (column 2).
  - Shape deviation at `t = 3`: for each MooNMD point in `dataset/official_data/rising_bubble/sources/c1g3l4s.txt` (columns: y x, plotted as `u 2:($1-0.5)`), the minimum distance to the mode's facet segment set from `log`; report mean and max. Also report the same metric between `original` and each other mode.
  - A delta table of every metric vs the `original` mode.
- [ ] **Step 2:** Run it on the latest results and save `summary.md` into the results directory. Expected: `native_wrapper` deltas ≈ 0; `nn_baseline_128_hgradient` finite, run completes, volume drift comparable in magnitude to `original`.
- [ ] **Step 3:** Plot overlays (experiment-local gnuplot or matplotlib script writing into the results dir; do not touch `tools/rising bubble/`): shape at `t = 3` (MooNMD + original + NN), rise velocity vs time, volume drift vs time.
- [ ] **Step 4:** Commit the summarizer and the summary/figures of the canary run.

---

### Task 8: Expand the Model Matrix, Then Case 2

- [ ] **Step 1:** Gate: proceed only if Task 5 passed and the Task 7 canary ran to completion with finite outputs.
- [ ] **Step 2:** Add modes `nn_baseline_64_hgradient`, `nn_baseline_256_hgradient`, `nn_baseline_512_hgradient` to the runner (only the `-I dataset/model/c_exports/<name>` include changes) and to the summarizer's mode list; run with `--nn-only` (controls are reused from the gated Task 5 results, not re-run); regenerate `summary.md`.
- [ ] **Step 2b (publish to dataset):** For each NN mode of the gated run, copy `out`, `log`, and `manifest.json` to `dataset/nn_data/rising-clsvof/<model_name>/` (create the tree; overwrite is allowed only when the manifest being replaced has the same source fingerprint — otherwise keep both and flag it). This is the curated data surface per the Run Economy policy; plotting reads official data from `dataset/official_data/` and NN data from `dataset/nn_data/`.
- [ ] **Step 3 (optional, after the case-1 matrix is clean):** Add case-2 modes: same source copy compiled with `-DCASE2=1 -DLEVELSET=1 -DCLSVOF=1`, work/results dirs suffixed `_case2`, cross-check archive `dataset/official_data/rising_bubble/raw/rising2-clsvof/`, MooNMD references `c2g3l4.txt`/`c2g3l4s.txt`. The same native-wrapper equivalence gate applies to case 2 independently.
- [ ] **Step 4:** Commit.

---

## Completion Criteria

```text
All pytest suites under experiments/rising_clsvof_kreplace/tests/ pass.
test_feature_header_compile.sh passes, including the include-precedence negative control.
run_canary.sh completes for the full mode matrix.
The result manifest names basilisk/src/test/rising.c and basilisk/src/integral.h as the only Basilisk inputs.
native_wrapper matches original on out (ignoring perf fields) and log (byte-identical).
native_perturbed DIFFERS from original (overlay liveness proven).
The t = 0 curvature spot-check passes (sign, magnitude, no clamp hits) before any NN dynamics are interpreted.
The NN modes change only the provider for ki, run to t = 3, and produce finite metrics in summary.md.
Controls were run once and reused: the model matrix ran with --nn-only against the gated control set.
Gated NN outputs are published under dataset/nn_data/rising-clsvof/<model_name>/.
git status --short -- basilisk shows no new entries.
```

## Risks / Open Questions

- **Distribution shift.** The exported models were trained on `hgradient`-style data; the rising bubble presents a closed interface, both curvature signs, and `|h*kappa|` up to ~0.03 at init (well inside a small-curvature regime, but the shape deforms strongly by `t = 3`). A stable-but-biased NN curvature will show up as rise-velocity and shape deltas in `summary.md` — that is the measurement, not a failure of the harness.
- **Sign convention.** Inside the bubble `d < 0` (init: `sqrt(...) - 0.25`). This is now a hard gate (Task 7 Step 0), not just a note: sign or magnitude disagreement at t = 0 is a harness/feature bug, and no NN dynamics may be interpreted past it.
- **Axisymmetric variants** (`rising-axi-clsvof`) are out of scope; `integral.h` has AXI-specific terms that deserve their own gate.
- **Clamp.** `1/Delta = 128` vs physical `kappa ≈ 4`: the default clamp only guards against NN blow-ups. If the NN run hits the clamp anywhere, the summarizer should say so (count clamped evaluations via a debug build if needed).
