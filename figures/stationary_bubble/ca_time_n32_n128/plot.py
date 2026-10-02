"""Figure 9 and its FP32 counterpart: one N32/N128 layout, two data sources."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (
    MATH_TEXT_PT, PANEL_LABEL_STYLE, apply_cfd_style, figure_size, save_figure, style_time_series,
)
import csv
import matplotlib.pyplot as plt
import numpy as np
from data_paths import run_dir
RESOLUTIONS = (32, 128)
METHODS = ('VOF-HF', 'CLSVOF', 'CLSVOF-NN')
PRECISIONS = ('float64-forward', 'float32')
DISPLAY_TAU = np.linspace(0, 2, 181)

def source_path(resolution, method, precision):
    directory = run_dir('stationary_bubble', resolution, method, precision=precision)
    filename = 'whole_domain_timeseries.csv' if method == 'CLSVOF-NN' and precision == 'float64-forward' else 'timeseries.csv'
    return directory / filename

def load_display_samples(path):
    """Identical native-sample selection for both inference precisions."""
    with path.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    tau = np.asarray([float(row['tau']) for row in rows])
    ca = np.asarray([float(row['capillary_number']) for row in rows])
    right = np.clip(np.searchsorted(tau, DISPLAY_TAU), 0, len(tau) - 1)
    left = np.maximum(right - 1, 0)
    choose_left = np.abs(tau[left] - DISPLAY_TAU) <= np.abs(tau[right] - DISPLAY_TAU)
    indices = np.unique(np.concatenate((np.where(choose_left, left, right), [int(np.argmax(ca)), len(tau) - 1])))
    indices = indices[ca[indices] > 0]
    return (tau[indices], ca[indices])

def draw_histories(traces, limits, output_stem):
    """One drawing implementation: precision never selects a different layout or style."""
    apply_cfd_style()
    (fig, axes) = plt.subplots(1, 2, figsize=figure_size('double', 82))
    fig.subplots_adjust(left=0.095, right=0.97, bottom=0.2, top=0.76, wspace=0.24)
    for (index, (ax, n)) in enumerate(zip(axes, RESOLUTIONS)):
        for method in METHODS:
            (tau, ca) = traces[n, method]
            ax.plot(tau, ca, label=method, **style_time_series(method))
        ax.set(
            xlim=(0, 2), yscale='log', ylim=limits[n], xticks=np.arange(0, 2.001, 0.25),
            xlabel='$\\tau$',
        )
        ax.tick_params(axis='y', labelsize=MATH_TEXT_PT)
        if index == 0:
            ax.set_ylabel('$\\mathrm{Ca}_{\\max}$')
        ax.set_title(f'$N={n}$', pad=7)
        ax.text(s=f'({chr(97 + index)})', transform=ax.transAxes, **PANEL_LABEL_STYLE)
    fig.legend(
        *axes[0].get_legend_handles_labels(), loc='upper center', bbox_to_anchor=(0.53, 0.95), ncol=3,
        columnspacing=1.8, handlelength=2.3, handletextpad=0.7, borderaxespad=0,
    )
    outputs = save_figure(fig, output_stem)
    plt.close(fig)
    return outputs

def main():
    paths = {(p, n, m): source_path(n, m, p) for p in PRECISIONS for n in RESOLUTIONS for m in METHODS}
    samples = {path: load_display_samples(path) for path in set(paths.values())}
    limits = {n: (
        min((samples[paths[p, n, m]][1].min() for p in PRECISIONS for m in METHODS)) / 5,
        max((samples[paths[p, n, m]][1].max() for p in PRECISIONS for m in METHODS)) * 5,
    ) for n in RESOLUTIONS}
    for precision in PRECISIONS:
        traces = {(n, m): samples[paths[precision, n, m]] for n in RESOLUTIONS for m in METHODS}
        stem = HERE / f'stationary_ca_N32_N128_crossing_{precision}'
        for path in draw_histories(traces, limits, stem):
            print(path)


if __name__ == '__main__':
    main()
