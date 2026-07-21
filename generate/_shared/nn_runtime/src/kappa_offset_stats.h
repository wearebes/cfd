#ifndef KAPPA_OFFSET_STATS_H
#define KAPPA_OFFSET_STATS_H

#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#ifdef _OPENMP
# include <omp.h>
#endif

#ifndef KAPPA_OFFSET_MAX_THREADS
# define KAPPA_OFFSET_MAX_THREADS 1024
#endif

typedef struct {
  unsigned long long evaluations;
  unsigned long long clamp_hits;
  unsigned long long guard_hits;
  double min_abs_denom;
  double max_abs_s;
  unsigned long long grad_n;
  double grad_sum;
  double grad_sum_sq;
  double grad_min;
  double grad_max;
  /* Keep adjacent thread slots on separate cache lines on common x86 hosts. */
  double cacheline_padding[6];
} kappa_offset_stats_record;

static kappa_offset_stats_record
  kappa_offset_stats_slots[KAPPA_OFFSET_MAX_THREADS];
static kappa_offset_stats_record kappa_offset_stats_total;

static inline void kappa_offset_stats_clear_record
  (kappa_offset_stats_record * record)
{
  record->evaluations = 0;
  record->clamp_hits = 0;
  record->guard_hits = 0;
  record->min_abs_denom = DBL_MAX;
  record->max_abs_s = 0.;
  record->grad_n = 0;
  record->grad_sum = 0.;
  record->grad_sum_sq = 0.;
  record->grad_min = DBL_MAX;
  record->grad_max = -DBL_MAX;
}

static inline void kappa_offset_stats_reset (void)
{
  for (int thread = 0; thread < KAPPA_OFFSET_MAX_THREADS; thread++)
    kappa_offset_stats_clear_record (&kappa_offset_stats_slots[thread]);
}

static inline int kappa_offset_stats_thread_index (void)
{
  int thread = 0;
#ifdef _OPENMP
  thread = omp_get_thread_num();
#endif
  if (thread < 0 || thread >= KAPPA_OFFSET_MAX_THREADS)
    abort();
  return thread;
}

static inline void kappa_offset_stats_record_sample
  (int guard, double denominator, double s, double grad, int clamped)
{
  kappa_offset_stats_record * record =
    &kappa_offset_stats_slots[kappa_offset_stats_thread_index()];
  record->evaluations++;
  record->guard_hits += (unsigned long long) guard;
  record->clamp_hits += (unsigned long long) clamped;
  record->min_abs_denom = fmin (record->min_abs_denom, fabs (denominator));
  record->max_abs_s = fmax (record->max_abs_s, fabs (s));
  record->grad_n++;
  record->grad_sum += grad;
  record->grad_sum_sq += grad*grad;
  record->grad_min = fmin (record->grad_min, grad);
  record->grad_max = fmax (record->grad_max, grad);
}

static inline kappa_offset_stats_record kappa_offset_stats_merge (void)
{
  kappa_offset_stats_record merged;
  kappa_offset_stats_clear_record (&merged);
  for (int thread = 0; thread < KAPPA_OFFSET_MAX_THREADS; thread++) {
    const kappa_offset_stats_record * record =
      &kappa_offset_stats_slots[thread];
    merged.evaluations += record->evaluations;
    merged.clamp_hits += record->clamp_hits;
    merged.guard_hits += record->guard_hits;
    merged.min_abs_denom = fmin (merged.min_abs_denom,
                                  record->min_abs_denom);
    merged.max_abs_s = fmax (merged.max_abs_s, record->max_abs_s);
    merged.grad_n += record->grad_n;
    merged.grad_sum += record->grad_sum;
    merged.grad_sum_sq += record->grad_sum_sq;
    merged.grad_min = fmin (merged.grad_min, record->grad_min);
    merged.grad_max = fmax (merged.grad_max, record->grad_max);
  }
  return merged;
}

static inline void kappa_offset_stats_print (FILE * stream)
{
  kappa_offset_stats_total = kappa_offset_stats_merge ();
  double mean = kappa_offset_stats_total.grad_n ?
    kappa_offset_stats_total.grad_sum/kappa_offset_stats_total.grad_n : NAN;
  double variance = kappa_offset_stats_total.grad_n ?
    fmax (0., kappa_offset_stats_total.grad_sum_sq/
          kappa_offset_stats_total.grad_n - mean*mean) : NAN;
  fprintf (stream,
           "kappa_offset_provider_stats evaluations=%llu clamp_hits=%llu denominator_guard_hits=%llu min_abs_denominator=%.17g max_abs_d_over_h=%.17g grad_samples=%llu grad_min=%.17g grad_mean=%.17g grad_std=%.17g grad_max=%.17g\n",
           kappa_offset_stats_total.evaluations,
           kappa_offset_stats_total.clamp_hits,
           kappa_offset_stats_total.guard_hits,
           kappa_offset_stats_total.min_abs_denom,
           kappa_offset_stats_total.max_abs_s,
           kappa_offset_stats_total.grad_n,
           kappa_offset_stats_total.grad_min, mean, sqrt (variance),
           kappa_offset_stats_total.grad_max);
}

#endif
