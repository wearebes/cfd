#ifndef STATIONARY_NN_FEATURES_H
#define STATIONARY_NN_FEATURES_H
#include <math.h>
static inline void stationary_build_raw27 (Point point, scalar d, float raw[27]) {
  int p = 0;
  for (int j = 1; j >= -1; j--) for (int i = -1; i <= 1; i++) raw[p++] = (float)(d[i,j]/Delta);
  for (int j = 1; j >= -1; j--) for (int i = -1; i <= 1; i++) { double gx=(d[i+1,j]-d[i-1,j])/(2.*Delta), gy=(d[i,j+1]-d[i,j-1])/(2.*Delta); raw[p++]=(float)(gx/(sqrt(sq(gx)+sq(gy))+1e-30)); }
  for (int j = 1; j >= -1; j--) for (int i = -1; i <= 1; i++) { double gx=(d[i+1,j]-d[i-1,j])/(2.*Delta), gy=(d[i,j+1]-d[i,j-1])/(2.*Delta); raw[p++]=(float)(gy/(sqrt(sq(gx)+sq(gy))+1e-30)); }
}
#endif
