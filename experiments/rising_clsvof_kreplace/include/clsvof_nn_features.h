#ifndef CLSVOF_NN_FEATURES_H
#define CLSVOF_NN_FEATURES_H

#include <math.h>

static inline void clsvof_build_raw27 (Point point, scalar d, float raw[27])
{
  int p = 0;
  for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++)
      raw[p++] = (float) (d[i,j]/Delta);

  for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++) {
      double gx = (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double gn = sqrt (sq(gx) + sq(gy)) + 1e-30;
      raw[p++] = (float) (gx/gn);
    }

  /* The training pipeline's y-normal convention is the negative of the
   * plain centered-difference gy/gn used above (verified 2026-07-09 via
   * the Task 7 Step 0 t=0 spot check: un-negated gy/gn gave only 48%
   * sign agreement with distance_curvature on the initial circle,
   * strongly correlated with the y-component of the normal, vs 100%
   * agreement with this negation -- see
   * experiments/rising_clsvof_kreplace/debug/). Likely a row-vs-Cartesian
   * y-axis mismatch in the offline feature/label generation this model
   * was trained on. */
  for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++) {
      double gx = (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double gn = sqrt (sq(gx) + sq(gy)) + 1e-30;
      raw[p++] = (float) (-gy/gn);
    }
}

#endif
