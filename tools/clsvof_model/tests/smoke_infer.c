#include <stdio.h>

#include "nn_weights.h"
#include "clsvof_mlp_infer.h"

int main(void)
{
  float raw[CLSVOF_NN_INPUT_DIM] = {0.0f};
  float hkappa = clsvof_nn_predict_hkappa(raw);
  printf("%.9g\n", (double) hkappa);
  return 0;
}
