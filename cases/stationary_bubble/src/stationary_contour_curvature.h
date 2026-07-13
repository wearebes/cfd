#ifndef STATIONARY_CONTOUR_CURVATURE_H
#define STATIONARY_CONTOUR_CURVATURE_H

/*
 * For d = r - R, every signed-distance contour d = const is a circle of
 * radius r = R + d.  The analytic curvature supplied to integral.h is thus
 * 1/(R + d), rather than the constant zero-contour value 1/R.
 */
#ifndef STATIONARY_RADIUS
# define STATIONARY_RADIUS 0.4
#endif

static inline double stationary_contour_curvature (Point point, scalar d)
{
  return 1./(STATIONARY_RADIUS + d[]);
}

#endif
