# Rising Bubble CLSVOF K Replacement

This experiment reproduces the stock Basilisk `rising-clsvof` benchmark
(Hysing et al. 2009, case 1) outside the Basilisk source tree, changing only
the cell-local curvature provider used by `integral.h`.

It does not modify files under `basilisk/`.

## Running

```bash
experiments/rising_clsvof_kreplace/run_canary.sh
```

This runs, in order:

- `original`: copied stock `rising.c` (as `rising-clsvof.c`) with stock
  `integral.h`. No overlay involved.
- `native_wrapper`: copied stock case with a generated local `integral.h`
  where `ki` calls `rising_k_provider(point, d)`, and the provider returns
  native `distance_curvature(point, d)`. Must match `original` (see Gates).
- `native_perturbed`: same overlay, but the provider returns
  `distance_curvature(point, d) * (1.001)` — a deliberate, scientifically
  meaningless perturbation whose only job is proving the overlay dispatch
  actually reaches the solver (see Gates).
- `nn_baseline_128_hgradient`: same overlay, provider returns NN
  `hkappa / Delta` from `dataset/model/c_exports/baseline_128_hgradient/`,
  clamped to `abs(kappa) <= 1/Delta`.

Add `--nn-only` to skip the three control modes and reuse the most recent
results directory whose `manifest.json` source fingerprint (SHA-256 of
`rising.c` + `integral.h` + compile flags) matches and whose
`gate_verdict.json` says `all_passed`. This is the only way `nn_baseline_*`
modes should be re-run when adding more models — controls are expensive
relative to a single NN run and must not be repeated per model. If no gated
control set matches, the runner refuses to run and tells you to run without
`--nn-only` first.

## Gates

1. **Native-wrapper equivalence (hard gate).** `native_wrapper` must match
   `original` on `out` (ignoring the wall-clock `perf.t`/`perf.speed`
   fields via `compare_out.py`) and be byte-identical on `log`. If this
   fails, the overlay changed more than the `ki` dispatch.
2. **Overlay liveness (hard gate).** `native_perturbed` must *differ* from
   `original`. If it doesn't, the `ki` replacement never reached the
   solver — every overlay-mode result, including NN, would be meaningless
   silently.
3. **`basilisk/` untouched.** `git status --short -- basilisk` must show no
   entries beyond whatever pre-existed before this experiment ran.

See `docs/superpowers/plans/2026-07-09-rising-clsvof-kreplace.md` for the
full task list, including the `t = 0` curvature spot-check that gates
before any NN dynamics are interpreted.

## A qcc quirk this harness works around

Basilisk's `qcc` resolves `#include` lines by scanning source text, not by
evaluating `#if`/`#ifdef` — even a textually-present but logically
unreachable `#include` (e.g. inside `#if RISING_K_MODE == RISING_K_NN_RAW`
when compiling with `RISING_K_MODE=RISING_K_NATIVE`) must still resolve to
a real file or the compile fails. Because of this, `native_wrapper` and
`native_perturbed` are compiled with the same
`-I tools/clsvof_model/include -I dataset/model/c_exports/baseline_128_hgradient`
paths as the NN modes even though their code path never touches the NN
model — the model directory used is an arbitrary placeholder, never
semantically referenced. `tools/basilisk-cc` was also fixed to stop adding
a redundant `-I"$BASILISK"` for external sources, which was independently
causing `qcc` to stage headers without include guards (e.g. `bcg.h`, which
both `navier-stokes/centered.h` and `tracer.h` include) twice and fail with
spurious "redefinition" errors.

## Output layout

```text
results/<UTC timestamp>/
  original/{out,log}
  native_wrapper/{out,log,integral.h}
  native_perturbed/{out,log,integral.h}
  nn_<model_name>/{out,log,integral.h}
  manifest.json
  gate_verdict.json      # written after Task 5 gate checks pass
  summary.md              # written by summarize_canary.py
```

Gated NN outputs are additionally published to
`dataset/nn_data/rising-clsvof/<model_name>/` once the gates pass (see the
plan's Run Economy and Data Placement policy) — that tree, not
`results/`, is the place to look for curated data to plot against
`dataset/official_data/`.
