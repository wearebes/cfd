# CLSVOF Redistance `imax` Formal Matrix Goal Plan

Date: 2026-07-11  
Workspace: `/Users/jcy/research/cfd`  
Execution mechanism: Codex Goal  
Current phase: **complete; 96/96 rows and strict closure passed**

Completion record (2026-07-12): matrix `20260710T172910Z` finished with 96
completed rows, zero failed rows, strict row audit PASS, workspace-boundary
audit PASS, matrix/golden verification PASS, six figure families with visual QA
PASS, and final closure audit PASS.

## 1. Goal

Run a formal, same-host experiment that isolates the effect of Basilisk
CLSVOF redistance iteration count

```text
imax in {0, 1, 2, 3, 4, 5}
```

for both physical benchmarks

```text
capillary wave
Hysing rising bubble Case 1
```

and both curvature methods

```text
CLSVOF native curvature
CLSVOF-NN matched-resolution curvature model
```

at source-resolution labels

```text
N in {64, 128, 256, 512}.
```

The final deliverable is not just raw runs. It must establish how `imax`
changes:

1. physical benchmark accuracy;
2. signed-distance quality of the evolved `d` field;
3. native-versus-NN paired behavior;
4. stability, volume/interface preservation, and failure rate;
5. runtime and scaling.

## 2. Scope decision requiring user confirmation

This plan interprets **rising bubble** as the primary official Hysing
**Case 1** benchmark only. Case 2 is not included in the 96-cell matrix.
Adding Case 2 would add another 48 formal cells and must be a separate goal
or an explicit scope expansion.

No stationary-bubble experiment is included.

## 3. Source-grounded fixed contracts

### 3.1 Official default

The live stock header calls:

```c
redistance (d, imax = 3, phixxmin = HUGE);
```

in `basilisk/src/two-phase-clsvof.h`. Thus `imax=3` is the official default
and the center/reference column of this sweep.

### 3.2 Only treatment variable

The only intended treatment variable is `imax`.

The following must remain fixed:

- `cfl = 0.5`;
- `order = 3`;
- `eps = 1e-6` for the physical call;
- `band = HUGE` for the solver convergence check;
- `phixxmin = HUGE`;
- CLSVOF VOF-relaxation weight `0.1`;
- benchmark geometry, material properties, boundary conditions, final time,
  tolerances, and output cadence;
- native curvature formula and integral surface-tension assembly;
- NN raw27 builder, feature order/sign, model weights, output scaling, and
  `abs(kappa) <= 1/Delta` clamp.

`imax=0` is defined precisely as:

```text
VOF relaxation remains active;
the Eikonal redistance loop is skipped;
the rest of CLSVOF remains active.
```

It must be labelled `imax0_no_eikonal`, not `no_clsvof`.

### 3.3 Method identities

| Formal method | Curvature provider | NN model policy |
| --- | --- | --- |
| `clsvof` | `distance_curvature(point, d)` through the accepted native wrapper | none |
| `clsvof_nn` | accepted benchmark-specific NN provider | `baseline_<N>_hgradient` matched to the same source-resolution label `N` |

The existing benchmark-specific feature contracts are frozen rather than
silently unified. Their exact stencil order, normal sign convention, scaling,
clamp, weight-header hash, and provider-header hash must be recorded in every
NN manifest.

## 4. Resolution identities

### 4.1 Capillary wave

For capwave, the source label is the square-grid `N` used by the stock case.

| Label | Grid | NN checkpoint |
| ---: | ---: | --- |
| 64 | 64 x 64 | `baseline_64_hgradient` |
| 128 | 128 x 128 | `baseline_128_hgradient` |
| 256 | 256 x 256 | `baseline_256_hgradient` |
| 512 | 512 x 512 | `baseline_512_hgradient` |

Physical reference: Prosperetti amplitude history.  
Final time: stock `t = 2.2426211256` with the stock 738 sample schedule.

### 4.2 Rising bubble Case 1

Rising uses `dimensions(nx = 4)` and `init_grid(1 << LEVEL)`. The formal
resolution label is `N = 1 << LEVEL`, not the short-side cell count.

| Label `N` | Compile flag | Actual grid | NN checkpoint |
| ---: | ---: | ---: | --- |
| 64 | `-DLEVEL=6` | 64 x 16 | `baseline_64_hgradient` |
| 128 | `-DLEVEL=7` | 128 x 32 | `baseline_128_hgradient` |
| 256 | `-DLEVEL=8` | 256 x 64 | `baseline_256_hgradient` |
| 512 | `-DLEVEL=9` | 512 x 128 | `baseline_512_hgradient` |

