# Figure contract: CLSVOF redistance imax formal matrix

Backend: Python/matplotlib only (the repository's existing plotting workflow).

## Submission contract

- Core conclusion: redistance iterations improve signed-distance quality, while
  the physically optimal iteration count and cost trade-off must be established
  independently for capwave and rising bubble.
- Figure archetype: quantitative grid with a physical-error hero figure and
  supporting heatmap/time-history/shape figures.
- Target output: double-column research figure bundle, 180 mm final width.
- Panel map: physical error trends; physical/SDF/runtime heatmaps; SDF versus
  physical error; selected N512 histories; rising N512 final shapes.
- Evidence hierarchy: audited physical-reference errors are primary; E-grad and
  runtime are validation/trade-off evidence; `imax=3`, native/NN pairing, and
  all four resolutions are controls/robustness evidence.
- Statistics: deterministic benchmark histories, no replicate error bars;
  metric definitions and complete `n=4` resolution coverage are stated in the
  source tables and captions.
- Source data: `metrics_wide.csv`, delta/trade-off/relationship tables,
  capwave/rising time-series tables, raw rising facet logs, Prosperetti and
  MooNMD references.
- Image integrity: no microscopy or raster manipulation; plots are generated
  directly from numeric source data, with 600-dpi PNG previews and editable
  SVG/PDF masters.
- Reviewer risk: avoid conflating lower E-grad with better physics; state the
  rising `N` to rectangular-grid mapping; show failures/clamps rather than
  filtering them; preserve `imax=3` as a reference rather than ground truth.

## Core conclusion to test

Increasing `imax` is expected to improve signed-distance quality monotonically,
but physical benchmark accuracy may reach a minimum or plateau at a moderate
iteration count. The figure must establish whether the stock `imax=3` is a
robust accuracy/cost compromise across benchmark, method, and resolution rather
than assuming that lower E-grad automatically means better physics.

This is a hypothesis until all 96 rows pass the formal audit. Titles and
captions must be rewritten from the measured final result, not from this prior.

## Evidence chain and panel map

Archetype: quantitative grid with one hero tradeoff panel.

1. Hero panel: physical benchmark error versus `imax`, faceted by benchmark and
   method, with resolution encoded consistently. Capwave uses Prosperetti
   relative RMS; rising Case 1 uses MooNMD velocity-history RMSE, with center
   RMSE and shape distance as supporting metrics.
2. SDF panel: `imax x N` heatmaps of post-redistance E-grad mean and p95 in the
   1.5-Delta band. This shows whether redistance quality changes monotonically.
3. Cost panel: runtime ratio versus the matched `imax=3` row and returned-step
   distributions. This separates nominal `imax` from actual returned steps.
4. Robustness panel: physical-error delta versus `imax=3` for native and NN,
   retaining every resolution rather than averaging away sign changes.
5. Supporting time histories: capwave amplitude and rising velocity/volume for
   selected `imax=0,2,3,5` rows at N512, generated only after all selected rows
   are accepted.

## Integrity and review risks

- Do not draw or infer missing cells; plotting is blocked until `audit.json`
  passes and all 96 rows are completed.
- Rising source labels N64/128/256/512 map to physical grids 64x16, 128x32,
  256x64, and 512x128; captions must state this.
- `imax=3` is the stock default/reference, not ground truth.
- A lower E-grad is not labelled an improvement in physics unless the physical
  reference metric also improves.
- Native and matched-resolution NN use fixed method colors in every panel;
  `imax=3` receives a neutral reference marker rather than a success color.
- Clamp hits, failed rows, and non-finite values are audit failures and may not
  be silently excluded.
- Heatmaps that contain zero use a linear scale or an explicitly documented
  floor; no hidden log-scale substitution.

## Export contract

- Main composite width: 180 mm; white background; editable text in SVG/PDF.
- Deliver PNG (600 dpi), SVG, and PDF from the same Python/matplotlib script.
- Font target: 7--8 pt at final size; colorblind-safe, low-saturation palette;
  no top/right spines; shared legends only where direct labels are impractical.
- Every plotted value must trace to `metrics_wide.csv`,
  `delta_vs_imax3.csv`, `paired_native_nn_deltas.csv`,
  `tradeoff_by_identity.csv`, `sdf_physics_relationship.csv`,
  `capwave_timeseries.csv`, or `rising_timeseries.csv` under the immutable
  matrix result directory.
- A source-data CSV is retained beside each figure, and final raster/vector
  outputs receive visual QA before delivery.
