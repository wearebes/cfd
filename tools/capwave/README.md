# Capwave plotting tool

Regenerates capwave figures from `dataset/official_data/capwave`.

The plotted metrics, axis labels, ranges, log scales, reference curves, and
line/point semantics follow the gnuplot blocks embedded in Basilisk's official
`test/capwave.c`. The colors and line styles are intentionally changed.

Run from the repository root:

```bash
tools/capwave/plot_capwave.sh
```

Outputs:

- `dataset/official_data/capwave/figures/author_style/capwave_amplitude.svg`
- `dataset/official_data/capwave/figures/author_style/capwave_rms_convergence.svg`
- `dataset/official_data/capwave/figures/author_style/capwave_rms_convergence_extended.svg`

Notes:

- The official source runs `N = 16, 32, 64, 128`; because `L0 = 2`, the RMS
  convergence abscissa is `N/L0 = 8, 16, 32, 64`.
- There is no `wave-8` amplitude file. The `8` point is the first RMS point in
  `log`, from the `N = 16` run.
- The extended convergence figure uses `raw/extended_vof` and
  `raw/extended_clsvof`, which extend the same setup to `N = 256, 512`. This
  figure converts the `log` abscissa from `N/L0` back to source resolution `N`,
  so the last point is displayed at `512`.
