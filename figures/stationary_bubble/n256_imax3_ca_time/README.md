# Stationary-bubble Ca(t), N256, imax=3

This single-resolution figure compares `CLSVOF` and `NN` over the completed
recorded-time interval `0 <= t <= 1`.

## Quantity definition

The raw time-series columns are

1. `t = mu * t_phys / D^2` (named `tau` in the generator),
2. `u_star = max(|u|) * sqrt(D)`,
3. volume-fraction change.

For `La = 12000`, the plotted capillary number is

```text
Ca(t) = u_star(t) / sqrt(La).
```

## Formal provenance

Matrix: `formal_180_epyc9654_32c_pack4_001`

| Figure label | Formal row ID | Raw SHA-256 | Samples | Final t |
|---|---|---|---:|---:|
| CLSVOF | `stationary_bubble__clsvof_native__N0256__imax03` | `3deba3b5af3a359073fd55790bd5d16e5d719b23c7a1da5c33c2d95eb0706ee0` | 569064 | 1 |
| NN | `stationary_bubble__clsvof_nn_cell_offset__N0256__imax03` | `849cd2a168fee7d1a6b4830b878b98f2331437ffdcd9e9161e066d7d294cc91d` | 569064 | 1 |

Both files are byte-identical to the corresponding raw outputs in the
checksum-verified formal result package. The plotting script checks these
hashes before loading the data.

Neither `imax=3` row satisfied the solver's `change(f) < 1e-10` early-stop
criterion. Both reached the time limit at `t=1`, with final volume-fraction
changes of approximately `1.30e-5` (CLSVOF) and `1.27e-5` (NN). The figure
therefore shows post-peak decay toward a nonzero residual-current regime; it
must not be described as convergence to zero. The main axis begins at the
shared startup peak (`t=7.0291e-6`) and uses logarithmic time.

The formal rows used 32 OpenMP threads on Linux. A new local four-thread rerun
is therefore unnecessary and is not represented by this figure.
