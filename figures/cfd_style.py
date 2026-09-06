"""Computers & Fluids/Elsevier manuscript figure style for the CFD paper.

This module freezes visual language only.  It deliberately does not choose a
metric, time window, axis scale, panel count, legend position, or manuscript
role for any figure.

Setup::

    import matplotlib.pyplot as plt
    from cfd_style import apply_cfd_style

    apply_cfd_style()

Axis-policy guidance
--------------------
* Time histories use a linear x-axis by default.
* Strictly positive quantities spanning roughly two or more orders of
  magnitude may use a logarithmic y-axis.
* Signed quantities use a linear y-axis and, when useful, a thin zero guide.
* Refinement sequences such as 16, 32, 64, ... use a true base-2 logarithmic
  x-axis while retaining the physical values as tick labels.
* Parameter scans containing zero, such as redistancing iterations, use their
  true linear coordinates rather than categorical spacing or a log axis.

Insets, twin axes, dense 2 x 4 layouts, decorative shading, arrows, and
explanatory text boxes are not part of this style contract.
"""

from __future__ import annotations

import math
from numbers import Integral
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import scienceplots  # noqa: F401  # registers the shared base styles
from matplotlib.figure import Figure


MM_TO_INCH = 1.0 / 25.4
SINGLE_COLUMN_MM = 90.0
DOUBLE_COLUMN_MM = 190.0
# Single source for the formal export resolution; the submission gate in
# manuscript_figures.py imports this rather than restating it.
EXPORT_DPI = 600
MIN_VISIBLE_TEXT_PT = 8.5
CANVAS_QUANTIZATION_TOLERANCE_MM = 0.15

BODY_TEXT_PT = 9.0
AXIS_LABEL_PT = 10.0
PANEL_LABEL_PT = 10.0
# Matplotlib renders mathematical superscripts/subscripts at roughly 70% of
# their parent text size.  A 10 pt parent therefore leaves about 7 pt in the
# source artwork and at least 6.7 pt after final journal placement, safely
# above Elsevier's 6 pt finished-size guidance.
MATH_TEXT_PT = 10.0
TITLE_TEXT_PT = MATH_TEXT_PT
TICK_TEXT_PT = 8.5
LEGEND_TEXT_PT = 8.5

METHOD_ORDER = ("Reference", "VOF-HF", "CLSVOF", "CLSVOF-NN")

# Internal dataset keys and export-only tags are normalized here before they
# can reach figure-facing text or method styling.  In particular,
# ``nn-crossing`` is an allowed filename/source tag, never a display name.
METHOD_LABEL_ALIASES = {
    "Reference": "Reference",
    "reference": "Reference",
    "VOF-HF": "VOF-HF",
    "vof-hf": "VOF-HF",
    "vof_hf": "VOF-HF",
    "CLSVOF": "CLSVOF",
    "clsvof": "CLSVOF",
    "native": "CLSVOF",
    "CLSVOF-NN": "CLSVOF-NN",
    "clsvof-nn": "CLSVOF-NN",
    "NN": "CLSVOF-NN",
    "nn": "CLSVOF-NN",
    "nn_cell_offset": "CLSVOF-NN",
    "nn-crossing": "CLSVOF-NN",
}

METHOD_STYLE: dict[str, dict[str, Any]] = {
    "Reference": {
        "color": "black",
        "marker": None,
        "linestyle": ":",
        "linewidth": 1.1,
    },
    "VOF-HF": {
        "color": "#C99700",
        "marker": "^",
        "linestyle": "--",
    },
    "CLSVOF": {
        "color": "#4477AA",
        "marker": "o",
        "linestyle": "-",
    },
    "CLSVOF-NN": {
        "color": "#EE6677",
        "marker": "s",
        "linestyle": "-",
    },
}

# Guidance only: ``figure_size`` does not enforce these height intervals.
HEIGHT_GUIDANCE_MM = {
    "single_panel": (60.0, 68.0),
    "one_by_two": (65.0, 75.0),
    "one_by_three": (55.0, 65.0),
    "two_by_two": (105.0, 125.0),
    "two_by_three": (110.0, 130.0),
}

