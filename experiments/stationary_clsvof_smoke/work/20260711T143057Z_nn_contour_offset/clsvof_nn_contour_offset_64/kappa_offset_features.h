#ifndef CLSVOF_KAPPA_OFFSET_FEATURES_H
#define CLSVOF_KAPPA_OFFSET_FEATURES_H

#include <math.h>

static inline void kappa_offset_build_raw27 (Point point, scalar d, float raw[27])
{
  int p = 0;
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++)
      raw[p++] = (float) (d[i,j]/Delta);
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++) {
      double gx = (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = (d[i,j +1] - d[i,j - 1])/(2.*Delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gx/norm);
    }
  for (int j = 1; j >= -1; j--)
    for (int i = -1; i <= 1; i++) {
      double gx = (d[i + 1,j] - d[i - 1,j])/(2.*Delta);
      double gy = (d[i,j +1] - d[i,j - 1])/(2.*Delta);
      double norm = sqrt (gx*gx + gy*gy) + 1e-30;
      raw[p++] = (float) (gy/norm);
    }
}

static inline double kappa_offset_grad_norm (Point point, scalar d)
{
  double gx = (d[1] - d[-1])/(2.*Delta);
  double gy = (d[0,1] - d[0,-1])/(2.*Delta);
  return sqrt (gx*gx + gy*gy);
}

#endif
