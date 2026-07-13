# Capwave NN cell-offset runner reproduction

Date: 2026-07-12

## Result

`cases/capwave/generate/nn_cell_offset.sh` passed the N64 reproduction gate.
No smoke result was published under `dataset/`.

## Checks

1. **Behavior preservation (default `imax=3`)**
   - Generated single-resolution case is byte-identical to the accepted
     2026-07-10 N64 reproduction case.
   - The first new full run is byte-identical to
     `/private/tmp/kappa_offset_capwave_final_offset_d_64_o2_20260710T2315Z`:
     - `wave-64`: 738 rows, SHA-256
       `479ddac7bce29d508cbe1877476007e1d58c66636e6a5920cdff8740e3f03930`
     - `log`: SHA-256
       `d637a8e8f52c46f5b397f3343b683a78e1f44a437b0aaa1f34b815b556f0a247`
     - Prosperetti relative RMS: `0.00710109`
2. **Executable path**
   - Shell syntax and Python source compile checks passed.
   - Full compile and solve completed successfully.
3. **Output routing**
   - smoke: `tem/capwave/nn_cell_offset/try_*`
   - formal default: `dataset/capwave/nn_cell_offset_matched/N0064`
   - formal non-default: `dataset/capwave/nondefault_redistance/imax_2/N0064`
4. **Repeat smoke**
   - A second independent `imax=3` run produced byte-identical `wave-64`
     and `log` files.
5. **Non-default control (`imax=2`)**
   - Generated header contains `redistance (d, imax = 2, ...)`.
   - `wave-64` SHA-256:
     `656558d674aae1eafa66676b0815ce241e145b45c7ef86f4dbfb98e0112cb309`
   - Prosperetti relative RMS: `0.00705089`.
   - The difference from `imax=3` confirms that the requested parameter
     affects execution. This is a smoke diagnostic, not a scientific finding.

Both default runs recorded 48,640 provider evaluations with zero clamp hits
and zero denominator-guard hits.

## Cleanup

The three new smoke result directories and their three compile work
directories were deleted after recording this report. Historical accepted
evidence was not modified.
