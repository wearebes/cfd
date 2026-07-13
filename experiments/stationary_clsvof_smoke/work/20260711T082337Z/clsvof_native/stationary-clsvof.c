/**
 * N64 stationary-bubble smoke case derived from Basilisk test/spurious.c.
 *
 * This case intentionally uses the official CLSVOF update path.  The native
 * build includes Basilisk's integral.h unchanged.  The analytic build uses a
 * local integral.h overlay that swaps only the active ki provider.
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

#define DIAMETER 0.8
#define RADIUS (DIAMETER/2.)
#define LAPLACE 12000.
#define MU sqrt(DIAMETER/LAPLACE)
#define TMAX (sq(DIAMETER)/MU)

scalar fn[];
FILE * fp = NULL;

int main (void)
{
  DT = HUGE [0];
  TOLERANCE = 1e-6 [*];
  stokes = true;
  rho1 = rho2 = 1.;
  mu1 = mu2 = MU;
  const scalar sigma[] = 1.;
  d.sigmaf = sigma;
  N = 1 << STATIONARY_LEVEL;
  run();
}

event init (i = 0)
{
  char name[80];
  sprintf (name, "La-%g-%d", LAPLACE, STATIONARY_LEVEL);
  fp = fopen (name, "w");

  // d = r - R: the bubble is d < 0 and d = 0 is the circular interface.
  foreach()
    d[] = sqrt(sq(x) + sq(y)) - RADIUS;
  boundary ({d});

  // The first change() call refreshes fn after CLSVOF builds f from d.
  foreach()
    fn[] = f[];
}

event logfile (i++; t <= TMAX)
{
  double df = change (f, fn);
  if (i > 1 && df < 1e-10)
    return 1;

  scalar un[];
  foreach()
    un[] = norm (u);
  fprintf (fp, "%g %g %g\n", MU*t/sq(DIAMETER),
           normf(un).max*sqrt(DIAMETER), df);
  fflush (fp);
}

event error (t = end)
{
  double vol = statsf(f).sum;
  double radius = sqrt(4.*vol/pi);
  scalar fref[], un[], ef[], kappa[];
  fraction (fref, sq(RADIUS) - sq(x) - sq(y));
  curvature (f, kappa);
  double ekmax = 0.;
  foreach() {
    un[] = norm(u);
    ef[] = f[] - fref[];
    if (kappa[] != nodata) {
      double ek = fabs(kappa[] - 1./radius);
      if (ek > ekmax)
        ekmax = ek;
    }
  }
  norm ne = normf (ef);
  fprintf (stderr, "%d %g %g %g %g %g %g\n",
           STATIONARY_LEVEL, LAPLACE, normf(un).max*sqrt(DIAMETER),
           ne.avg, ne.rms, ne.max, ekmax);
  if (fp)
    fclose (fp);
}
