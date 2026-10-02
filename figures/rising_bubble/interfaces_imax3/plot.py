"""Case 1 and Case 2 final interfaces, with five grids and the Hysing reference."""
from pathlib import Path
import argparse
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (
    apply_cfd_style, figure_size, save_figure, BODY_TEXT_PT, LEGEND_TEXT_PT, PANEL_LABEL_STYLE,
)
from data_paths import ROOT, run_dir
import contourpy
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
METHODS = ('VOF-HF', 'CLSVOF', 'CLSVOF-NN')
COLORS = {32: '#E69F00', 64: '#0072B2', 128: '#D62728', 256: '#009E73', 512: '#7A3DB8'}
REFERENCE_STYLE = dict(color='black', linestyle=(0, (4.0, 2.5)), lw=1.5)
AXES = {
    1: ((-0.4, 0.4), (0.88, 1.38), (-0.4, -0.2, 0, 0.2, 0.4), (0.9, 1, 1.1, 1.2, 1.3)),
    2: ((-0.4, 0.4), (0.58, 1.38), (-0.4, -0.2, 0, 0.2, 0.4), (0.6, 0.8, 1, 1.2, 1.4)),
    'zoom': ((0.18, 0.4), (0.58, 1.06), (0.2, 0.3, 0.4), (0.6, 0.8, 1)),
}

def reference_curve(case):
    points = np.loadtxt(ROOT / f'dataset/rising_bubble/case{case}/reference/hysing/interface.dat')
    points[:, 0] -= 0.5
    return points[np.r_[True, np.any(np.diff(points, axis=0) != 0, axis=1)]]

def phase_fraction_contour(case, resolution, method, domain='half'):
    path = run_dir('rising_bubble', resolution, method, case_id=case, domain=domain) / 'fields.csv.gz'
    frame = pd.read_csv(path, usecols=['snapshot', 'x', 'y', 'phase_fraction'], float_precision='round_trip')
    field = frame[frame.snapshot == 'final'].pivot(index='x', columns='y', values='phase_fraction')
    (y, x) = (field.index.to_numpy(), field.columns.to_numpy())
    values = field.to_numpy()
    if domain == 'half':
        x, values = np.r_[-x[::-1], x], np.concatenate((values[:, ::-1], values), axis=1)
    contour = contourpy.contour_generator(
        x=x, y=y, z=values, name='serial',
        line_type='Separate',
    )
    return contour.lines(0.5)[0]

def panel(ax, reference, curves, view):
    ax.plot(reference[:, 0], reference[:, 1], zorder=5.5, **REFERENCE_STYLE)
    for (n, curve) in curves.items():
        ax.plot(
            curve[:, 0], curve[:, 1], color=COLORS[n], linestyle='-', lw=1.2,
            zorder=2 + list(COLORS).index(n),
        )
    (xlim, ylim, xticks, yticks) = AXES[view]
    ax.set_xticks(xticks)
    ax.set_yticks(yticks)
    ax.set(xlim=xlim, ylim=ylim, aspect='equal', adjustable='box')
    ax.tick_params(pad=1.3)
    if view == 'zoom':
        ax.minorticks_off()
    for spine in ax.spines.values():
        spine.set(visible=True, linewidth=0.8, color='black')

def legend(fig):
    ref = fig.legend(
        handles=[Line2D([0], [0], label='Reference', **REFERENCE_STYLE)], loc='upper center',
        bbox_to_anchor=(0.255, 0.94), handlelength=2.35, handletextpad=0.55,
    )
    grids = fig.legend(
        handles=[Line2D([0], [0], color=color, linestyle='-', lw=1.2, label=str(n)) for (n, color) in COLORS.items()],
        loc='upper center', bbox_to_anchor=(0.675, 0.94), ncol=5, handlelength=2.35,
        handletextpad=0.55, columnspacing=1.0,
    )
    fig.canvas.draw()
    boxes = [item.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted()) for item in (ref, grids)]
    center_y = 0.25 * (boxes[0].y0 + boxes[0].y1 + boxes[1].y0 + boxes[1].y1)
    fig.text(0.35, center_y, 'Grid resolution:', ha='left', va='center', fontsize=LEGEND_TEXT_PT)

