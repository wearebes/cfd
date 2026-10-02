"""Stationary-bubble velocity fields: three methods at N=32 and tau=1."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (
    apply_cfd_style, figure_size, save_figure, FIELD_CMAP, INTERFACE_COLOR, INTERFACE_LINEWIDTH_PT,
    MATH_TEXT_PT, PANEL_LABEL_STYLE,
)
from data_paths import run_dir
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd
METHODS = ('VOF-HF', 'CLSVOF', 'CLSVOF-NN')

def load_field(method):
    frame = pd.read_csv(
        run_dir('stationary_bubble', 32, method) / 'fields.csv.gz', float_precision='round_trip',
    )
    frame = frame[frame.snapshot == 'middle'].sort_values(['y', 'x'])
    (ux, uy, phase) = (frame[key].to_numpy().reshape(32, 32) for key in ('u_x', 'u_y', 'phase_fraction'))
    return (np.unique(frame.x), np.unique(frame.y), ux, uy, np.hypot(ux, uy), phase)

def arrows(ax, x, y, ux, uy, speed):
    sample = np.s_[2::4, 2::4]
    (xx, yy) = np.meshgrid(x, y)
    magnitude = np.ma.masked_less(speed[sample], 1e-17)
    ax.quiver(
        xx[sample], yy[sample], ux[sample] / magnitude, uy[sample] / magnitude, angles='xy',
        scale_units='xy', scale=18.0, pivot='mid', color='white', edgecolor=INTERFACE_COLOR,
        linewidth=0.3, width=0.006, headwidth=3.5, headlength=4.5, headaxislength=4.0, zorder=4,
    )

def main():
    apply_cfd_style()
    (fig, axes) = plt.subplots(1, 3, figsize=figure_size('double', 64), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.065, right=0.9, bottom=0.19, top=0.84, wspace=0.1)
    edges = np.linspace(0, 1, 33)
    for (index, (ax, method)) in enumerate(zip(axes, METHODS)):
        (x, y, ux, uy, speed, phase) = load_field(method)
        mesh = ax.pcolormesh(
            edges, edges, speed, cmap=FIELD_CMAP['nonnegative'],
            norm=LogNorm(vmin=1e-18, vmax=1e-08, clip=True), shading='flat',
        )
        ax.contour(
            x, y, phase, levels=[0.5], colors=INTERFACE_COLOR,
            linewidths=INTERFACE_LINEWIDTH_PT,
        )
        arrows(ax, x, y, ux, uy, speed)
        ax.set(
            aspect='equal', xlim=(0, 1), ylim=(0, 1), xticks=(0, 0.5, 1), yticks=(0, 0.5, 1),
            xlabel='$x$',
        )
        ax.set_title(method, pad=5)
        ax.text(s=f'({chr(97 + index)})', transform=ax.transAxes, **PANEL_LABEL_STYLE)
    axes[0].set_ylabel('$y$')
    colorbar = fig.colorbar(mesh, cax=fig.add_axes((0.917, 0.215, 0.018, 0.565)))
    colorbar.ax.set_title('$|\\mathbf{u}|$', pad=5)
    colorbar.ax.tick_params(direction='in', length=3.0, labelsize=MATH_TEXT_PT)
    stem = HERE / 'velocity_field_N32_tau1_vof-hf_clsvof-crossing_nn-crossing_float64-forward'
    print(save_figure(fig, stem))
    plt.close(fig)


if __name__ == '__main__':
    main()
