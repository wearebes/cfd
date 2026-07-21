# Oscillating-droplet NN result figure contract

- Core conclusion: determine whether matched NN cell-offset curvature changes CLSVOF damping toward the inviscid/VOF-HF reference without sacrificing its frequency accuracy.
- Figure archetype: quantitative grid with paired causal evidence.
- Backend: Python/matplotlib only.
- Target/output: double-column scientific figure, 183 mm wide; one opaque-white 600-dpi PNG. Do not generate PDF, SVG, or TIFF unless explicitly requested.
- Panel a: N64 kinetic-energy trajectory, native versus NN.
- Panel b: N128 kinetic-energy trajectory, native versus NN.
- Panel c: fitted damping `b` at N64/N128, with matched Standard VOF-HF descriptive reference.
- Panel d: absolute frequency error at N64/N128, with matched Standard VOF-HF descriptive reference.
- Hero evidence: paired trajectory and damping changes on the identical CLSVOF host.
- Validation evidence: frequency error and provider health gates reported outside the figure.
- Statistics: gnuplot asymptotic fit standard errors; no repeated-run variability or significance test is claimed.
- Source data: formal row `k-*`, `comparison.csv`, and `landscape_5method.csv`.
- Reviewer risk: only two matched NN resolutions exist; do not infer convergence order or cross-solver causality.
