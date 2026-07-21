#!/usr/bin/env python3
"""Append non-scheduling Basilisk field checkpoints to a generated case."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEDULES = {
    "capwave": {
        "coordinate": "t*11.1366559937",
        "coordinate_name": "tau",
        "targets": [
            ("tau_0", 0.0, 0.0),
            ("tau_2pi", 6.283185307179586, 6.283185307179586 / 11.1366559937),
            ("tau_4pi", 12.566370614359172, 12.566370614359172 / 11.1366559937),
            ("tau_6pi", 18.84955592153876, 18.84955592153876 / 11.1366559937),
        ],
        "reason": "not_reached_before_terminal_time",
    },
    "rising_bubble": {
        "coordinate": "t",
        "coordinate_name": "time",
        "targets": [("t_0", 0.0, 0.0), ("t_1", 1.0, 1.0), ("t_2", 2.0, 2.0)],
        "reason": "not_reached_before_terminal_time",
    },
    "stationary_bubble": {
        "coordinate": "MU*t/sq(DIAMETER)",
        "coordinate_name": "tau",
        "targets": [
            ("tau_0", 0.0, 0.0),
            ("tau_0p01", 0.01, -1.0),
            ("tau_0p1", 0.1, -1.0),
            ("tau_0p5", 0.5, -1.0),
        ],
        "reason": "not_reached_due_to_convergence_or_tau_limit",
    },
    "oscillating_droplet": {
        "coordinate": "t",
        "coordinate_name": "time",
        # Targets are multiples of the kinetic-energy period pi/omega0,
        # not the n=2 shape period 2*pi/omega0.
        "targets": [
            ("ke_cycle_0", 0.0, 0.0),
            ("ke_cycle_5", 0.20289030292962963, 0.20289030292962963),
            ("ke_cycle_10", 0.40578060585925926, 0.40578060585925926),
            ("ke_cycle_15", 0.6086709087888889, 0.6086709087888889),
            ("ke_cycle_20", 0.8115612117185185, 0.8115612117185185),
        ],
        "reason": "not_reached_before_terminal_time",
    },
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render(case: str) -> str:
    schedule = SCHEDULES[case]
    targets = schedule["targets"]
    labels = ", ".join(f'"{label}"' for label, _, _ in targets)
    coordinates = ", ".join(f"{coordinate:.17g}" for _, coordinate, _ in targets)
    times = ", ".join(f"{time:.17g}" for _, _, time in targets)
    return f'''\n\n/* Scientific field checkpoints are observational: this i++ event records the
   first existing solver state crossing each target and never schedules time. */
#define SCIENTIFIC_CHECKPOINT_COUNT {len(targets)}
static const char * scientific_checkpoint_labels[SCIENTIFIC_CHECKPOINT_COUNT] = {{{labels}}};
static const double scientific_checkpoint_targets[SCIENTIFIC_CHECKPOINT_COUNT] = {{{coordinates}}};
static const double scientific_checkpoint_target_times[SCIENTIFIC_CHECKPOINT_COUNT] = {{{times}}};
static int scientific_checkpoint_written[SCIENTIFIC_CHECKPOINT_COUNT] = {{0}};
static double scientific_checkpoint_actual_times[SCIENTIFIC_CHECKPOINT_COUNT] = {{0}};
static double scientific_checkpoint_actual_coordinates[SCIENTIFIC_CHECKPOINT_COUNT] = {{0}};
static int scientific_checkpoint_iterations[SCIENTIFIC_CHECKPOINT_COUNT] = {{0}};
static int scientific_checkpoint_interface_counts[SCIENTIFIC_CHECKPOINT_COUNT] = {{0}};

static int scientific_interface_cell_count (void)
{{
  int count = 0;
  foreach(reduction(+:count))
    if (f[] > 1e-12 && f[] < 1. - 1e-12)
      count++;
  return count;
}}

static void scientific_write_checkpoint (int index, double coordinate,
                                         int iteration)
{{
  int interface_cells = scientific_interface_cell_count();
  if (interface_cells <= 0) {{
    fprintf (stderr,
             "SCIENTIFIC_CHECKPOINT_FAILURE label=%s t=%.17g interface_cells=%d\\n",
             scientific_checkpoint_labels[index], t, interface_cells);
    fflush (stderr);
    exit (87);
  }}
  char path[160];
  sprintf (path, "checkpoints/%s.dump", scientific_checkpoint_labels[index]);
  dump (file = path);
  scientific_checkpoint_written[index] = 1;
  scientific_checkpoint_actual_times[index] = t;
  scientific_checkpoint_actual_coordinates[index] = coordinate;
  scientific_checkpoint_iterations[index] = iteration;
  scientific_checkpoint_interface_counts[index] = interface_cells;
}}

event scientific_checkpoint_observe (i++, last)
{{
  double coordinate = {schedule['coordinate']};
  for (int index = 0; index < SCIENTIFIC_CHECKPOINT_COUNT; index++)
    if (!scientific_checkpoint_written[index] &&
        coordinate + 1e-12 >= scientific_checkpoint_targets[index])
      scientific_write_checkpoint (index, coordinate, i);
}}

event scientific_checkpoint_finalize (t = end, last)
{{
  double coordinate = {schedule['coordinate']};
  int interface_cells = scientific_interface_cell_count();
  if (interface_cells <= 0) {{
    fprintf (stderr,
             "SCIENTIFIC_CHECKPOINT_FAILURE label=terminal t=%.17g interface_cells=%d\\n",
             t, interface_cells);
    fflush (stderr);
    exit (87);
  }}
  dump (file = "checkpoints/terminal.dump");
  FILE * index_fp = fopen ("checkpoint_index.csv", "w");
  if (!index_fp) {{
    perror ("checkpoint_index.csv");
    exit (1);
  }}
  fprintf (index_fp,
           "label,coordinate_name,target_coordinate,target_time,actual_coordinate,actual_time,iteration,status,reason,dump_path,interface_cells\\n");
  for (int index = 0; index < SCIENTIFIC_CHECKPOINT_COUNT; index++)
    if (scientific_checkpoint_written[index])
      fprintf (index_fp,
               "%s,{schedule['coordinate_name']},%.17g,%.17g,%.17g,%.17g,%d,written,,checkpoints/%s.dump,%d\\n",
               scientific_checkpoint_labels[index],
               scientific_checkpoint_targets[index],
               scientific_checkpoint_target_times[index],
               scientific_checkpoint_actual_coordinates[index],
               scientific_checkpoint_actual_times[index],
               scientific_checkpoint_iterations[index],
               scientific_checkpoint_labels[index],
               scientific_checkpoint_interface_counts[index]);
    else
      fprintf (index_fp,
               "%s,{schedule['coordinate_name']},%.17g,%.17g,,,,not_reached,{schedule['reason']},,0\\n",
               scientific_checkpoint_labels[index],
               scientific_checkpoint_targets[index],
               scientific_checkpoint_target_times[index]);
  fprintf (index_fp,
           "terminal,{schedule['coordinate_name']},,,%.17g,%.17g,%d,written,actual_terminal_state,checkpoints/terminal.dump,%d\\n",
           coordinate, t, i, interface_cells);
  fclose (index_fp);
}}
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", choices=tuple(SCHEDULES), required=True)
    parser.add_argument("--provenance", type=Path)
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    if "event scientific_checkpoint_observe" in source:
        raise SystemExit("source already contains scientific checkpoints")
    output = source + render(args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    if args.provenance:
        payload = {
            "schema_version": 1,
            "case": args.case,
            "source_sha256": sha256_text(source),
            "generated_sha256": sha256_text(output),
            "semantics": "first existing i++ state crossing target; no time scheduling",
            "schedule": SCHEDULES[args.case],
        }
        args.provenance.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
