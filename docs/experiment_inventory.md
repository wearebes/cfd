# CFD Experiment Inventory

Last audited: 2026-07-10 00:15:53 CST

Purpose: keep every CFD run identifiable before results are interpreted. A row is report-usable only when it has an explicit result directory, manifest/provenance, completed raw outputs, and a summary/gate status.

## Current Contract Vocabulary

| Field | Meaning |
| --- | --- |
| `original` | Stock Basilisk case, no local `integral.h` overlay. |
| `native_wrapper` | Local overlay is compiled, but provider returns `distance_curvature(point, d)`. This is the equivalence control. |
| `native_perturbed` | Local overlay is compiled and returns `distance_curvature(point, d) * 1.001`. This is a liveness control only. |
| `nn_baseline_<N>_hgradient` | Overlay provider builds raw27 features, runs the exported MLP header from `experiments/clsvof_kappa_offset_conversion/models/c_exports/baseline_<N>_hgradient/nn_weights.h`, converts `h*kappa` to `kappa`, then applies the configured clamp. |
| `raw27` | `[phi9/Delta, nx9, ny9]`; exact stencil order and `ny` sign are implementation-specific and must be recorded for each experiment family. |
| `scale` | NN output is `h*kappa`; solver curvature is `kappa = hkappa / Delta`. |
| `clamp` | Current k-replacement experiments use `abs(kappa) <= 1/Delta` unless a run explicitly records otherwise. |

## Report-Use Gate

Do not treat a run as final evidence unless all are true:

| Gate | Required evidence |
| --- | --- |
| G1 identity | Result directory has a manifest naming source case, source `integral.h`, replacement, modes, weights, compile flags, and clamp. |
| G2 completion | Every expected mode has non-empty raw outputs (`out`/`log` for rising, `stdout.txt`/`log`/`wave-*` for capwave). |
| G3 overlay control | `native_wrapper` is equal to `original`, and `native_perturbed` differs when that mode is part of the design. |
| G4 NN provenance | Every NN row records the exact weight header path and checkpoint policy. |
| G5 feature contract | raw27 order/sign/scale is explicit; unresolved feature-convention experiments stay diagnostic only. |
| G6 summary | Summary table exists and states whether the row is accepted, partial, or diagnostic. |

## Rising CLSVOF K-Replacement Runs

Common implementation:

| Property | Value |
| --- | --- |
| Workspace | `/Users/jcy/research/cfd/experiments/rising_clsvof_kreplace` |
| Source case | `/Users/jcy/research/cfd/basilisk/src/test/rising.c` |
| Source integral | `/Users/jcy/research/cfd/basilisk/src/integral.h` |
| Overlay replacement | `double ki = distance_curvature(point, d)` -> `double ki = rising_k_provider(point, d)` |
| Feature header | `/Users/jcy/research/cfd/experiments/rising_clsvof_kreplace/include/clsvof_nn_features.h` |
| Current raw27 convention | `j=-1..1`, `i=-1..1`; `phi=d/Delta`; `nx=gx/|g|`; `ny=-gy/|g|` |
| NN scale/clamp | `kappa = hkappa / Delta`, then `abs(kappa) <= 1/Delta` |

