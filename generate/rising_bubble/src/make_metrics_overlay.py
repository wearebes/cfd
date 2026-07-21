#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LOGFILE_END = """  putchar ('\\n');
  fflush (stdout);
}"""
CIRCULARITY_EVENTS = r"""

static FILE * rising_circularity_fp = NULL;
static double rising_circularity_last_t = -HUGE;

void rising_write_circularity_sample (double sample_t, int sample_i)
{
  if (fabs (sample_t - rising_circularity_last_t) <= 1e-12)
    return;
  double sb = 0.;
  foreach(reduction(+:sb))
    sb += (1. - f[])*dv();
  double perim = interface_area (f);

  /* The computational domain contains half of the bubble. Reconstruct the
     full-domain circularity using A_full = 2*sb and P_full = 2*perim. */
  double circ = perim > 0. ? sqrt (2.*pi*sb)/perim : -1.;
  if (!rising_circularity_fp) {
    rising_circularity_fp = fopen ("circularity.csv", "w");
    if (!rising_circularity_fp) {
      perror ("circularity.csv");
      exit (1);
    }
    fprintf (rising_circularity_fp,
             "time,iteration,half_area,half_perimeter,circularity\n");
  }
  fprintf (rising_circularity_fp, "%g,%d,%.17g,%.17g,%.17g\n",
           sample_t, sample_i, sb, perim, circ);
  fflush (rising_circularity_fp);
  rising_circularity_last_t = sample_t;
}

event circularity_history (i++)
  rising_write_circularity_sample (t, i);

event circularity_final (t = 3.)
  rising_write_circularity_sample (t, i);
"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_overlay_text(source: str) -> str:
    if "event circularity_history" in source:
        raise ValueError("expected exactly one uninstrumented stock rising source")
    if source.count(LOGFILE_END) != 1:
        raise ValueError(
            "expected exactly one stock rising logfile terminator: "
            f"{source.count(LOGFILE_END)}"
        )
    return source.replace(LOGFILE_END, LOGFILE_END + CIRCULARITY_EVENTS, 1)


def build_provenance(source: str, output: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_sha256": sha256_text(source),
        "generated_sha256": sha256_text(output),
        "diagnostic_file": "circularity.csv",
        "metric_columns": [
            "time", "iteration", "half_area", "half_perimeter", "circularity"
        ],
        "sampling": "every original solver iteration, plus exact t=3",
        "half_domain_reconstruction": {
            "area_full": "2*sb",
            "perimeter_full": "2*interface_area(f)",
            "circularity": "sqrt(2*pi*sb)/interface_area(f)",
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--provenance", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source.read_text(encoding="utf-8")
    output = build_overlay_text(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    if args.provenance:
        args.provenance.parent.mkdir(parents=True, exist_ok=True)
        args.provenance.write_text(
            json.dumps(build_provenance(source, output), indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
