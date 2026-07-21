/**
# Oscillating droplet: single-level CLSVOF host

This is a row-isolated form of the frozen CLSVOF extension.  The physical
setup, observables and official fit are unchanged.  METHOD_NN only selects the
generated integral.h overlay; all other method-level inputs are identical.
*/

#include "navier-stokes/centered.h"
#define FILTERED 1

// The stock CLSVOF header hard-codes imax=3.  Formal sensitivity rows use a
// row-local header overlay which reads this runtime value instead, allowing
// one numerically identical executable per (LEVEL, method) to serve all imax.
int oscillation_redistance_imax = 3;
#include "two-phase-clsvof.h"

#ifndef METHOD_NN
# define METHOD_NN 0
#endif
#if METHOD_NN
# include "oscillation_raw27_adapter.h"
#endif
#include "integral.h"

#ifndef LEVEL
# define LEVEL 6
#endif
#ifndef T_END
# define T_END 1.0
#endif
#ifndef ENABLE_FIT
# define ENABLE_FIT 1
#endif
#ifndef KINETIC_ENERGY_FAILURE_LIMIT
# define KINETIC_ENERGY_FAILURE_LIMIT 1e-2
#endif
#ifndef ENABLE_SNAPSHOTS
# define ENABLE_SNAPSHOTS 0
#endif

#define D 0.2

FILE * fp = NULL;

int main()
{
  char * redistance_imax_text = getenv ("OSCILLATION_REDISTANCE_IMAX");
  if (redistance_imax_text) {
    char * end = NULL;
    long value = strtol (redistance_imax_text, &end, 10);
    if (!end || *end || value < 0 || value > 5) {
      fprintf (stderr, "invalid OSCILLATION_REDISTANCE_IMAX=%s\n",
               redistance_imax_text);
      return 2;
    }
    oscillation_redistance_imax = value;
  }
  rho1 = 1, rho2 = 1e-3;
  const scalar sigma[] = 1.;
  d.sigmaf = sigma;
  L0 = 0.5 [0];
  TOLERANCE = 1e-4 [*];
  remove ("error");
  remove ("laplace");
  remove ("log");
  N = 1 << LEVEL;
  char name[80];
  sprintf (name, "k-%d", LEVEL);
  fp = fopen (name, "w");
  run();
  fclose (fp);
#if ENABLE_FIT
  int grep_status = system ("grep ^fit out >> log");
  if (grep_status != 0) {
    fprintf (stderr, "OSCILLATION_FIT_FAILURE grep_status=%d\n", grep_status);
    return 3;
  }
#endif
}

event init (i = 0) {
  foreach()
    d[] = D/2.*(1. + 0.05*cos(2.*atan2(y,x))) - sqrt(sq(x) + sq(y));
}

event logfile (i++; t <= T_END) {
  double ke = 0.;
  foreach (reduction(+:ke))
    ke += dv()*(sq(u.x[]) + sq(u.y[]))*rho(sf[]);
  fprintf (fp, "%g %g %d\n", t, ke, mgp.i);
  fflush (fp);
  if (!isfinite (ke) || ke > KINETIC_ENERGY_FAILURE_LIMIT) {
    fprintf (stderr,
             "OSCILLATION_NUMERICAL_FAILURE t=%.17g kinetic_energy=%.17g limit=%.17g\n",
             t, ke, (double) KINETIC_ENERGY_FAILURE_LIMIT);
    fflush (stderr);
    exit (86);
  }
}

#if ENABLE_SNAPSHOTS
/* One theoretical n=2 shape period, sampled at quarter-period phases.  These
   events are disabled in formal metric rows and enabled only for the matched
   process-figure reruns. */
event interface_snapshots (t = {0.,
                                0.02028903029296296,
                                0.04057806058592593,
                                0.06086709087888889,
                                0.08115612117185185}) {
  static int snapshot_index = 0;
  char name[80];
  sprintf (name, "interface-%02d.dat", snapshot_index);
  FILE * snapshot_fp = fopen (name, "w");
  if (!snapshot_fp) {
    perror (name);
    exit (1);
  }
  output_facets (f, snapshot_fp);
  fclose (snapshot_fp);

  FILE * time_fp = fopen ("snapshot_times.csv",
                          snapshot_index == 0 ? "w" : "a");
  if (!time_fp) {
    perror ("snapshot_times.csv");
    exit (1);
  }
  if (snapshot_index == 0)
    fprintf (time_fp, "snapshot_index,time\n");
  fprintf (time_fp, "%d,%.17g\n", snapshot_index, t);
  fclose (time_fp);
  snapshot_index++;
}
#endif

#if ENABLE_FIT
event fit (t = end) {
  FILE * gp = popen ("gnuplot 2>&1", "w");
  if (!gp) {
    perror ("popen gnuplot");
    exit (1);
  }
  fprintf (gp,
           "k(t)=a*exp(-b*t)*(1.-cos(c*t))\n"
           "a = 3e-4\n"
           "b = 1.5\n"
           "\n"
           "D = %g\n"
           "n = 2.\n"
           "sigma = 1.\n"
           "rhol = 1.\n"
           "rhog = 1./1000.\n"
           "r0 = D/2.\n"
           "omega0 = sqrt((n**3-n)*sigma/((rhol+rhog)*r0**3))\n"
           "\n"
           "c = 2.*omega0\n"
           "fit k(x) 'k-%d' via a,b,c\n"
           "level = %d\n"
           "res = D/%g*2.**level\n"
           "print sprintf (\"fit %%g %%.6f %%.2f %%.0f\\n\", res, a, b, c, D)\n"
           "\n"
           "set table 'fit-%d'\n"
           "plot [0:1] 2.*a*exp(-b*x)\n"
           "unset table\n"
           "\n"
           "set print 'error' append\n"
           "print res, c/2./omega0-1., D\n"
           "\n"
           "set print 'laplace' append\n"
           "empirical_constant = 30.\n"
           "print res, (1./((b*b)*D**3.))*empirical_constant**2, D\n"
           "\n",
           D, LEVEL, LEVEL, L0, LEVEL);
  int fit_status = pclose (gp);
  if (fit_status != 0) {
    fprintf (stderr, "OSCILLATION_FIT_FAILURE pclose_status=%d\n", fit_status);
    fflush (stderr);
    exit (1);
  }
}
#endif

#if TREE
event adapt (i++) {
  adapt_wavelet ({f,u}, {5e-3,1e-3,1e-3}, LEVEL);
}
#endif
