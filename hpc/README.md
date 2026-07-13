# Ubuntu HPC runner

Target: Ubuntu 22.04 x86_64, one host, OpenMP only.

Create a clean deployment archive from the current research workspace:

```bash
bash hpc/prepare_deployment.sh
```

Copy `hpc/packages/cfd-hpc-runner.tar.gz` and its `.sha256` file to the
Ubuntu host, verify the checksum, and extract it. The archive contains source,
weights, environment scripts, tests, and matrix configuration. It excludes
compiled objects, `qcc`, caches, work directories, and results.

One-time setup after extracting into the final path:

```bash
bash hpc/bootstrap_ubuntu.sh
```

Formal 180-row submission and verified package:

```bash
bash hpc/submit_matrix.sh --cpus 128 --matrix-id formal_180_001
```

Always choose and record a fixed matrix ID. Use `--resume` only when restarting
that same ID after an interruption:

```bash
bash hpc/submit_matrix.sh --cpus 128 --matrix-id formal_180_001 --resume
```

The default is strictly sequential at the row level (`--max-active-rows 1`).
Each row still uses the OpenMP thread count selected by
`hpc/config/thread_policy.json`. Pass a different `--policy` file to change
threads without editing the runner. Multi-row concurrency is only enabled by
an explicit `--max-active-rows N` greater than one.

For an independent acceptance record of the four rising OpenMP smokes, use
`hpc/verify_rising_openmp_smokes.py` with the Case 1/2 native and NN result
directories. It rejects missing `CASE2=1`, serial execution, compiler stderr,
incomplete `t=3` output, row-count mismatches, and non-canonical NN headers.

The matrix contains capwave, rising Case 1, rising Case 2, and stationary
N64-N256; native and NN cell-offset; imax 0-5. Stationary N512 is rejected.

See `docs/server/ubuntu22-hpc-operator-handoff.md` for the exact upload,
bootstrap, preflight, canary, formal-run, monitoring, recovery, and result
transfer procedure.
