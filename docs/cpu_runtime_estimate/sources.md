# Revised 128-CPU runtime estimate source notes

Generated: 2026-07-13 (Asia/Shanghai)

## Decision and corrected scope

Estimate the wall time after two scope corrections:

- Rising bubble includes both Hysing Case 1 and Case 2.
- Stationary bubble includes N64, N128, and N256, but excludes N512.

Price is not the primary decision criterion. The target remains an Ubuntu 22.04
128-CPU resource pool with resource-aware OpenMP row concurrency.

## Revised matrix

| Benchmark branch | Resolutions | Methods | imax | Rows |
| --- | --- | --- | --- | ---: |
| capwave | 64, 128, 256, 512 | native, NN cell-offset | 0-5 | 48 |
| rising Hysing Case 1 | 64, 128, 256, 512 | native, NN cell-offset | 0-5 | 48 |
| rising Hysing Case 2 | 64, 128, 256, 512 | native, NN cell-offset | 0-5 | 48 |
| stationary bubble | 64, 128, 256 | native, NN cell-offset | 0-5 | 36 |

Total: 180 formal rows.

## NN cell-offset implementation audit

There are two formal methods, not three: `native` and `nn`. The
benchmark branches are capwave, rising Case 1, rising Case 2, and stationary.

- Capwave, rising Case 1, and stationary generators copy the same canonical
  header: `cases/_shared/nn_cell_curvature/src/clsvof_nn_cell_curvature.h`.
- All three use the same `make_overlay_integral.py`, which replaces exactly the
  active `distance_curvature(point, d)` assignment and includes the canonical
  header.
- All three select weights only by resolution from
  `experiments/clsvof_kappa_offset_conversion/models/c_exports/baseline_<resolution>_hgradient/nn_weights.h`.
- The canonical header SHA-256 is
  `4e9509025d48dcbdf59f9407aa868321fdf54abd8129097fd17748dd78f5dc1b`.
  It matches the completed stationary N64 cell-offset artifact.
- Rising Case 2 is not yet connected to the new formal generator. The current
  generator explicitly says Hysing Case 1 and does not pass `-DCASE2=1`.
- Legacy Case 2 results under
  `experiments/rising_clsvof_kreplace/results_case2/` prove the official Case 2
  host can run with `-DCASE2=1`, but they use the older `rising_k_provider`
  route and must not be relabelled as formal shared-header cell-offset evidence.

Required implementation: add a `--case 1|2` argument, pass `-DCASE2=1` only for
Case 2, route results to separate `rising_case1` and `rising_case2` directories,
and record the same canonical header and weight SHA-256 in both manifests.

## Repository runtime evidence

- Native capwave and rising Case 1 timings: 48 completed imax 0-5 rows under
  `experiments/clsvof_redistance_imax_matrix/results/20260710T172910Z/`.
- Capwave, both methods: 72.53 equivalent Apple-M3 single-thread hours.
- Rising Case 1, both methods: 14.21 hours.
- Rising Case 2 has a completed legacy N256 canary, but no formal four-
  resolution imax matrix. Its current planning estimate is 2.0 times Case 1,
  with a sensitivity range of 1.5-2.5 times: 21.32-35.53 hours, central 28.42.
- Stationary N64 full-horizon evidence: native about 43.5 minutes and current
  NN cell-offset about 20.9 minutes. N128 and N256 remain modeled.

## Workload model after removing stationary N512

Stationary uses the same measured N64 base and imax factor as the previous
report, with resolution exponent p in {3.0, 3.25, 3.5}; only N64-N256 are now
included.

- Stationary low, p=3.0: 442.93 hours.
- Stationary central, p=3.25: 612.96 hours.
- Stationary high, p=3.5: 851.35 hours.
- Complete matrix equivalent work, using central 2.0x for rising Case 2:
  - optimistic: 558.09 hours.
  - central: 728.12 hours.
  - conservative: 966.51 hours.
- Stationary is 84.2% of the central workload, down from 98.5% when N512 was
  included.

## 128-CPU wall-time model

Using the same provisional aggregate effective throughput assumptions:

- optimistic: 558.09 / 48 = 11.6 hours.
- central: 728.12 / 40 = 18.2 hours.
- conservative: 966.51 / 32 = 30.2 hours.

Thus the formal matrix is provisionally a 12-30 hour job on the performance-
first EPYC 9754 configuration. Allow about two calendar days for preflight,
OpenMP canaries, formal execution, validation, retries, and packaging. This is
still a model, not an observed server benchmark.

## Important limitations

- Rising Case 2 formal cell-offset generation is not implemented yet.
- No target-host OpenMP scaling canary has been run.
- Stationary N128/N256 runtimes remain modeled.
- The NN statistics globals are not thread-safe and must be converted to
  per-thread accumulation before formal OpenMP execution.
- The server's 128 CPU label may describe vCPUs rather than physical cores;
  `lscpu -e=CPU,CORE,SOCKET,NODE` remains a mandatory preflight check.

## Report chart map

- Runtime strategy bar chart: compare 128x1, 64x2, and 32x4 under the central
  728.12-hour workload. It supports the claim that row concurrency is likely to
  finish the matrix sooner than one 128-thread row.
