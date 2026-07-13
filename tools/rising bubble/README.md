# Rising-bubble plotting tool

Regenerates rising-bubble figures from `dataset/official_data/rising_bubble`.

The plotted metrics, axis labels, ranges, legend positions, reference curves,
and line semantics follow the gnuplot blocks embedded in Basilisk's official
`test/rising.c`. The colors and line styles are intentionally changed.

Run from the repository root:

```bash
"tools/rising bubble/plot_rising_bubble.sh"
```

Outputs:

- `dataset/official_data/rising_bubble/figures/author_style/rising_case1_shape.svg`
- `dataset/official_data/rising_bubble/figures/author_style/rising_case2_shape.svg`
- `dataset/official_data/rising_bubble/figures/author_style/rising_case1_velocity.svg`
- `dataset/official_data/rising_bubble/figures/author_style/rising_case1_volume.svg`
- `dataset/official_data/rising_bubble/figures/author_style/rising_case2_velocity.svg`
- `dataset/official_data/rising_bubble/figures/author_style/rising_case2_volume.svg`
