/**
# Non-official CLSVOF extension of the official oscillation test

This case keeps the physical setup, LEVEL 4--7 loop, kinetic-energy
measurement and gnuplot fitting contract of src/test/oscillation.c.  The only
method-level changes are the CLSVOF two-phase host, integral surface tension,
distance-field initialisation and sigma binding required by those components.
*/

#include "navier-stokes/centered.h"
#define FILTERED 1
#include "two-phase-clsvof.h"
#include "integral.h"

#define D 0.2

FILE * fp = NULL;
int LEVEL;

int main()
{
  rho1 = 1, rho2 = 1e-3;

  const scalar sigma[] = 1.;
  d.sigmaf = sigma;
  L0 = 0.5 [0];
  TOLERANCE = 1e-4 [*];
  remove ("error");
  remove ("laplace");
  for (LEVEL = 4; LEVEL <= 7; LEVEL++) {
    N = 1 << LEVEL;
    char name[80];
    sprintf (name, "k-%d", LEVEL);
    fp = fopen (name, "w");
    run();
    fclose (fp);
  }
  int grep_status = system ("grep ^fit out >> log");
  if (grep_status != 0) {
    fprintf (stderr, "OSCILLATION_FIT_FAILURE grep_status=%d\n", grep_status);
    return 3;
  }
}

event init (i = 0) {
  foreach()
    d[] = D/2.*(1. + 0.05*cos(2.*atan2(y,x))) - sqrt(sq(x) + sq(y));
}

event logfile (i++; t <= 1) {
  double ke = 0.;
  foreach (reduction(+:ke))
    ke += dv()*(sq(u.x[]) + sq(u.y[]))*rho(sf[]);
  fprintf (fp, "%g %g %d\n", t, ke, mgp.i);
  fflush (fp);
}

event fit (t = end) {
  FILE * fp = popen ("gnuplot 2>&1", "w");
  if (!fp) {
    perror ("popen gnuplot");
    exit (1);
  }
  fprintf (fp,
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
  int fit_status = pclose (fp);
  if (fit_status != 0) {
    fprintf (stderr, "OSCILLATION_FIT_FAILURE pclose_status=%d\n", fit_status);
    fflush (stderr);
    exit (1);
  }
}

#if TREE
event adapt (i++) {
  adapt_wavelet ({f,u}, {5e-3,1e-3,1e-3}, LEVEL);
}
#endif
