# CLSVOF redistance imax formal matrix

This directory contains the runner for the planned 96-cell matrix defined in:

- `docs/superpowers/plans/2026-07-11-clsvof-redistance-imax-formal-matrix.md`
- `docs/superpowers/plans/2026-07-11-clsvof-redistance-imax-acceptance-contract.md`
- `docs/superpowers/plans/2026-07-11-clsvof-redistance-imax-matrix-preview.csv`

The implementation is external to `basilisk/src`. A row-specific local copy of
`two-phase-clsvof.h` changes only the stock `imax=3` argument and adds read-only
SDF diagnostics around the actual physical redistance call.

NN rows must reuse the sole deployment map in
`experiments/clsvof_kappa_offset_conversion`: the model predicts
`q_gamma = Delta*kappa_gamma`, then the provider converts it to the curvature
of the level set through the current cell,
`q_cell = q_gamma/(1 + (d/Delta)*q_gamma)`, and returns `q_cell/Delta`.
The obsolete direct `q_gamma/Delta` providers and the
`CAPWAVE_K_NN_RAW`/`RISING_K_NN_RAW` compile modes are forbidden. Native rows
use the stock `integral.h` without a wrapper provider.

The historical result root `results/20260710T172910Z` is no longer a complete
matrix. It retains only 48 native rows; its obsolete direct-NN rows and all
derived 96-row audits/figures were deleted. See `NATIVE_ONLY_RETAINED.md`.
Future cell-offset NN runs require a new matrix identity and may not reuse old
NN metrics.

Execution is gated. Do not launch the general matrix until generator tests,
compile tests, stock `imax=3` equivalence, and the full N64 extreme rows pass.

The adaptive scheduler originally used a hard ceiling of four single-core
solver rows. On 2026-07-11 the user explicitly raised the approved ceiling to
five; the five-row setting is used only with the same AC-power and memory gates.
The managed execution environment rejected macOS background QoS and positive
nice settings, so the scheduler uses plain-priority processes and protects
interactive work through AC-power and memory-pressure launch gates. Three-row
execution passed the N64/N128/N256 canaries; five rows are now an explicit
throughput choice and may still be lowered without changing matrix identity.

## Report-facing outputs

`summarize_matrix.py` recomputes capwave time-history errors directly from each
738-row `wave-N` file and the frozen stock `prosperetti.h`. The independently
recomputed relative RMS is accepted against the solver's `%g` log value with
absolute tolerance `3e-8` and relative tolerance `3e-5`; this bound covers the
observed decimal-output rounding without masking a changed waveform.

`analyze_matrix.py` emits both kinds of comparisons required by the formal
contract: `delta_vs_imax3.csv` compares each method with its stock-iteration
reference, while `paired_native_nn_deltas.csv` computes NN minus native at the
same `(benchmark, N, imax)`. `convergence_by_imax.csv` contains capwave observed
orders and runtime-scaling exponents across the available resolutions.
`tradeoff_by_identity.csv` keeps the physical-error, SDF-error, runtime, and
`imax=3` choices separate, and `sdf_physics_relationship.csv` records whether
lower E-grad and lower physical error are actually aligned for each identity.
`runtime.csv` gives a uniform 96-row cost table (launcher wall time for every
row and stock CPU/real time where emitted), while `failures.csv` is the explicit
failure ledger and remains header-only when no formal row fails.

`plot_formal_matrix.py` is hard-gated on `audit.json` reporting exactly 96
completed rows and `passed=true`. It then renders the physical-error trends,
physical/SDF/runtime heatmaps, SDF-versus-physics relationships, selected N512
time histories, and rising final-shape overlays from the audited CSV/raw files.
Every figure is exported as editable-text SVG, PDF, and 600-dpi PNG with a
companion source-data CSV and QA manifest.

After the strict row audit passes, `verify_formal_matrix.py` reruns the matrix
test suite and the raw27/C-forward golden-vector parity suite and records their
logs and input hashes. `closure_audit.py` is the final gate: it requires all 96
rows, aggregate tables, time histories, 18 figure exports, six figure source
tables, editable SVG text, passed visual QA, and the verification manifest.
`audit_workspace_boundary.py` additionally compares the exact current
`basilisk/src` Git-status set with the dirty-worktree baseline captured before
execution, so pre-existing user files are preserved without being mistaken for
matrix-created source changes.
