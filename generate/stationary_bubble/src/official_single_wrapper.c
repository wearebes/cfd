#define main spurious_official_matrix_main
#include "spurious.c"
#undef main

#ifndef SINGLE_LEVEL
# error "SINGLE_LEVEL must be defined"
#endif

int main()
{
  DT = HUGE [0];
  TOLERANCE = 1e-6 [*];
  stokes = true;
  c.sigma = 1.;
  LAPLACE = 12000.;
  DC = 1e-10;
  LEVEL = SINGLE_LEVEL;
  N = 1 << LEVEL;
  run();
}
