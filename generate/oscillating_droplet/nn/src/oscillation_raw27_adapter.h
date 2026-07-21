#ifndef OSCILLATION_RAW27_ADAPTER_H
#define OSCILLATION_RAW27_ADAPTER_H

/* The trained model uses phi = r - R (negative inside), while this host uses
 * d = R - r (positive inside).  The shared provider applies this sign both to
 * raw phi/normals and to q_gamma before the solver-side contour offset. */
#define KAPPA_OFFSET_MODEL_PHI_SIGN (-1.0)

#endif