FIELD_CMAP = {
    "nonnegative": "viridis",
    "signed": "RdBu_r",
    "vof_fraction": "viridis",
}
VOF_FRACTION_LIMITS = (0.0, 1.0)
INTERFACE_COLOR = "#222222"
INTERFACE_LINEWIDTH_PT = (0.8, 1.0)

# Use with ``ax.text(transform=ax.transAxes, s="(a)", **PANEL_LABEL_STYLE)``.
PANEL_LABEL_STYLE: dict[str, Any] = {
    "x": -0.12,
    "y": 1.04,
    "fontsize": PANEL_LABEL_PT,
    "fontweight": "bold",
    "ha": "left",
    "va": "bottom",
}


def apply_cfd_style() -> None:
    """Apply the Computers & Fluids/Elsevier manuscript overrides to Matplotlib.

    This is the only supported style entry point.  It applies the registered
    ``science``/``no-latex`` base and then the authoritative CFD overrides.
    """

    plt.style.use(["science", "no-latex"])
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.family": "serif",
            "font.serif": ["Times New Roman"],
            "font.size": BODY_TEXT_PT,
            "mathtext.fontset": "stix",
            "text.usetex": False,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "svg.hashsalt": "cfd-computers-fluids-elsevier-figure-style-v3",
            "axes.labelsize": AXIS_LABEL_PT,
            "axes.titlesize": TITLE_TEXT_PT,
            "axes.linewidth": 0.8,
            "axes.grid": False,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "axes.unicode_minus": True,
            "xtick.labelsize": TICK_TEXT_PT,
            "ytick.labelsize": TICK_TEXT_PT,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
            "xtick.major.size": 3.5,
            "ytick.major.size": 3.5,
            "xtick.minor.size": 2.0,
            "ytick.minor.size": 2.0,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.minor.width": 0.6,
            "ytick.minor.width": 0.6,
            "lines.linewidth": 1.2,
            "lines.markersize": 4.5,
            "lines.solid_capstyle": "round",
            "legend.fontsize": LEGEND_TEXT_PT,
            "legend.frameon": False,
            "legend.numpoints": 1,
            "savefig.dpi": EXPORT_DPI,
            "savefig.bbox": None,
            "savefig.pad_inches": 0.0,
            "savefig.facecolor": "white",
            "savefig.transparent": False,
            "figure.autolayout": False,
            "figure.constrained_layout.use": False,
        }
    )


def figure_size(width: str, height_mm: float) -> tuple[float, float]:
    """Return an exact 90 mm or 190 mm canvas size in inches.

    Height remains figure-specific and is only required to be finite and
    positive.  ``HEIGHT_GUIDANCE_MM`` contains non-binding starting ranges.
    """

    widths = {
        "single": SINGLE_COLUMN_MM,
        "double": DOUBLE_COLUMN_MM,
    }
    if width not in widths:
        raise ValueError(f"Unknown figure width: {width!r}")
    try:
        height = float(height_mm)
    except (TypeError, ValueError) as exc:
        raise ValueError("height_mm must be a finite positive number") from exc
    if not math.isfinite(height) or height <= 0.0:
        raise ValueError("height_mm must be a finite positive number")
    return widths[width] * MM_TO_INCH, height * MM_TO_INCH


def canonical_method_label(method: str) -> str:
    """Return the only allowed figure-facing label for a method identifier."""

    try:
        return METHOD_LABEL_ALIASES[method]
    except KeyError as exc:
        raise ValueError(
            f"Unknown CFD method: {method!r}; expected one of "
            f"{tuple(METHOD_LABEL_ALIASES)}"
        ) from exc


def _method_style(method: str) -> dict[str, Any]:
    return dict(METHOD_STYLE[canonical_method_label(method)])


def _finish_marker_style(
    style: dict[str, Any], *, marker_size: float, marker_edge_width: float
) -> dict[str, Any]:
    if style.get("marker") is None:
        for key in (
            "markerfacecolor",
            "markeredgecolor",
            "markeredgewidth",
            "markersize",
            "markevery",
        ):
            style.pop(key, None)
        return style
    style.setdefault("markerfacecolor", "white")
    style.setdefault("markeredgecolor", style["color"])
    style.setdefault("markeredgewidth", marker_edge_width)
    style.setdefault("markersize", marker_size)
    return style


