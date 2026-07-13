# Ubuntu HPC 180-row OpenMP Matrix Implementation Plan

Date: 2026-07-13  
Workspace: `/Users/jcy/research/cfd`  
Plan status: **implemented locally; awaiting Ubuntu 22.04 host gates**  
Target: Ubuntu 22.04 LTS, x86_64, one 128-CPU cloud host, no Slurm/MPI/GPU

## 1. Goal

Build a clean, reproducible deployment layer that can be transferred as a
verified tarball without Git, bootstrapped once on Ubuntu, and then run with
one command:

```bash
bash hpc/submit_matrix.sh --cpus 128 --matrix-id formal_180_001
```

That command must preflight the host, select a measured OpenMP/thread policy,
run the accepted 180-row formal matrix, validate every row, resume without
silently accepting corruption, and emit one final package:

```text
hpc/packages/cfd_hpc_180_<matrix_id>.tar.gz
```

The existing `cases/`, `dataset/`, `figures/`, `report/`, `tem/`, and legacy
`experiments/` layout is not moved. The new `hpc/` directory is an orchestration
and packaging layer only.

Implementation note: the phase descriptions below preserve the original
design rationale. The accepted operational behavior follows the later user
decision to run exactly one formal row at a time (`--max-active-rows 1`), with
OpenMP inside that row. The authoritative server procedure is
`docs/server/ubuntu22-hpc-operator-handoff.md`.

## 2. Frozen scientific matrix

### 2.1 Formal methods

Exactly two methods are formal:

```text
clsvof_native
clsvof_nn_cell_offset
```

Diagnostic analytic, legacy direct-NN, `rising_k_provider`, contour-oracle, and
other smoke modes are not formal methods and cannot be relabelled into this
matrix.

### 2.2 Formal benchmark branches

| Benchmark identity | Resolutions | Methods | imax | Rows |
| --- | --- | --- | --- | ---: |
| `capwave` | 64, 128, 256, 512 | 2 | 0-5 | 48 |
| `rising_case1` | 64, 128, 256, 512 | 2 | 0-5 | 48 |
| `rising_case2` | 64, 128, 256, 512 | 2 | 0-5 | 48 |
| `stationary_bubble` | 64, 128, 256 | 2 | 0-5 | 36 |
| **Total** |  |  |  | **180** |

Structural invariants:

- exactly 180 unique row IDs;
- exactly 30 rows for each `imax` in `0,1,2,3,4,5`;
- exactly 90 native and 90 NN rows;
- no stationary N512 row may be generated, dry-run, scheduled, resumed, or
  packaged;
- rising Case 1 and Case 2 are distinct benchmark identities;
- all NN rows use `baseline_<N>_hgradient` matching the row resolution;
- all NN benchmark branches use the same canonical cell-offset implementation.

### 2.3 Canonical row identity

```text
<benchmark>__<method>__N####__imax##
```

Examples:

```text
rising_case1__clsvof_nn_cell_offset__N0256__imax03
rising_case2__clsvof_nn_cell_offset__N0256__imax03
stationary_bubble__clsvof_native__N0128__imax05
```

The row ID is immutable and is used by the matrix, result path, staging path,
resume logic, logs, and package manifest.

## 3. Current-state findings that the implementation must address

1. `cases/rising_bubble/generate/nn_cell_offset.sh` is hard-coded to Hysing
   Case 1 and does not pass `-DCASE2=1`.
2. Capwave, rising Case 1, and stationary already copy the same canonical
   `cases/_shared/nn_cell_curvature/src/clsvof_nn_cell_curvature.h`.
3. The canonical header currently contains shared global statistics writes;
   these are unsafe in a formal OpenMP build.
4. `cases/_shared/nondefault_redistance/run_matrix.py` currently expands a
   132-row NN-only, imax 0-10, one-thread-per-row matrix and forces
   `OMP_NUM_THREADS=1`.
5. The older `experiments/clsvof_redistance_imax_matrix/` runner is macOS-
   specific in several places, contains absolute Python paths, and uses the
   older experiment provider surface. It is evidence and test reference, not
   the Ubuntu implementation base.
