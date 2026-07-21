# Rising-bubble NN cell-offset runner reproduction

Date: 2026-07-12

Scope: planar Hysing Case 1.

## Result

`cases/rising_bubble/generate/nn.sh` passed the matched-resolution
smoke and behavior-preservation gates. No smoke result was published under
`dataset/`.

## Checks

1. **Behavior preservation**
   - A full N256 (`LEVEL=8`, actual grid `256x64`) `imax=3` replay reached
     `t=3` with 1,637 physical rows.
   - Every row's first six solver columns is identical at the file's output
     precision to the accepted 2026-07-10 cell-offset run. The canonical
     physical-column SHA-256 is
     `ceb08d32d9c09416dfab1155fc218b99b84d192b88e616984bab52e806c3b6d7`.
   - Final values: volume drift `-9.33764e-05`, center `1.0806`, velocity
     `0.193281`.
   - Whole stdout files are intentionally not compared byte-for-byte because
     later columns contain wall/CPU performance measurements.
   - The historical run used the pre-migration split provider headers while
     the new runner uses the combined shared header. The physical columns are
     equal, provider evaluation/clamp/guard counts are equal, but the minimum
     observed denominator differs (`0.9376923216` historical vs
     `0.9381517375` new). This diagnostic difference is recorded rather than
     hidden; it does not change any printed benchmark physical column.
2. **Executable path**
   - Shell syntax passed; full compile and solve completed for N64 and N256.
   - Resolution mapping is N64/128/256/512 to LEVEL 6/7/8/9, i.e. actual
     grids `64x16`, `128x32`, `256x64`, `512x128`.
3. **Output routing**
   - smoke: `tem/rising_bubble/nn/try_*`
   - formal default: `dataset/rising_bubble/nn_matched/N0064`
   - formal non-default:
     `dataset/rising_bubble/nondefault_redistance/imax_2/N0064`
4. **Repeat smoke**
   - Two independent N64 `imax=3` runs each produced 215 physical rows.
   - Their canonical physical-column SHA-256 is identical:
     `9bdc40b56db8cbdae2805d190ba1d24f36b49dbeb2c091d7e7dc16bb9387db42`.
   - Provider statistics are also byte-identical: 7,049 evaluations, zero
     clamp hits, and zero denominator-guard hits.
5. **Non-default control (`imax=2`)**
   - Generated header contains `redistance (d, imax = 2, ...)`.
   - Canonical physical-column SHA-256 is
     `2134453015f12be91625e998c37596454f341b4a3f256a2e90fe68d73b9b62bc`.
   - Final values differ from default (`volume drift 0.000192332`, center
     `1.07587`, velocity `0.193567`), confirming the parameter affects the
     solve. This is a smoke diagnostic, not a scientific conclusion.

## Cleanup

The four new smoke result directories and their four compile work directories
were deleted after recording this report. Historical accepted evidence was not
modified.