def style_time_series(
    method: str,
    n_points: int,
    marker_count: int = 10,
    **overrides: Any,
) -> dict[str, Any]:
    """Return plot kwargs for a time history with sparse markers.

    Numerical curves receive exactly ``marker_count`` marker indices whenever
    at least that many samples exist; otherwise every available point is
    marked.  ``marker_count`` is restricted to the style-v1 range of 8--12.
    """

    if isinstance(n_points, bool) or not isinstance(n_points, Integral):
        raise ValueError("n_points must be a positive integer")
    if n_points <= 0:
        raise ValueError("n_points must be a positive integer")
    if (
        isinstance(marker_count, bool)
        or not isinstance(marker_count, Integral)
        or not 8 <= marker_count <= 12
    ):
        raise ValueError("marker_count must be an integer from 8 to 12")

    style = _method_style(method)
    style.setdefault("linewidth", 1.2)
    style.update(overrides)
    style = _finish_marker_style(
        style, marker_size=4.5, marker_edge_width=0.9
    )
    if style.get("marker") is not None:
        count = min(int(marker_count), int(n_points))
        if count == 1:
            indices = [0]
        else:
            indices = [
                round(index * (n_points - 1) / (count - 1))
                for index in range(count)
            ]
        style.setdefault("markevery", indices)
    return style


def style_discrete_series(method: str, **overrides: Any) -> dict[str, Any]:
    """Return plot kwargs for a grid or numerical-parameter series."""

    style = _method_style(method)
    style.setdefault("linewidth", 1.2)
    style.update(overrides)
    return _finish_marker_style(
        style, marker_size=5.0, marker_edge_width=1.0
    )


def save_figure(fig: Figure, output_stem: str | Path) -> Path:
    """Save one exact-width, opaque 600 dpi PNG.

    ``output_stem`` must be suffix-free.  The function preserves the original
    canvas, does not apply a tight bounding box, and intentionally leaves figure
    closing to the caller.  PDF/SVG/TIFF are opt-in exports outside the formal
    repository default.
    """

    stem = Path(output_stem)
    if not stem.name or stem.suffix:
        raise ValueError("output_stem must be a suffix-free file stem")

    width_mm = float(fig.get_figwidth()) / MM_TO_INCH
    canonical_width = next(
        (
            expected
            for expected in (SINGLE_COLUMN_MM, DOUBLE_COLUMN_MM)
            if math.isclose(
                width_mm,
                expected,
                rel_tol=0.0,
                abs_tol=CANVAS_QUANTIZATION_TOLERANCE_MM,
            )
        ),
        None,
    )
    if canonical_width is None:
        raise ValueError(
            "figure width must be exactly 90 mm (single) or 190 mm (double); "
            f"received {width_mm:.6g} mm"
        )
    if not math.isfinite(float(fig.get_figheight())) or fig.get_figheight() <= 0.0:
        raise ValueError("figure height must be finite and positive")

    # Some GUI canvas managers round a requested figsize to 0.01 inch.  Accept
    # only that narrow, known quantization and restore the exact journal width
    # without forwarding another resize to the GUI manager.
    fig.set_size_inches(
        canonical_width * MM_TO_INCH,
        fig.get_figheight(),
        forward=False,
    )

    stem.parent.mkdir(parents=True, exist_ok=True)
    png_path = stem.with_suffix(".png")

    fig.savefig(
        png_path,
        format="png",
        dpi=EXPORT_DPI,
        bbox_inches=None,
        pad_inches=0.0,
        facecolor="white",
        transparent=False,
        metadata={"Software": "Matplotlib + CFD Computers & Fluids/Elsevier Figure Style v2"},
    )
    return png_path


def save_pdf_figure(fig: Figure, output_path: str | Path) -> Path:
    """Save one opt-in PDF with embedded TrueType fonts and a fixed canvas."""

    path = Path(output_path)
    if path.suffix.lower() != ".pdf":
        raise ValueError("output_path must have a .pdf suffix")
    path.parent.mkdir(parents=True, exist_ok=True)

    with plt.rc_context({"pdf.fonttype": 42}):
        fig.savefig(
            path,
            format="pdf",
            bbox_inches=None,
            pad_inches=0.0,
            facecolor="white",
            transparent=False,
            metadata={
                "Title": path.stem,
                "Creator": "Matplotlib + CFD Computers & Fluids/Elsevier Figure Style v2",
                "CreationDate": None,
            },
        )
    return path


