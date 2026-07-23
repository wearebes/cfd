#define main oscillation_vof_hf_suite_main
#include "oscillation.c"
#undef main

#ifndef SINGLE_LEVEL
# error "SINGLE_LEVEL must be defined"
#endif

int main()
{
  rho1 = 1., rho2 = 1e-3;
  f.sigma = 1.;
  L0 = 0.5 [0];
  TOLERANCE = 1e-4 [*];
  remove ("error");
  remove ("laplace");

  LEVEL = SINGLE_LEVEL;
  N = 1 << LEVEL;
  char name[80];
  sprintf (name, "k-%d", LEVEL);
  fp = fopen (name, "w");
  run();
  fclose (fp);
  system ("grep ^fit out >> log");
}

event vof_hf_termination_record (t = end, last)
{
  FILE * termination_fp = fopen ("termination.csv", "w");
  if (!termination_fp) {
    perror ("termination.csv");
    exit (1);
  }
  fprintf (termination_fp,
           "reason,requested_terminal_time,actual_terminal_time,iteration\n");
  fprintf (termination_fp, "fixed_time_limit,1,%.17g,%d\n", t, i);
  fclose (termination_fp);
}