Physical reference: Hysing/MooNMD Case 1.  
Final time: stock `t = 3`.

This distinction is essential: the existing rising four-checkpoint run used
the same default `LEVEL=8` grid for all four checkpoints. It is a checkpoint
ablation at `N=256`, not a four-resolution sweep.

## 5. Formal result matrix

The formal matrix contains:

```text
2 benchmarks x 2 methods x 4 resolutions x 6 imax values = 96 cells
```

### 5.1 Count by benchmark and method

| Benchmark | Method | Resolutions | `imax` values | Formal cells |
| --- | --- | ---: | ---: | ---: |
| capwave | `clsvof` | 4 | 6 | 24 |
| capwave | `clsvof_nn` | 4 | 6 | 24 |
| rising Case 1 | `clsvof` | 4 | 6 | 24 |
| rising Case 1 | `clsvof_nn` | 4 | 6 | 24 |
| **Total** |  |  |  | **96** |

Each `imax` slice contains 16 paired results:

```text
capwave: 4 native + 4 NN
rising:  4 native + 4 NN
```

### 5.2 Existing `imax=3` reuse audit

Candidate reusable formal cells, subject to source/hash and generated-header
equivalence gates:

| Benchmark | Candidate reusable `imax=3` cells | Count |
| --- | --- | ---: |
| capwave native | N64, N128, N256, N512 from accepted/archived stock CLSVOF data | 4 |
| capwave NN | matched N64, N128, N256, N512 accepted rows | 4 |
| rising native | official default N256 (`LEVEL=8`) | 1 |
| rising NN | matched `baseline_256_hgradient` at default N256 | 1 |
| **Candidate reuse** |  | **10** |

Missing `imax=3` formal cells:

```text
rising native N64, N128, N512
rising NN N64, N128, N512
```

Therefore, if all reuse gates pass:

```text
96 total - 10 reusable = 86 new formal cells to execute.
```

If a reused row fails source/provenance/equivalence checks, it is rerun and
the executed count increases; no stale result is silently imported.

The existing rising N256 runs using the 64/128/512 checkpoints remain useful
diagnostic checkpoint ablations, but they are not substituted into the
matched-resolution formal matrix.

## 6. Out-of-tree implementation contract

No file under `basilisk/src` may be edited.

Create a new isolated experiment surface:

```text
experiments/clsvof_redistance_imax_matrix/
  README.md
  config/matrix.json
  make_redistance_overlay.py
  run_row.py
  run_matrix.py
  summarize_matrix.py
  tests/
  work/                 # regenerable, ignored
  results/<matrix_id>/  # immutable evidence
```

`make_redistance_overlay.py` will copy the live stock
`two-phase-clsvof.h` into each row's work directory and make exactly one
guarded substitution:

```c
redistance (d, imax = 3, phixxmin = HUGE);
```

to a generated row-specific call using the requested integer `imax`. The
generator must fail unless the stock target occurs exactly once. It must emit
the source hash, generated hash, substitution count, and a diff snippet.

The copied stock benchmark source then resolves the generated local
`two-phase-clsvof.h`; include order must be tested explicitly with qcc.

For native and NN paired rows, the generated redistance header is identical.
Only the accepted curvature provider mode differs.

## 7. Instrumentation contract

This is a formal physical sweep, not the earlier diagnostic branch experiment.
Each row's evolved `d` must actually use its assigned `imax` for all subsequent
physics.

Read-only logging is still required so the mechanism can be interpreted:

- returned redistance iteration count per physical step;
- pre/post `E_grad = abs(|grad d| - 1)` in `1.5 Delta` and `3 Delta` bands;
- `grad_min`, `grad_max`, mean, RMS, and maximum `E_grad`;
- zero-sign mismatch count across redistance;
- VOF-versus-phi reconstructed volume difference;
- provider evaluations and clamp hits for NN;
- wall time for every row; stock-reported CPU time where the benchmark emits
  it (rising does, capwave does not); solver/redistance-call count and
  peak-status metadata. Cross-benchmark cost comparisons use the uniformly
  captured launcher wall time rather than a reconstructed CPU estimate.

Logging must use a fixed stride and always include initial/final records so it
does not create unbounded output. It must not modify `d`, `f`, curvature, or
the physical timestep.

## 8. Benchmark metrics

### 8.1 Capillary wave outputs

Per formal cell:

