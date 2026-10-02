#!/usr/bin/env python3
"""Build source-checked integral.h overlays for curvature providers."""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET = "double ki = distance_curvature (point, d);"
REPLACEMENT = "double ki = kappa_offset_provider (point, d);"
ORACLE_REPLACEMENT = "double ki = oracle_curvature_provider (point, d);"
MARKER_LINE = "#endif // CURVATURE\n"
NN_INCLUDE = '#include "clsvof_nn_cell_curvature.h"\n'
DEFINE = (
    "#define CURVATURE 1 // set to 1 (resp. 2) to use curvature "
    "(resp. linear) interpolation of curvature"
)
PRECOMPUTE_TARGET = """      scalar kappa[];
      foreach()
\tkappa[] = distance_curvature (point, d);"""
NN_C2_PRECOMPUTE = """      scalar kappa[], kappa_ready[];
      foreach() {
        int endpoint_needed = 0;
        foreach_dimension()
          for (int neighbor = -1; neighbor <= 1; neighbor += 2)
            if (nn_interface_c2_endpoint_needed (d[], d[neighbor]))
              endpoint_needed = 1;
        if (endpoint_needed) {
          kappa[] = nn_interface_c2_predict_endpoint (point, d);
          kappa_ready[] = 1.;
        }
        else {
          kappa[] = 0.;
          kappa_ready[] = 0.;
        }
      }
      boundary ({kappa, kappa_ready});"""
ORACLE_C2_PRECOMPUTE = """      scalar kappa[];
      foreach()
        kappa[] = 1./ORACLE_RADIUS;"""
INTERPOLATION_TARGET = "double ki = kappa[] + xi*(kappa[i] - kappa[]);"
NN_C2_INTERPOLATION = (
    "double ki = nn_interface_c2_interpolate "
    "(kappa[], kappa[i], xi, kappa_ready[], kappa_ready[i]);"
)
ORACLE_PROVIDER = r'''
#ifndef ORACLE_CURVATURE_MODE
# error "ORACLE_CURVATURE_MODE must be defined"
#endif
#ifndef ORACLE_RADIUS
# error "ORACLE_RADIUS must be defined"
#endif

static inline double oracle_curvature_provider (Point point, scalar d)
{
#if ORACLE_CURVATURE_MODE == 1
  double r = ORACLE_RADIUS + d[];
  if (!isfinite (r) || r <= 0.)
    abort();
  return 1./r;
#elif ORACLE_CURVATURE_MODE == 2
  if (!isfinite ((double) ORACLE_RADIUS) || ORACLE_RADIUS <= 0.)
    abort();
  return 1./ORACLE_RADIUS;
#else
# error "invalid ORACLE_CURVATURE_MODE"
#endif
}
'''.lstrip()


def _require_once(source: str, target: str, label: str) -> None:
    count = source.count(target)
    if count != 1:
        raise ValueError(f"expected exactly one {label}, found {count}")


def _enable_curvature_two(source: str) -> str:
    _require_once(source, DEFINE, "CURVATURE definition")
    return source.replace(DEFINE, DEFINE.replace("CURVATURE 1", "CURVATURE 2"), 1)


def build_overlay_text(
    source: str, provider: str = "nn", method: str | None = None
) -> str:
    """Return one reviewed provider/consumer overlay.

    ``provider=oracle`` remains the backward-compatible cell-local Oracle
    route.  NN cell mode is also unchanged; only ``nn-c2`` replaces the native
    endpoint precompute with NN endpoint predictions.
    """
    _require_once(source, MARKER_LINE, "CURVATURE closing marker")
    method = method or "nn-cell"
    if provider == "oracle" and method == "nn-cell":
        _require_once(source, TARGET, "cell-local curvature assignment")
        return source.replace(TARGET, ORACLE_REPLACEMENT, 1).replace(
            MARKER_LINE, f"{MARKER_LINE}\n{ORACLE_PROVIDER}", 1
        )
    if provider == "oracle" and method == "oracle-c2":
        _require_once(source, PRECOMPUTE_TARGET, "native C2 precompute block")
        _require_once(source, INTERPOLATION_TARGET, "native C2 interpolation")
        overlay = _enable_curvature_two(source)
        overlay = overlay.replace(PRECOMPUTE_TARGET, ORACLE_C2_PRECOMPUTE, 1)
        return overlay.replace(
            MARKER_LINE, f"{MARKER_LINE}\n{ORACLE_PROVIDER}", 1
        )
    if provider == "oracle":
        raise ValueError("invalid Oracle curvature method")
    if provider != "nn":
        raise ValueError(f"unsupported provider: {provider}")
    if method == "nn-cell":
        _require_once(source, TARGET, "cell-local curvature assignment")
        return source.replace(TARGET, REPLACEMENT, 1).replace(
            MARKER_LINE, f"{MARKER_LINE}\n{NN_INCLUDE}", 1
        )
    if method == "native-c2":
        _require_once(source, PRECOMPUTE_TARGET, "native C2 precompute block")
        _require_once(source, INTERPOLATION_TARGET, "native C2 interpolation")
        return _enable_curvature_two(source)
    if method == "nn-c2":
        _require_once(source, PRECOMPUTE_TARGET, "native C2 precompute block")
        _require_once(source, INTERPOLATION_TARGET, "native C2 interpolation")
        overlay = _enable_curvature_two(source)
        overlay = overlay.replace(
            MARKER_LINE,
            MARKER_LINE
            + '\n#include "clsvof_nn_cell_curvature.h"\n'
            + '#include "c2_interface_provider.h"\n',
            1,
        )
        overlay = overlay.replace(PRECOMPUTE_TARGET, NN_C2_PRECOMPUTE, 1)
        overlay = overlay.replace(INTERPOLATION_TARGET, NN_C2_INTERPOLATION, 1)
        if "kappa[] = distance_curvature (point, d);" in overlay:
            raise ValueError("native distance_curvature remains in NN C2 precompute")
        return overlay
    raise ValueError(f"invalid curvature method: {method}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--provider", choices=("nn", "oracle"), default="nn")
    parser.add_argument(
        "--method", choices=("nn-cell", "native-c2", "nn-c2", "oracle-c2")
    )
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_overlay_text(
            args.source.read_text(encoding="utf-8"),
            provider=args.provider,
            method=args.method,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
