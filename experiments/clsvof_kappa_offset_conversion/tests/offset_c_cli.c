#include <stdio.h>
#define CLSVOF_NN_CELL_ARRAY_ONLY 1
#include "clsvof_nn_cell_curvature.h"

int main (void)
{
  double q, s;
  while (scanf ("%lf %lf", &q, &s) == 2) {
    int guard_cell = 0, guard_inverse = 0;
    double denominator_cell, denominator_inverse;
    double q_cell = kappa_offset_q_cell (q, s, &guard_cell, &denominator_cell);
    double q_inverse = kappa_offset_q_gamma (q_cell, s, &guard_inverse,
                                              &denominator_inverse);
    printf ("%.17g %.17g %.17g %.17g %d %d\n",
            q_cell, q_inverse, denominator_cell, denominator_inverse,
            guard_cell, guard_inverse);
  }
  return 0;
}
