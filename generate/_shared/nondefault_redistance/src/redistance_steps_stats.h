#ifndef REDISTANCE_STEPS_STATS_H
#define REDISTANCE_STEPS_STATS_H

#include <limits.h>
#include <stdio.h>

#ifndef REDISTANCE_FIXED_STEPS
# error "REDISTANCE_FIXED_STEPS must be defined before this header"
#endif

static unsigned long long redistance_fixed_steps_calls;
static unsigned long long redistance_fixed_steps_mismatch_count;
static unsigned long long redistance_fixed_steps_total_iterations;
static int redistance_fixed_steps_min_iterations = INT_MAX;
static int redistance_fixed_steps_max_iterations = INT_MIN;

static inline void redistance_fixed_steps_record (int returned)
{
  redistance_fixed_steps_calls++;
  redistance_fixed_steps_total_iterations += (unsigned long long) returned;
  if (returned < redistance_fixed_steps_min_iterations)
    redistance_fixed_steps_min_iterations = returned;
  if (returned > redistance_fixed_steps_max_iterations)
    redistance_fixed_steps_max_iterations = returned;
  if (returned != REDISTANCE_FIXED_STEPS)
    redistance_fixed_steps_mismatch_count++;
}

event redistance_fixed_steps_stats (t = end)
{
  int minimum = redistance_fixed_steps_calls ?
    redistance_fixed_steps_min_iterations : -1;
  int maximum = redistance_fixed_steps_calls ?
    redistance_fixed_steps_max_iterations : -1;
  fprintf (stderr,
           "redistance_fixed_steps_stats requested_steps=%d redistance_calls=%llu min_iterations_per_call=%d max_iterations_per_call=%d mismatch_count=%llu total_iterations=%llu\n",
           REDISTANCE_FIXED_STEPS, redistance_fixed_steps_calls,
           minimum, maximum, redistance_fixed_steps_mismatch_count,
           redistance_fixed_steps_total_iterations);
}

#endif