6. Existing case generators use `shasum`; formal integrity must instead use a
   shared Python `hashlib` implementation.
7. The current worktree is dirty and contains untracked results/build files.
   Deployment must be created from an explicit allowlist, not by pushing this
   worktree wholesale.

## 4. Target deployment tree

Add the following without moving existing research directories:

```text
hpc/
  README.md
  bootstrap_ubuntu.sh
  submit_matrix.sh
  preflight_hpc.py
  run_matrix.py
  run_row.py
  verify_matrix.py
  collect_results.sh
  lib/
    integrity.py
    matrix.py
    platform.py
    scheduler.py
  config/
    matrix_180.json
    thread_policy.json
    provenance.lock.json
  tests/
    test_matrix_contract.py
    test_rising_cases.py
    test_stationary_boundary.py
    test_openmp_stats.py
    test_integrity_resume.py
    test_scheduler.py
    test_package.py
  work/                  # ignored; failed work retained
  results/               # ignored; immutable formal rows
  packages/              # ignored; final tar.gz and SHA256
```

Case-local additions/changes:

```text
cases/capwave/generate/native.sh                     # new
cases/capwave/generate/nn_cell_offset.sh             # OpenMP/hash interface
cases/rising_bubble/generate/native.sh               # new, --case 1|2
cases/rising_bubble/generate/nn_cell_offset.sh       # add --case 1|2
cases/stationary_bubble/generate/native.sh            # new
cases/stationary_bubble/generate/nn_cell_offset.sh    # N512 rejection/OpenMP/hash
cases/_shared/nn_cell_curvature/src/
  clsvof_nn_cell_curvature.h                          # thread-safe statistics
cases/_shared/nn_cell_curvature/tests/
  openmp_stats_smoke.c                                # new parity harness
```

CI addition:

```text
.github/workflows/ubuntu-hpc.yml
```

## 5. Phase 0 - Freeze source and deployment boundary

### Work

1. Record current source identities for:
   - official Basilisk case/header files;
   - the canonical cell-offset header;
   - the overlay generators;
   - the four `nn_weights.h` files;
   - the C inference header;
   - the accepted stationary host.
2. Create `hpc/config/provenance.lock.json` using Python `hashlib`.
3. Define a deployment allowlist rather than cleaning or repurposing the dirty
   research worktree.
4. Add ignore rules for `hpc/work`, `hpc/results`, `hpc/packages`, `.qcc`,
   binaries, objects, archives, caches, and macOS metadata.

### Gate P0

- The allowlist contains only Basilisk source required at build time, `cases/`,
  model exports, inference headers, `hpc/`, tests, and documentation.
- No Mach-O binary, current `qcc`, `.o`, `.a`, `.qcc`, result, smoke output,
  timestamped work directory, or absolute symlink is included.
- All provenance paths are repository-relative.

## 6. Phase 1 - Make the 180-row matrix executable and unambiguous

### Files

- `hpc/lib/matrix.py`
- `hpc/config/matrix_180.json`
- `hpc/tests/test_matrix_contract.py`
- `hpc/tests/test_stationary_boundary.py`

### Work

1. Represent each row with:

   ```text
   row_id, benchmark, rising_case, method, resolution, level,
   actual_grid, imax, model_name, expected_output
   ```

2. Generate the JSON deterministically from frozen axes; do not hand-maintain
   180 copied objects.
3. Use these resolution mappings:

   - capwave: N64/128/256/512 square source labels;
   - rising: LEVEL 6/7/8/9 with actual grids 64x16, 128x32, 256x64,
     512x128;
   - stationary: LEVEL 6/7/8 only.
4. Restrict `imax` to integer 0-5 at the matrix library, CLI, generator, and
   row-runner boundaries.
5. Make stationary N512 a hard error, not merely an omitted default.

### Tests

