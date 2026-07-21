# Reproducible data generation

`generate/` is the human-readable source of truth for producing solver data.
Every runnable row has an explicit output path, exposes its scientific
parameters on the command line, and can show the fully resolved plan before
compilation.

## Entrypoints

| case | official stock reference | matched CLSVOF | NN treatment |
|---|---|---|---|
| capillary wave | `capwave/official.sh` | `capwave/clsvof.sh` | `capwave/nn.sh` |
| rising bubble | `rising_bubble/official.sh` | `rising_bubble/clsvof.sh` | `rising_bubble/nn.sh` |
| stationary bubble | `stationary_bubble/official.sh` | `stationary_bubble/clsvof.sh` | `stationary_bubble/nn.sh` |
| oscillating droplet | `oscillating_droplet/official.sh` | `oscillating_droplet/nn/generate/run_row.py --method clsvof` | `oscillating_droplet/nn/generate/run_row.py --method nn` |

The shell rows share these controls:

```text
--output PATH --resolution N --threads N --smoke|--formal --dry-run
```

Matched CLSVOF and NN rows also expose `--imax 0..5`. NN rows expose
`--model NAME`. Rising bubble adds `--case 1|2`; stationary bubble adds
`--tau-max`. Run an entrypoint with `--help` for its exact contract.

The official oscillating-droplet reference is intentionally fixed to the
official LEVEL 4--7 suite. It does not offer a resolution override because
changing that suite would no longer reproduce the stock reference.

## Audit before execution

For example, inspect an N64 NN plan without creating the requested output:

```bash
bash generate/capwave/nn.sh \
  --formal --resolution 64 --imax 3 --model baseline_64_hgradient \
  --threads 1 --output /absolute/result/path --dry-run
```

The JSON output contains the exact compile/run argument arrays, parameters,
environment, source hashes, generator hash, Git state and `plan_sha256`.
Actual execution reconstructs the same plan, writes `manifest.json` with
`status: running` before compilation, and refuses to mark it completed if the
plan or a source hash changed. A normal failure is retained as `failed`; an
ungraceful kill leaves visible `running` evidence rather than an apparently
complete dataset.

Each successful output contains `source_snapshot/` plus the raw and derived
scientific artifacts. Existing output paths are never overwritten.

## Models and formal scope

The shared NN C runtime is `generate/_shared/nn_runtime/`. Formal generated C
weights are restricted to:

```text
dataset/model/c_exports/baseline_{64,128,256,512}_hgradient/
```

N32 and other exploratory exports belong under
`dataset/model/diagnostic_c_exports/` and cannot enter the 180-row formal
matrix. Stationary-bubble N512 is also outside that matrix.

## Generated documentation and campaign boundary

Each case's `summary.yaml` is generated from the entrypoints' live dry-run
contracts:

```bash
python3 generate/_shared/render_summaries.py
python3 generate/_shared/render_summaries.py --check
```

Framework acceptance uses one real N64 smoke per case. The formal matrix is
not part of this setup check and is never launched implicitly.
