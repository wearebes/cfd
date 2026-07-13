# N64 CLSVOF stationary-bubble smoke

This isolated experiment derives its physical and output contract from
`basilisk/src/test/spurious.c`, while using Basilisk CLSVOF
(`two-phase-clsvof.h` plus `integral.h`).

Run the native/analytic controls with:

```bash
./experiments/stationary_clsvof_smoke/run_smoke.sh
```

`clsvof_native` uses the stock `integral.h`.  `clsvof_contour_analytic`
changes only the active curvature assignment to `1/(R + d)`, the curvature
of the current signed-distance contour for `d = r - R`.

Run the sole supported NN deployment path with:

```bash
./experiments/stationary_clsvof_smoke/run_nn_smoke.sh
```

The model predicts zero-level-set curvature
`q_gamma = Delta*kappa_gamma`. The shared
`clsvof_nn_cell_curvature.h` provider converts this to
the curvature of the level set through the current cell,
`q_cell = q_gamma/(1 + (d/Delta)*q_gamma)`, and returns
`kappa_cell = q_cell/Delta` to the active `ki` assignment in `integral.h`.
There is no direct `q_gamma/Delta` executable mode.

Each timestamped result directory contains the official-compatible
`La-12000-6` time series, the final `log`, provenance `manifest.json`, and a
derived `summary.csv`.  `summary.csv` records Ca as a descriptive smoke
metric; it is not a pass/fail gate.

Historical timestamped direct-NN result directories are retained only as
non-executable audit evidence. They are not supported methods and must not be
merged into current summaries or formal matrices.
