#define main capwave_vof_hf_matrix_main
#include "capwave.c"
#undef main

#ifndef SINGLE_N
# error "SINGLE_N must be defined"
#endif

int main()
{
  size (2. [1]);
  Y0 = -L0/2.;
  f.sigma = 1.;
  TOLERANCE = 1e-6 [*];
  mu[] = {0.0182571749236, 0.0182571749236};
  N = SINGLE_N;
  se = 0;
  ne = 0;
  run();
}
