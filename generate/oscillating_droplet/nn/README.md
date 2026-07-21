# Oscillating droplet CLSVOF NN cell-offset experiment

This case compares a frozen CLSVOF host with one treatment in which the
cell-local `integral.h` curvature is supplied by the matched-resolution NN.

The model predicts interface `q_gamma = Delta*kappa_gamma` using the training
sign `phi = r - R`.  The oscillation host uses `d = R - r`, so the case adapter
builds raw27 from `-d`, reverses the model curvature sign, and then applies
`q_cell = q_gamma/(1 + (d/Delta)*q_gamma)` before returning `q_cell/Delta`.

Formal matched rows are limited to LEVEL 6/N64 and LEVEL 7/N128. Probe-only
and short-time rows belong under `tem/`; full formal run directories belong
under `hpc/results/oscillating_droplet/nn_matched/<run_id>/`.
Only their final numerical time series are published into the canonical
`dataset/oscillating_droplet/Nxxxx/imax03/{clsvof,nn}/` paths.

The separate redistance sensitivity matrix covers matched LEVEL 6--9
(N64/N128/N256/N512), `imax=0..5`, and paired CLSVOF/NN rows. It is written
under `hpc/results/oscillating_droplet/nn_redistance_imax/<run_id>/`.
After verification, only final `timeseries.dat` products are published into
the canonical dataset.

Reproduction sequence:

```bash
python3 -m pytest generate/oscillating_droplet/nn/tests \
  generate/_shared/nn_runtime/tests -q
bash generate/oscillating_droplet/nn/generate/run_canary.sh
bash generate/oscillating_droplet/nn/generate/run_matched_matrix.sh <run_id>
python3 generate/oscillating_droplet/nn/analyze/summarize_rows.py \
  hpc/results/oscillating_droplet/nn_matched/<run_id>
MPLCONFIGDIR=/tmp/matplotlib-cfd python3 \
  generate/oscillating_droplet/nn/analyze/plot_overview.py \
  hpc/results/oscillating_droplet/nn_matched/<run_id> \
  figures/oscillating_droplet/nn_matched/<run_id>
```

Redistance sensitivity execution:

```bash
python3 generate/oscillating_droplet/nn/generate/run_imax_matrix.py \
  --run-id <run_id> --jobs 4
python3 generate/oscillating_droplet/nn/analyze/summarize_imax_matrix.py \
  hpc/results/oscillating_droplet/nn_redistance_imax/<run_id> \
  --publish-dataset
```

Publication is blocked unless all 48 rows are accounted for and no
infrastructure failure remains. Numerically failed rows are retained as partial
time series and recorded with `complete=false` in `dataset/runtime.csv`.

The completed local reference run is `20260714T163300Z`; see its `RESULTS.md`
and `verification.json` before interpreting the figures.
