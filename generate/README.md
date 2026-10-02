# Canonical data generation

Status: implementation candidate for user/Claude review. No new 56-row smoke or
397-row formal campaign has been started, and no Git commit is performed by
these scripts.

`generate/job.sh` is the only campaign entrypoint. It creates a new dataset
under `data/` and never overwrites the historical `dataset/` tree.

## Linux installation and commands

Run this once on the Ubuntu/Linux execution host:

```bash
bash generate/setup_linux.sh --install
bash generate/setup_linux.sh --check
```

Campaign orchestration uses Python 3.10+ and its standard library. `job.sh`
uses `python3`, or the interpreter set by `CFD_PYTHON`. Model export and plotting
use their existing PyTorch and scientific Python environments.

`setup_linux.sh` installs and checks GCC, OpenMP, gnuplot, system monitoring
tools and a Linux-native `qcc`. It copies the bundled Basilisk source into
ignored `build/linux-toolchain/`, selects `config.gcc`, and builds `qcc`.
`job.sh` finds that compiler automatically.

The execution contract is native Linux with at least one visible CPU.
`cpu_slots=auto` uses every CPU available to the process after Linux affinity and
cgroup-quota limits; per-row thread ceilings are clamped to that total. `--check` runs both a two-thread GCC/OpenMP probe and
a minimal `qcc` compile/run probe. Slow Windows-mounted filesystems are rejected.

Campaign commands:

```bash
bash generate/job.sh check
bash generate/job.sh plan --scope smoke
bash generate/job.sh plan --scope formal
bash generate/job.sh smoke
bash generate/job.sh verify --scope smoke
bash generate/job.sh formal
bash generate/job.sh verify --scope formal
```

`check` and `plan` do not run a solver. `smoke` is the optional 56-row
review campaign described below. `formal` starts the complete matrix when the
user explicitly invokes it. Formal startup refuses a dirty worktree; resume requires the same
Git commit, source lock and resource policy. Nothing commits automatically.
Historical `dataset/` outputs do not need to be committed. The formal campaign
should run from a fresh, clean Linux checkout after the reviewed implementation
commit; this preserves the strict clean-worktree gate without forcing unrelated
Mac-side research artifacts into Git.

## NN inference precision

All existing NN case runners accept
`--inference-precision float32|float64-forward`. The compatibility spelling
`float64-accum` is normalized to the public manifest value `float64-forward`.
Set `CFD_NN_INFERENCE_PRECISION` to apply the same setting to every NN row
launched by `job.sh`; the default remains `float32`.

Inference precision is a recorded numerical parameter, not a new case, method,
data root or plotting workflow. Formal outputs retain the existing case-first
paths under `data/`, and figures retain their existing case-local plot scripts.
The manifest and compile command record the chosen precision.

## Fixed task matrix

Method names and directories are exactly `VOF-HF`, `CLSVOF` and `NN`.
`VOF-HF` has no `imax` or NN model. It is the independent official numerical
reference for every case. Oscillating additionally has a uniform VOF-HF
matched-reference row at each N; both adaptive and uniform paths use only the
Standard centered solver variant.

Capillary Wave, Rising Bubble cases 1/2 and Oscillating Droplet use
`imax={0,1,2,3,4,5,10,15,20}`; `imax=3` is the main/default result and the
other eight values are formal sensitivity rows. Stationary Bubble runs only
`imax=0`, which is its default result. Every NN row is locked to
`baseline_<N>_hgradient`.

| physical branch | grid contract | N | VOF-HF | CLSVOF | NN | total |
|---|---|---|---:|---:|---:|---:|
| Capillary Wave | all uniform | 32, 64, 128, 256, 512 | 5 | 45 | 45 | 95 |
| Rising Bubble case 1 | all uniform | 32, 64, 128, 256, 512 | 5 | 45 | 45 | 95 |
| Rising Bubble case 2 | all uniform | 32, 64, 128, 256, 512 | 5 | 45 | 45 | 95 |
| Stationary Bubble | VOF-HF adaptive; CLSVOF/NN uniform | 32, 64, 128, 256 | 4 | 4 | 4 | 12 |
| Oscillating Droplet | 5 adaptive official VOF-HF + uniform three-method comparison | 32, 64, 128, 256, 512 | 10 | 45 | 45 | 100 |
| **total** | — | — | **29** | **184** | **184** | **397** |