- 180 rows and 180 unique row IDs;
- 48/48/48/36 rows by benchmark;
- 90/90 rows by method;
- 30 rows per imax;
- imax 0 and 5 accepted; -1 and 6 rejected;
- rising cases have distinct row IDs and output paths;
- stationary 512 construction raises an explicit error;
- two dry-runs cannot resolve to the same final path.

### Gate P1

`pytest hpc/tests/test_matrix_contract.py hpc/tests/test_stationary_boundary.py -q`
passes, and `python3 hpc/run_matrix.py --dry-run` reports exactly 180 rows.

## 7. Phase 2 - Integrate rising Case 2 into the canonical cell-offset path

### Files

- `cases/rising_bubble/generate/nn_cell_offset.sh`
- `cases/rising_bubble/generate/native.sh`
- `cases/rising_bubble/summary.yaml`
- `hpc/tests/test_rising_cases.py`

### Work

1. Add required `--case 1|2`.
2. Compile flags:

   ```text
   Case 1: -DLEVELSET=1 -DCLSVOF=1 -DLEVEL=<level>
   Case 2: -DLEVELSET=1 -DCLSVOF=1 -DCASE2=1 -DLEVEL=<level>
   ```

3. Both cases must copy the same canonical
   `clsvof_nn_cell_curvature.h`, invoke the same
   `make_overlay_integral.py`, and select weights only by resolution.
4. Manifest identity must contain:

   ```json
   {
     "case": "rising_bubble",
     "benchmark_case": "hysing_case_1 or hysing_case_2",
     "benchmark": "rising_case1 or rising_case2"
   }
   ```

5. Never copy outputs from the legacy `rising_k_provider` results into the new
   formal path.
6. Add a native generator using the same stock source, redistance overlay,
   resolution mapping, final-time validation, and manifest schema.

### Tests

- dry-run commands differ only by `-DCASE2=1` and identity/path fields;
- Case 1 command does not accidentally define `CASE2`;
- Case 2 command defines it exactly once;
- Case 1/2 NN manifests contain identical canonical-header SHA-256 at the same
  resolution;
- Case 1/2 use identical weight SHA-256 for the same N;
- both N64 native and NN smokes reach `t=3`;
- output validator accepts finite Hysing columns and rejects truncated output.

### Gate P2

Four Ubuntu smokes pass:

```text
rising Case 1 native N64 imax3
rising Case 1 NN     N64 imax3
rising Case 2 native N64 imax3
rising Case 2 NN     N64 imax3
```

## 8. Phase 3 - Add native case generators and one manifest schema

### Files

- `cases/capwave/generate/native.sh`
- `cases/rising_bubble/generate/native.sh`
- `cases/stationary_bubble/generate/native.sh`
- existing NN generators
- `hpc/lib/integrity.py`
- `hpc/run_row.py`

### Work

1. Native and NN paired rows must share the same copied official case and the
   same generated redistance header.
2. Only the curvature-provider route differs.
3. Replace generator-local `shasum` calls with shared Python `hashlib` manifest
   generation.
4. Standardize per-row output under:

   ```text
   hpc/results/<matrix_id>/<benchmark>/N####/imax##/<method>/
   ```

5. Each row manifest records:
   - row and matrix identity;
   - benchmark/method/N/LEVEL/grid/imax/model;
   - source, Basilisk header, generated redistance header, overlay generator,
     canonical cell-offset header, C inference header, and weight hashes;
   - exact compile command and environment;
   - OpenMP thread count and assigned CPU list;
   - start/end UTC, wall time, exit state, peak RSS;
   - all primary output hashes, byte counts, and line counts;
   - platform fingerprint and provenance-lock hash.
6. Native manifests use `null` for NN-only artifacts; they never inherit a
   weight/header identity.

### Gate P3

- For every paired smoke, `generated_redistance_sha256` is identical.
- NN rows match the locked canonical header and weight hashes.
- Native rows contain no NN provider.
- A manifest can be independently regenerated from the row directory.

## 9. Phase 4 - Make NN statistics correct under OpenMP

### Files

