"""Plot representative Capwave amplitude histories from formal result rows."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import PANEL_LABEL_STYLE, apply_cfd_style, figure_size, save_figure, style_time_series
import matplotlib.pyplot as plt
import pandas as pd
from data_paths import run_dir
A0 = 0.01
PANELS = (('a', 32), ('b', 128), ('c', 512))
METHOD_ORDER = ('Prosperetti', 'VOF-HF', 'CLSVOF', 'CLSVOF-NN')
NUMERICAL_LINE_ZORDER = 2
REFERENCE_ZORDER = 3
OUTPUT_STEM = HERE / 'capwave_amplitude_histories_float64-forward'

def main():
    panel_data = {}
    for (_, resolution) in PANELS:
        runs = {method: pd.read_csv(run_dir('capwave', resolution, method) / 'timeseries.csv') for method in ('VOF-HF', 'CLSVOF', 'CLSVOF-NN')}
        anchor = runs['VOF-HF']
        runs['Prosperetti'] = pd.DataFrame({'tau': anchor['tau'], 'amplitude': anchor['reference_amplitude']})
        panel_data[resolution] = runs
    apply_cfd_style()
    (fig, axes_grid) = plt.subplots(1, len(PANELS), figsize=figure_size('double', 65.0), sharey=True, squeeze=False)
    axes = axes_grid[0]
    fig.subplots_adjust(left=0.08, right=0.975, bottom=0.2, top=0.75, wspace=0.2)
    for (ax, (panel, resolution)) in zip(axes, PANELS):
        for method in METHOD_ORDER:
            series = panel_data[resolution][method]
            display_method = 'Reference' if method == 'Prosperetti' else method
            ax.plot(
                series['tau'], series['amplitude'] / A0,
                label='Prosperetti' if method == 'Prosperetti' else display_method,
                zorder=REFERENCE_ZORDER if method == 'Prosperetti' else NUMERICAL_LINE_ZORDER,
                **style_time_series(display_method),
            )
        ax.set_xlim(0.0, 25.0)
        ax.set_ylim(0.0, 1.05)
        ax.set_xticks([0, 5, 10, 15, 20, 25])
        ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xlabel('$\\tau$')
        ax.set_title(f'$N_\\lambda={resolution // 2}$', pad=4)
        ax.text(s=f'({panel})', transform=ax.transAxes, **PANEL_LABEL_STYLE)
    axes[0].set_ylabel('$\\eta^{\\max}/A_0$')
    (handles, labels) = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.95), ncol=4, handlelength=2.8,
        columnspacing=1.4,
    )
    paths = save_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)


if __name__ == '__main__':
    main()
