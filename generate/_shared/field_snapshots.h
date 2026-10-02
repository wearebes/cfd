#ifndef CFD_FIELD_SNAPSHOTS_H
#define CFD_FIELD_SNAPSHOTS_H

#include <float.h>
#include <math.h>
#include <stdio.h>
#include "curvature.h"

/*
 * Observational two-snapshot output shared by every generated benchmark row.
 * The middle snapshot is the first native solver state at or after the target;
 * it does not add a scheduled time and therefore does not shorten a timestep.
 */

#ifndef CFD_SNAPSHOT_MIDDLE_SOLVER_TIME
# error "CFD_SNAPSHOT_MIDDLE_SOLVER_TIME must be defined"
#endif
#ifndef CFD_SNAPSHOT_FINAL_SOLVER_TIME
# error "CFD_SNAPSHOT_FINAL_SOLVER_TIME must be defined"
#endif
#ifndef CFD_SNAPSHOT_PHASE_VALUE
# error "CFD_SNAPSHOT_PHASE_VALUE must be defined"
#endif
#ifndef CFD_SNAPSHOT_BENCHMARK_TIME
# define CFD_SNAPSHOT_BENCHMARK_TIME(value) (value)
#endif
#ifndef CFD_SNAPSHOT_CLSVOF
# define CFD_SNAPSHOT_CLSVOF 0
#endif
#ifndef METHOD_NN
# define METHOD_NN 0
#endif
#ifndef METHOD_ORACLE
# define METHOD_ORACLE 0
#endif

static int cfd_middle_snapshot_written = 0;

static void cfd_write_field_snapshot (const char * label,
                                      double target_solver_time,
                                      int snapshot_iteration)
{
  scalar phase_snapshot[], common_curvature[], omega[];
  foreach()
    phase_snapshot[] = CFD_SNAPSHOT_PHASE_VALUE;
  boundary ({phase_snapshot});
  curvature (phase_snapshot, common_curvature);
  vorticity (u, omega);

  FILE * field_fp = fopen ("fields.csv",
                           cfd_middle_snapshot_written ? "a" : "w");
  if (!field_fp) {
    perror ("fields.csv");
    exit (1);
  }
  if (!cfd_middle_snapshot_written)
    fprintf (field_fp,
             "snapshot,target_solver_time,actual_solver_time,"
             "actual_benchmark_time,iteration,x,y,Delta,level,u_x,u_y,"
             "pressure,vorticity,phase_fraction,common_curvature,"
             "common_curvature_valid,active_curvature,"
             "active_curvature_valid\n");

  foreach (serial) {
    int common_valid = common_curvature[] != nodata &&
      isfinite (common_curvature[]);
    int active_valid = 0;
    double active_curvature = nodata;
#if CFD_SNAPSHOT_CLSVOF
    for (int offset = -1; offset <= 1; offset += 2)
      if (d[]*(d[] + d[offset]) < 0. ||
          d[]*(d[] + d[0,offset]) < 0.)
        active_valid = 1;
    if (active_valid) {
# if METHOD_NN
      active_curvature = kappa_offset_provider_diagnostic (point, d);
# elif METHOD_ORACLE
      active_curvature = oracle_curvature_provider (point, d);
# else
      active_curvature = distance_curvature (point, d);
# endif
      active_valid = active_curvature != nodata && isfinite (active_curvature);
    }
#else
    active_valid = common_valid;
    active_curvature = common_curvature[];
#endif
    fprintf (field_fp,
             "%s,%.17g,%.17g,%.17g,%d,%.17g,%.17g,%.17g,%d,"
             "%.17g,%.17g,%.17g,%.17g,%.17g,",
             label, target_solver_time, t, CFD_SNAPSHOT_BENCHMARK_TIME(t),
             snapshot_iteration, x, y, Delta, level, u.x[], u.y[], p[], omega[],
             phase_snapshot[]);
    if (common_valid)
      fprintf (field_fp, "%.17g,1,", common_curvature[]);
    else
      fprintf (field_fp, ",0,");
    if (active_valid)
      fprintf (field_fp, "%.17g,1\n", active_curvature);
    else
      fprintf (field_fp, ",0\n");
  }
  fclose (field_fp);
}

event cfd_middle_field_snapshot (i++)
{
  if (!cfd_middle_snapshot_written &&
      t + 64.*DBL_EPSILON*fmax(1., fabs(t)) >=
      CFD_SNAPSHOT_MIDDLE_SOLVER_TIME) {
    cfd_write_field_snapshot ("middle", CFD_SNAPSHOT_MIDDLE_SOLVER_TIME, i);
    cfd_middle_snapshot_written = 1;
  }
}

event cfd_final_field_snapshot (t = end, last)
{
  cfd_write_field_snapshot ("final", CFD_SNAPSHOT_FINAL_SOLVER_TIME, i);
}

#endif