Formal roles are fixed at 24 `official_reference`, 5 `matched_reference`, 48
`default` and 320 `sensitivity` rows.

The 56-row smoke contains the N32/N64 default rows plus an N32 canary for every
new `imax=10,15,20` CLSVOF/NN branch. Oscillating has both adaptive official
VOF-HF and uniform matched VOF-HF at N32/N64. Its method counts are 12 VOF-HF,
22 CLSVOF and 22 NN rows. Smoke runs the full physical horizon; it is a matrix
reduction, not a shortened scientific trajectory.

## Numerical horizons

| case | fixed horizon and observations | grid interpretation |
|---|---|---|
| Capillary Wave | official 738 samples through solver `t=2.2426211256` | uniform `N x N`; N256/N512 are stock-compatible extensions |
| Rising Bubble cases 1/2 | `t=0..3`; history, circularity and final interface | uniform `N x N/4`; stock default is N256 |
| Stationary Bubble | fixed `tau=0..2`, exact milestones at `tau=1` and `tau=2`; no convergence early stop | VOF-HF adaptive TREE; CLSVOF/NN uniform; N512 excluded |
| Oscillating Droplet | official `t<=1` horizon and fit channels | adaptive TREE for official VOF-HF; uniform N-matched VOF-HF/CLSVOF/NN; Standard centered solver only |

The case sources retain their reviewed physical constants. Generated
CLSVOF/NN pairs use the same case host, N, `imax`, horizon, compiler flags and
thread allocation; NN changes only the active curvature provider and model.

## Parallel execution on Linux

The campaign is deliberately not a serial loop and does not precompile the
entire matrix. Compilation and solving share one bounded pipeline: up to 8
independent compilers are allowed before solving begins, at most 8 remain active
while solvers run, and no more than 16 verified builds may wait ahead. A row is
eligible to solve immediately after its executable verifies. Compiler processes
also consume scheduler slots, so the combined compile-plus-solve allocation
never exceeds the 32 CPUs visible to the container. These caps avoid cgroup
memory reclaim on 60 GiB execution containers while removing the old
all-builds-before-any-result delay.

The solve policy in `resource_policy.linux-auto.json` uses all CPUs visible to
the process. On the current 32-CPU host it resolves to:

| row | threads/slots | maximum simultaneous rows when homogeneous |
|---|---:|---:|
| VOF-HF at any N | 1 | used as backfill |
| CLSVOF/NN N32 | 2 | 16 |
| CLSVOF/NN N64 | 4 | 8 |
| CLSVOF/NN N128 | 8 | 4 |
| CLSVOF/NN N256 | 8 | 4 |
| CLSVOF/NN N512 | 16 | 2 |

This is a throughput-first policy for a 32-CPU allocation: it keeps multiple
rows active at every N instead of assigning all cores to one two-dimensional
N512 row. On smaller Linux allocations each per-row value is automatically
clamped to the available slots. The solve scheduler launches any queued row that fits the remaining slots. VOF-HF
rows are introduced early as one-slot backfill instead of leaving a serial
tail. A failed row is recorded with its phase, attempt, exception and log path;
other rows continue. Failed rows receive one deferred retry after the initial
wave, and a repeatedly failing row blocks `READY.json` without idling or
discarding successful rows. The terminal log shows running rows and allocated
CPU slots. Per-row failures and progress are recorded in `_meta/run.json`.

VOF-HF remains single-threaded. CLSVOF and NN use OpenMP with
`OMP_DYNAMIC=false`; both methods receive the same threads at the same N.

For traceability, each row still has separate, hash-bound build and solve
steps even though different rows overlap in the pipeline. Direct runner calls
reject `--precompiled`. The internal scheduler hashes the executable, compiler
command, sources, OpenMP environment and scientific parameters, verifies they
are unchanged at solve time, embeds a `build_binding` in `manifest.json`, then
deletes the temporary `_meta/builds/<row>` directory. A changed binary or plan
blocks that row.

