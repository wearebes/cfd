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
#ifndef KAPPA_OFFSET_INFERENCE_DOUBLE
#define KAPPA_OFFSET_INFERENCE_DOUBLE 0
#endif
#if KAPPA_OFFSET_INFERENCE_DOUBLE
typedef double kappa_offset_inference_real;
#else
typedef float kappa_offset_inference_real;
#endif
#ifndef KAPPA_OFFSET_MODEL_PHI_SIGN
#define KAPPA_OFFSET_MODEL_PHI_SIGN 1.0
#endif
#define KAPPA_OFFSET_TRANSFORM_CELL 1
#define KAPPA_OFFSET_TRANSFORM_INTERFACE 2
#ifndef KAPPA_OFFSET_TRANSFORM_MODE
#define KAPPA_OFFSET_TRANSFORM_MODE KAPPA_OFFSET_TRANSFORM_CELL
#endif
#if KAPPA_OFFSET_TRANSFORM_MODE != KAPPA_OFFSET_TRANSFORM_CELL && \
    KAPPA_OFFSET_TRANSFORM_MODE != KAPPA_OFFSET_TRANSFORM_INTERFACE
#error "KAPPA_OFFSET_TRANSFORM_MODE must be CELL or INTERFACE"
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

/* Select the curvature inserted into integral.h's cell-local ki slot.  The
 * cell mode maps the predicted interface curvature to the current distance
 * contour; the interface mode deliberately injects the predicted zero-contour
 * curvature unchanged. */
static inline double kappa_offset_q_provider (double q_gamma, double d_over_h,
                                              int * guard_hit,
                                              double * denominator)
{
#if KAPPA_OFFSET_TRANSFORM_MODE == KAPPA_OFFSET_TRANSFORM_CELL
  return kappa_offset_q_cell (q_gamma, d_over_h, guard_hit, denominator);
#else
  (void) d_over_h;
  if (guard_hit)
    *guard_hit = 0;
  if (denominator)
    *denominator = 1.;
  return q_gamma;
#endif
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

/* Strict phi9-only normals: C nx, C ny, L ny, R ny, T nx, B nx.
 * Tangential centered differences and first-order inward differences.
 * Canonical order is TL,T,TR,L,C,R,BL,B,BR. No second-ring reads. */
static inline void kappa_offset_local_normals (kappa_offset_inference_real * raw)
{
  double p[9];
  for (int k = 0; k < 9; k++) p[k] = raw[k];
  double gx[5] = {.5*(p[5]-p[3]), p[4]-p[3], p[5]-p[4],
                  .5*(p[2]-p[0]), .5*(p[8]-p[6])};
  double gy[5] = {.5*(p[1]-p[7]), .5*(p[0]-p[6]), .5*(p[2]-p[8]),
                  p[1]-p[4], p[4]-p[7]};
  double nx[5], ny[5];
  for (int k = 0; k < 5; k++) {
    double mag = hypot(gx[k], gy[k]);
    if (mag == 0.) mag = 1.;
    nx[k] = gx[k]/mag; ny[k] = gy[k]/mag;
  }
  raw[9] = nx[0]; raw[10] = ny[0]; raw[11] = ny[1];
  raw[12] = ny[2]; raw[13] = nx[3]; raw[14] = nx[4];
}

static inline void kappa_offset_build_raw27 (Point point, scalar d,
                                              kappa_offset_inference_real raw[CLSVOF_NN_INPUT_DIM])
{
  int p = 0;
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++)
      raw[p++] = (kappa_offset_inference_real)
        (KAPPA_OFFSET_MODEL_PHI_SIGN*d[i,j]/Delta);
#if CLSVOF_NN_INPUT_DIM == 15
  kappa_offset_local_normals(raw);
  return;
#endif
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++) {
#if CLSVOF_NN_INPUT_DIM == 9 || CLSVOF_NN_INPUT_DIM == 15
      continue;
#elif CLSVOF_NN_INPUT_DIM == 11
      if (i != 0 || j != 0) continue;
#elif CLSVOF_NN_INPUT_DIM == 19
      if (abs(i) + abs(j) > 1) continue;
#elif CLSVOF_NN_INPUT_DIM != 27
#error "Unsupported normal feature dimension"
#endif
      double gx = KAPPA_OFFSET_MODEL_PHI_SIGN*
        (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = KAPPA_OFFSET_MODEL_PHI_SIGN*
        (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (kappa_offset_inference_real) (gx/norm);
    }
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++) {
#if CLSVOF_NN_INPUT_DIM == 9 || CLSVOF_NN_INPUT_DIM == 15
      continue;
#elif CLSVOF_NN_INPUT_DIM == 11
      if (i != 0 || j != 0) continue;
#elif CLSVOF_NN_INPUT_DIM == 19
      if (abs(i) + abs(j) > 1) continue;
#elif CLSVOF_NN_INPUT_DIM != 27
#error "Unsupported normal feature dimension"
#endif
      double gx = KAPPA_OFFSET_MODEL_PHI_SIGN*
        (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = KAPPA_OFFSET_MODEL_PHI_SIGN*
        (d[i,j + 1] - d[i,j - 1])/(2.*Delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (kappa_offset_inference_real) (gy/norm);
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

static inline double kappa_offset_provider_value (Point point, scalar d,
                                                   int record_stats,
                                                   int record_probe)
{
  kappa_offset_inference_real raw[CLSVOF_NN_INPUT_DIM];
  kappa_offset_build_raw27 (point, d, raw);
  double q_gamma_model = (double) clsvof_nn_predict_hkappa (raw);
  double q_gamma_solver = KAPPA_OFFSET_MODEL_PHI_SIGN*q_gamma_model;
  double s = d[]/Delta;
  double grad = kappa_offset_grad_norm (point, d);
  int guard = 0, clamped = 0;
  double denominator = 1.;
  double q_provider = kappa_offset_q_provider (q_gamma_solver, s, &guard,
                                                &denominator);
  if (q_provider > KAPPA_OFFSET_CLAMP_FACTOR) {
    q_provider = KAPPA_OFFSET_CLAMP_FACTOR;
    clamped = 1;
  }
  else if (q_provider < -KAPPA_OFFSET_CLAMP_FACTOR) {
    q_provider = -KAPPA_OFFSET_CLAMP_FACTOR;
    clamped = 1;
  }
  if (record_stats)
    kappa_offset_stats_record_sample (guard, denominator, s, grad, clamped);
  if (record_probe && kappa_offset_probe_now ()) {
#ifdef _OPENMP
# pragma omp critical(kappa_offset_probe_output)
#endif
    {
      fprintf (stderr,
               "KAPPA_OFFSET_PROBE %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %d %d\n",
               t, x, y, s, grad, q_gamma_model, q_gamma_solver, q_provider,
               distance_curvature (point, d)*Delta, denominator, clamped, guard);
    }
  }
  if (KAPPA_OFFSET_PROBE_ONLY)
    return distance_curvature (point, d);
  return q_provider/Delta;
}

static inline double kappa_offset_provider (Point point, scalar d)
{
  return kappa_offset_provider_value (point, d, 1, 1);
}

/* Diagnostic-only evaluation of the exact active NN provider.  This must not
 * change provider counts or emit probes when milestones are sampled. */
static inline double kappa_offset_provider_diagnostic (Point point, scalar d)
{
  return kappa_offset_provider_value (point, d, 0, 0);
}

event kappa_offset_provider_reset (t = 0)
  kappa_offset_reset_stats ();

event kappa_offset_provider_stats (t = end)
  kappa_offset_stats_print (stderr);

#endif
#endif
