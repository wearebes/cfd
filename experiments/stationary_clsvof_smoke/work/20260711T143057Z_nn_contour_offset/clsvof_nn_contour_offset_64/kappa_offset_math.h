#ifndef CLSVOF_KAPPA_OFFSET_MATH_H
#define CLSVOF_KAPPA_OFFSET_MATH_H

#include <math.h>

#ifndef KAPPA_OFFSET_DENOMINATOR_GUARD
#define KAPPA_OFFSET_DENOMINATOR_GUARD 0.25
#endif

static inline double kappa_offset_safe_denominator (double denominator, int * hit)
{
  if (fabs (denominator) >= KAPPA_OFFSET_DENOMINATOR_GUARD)
    return denominator;
  if (hit)
    *hit = 1;
  return copysign (KAPPA_OFFSET_DENOMINATOR_GUARD,
                   denominator == 0. ? 1. : denominator);
}

/* Convert the zero-level-set prediction to the curvature of the level set
 * through the current solver cell.  This is the only NN deployment map. */
static inline double kappa_offset_q_cell (double q_gamma, double d_over_h,
                                          int * guard_hit, double * denominator)
{
  double raw = 1. + d_over_h*q_gamma;
  if (denominator)
    *denominator = raw;
  return q_gamma/kappa_offset_safe_denominator (raw, guard_hit);
}

/* This inverse is retained solely for formula round-trip tests; it is never
 * a solver inference path. */
static inline double kappa_offset_q_gamma (double q_d, double d_over_h,
                                           int * guard_hit, double * denominator)
{
  double raw = 1. - d_over_h*q_d;
  if (denominator)
    *denominator = raw;
  return q_d/kappa_offset_safe_denominator (raw, guard_hit);
}

#endif
