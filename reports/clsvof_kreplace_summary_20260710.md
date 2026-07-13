# CLSVOF NN Curvature Replacement Status 20260710

## Executive Verdict

Status: **accepted for the requested rising + capwave closure**.

The raw27 and C forward contract gate is proven for a nonzero golden vector across all four `baseline_{64,128,256,512}_hgradient` exports. Rising case1 now has same-host accepted runtime evidence: the native-wrapper and overlay-liveness gates pass, and all four NN rows reran with `provider_evaluations=216126` and `clamp_hits=0`.

Rising case2 now has accepted runtime evidence from a fresh rerun with provider stats and a gate verdict. Capwave has accepted fixed-sweep control evidence for the checked stock host loop and accepted matched-resolution NN rows for N64/N128/N256/N512. No accepted NN row has nonzero clamp hits.

## Gate Table

| gate | status | evidence |
| --- | --- | --- |
| model exports present | passed | four directories exist under `dataset/model/c_exports/` |
| zero-input C export smoke | passed | `test_export_parity.py`, max abs diff `3.168e-08` |
| nonzero golden raw27 parity | passed | `test_golden_vector_parity.py` checks C `patch5` builder against PINN extractor fixture |
| nonzero C forward parity | passed | same test checks all four checkpoints against PyTorch |
| overlay single-site replacement | passed | pytest checks only `double ki = distance_curvature(point, d)` is replaced |
| provider eval/clamp counters | implemented | overlay emits `rising_k_provider_stats evaluations=... clamp_hits=...` at `t=end` |
| rising case1 runtime rows with clamp hits | passed | all four NN rows report `provider_evaluations=216126`, `clamp_hits=0` |
| rising case2 runtime rows with clamp hits | passed | `20260709T174800Z` has a gate verdict and all four NN rows report zero clamp hits |
| capwave scaffold tests | passed | `experiments/capwave_clsvof_kreplace/tests` covers overlay, single-resolution patch, run script flags, summary parsing |
| capwave raw27 parity | passed | `test_golden_vector_parity.py` now checks capwave C `patch5` builder against the PINN extractor fixture |
| capwave diagnostic imports | diagnostic | three stable `/private/tmp` result bundles imported under `experiments/capwave_clsvof_kreplace/diagnostic_imports/` |
| capwave fixed-sweep runtime rows with clamp hits | passed | `20260709T173527Z` stock host loop N=16..128 has zero clamp hits and exact official wave equivalence |
| capwave matched-resolution N64/N128 rows with clamp hits | passed | N64 `20260709T173049Z` and N128 `20260709T174010Z` have zero clamp hits |
| capwave matched-resolution N256/N512 rows with clamp hits | passed | N256 `20260709T182905Z` and N512 `20260709T190130Z` have zero clamp hits |

## Call-Site Contract

Current overlay target:

| source line role | replacement |
| --- | --- |
| rising `double ki = distance_curvature (point, d);` | `double ki = rising_k_provider (point, d);` |
| capwave `double ki = distance_curvature (point, d);` | `double ki = capwave_k_provider (point, d);` |

The replacement remains inside the existing Basilisk interface-crossing guard. `CURVATURE==2` prefilled-kappa mode is not current evidence.

## Rising Evidence

| identity | status | reason |
| --- | --- | --- |
| case1 `experiments/rising_clsvof_kreplace/results/20260709T141809Z` | accepted | native-wrapper equivalence and overlay liveness passed; all four NN rows have `clamp_hits=0` |
| case1 four-checkpoint table | diagnostic | valid runtime evidence, but this is a training-rho/checkpoint ablation, not a cross-case headline result |
| case2 `experiments/rising_clsvof_kreplace/results_case2/20260709T174800Z` | accepted | fresh rerun completed with `gate_verdict.json`; all four NN rows have `clamp_hits=0` |

Case1 accepted-runtime rows:

| mode | provider evals | clamp hits | d max(vb) | d final vb | d final xb | role |
| --- | --- | --- | --- | --- | --- | --- |
| `nn_baseline_64_hgradient` | 216126 | 0 | 0 | -1.3e-05 | -1e-05 | diagnostic ablation |
| `nn_baseline_128_hgradient` | 216126 | 0 | -1e-06 | -1.4e-05 | -1e-05 | diagnostic ablation |
| `nn_baseline_256_hgradient` | 216126 | 0 | -2e-06 | -1.5e-05 | -2e-05 | diagnostic ablation |
| `nn_baseline_512_hgradient` | 216126 | 0 | -1e-06 | -1.7e-05 | -2e-05 | diagnostic ablation |

Case2 accepted-runtime rows:

| mode | provider evals | clamp hits | d max(vb) | d final vb | d final xb | role |
| --- | --- | --- | --- | --- | --- | --- |
| `nn_baseline_64_hgradient` | 102641 | 0 | 0 | 0.000145 | -1e-05 | diagnostic ablation |
| `nn_baseline_128_hgradient` | 102672 | 0 | 0 | 0.00018 | 1e-05 | diagnostic ablation |
| `nn_baseline_256_hgradient` | 102862 | 0 | 0 | 0.000289 | 1e-05 | diagnostic ablation |
| `nn_baseline_512_hgradient` | 102638 | 0 | 0 | 8.7e-05 | -1e-05 | diagnostic ablation |