| Exp ID | Case | Command family | Modes | Result root | Status | Evidence boundary |
| --- | --- | --- | --- | --- | --- | --- |
| `RISE-C1-20260709T141809Z` | Hysing rising case 1, `-DLEVELSET=1 -DCLSVOF=1` | `experiments/rising_clsvof_kreplace/run_canary.sh` plus later `--nn-only` additions | `original`, `native_wrapper`, `native_perturbed`, `nn_baseline_64_hgradient`, `nn_baseline_128_hgradient`, `nn_baseline_256_hgradient`, `nn_baseline_512_hgradient` | `/Users/jcy/research/cfd/experiments/rising_clsvof_kreplace/results/20260709T141809Z` | Completed and summarized. Controls have `gate_verdict.json`; NN rows are summarized but should remain diagnostic until raw27 parity is explicitly closed. | `manifest.json`, `gate_verdict.json`, `summary.md`, `t0_spot_check_report.txt`, per-mode `out`/`log`. |
| `RISE-C2-20260709T153210Z` | Hysing rising case 2, `-DLEVELSET=1 -DCLSVOF=1 -DCASE2=1` | `experiments/rising_clsvof_kreplace/run_canary.sh --case2` | Intended: `original`, `native_wrapper`, `native_perturbed`, `nn_baseline_64_hgradient`, `nn_baseline_128_hgradient`, `nn_baseline_256_hgradient`, `nn_baseline_512_hgradient` | `/Users/jcy/research/cfd/experiments/rising_clsvof_kreplace/results_case2/20260709T153210Z` | Partial/in progress. Archived evidence exists through `nn_baseline_128_hgradient`; current active process is building/running `nn_baseline_256_hgradient`; no summary or gate verdict yet. | `manifest.json`, partial per-mode `out`/`log`. Do not use for final comparison yet. |

Active rising process observed at audit time:

| PID group | Meaning | Status |
| --- | --- | --- |
| `bash experiments/rising_clsvof_kreplace/run_canary.sh --case2` | Case 2 matrix run in current workspace. | Active. |
| `qcc ... -DCASE2=1 -DRISING_K_MODE=RISING_K_NN_RAW ... baseline_256_hgradient` | Case 2 NN `baseline_256_hgradient` compile/run step. | Active/incomplete; work dir has binary but `out`/`log` were empty at audit time. |

## Capwave CLSVOF K-Replacement Runs

Important: capwave implementation/results are currently in a temporary worktree, not the main workspace.

| Property | Value |
| --- | --- |
| Temporary workspace | `/private/tmp/cfd-capwave-clsvof-kreplace/experiments/capwave_clsvof_kreplace` |
| Main workspace state | Only plans exist under `/Users/jcy/research/cfd/docs/superpowers/plans`; no `/Users/jcy/research/cfd/experiments/capwave_clsvof_kreplace` implementation directory was present at audit time. |
| Source case | `/private/tmp/cfd-capwave-clsvof-kreplace/basilisk/src/test/capwave-clsvof.c` |
| Overlay replacement | `double ki = distance_curvature(point, d)` -> `double ki = capwave_k_provider(point, d)` |
| Feature header | `/private/tmp/cfd-capwave-clsvof-kreplace/experiments/capwave_clsvof_kreplace/include/clsvof_nn_features.h` |
| Current raw27 convention | `j=-1..1`, `i=-1..1`; `phi=d/Delta`; `nx=gx/|g|`; `ny=gy/|g|` |
| NN scale/clamp | `kappa = hkappa / Delta`, then `abs(kappa) <= 1/Delta` |

| Exp ID | Case | Modes | Result root | Status | Evidence boundary |
| --- | --- | --- | --- | --- | --- |
| `CAP-CANARY-128-20260709T093531Z` | Capillary wave CLSVOF original loop, N = 16, 32, 64, 128 | `original`, `native_wrapper`, `nn_baseline_128_hgradient` | `/private/tmp/cfd-capwave-clsvof-kreplace/experiments/capwave_clsvof_kreplace/results/20260709T093531Z` | Completed and summarized. Diagnostic until copied/registered in main workspace. | `manifest.json`, `summary.md`, per-mode `stdout.txt`/`log`/`wave-*`. |
| `CAP-MATRIX-ALL-20260709T122142Z` | Capillary wave CLSVOF original loop, all modes emit N = 16, 32, 64, 128 | `original`, `native_wrapper`, `nn_baseline_64_hgradient`, `nn_baseline_128_hgradient`, `nn_baseline_256_hgradient`, `nn_baseline_512_hgradient` | `/private/tmp/cfd-capwave-clsvof-kreplace/experiments/capwave_clsvof_kreplace/results/20260709T122142Z` | Completed and summarized. Not a matched-resolution design; every NN checkpoint is evaluated across the same N loop. | `manifest.json`, `summary.md`, per-mode `stdout.txt`/`log`/`wave-*`. |
| `CAP-CTRL-SINGLE-N-20260709T130114Z` | Capillary wave single-resolution controls | `original_N64`, `original_N128`, `original_N256`, `native_wrapper_N64`, `native_wrapper_N128` | `/private/tmp/cfd-capwave-clsvof-kreplace/experiments/capwave_clsvof_kreplace/results/20260709T130114Z` | Partial control-only scratch run. No manifest or summary observed. | Per-mode `stdout.txt`/`log`/`wave-*`; diagnostic only. |
| `CAP-MATCHED-NN-20260709T134408Z` | Capillary wave matched checkpoint/resolution run | Intended: `nn_baseline_64_hgradient` at N64, `nn_baseline_128_hgradient` at N128, `nn_baseline_256_hgradient` at N256, `nn_baseline_512_hgradient` at N512 | `/private/tmp/cfd-capwave-clsvof-kreplace/experiments/capwave_clsvof_kreplace/results/20260709T134408Z` | Partial/in progress. Results for 64/128/256 were archived; 512 was still running at audit time. No summary observed yet. | Partial per-mode `stdout.txt`/`log`/`wave-*`; do not use until 512 archives and summary is produced. |

