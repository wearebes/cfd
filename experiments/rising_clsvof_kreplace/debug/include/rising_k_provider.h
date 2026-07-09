#ifndef RISING_K_PROVIDER_T0_DEBUG_H
#define RISING_K_PROVIDER_T0_DEBUG_H

/* Task 7 Step 0 instrumentation only. Not used by the canary: always
 * returns the native curvature (safe physics for the whole run) but at
 * the very first acceleration call (t == 0, the only point in this file
 * where the analytic curvature is known a priori) also computes the NN
 * curvature and prints both for comparison. `i` (iteration count) is not
 * a real global in Basilisk-generated code -- it is only meaningful
 * inside an event body -- so t == 0 is used instead to identify the
 * first call; t is a true global and this is the only i at which t is
 * exactly 0.0. */

#include <stdio.h>
#include "nn_weights.h"
#include "clsvof_mlp_infer.h"
#include "clsvof_nn_features.h"

#ifndef RISING_K_CLAMP_FACTOR
#define RISING_K_CLAMP_FACTOR 1.0
#endif

static inline double rising_k_provider (Point point, scalar d)
{
  double ki_native = distance_curvature (point, d);
  if (t == 0.0) {
    float raw[CLSVOF_NN_INPUT_DIM];
    clsvof_build_raw27 (point, d, raw);
    double kappa_nn = (double) clsvof_nn_predict_hkappa (raw)/Delta;
    double limit = RISING_K_CLAMP_FACTOR/Delta;
    int clamped = 0;
    if (kappa_nn > limit) { kappa_nn = limit; clamped = 1; }
    else if (kappa_nn < -limit) { kappa_nn = -limit; clamped = 1; }
    fprintf (stderr, "T0SPOT %.17g %.17g %.17g %.17g %d\n",
	     x, y, ki_native, kappa_nn, clamped);
  }
  return ki_native;
}

#endif
