# Legacy-to-generate N64 equivalence gate

Date: 2026-07-21

Scope: one single-threaded N64, `imax=3`, smoke row for both `clsvof` and
`nn`, comparing the restored `cases/` entrypoints with the new `generate/`
entrypoints. This is migration evidence only; it is not a formal dataset.

## Result

| case/method | scientific comparison | result |
|---|---|---|
| capwave/clsvof | `wave-64`, official error `log` | byte-identical |
| capwave/nn | `wave-64`, official error `log`, provider statistics | byte-identical |
| rising/clsvof | interface `log`; history columns t, volume, phase marker, center, velocity, dt | numerically identical |
| rising/nn | interface `log`; history columns t, volume, phase marker, center, velocity, dt; provider statistics | numerically identical |
| stationary/clsvof | `La-12000-6` trajectory | byte-identical |
| stationary/nn | `La-12000-6` trajectory and provider statistics | byte-identical |

Runtime/performance text is deliberately excluded: wall/CPU rates in capwave
and Basilisk performance columns in rising bubble varied between consecutive
runs while the scientific columns were identical.

## Documented diagnostic exception

The full stationary terminal `log` is not byte-equivalent. The velocity
metric is unchanged, but the shape and curvature fields differ because the
current `generate/stationary_bubble/src/stationary-clsvof.c` already contains
an observable correction absent from the restored legacy source:

- it constructs the official-compatible bubble fraction as `1 - f`;
- it computes volume, shape error and curvature from that bubble fraction;
- it applies an explicit max reduction for curvature error;
- it records the termination reason and terminal nondimensional time.

The solver trajectories remain byte-identical, showing that this is a
diagnostic correction rather than a trajectory change. The repository's
formal-v2 contract also forbids publishing the known-invalid pre-correction
stationary `ekmax`. The migration gate therefore passes for physics and
scientific primary streams with this correction explicitly recorded; it does
not claim that runtime text or every derived legacy field is byte-identical.

Machine-readable evidence is stored at
`reports/generate_framework/legacy_equivalence_n64.json` and can be reproduced
with `generate/_shared/verify_legacy_equivalence.py` while both smoke roots are
available.

## Reproduction roots from this gate

```text
/tmp/cfd-n64-legacy.ncw9wZ
/tmp/cfd-n64-canary.YbWFqJ
```

These are temporary smoke artifacts, not canonical results.
