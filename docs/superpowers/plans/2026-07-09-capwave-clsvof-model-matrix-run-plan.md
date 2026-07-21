# Capwave CLSVOF Model Matrix Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the capwave CLSVOF model-integration code is complete, run the four exported model experiments for `64`, `128`, `256`, and `512` without mixing unfinished implementation evidence into the report surface.

**Architecture:** This is an execution-gating plan layered on top of `docs/superpowers/plans/2026-07-09-capwave-clsvof-kreplace.md`. The existing implementation plan owns the model provider, `integral.h` overlay, runner, and summarizer; this plan owns when to launch the run matrix, which readiness gates must pass first, and how to defer the launch if the implementation is still incomplete. All experiment outputs stay under `experiments/capwave_clsvof_kreplace/results/`.

**Tech Stack:** Bash, Python 3, Basilisk `qcc` through `tools/basilisk-run`, generated C model exports in `experiments/clsvof_kappa_offset_conversion/models/c_exports/baseline_{64,128,256,512}_hgradient/`, and Markdown/CSV run summaries.

---

## Timing Contract

Reference time: `2026-07-09 20:18 CST`.

- Primary launch checkpoint: `2026-07-09 20:48 CST` (`T0 + 30 min`).
- Fallback launch checkpoint: `2026-07-09 21:18 CST` (`T0 + 60 min`) if the implementation is not complete at the primary checkpoint.
- Do not start the run matrix before the readiness gates below are green.
- If the primary checkpoint finds incomplete code, record the exact failing gate and defer to the fallback checkpoint instead of starting a partial experiment.

## Readiness Gates Before Any Matrix Run

- [ ] `experiments/capwave_clsvof_kreplace/` exists.
- [ ] `experiments/capwave_clsvof_kreplace/run_canary.sh` exists and is executable.
- [ ] `experiments/capwave_clsvof_kreplace/summarize_canary.py` exists.
- [ ] `experiments/capwave_clsvof_kreplace/make_overlay_integral.py` exists.
- [ ] `experiments/capwave_clsvof_kreplace/include/capwave_k_provider.h` exists.
- [ ] `experiments/capwave_clsvof_kreplace/include/clsvof_nn_features.h` exists.
- [ ] `experiments/capwave_clsvof_kreplace/run_canary.sh` includes these four model modes:

```text
nn_baseline_64_hgradient
nn_baseline_128_hgradient
nn_baseline_256_hgradient
nn_baseline_512_hgradient
```

- [ ] All four model export directories exist:

```text
experiments/clsvof_kappa_offset_conversion/models/c_exports/baseline_64_hgradient/
experiments/clsvof_kappa_offset_conversion/models/c_exports/baseline_128_hgradient/
experiments/clsvof_kappa_offset_conversion/models/c_exports/baseline_256_hgradient/
experiments/clsvof_kappa_offset_conversion/models/c_exports/baseline_512_hgradient/
```

- [ ] The overlay generator test passes:

```bash
/opt/anaconda3/envs/pinn/bin/python -m pytest \
  experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py -q
```

- [ ] The provider/header compile test passes:

```bash
bash experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh
```

## Task 1: Primary Launch Check At 20:48 CST

**Files:**
- Read: `docs/superpowers/plans/2026-07-09-capwave-clsvof-kreplace.md`
- Read: `experiments/capwave_clsvof_kreplace/run_canary.sh`
- Read: `experiments/capwave_clsvof_kreplace/summarize_canary.py`
- Write only if the run succeeds: `experiments/capwave_clsvof_kreplace/results/<timestamp>/summary.md`

- [ ] **Step 1: Inspect implementation completeness**

Run:

```bash
test -x experiments/capwave_clsvof_kreplace/run_canary.sh
test -f experiments/capwave_clsvof_kreplace/summarize_canary.py
test -f experiments/capwave_clsvof_kreplace/make_overlay_integral.py
test -f experiments/capwave_clsvof_kreplace/include/capwave_k_provider.h
test -f experiments/capwave_clsvof_kreplace/include/clsvof_nn_features.h
```

Expected: all commands exit with status `0`.

- [ ] **Step 2: Verify the four-model matrix is present in the runner**

Run:

```bash
rg -n "nn_baseline_(64|128|256|512)_hgradient" \
  experiments/capwave_clsvof_kreplace/run_canary.sh
```

Expected: one or more matches for each of `64`, `128`, `256`, and `512`.

- [ ] **Step 3: Run the preflight tests**

Run:

```bash
/opt/anaconda3/envs/pinn/bin/python -m pytest \
  experiments/capwave_clsvof_kreplace/tests/test_make_overlay_integral.py -q

bash experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh
```

Expected: both commands pass.

- [ ] **Step 4: Launch the matrix only if Steps 1-3 pass**

Run:

```bash
experiments/capwave_clsvof_kreplace/run_canary.sh
latest="$(find experiments/capwave_clsvof_kreplace/results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
/opt/anaconda3/envs/pinn/bin/python \
  experiments/capwave_clsvof_kreplace/summarize_canary.py "$latest" \
  > "$latest/summary.md"
cat "$latest/summary.md"
```

Expected: `summary.md` includes `original`, `native_wrapper`, `nn_baseline_64_hgradient`, `nn_baseline_128_hgradient`, `nn_baseline_256_hgradient`, and `nn_baseline_512_hgradient`, with finite RMS rows and no missing `wave-*` files.

- [ ] **Step 5: If any readiness gate fails, do not run**

Record a short blocker note in the thread with:

```text
Primary launch blocked at 2026-07-09 20:48 CST.
Failed gate: <exact command or missing file>.
Action: defer to fallback checkpoint at 2026-07-09 21:18 CST.
```

## Task 2: Fallback Launch Check At 21:18 CST

**Files:**
- Read: same files as Task 1
- Write only if the run succeeds: `experiments/capwave_clsvof_kreplace/results/<timestamp>/summary.md`

- [ ] **Step 1: Repeat the readiness gates from Task 1**

Run the same Step 1, Step 2, and Step 3 commands from Task 1.

Expected: all gates pass before any experiment starts.

- [ ] **Step 2: Launch the matrix if gates now pass**

Run the same matrix command from Task 1 Step 4.

Expected: all four model modes complete with finite summaries.

- [ ] **Step 3: If the fallback also fails, stop**

Do not start a partial run. Report:

```text
Fallback launch blocked at 2026-07-09 21:18 CST.
Failed gate: <exact command or missing file>.
No experiment matrix was started.
```

## Completion Criteria

The experiment run is complete only when:

- [ ] A timestamped result directory exists under `experiments/capwave_clsvof_kreplace/results/`.
- [ ] That result directory contains `summary.md`.
- [ ] `summary.md` includes all four NN model modes: `64`, `128`, `256`, and `512`.
- [ ] `summary.md` includes `original` and `native_wrapper` controls.
- [ ] The latest manifest identifies `basilisk/src/test/capwave-clsvof.c` as the source case.
- [ ] `git status --short -- basilisk` is empty, or any Basilisk-tree changes are explicitly identified as pre-existing and unrelated.

## Self-Review

- Spec coverage: The plan covers the user's four exported model resolutions and the delayed start rule.
- Evidence boundary: The matrix starts only after the model-integration code and preflight tests are complete.
- Timing clarity: `30 minutes later` is treated as `20:48 CST`; `1 hour later` is treated as `21:18 CST` from the same reference time.
