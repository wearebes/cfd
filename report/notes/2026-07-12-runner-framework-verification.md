# Runner framework verification

Date: 2026-07-12

## Outcome

The case-first NN cell-offset execution path is runnable for capwave,
rising-bubble Case 1, and stationary bubble. Each case owns one shell runner;
the redistance matrix is a thin caller of the capwave/rising runners.

Smoke results were written only below `tem/`. Formal routing was verified with
dry-runs and was not executed, so no smoke result entered a canonical dataset.
All smoke and compile-work directories created in this verification were
deleted after their measurements were recorded in the case reports.

## Reproduction summary

| Case | Preservation check | Repeat check | imax control |
| --- | --- | --- | --- |
| stationary bubble N64 | full default run byte-identical to accepted 71,133-row series | two short default runs byte-identical | imax=2 header and series differ |
| capwave N64 | full 738-row wave and log byte-identical to accepted result | two default runs byte-identical | imax=2 header, wave hash and RMS differ |
| rising Case 1 | N256 physical columns identical to accepted full run at printed precision | two N64 physical trajectories and provider stats identical | imax=2 header and physical trajectory differ |

Rising stdout also includes non-deterministic CPU/performance columns, so its
repeat gate compares the first six benchmark/step columns rather than whole
files. The historical rising accepted run used split provider headers; the new
combined header preserves all printed physical columns but changes the
recorded minimum denominator. Details are retained in the rising case report.

## Routing

| Case | Smoke | Formal default (`imax=3`) | Formal non-default |
| --- | --- | --- | --- |
| capwave | `tem/capwave/nn_cell_offset/try_*` | `dataset/capwave/nn_cell_offset_matched/N####` | `dataset/capwave/nondefault_redistance/imax_N/N####` |
| rising bubble | `tem/rising_bubble/nn_cell_offset/try_*` | `dataset/rising_bubble/nn_cell_offset_matched/N####` | `dataset/rising_bubble/nondefault_redistance/imax_N/N####` |
| stationary bubble | `tem/stationary_bubble/nn_cell_offset/try_*` | `dataset/stationary_bubble/nn_cell_offset_matched/N####` | `dataset/stationary_bubble/nondefault_redistance/imax_N/N####` |

Formal runners reject an existing destination rather than overwriting it.
The matrix scheduler defaults to `imax=0,1,2,4,5`; `imax=3` remains outside
`nondefault_redistance`.

## Independent tests

- C/PyTorch raw27 and forward golden parity: 2 passed.
- Cell-offset math and integral overlay: 4 passed.
- Redistance overlay: 11 passed.
- Matrix configuration, scheduling, row command, and provenance: 21 passed.
- Total: 38 passed.

Two non-authoritative invocations failed before test execution: system Python
did not contain torch, and the first `pinn` import aborted until BLAS/OpenMP
threads were constrained. One redistance invocation was also collected from
the wrong working directory. The authoritative invocations above used the
required environment and module working directory and passed.

## Detailed reports

- `report/notes/2026-07-12-stationary-runner-reproduction.md`
- `report/notes/2026-07-12-capwave-runner-reproduction.md`
- `report/notes/2026-07-12-rising-runner-reproduction.md`
