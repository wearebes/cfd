# Rising bubble official data

Archived local data for Basilisk's official `test/rising.c` benchmark.

## Contents

- `raw/`: official variants referenced by the gnuplot blocks in `rising.c`.
- `figures/`: gnuplot scripts and SVGs for the official rising-bubble plots.
- `sources/`: `rising.c` and MooNMD reference data snapshots.

## Variants

Case 1:

- `rising`
- `rising-levelset`
- `rising-clsvof`
- `rising-axi`
- `rising-axi-clsvof`
- `rising-axi-momentum`

Case 2:

- `rising2`
- `rising2-levelset`
- `rising2-clsvof`

## Data columns

Each `out` file starts with:

```text
t sb -1 xb vb dt perf.t perf.speed ...
```

Fields used by official plots:

- column 1: time
- column 2: relative volume difference `(vb - vb0)/vb0`
- column 5: rise velocity

Each `log` file contains final-time bubble interface facets at `t = 3` and is
used by the official shape plots as columns 1 and 2.
