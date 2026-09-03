#ifndef CLSVOF_MLP_INFER_H
#define CLSVOF_MLP_INFER_H

#include <stddef.h>

#ifndef CLSVOF_NN_INPUT_DIM
#error "Include an exported nn_weights.h before clsvof_mlp_infer.h"
#endif

#if KAPPA_OFFSET_INFERENCE_DOUBLE
typedef double clsvof_nn_infer_real;
#else
typedef float clsvof_nn_infer_real;
#endif

static inline clsvof_nn_infer_real clsvof_relu(clsvof_nn_infer_real x)
{
  return x > 0.0 ? x : 0.0;
}

static inline clsvof_nn_infer_real clsvof_nn_predict_hkappa(
  const clsvof_nn_infer_real raw[CLSVOF_NN_INPUT_DIM])
{
  clsvof_nn_infer_real h0[CLSVOF_NN_HIDDEN_UNITS];
  clsvof_nn_infer_real h1[CLSVOF_NN_HIDDEN_UNITS];
  clsvof_nn_infer_real h2[CLSVOF_NN_HIDDEN_UNITS];
  clsvof_nn_infer_real h3[CLSVOF_NN_HIDDEN_UNITS];
  clsvof_nn_infer_real x[CLSVOF_NN_INPUT_DIM];

  for (size_t i = 0; i < CLSVOF_NN_INPUT_DIM; ++i)
    x[i] = (raw[i] - clsvof_nn_mean[i]) / clsvof_nn_std[i];

  for (size_t o = 0; o < CLSVOF_NN_HIDDEN_UNITS; ++o) {
    clsvof_nn_infer_real acc = clsvof_nn_b0[o];
    for (size_t i = 0; i < CLSVOF_NN_INPUT_DIM; ++i)
      acc += clsvof_nn_w0[o][i] * x[i];
    h0[o] = clsvof_relu(acc);
  }

  for (size_t o = 0; o < CLSVOF_NN_HIDDEN_UNITS; ++o) {
    clsvof_nn_infer_real acc = clsvof_nn_b1[o];
    for (size_t i = 0; i < CLSVOF_NN_HIDDEN_UNITS; ++i)
      acc += clsvof_nn_w1[o][i] * h0[i];
    h1[o] = clsvof_relu(acc);
  }

  for (size_t o = 0; o < CLSVOF_NN_HIDDEN_UNITS; ++o) {
    clsvof_nn_infer_real acc = clsvof_nn_b2[o];
    for (size_t i = 0; i < CLSVOF_NN_HIDDEN_UNITS; ++i)
      acc += clsvof_nn_w2[o][i] * h1[i];
    h2[o] = clsvof_relu(acc);
  }

  for (size_t o = 0; o < CLSVOF_NN_HIDDEN_UNITS; ++o) {
    clsvof_nn_infer_real acc = clsvof_nn_b3[o];
    for (size_t i = 0; i < CLSVOF_NN_HIDDEN_UNITS; ++i)
      acc += clsvof_nn_w3[o][i] * h2[i];
    h3[o] = clsvof_relu(acc);
  }

  clsvof_nn_infer_real out = clsvof_nn_b4[0];
  for (size_t i = 0; i < CLSVOF_NN_HIDDEN_UNITS; ++i)
    out += clsvof_nn_w4[0][i] * h3[i];
  return out;
}

#endif
