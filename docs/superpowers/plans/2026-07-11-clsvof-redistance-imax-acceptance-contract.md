# CLSVOF Redistance `imax` Matrix Acceptance Contract

Date: 2026-07-11  
Goal: formal `imax=0..5` matrix for capwave and Hysing rising-bubble Case 1  
Authority: this contract is subordinate to the user's final scope confirmation
and the main plan
`docs/superpowers/plans/2026-07-11-clsvof-redistance-imax-formal-matrix.md`.

The user confirmed the main scope on 2026-07-11, initially authorised an
adaptive maximum of four concurrent single-core cases, and subsequently raised
the hard ceiling to five on the 8-core/24-GB M3. This scheduling amendment does
not change any physical row identity or acceptance criterion.

## A. Matrix identity

The authoritative planned-row list is:

```text
docs/superpowers/plans/2026-07-11-clsvof-redistance-imax-matrix-preview.csv
```

The matrix is structurally valid only if all checks pass:

- exactly 96 data rows;
- exactly 96 unique `row_id` values;
- exactly 16 rows for each `imax` in `0,1,2,3,4,5`;
- exactly 24 rows for each benchmark/method pair;
- exactly 48 capwave rows;
- exactly 48 rising Case 1 rows;
- exactly two methods: `clsvof`, `clsvof_nn`;
- exactly four source-resolution labels: 64, 128, 256, 512;
- NN checkpoint equals `baseline_<N>_hgradient` for every NN row;
- rising resolution mapping is exactly:
  `N64/LEVEL6/64x16`, `N128/LEVEL7/128x32`,
  `N256/LEVEL8/256x64`, `N512/LEVEL9/512x128`.

The current planning preview contains 10 `candidate_reuse` rows and 86
`planned_run` rows. `candidate_reuse` is not equivalent to accepted evidence;
each candidate must pass Section D.

## B. Treatment isolation contract

Across the formal matrix, the intended treatment variable is only:

```text
redistance imax = 0, 1, 2, 3, 4, or 5
```

The following are invariants:

- stock benchmark geometry and initial conditions;
- stock physical final time and output cadence;
- material properties and boundary conditions;
- physical solver tolerances;
- CLSVOF VOF-relaxation weight `0.1`;
- redistance `cfl=0.5`, `order=3`, `eps=1e-6`, `band=HUGE`;
- CLSVOF `phixxmin=HUGE`;
- native curvature and surface-tension assembly;
- benchmark-specific accepted NN feature convention;
- NN checkpoint selected by matched source resolution;
- `h*kappa -> kappa` conversion;
- `abs(kappa) <= 1/Delta` clamp.

`imax=0` must retain VOF relaxation and skip only the Eikonal redistance
iteration loop.

Any source or configuration drift outside this list invalidates same-matrix
comparison until a new matrix identity is issued.

## C. Implementation gate

Implementation is accepted only if:

1. no tracked or untracked source under `basilisk/src` is created or modified
   by the matrix implementation;
2. work occurs under `experiments/clsvof_redistance_imax_matrix/`;
3. the redistance overlay generator finds exactly one stock target call;
4. invalid or non-integer `imax` values are rejected;
5. generated `imax=3` header differs from stock only by the parameterization
   mechanism required by the runner;
6. native and NN paired rows use byte-identical generated redistance headers;
7. source, generated-header, provider, feature, and weight hashes are included
   in each row manifest;
8. copied official capwave and rising cases compile in both native and NN
   modes;
9. automated tests prove deterministic row IDs, manifests, and matrix counts;
10. the pre-existing dirty-worktree baseline is recorded and preserved.

## D. Existing `imax=3` reuse gate

A candidate reuse row is accepted only if:

- raw output exists and is non-empty;
- the output reaches the official final time;
- all expected benchmark samples/files exist;
- source case, `two-phase-clsvof.h`, `redistance.h`, `integral.h`, provider,
  features, weights, compile flags, and physical settings are equivalent to
  the new matrix contract;
- the source/provenance chain is recorded in the new matrix manifest;
- a generated-header `imax=3` equivalence replay matches stock physical
  output, ignoring only nondeterministic runtime fields;
- the summarizer reproduces the previously published metric from raw data.

If any requirement is missing or cannot be proven, the row changes from
`candidate_reuse` to `planned_run` and is rerun. No value may be copied from a
summary table without its raw evidence.

## E. Per-row execution contract

Every attempted row receives:

- immutable `row_id`;
- start/end timestamps;
- exact command and working directory;
- compile flags and environment fields relevant to qcc/OpenMP;
- all source and generated-file hashes;
- expected benchmark, method, N, LEVEL/grid, checkpoint, and imax;
- atomic state transition from `planned` to `running` to one terminal state;
- stdout, stderr/log, physical raw output, diagnostic raw output, and manifest;
- wall time and final physical time for every row; stock-reported CPU time when
  present (rising) without inventing a value where the stock case omits it
  (capwave); solver/redistance-call count;
- last-progress timestamp for monitoring and recovery.

Allowed execution terminal states:

```text
completed
failed_compile
failed_runtime
failed_nonfinite
failed_missing_output
blocked_resource
```

No row may remain silently absent or indefinitely marked `running` after the
launcher has stopped.

## F. Completed-row physical gates

### F1. Capillary wave

A capwave row is `completed` only if:

- solver reaches stock final time `t=2.2426211256`;
- `wave-N` contains the complete stock schedule of 738 finite samples;
- final relative RMS against Prosperetti is finite and parseable;
- the amplitude history has finite time and amplitude columns;
- the output resolution label matches the manifest;
- native/NN provider statistics are present when applicable;
- the summarizer independently reproduces the RMS from `wave-N` and
  `prosperetti.h` within the parser's documented numerical tolerance.

