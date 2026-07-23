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
#ifndef KAPPA_OFFSET_MODEL_PHI_SIGN
#define KAPPA_OFFSET_MODEL_PHI_SIGN 1.0
#endif
#ifndef KAPPA_OFFSET_PROBE_ONLY
#define KAPPA_OFFSET_PROBE_ONLY 0
#endif
#ifndef KAPPA_OFFSET_INITIAL_PROBE_SAMPLES
#define KAPPA_OFFSET_INITIAL_PROBE_SAMPLES 0
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
static inline void clsvof_nn_cell_build_raw27_signed_from_patch5 (
  const double patch[5][5], double delta, double model_phi_sign,
  float raw[27])
{
  int p = 0;
  for (int row = 3; row >= 1; row--)
    for (int column = 1; column <= 3; column++)
      raw[p++] = (float) (model_phi_sign*patch[row][column]/delta);
  for (int row = 3; row >= 1; row--)
    for (int column = 1; column <= 3; column++) {
      double gx = model_phi_sign*
        (patch[row][column + 1] - patch[row][column - 1])/(2.*delta);
      double gy = model_phi_sign*
        (patch[row + 1][column] - patch[row - 1][column])/(2.*delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gx/norm);
    }
  for (int row = 3; row >= 1; row--)
    for (int column = 1; column <= 3; column++) {
      double gx = model_phi_sign*
        (patch[row][column + 1] - patch[row][column - 1])/(2.*delta);
      double gy = model_phi_sign*
        (patch[row + 1][column] - patch[row - 1][column])/(2.*delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gy/norm);
    }
}

static inline void clsvof_nn_cell_build_raw27_from_patch5 (
  const double patch[5][5], double delta, float raw[27])
{
  clsvof_nn_cell_build_raw27_signed_from_patch5 (patch, delta, 1., raw);
}

#ifndef CLSVOF_NN_CELL_ARRAY_ONLY

#include "nn_weights.h"
#include "clsvof_mlp_infer.h"
#include "kappa_offset_stats.h"

static inline void kappa_offset_build_raw27 (Point point, scalar d,
                                              float raw[27])
{
  int p = 0;
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++)
      raw[p++] = (float) (KAPPA_OFFSET_MODEL_PHI_SIGN*d[i,j]/Delta);
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++) {
      double gx = KAPPA_OFFSET_MODEL_PHI_SIGN*
        (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = KAPPA_OFFSET_MODEL_PHI_SIGN*
        (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gx/norm);
    }
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++) {
      double gx = KAPPA_OFFSET_MODEL_PHI_SIGN*
        (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = KAPPA_OFFSET_MODEL_PHI_SIGN*
        (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
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

static double kappa_offset_next_probe_time = 0.;
static double kappa_offset_active_probe_time = -DBL_MAX;
static unsigned long long kappa_offset_initial_probe_samples = 0;

static inline void kappa_offset_reset_stats (void)
{
  kappa_offset_stats_reset ();
  kappa_offset_next_probe_time = 0.;
  kappa_offset_active_probe_time = -DBL_MAX;
  kappa_offset_initial_probe_samples = 0;
}

static inline int kappa_offset_probe_now (void)
{
#if KAPPA_OFFSET_INITIAL_PROBE_SAMPLES > 0
  int probe = 0;
# ifdef _OPENMP
#  pragma omp critical(kappa_offset_probe_state)
# endif
  {
    probe = kappa_offset_initial_probe_samples <
      KAPPA_OFFSET_INITIAL_PROBE_SAMPLES;
    kappa_offset_initial_probe_samples++;
  }
  return probe;
#else
  if (KAPPA_OFFSET_PROBE_INTERVAL <= 0.)
    return 0;
  int probe = 0;
#ifdef _OPENMP
# pragma omp critical(kappa_offset_probe_state)
#endif
  {
    double eps = 128.*DBL_EPSILON*fmax (1., fabs (t));
    if (t + eps >= kappa_offset_next_probe_time) {
      while (t + eps >= kappa_offset_next_probe_time)
        kappa_offset_next_probe_time += KAPPA_OFFSET_PROBE_INTERVAL;
      kappa_offset_active_probe_time = t;
    }
    probe = fabs (t - kappa_offset_active_probe_time) <= eps;
  }
  return probe;
#endif
}

static inline double kappa_offset_provider (Point point, scalar d)
{
  float raw[CLSVOF_NN_INPUT_DIM];
  kappa_offset_build_raw27 (point, d, raw);
  double q_gamma_model = (double) clsvof_nn_predict_hkappa (raw);
  double q_gamma_solver = KAPPA_OFFSET_MODEL_PHI_SIGN*q_gamma_model;
  double s = d[]/Delta;
  double grad = kappa_offset_grad_norm (point, d);
  int guard = 0, clamped = 0;
  double denominator = 1.;
  double q_cell = kappa_offset_q_cell (q_gamma_solver, s, &guard, &denominator);
  if (q_cell > KAPPA_OFFSET_CLAMP_FACTOR) {
    q_cell = KAPPA_OFFSET_CLAMP_FACTOR;
    clamped = 1;
  }
  else if (q_cell < -KAPPA_OFFSET_CLAMP_FACTOR) {
    q_cell = -KAPPA_OFFSET_CLAMP_FACTOR;
    clamped = 1;
  }
  kappa_offset_stats_record_sample (guard, denominator, s, grad, clamped);
  if (kappa_offset_probe_now ()) {
#ifdef _OPENMP
# pragma omp critical(kappa_offset_probe_output)
#endif
    {
      fprintf (stderr,
               "KAPPA_OFFSET_PROBE %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %d %d\n",
               t, x, y, s, grad, q_gamma_model, q_gamma_solver, q_cell,
               distance_curvature (point, d)*Delta, denominator, clamped, guard);
    }
  }
  if (KAPPA_OFFSET_PROBE_ONLY)
    return distance_curvature (point, d);
  return q_cell/Delta;
}

event kappa_offset_provider_reset (t = 0)
  kappa_offset_reset_stats ();

event kappa_offset_provider_stats (t = end)
  kappa_offset_stats_print (stderr);

#endif
#endif