## Final data layout

```text
data/
├── _smoke/
│   └── vof_clsvof_nn_benchmarks_v2/
└── vof_clsvof_nn_benchmarks_v2/
    ├── READY.json
    ├── _meta/
    │   ├── run.json
    │   ├── tasks.csv
    │   ├── schema.json
    │   ├── source_lock.json
    │   ├── resource_policy.json
    │   ├── logs/{build,solve}/
    │   ├── sources/sha256/<hash>
    │   ├── references/
    │   │   ├── prosperetti.h
    │   │   └── hysing/{case1_history,case1_interface,
    │   │               case2_history,case2_interface}.txt
    │   └── models/baseline_<N>_hgradient/
    │       ├── export_manifest.json
    │       └── nn_weights.h
    ├── capwave/
    │   ├── summary.csv
    │   └── Nxxxx/{VOF-HF,imaxNN/{CLSVOF,NN}}/
    ├── rising_bubble/caseK/
    │   ├── summary.csv
    │   └── Nxxxx/{VOF-HF,imaxNN/{CLSVOF,NN}}/
    ├── stationary_bubble/
    │   ├── summary.csv
    │   └── Nxxxx/{VOF-HF,imax00/{CLSVOF,NN}}/
    └── oscillating_droplet/
        ├── summary.csv
        ├── adaptive/Nxxxx/VOF-HF/
        └── uniform/Nxxxx/{VOF-HF,imaxNN/{CLSVOF,NN}}/
```

`sources/sha256/` is only a content-addressed deduplication store. SHA-256 is a
file fingerprint for reproducibility; it does not create a new model. Model C
exports and analytic/reference tables are stored once under `_meta/`.
Each row manifest records its source references and, for oscillating VOF-HF,
the official comparison result.

## Exact files in each completed row

The solver first creates its official/raw intermediate outputs. Scientific
checks recompute metrics and validate coverage. Only then are the validated
values embedded in `manifest.json` and the intermediates compacted. After
campaign-level source deduplication, a row contains exactly:

| case | final row files |
|---|---|
| Capillary Wave | `manifest.json`, `timeseries.csv`, `fields.csv.gz`, `run.log` |
| Rising Bubble | `manifest.json`, `timeseries.csv`, `interface_t3.csv.gz`, `fields.csv.gz`, `run.log` |
| Stationary Bubble | `manifest.json`, `timeseries.csv`, `milestones.csv`, `fields.csv.gz`, `run.log` |
| Oscillating Droplet | `manifest.json`, `timeseries.csv`, `fit.csv`, `fields.csv.gz`, `run.log` |

`manifest.json` contains row identity, resolved commands, exact source hashes,
build binding, artifact hashes, scalar metrics and NN provider counters. This
replaces separate per-row `metrics.csv`, `scientific_artifacts.json` and
`provider_stats.csv` files without discarding their information.

Main table columns are locked in `_meta/schema.json`:

- Capillary `timeseries.csv`: `tau, amplitude, reference_amplitude,
  amplitude_error`.
- Rising `timeseries.csv`: `time, iteration, relative_volume_change,
  center_of_mass_x, rise_velocity_x, dt, circularity, half_area,
  half_perimeter`; `interface_t3.csv.gz` stores segment endpoints.
- Stationary `timeseries.csv`: `tau, u_star, delta_fraction,
  capillary_number`; `milestones.csv` contains both `tau_1` and `tau_2`, shape
  errors, official-style curvature error and active-provider curvature error.
- Oscillating `timeseries.csv`: `time, kinetic_energy, pressure_iterations`;
  `fit.csv` stores fit parameters/uncertainties, frequency errors, equivalent
  Laplace number and `damped` versus `nonphysical_growth`.

## Field snapshots and heatmaps

Every row has one deterministic gzip CSV containing two complete cell fields:

- `middle`: the first native solver state at or after the case target. It does
  not schedule a new time and does not shorten a timestep.
- `final`: the terminal solver state.