- `cases/_shared/nn_cell_curvature/src/clsvof_nn_cell_curvature.h`
- `cases/_shared/nn_cell_curvature/tests/openmp_stats_smoke.c`
- `hpc/tests/test_openmp_stats.py`

### Work

1. Replace per-cell writes to shared global counters/sums/min/max with a
   per-thread statistics structure indexed by `omp_get_thread_num()`.
2. Allocate/reset one structure per `omp_get_max_threads()` before evaluation.
3. Each evaluation writes only to its thread-local slot.
4. Merge counts, sums, minima, maxima, and gradient moments deterministically
   only when emitting final statistics.
5. Preserve a `_OPENMP`-free serial fallback with identical output semantics.
6. Disable probes for formal runs. If probes remain supported for diagnostics,
   their scheduling state must also be synchronized or thread-local.
7. Do not use a global `critical` section on every cell inference; that would
   make the statistics correct but destroy scaling.

### Tests

- compile the same harness without OpenMP and with `-fopenmp`;
- compare 1-thread and 2/4/8-thread total evaluations and clamp/guard hits
  exactly;
- compare min/max exactly and sums/moments within a documented floating-point
  reduction tolerance;
- run under ThreadSanitizer if the Ubuntu compiler/runtime supports it;
- check that formal probe output is disabled.

### Gate P4

OpenMP parity tests pass, and the N64 NN smoke produces the same physical row
count/final-time contract at 1 and 4 threads.

## 10. Phase 5 - Enable OpenMP compilation and CPU binding

### Files

- all case generators
- `hpc/lib/platform.py`
- `hpc/run_row.py`
- `hpc/tests/test_scheduler.py`

### Work

1. Add `--threads N` and `--cpu-list LIST` to the row interface.
2. Add `-fopenmp` to both compile and link commands.
3. Set per-row environment:

   ```text
   OMP_NUM_THREADS=<assigned threads>
   OMP_DYNAMIC=FALSE
   OMP_PROC_BIND=close
   OMP_PLACES=cores
   OPENBLAS_NUM_THREADS=1
   MKL_NUM_THREADS=1
   VECLIB_MAXIMUM_THREADS=1
   ```

4. Launch with `taskset --cpu-list <assigned-list>`.
5. Parse `lscpu -p=CPU,CORE,SOCKET,NODE` and create CPU groups that:
   - do not overlap;
   - prefer one hardware thread per physical core first;
   - stay within one NUMA node when possible;
   - expand across nodes only when the requested group cannot fit;
   - report explicitly when the provider exposes SMT/vCPUs rather than 128
     physical cores.
6. Record the actual affinity seen inside each row.

### Gate P5

- Two concurrent smoke rows receive disjoint CPU sets.
- Each row reports the requested OpenMP thread count.
- No row can launch when its requested CPU group exceeds the allowed resource
  pool.
- A synthetic oversubscription test is rejected before subprocess creation.

## 11. Phase 6 - Implement the weighted 128-CPU scheduler

### Files

- `hpc/config/thread_policy.json`
- `hpc/lib/scheduler.py`
- `hpc/run_matrix.py`
- `hpc/tests/test_scheduler.py`

### Initial policy before server canary

| Scope | Threads/row | Maximum concurrent rows in 128 slots |
| --- | ---: | ---: |
| capwave/rising N64 | 8 | 16 |
| capwave/rising N128 | 16 | 8 |
| capwave/rising N256 | 32 | 4 |
| capwave/rising N512 | 64 | 2 |
| stationary N64 | 16 | 8 |
| stationary N128 | 32 | 4 |
| stationary N256 | 64 | 2 |

### Work

1. Replace `--jobs` as the primary resource control with a CPU-token scheduler:

   ```text
   sum(threads assigned to active rows) <= --cpus
   ```

2. `--cpus 128` is user control; preflight may lower the usable pool if fewer
   CPUs are visible.
3. Queue order:
   - Phase A: all 48 N64 formal rows;
   - validate Phase A completely;
   - Phase B: remaining 132 rows, longest predicted runtime first;
   - deterministic tie-break by benchmark, method, N, imax.
