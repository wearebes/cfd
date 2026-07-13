#ifndef CLSVOF_NN_CELL_CURVATURE_H
#define CLSVOF_NN_CELL_CURVATURE_H

#include <float.h>
#include <math.h>
#include <stdio.h>

#ifndef KAPPA_OFFSET_DENOMINATOR_GUARD
#define KAPPA_OFFSET_DENOMINATOR_GUARD 0.25
#endif
#ifndef KAPPA_OFFSET_CLAMP_FACTOR
#define KAPPA_OFFSET_CLAMP_FACTOR 1.0
#endif
#ifndef KAPPA_OFFSET_PROBE_INTERVAL
#define KAPPA_OFFSET_PROBE_INTERVAL 0.0
#endif

static inline double kappa_offset_safe_denominator (double denominator,
                                                     int * hit)
{
  if (fabs (denominator) >= KAPPA_OFFSET_DENOMINATOR_GUARD)
    return denominator;
  if (hit)
    *hit = 1;
  return copysign (KAPPA_OFFSET_DENOMINATOR_GUARD,
                   denominator == 0. ? 1. : denominator);
}

static inline double kappa_offset_q_cell (double q_gamma, double d_over_h,
                                          int * guard_hit,
                                          double * denominator)
{
  double raw = 1. + d_over_h*q_gamma;
  if (denominator)
    *denominator = raw;
  return q_gamma/kappa_offset_safe_denominator (raw, guard_hit);
}

/* Test-only inverse; never used for solver inference. */
static inline double kappa_offset_q_gamma (double q_cell, double d_over_h,
                                           int * guard_hit,
                                           double * denominator)
{
  double raw = 1. - d_over_h*q_cell;
  if (denominator)
    *denominator = raw;
  return q_cell/kappa_offset_safe_denominator (raw, guard_hit);
}

/* Array form used by the training/C golden-vector gate. patch[row][column]
 * follows the training array convention; the central solver cell is [2][2]. */
static inline void clsvof_nn_cell_build_raw27_from_patch5 (
  const double patch[5][5], double delta, float raw[27])
{
  int p = 0;
  for (int row = 3; row >= 1; row--)
    for (int column = 1; column <= 3; column++)
      raw[p++] = (float) (patch[row][column]/delta);
  for (int row = 3; row >= 1; row--)
    for (int column = 1; column <= 3; column++) {
      double gx = (patch[row][column + 1] - patch[row][column - 1])/(2.*delta);
      double gy = (patch[row + 1][column] - patch[row - 1][column])/(2.*delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gx/norm);
    }
  for (int row = 3; row >= 1; row--)
    for (int column = 1; column <= 3; column++) {
      double gx = (patch[row][column + 1] - patch[row][column - 1])/(2.*delta);
      double gy = (patch[row + 1][column] - patch[row - 1][column])/(2.*delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gy/norm);
    }
}

#ifndef CLSVOF_NN_CELL_ARRAY_ONLY

#include "nn_weights.h"
#include "clsvof_mlp_infer.h"

static inline void kappa_offset_build_raw27 (Point point, scalar d,
                                              float raw[27])
{
  int p = 0;
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++)
      raw[p++] = (float) (d[i,j]/Delta);
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++) {
      double gx = (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gx/norm);
    }
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++) {
      double gx = (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gy/norm);
    }
}

static inline double kappa_offset_grad_norm (Point point, scalar d)
{
  double gx = (d[1] - d[-1])/(2.*Delta);
  double gy = (d[0,1] - d[0,-1])/(2.*Delta);
  return sqrt (gx*gx + gy*gy);
}

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
  kappa_offset_evaluations = kappa_offset_clamp_hits = kappa_offset_guard_hits = 0;
  kappa_offset_min_abs_denom = DBL_MAX;
  kappa_offset_max_abs_s = 0.;
  kappa_offset_grad_n = 0;
  kappa_offset_grad_sum = kappa_offset_grad_sum_sq = 0.;
  kappa_offset_grad_min = DBL_MAX;
  kappa_offset_grad_max = -DBL_MAX;
  kappa_offset_next_probe_time = 0.;
  kappa_offset_active_probe_time = -DBL_MAX;
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
  kappa_offset_min_abs_denom = fmin (kappa_offset_min_abs_denom,
                                     fabs (denominator));
  kappa_offset_max_abs_s = fmax (kappa_offset_max_abs_s, fabs (s));
  kappa_offset_grad_n++;
  kappa_offset_grad_sum += grad;
  kappa_offset_grad_sum_sq += grad*grad;
  kappa_offset_grad_min = fmin (kappa_offset_grad_min, grad);
  kappa_offset_grad_max = fmax (kappa_offset_grad_max, grad);
  if (q_cell > KAPPA_OFFSET_CLAMP_FACTOR) {
    q_cell = KAPPA_OFFSET_CLAMP_FACTOR;
    clamped = 1;
  }
  else if (q_cell < -KAPPA_OFFSET_CLAMP_FACTOR) {
    q_cell = -KAPPA_OFFSET_CLAMP_FACTOR;
    clamped = 1;
  }
  kappa_offset_clamp_hits += (unsigned long long) clamped;
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
           kappa_offset_evaluations, kappa_offset_clamp_hits,
           kappa_offset_guard_hits, kappa_offset_min_abs_denom,
           kappa_offset_max_abs_s, kappa_offset_grad_n,
           kappa_offset_grad_min, mean, sqrt (variance), kappa_offset_grad_max);
}

#endif
#endif