- complete stock-cadence `wave-N` history;
- relative RMS error against Prosperetti;
- maximum amplitude error;
- phase-sensitive time-history L2 error;
- paired NN-minus-native RMS and waveform delta at the same `(N, imax)`;
- `E_grad` summaries and returned-step distribution;
- volume/interface consistency;
- runtime and provider statistics.

Across resolutions:

- convergence plot and observed slope for each `(method, imax)`;
- `imax x N` heatmaps for physical error, SDF error, NN-native delta, and
  runtime.

### 8.2 Rising-bubble outputs

Per formal cell:

- full stock `out` time history and final interface facets;
- maximum rise velocity and time of maximum;
- final rise velocity;
- final center position;
- maximum relative volume drift;
- final-shape mean and maximum distance to MooNMD reference;
- paired NN-minus-native deltas at the same `(N, imax)`;
- `E_grad` summaries and returned-step distribution;
- runtime and provider statistics.

Across resolutions:

- velocity histories and final-shape overlays;
- `imax x N` heatmaps for velocity, position, volume, shape, SDF error,
  NN-native delta, and runtime.

## 9. Evidence layout and row state machine

Each cell has an immutable row identity:

```text
<benchmark>__case1-if-rising__<method>__N####__imax##
```

Suggested result layout:

```text
results/<matrix_id>/
  matrix_manifest.json
  matrix_status.csv
  capwave/N0064/imax00/clsvof/
  capwave/N0064/imax00/clsvof_nn/
  rising_case1/N0064/imax00/clsvof/
  rising_case1/N0064/imax00/clsvof_nn/
  ...
  tables/
    metrics_long.csv
    metrics_wide.csv
    runtime.csv
    failures.csv
  figures/
  summary.md
```

Every formal cell must end in one explicit state:

```text
planned
running
completed
failed_compile
failed_runtime
failed_nonfinite
failed_missing_output
blocked_resource
```

There may be failed cells, especially at `imax=0`; there may not be silent or
missing cells. A failed physical row remains a scientific result and records
the last valid time, error text, and partial outputs.

## 10. Gates and execution order

### Gate A: inventory freeze

Before implementation or running:

1. snapshot hashes of stock cases, `two-phase-clsvof.h`, `redistance.h`,
   `integral.h`, providers, feature headers, and four NN weight headers;
2. record the dirty-worktree baseline without deleting or resetting user work;
3. add the matrix identity to `docs/experiment_inventory.md`;
4. generate `matrix.json` with all 96 expected row IDs.

### Gate B: generator and compile tests

Required tests:

- exactly-one redistance-call substitution;
- `imax=0..5` generated correctly;
- invalid `imax` rejected;
- stock sources and `basilisk/src` unchanged;
- copied capwave and rising sources compile for native and NN modes;
- manifest hashes and row IDs are deterministic.

### Gate C: `imax=3` equivalence

Before reusing old rows, run cheap same-source equivalence checks:

- capwave N64 native generated-header replay versus stock imax=3;
- rising N256 native generated-header replay versus stock imax=3;
- confirm generated physical outputs match, ignoring only runtime fields;
- confirm the forced `imax=3` diagnostic path and stock call produce the same
  returned-step behavior.

If this gate fails, stop matrix execution and fix identity/provenance. Do not
reinterpret the mismatch as an `imax` effect.

### Gate D: full N64 extremes first

Execute complete physical rows for both methods and both benchmarks at N64,
starting with `imax=0` and `imax=5`. These are formal matrix cells, not throwaway
smokes. They test whether the two extreme settings remain finite to final time.

### Gate E: ascending-resolution matrix

After N64 results are complete:

1. finish all imax values at N64;
2. run N128;
3. run N256;
4. run N512;
5. keep native and matched NN rows adjacent for the same `(benchmark,N,imax)`.

Within a resolution, recommended order is:

```text
imax 3 -> 2 -> 4 -> 1 -> 5 -> 0
```

with already accepted imax=3 rows registered rather than rerun when reuse gates
pass.

### Gate F: closure

The matrix is closed only when:

- all 96 row IDs have terminal states;
- every completed row has expected raw outputs and hashes;
- summaries reproduce benchmark metrics from raw data;
- NN rows report weight provenance, evaluation count, and clamp hits;
- figures are generated only from accepted completed rows;
- failures are included in the summary rather than omitted;
- the final report distinguishes SDF improvement from physical improvement.

## 11. Run economy, persistence, and monitoring

Machine facts observed during planning:

