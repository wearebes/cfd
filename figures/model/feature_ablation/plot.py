"""Appendix input ablation: five N_train=32 models on Circle and Flower."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import apply_cfd_style, figure_size, PANEL_LABEL_STYLE, save_figure
import csv
import os
import matplotlib.pyplot as plt
ROOT = HERE.parents[2]
PINN = Path(os.environ.get('CFD_PINN_ROOT', ROOT.parent / 'PINN'))
OLD = PINN / 'tem/center_normal_comparison/paper_aligned'
LOCAL = PINN / 'tem/local_normal_comparison/results'
DIMS = (9, 11, 15, 19, 27)
COLORS = {9: '#CC79A7', 11: '#E69F00', 15: '#D55E00', 19: '#009E73', 27: '#0072B2', 'FD': '#222222'}

def read_metrics(kind):

    def read(path):
        with path.open(newline='') as stream:
            return list(csv.DictReader(stream))
    old = read(OLD / f'{kind}_metrics.csv')
    local = read(LOCAL / f'{kind}_metrics.csv')
    rows = [r for r in old if r['method'] == 'FD' or (int(float(r['train_N'])) == 32 and int(float(r['input_dim'])) in (9, 11, 19, 27))]
    rows += [r for r in local if r['method'] == '15D train 32']
    return rows

def main():
    (circle, flower) = (read_metrics('circle'), read_metrics('flower'))
    apply_cfd_style()
    (fig, axes) = plt.subplots(1, 3, figsize=figure_size('double', 66))
    fig.subplots_adjust(left=0.095, right=0.98, bottom=0.22, top=0.76, wspace=0.34)
    panels = [
        (circle, None, 'Circle (SDF)'), (flower, 'smooth', 'Smooth flower'),
        (flower, 'acute', 'Acute flower'),
    ]
    for (index, (ax, (rows, family, title))) in enumerate(zip(axes, panels)):
        xkey = 'r_over_h' if family is None else 'step'
        for dim in (*DIMS, 'FD'):
            method = 'FD' if dim == 'FD' else f'{dim}D train 32'
            selected = sorted(
                (r for r in rows if r['method'] == method and (family is None or r['family'] == family)),
                key=lambda r: float(r[xkey]),
            )
            x = [float(r[xkey]) for r in selected]
            y = [float(r['mse']) for r in selected]
            label = '9D ($\\phi/h$)' if dim == 9 else str(dim) if dim == 'FD' else f'{dim}D'
            ax.plot(
                x, y, label=label, color=COLORS[dim],
                marker='o', markersize=1.8, markerfacecolor='white', markeredgewidth=0.5,
                linestyle=':' if dim == 'FD' else '-', linewidth=1.2,
            )
        ax.set_yscale('log')
        ax.set_ylabel('MSE of $h\\kappa$')
        if family is None:
            ax.set_xscale('log')
            ax.set_xlabel('$R/h$')
        else:
            ax.set_xlim(0, 30)
            ax.set_xticks([0, 10, 20, 30])
            ax.set_xlabel('Reinitialization step')
        ax.set_title(title, pad=6)
        ax.text(s=f'({chr(97 + index)})', transform=ax.transAxes, **PANEL_LABEL_STYLE)
    fig.legend(
        *axes[0].get_legend_handles_labels(), loc='upper center', bbox_to_anchor=(0.53, 0.975), ncol=6,
        handlelength=2.2, columnspacing=1.15,
    )
    print(save_figure(fig, HERE / 'feature_ablation_N32'))
    plt.close(fig)


if __name__ == '__main__':
    main()
