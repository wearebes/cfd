# Rising-bubble plotting tool

Regenerates rising-bubble figures from `dataset/rising_bubble`.

The plotted metrics, axis labels, ranges, legend positions, reference curves,
and line semantics follow the gnuplot blocks embedded in Basilisk's official
`test/rising.c`. The colors and line styles are intentionally changed.

Run from the repository root:

```bash
"tools/rising bubble/plot_rising_bubble.sh"
```

Outputs:

- `figures/rising_bubble/official_reproduction/rising_case1_shape.svg`
- `figures/rising_bubble/official_reproduction/rising_case2_shape.svg`
- `figures/rising_bubble/official_reproduction/rising_case1_velocity.svg`
- `figures/rising_bubble/official_reproduction/rising_case1_volume.svg`
- `figures/rising_bubble/official_reproduction/rising_case2_velocity.svg`
- `figures/rising_bubble/official_reproduction/rising_case2_volume.svg`
