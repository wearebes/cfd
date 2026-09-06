# Figure artifact policy

- `figures/` is a repository-root artifact surface, separate from `dataset/`.
- The first directory level is the scientific case name used by `dataset/`.
- Each figure type has one leaf directory containing exactly one runnable
  `plot.py`, its corresponding PNG, and any figure-specific source data.
- Data reused by multiple figures live once under the case's `shared_data/`
  directory; full formal results remain in `dataset/`.
- When several figures in one case reuse plotting logic, that implementation
  may live once in a case-local `_plot_common.py`; every figure still has its
  own runnable leaf-level `plot.py` entry point.
- Run a figure from its leaf directory with `python3 plot.py` in an environment
  providing matplotlib, NumPy, and pandas where required.
- A formal image is accepted only after its adjacent `plot.py` has generated
  that exact file twice consecutively with the same SHA-256 hash. An image with
  no adjacent runnable entry point does not belong in `figures/`.
- Use Python/matplotlib for repository scientific figures unless the user
  explicitly requests another backend.
- Use the unified scientific method names in all figure-facing labels and
  formal figure names: `CLSVOF` for the baseline and `NN` for the learned
  variant. Internal dataset/path identifiers such as `native`, `nn`, and
  `nn_cell_offset` must not replace these labels in titles, legends, axes,
  annotations, or formal figure names.
- PNG is the only image deliverable by default. Export one opaque-white,
  tightly cropped PNG at 600 dpi.
- Do not generate PDF, SVG, TIFF, or other duplicate image formats unless the
  user explicitly requests a specific additional format.
- Keep smoke plots, experimental scripts, caches, and time-stamped attempts
  under `tem/`, not in the formal figure tree.
- Preserve upstream/reference-only images under `tem/` or their source-data
  archive; do not mix them with locally reproducible formal figure outputs.

## Current FP64 manuscript plots

The manuscript plots restored from `chore/figures-reorg-fp64-switch` read
original run artifacts under `data/` through `data_paths.py`. They default to
`CFD_NN_INFERENCE_PRECISION=float64-forward`; the loader checks the recorded
precision, compile flag, completion state and published artifact hashes.
The Hysing reference files remain under `dataset/rising_bubble/case*/reference/hysing/`.
The older figure families above still use their existing historical sources.

The manuscript result entry points are `stationary_bubble/ca_terminal_vs_grid`,
`stationary_bubble/ca_time_n32_n128`, `stationary_bubble/velocity_fields`,
`capwave/amplitude_histories`, `capwave/e2_grid_convergence`,
`rising_bubble/interfaces_imax3`, and `rising_bubble/histories_imax3`.
Each contains `plot.py`. For the velocity-field manuscript panel, pass
`--resolution 32 --tau 1 --nn-source crossing`.
Stationary terminal and history plots use the whole-domain maximum, matching
the manuscript definition. Stationary N256 has complete published terminal
artifacts but a failed runner status; the loader warns about this explicit
exception. N512 stationary output is not used.

Build the paper with `latexmk -cd -pdf -outdir=../tem/paper_build_fp64 paper/main.tex`
from the repository root, keeping build output outside `paper/`.