## Capwave Evidence

| identity | status | reason |
| --- | --- | --- |
| main-workspace scaffold `experiments/capwave_clsvof_kreplace` | accepted scaffold | implementation and tests exist; selected-mode runner records source hashes and selected modes |
| diagnostic imports `experiments/capwave_clsvof_kreplace/diagnostic_imports/20260710_from_private_tmp` | diagnostic | stable temp result bundles copied with provenance; they predate the capwave raw27/counter gate |
| `/private/tmp/cfd-capwave-clsvof-kreplace/results/20260709T134408Z` | blocked | active N512 temp run was still writing during import and was not copied as complete evidence |
| capwave fixed-sweep `20260709T173527Z` | accepted | checked stock host loop N=16..128; source hashes recorded; all provider footers have zero clamp hits |
| capwave fixed-sweep `20260709T173134Z` | superseded | runner bug mislabeled a single N128 patched case as fixed sweep; not used as accepted evidence |
| capwave matched-resolution N64 `20260709T173049Z` | accepted | source hashes recorded; `provider_evaluations=48640`, `clamp_hits=0` |
| capwave matched-resolution N128 `20260709T174010Z` | accepted | source hashes recorded; `provider_evaluations=285144`, `clamp_hits=0` |
| capwave matched-resolution N256 `20260709T182905Z` | accepted | source hashes recorded; `provider_evaluations=1522472`, `clamp_hits=0` |
| capwave matched-resolution N512 `20260709T190130Z` | accepted | source hashes recorded; `provider_evaluations=8756096`, `clamp_hits=0` |

Capwave accepted rows:

| identity | dataset CLSVOF rel RMS | NN/control rel RMS | provider evals | clamp hits | wave RMS delta vs dataset CLSVOF |
| --- | ---: | ---: | ---: | ---: | ---: |
| fixed-sweep N16/N32/N64/N128 native wrapper | official waves exact for all four rows | official waves exact for all four rows | 11824 / 35536 / 84176 / 369320 | 0 / 0 / 0 / 0 | 0 |
| matched N64 `nn_baseline_64_hgradient` | 0.00722669 | 0.00710848 | 48640 | 0 | 2.2446043891668784e-06 |
| matched N128 `nn_baseline_128_hgradient` | 0.00205188 | 0.00210084 | 285144 | 0 | 6.0833730999045488e-07 |
| matched N256 `nn_baseline_256_hgradient` | 0.00109024 | 0.0011096 | 1522472 | 0 | 2.684901301009066e-07 |
| matched N512 `nn_baseline_512_hgradient` | 0.000836646 | 0.000836798 | 8756096 | 0 | 3.91611427348643e-08 |

## Verification Commands

| command | result |
| --- | --- |
| `python3 -m pytest experiments/rising_clsvof_kreplace/tests` | 20 passed |
| `bash experiments/rising_clsvof_kreplace/tests/test_feature_header_compile.sh` | passed |
| `python3 -m pytest experiments/capwave_clsvof_kreplace/tests` | 17 passed |
| `bash experiments/capwave_clsvof_kreplace/tests/test_feature_header_compile.sh` | passed |
| `env KMP_DUPLICATE_LIB_OK=TRUE /opt/anaconda3/envs/pinn/bin/python -m pytest tools/clsvof_model/tests/test_golden_vector_parity.py` | 3 passed |
| `env KMP_DUPLICATE_LIB_OK=TRUE /opt/anaconda3/envs/pinn/bin/python tools/clsvof_model/tests/test_export_parity.py` | passed, max abs diff `3.168e-08` |
| `bash experiments/rising_clsvof_kreplace/run_canary.sh --case2` | accepted case2 row set, all provider-backed modes `clamp_hits=0` |
| `CAPWAVE_SELECTED_MODES=nn_baseline_64_hgradient bash experiments/capwave_clsvof_kreplace/run_canary.sh` | accepted N64 row, `clamp_hits=0` |
| `CAPWAVE_SELECTED_MODES=native_wrapper_fixed_sweep bash experiments/capwave_clsvof_kreplace/run_canary.sh` | accepted corrected fixed sweep, `clamp_hits=0` for N16/N32/N64/N128 |
| `CAPWAVE_SELECTED_MODES=nn_baseline_128_hgradient bash experiments/capwave_clsvof_kreplace/run_canary.sh` | accepted N128 row, `clamp_hits=0` |
| `CAPWAVE_SELECTED_MODES=nn_baseline_256_hgradient bash experiments/capwave_clsvof_kreplace/run_canary.sh` | accepted N256 row, `clamp_hits=0` |
| `CAPWAVE_SELECTED_MODES=nn_baseline_512_hgradient bash experiments/capwave_clsvof_kreplace/run_canary.sh` | accepted N512 row, `clamp_hits=0` |

## Final Status Table

| item | status |
| --- | --- |
| rising case1 | accepted |
| rising case2 | accepted |
| capwave fixed-sweep N16/N32/N64/N128 | accepted |
| capwave matched-resolution N64/N128/N256/N512 | accepted |

## Limitations

This report does not claim NN improvement. The accepted rising and capwave rows show same-host near-parity with zero clamp hits, not solver-level superiority. Temporary imports and the mislabeled fixed-sweep run remain diagnostic/superseded and are not used as accepted evidence.
