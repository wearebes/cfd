/**
# Capillary wave, extended to N = 512

Local extended-resolution copy of the official `capwave.c`. The only
numerical-loop change is extending the maximum resolution from N = 128 to
N = 512.
*/

#include "grid/multigrid.h"
#include "navier-stokes/centered.h"
#if CLSVOF
# include "two-phase-clsvof.h"
# include "integral.h"
# include "curvature.h"
#else
# include "vof.h"
# include "tension.h"
scalar f[], * interfaces = {f};
#endif
#include "prosperetti.h"

uf.n[left]   = 0.;
uf.n[right]  = 0.;
uf.n[top]    = 0.;
uf.n[bottom] = 0.;

double se = 0; int ne = 0;

int main() {
  size (2. [1]);
  Y0 = -L0/2.;
#if CLSVOF
  const scalar sigma[] = 1.;
  d.sigmaf = sigma;
#else
  f.sigma = 1.;
#endif
  TOLERANCE = 1e-6 [*];
  mu[] = {0.0182571749236, 0.0182571749236};

  for (N = 16; N <= 512; N *= 2) {
    se = 0, ne = 0;
    run();
  }
}

event init (t = 0) {
  double k = 2., a = 0.01;
#if CLSVOF
  foreach()
    d[] = y - a*cos (k*pi*x);
#else
  fraction (f, y - a*cos (k*pi*x));
#endif
}

event vof (i++, first);

event amplitude (t += 3.04290519077e-3; t <= 2.2426211256) {
  scalar pos[];
  position (f, pos, {0,1 [0]});
  double max = statsf(pos).max;

  char name[80];
  sprintf (name, "wave-%d", N);
  static FILE * fp = fopen (name, "w");
  fprintf (fp, "%g %g\n", t*11.1366559937, max);
  fflush (fp);

  se += sq(max - prosperetti[ne][1]); ne++;
}

event error (t = end)
  fprintf (stderr, "%g %g\n", N/L0, sqrt(se/ne)/0.01);