Active capwave process observed at audit time:

| PID group | Meaning | Status |
| --- | --- | --- |
| `/private/tmp/cfd-capwave-clsvof-kreplace/.../nn_baseline_512_hgradient` | Matched N512 capwave NN run. | Active. |
| `./capwave-clsvof` | Actual capwave binary for `nn_baseline_512_hgradient`. | Active/incomplete; result copy step had not completed at audit time. |

## Planned But Not Yet Main-Workspace Results

| Plan | Path | Current state |
| --- | --- | --- |
| Rising CLSVOF k replacement | `/Users/jcy/research/cfd/docs/superpowers/plans/2026-07-09-rising-clsvof-kreplace.md` | Implemented in `/Users/jcy/research/cfd/experiments/rising_clsvof_kreplace`. |
| Capwave CLSVOF k replacement | `/Users/jcy/research/cfd/docs/superpowers/plans/2026-07-09-capwave-clsvof-kreplace.md` | Implemented only in `/private/tmp/cfd-capwave-clsvof-kreplace` at audit time. |
| Capwave model matrix | `/Users/jcy/research/cfd/docs/superpowers/plans/2026-07-09-capwave-clsvof-model-matrix-run-plan.md` | Partially executed in temporary capwave workspace. Needs main-workspace sync/registration before it is treated as durable evidence. |

## Immediate Rules Before More Runs

1. Add a new row here before launching a new CFD run.
2. Do not reuse a result directory for a different experiment identity.
3. Do not count active work directories as completed evidence.
4. Keep `case1` and `case2` rising results separate.
5. Keep capwave temporary-worktree results separate from main-workspace durable results until copied with provenance.
6. Do not merge `per-resolution checkpoint` rows with `fixed-r128 cleanroom` rows in the same report table.
7. Any row involving NN must state the exact raw27 convention and whether `ny` is flipped.
8. A final report table should include `Exp ID`, `case`, `mode`, `checkpoint`, `raw27 contract`, `scale`, `clamp`, `result root`, and `status`.

## Formal CLSVOF Redistance `imax` Matrix

| Exp ID | Scope | Matrix | Result root | Status | Evidence contract |
| --- | --- | --- | --- | --- | --- |
| `CLSVOF-IMAX-20260710T172910Z` | Capwave + Hysing rising Case 1; N=64/128/256/512; imax=0..5 | Currently retained: 48 native cells; 5 native `imax=3` candidate-reuse rows preserve `reuse_validation`. The former 48 NN cells used obsolete direct `q_gamma/Delta` and were deleted with all derived aggregates/audits/figures. | `experiments/clsvof_redistance_imax_matrix/results/20260710T172910Z` | Native-only retained evidence; not a complete matrix and supports no NN-versus-native conclusion. Future NN rows must use shared cell-offset curvature and a new matrix identity. | `results/20260710T172910Z/NATIVE_ONLY_RETAINED.md`, `docs/repository_organization_plan.md` |
