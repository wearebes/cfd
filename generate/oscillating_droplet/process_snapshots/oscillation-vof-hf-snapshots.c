/**
# N128 VOF-HF process snapshots for the oscillating-droplet benchmark

This is a single-level, output-instrumented form of the official standard VOF
branch.  The physical setup and adaptive tolerances match oscillation.c.  The
only additions are five phase-resolved interface outputs and a short horizon.
*/

#include "navier-stokes/centered.h"
#define FILTERED 1
#include "two-phase.h"
#include "tension.h"

#ifndef LEVEL
# define LEVEL 7
#endif
#ifndef T_END
# define T_END 0.08115612117185185
#endif

#define D 0.2

FILE * kinetic_fp = NULL;

int main()
{
  rho1 = 1., rho2 = 1e-3;
  f.sigma = 1.;
  L0 = 0.5 [0];
  TOLERANCE = 1e-4 [*];
  N = 1 << LEVEL;
  kinetic_fp = fopen ("k-vof-hf", "w");
  if (!kinetic_fp) {
    perror ("k-vof-hf");
    return 1;
  }
  run();
  fclose (kinetic_fp);
}

event init (i = 0)
  fraction (f, D/2.*(1. + 0.05*cos(2.*atan2(y,x)))
            - sqrt(sq(x) + sq(y)));

event logfile (i++; t <= T_END) {
  double ke = 0.;
  foreach (reduction(+:ke))
    ke += dv()*(sq(u.x[]) + sq(u.y[]))*rho(sf[]);
  fprintf (kinetic_fp, "%.17g %.17g %d\n", t, ke, mgp.i);
  fflush (kinetic_fp);
}

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

#if TREE
event adapt (i++)
  adapt_wavelet ({f,u}, {5e-3,1e-3,1e-3}, LEVEL);
#endif
