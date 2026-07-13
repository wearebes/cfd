# Solver-facing curvature and denominator note

## What the stock solver asks for

At the active `distance_curvature(point, d)` call, Basilisk uses a 3x3 central
difference of the current level-set field `d` and returns the curvature of the
level set passing through the current cell centre. It does **not** first project
the cell to the zero level set. The NN replacement must therefore return a
cell-local curvature, in physical units, at that same call site.

The model predicts the dimensionless zero-level-set quantity

\[
q_\Gamma = \Delta\kappa_\Gamma.
\]

For a signed-distance field, the corresponding current-cell level-set value is

\[
q_{\rm cell}=\frac{q_\Gamma}{D},\qquad
D=1+\frac{d}{\Delta}q_\Gamma,
\qquad
k_{\rm NN}=\frac{q_{\rm cell}}{\Delta}.
\]

This is the sole NN inference map in `clsvof_nn_cell_curvature.h`. The old direct
return `q_gamma/Delta` is not an executable provider mode.

## What “denominator risk” means

The division by `D` does not materially lose floating-point precision: the
conversion is performed in `double`, so ordinary rounding is around machine
precision. The relevant risk is instead **model-error amplification**. A small
prediction error `delta q_gamma` changes the converted value approximately by

\[
\delta q_{\rm cell}\approx\frac{\delta q_\Gamma}{D^2}.
\]

Thus `D` near zero is geometrically ill-conditioned. For intuition: if
`D = 1`, there is no amplification; if `D = 0.9`, a relative prediction error
is enlarged by about `1/0.9`; and at `D = 0.25`, it can be enlarged by up to
four times in relative terms. This is not a loss caused by the division itself.

The provider uses a signed denominator guard `|D| >= 0.25`, records every guard
hit, and clamps only after conversion. A guard or clamp hit makes a validation
run unacceptable. In the completed analytic and host runs there were no guard
or clamp hits; the offline minimum observed `|D|` was 0.8693.

## Scope

This alignment makes the NN return the same *geometric location* of curvature
as the stock cell-local operator. It does not claim to reproduce the stock
finite-difference value bit-for-bit, nor does it by itself guarantee an
improvement of the full discrete surface-tension operator.
