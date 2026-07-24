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

`requirements.txt` installs the Python-only dependency (`pytest`). GCC,
OpenMP, gnuplot, system monitoring tools and the Linux `qcc` binary cannot be
installed by pip, so `setup_linux.sh` installs and checks them. The setup copies
the bundled Basilisk source into ignored `build/linux-toolchain/`, switches that
copy to Basilisk's `config.gcc`, and builds a Linux-native `qcc`. It also creates
the ignored `build/linux-venv/`. `job.sh` finds both automatically; no export is
required.

The execution contract is native Linux with at least one visible CPU.
`cpu_slots=auto` uses every CPU available to the process after Linux affinity and
cgroup-quota limits; per-row thread ceilings are clamped to that total. `--check` runs both a two-thread GCC/OpenMP probe and
a minimal `qcc` compile/run probe. Slow Windows-mounted filesystems are rejected.

Campaign commands:

```bash
bash generate/job.sh layout
bash generate/job.sh check
bash generate/job.sh plan --scope smoke
bash generate/job.sh plan --scope formal
bash generate/job.sh smoke
bash generate/job.sh verify --scope smoke
bash generate/job.sh formal
bash generate/job.sh verify --scope formal
```

`layout`, `check` and `plan` do not run a solver. `smoke` is the optional 56-row
review campaign described below. `formal` starts the complete matrix when the
user explicitly invokes it. Formal startup refuses a dirty worktree; resume requires the same
Git commit, source lock and resource policy. Nothing commits automatically.
Historical `dataset/` outputs do not need to be committed. The formal campaign
should run from a fresh, clean Linux checkout after the reviewed implementation
commit; this preserves the strict clean-worktree gate without forcing unrelated
Mac-side research artifacts into Git.

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

The campaign is deliberately not a serial loop. It has two stages:

1. Compile every pending row first, with as many independent compiler
   processes as there are available CPU slots.
2. Run multiple solved rows concurrently under one slot-bounded scheduler.

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
clamped to the available slots. The scheduler launches any queued row that fits the remaining slots. VOF-HF
rows are introduced early as one-slot backfill instead of leaving a serial
tail. It records the actual allocation and host CPU/memory/swap samples in
`_meta/resource_usage.csv`; `_meta/resource_summary.json` reports mean measured
CPU use while all available solve slots were allocated. Slot saturation is the hard
contract. Measured utilization can briefly dip during solver serial sections
and I/O, so the smoke report—not an unsupported promise—is used to review
whether the candidate policy keeps the target host sufficiently busy.

VOF-HF remains single-threaded. CLSVOF and NN use OpenMP with
`OMP_DYNAMIC=false`; both methods receive the same threads at the same N.

For traceability and throughput, the compile stage and solve stage are
separate. This is not arbitrary precompilation: direct runner calls still
reject `--precompiled`. The internal scheduler hashes the executable, compiler
command, sources, OpenMP environment and scientific parameters, verifies they
are unchanged at solve time, embeds a `build_binding` in `manifest.json`, then
deletes the temporary `_meta/builds/<row>` directory. A changed binary or plan
blocks the row.

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
    │   ├── resource_usage.csv
    │   ├── resource_summary.json
    │   ├── object_index.json
    │   ├── oscillating_vof_hf_official.json
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
leave a partial row directory. Before resuming:

1. confirm that no campaign solver process remains;
2. move the one incomplete row directory aside for diagnosis, or delete that
   exact row after review;
3. rerun the same `job.sh smoke` or `job.sh formal` command.

Completed rows and verified temporary builds are reused. The campaign refuses
to guess through an incomplete row or mix changed sources/settings.

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
