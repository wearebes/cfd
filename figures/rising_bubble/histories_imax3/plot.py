"""Case 2 rising-bubble histories at a selected grid (default N=256), imax/steps=3."""
from pathlib import Path
import argparse
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (
    apply_cfd_style, figure_size, save_figure, style_time_series, BODY_TEXT_PT, PANEL_LABEL_STYLE,
)
from data_paths import ROOT, run_dir
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
TIME = np.arange(0, 3.0 + 0.0025, 0.005)
METHODS = ('VOF-HF', 'CLSVOF', 'CLSVOF-NN')
METRICS = (
    ('center_of_mass_x', 'Vertical centroid, $y_c$', '$y_c$', (0.48, 1.16), 3),
    ('rise_velocity_x', 'Mean rise velocity, $v_c$', '$v_c$', (-0.01, 0.27), 4),
    ('circularity', 'Circularity, $\\mathcal{C}$', '$\\mathcal{C}$', (0.43, 1.02), 2),
)

def main(domain='half', resolution=256):
    raw = np.loadtxt(ROOT / 'dataset/rising_bubble/case2/reference/hysing/history.dat')
    ref = np.vstack(([[0, 0, 1, 0.5, 0]], raw))
    curves = {method: pd.read_csv(run_dir('rising_bubble', resolution, method, case_id=2, domain=domain) / 'timeseries.csv') for method in METHODS}
    apply_cfd_style()
    (fig, axes) = plt.subplots(1, 3, figsize=figure_size('double', 65))
    fig.subplots_adjust(left=0.085, right=0.975, bottom=0.2, top=0.73, wspace=0.3)
    for (column, (ax, (metric, title, ylabel, ylim, ref_column))) in enumerate(zip(axes, METRICS)):
        for (index, (method, frame)) in enumerate(curves.items()):
            ax.plot(
                TIME, np.interp(TIME, frame.time, frame[metric]), zorder=2 + index,
                **style_time_series(method, linewidth=1.15, alpha=1.0),
            )
        ax.plot(
            TIME, np.interp(TIME, ref[:, 0], ref[:, ref_column]), label='Reference', zorder=10,
            **style_time_series('Reference', linewidth=1.1, alpha=0.78),
        )
        ax.set(xlim=(0, 3), ylim=ylim, xlabel='$t$', ylabel=ylabel)
        ax.set_title(title, pad=4)
        ax.text(s=f'({chr(97 + column)})', transform=ax.transAxes, **PANEL_LABEL_STYLE)
    label = 'Test Case 2' if resolution == 256 else f'Test Case 2, $N={resolution}$'
    fig.text(0.025, 0.46, label, rotation=90, ha='center', va='center', fontsize=BODY_TEXT_PT)
    handles = [Line2D([0], [0], label=method, **style_time_series(method, linewidth=width)) for (method, width) in (('Reference', 1.1), *((m, 1.15) for m in METHODS))]
    fig.legend(
        handles=handles, loc='upper center', bbox_to_anchor=(0.54, 0.94), ncol=4, handlelength=2.0,
        columnspacing=1.2, borderaxespad=0,
    )
    suffix = '_whole-domain' if domain == 'whole' else ''
    if resolution != 256:
        suffix += f'_N{resolution:04d}'
    print(save_figure(fig, HERE / f'histories_imax3_case2{suffix}_float64-forward'))
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', choices=('half', 'whole'), default='half')
    parser.add_argument('--resolution', type=int, choices=(32, 64, 128, 256, 512), default=256)
    args = parser.parse_args()
    main(args.domain, args.resolution)
