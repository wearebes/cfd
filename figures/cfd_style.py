"""Shared typography, curve styles and PNG/PDF export for the paper."""
from pathlib import Path
import os
import sys
sys.dont_write_bytecode = True
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/cfd-paper-mpl')
os.environ.setdefault('XDG_CACHE_HOME', '/private/tmp/cfd-paper-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import scienceplots  # registers Matplotlib's science style
MM_TO_INCH = 1.0 / 25.4
SINGLE_COLUMN_MM = 90.0
DOUBLE_COLUMN_MM = 190.0
EXPORT_DPI = 600
BODY_TEXT_PT = 9.0
AXIS_LABEL_PT = 10.0
MATH_TEXT_PT = 10.0
TITLE_TEXT_PT = MATH_TEXT_PT
TICK_TEXT_PT = 8.5
LEGEND_TEXT_PT = 8.5
PANEL_LABEL_PT = 10.0
FIELD_CMAP = {'nonnegative': 'viridis'}
INTERFACE_COLOR = '#222222'
INTERFACE_LINEWIDTH_PT = 0.9
PANEL_LABEL_STYLE = {
    'x': -0.12, 'y': 1.04, 'fontsize': PANEL_LABEL_PT, 'fontweight': 'bold',
    'ha': 'left', 'va': 'bottom',
}
METHOD_STYLE = {
    'Reference': {'color': 'black', 'marker': None, 'linestyle': ':', 'linewidth': 1.1},
    'VOF-HF': {'color': '#C99700', 'marker': None, 'linestyle': '--'},
    'CLSVOF': {'color': '#4477AA', 'marker': None, 'linestyle': '-'},
    'CLSVOF-NN': {'color': '#EE6677', 'marker': None, 'linestyle': '-'},
}

def apply_cfd_style():
    """Apply the paper's fonts, axes and line styles."""
    plt.style.use(['science', 'no-latex'])
    plt.rcParams.update(
        {
            'figure.facecolor': 'white', 'axes.facecolor': 'white', 'font.family': 'serif',
            'font.serif': ['Times New Roman'], 'font.size': BODY_TEXT_PT, 'mathtext.fontset': 'stix',
            'text.usetex': False, 'pdf.fonttype': 42, 'axes.labelsize': AXIS_LABEL_PT,
            'axes.titlesize': TITLE_TEXT_PT, 'axes.linewidth': 0.8, 'axes.grid': False,
            'axes.spines.top': True, 'axes.spines.right': True, 'axes.unicode_minus': True,
            'xtick.labelsize': TICK_TEXT_PT, 'ytick.labelsize': TICK_TEXT_PT, 'xtick.direction': 'in',
            'ytick.direction': 'in', 'xtick.top': True, 'ytick.right': True, 'xtick.major.size': 3.5,
            'ytick.major.size': 3.5, 'xtick.minor.size': 2.0, 'ytick.minor.size': 2.0,
            'xtick.major.width': 0.8, 'ytick.major.width': 0.8, 'xtick.minor.width': 0.6,
            'ytick.minor.width': 0.6, 'lines.linewidth': 1.2, 'lines.markersize': 2.8,
            'lines.solid_capstyle': 'round', 'legend.fontsize': LEGEND_TEXT_PT,
            'legend.frameon': False, 'legend.numpoints': 1, 'savefig.dpi': EXPORT_DPI,
            'savefig.bbox': None, 'savefig.pad_inches': 0.0, 'savefig.facecolor': 'white',
            'savefig.transparent': False, 'figure.autolayout': False,
            'figure.constrained_layout.use': False,
        },
    )

def figure_size(width, height_mm):
    return (
        {'single': SINGLE_COLUMN_MM, 'double': DOUBLE_COLUMN_MM}[width] * MM_TO_INCH,
        height_mm * MM_TO_INCH,
    )


def style_time_series(method, **overrides):
    """Continuous curves use the paper method style without markers."""
    style = dict(METHOD_STYLE[method])
    style.setdefault('linewidth', 1.2)
    style.update(overrides)
    return style

def style_discrete_series(method, **overrides):
    """Grid comparisons use small circles at every observation."""
    style = style_time_series(method, **overrides)
    style.update(
        marker='o', markersize=2.8, markeredgewidth=0.65, markerfacecolor='white',
        markeredgecolor=style['color'],
    )
    return style

def save_figure(fig, output_stem):
    """Export the same artwork as a 600 dpi PNG and a vector PDF."""
    stem = Path(output_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    for ax in fig.axes:
        for collection in ax.collections:
            collection.set_rasterized(False)
    (png, pdf) = (stem.with_suffix('.png'), stem.with_suffix('.pdf'))
    common = dict(bbox_inches=None, pad_inches=0.0, facecolor='white', transparent=False)
    fig.savefig(
        png, format='png', dpi=EXPORT_DPI, **common,
        metadata={'Software': 'Matplotlib + CFD Computers & Fluids/Elsevier Figure Style v2'},
    )
    fig.savefig(
        pdf, format='pdf', **common,
        metadata={'Creator': 'Matplotlib', 'CreationDate': None, 'ModDate': None},
    )
    return (png, pdf)
