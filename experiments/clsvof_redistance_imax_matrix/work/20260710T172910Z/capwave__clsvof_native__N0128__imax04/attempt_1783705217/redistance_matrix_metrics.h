#ifndef REDISTANCE_MATRIX_METRICS_H
#define REDISTANCE_MATRIX_METRICS_H

#include <stdio.h>

#ifndef REDIST_MATRIX_IMAX
#error "REDIST_MATRIX_IMAX must be defined by the generated CLSVOF header"
#endif

#ifndef REDIST_MATRIX_LOG_STRIDE
#define REDIST_MATRIX_LOG_STRIDE 10
#endif

static FILE * redistance_matrix_metrics_fp = NULL;
static FILE * redistance_matrix_returns_fp = NULL;
/* Static storage is zero-initialised. Avoid an explicit brace initializer:
 * Basilisk's source transformer can misparse it in included solver headers. */
static unsigned long long redistance_matrix_return_counts[64];
static unsigned long long redistance_matrix_call_count = 0;

static inline bool redistance_matrix_should_sample (int iteration)
{
  return iteration == 0 ||
    (REDIST_MATRIX_LOG_STRIDE > 0 && iteration % REDIST_MATRIX_LOG_STRIDE == 0);
}

static void redistance_matrix_open_metrics (void)
{
  if (redistance_matrix_metrics_fp)
    return;
  redistance_matrix_metrics_fp = fopen ("redistance_metrics.csv", "w");
  if (!redistance_matrix_metrics_fp) {
    perror ("redistance_metrics.csv");
    exit (2);
  }
  fprintf (redistance_matrix_metrics_fp,
           "N,t,i,imax,stage,returned_steps,band_cells,count,"
           "Egrad_mean,Egrad_rms,Egrad_linf,grad_min,grad_max,"
           "phi_change_mean,phi_change_linf,sign_mismatch,"
           "f_interface_l1,f_interface_count,volume_phi,volume_vof,"
           "volume_rel_diff\n");
  fflush (redistance_matrix_metrics_fp);
}

static void redistance_matrix_measure (const char * stage,
                                       scalar probe, scalar before,
                                       bool compare_change,
                                       int returned_steps,
                                       int iteration, double physical_time,
                                       double band_cells)
{
  redistance_matrix_open_metrics();

  double grad_sum = 0., grad_sum2 = 0., grad_linf = 0.;
  double grad_min = HUGE, grad_max = 0.;
  double change_sum = 0., change_linf = 0.;
  int count = 0, sign_mismatch = 0;

  foreach (reduction(+:grad_sum) reduction(+:grad_sum2)
           reduction(max:grad_linf) reduction(min:grad_min)
           reduction(max:grad_max) reduction(+:change_sum)
           reduction(max:change_linf) reduction(+:count)
           reduction(+:sign_mismatch)) {
    if (fabs(before[]) <= band_cells*Delta) {
      double gx = (probe[1] - probe[-1])/(2.*Delta);
      double gy = (probe[0,1] - probe[0,-1])/(2.*Delta);
      double grad = sqrt(sq(gx) + sq(gy));
      double error = fabs(grad - 1.);
      double change = compare_change ? fabs(probe[] - before[]) : 0.;
      grad_sum += error;
      grad_sum2 += sq(error);
      grad_linf = max(grad_linf, error);
      grad_min = min(grad_min, grad);
      grad_max = max(grad_max, grad);
      change_sum += change;
      change_linf = max(change_linf, change);
      count++;
      if (compare_change && ((probe[] > 0.) != (before[] > 0.)))
        sign_mismatch++;
    }
  }

  vertex scalar vprobe[];
  foreach_vertex()
    vprobe[] = (probe[] + probe[-1] + probe[0,-1] + probe[-1,-1])/4.;
  scalar fprobe[];
  fractions (vprobe, fprobe);

  double f_l1_sum = 0., volume_probe = 0., volume_vof = 0.;
  int f_count = 0;
  foreach (reduction(+:f_l1_sum) reduction(+:volume_probe)
           reduction(+:volume_vof) reduction(+:f_count)) {
    double fp = clamp(fprobe[], 0., 1.);
    double fv = clamp(f[], 0., 1.);
    volume_probe += fp*sq(Delta);
    volume_vof += fv*sq(Delta);
    if ((fp > 1e-12 && fp < 1. - 1e-12) ||
        (fv > 1e-12 && fv < 1. - 1e-12)) {
      f_l1_sum += fabs(fp - fv);
      f_count++;
    }
  }

  fprintf (redistance_matrix_metrics_fp,
           "%d,%.17g,%d,%d,%s,%d,%.1f,%d,"
           "%.12g,%.12g,%.12g,%.12g,%.12g,"
           "%.12g,%.12g,%d,%.12g,%d,%.12g,%.12g,%.12g\n",
           N, physical_time, iteration, REDIST_MATRIX_IMAX, stage,
           returned_steps, band_cells, count,
           count ? grad_sum/count : nodata,
           count ? sqrt(grad_sum2/count) : nodata,
           grad_linf, count ? grad_min : nodata, grad_max,
           count ? change_sum/count : nodata, change_linf, sign_mismatch,
           f_count ? f_l1_sum/f_count : 0., f_count,
           volume_probe, volume_vof,
           volume_vof != 0. ? (volume_probe - volume_vof)/volume_vof : nodata);
  fflush (redistance_matrix_metrics_fp);
}

static inline void redistance_matrix_record_return (int returned_steps,
                                                     int iteration,
                                                     double physical_time)
{
  redistance_matrix_call_count++;
  if (returned_steps >= 0 && returned_steps < 64)
    redistance_matrix_return_counts[returned_steps]++;

  if (!redistance_matrix_returns_fp) {
    redistance_matrix_returns_fp = fopen ("redistance_return_trace.csv", "w");
    if (!redistance_matrix_returns_fp) {
      perror ("redistance_return_trace.csv");
      exit (2);
    }
    fprintf (redistance_matrix_returns_fp,
             "N,t,i,imax,returned_steps,total_calls\n");
  }
  fprintf (redistance_matrix_returns_fp, "%d,%.17g,%d,%d,%d,%llu\n",
           N, physical_time, iteration, REDIST_MATRIX_IMAX, returned_steps,
           redistance_matrix_call_count);
  fflush (redistance_matrix_returns_fp);
}

#endif
