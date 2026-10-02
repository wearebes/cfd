/**
 * Single-resolution stationary-bubble case derived from Basilisk
 * test/spurious.c.
 *
 * This case intentionally uses the official CLSVOF update path.  The native
 * build includes Basilisk's integral.h unchanged.  The NN and Oracle builds
 * use local integral.h overlays that swap only the active ki provider.
 */

#define JACOBI 1

#include "grid/multigrid.h"
#include "navier-stokes/centered.h"
#include "two-phase-clsvof.h"
#include "integral.h"
#include "curvature.h"

#ifndef STATIONARY_LEVEL
# define STATIONARY_LEVEL 6
#endif

#ifndef STATIONARY_TAU_MAX
# define STATIONARY_TAU_MAX 2.
#endif

#ifndef METHOD_NN
# define METHOD_NN 0
#endif

#ifndef METHOD_ORACLE
# define METHOD_ORACLE 0
#endif

#if METHOD_NN && METHOD_ORACLE
# error "METHOD_NN and METHOD_ORACLE are mutually exclusive"
#endif

#ifndef STATIONARY_FULL_DOMAIN
# define STATIONARY_FULL_DOMAIN 0
#endif

#define DIAMETER 0.8
#define RADIUS (DIAMETER/2.)
#define LAPLACE 12000.
#define MU sqrt(DIAMETER/LAPLACE)
#define TMAX (STATIONARY_TAU_MAX*sq(DIAMETER)/MU)
#define TAU_ONE_TIME (sq(DIAMETER)/MU)
#ifndef STATIONARY_CA_BAND_CELLS
# define STATIONARY_CA_BAND_CELLS 4.
#endif
#ifndef STATIONARY_NN_C2_TRACE
# define STATIONARY_NN_C2_TRACE 0
#endif
#ifndef STATIONARY_NN_C2_TRACE_TAU_START
# define STATIONARY_NN_C2_TRACE_TAU_START 0.
#endif
#ifndef STATIONARY_NN_C2_TRACE_TAU_END
# define STATIONARY_NN_C2_TRACE_TAU_END 0.
#endif

scalar fn[];
FILE * fp = NULL;
FILE * fp_whole = NULL;
FILE * milestones_fp = NULL;
const char * stationary_stop_reason = "fixed_tau_limit";
double stationary_stop_tau = -1.;
int stationary_stop_iteration = -1;

int main (void)
{
#if STATIONARY_FULL_DOMAIN
  size (2.);
  origin (-1., -1.);
#endif
  DT = HUGE [0];
  TOLERANCE = 1e-6 [*];
  stokes = true;
  rho1 = rho2 = 1.;
  mu1 = mu2 = MU;
  const scalar sigma[] = 1.;
  d.sigmaf = sigma;
  N = 1 << STATIONARY_LEVEL;
#ifdef STATIONARY_DEBUG
  fprintf (stderr, "DEBUG TMAX=%g MU=%g N=%d\n", TMAX, MU, N);
#endif
  run();
}

event init (i = 0)
{
  char name[80];
  sprintf (name, "La-%g-%d", LAPLACE, STATIONARY_LEVEL);
  fp = fopen (name, "w");
  sprintf (name, "La-whole-%g-%d", LAPLACE, STATIONARY_LEVEL);
  fp_whole = fopen (name, "w");
  milestones_fp = fopen ("milestones.csv", "w");
  if (!fp || !fp_whole || !milestones_fp) {
    perror ("stationary output");
    exit (1);
  }
  fprintf (milestones_fp,
           "milestone,tau,iteration,u_star,shape_error_avg,shape_error_rms,"
           "shape_error_max,official_style_ekmax,active_provider_ekmax,"
           "active_provider_samples\n");
  fflush (milestones_fp);

  // d = r - R: the bubble is d < 0 and d = 0 is the circular interface.
  foreach()
    d[] = sqrt(sq(x) + sq(y)) - RADIUS;
  boundary ({d});

  // The first change() call refreshes fn after CLSVOF builds f from d.
  foreach()
    fn[] = f[];
}

static double stationary_interface_band_u_star (void)
{
  /* STATIONARY_CA_BAND_CELLS is the total band width in Delta units. */
  double umax = 0.;
  foreach (reduction(max:umax))
    if (fabs(sqrt(sq(x) + sq(y)) - RADIUS) <=
        0.5*STATIONARY_CA_BAND_CELLS*Delta) {
      double speed = norm(u);
      if (speed > umax)
        umax = speed;
    }
  return umax*sqrt(DIAMETER);
}

static double stationary_whole_domain_u_star (void)
{
  scalar un[];
  foreach()
    un[] = norm (u);
  return normf(un).max*sqrt(DIAMETER);
}

#if METHOD_NN && STATIONARY_NN_C2_TRACE
static void stationary_trace_nn_c2_endpoints (void)
{
  double tau = MU*t/sq(DIAMETER);
  if (tau < STATIONARY_NN_C2_TRACE_TAU_START ||
      tau > STATIONARY_NN_C2_TRACE_TAU_END)
    return;
  foreach() {
    int endpoint_needed = 0;
    foreach_dimension()
      for (int neighbor = -1; neighbor <= 1; neighbor += 2)
        if (nn_interface_c2_endpoint_needed (d[], d[neighbor]))
          endpoint_needed = 1;
    if (endpoint_needed) {
      double kappa = kappa_offset_provider_value (point, d, 0, 0);
      fprintf (stderr,
               "NN_C2_ENDPOINT_TRACE %.17g %.17g %.17g %.17g %.17g %.17g\n",
               t, x, y, d[]/Delta, kappa*Delta, tau);
    }
  }
}
#endif

