"""Plot formal Capwave E2 grid convergence."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import MATH_TEXT_PT, apply_cfd_style, figure_size, save_figure, style_discrete_series
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FixedLocator, LogFormatterMathtext, LogLocator, NullFormatter
from data_paths import run_dir
A0 = 0.01
RESOLUTIONS = (32, 64, 128, 256, 512)
METHODS = ('VOF-HF', 'CLSVOF', 'CLSVOF-NN')
PLOT_ZORDER = {'VOF-HF': 3, 'CLSVOF': 3, 'CLSVOF-NN': 4}
PLOT_Y_LIMITS = (0.0003, 0.14)
OUTPUT_STEM = HERE / 'capwave_e2_grid_convergence_float64-forward'

def load_e2(resolution, method):
    series = pd.read_csv(run_dir('capwave', resolution, method) / 'timeseries.csv')
    residual = series['amplitude'].to_numpy(dtype=float) - series['reference_amplitude'].to_numpy(dtype=float)
    return float(np.sqrt(np.mean(np.square(residual))) / A0)

def main():
    apply_cfd_style()
    (fig, ax) = plt.subplots(figsize=figure_size('single', 67.0))
    fig.subplots_adjust(left=0.205, right=0.96, bottom=0.19, top=0.94)
    for method in METHODS:
        ax.plot(
            [n // 2 for n in RESOLUTIONS], [load_e2(n, method) for n in RESOLUTIONS], label=method,
            zorder=PLOT_ZORDER[method], **style_discrete_series(method),
        )
    slope_one_x = np.array([18.0, 256.0])
    slope_one_y = 0.03 * (64.0 / slope_one_x)
    slope_two_x = np.array([16.0, 256.0])
    slope_two_y = 0.024 * np.square(32.0 / slope_two_x)
    ax.plot(slope_one_x, slope_one_y, color='#777777', lw=0.8, ls='--', zorder=1)
    ax.plot(slope_two_x, slope_two_y, color='#777777', lw=0.8, ls=':', zorder=1)
    ax.text(
        89, 0.021, '$O(N_\\lambda^{-1})$', color='#666666', fontsize=MATH_TEXT_PT, rotation=-18,
        ha='left', va='bottom',
    )
    ax.text(
        22, 0.044, '$O(N_\\lambda^{-2})$', color='#666666', fontsize=MATH_TEXT_PT, rotation=-31,
        ha='left', va='top',
    )
    ax.set_xscale('log', base=2)
    ax.set_yscale('log')
    ax.tick_params(axis='y', labelsize=MATH_TEXT_PT)
    ax.set_xlim(14, 290)
    ax.set_ylim(*PLOT_Y_LIMITS)
    major_x = np.array([16.0, 32.0, 64.0, 128.0, 256.0])
    minor_x = np.sqrt(major_x[:-1] * major_x[1:])
    ax.xaxis.set_major_locator(FixedLocator(major_x))
    ax.set_xticklabels(['16', '32', '64', '128', '256'])
    ax.xaxis.set_minor_locator(FixedLocator(minor_x))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_major_locator(LogLocator(base=10.0, subs=(1.0,)))
    ax.yaxis.set_major_formatter(LogFormatterMathtext(base=10.0))
    ax.yaxis.set_minor_locator(LogLocator(base=10.0, subs=(2.0, 5.0)))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel('$N_\\lambda$')
    ax.set_ylabel('$E_2$')
    ax.legend(loc='lower left', handlelength=2.4)
    paths = save_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)


if __name__ == '__main__':
    main()
