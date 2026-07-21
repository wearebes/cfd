#ifndef CLSVOF_MLP_INFER_H
#define CLSVOF_MLP_INFER_H

#include <stddef.h>

#ifndef CLSVOF_NN_INPUT_DIM
#error "Include an exported nn_weights.h before clsvof_mlp_infer.h"
#endif

static inline float clsvof_relu(float x)
{
  return x > 0.0f ? x : 0.0f;
}

static inline float clsvof_nn_predict_hkappa(const float raw[CLSVOF_NN_INPUT_DIM])
{
  float h0[CLSVOF_NN_HIDDEN_UNITS];
  float h1[CLSVOF_NN_HIDDEN_UNITS];
  float h2[CLSVOF_NN_HIDDEN_UNITS];
  float h3[CLSVOF_NN_HIDDEN_UNITS];
  float x[CLSVOF_NN_INPUT_DIM];

  for (size_t i = 0; i < CLSVOF_NN_INPUT_DIM; ++i)
    x[i] = (raw[i] - clsvof_nn_mean[i]) / clsvof_nn_std[i];

  for (size_t o = 0; o < CLSVOF_NN_HIDDEN_UNITS; ++o) {
    float acc = clsvof_nn_b0[o];
    for (size_t i = 0; i < CLSVOF_NN_INPUT_DIM; ++i)
      acc += clsvof_nn_w0[o][i] * x[i];
    h0[o] = clsvof_relu(acc);
  }

  for (size_t o = 0; o < CLSVOF_NN_HIDDEN_UNITS; ++o) {
    float acc = clsvof_nn_b1[o];
    for (size_t i = 0; i < CLSVOF_NN_HIDDEN_UNITS; ++i)
      acc += clsvof_nn_w1[o][i] * h0[i];
    h1[o] = clsvof_relu(acc);
  }

  for (size_t o = 0; o < CLSVOF_NN_HIDDEN_UNITS; ++o) {
    float acc = clsvof_nn_b2[o];
    for (size_t i = 0; i < CLSVOF_NN_HIDDEN_UNITS; ++i)
      acc += clsvof_nn_w2[o][i] * h1[i];
    h2[o] = clsvof_relu(acc);
  }

  for (size_t o = 0; o < CLSVOF_NN_HIDDEN_UNITS; ++o) {
    float acc = clsvof_nn_b3[o];
    for (size_t i = 0; i < CLSVOF_NN_HIDDEN_UNITS; ++i)
      acc += clsvof_nn_w3[o][i] * h2[i];
    h3[o] = clsvof_relu(acc);
  }

  float out = clsvof_nn_b4[0];
  for (size_t i = 0; i < CLSVOF_NN_HIDDEN_UNITS; ++i)
    out += clsvof_nn_w4[0][i] * h3[i];
  return out;
}

#endif
