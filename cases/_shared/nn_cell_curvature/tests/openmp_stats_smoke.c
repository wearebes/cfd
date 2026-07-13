#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "kappa_offset_stats.h"

int main (int argc, char ** argv)
{
  int samples = argc > 1 ? atoi (argv[1]) : 100000;
  if (samples < 1)
    return 2;
  kappa_offset_stats_reset ();

#ifdef _OPENMP
# pragma omp parallel for schedule(static)
#endif
  for (int i = 0; i < samples; i++) {
    int guard = i % 17 == 0;
    int clamped = i % 23 == 0;
    double denominator = 0.25 + (i % 101)/100.;
    double s = ((i % 41) - 20)/10.;
    double grad = 0.5 + (i % 37)/20.;
    kappa_offset_stats_record_sample
      (guard, denominator, s, grad, clamped);
  }

  kappa_offset_stats_record stats = kappa_offset_stats_merge ();
  printf ("evaluations=%llu clamp_hits=%llu guard_hits=%llu "
          "min_abs_denom=%.17g max_abs_s=%.17g grad_n=%llu "
          "grad_sum=%.17g grad_sum_sq=%.17g grad_min=%.17g grad_max=%.17g\n",
          stats.evaluations, stats.clamp_hits, stats.guard_hits,
          stats.min_abs_denom, stats.max_abs_s, stats.grad_n,
          stats.grad_sum, stats.grad_sum_sq, stats.grad_min, stats.grad_max);
  return stats.evaluations == (unsigned long long) samples ? 0 : 1;
}
