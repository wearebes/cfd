#ifndef CLSVOF_KAPPA_OFFSET_PROVIDER_H
#define CLSVOF_KAPPA_OFFSET_PROVIDER_H

#include <float.h>
#include <math.h>
#include <stdio.h>

#include "kappa_offset_math.h"

#ifndef KAPPA_OFFSET_CLAMP_FACTOR
#define KAPPA_OFFSET_CLAMP_FACTOR 1.0
#endif
#ifndef KAPPA_OFFSET_PROBE_INTERVAL
#define KAPPA_OFFSET_PROBE_INTERVAL 0.0
#endif

/* qcc sees textual includes before evaluating #if, hence every run receives
 * model include paths even when this branch is not executed. */
#include "kappa_offset_features.h"
#include "nn_weights.h"
#include "clsvof_mlp_infer.h"

static unsigned long long kappa_offset_evaluations = 0;
static unsigned long long kappa_offset_clamp_hits = 0;
static unsigned long long kappa_offset_guard_hits = 0;
static double kappa_offset_min_abs_denom = DBL_MAX;
static double kappa_offset_max_abs_s = 0.;
static unsigned long long kappa_offset_grad_n = 0;
static double kappa_offset_grad_sum = 0., kappa_offset_grad_sum_sq = 0.;
static double kappa_offset_grad_min = DBL_MAX, kappa_offset_grad_max = -DBL_MAX;
static double kappa_offset_next_probe_time = 0.;
static double kappa_offset_active_probe_time = -DBL_MAX;

static inline void kappa_offset_reset_stats (void)
{
  kappa_offset_evaluations = 0;
  kappa_offset_clamp_hits = 0;
  kappa_offset_guard_hits = 0;
  kappa_offset_min_abs_denom = DBL_MAX;
  kappa_offset_max_abs_s = 0.;
  kappa_offset_grad_n = 0;
  kappa_offset_grad_sum = kappa_offset_grad_sum_sq = 0.;
  kappa_offset_grad_min = DBL_MAX;
  kappa_offset_grad_max = -DBL_MAX;
  kappa_offset_next_probe_time = 0.;
  kappa_offset_active_probe_time = -DBL_MAX;
}

static inline void kappa_offset_observe (double s, double grad,
                                         double denominator)
{
  kappa_offset_min_abs_denom = fmin (kappa_offset_min_abs_denom,
                                      fabs (denominator));
  kappa_offset_max_abs_s = fmax (kappa_offset_max_abs_s, fabs (s));
  kappa_offset_grad_n++;
  kappa_offset_grad_sum += grad;
  kappa_offset_grad_sum_sq += grad*grad;
  kappa_offset_grad_min = fmin (kappa_offset_grad_min, grad);
  kappa_offset_grad_max = fmax (kappa_offset_grad_max, grad);
}

static inline int kappa_offset_probe_now (void)
{
  if (KAPPA_OFFSET_PROBE_INTERVAL <= 0.)
    return 0;
  double eps = 128.*DBL_EPSILON*fmax (1., fabs (t));
  if (t + eps >= kappa_offset_next_probe_time) {
    while (t + eps >= kappa_offset_next_probe_time)
      kappa_offset_next_probe_time += KAPPA_OFFSET_PROBE_INTERVAL;
    kappa_offset_active_probe_time = t;
  }
  return fabs (t - kappa_offset_active_probe_time) <= eps;
}

static inline double kappa_offset_clamp (double q, int * hit)
{
  if (q > KAPPA_OFFSET_CLAMP_FACTOR) {
    kappa_offset_clamp_hits++;
    if (hit) *hit = 1;
    return KAPPA_OFFSET_CLAMP_FACTOR;
  }
  if (q < -KAPPA_OFFSET_CLAMP_FACTOR) {
    kappa_offset_clamp_hits++;
    if (hit) *hit = 1;
    return -KAPPA_OFFSET_CLAMP_FACTOR;
  }
  return q;
}

static inline double kappa_offset_provider (Point point, scalar d)
{
  kappa_offset_evaluations++;
  float raw[CLSVOF_NN_INPUT_DIM];
  kappa_offset_build_raw27 (point, d, raw);
  double q_gamma = (double) clsvof_nn_predict_hkappa (raw);
  double s = d[]/Delta;
  double grad = kappa_offset_grad_norm (point, d);
  int guard = 0, clamped = 0;
  double denominator = 1.;
  double q_cell = kappa_offset_q_cell (q_gamma, s, &guard, &denominator);
  kappa_offset_guard_hits += (unsigned long long) guard;
  kappa_offset_observe (s, grad, denominator);
  q_cell = kappa_offset_clamp (q_cell, &clamped);
  if (kappa_offset_probe_now ())
    fprintf (stderr,
             "KAPPA_OFFSET_PROBE %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %d %d\n",
             t, x, y, s, grad, q_gamma, q_cell,
             distance_curvature (point, d)*Delta, denominator, clamped, guard);
  return q_cell/Delta;
}

event kappa_offset_provider_reset (t = 0)
  kappa_offset_reset_stats ();

event kappa_offset_provider_stats (t = end)
{
  double mean = kappa_offset_grad_n ? kappa_offset_grad_sum/kappa_offset_grad_n : NAN;
  double variance = kappa_offset_grad_n ?
    fmax (0., kappa_offset_grad_sum_sq/kappa_offset_grad_n - mean*mean) : NAN;
  fprintf (stderr,
           "kappa_offset_provider_stats evaluations=%llu clamp_hits=%llu denominator_guard_hits=%llu min_abs_denominator=%.17g max_abs_d_over_h=%.17g grad_samples=%llu grad_min=%.17g grad_mean=%.17g grad_std=%.17g grad_max=%.17g\n",
           kappa_offset_evaluations, kappa_offset_clamp_hits, kappa_offset_guard_hits,
           kappa_offset_min_abs_denom, kappa_offset_max_abs_s, kappa_offset_grad_n,
           kappa_offset_grad_min, mean, sqrt (variance), kappa_offset_grad_max);
}

#endif
