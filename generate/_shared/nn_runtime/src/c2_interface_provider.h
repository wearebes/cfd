#ifndef CLSVOF_NN_INTERFACE_C2_H
#define CLSVOF_NN_INTERFACE_C2_H

#include <math.h>

static inline int nn_interface_c2_endpoint_needed (double d0, double d1)
{
  return d0*(d0 + d1) < 0. || d1*(d1 + d0) < 0.;
}

static inline double nn_interface_c2_interpolate_value
  (double kappa0, double kappa1, double xi,
   int ready0, int ready1, int * missing_endpoint)
{
  if (!ready0 || !ready1) {
    if (missing_endpoint)
      (*missing_endpoint)++;
    return NAN;
  }
  return (1. - xi)*kappa0 + xi*kappa1;
}

#ifndef CLSVOF_NN_INTERFACE_C2_ARRAY_ONLY

#include <stdio.h>
#include <stdlib.h>

static unsigned long long
  nn_interface_c2_crossings[KAPPA_OFFSET_MAX_THREADS],
  nn_interface_c2_endpoint_predictions[KAPPA_OFFSET_MAX_THREADS],
  nn_interface_c2_missing_endpoint[KAPPA_OFFSET_MAX_THREADS];

static inline double nn_interface_c2_predict_endpoint (Point point, scalar d)
{
  nn_interface_c2_endpoint_predictions[kappa_offset_stats_thread_index()]++;
  /* INTERFACE mode returns q_gamma/Delta without q_gamma-to-q_cell mapping. */
  return kappa_offset_provider_value (point, d, 1, 0);
}

static inline double nn_interface_c2_interpolate
  (double kappa0, double kappa1, double xi, double ready0, double ready1)
{
  int thread = kappa_offset_stats_thread_index();
  nn_interface_c2_crossings[thread]++;
  int missing = 0;
  double value = nn_interface_c2_interpolate_value
    (kappa0, kappa1, xi, ready0 > 0.5, ready1 > 0.5, &missing);
  if (missing) {
    nn_interface_c2_missing_endpoint[thread] += (unsigned long long) missing;
    fprintf (stderr,
             "nn_interface_c2_missing xi=%.17g ready0=%.17g ready1=%.17g\n",
             xi, ready0, ready1);
    abort();
  }
  return value;
}

event nn_interface_c2_reset (t = 0)
{
  for (int thread = 0; thread < KAPPA_OFFSET_MAX_THREADS; thread++) {
    nn_interface_c2_crossings[thread] = 0;
    nn_interface_c2_endpoint_predictions[thread] = 0;
    nn_interface_c2_missing_endpoint[thread] = 0;
  }
}

event nn_interface_c2_stats (t = end)
{
  unsigned long long crossings = 0, endpoint_predictions = 0,
    missing_endpoint = 0;
  for (int thread = 0; thread < KAPPA_OFFSET_MAX_THREADS; thread++) {
    crossings += nn_interface_c2_crossings[thread];
    endpoint_predictions += nn_interface_c2_endpoint_predictions[thread];
    missing_endpoint += nn_interface_c2_missing_endpoint[thread];
  }
  fprintf (stderr,
           "nn_interface_c2_stats crossings=%llu endpoint_predictions=%llu missing_endpoint=%llu\n",
           crossings, endpoint_predictions, missing_endpoint);
}

#endif
#endif