def case1(curves, reference):
    fig = plt.figure(figsize=figure_size('double', 60))
    grid = fig.add_gridspec(1, 3, left=0.075, right=0.965, bottom=0.12, top=0.72, wspace=0.18)
    axes = []
    for (column, method) in enumerate(METHODS):
        ax = fig.add_subplot(grid[0, column])
        axes.append(ax)
        panel(ax, reference, {n: curves[method, n] for n in COLORS}, 1)
        ax.set_title(method, pad=4)
        ax.text(s=f'({chr(97 + column)})', transform=ax.transAxes, **PANEL_LABEL_STYLE)
        ax.tick_params(axis='y', labelleft=column == 0)
    axes[0].set_ylabel('$y$')
    axes[1].set_xlabel('$x$')
    for ax in axes:
        ax.set_anchor('N')
    legend(fig)
    return fig

def case2(curves, reference):
    fig = plt.figure(figsize=figure_size('double', 160))
    outer = fig.add_gridspec(3, 1, left=0.065, right=0.975, bottom=0.065, top=0.88, hspace=0.18)
    (overall, zooms) = ([], [])
    for (row, method) in enumerate(METHODS):
        grid = outer[row].subgridspec(1, 6, width_ratios=(2.15, 1, 1, 1, 1, 1), wspace=0.1)
        ax = fig.add_subplot(grid[0, 0])
        zoom = [fig.add_subplot(grid[0, j]) for j in range(1, 6)]
        overall.append(ax)
        zooms.append(zoom)
        panel(ax, reference, {n: curves[method, n] for n in COLORS}, 2)
        (xlim, ylim, _, _) = AXES['zoom']
        ax.add_patch(
            Rectangle(
                (xlim[0], ylim[0]), xlim[1] - xlim[0], ylim[1] - ylim[0], fill=False,
                edgecolor='#666666', linewidth=0.8, linestyle=(0, (2.5, 1.8)), zorder=10,
            ),
        )
        ax.text(s=f'({chr(97 + row)})', transform=ax.transAxes, **PANEL_LABEL_STYLE)
        ax.text(
            0.02, 1.035, method, transform=ax.transAxes, ha='left', va='bottom', fontsize=BODY_TEXT_PT,
        )
        ax.set_ylabel('$y$')
        ax.tick_params(axis='x', labelbottom=row == 2)
        for (column, (n, zoom_ax)) in enumerate(zip(COLORS, zoom)):
            panel(zoom_ax, reference, {n: curves[method, n]}, 'zoom')
            if row == 0:
                zoom_ax.set_title(f'$N={n}$', pad=3)
            zoom_ax.tick_params(axis='y', labelleft=column == 0)
            zoom_ax.tick_params(axis='x', labelbottom=row == 2)
    overall[-1].set_xlabel('$x$')
    fig.canvas.draw()
    center_y = 0.5 * (overall[0].get_position().y1 + overall[-1].get_position().y0)
    fig.text(
        0.025, center_y, 'Test Case 2', rotation=90, ha='center', va='center', fontsize=BODY_TEXT_PT,
    )
    (left, right) = (zooms[-1][0].get_position(), zooms[-1][-1].get_position())
    fig.text(0.5 * (left.x0 + right.x1), left.y0 - 0.025, '$x$', ha='center', va='top')
    legend(fig)
    return fig


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', choices=('half', 'whole'), default='half')
    args = parser.parse_args()
    suffix = '_whole-domain' if args.domain == 'whole' else ''
    apply_cfd_style()
    for (case, draw) in ((1, case1), (2, case2)):
        curves = {(m, n): phase_fraction_contour(case, n, m, args.domain) for m in METHODS for n in COLORS}
        fig = draw(curves, reference_curve(case))
        print(save_figure(fig, HERE / f'interfaces_case{case}{suffix}_float64-forward'))
        plt.close(fig)