4. A completed row releases its exact CPU group, allowing smaller rows to fill
   gaps without oversubscription.
5. Graceful stop stops launching new rows but lets active rows finish.
6. A failed row does not trigger automatic parameter relaxation or overwrite.
7. `capacity.json` may replace initial thread counts after canary, but the
   accepted policy and its hash become part of the matrix identity.

### Tests

- never allocate more than 128 tokens;
- no CPU-list overlap;
- N64 phase contains exactly 48 rows;
- Phase B contains exactly 132 rows and no stationary N512;
- LPT ordering is deterministic;
- freed resources are reused;
- signal stop drains active rows without starting queued rows;
- invalid capacity policy is rejected.

### Gate P6

A dry scheduler simulation reaches 180 terminal simulated rows with zero
oversubscription, duplicate paths, or missing rows.

## 12. Phase 7 - Implement atomic results and strict resume

### Files

- `hpc/lib/integrity.py`
- `hpc/run_row.py`
- `hpc/verify_matrix.py`
- `hpc/tests/test_integrity_resume.py`

### Row state machine

```text
planned -> compiling -> running -> validating -> completed
                                      |-> failed_validation
compiling -> failed_compile
running   -> failed_runtime
```

### Work

1. Write work under `hpc/work/<matrix_id>/<row_id>/<attempt_id>/`.
2. Copy validated results to a staging directory on the same filesystem as the
   final result.
3. Generate manifest and recompute all hashes from staging.
4. Atomically rename staging to the immutable final row path.
5. Refuse to overwrite any existing final path.
6. On success, remove work by default; on failure, retain work and logs.
7. `--resume` skips only when:
   - row/matrix identity matches;
   - provenance and policy hashes match;
   - every declared primary file exists;
   - SHA-256, bytes, and line counts recompute exactly;
   - no undeclared staging directory exists.
8. Missing file, wrong hash, identity mismatch, or stale staging is a hard
   error requiring explicit operator action; it is never silently overwritten.

### Tests

- valid completed row is skipped;
- one-byte corruption is rejected;
- missing output is rejected;
- wrong Case 1/Case 2 identity is rejected;
- wrong header/weight/policy hash is rejected;
- stale staging is rejected;
- existing final destination prevents publish;
- atomic rename leaves either the old complete state or new complete state.

### Gate P7

The corruption/resume test suite passes entirely using Python `hashlib`.

## 13. Phase 8 - Ubuntu bootstrap, environment, and provenance

### Files

- `hpc/bootstrap_ubuntu.sh`
- `hpc/config/provenance.lock.json`
- `hpc/README.md`

### Bootstrap contract

Install exactly the required system packages:

```text
git build-essential gawk bison python3 python3-pytest time jq
numactl util-linux ca-certificates
```

No PyTorch, MPI, CUDA, desktop environment, Conda, or graphics package is
required on the server.

### Work

1. Verify Ubuntu 22.04 and x86_64; fail otherwise unless an explicit
   development override is supplied.
2. Make `basilisk/src/config` a relative link to `config.gcc`.
3. Build `qcc` from the packaged source after extraction to its final path.
4. Verify `qcc` and smoke binaries are x86_64 ELF, not Mach-O.
5. Verify all locked hashes before building formal rows.
6. Make bootstrap idempotent.
7. Record compiler, libc, kernel, Python, qcc, and repository paths.
8. Warn that the repository must not be moved after qcc is built; rebuilding
   qcc is required after a move.

### Gate P8

Running bootstrap twice succeeds, changes no locked source, and produces a
working OpenMP N64 compile smoke.

## 14. Phase 9 - Host preflight and capacity canary

### Files

- `hpc/preflight_hpc.py`
- `hpc/config/thread_policy.json`
- `hpc/tests/test_package.py`

### Preflight report

Write `hpc/results/<matrix_id>/platform/` containing:

```text
lscpu.txt
lscpu_extended.csv
numactl_hardware.txt
memory.txt
disk.txt
toolchain.json
platform.json
preflight.json
capacity.json
```

