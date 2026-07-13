# CLSVOF curvature position-conversion validation

This external experiment keeps the Basilisk tree read-only. Generated overlays
replace only the active cell-local curvature provider call.

The experiment exposes exactly two scientific runs: untouched `original`
CLSVOF and `nn_cell_levelset`. The NN run maps the model's
zero-level-set prediction `q_gamma` to the current cell's level-set curvature
with `q_cell = q_gamma/(1 + (d/Delta)*q_gamma)` and returns `q_cell/Delta`.
The shared implementation is the single header
`include/clsvof_nn_cell_curvature.h`. The former direct `q_gamma/Delta` and
gradient-adjusted modes have been removed
from the executable provider and runner. The former `native_wrapper` control
was also removed after stock equivalence had been established. Historical
timestamped results remain read-only audit evidence. See
[SOLVER_K_SEMANTICS.md](SOLVER_K_SEMANTICS.md).
