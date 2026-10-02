#!/usr/bin/env python3
"""Derive a single-grid tau=2 VOF-HF host from stock spurious.c."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


STOCK_TMAX = "#define TMAX (sq(DIAMETER)/MU)"
FIXED_TMAX = """#define TMAX (2.*sq(DIAMETER)/MU)
#define TAU_ONE_TIME (sq(DIAMETER)/MU)"""
MAIN_START = "int main() {"
MAIN_END = "\n/**\nWe allocate a field"
SINGLE_MAIN = r'''#ifndef SINGLE_LEVEL
# error "SINGLE_LEVEL must be defined"
#endif

int main() {
  DT = HUGE [0];
  TOLERANCE = 1e-6 [*];
  stokes = true;
  c.sigma = 1.;
  LAPLACE = 12000.;
  DC = -1.;
  LEVEL = SINGLE_LEVEL;
  N = 1 << LEVEL;
  run();
}
'''
CONVERGENCE_STOP = """  if (i > 1 && dc < DC)
    return 1; /* stop */
"""
ERROR_START = "event error (t = end) {"
ERROR_END = "\n/**\nWe use an adaptive mesh"
DIAGNOSTICS = r'''typedef struct {
  double u_star;
  double shape_error_avg;
  double shape_error_rms;
  double shape_error_max;
  double curvature_ekmax;
  int curvature_samples;
} vof_hf_diagnostics;

static FILE * vof_hf_milestones_fp = NULL;

static vof_hf_diagnostics vof_hf_measure (void)
{
  double vol = statsf(c).sum;
  double radius = sqrt(4.*vol/pi);
  scalar cref[], un[], ec[], kappa[];
  fraction (cref, sq(DIAMETER/2) - sq(x) - sq(y));
  curvature (c, kappa);
  double ekmax = 0.;
  int curvature_samples = 0;
  foreach (reduction(max:ekmax) reduction(+:curvature_samples)) {
    un[] = norm(u);
    ec[] = c[] - cref[];
    if (kappa[] != nodata) {
      double ek = fabs(kappa[] - 1./radius);
      if (ek > ekmax)
        ekmax = ek;
      curvature_samples++;
    }
  }
  norm ne = normf(ec);
  vof_hf_diagnostics diagnostics = {
    normf(un).max*sqrt(DIAMETER), ne.avg, ne.rms, ne.max,
    ekmax, curvature_samples
  };
  return diagnostics;
}

static vof_hf_diagnostics vof_hf_write_milestone
  (const char * label, double tau, int iteration)
{
  if (!vof_hf_milestones_fp) {
    vof_hf_milestones_fp = fopen ("milestones.csv", "w");
    if (!vof_hf_milestones_fp) {
      perror ("milestones.csv");
      exit (1);
    }
    fprintf (vof_hf_milestones_fp,
             "milestone,tau,iteration,u_star,shape_error_avg,shape_error_rms,"
             "shape_error_max,official_style_ekmax,active_provider_ekmax,"
             "active_provider_samples\n");
  }
  vof_hf_diagnostics diagnostics = vof_hf_measure();
  fprintf (vof_hf_milestones_fp,
           "%s,%.17g,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%d\n",
           label, tau, iteration, diagnostics.u_star,
           diagnostics.shape_error_avg, diagnostics.shape_error_rms,
           diagnostics.shape_error_max, diagnostics.curvature_ekmax,
           diagnostics.curvature_ekmax, diagnostics.curvature_samples);
  fflush (vof_hf_milestones_fp);
  return diagnostics;
}

event tau_one_milestone (t = TAU_ONE_TIME)
  vof_hf_write_milestone ("tau_1", 1., i);

event fixed_horizon (t = TMAX)
  return 1;

event error (t = end) {
  double terminal_tau = MU*t/sq(DIAMETER);
  vof_hf_diagnostics diagnostics = vof_hf_write_milestone
    ("terminal", terminal_tau, i);
  fprintf (stderr, "%d %g %g %g %g %g %g\n",
           LEVEL, LAPLACE, diagnostics.u_star,
           diagnostics.shape_error_avg, diagnostics.shape_error_rms,
           diagnostics.shape_error_max, diagnostics.curvature_ekmax);
  FILE * termination_fp = fopen ("termination.csv", "w");
  if (!termination_fp) {
    perror ("termination.csv");
    exit (1);
  }
  fprintf (termination_fp,
           "reason,requested_terminal_tau,actual_terminal_tau,iteration\n");
  fprintf (termination_fp, "fixed_tau_limit,2,%.17g,%d\n", terminal_tau, i);
  fclose (termination_fp);
  if (fp)
    fclose (fp);
  if (vof_hf_milestones_fp)
    fclose (vof_hf_milestones_fp);
}
'''


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def replace_once(source: str, target: str, replacement: str) -> str:
    if source.count(target) != 1:
        raise ValueError(f"expected one occurrence of {target!r}")
    return source.replace(target, replacement, 1)


def build(source: str, domain: str = "quarter") -> str:
    source = replace_once(source, STOCK_TMAX, FIXED_TMAX)
    main_start = source.index(MAIN_START)
    main_end = source.index(MAIN_END, main_start)
    source = source[:main_start] + SINGLE_MAIN + source[main_end:]
    source = replace_once(
        source,
        CONVERGENCE_STOP,
        "  /* Fixed-horizon comparison: record dc but do not stop early. */\n",
    )
    error_start = source.index(ERROR_START)
    error_end = source.index(ERROR_END, error_start)
    source = source[:error_start] + DIAGNOSTICS + source[error_end:]
    if domain == "whole":
        source = replace_once(source, "  DT = HUGE [0];",
                              "  size (2.);\n  origin (-1., -1.);\n  DT = HUGE [0];")
        source = replace_once(source, "sqrt(4.*vol/pi)", "sqrt(vol/pi)")
    elif domain != "quarter":
        raise ValueError(f"unsupported domain: {domain}")
    return source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--domain", choices=("quarter", "whole"), default="quarter")
    args = parser.parse_args()
    stock = args.source.read_text(encoding="utf-8")
    generated = build(stock, args.domain)
    args.output.write_text(generated, encoding="utf-8")
    args.provenance.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "basilisk/src/test/spurious.c",
                "source_sha256": sha256(stock),
                "generated_sha256": sha256(generated),
                "method": "VOF-HF",
                "domain": args.domain,
                "allowed_changes": [
                    "single_grid_selection",
                    "fixed_tau_2_horizon",
                    "disable_convergence_early_stop",
                    "tau_1_and_tau_2_observations",
                    *(["full_circle_domain", "full_circle_equivalent_radius"]
                      if args.domain == "whole" else []),
                ],
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
