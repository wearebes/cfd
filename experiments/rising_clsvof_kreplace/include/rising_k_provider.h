#ifndef RISING_K_PROVIDER_H
#define RISING_K_PROVIDER_H

#ifndef RISING_K_NATIVE
#define RISING_K_NATIVE 0
#endif

#ifndef RISING_K_NN_RAW
#define RISING_K_NN_RAW 1
#endif

#ifndef RISING_K_NATIVE_PERTURBED
#define RISING_K_NATIVE_PERTURBED 2
#endif

#ifndef RISING_K_MODE
#define RISING_K_MODE RISING_K_NATIVE
#endif

#ifndef RISING_K_CLAMP_FACTOR
#define RISING_K_CLAMP_FACTOR 1.0
#endif

/* Basilisk's qcc resolves #include lines by scanning source text, not by
 * evaluating #if — even an unreachable branch fails to compile if the
 * included file cannot be found. So callers must always pass -I flags for
 * nn_weights.h/clsvof_mlp_infer.h, even when RISING_K_MODE never selects
 * the NN branch at runtime. See experiments/rising_clsvof_kreplace/README.md. */
#if RISING_K_MODE == RISING_K_NN_RAW
#include "nn_weights.h"
#include "clsvof_mlp_infer.h"
#include "clsvof_nn_features.h"
#endif

static inline double rising_k_provider (Point point, scalar d)
{
#if RISING_K_MODE == RISING_K_NATIVE
  return distance_curvature (point, d);
#elif RISING_K_MODE == RISING_K_NATIVE_PERTURBED
  return distance_curvature (point, d) * (1. + 1e-3);
#elif RISING_K_MODE == RISING_K_NN_RAW
  float raw[CLSVOF_NN_INPUT_DIM];
  clsvof_build_raw27 (point, d, raw);
  double kappa = (double) clsvof_nn_predict_hkappa (raw)/Delta;
  double limit = RISING_K_CLAMP_FACTOR/Delta;
  if (kappa > limit)
    kappa = limit;
  else if (kappa < -limit)
    kappa = -limit;
  return kappa;
#else
#error "Unsupported RISING_K_MODE"
#endif
}

#endif