Targets are Capillary solver `t=1.1213105628`, Rising `t=1.5`, Stationary exact
`tau=1`, and Oscillating `t=0.5`. Final targets are each official horizon.

`fields.csv.gz` records snapshot/target/actual times, iteration, `x`, `y`,
`Delta`, level, both velocity components, pressure, vorticity, target-phase
fraction, common phase-fraction curvature, exact active-provider curvature and
validity flags. Invalid curvature values are empty rather than fake zeroes.
Velocity magnitude and Capillary-number heatmaps can therefore be rebuilt
without saving redundant columns.

The 56-row smoke is the storage gate: its actual compressed bytes and cell
records are summarized before formal approval. No field is silently dropped or
downsampled by the formal runner.

`data/` is intentionally ignored by Git because the field datasets are large.
Before the formal campaign, choose a second storage location and copy the
completed dataset plus `READY.json` there. The manifests and SHA-256 records
detect corruption; the second copy provides persistence.

## Interruption and resume

Compiler and solver rows run in separate process groups. `SIGINT`, `SIGTERM` or
terminal hangup stops every active group before the campaign exits, preventing
orphaned qcc/solver processes. An ungraceful machine or kernel failure can still
leave a partial row directory. On resume, the scheduler first re-verifies every
recorded completed row, recovers a valid unrecorded row, and removes only an
exact invalid partial-row directory before rescheduling it. Before resuming:

1. confirm that no campaign solver process remains;
2. preserve `_meta/logs/` because it contains per-attempt diagnostics;
3. rerun the same `job.sh smoke` or `job.sh formal` command.

Completed rows and verified temporary builds are reused. The campaign refuses
to mix changed sources/settings. Row finalization is idempotent and retried
three times. Completed rows retain their source references in `manifest.json`.

## Completion and review gates

A row must reach its fixed horizon, pass its benchmark-specific raw-output and
derived-metric checks, include both field snapshots, match every artifact hash,
and have a valid build binding. NN must report positive active-provider calls;
CLSVOF and VOF-HF must not contain NN provider counters. CLSVOF/NN pairs must
share the same redistance overlay hash.

`READY.json` appears only after every row verifies. `analysis_ready=true` means
the data are complete and drawable; it does not declare that every physical
result is scientifically accepted. User/Claude review remains a separate gate.

The intended release sequence is:

```text
clean Git checkout -> Linux setup/check -> job.sh check
-> explicit formal start -> 397-row verification -> user/Claude review
-> external data backup
```


## Normal-stencil ablation (CLSVOF C2, FP64 forward)

The NN runners accept `--feature-mode phi9_full_normal|phi9_center_normal|phi9_cross_normal`.
These select 27D, 11D, and 19D inputs respectively; phi9 is retained in every mode.
The 19D normals use stencil positions [1,3,4,5,7], and 11D uses position [4].
The export manifest is checked against the selected dimension and feature order.
Export checkpoint data with `generate/_shared/nn_runtime/export_model.py`.
Weights and standardization constants retain float32 storage; `--inference-precision float64-forward`
uses double inputs, standardization arithmetic, activations, accumulation and output.

Example (N32/N64 refer to the matching training and CFD grid in this existing matrix):

```bash
python generate/_shared/nn_runtime/export_model.py --checkpoint /path/to/cell_32_hcross_normal.pt --name cell_32_hcross_normal --output data/model/c_exports/cell_32_hcross_normal
bash generate/capwave/NN.sh --formal --resolution 32 --feature-mode phi9_cross_normal --curvature-mode interface --steps 3 --inference-precision float64-forward --threads 1 --output data/normal_ablation/capwave/N0032/19D
```

Rising bubble uses the same options with `--case 1` or `--case 2`.
Stationary bubble uses `--steps 0` and the existing fixed horizon tau=2.
The fixed-step redistance header is a generate-owned copy of the prior formal source snapshot,
compiled as a local overlay. The Basilisk source tree is not edited.
At most six independent single-threaded runners were used for this comparison.
Do not edit a runner file while its shell process is active.

