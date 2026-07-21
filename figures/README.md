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
- Use scientific method names in all figure-facing labels and formal figure
  names: `CLSVOF` for the baseline and `CLSVOF NN cell-offset` for the NN
  variant. `native` is only an internal dataset/path identifier and must not
  appear in titles, legends, axes, annotations, or formal figure names.
- PNG is the only image deliverable by default. Export one opaque-white,
  tightly cropped PNG at 600 dpi.
- Do not generate PDF, SVG, TIFF, or other duplicate image formats unless the
  user explicitly requests a specific additional format.
- Keep smoke plots, experimental scripts, caches, and time-stamped attempts
  under `tem/`, not in the formal figure tree.
- Preserve upstream/reference-only images under `tem/` or their source-data
  archive; do not mix them with locally reproducible formal figure outputs.