### Work

1. Check OS/architecture, source hashes, qcc, GCC/OpenMP compile, CPU topology,
   affinity, NUMA, RAM, disk, and write/rename behavior.
2. Run short correctness smokes for:
   - capwave NN N64 imax3;
   - rising Case 1 NN N64 imax3;
   - rising Case 2 NN N64 imax3;
   - stationary NN N64 imax3 with smoke horizon.
3. Run fixed-input scaling canaries at 1, 16, 32, 64, and 128 threads where
   topology permits.
4. Measure wall time, user/system time, peak RSS, CPU utilization, and result
   identity.
5. Compare 32x4, 64x2, and 128x1 aggregate throughput without allowing canary
   outputs into formal result paths.
6. Generate `capacity.json` with measured thread choices and CPU groups.
7. Delete canary output after its report and hashes are finalized.

### Capacity rules

- Prefer 32x4 or 64x2 by total throughput.
- Use 128x1 only if it is demonstrably better for total retained workload, not
  merely for one-row latency.
- No formal row starts when preflight is FAIL.
- No automatic assumption that `128 CPU` means 128 physical cores.

### Gate P9

`preflight.json.status == "PASS"`, all correctness smokes pass, and
`capacity.json` contains a non-overlapping, measured policy.

## 15. Phase 10 - One-command submission and final package

### Files

- `hpc/submit_matrix.sh`
- `hpc/collect_results.sh`
- `hpc/verify_matrix.py`

### Submit command

After bootstrap:

```bash
bash hpc/submit_matrix.sh --cpus 128 --matrix-id formal_180_001
```

Optional explicit matrix identity:

```bash
bash hpc/submit_matrix.sh \
  --cpus 128 \
  --matrix-id formal_180_001
```

### Submit flow

1. acquire a single-run lock;
2. run preflight or validate an existing matching `capacity.json`;
3. verify matrix/provenance/policy identities;
4. print the 180-row dry-run summary;
5. run and validate all 48 N64 formal rows;
6. stop if any N64 row is incomplete or invalid;
7. run remaining 132 rows with weighted LPT scheduling;
8. verify 180 terminal row identities and all completed outputs;
9. generate matrix-level status/manifest/timing/failure summaries;
10. call `collect_results.sh`;
11. print only the final package and SHA-256 paths as the final success lines.

### Package layout

```text
cfd_hpc_180_<matrix_id>/
  README.txt
  matrix_manifest.json
  matrix_status.csv
  matrix_timing.csv
  failure_ledger.csv
  provenance.lock.json
  capacity.json
  platform/
  results/
    capwave/N####/imax##/<method>/
    rising_case1/N####/imax##/<method>/
    rising_case2/N####/imax##/<method>/
    stationary_bubble/N####/imax##/<method>/
  logs/
  SHA256SUMS
```

Produce:

```text
hpc/packages/cfd_hpc_180_<matrix_id>.tar.gz
hpc/packages/cfd_hpc_180_<matrix_id>.tar.gz.sha256
```

The package contains results and evidence only. It does not contain compiler
caches, successful work directories, Git history, or smoke/canary raw output.

### Gate P10

- archive extracts successfully;
- package `SHA256SUMS` verifies after extraction;
- outer tarball SHA-256 verifies;
- extracted matrix manifest contains exactly 180 unique row IDs;
- no stationary N512 path exists;
- no file path escapes the package root.

## 16. Phase 11 - GitHub Actions fresh-clone gate

### File

- `.github/workflows/ubuntu-hpc.yml`

### CI jobs

1. Checkout on Ubuntu 22.04.
2. Run bootstrap and verify ELF qcc.
3. Run Python/unit tests.
4. Compile serial and OpenMP cell-offset statistics harnesses.
5. Verify all locked hashes.
6. Generate and validate the 180-row dry-run matrix.
7. Prove imax 0/5 accepted and -1/6 rejected.
8. Prove stationary N512 rejected.
9. Compile/run capwave, rising Case 1, rising Case 2, and stationary N64 smokes.
10. Run resume acceptance and corruption rejection tests.
11. Build a synthetic mini-package and verify its hashes and safe extraction.