`figures/plot_all.py` generates only the paper selection.
Failed initial rising compilation attempts remain in `.failed_compile_1` directories and are
excluded from the comparison. All 16 canonical ablation rows completed successfully.
Two N64 stationary completion states were recovered through the existing manifest command
using the hash-identical launch script and original plan; their elapsed seconds come from
the external runner observation. New and historical elapsed times are not a controlled speed benchmark.


## C1 direct normal-stencil ablation (FP64 forward)

`--curvature-mode direct` reuses the archived NN-interface-C1 implementation:
CURVATURE=1 calls the current-cell NN provider; TRANSFORM_MODE=2 returns q_gamma
without the distance-contour conversion. There is no C2 endpoint interpolation.
The existing sign convention and curvature clamp are retained. `cell` still means
C1 with distance-contour conversion; `interface` still means C2 interpolation.

The formal C1 matrix uses all three cell models (11D/19D/27D), N32/N64, capwave,
stationary bubble, and rising bubble cases 1 and 2: 24 new runs. Physical settings,
fixed redistance steps (stationary 0, others 3), horizons, and FP64 precision match
the preceding C2 normal ablation. Each run uses one thread, with at most six concurrent runs.
Results are under `data/normal_ablation_c1_fp64/<case>/[case1|case2/]N####/<dim>D/`.

```bash
bash generate/capwave/NN.sh --formal --resolution 32 --model cell_32_hgradient --feature-mode phi9_full_normal --curvature-mode direct --steps 3 --inference-precision float64-forward --threads 1 --output data/normal_ablation_c1_fp64/capwave/N0032/27D
```

All six NN runs are C1 direct; the VOF-HF and native
CLSVOF-C2 comparator data are reused from the preceding comparison. The stationary
summary metric is Ca_final at tau=2; Ca_max is retained only as a separate transient
metric. No C2 result is reused as an NN C1 result.


## Strict 3x3 local-normal input (15D)

All three NN runners accept `--feature-mode phi9_local_normal`, selecting
`cell_{N}_hlocal_normal`. The input is `[phi9/h, nx_C, ny_C, ny_L, ny_R, nx_T, nx_B]`.
Normals are derived solely from phi9: centered tangential differences and
first-order inward differences at the four edge points, followed by unit
normalization (zero gradient gives zero). This is not a subset of the old
full-field centered normals. The curvature modes and precision switches are
unchanged. Export the matching PINN checkpoint with `export_model.py` before
running; the export manifest must declare this exact 15D order.

## Stationary bubble: full-circle extension

The stationary runners accept `--domain quarter|whole` (default: `quarter`).
The whole-domain CLSVOF/NN entry is `stationary-bubble-whole.c`, which includes
and reuses the original case. The VOF-HF builder applies the same domain change
to its generated host. No files in `basilisk/` are modified.

The full circle has radius 0.4 in `[-1,1]^2`, with the existing symmetry outer
boundaries and tau=2 horizon. `--resolution R` retains the original contract:
h=1/R and the model is numbered R in both domains. The actual cells per side
are R in the quadrant and 2R in the whole domain (maximum resolution for
adaptive VOF-HF). Manifests record `resolution`, `cells_per_side` and
`grid_spacing` separately. Formal runs enforce the same-numbered model.
The existing campaign matrix remains the quadrant matrix; run this extension
with the case runners and a separate output directory.

```bash
bash generate/stationary_bubble/NN.sh --domain whole --resolution 32 \
  --model cell_32_hgradient --steps 0 --curvature-mode interface \
  --inference-precision float64-forward --formal --threads 1 \
  --output data/stationary_bubble/whole_domain/N0032/NN
```

Use `CLSVOF.sh --imax 0` and `VOF-HF.sh` with the same domain and resolution
for the native pair and VOF-HF reference. FP64 forward uses FP32 stored weights
with FP64 inference arithmetic. Manifests record domain, matched resolution,
`compile_seconds`, `solver_seconds` and total `elapsed_seconds` (wall time,
whole seconds). CLSVOF and NN both retain `whole_domain_timeseries.csv`, so all
three methods can be compared using the maximum speed over the computational
domain instead of mixing interface-band and domain-wide diagnostics.
