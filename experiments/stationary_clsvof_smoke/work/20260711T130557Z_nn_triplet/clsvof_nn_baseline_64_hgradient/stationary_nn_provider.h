#ifndef STATIONARY_NN_PROVIDER_H
#define STATIONARY_NN_PROVIDER_H
#include <stdio.h>
#include "nn_weights.h"
#include "clsvof_mlp_infer.h"
#include "stationary_nn_features.h"
static unsigned long long stationary_nn_evaluations = 0, stationary_nn_clamp_hits = 0;
static double stationary_nn_min = HUGE, stationary_nn_max = -HUGE;
static inline double stationary_nn_curvature (Point point, scalar d) {
  float raw[27]; stationary_build_raw27(point,d,raw); double k=(double)clsvof_nn_predict_hkappa(raw)/Delta, limit=1./Delta;
  stationary_nn_evaluations++; if(k>limit){k=limit;stationary_nn_clamp_hits++;} if(k < -limit){k=-limit;stationary_nn_clamp_hits++;}
  if(k<stationary_nn_min)stationary_nn_min=k; if(k>stationary_nn_max)stationary_nn_max=k; return k;
}
static inline void stationary_nn_stats(FILE *fp) { fprintf(fp,"stationary_nn_stats evaluations=%llu clamp_hits=%llu kappa_min=%g kappa_max=%g\n",stationary_nn_evaluations,stationary_nn_clamp_hits,stationary_nn_min,stationary_nn_max); }
#endif