def save_figure_pdf(fig: Figure, output_stem: str | Path) -> Path:
    """Save one exact-width vector PDF when explicitly requested.

    The PDF uses the same fixed canvas and opaque white background as the
    formal PNG export.  Text is embedded as TrueType through ``pdf.fonttype``
    in :func:`apply_cfd_style` so labels remain selectable and editable.
    """

    stem = Path(output_stem)
    if not stem.name or stem.suffix:
        raise ValueError("output_stem must be a suffix-free file stem")

    width_mm = float(fig.get_figwidth()) / MM_TO_INCH
    canonical_width = next(
        (
            expected
            for expected in (SINGLE_COLUMN_MM, DOUBLE_COLUMN_MM)
            if math.isclose(
                width_mm,
                expected,
                rel_tol=0.0,
                abs_tol=CANVAS_QUANTIZATION_TOLERANCE_MM,
            )
        ),
        None,
    )
    if canonical_width is None:
        raise ValueError(
            "figure width must be exactly 90 mm (single) or 190 mm (double); "
            f"received {width_mm:.6g} mm"
        )
    if not math.isfinite(float(fig.get_figheight())) or fig.get_figheight() <= 0.0:
        raise ValueError("figure height must be finite and positive")

    fig.set_size_inches(
        canonical_width * MM_TO_INCH,
        fig.get_figheight(),
        forward=False,
    )

    stem.parent.mkdir(parents=True, exist_ok=True)
    pdf_path = stem.with_suffix(".pdf")
    fig.savefig(
        pdf_path,
        format="pdf",
        bbox_inches=None,
        pad_inches=0.0,
        facecolor="white",
        transparent=False,
        metadata={
            "Creator": "Matplotlib + CFD Computers & Fluids/Elsevier Figure Style v2",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    return pdf_path


def save_figure_svg(fig: Figure, output_stem: str | Path) -> Path:
    """Save one exact-width SVG with editable text and a fixed canvas."""

    stem = Path(output_stem)
    if not stem.name or stem.suffix:
        raise ValueError("output_stem must be a suffix-free file stem")

    width_mm = float(fig.get_figwidth()) / MM_TO_INCH
    canonical_width = next(
        (
            expected
            for expected in (SINGLE_COLUMN_MM, DOUBLE_COLUMN_MM)
            if math.isclose(
                width_mm,
                expected,
                rel_tol=0.0,
                abs_tol=CANVAS_QUANTIZATION_TOLERANCE_MM,
            )
        ),
        None,
    )
    if canonical_width is None:
        raise ValueError(
            "figure width must be exactly 90 mm (single) or 190 mm (double); "
            f"received {width_mm:.6g} mm"
        )
    if not math.isfinite(float(fig.get_figheight())) or fig.get_figheight() <= 0.0:
        raise ValueError("figure height must be finite and positive")

    fig.set_size_inches(
        canonical_width * MM_TO_INCH,
        fig.get_figheight(),
        forward=False,
    )

    stem.parent.mkdir(parents=True, exist_ok=True)
    svg_path = stem.with_suffix(".svg")
    with plt.rc_context(
        {
            "svg.fonttype": "none",
            "svg.hashsalt": "cfd-computers-fluids-elsevier-figure-style-v2",
        }
    ):
        fig.savefig(
            svg_path,
            format="svg",
            bbox_inches=None,
            pad_inches=0.0,
            facecolor="white",
            transparent=False,
            metadata={
                "Title": stem.name,
                "Creator": "Matplotlib + CFD Computers & Fluids/Elsevier Figure Style v2",
                "Date": None,
            },
        )
    return svg_path


def save_manuscript_figure(fig: Figure, output_stem: str | Path) -> tuple[Path, ...]:
    """Export the manuscript's opaque 600 dpi PNG."""
    return (save_figure(fig, output_stem),)
