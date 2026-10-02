"""Plot the stationary-bubble whole-domain Ca versus grid resolution.

The figure is a grid-resolution diagnostic, not a convergence-order claim.
It compares the VOF-HF reference with the native and learned crossing formulations.
The reported value is the maximum speed over the full computational domain
at tau=2, nondimensionalized as a capillary number."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import MATH_TEXT_PT, apply_cfd_style, figure_size, save_figure, style_discrete_series
import csv
import gzip
from math import hypot, sqrt
import matplotlib.pyplot as plt
from data_paths import run_dir
VISCOSITY = sqrt(0.8 / 12000.0)
SURFACE_TENSION = 1.0
RESOLUTIONS = (32, 64, 128, 256)
OUTPUT_STEM = HERE / 'stationary_bubble_summary-crossing_float64-forward'
FIGURE_HEIGHT_MM = 67.0

def endpoint_ca(method, resolution):
    path = run_dir('stationary_bubble', resolution, method) / 'fields.csv.gz'
    with gzip.open(path, 'rt', newline='', encoding='utf-8') as stream:
        speed = max(
            (hypot(float(row['u_x']), float(row['u_y'])) for row in csv.DictReader(stream) if row['snapshot'] == 'final'),
        )
    return VISCOSITY * speed / SURFACE_TENSION

def main():
    apply_cfd_style()
    methods = ('VOF-HF', 'CLSVOF', 'CLSVOF-NN')
    (fig, ax) = plt.subplots(figsize=figure_size('single', height_mm=FIGURE_HEIGHT_MM))
    fig.subplots_adjust(left=0.2, right=0.955, bottom=0.2, top=0.78)
    for method in methods:
        ax.plot(
            RESOLUTIONS, [endpoint_ca(method, n) for n in RESOLUTIONS], label=method,
            **style_discrete_series(method, linewidth=1.08),
        )
    ax.set_xscale('log', base=2)
    ax.set_yscale('log')
    ax.tick_params(axis='y', labelsize=MATH_TEXT_PT)
    ax.set_xlim(29.5, 278.0)
    ax.set_ylim(8e-18, 1e-14)
    ax.set_xticks(RESOLUTIONS)
    ax.set_xticklabels([str(value) for value in RESOLUTIONS])
    ax.tick_params(axis='x', which='minor', bottom=False, top=False)
    ax.set_xlabel('$N$')
    ax.set_ylabel('$\\mathrm{Ca}_{\\max}$')
    ax.legend(
        loc='lower center', bbox_to_anchor=(0.48, 1.02), ncol=3, columnspacing=1.3, handlelength=1.8,
        handletextpad=0.4, frameon=False,
    )
    paths = save_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)
    return paths


if __name__ == '__main__':
    main()