### Gate P11

No server rental is authorized until the complete fresh-clone workflow is
green.

## 17. Phase 12 - Real-server release sequence

1. Rent the performance-first 128-CPU EPYC 9754 option.
2. Verify and extract the deployment tarball into its final absolute path.
3. Do not move it after qcc build.
4. Run once:

   ```bash
   bash hpc/bootstrap_ubuntu.sh
   ```

5. Submit everything:

   ```bash
   bash hpc/submit_matrix.sh --cpus 128 --matrix-id formal_180_001
   ```

6. Release gates inside the command:
   - preflight PASS;
   - capacity canary PASS;
   - 48/48 N64 formal rows valid;
   - 180/180 terminal row identities;
   - package verification PASS.
7. Transfer only the final `.tar.gz` and `.sha256` to the local machine.
8. Verify the outer hash locally before extracting.
9. Keep the server until local extraction and internal `SHA256SUMS` verification
   pass.

## 18. Failure and recovery policy

- Compile/runtime/validation failures are formal terminal evidence and retain
  their work directory.
- The scheduler may continue unrelated rows only after recording the failure;
  the final package cannot be marked complete while a row lacks an accepted
  terminal state.
- No failed row is retried with changed physics, tolerance, imax, resolution,
  method, thread count, or compiler flag under the same row identity.
- An infrastructure-only retry may reuse the row identity only when the first
  attempt produced no accepted physical result and both attempts are preserved
  in the ledger.
- `--resume` never deletes, repairs, or overwrites corruption automatically.
- Operator cleanup is explicit and row-scoped.

## 19. Implementation order and review checkpoints

| Order | Deliverable | Review question |
| ---: | --- | --- |
| 1 | Matrix library/config/tests | Is the scientific scope exactly 180 rows? |
| 2 | Rising Case 2 canonical integration | Do Case 1/2 differ only by official Case 2 flags/physics? |
| 3 | Native generators/common manifests | Are native/NN pairs comparable and traceable? |
| 4 | Thread-safe NN statistics | Is OpenMP numerically and statistically correct? |
| 5 | OpenMP row interface/CPU binding | Are CPU groups real, disjoint, and recorded? |
| 6 | Weighted scheduler | Does total assigned CPU never exceed the pool? |
| 7 | Atomic publish/resume | Is corruption always rejected? |
| 8 | Ubuntu bootstrap/preflight | Can a fresh clone build without local Mac dependencies? |
| 9 | One-command submit/package | Does one command produce one verified tarball? |
| 10 | GitHub Actions | Does the whole source path pass on clean Ubuntu 22.04? |
| 11 | Real-server canary/formal | Does measured capacity support the deadline? |

No later checkpoint begins when the preceding gate is red.

## 20. Definition of done

Implementation is complete only when all are true:

- the deployment repository contains only the allowlisted executable source
  and environment contract;
- Ubuntu 22.04 fresh-clone CI is green;
- both rising cases use the canonical shared cell-offset header and separate
  benchmark identities;
- NN statistics pass serial/OpenMP parity;
- the matrix is exactly 180 rows with stationary N512 impossible;
- preflight/capacity output is reproducible and hashed;
- the N64 formal gate is 48/48;
- all 180 rows have valid terminal evidence;
- strict resume rejects every tested corruption class;
- one `submit_matrix.sh` command completes orchestration;
- one verified `tar.gz` contains all necessary results, logs, manifests,
  provenance, platform information, and checksums;
- local extraction and both outer/inner SHA-256 verification pass.

## 21. Explicit non-goals

- no Slurm, MPI, GPU, CUDA, or server-side PyTorch;
- no modification of upstream Basilisk physics sources in place;
- no Git transport of formal datasets, work directories, or packages;
- no stationary N512 formal experiment;
- no use of legacy direct-NN/analytic modes as formal cell-offset rows;
- no promise of an exact wall time before the target-host capacity canary.