```text
Apple M3, 8 CPU cores, 24 GB RAM
approximately 159 GiB workspace filesystem free
```

Observed imax=3 reference wall times include:

- capwave NN: about 22 s at N64, 204 s at N128, 1912 s at N256,
  and 18,580 s (5.16 h) at N512;
- capwave native extended N512: about 1693 s (28 min);
- rising default N256: about 120 s native and 232 s NN in the current runner.

The new work is dominated by capwave NN N512. A reasonable planning estimate
is roughly **35-45 sequential wall-clock hours** for the 86 new cells, with
uncertainty from `imax`, thermal throttling, failures, and reruns. This is an
estimate, not a completion promise.

Execution policy, revised after the user first authorised four and then
explicitly raised the ceiling to five single-core
cases on the 8-core/24-GB M3 while preserving capacity for daily work:

- hard ceiling: five concurrent Basilisk row processes;
- initial target after the completed two-process N64 extreme gate: three
  concurrent rows while AC-powered, memory pressure is healthy, and observed
  load/interactive behavior remains acceptable;
- the managed environment rejected both background QoS (`taskpolicy -b`) and
  positive `nice`; all formal rows therefore run at plain priority and
  concurrency is the primary protection for foreground applications;
- the scheduler may reduce its launch target from 5 to 4, 3, 2, or 1 when memory
  pressure drops, load remains high, thermal throttling is inferred from falling
  per-row throughput, or the user reports interactive lag;
- no new row starts while on battery; already-running, healthy rows are not
  killed solely because power state changes;
- use `memory_pressure -Q`, `pmset -g batt`, `uptime`, per-row progress rate,
  and active matrix-process count as launch signals;
- first complete the formal N64 `imax=0/5` extreme gate (completed successfully
  at two concurrent rows with about 56--58% free memory reported);
- after the extreme gate, use longest-processing-time-first scheduling to
  minimise makespan, starting expensive capwave NN high-resolution rows early
  while filling remaining slots with shorter paired native/NN rows;
- no more than five matrix rows total and no duplicate row identity may run;
- use a resumable launcher under `screen`/Goal monitoring and `caffeinate`
  while the queue is active;
- atomic status updates (`running` -> terminal state);
- preserve a completed row and skip it on resume when hashes match;
- monitor progress through output line counts, timestamps, and process status;
- do not kill a progressing long run merely because it is quiet;
- no destructive cleanup of work or partial results without a separate audit.

## 12. Final deliverables

1. `matrix_status.csv`: all 96 row identities and terminal states.
2. `metrics_long.csv`: one metric per row/key.
3. `metrics_wide.csv`: report-facing 96-row table.
4. Native/NN paired-delta tables at every `(benchmark,N,imax)`.
5. Capwave wave histories, RMS/convergence plots, and heatmaps.
6. Rising velocity/volume/shape plots and heatmaps.
7. SDF-quality versus physical-error analysis.
8. Runtime scaling and cost table.
9. Failure ledger for unstable/nonfinite rows.
10. `summary.md` with evidence-first conclusions:
    - best `imax` by benchmark/method/resolution;
    - whether an `imax` effect is consistent across resolution;
    - whether NN changes sensitivity to redistance;
    - whether better `E_grad` actually improves physical metrics;
    - whether the official `imax=3` is near the Pareto frontier.

## 13. Explicit non-goals

- no modification of `basilisk/src`;
- no retraining or tuning NN models;
- no change to curvature clamp, feature convention, or surface-tension
  formulation;
- no Case 2 rising matrix unless explicitly added;
- no stationary-bubble rows;
- no conclusion that lower `E_grad` is automatically better physics;
- no relabelling of existing rising checkpoint-ablation rows as
  matched-resolution evidence.

## 14. Approval checkpoint

The user confirmed the following scope on 2026-07-11:

1. rising scope is Hysing Case 1 only;
2. rising labels 64/128/256/512 mean `N=1<<LEVEL`, producing grids
   64x16/128x32/256x64/512x128;
3. NN uses the matched `baseline_<N>_hgradient` checkpoint;
4. the formal matrix is 96 cells, with 10 candidate imax=3 reuses and
   approximately 86 new runs;
5. failed/unstable rows count as formal outcomes rather than being silently
   replaced by altered parameters;
6. the scheduler was initially authorised for four concurrent single-core
   cases; the user subsequently raised the hard ceiling to five on the
   8-core/24-GB M3, with the existing AC-power, memory, no-duplicate, and
   adaptive-downshift safeguards unchanged.
