# Cloud matrix: three cases, imax 0 through 10

Date: 2026-07-12

## Matrix

| Case | Resolutions | imax | Rows |
| --- | --- | --- | ---: |
| capwave | 64, 128, 256, 512 | 0..10 | 44 |
| rising bubble, Hysing Case 1 | 64, 128, 256, 512 | 0..10 | 44 |
| stationary bubble | 64, 128, 256, 512 | 0..10 | 44 |
| **Total** |  |  | **132** |

There are 12 default rows (`imax=3`) and 120 non-default rows. Default rows
are routed to `nn_cell_offset_matched`; they are not duplicated under
`nondefault_redistance`.

The declarative matrix is
`cases/_shared/nondefault_redistance/config/matrix_imax_0_10.yaml`.

## Parallel execution model

Each Basilisk row is a single-threaded process. `--jobs N` controls how many
independent rows run at the same time. The scheduler sets common BLAS/OpenMP
thread variables to one to prevent nested oversubscription.

The selected job count must fit both CPU and memory. On a machine with many
cores but limited RAM, start below the visible core count because multiple
N512 rows can be memory-intensive.

## Cloud commands

After copying the repository to a Linux server, rebuild the Basilisk tools for
that server rather than reusing local macOS binaries:

```bash
make -C basilisk/src -B qcc
make -C basilisk/src/gl -B
```

Validate all 132 commands and destinations without running a solver:

```bash
python3 cases/_shared/nondefault_redistance/run_matrix.py \
  --formal --dry-run --jobs 8 \
  --summary report/runs/cloud_imax_0_10_dryrun.json
```

Run the full matrix with a user-selected concurrency level:

```bash
CORES=16
mkdir -p report/runs
nohup python3 cases/_shared/nondefault_redistance/run_matrix.py \
  --formal --jobs "$CORES" --resume \
  --summary report/runs/cloud_imax_0_10.json \
  > report/runs/cloud_imax_0_10.jsonl 2>&1 &
```

`--resume` skips an existing result only when its formal manifest matches the
case, method, resolution and imax. Existing incomplete or mismatched targets
are reported as failures and are not overwritten.

To run a subset, use `--cases`, `--resolutions`, or `--imax`, for example:

```bash
python3 cases/_shared/nondefault_redistance/run_matrix.py \
  --formal --jobs 8 --resume \
  --cases capwave rising_bubble \
  --resolutions 64 128 \
  --imax 0 1 2 3 4 5 6 7 8 9 10
```

## Verified behavior

- Full 132-row formal dry-run with `--jobs 8`: 132 planned, 0 failed, 132
  unique output destinations.
- Two independent concurrent N64/imax=10 smoke matrices with `--jobs 3`:
  all three cases completed both times.
- Capwave: 738-row wave output byte-identical between repeats, SHA-256
  `f941347f9a7af629b3e965c769194c4f76c9e8df10dcd5b7e3506ff2d7e0ce23`.
- Rising: 215 physical rows identical between repeats, canonical physical
  SHA-256
  `4babaa8ab220a05bb4b55c1ae7829c8c2f49ede1a66713c30e889929a6206630`.
- Stationary: 712-row series byte-identical between repeats, SHA-256
  `b8d2941a47d8587a8dce3e5c1cc1c8bd19f05472affdc76d9e73afbbc5f1b208`.
- Every generated local header contained `redistance (d, imax = 10, ...)`.
- 56 authoritative regression tests passed. A root-directory invocation of
  four legacy matrix test modules failed during collection because those tests
  import sibling modules; the authoritative rerun from the legacy experiment
  directory passed all 21 tests.

The two local smoke matrices and their compile work directories were deleted
after this report was written. No formal dataset was created locally.