### F2. Rising bubble Case 1

A rising row is `completed` only if:

- solver reaches stock final time `t=3`;
- `out` has the stock header and a finite final-time row;
- final interface-facet output is non-empty;
- center position, rise velocity, and relative volume columns remain finite;
- resolution/LEVEL/grid identity matches the manifest;
- native/NN provider statistics are present when applicable;
- the summarizer extracts finite peak/final velocity, final position, maximum
  volume drift, and shape-distance metrics.

## G. Redistance/SDF evidence gates

Every completed row must provide read-only physical-path diagnostics for:

- actual returned redistance iteration count distribution;
- pre/post `E_grad = abs(|grad d| - 1)` in `1.5*Delta` and `3*Delta` bands;
- `E_grad` mean, RMS, maximum, and 95th percentile over physical time;
- `grad_min` and `grad_max`;
- sign-mismatch count across the actual redistance update;
- phi-reconstructed versus VOF volume difference;
- mean/max change in `d` across redistance;
- fixed diagnostic logging stride plus initial/final records.

The diagnostics must observe the actual evolving physical `d`; they may not
replace it with a diagnostic branch. An `imax=3` equivalence test must prove
that enabling read-only logging does not alter benchmark physical outputs.

For `imax=0`, the returned-step count must be zero. For `imax>0`, every
returned count must satisfy `1 <= returned <= imax`; early convergence is
recorded rather than forced away.

## H. NN-specific evidence gates

Every NN row must record:

- exact `baseline_<N>_hgradient` checkpoint and weight-header hash;
- benchmark-specific raw27 order and normal-sign convention;
- feature scaling and output `h*kappa` scaling;
- provider evaluation count;
- clamp-hit count;
- nonzero golden-vector feature/forward parity gate version.

A completed NN row with nonzero clamp hits remains raw evidence but is marked
`flagged_clamp` in the report and cannot support an unqualified in-distribution
NN claim.

## I. Failure evidence contract

Numerical instability is a possible experimental result, especially for
`imax=0`. A failed row must preserve:

- last finite physical time and solver iteration;
- failure classification;
- error/exit status;
- last available physical and SDF diagnostics;
- partial raw outputs;
- command, hashes, and runtime;
- whether the native paired row at the same `(benchmark,N,imax)` failed.

No parameter may be silently relaxed to convert a failed row into a completed
row. A deliberately changed retry is a new experiment identity, outside this
96-row matrix unless explicitly approved.

## J. Matrix-level analysis gates

The final matrix report must include:

1. a 96-row status table, including failures;
2. `metrics_long.csv` and `metrics_wide.csv` generated from raw data;
3. paired NN-minus-native deltas at every comparable `(benchmark,N,imax)`;
4. capwave physical-error, SDF-error, convergence, and runtime matrices;
5. rising velocity/position/volume/shape, SDF-error, and runtime matrices;
6. `imax x N` heatmaps for both methods and both benchmarks;
7. time-history plots for capwave amplitude and rising velocity/volume;
8. rising final-shape overlays against MooNMD;
9. SDF-quality versus physical-error analysis;
10. runtime scaling and failure ledger;
11. explicit separation of:
    - lower `E_grad`;
    - better physical benchmark accuracy;
    - smaller NN-native difference;
    - higher computational cost.

The report may not infer that more redistance is better solely from SDF
quality. The official `imax=3` reference must be shown explicitly in every
relevant plot/table.

## K. Matrix closure test

The formal execution goal is complete only when all are true:

- user approved the scope before implementation/running;
- all 96 row IDs exist in the final matrix manifest;
- all 96 rows have terminal states;
- every `completed` row passes its benchmark and evidence gates;
- every failed/blocked row passes the failure evidence contract;
- no unapproved source/config drift occurred;
- no matrix run modified `basilisk/src`;
- all required aggregate tables and figures exist;
- summary conclusions are reproducible from raw outputs;
- final completion audit maps every clause in this contract to a concrete
  file, row, command output, or test result.

Until these conditions are proven, the Codex Goal remains active.

## L. User approval fields

Confirmed by the user on 2026-07-11:

- [x] Rising scope is Hysing Case 1 only.
- [x] Rising N/LEVEL/grid mapping is accepted.
- [x] NN checkpoint is matched by source-resolution label N.
- [x] Formal scope is 96 cells.
- [x] Existing `imax=3` rows are reused only after Section D passes.
- [x] Failed/nonfinite rows remain formal outcomes and are not hidden.
- [x] Estimated long-run cost and resumable execution policy are accepted.
- [x] At most five single-core cases may run concurrently under the later user
  override, with adaptive reduction to protect interactive use.

## M. Resource scheduler acceptance contract

The scheduler is accepted only if:

- `MAX_JOBS` defaults to 4 and may reach 5 only under the recorded 2026-07-11
  user override; values above 5 are rejected;
- each solver uses `taskpolicy -b` and positive `nice` when supported; the
  managed macOS environment rejected both mechanisms, so plain-priority
  execution plus the concurrency ceiling is the recorded fallback;
- no new row launches on battery power;
- memory pressure and current active-row count are checked before each launch;
- the scheduler can be resumed without duplicating `running` or `completed`
  row identities;
- launch target can be changed to 1/2/3/4/5 without rewriting matrix identity;
- N64 extreme rows complete before the general longest-processing-time queue
  is unlocked;
- progress is persisted outside the process so a Codex/app restart does not
  lose row state;
- reducing concurrency never kills a healthy progressing row; it only delays
  future launches;
- a user-requested pause stops new launches and preserves active-row evidence.