event logfile (i++; t <= TMAX)
{
  double df = change (f, fn);
  fprintf (fp, "%g %g %g\n", MU*t/sq(DIAMETER),
           stationary_interface_band_u_star(), df);
  fflush (fp);
  fprintf (fp_whole, "%g %g %g\n", MU*t/sq(DIAMETER),
           stationary_whole_domain_u_star(), df);
  fflush (fp_whole);
#if METHOD_NN && STATIONARY_NN_C2_TRACE
  stationary_trace_nn_c2_endpoints ();
#endif
}

typedef struct {
  double u_star;
  double shape_error_avg;
  double shape_error_rms;
  double shape_error_max;
  double official_style_ekmax;
  double active_provider_ekmax;
  int active_provider_samples;
} stationary_diagnostics;

static stationary_diagnostics stationary_measure (void)
{
  /* two-phase-clsvof.h sets f=1 outside for d=r-R, while the stock
   * spurious.c diagnostic uses a fraction which is one inside the bubble. */
  scalar bubble[];
  foreach()
    bubble[] = 1. - f[];
  boundary ({bubble});

  double vol = statsf(bubble).sum;
  double radius = sqrt((STATIONARY_FULL_DOMAIN ? 1. : 4.)*vol/pi);
  scalar fref[], ef[], kappa[];
  fraction (fref, sq(RADIUS) - sq(x) - sq(y));
  curvature (bubble, kappa);
  double official_ekmax = 0.;
  foreach (reduction(max:official_ekmax)) {
    ef[] = bubble[] - fref[];
    if (kappa[] != nodata) {
      double ek = fabs(kappa[] - 1./radius);
      if (ek > official_ekmax)
        official_ekmax = ek;
    }
  }

  /* Match the cells used by integral.h's active diagonal-stress provider.
   * Diagnostic provider calls must not alter runtime provider statistics. */
  double active_ekmax = 0.;
  int active_samples = 0;
  foreach (reduction(max:active_ekmax) reduction(+:active_samples)) {
    int active = 0;
    for (int offset = -1; offset <= 1; offset += 2) {
      if (d[]*(d[] + d[offset]) < 0. ||
          d[]*(d[] + d[0,offset]) < 0.)
        active = 1;
    }
    if (active) {
#if METHOD_NN
      double active_kappa = kappa_offset_provider_diagnostic (point, d);
#elif METHOD_ORACLE
      double active_kappa = oracle_curvature_provider (point, d);
#else
      double active_kappa = distance_curvature (point, d);
#endif
      double ek = fabs(active_kappa - 1./radius);
      if (ek > active_ekmax)
        active_ekmax = ek;
      active_samples++;
    }
  }

  norm ne = normf (ef);
  stationary_diagnostics diagnostics = {
    stationary_interface_band_u_star(), ne.avg, ne.rms, ne.max,
    official_ekmax, active_ekmax, active_samples
  };
  return diagnostics;
}

static stationary_diagnostics stationary_write_milestone
  (const char * label, double tau, int iteration)
{
  stationary_diagnostics diagnostics = stationary_measure ();
  fprintf (milestones_fp,
           "%s,%.17g,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%d\n",
           label, tau, iteration, diagnostics.u_star,
           diagnostics.shape_error_avg, diagnostics.shape_error_rms,
           diagnostics.shape_error_max, diagnostics.official_style_ekmax,
           diagnostics.active_provider_ekmax,
           diagnostics.active_provider_samples);
  fflush (milestones_fp);
  return diagnostics;
}

event tau_one_milestone (t = TAU_ONE_TIME)
{
  stationary_write_milestone ("tau_1", 1., i);
}

/*
 * An explicit time event makes Basilisk shorten the last timestep to TMAX.
 * Relying only on the logfile condition would stop after the first step past
 * TMAX, and CLSVOF/NN rows could then end at slightly different tau values.
 */
event fixed_horizon (t = TMAX)
{
  stationary_stop_tau = MU*t/sq(DIAMETER);
  stationary_stop_iteration = i;
  return 1;
}

event error (t = end)
{
  if (stationary_stop_tau < 0.) {
    stationary_stop_tau = MU*t/sq(DIAMETER);
    stationary_stop_iteration = i;
  }
  stationary_diagnostics diagnostics = stationary_write_milestone
    ("terminal", stationary_stop_tau, stationary_stop_iteration);
  fprintf (stderr, "%d %g %g %g %g %g %g\n",
           STATIONARY_LEVEL, LAPLACE, diagnostics.u_star,
           diagnostics.shape_error_avg, diagnostics.shape_error_rms,
           diagnostics.shape_error_max, diagnostics.official_style_ekmax);
  FILE * termination_fp = fopen ("termination.csv", "w");
  if (!termination_fp) {
    perror ("termination.csv");
    exit (1);
  }
  fprintf (termination_fp,
           "reason,requested_terminal_tau,actual_terminal_tau,iteration\n");
  fprintf (termination_fp, "%s,%.17g,%.17g,%d\n", stationary_stop_reason,
           (double) STATIONARY_TAU_MAX, stationary_stop_tau,
           stationary_stop_iteration);
  fclose (termination_fp);
  if (fp)
    fclose (fp);
  if (fp_whole)
    fclose (fp_whole);
  if (milestones_fp)
    fclose (milestones_fp);
}
