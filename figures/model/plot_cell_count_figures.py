"""Render the six paper model-result figures from their existing source tables."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent / 'shared_data'
FIGURES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import MATH_TEXT_PT, PANEL_LABEL_STYLE, figure_size, apply_cfd_style, save_figure
import csv
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm, LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.ticker import ScalarFormatter
RESOLUTIONS = (32, 64, 128, 256, 512)
RESOLUTION_COLORS = {32: '#E69F00', 64: '#0072B2', 128: '#D62728', 256: '#009E73', 512: '#7A3DB8'}

OUTPUT_FOLDERS = {
    'train_validation_hk_loss_cell_count': 'training_history',
    'fig01_cross_resolution_cell_count': 'cross_resolution',
    'fig02_circle_r_over_h_cell_count': 'circle',
    'fig03_flower_sensitivity_cell_count': 'flower_sensitivity',
    'fig04_flower_error_map_cell_count': 'flower_error_map',
    'appendix_b_sdf_only_cell_count': 'sdf_ablation',
}
TRAIN_RESOLUTIONS = (32, 256)
TRAINING_LINESTYLES = {'mixed_sdf_algebraic': '-', 'sdf_only': '--'}


def read_rows(path):
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))

def panel_label(ax, label):
    ax.text(s=label, transform=ax.transAxes, **PANEL_LABEL_STYLE)

def render_outputs(fig, stem):
    name = stem.name
    output_stem = FIGURES_ROOT / 'model' / OUTPUT_FOLDERS[name] / name
    outputs = save_figure(fig, output_stem)
    plt.close(fig)
    return outputs

def render_training_history():
    source = HERE / 'train_validation_hk_loss_cell_count.source.csv'
    rows = read_rows(source)
    apply_cfd_style()
    (fig, axes) = plt.subplots(1, 2, figsize=figure_size('double', 76.0), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.085, right=0.975, bottom=0.2, top=0.79, wspace=0.18)
    handles = []
    for (panel_index, (ax, split, title)) in enumerate(zip(axes, ('train', 'validation'), ('Training', 'Validation'))):
        for n_train in RESOLUTIONS:
            series = sorted(
                (row for row in rows if row['split'] == split and int(row['n_train']) == n_train),
                key=lambda row: int(row['step']),
            )
            (line,) = ax.plot(
                [int(row['step']) for row in series], [float(row['hk_loss']) for row in series],
                color=RESOLUTION_COLORS[n_train], linestyle='-', linewidth=1.2,
                marker='o', markersize=1.1, markerfacecolor='white', markeredgewidth=0.3,
                label=f'$N_{{\\mathrm{{train}}}}={n_train}$',
            )
            if panel_index == 0:
                handles.append(line)
        ax.set_yscale('log')
        ax.set_xlim(0, 230)
        ax.set_ylim(1e-07, 0.0004)
        ax.set_xlabel('Epoch')
        ax.set_title(title, pad=6.0)
        ax.tick_params(axis='y', labelsize=MATH_TEXT_PT)
        panel_label(ax, f'({chr(97 + panel_index)})')
    axes[0].set_ylabel('MSE')
    fig.legend(
        handles=handles, loc='upper center', bbox_to_anchor=(0.53, 0.97), ncol=5,
        fontsize=MATH_TEXT_PT, handlelength=2.1, handletextpad=0.45, columnspacing=1.35,
    )
    return render_outputs(fig, HERE / 'train_validation_hk_loss_cell_count')

def render_cross_resolution():
    source = HERE / 'fig01_cross_resolution_cell_count.source.csv'
    rows = read_rows(source)
    apply_cfd_style()
    (fig, axes) = plt.subplots(1, 2, figsize=figure_size('double', 70.0))
    fig.subplots_adjust(left=0.085, right=0.975, bottom=0.21, top=0.75, wspace=0.2)
    x = np.arange(len(RESOLUTIONS), dtype=float)
    for (ax, metric, label) in zip(axes, ('mse', 'mae'), ('(a)', '(b)')):
        for n_train in RESOLUTIONS:
            series = sorted(
                (row for row in rows if row['method'] == 'NN' and int(row['train_n']) == n_train),
                key=lambda row: int(row['test_n']),
            )
            ax.plot(
                x, [float(row[metric]) for row in series], color=RESOLUTION_COLORS[n_train],
                linestyle='-', marker='o', markersize=2.8, markerfacecolor='white',
                markeredgecolor=RESOLUTION_COLORS[n_train], markeredgewidth=0.65,
                label=f'$N_{{\\mathrm{{train}}}}={n_train}$',
            )
        fd = sorted((row for row in rows if row['method'] == 'FD'), key=lambda row: int(row['test_n']))
        ax.plot(
            x, [float(row[metric]) for row in fd], color='black', linestyle=':', linewidth=1.35,
            marker='o', markersize=2.8, markeredgewidth=0.65, label='FD',
        )
        ax.set_yscale('log')
        ax.set_xticks(x, [str(value) for value in RESOLUTIONS])
        ax.set_xlabel('Test resolution $N_{\\mathrm{test}}$')
        ax.set_ylabel(metric.upper())
        ax.tick_params(axis='y', labelsize=MATH_TEXT_PT)
        panel_label(ax, label)
    (handles, labels) = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc='upper center', ncol=6, bbox_to_anchor=(0.53, 0.965),
        fontsize=MATH_TEXT_PT, handlelength=2.4, columnspacing=1.1,
    )
    return render_outputs(fig, HERE / 'fig01_cross_resolution_cell_count')

def render_circle():
    source = HERE / 'fig02_circle_r_over_h_cell_count.source.csv'
    return render_curvature_scan(source)


def render_curvature_scan(source, output_stem=None, *, xlabel='$R/h$', dense=False):
    """Plot the existing six-method curvature scan, including exploratory geometries."""
    rows = read_rows(source)
    apply_cfd_style()
    (fig, axes) = plt.subplots(1, 2, figsize=figure_size('double', 70.0))
    fig.subplots_adjust(left=0.085, right=0.975, bottom=0.24, top=0.75, wspace=0.2)
    for (ax, metric, label) in zip(axes, ('mse', 'mae'), ('(a)', '(b)')):
        for n_train in RESOLUTIONS:
            series = sorted(
                (row for row in rows if row['method'] == 'NN' and int(row['train_n']) == n_train),
                key=lambda row: float(row['r_over_h']),
            )
            ax.plot(
                [float(row['r_over_h']) for row in series], [float(row[metric]) for row in series],
                color=RESOLUTION_COLORS[n_train], linestyle='-',
                marker='o', markersize=1.8, markerfacecolor='white', markeredgewidth=0.5,
                markevery=32 if dense else 1,
                label=f'$N_{{\\mathrm{{train}}}}={n_train}$',
            )
        fd = sorted((row for row in rows if row['method'] == 'FD'), key=lambda row: float(row['r_over_h']))
        ax.plot(
            [float(row['r_over_h']) for row in fd], [float(row[metric]) for row in fd], color='black',
            linestyle=':', linewidth=1.35, label='FD',
            marker='o', markersize=1.8, markerfacecolor='white', markeredgewidth=0.5,
            markevery=32 if dense else 1,
        )
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_ylabel(metric.upper())
        ax.tick_params(axis='both', labelsize=MATH_TEXT_PT)
        panel_label(ax, label)
    fig.supxlabel(xlabel, x=0.53, y=0.06)
    (handles, labels) = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc='upper center', ncol=6, bbox_to_anchor=(0.53, 0.965),
        fontsize=MATH_TEXT_PT, handlelength=2.4, columnspacing=1.1,
    )
    if output_stem is None:
        return render_outputs(fig, HERE / 'fig02_circle_r_over_h_cell_count')
    outputs = save_figure(fig, output_stem)
    plt.close(fig)
    return outputs

def _flower_series(rows, family, metric, method, selection):
    return sorted(
        (row for row in rows if row['family'] == family and row['metric'] == metric and (row['method'] == method) and (row['selection'] == selection)),
        key=lambda row: int(row['step']),
    )

def render_flower_sensitivity():
    source = HERE / 'fig03_flower_sensitivity_cell_count.source.csv'
    rows = read_rows(source)
    apply_cfd_style()
    (fig, axes) = plt.subplots(2, 2, figsize=figure_size('double', 110.0), sharex='col')
    fig.subplots_adjust(left=0.085, right=0.975, bottom=0.14, top=0.91, wspace=0.2, hspace=0.38)
    for (col, family) in enumerate(('smooth', 'acute')):
        top = axes[0, col]
        for (method, color, linestyle) in (('NN', '#009E73', '-'), ('FD', 'black', ':')):
            series = _flower_series(rows, family, 'hkappa_mse', method, 'interface_nodes')
            top.plot(
                [int(row['step']) for row in series], [float(row['value']) for row in series],
                color=color, linestyle=linestyle,
                marker='o', markersize=1.8, markerfacecolor='white', markeredgewidth=0.5,
                label='NN ($N_{\\mathrm{train}}=256$)' if method == 'NN' else 'FD',
            )
        formatter = ScalarFormatter(useMathText=True)
        formatter.set_powerlimits((0, 0))
        top.yaxis.set_major_formatter(formatter)
        top.yaxis.get_offset_text().set_fontsize(MATH_TEXT_PT)
        top.margins(y=0.08)
        if col == 0:
            top.set_ylabel('MSE of $h\\kappa$')
        top.set_title(f'{family.capitalize()} flower')
        bottom = axes[1, col]
        for (metric, color, linestyle, label) in (('sdf_mean', '#355C8A', '--', 'Mean'), ('sdf_max', '#0072B2', '-', 'Max')):
            series = _flower_series(rows, family, metric, 'SDF', 'interface_nodes')
            bottom.plot(
                [int(row['step']) for row in series], [float(row['value']) for row in series],
                color=color, linestyle=linestyle, label=label,
                marker='o', markersize=1.8, markerfacecolor='white', markeredgewidth=0.5,
            )
        bottom.set_yscale('log')
        bottom.set_xlabel('Reinitialization step')
        if col == 0:
            bottom.set_ylabel('$E_{\\nabla\\phi}$')
    axes[0, 0].legend(
        loc='upper right', ncol=2, columnspacing=1.5, handletextpad=0.45, fontsize=MATH_TEXT_PT,
    )
    axes[1, 0].legend(loc='upper right', ncol=2, columnspacing=1.5, handletextpad=0.45)
    for (ax, label) in zip(axes.flat, ('(a)', '(b)', '(c)', '(d)')):
        ax.tick_params(labelsize=MATH_TEXT_PT)
        panel_label(ax, label)
    return render_outputs(fig, HERE / 'fig03_flower_sensitivity_cell_count')

def flower_error_data():
    old = pd.read_csv(HERE / 'fig04_flower_error_map_cell_count.source.csv.gz')
    extra = pd.read_csv(HERE / 'flower_steps_3_5.csv')
    return pd.concat([old[old.step.isin([0, 1, 10])], extra[extra.step == 3]], ignore_index=True)

def render_flower_error_map():
    data = flower_error_data()
    norm = LogNorm(vmin=0.0001, vmax=0.12, clip=False)
    values = np.array([1e-4, 3.16227766e-4, 1e-3, 3.16227766e-3, 1e-2, .12])
    positions = np.log(values / 1e-4) / np.log(.12 / 1e-4)
    cmap = LinearSegmentedColormap.from_list('flower_error_rainbow', list(zip(
        positions, ['#d7191c', '#ff8c00', '#ffe600', '#20bd45', '#0066ff', '#08085c']
    )), N=512)
    apply_cfd_style()
    (fig, axes) = plt.subplots(2, 4, figsize=figure_size('double', 100))
    fig.subplots_adjust(left=0.075, right=0.83, bottom=0.06, top=0.88, wspace=0.08, hspace=0.23)
    for (row, family) in enumerate(('smooth', 'acute')):
        for (col, step) in enumerate((0, 1, 3, 10)):
            ax = axes[row, col]
            frame = data[(data.family == family) & (data.step == step)].sort_values('theta_rad')
            xy = frame[['x', 'y']].to_numpy()
            error = frame.nn_abs_error.to_numpy()
            closed = np.vstack([xy, xy[0]])
            segments = np.stack([closed[:-1], closed[1:]], axis=1)
            values = 0.5 * (error + np.roll(error, -1))
            collection = LineCollection(segments, cmap=cmap, norm=norm, linewidths=2.2)
            collection.set_array(values)
            ax.add_collection(collection)
            ax.update_datalim(xy)
            ax.autoscale_view()
            ax.set_aspect('equal', adjustable='datalim')
            ax.margins(0.08)
            ax.set_xticks([])
            ax.set_yticks([])
            if row == 0:
                ax.set_title(f'Step {step}')
            if col == 0:
                ax.set_ylabel(family.capitalize(), labelpad=9)
            ax.text(s=f'({chr(97 + 4 * row + col)})', transform=ax.transAxes, **PANEL_LABEL_STYLE)
    cb = fig.colorbar(collection, cax=fig.add_axes([0.855, 0.21, 0.018, 0.57]), extend='min')
    cb.solids.set_edgecolor('face')
    cb.set_ticks([0.0001, 0.001, 0.01, 0.1])
    cb.set_ticklabels(['$10^{-4}$', '$10^{-3}$', '$10^{-2}$', '$10^{-1}$'])
    cb.set_label('Absolute error in $h\\kappa$')
    return render_outputs(fig, HERE / 'fig04_flower_error_map_cell_count')

def render_sdf_ablation():
    source = HERE / 'appendix_sdf_mixed_circle_cell_count.source.csv'
    rows = read_rows(source)
    apply_cfd_style()
    (fig, axes) = plt.subplots(1, 2, figsize=figure_size('double', 70.0), sharey=True)
    fig.subplots_adjust(left=0.085, right=0.975, bottom=0.22, top=0.75, wspace=0.18)
    for (ax, field, title, label) in zip(
        axes, ('sdf', 'algebraic'), ('Signed-distance field', 'Algebraic field'), ('(a)', '(b)'),
    ):
        for train_n in TRAIN_RESOLUTIONS:
            for training_data in ('mixed_sdf_algebraic', 'sdf_only'):
                series = sorted(
                    (row for row in rows if row['test_field'] == field and row['method'] == 'NN' and (int(row['train_n']) == train_n) and (row['training_data'] == training_data)),
                    key=lambda row: float(row['r_over_h']),
                )
                ax.plot(
                    [float(row['r_over_h']) for row in series], [float(row['mse']) for row in series],
                    color=RESOLUTION_COLORS[train_n], linestyle=TRAINING_LINESTYLES[training_data],
                    marker='o', markersize=1.8, markerfacecolor='white', markeredgewidth=0.5,
                )
        fd = sorted(
            (row for row in rows if row['test_field'] == field and row['method'] == 'FD'),
            key=lambda row: float(row['r_over_h']),
        )
        ax.plot(
            [float(row['r_over_h']) for row in fd], [float(row['mse']) for row in fd], color='black',
            linestyle=':', linewidth=1.35,
            marker='o', markersize=1.8, markerfacecolor='white', markeredgewidth=0.5,
        )
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_title(title)
        ax.set_xlabel('$R/h$')
        ax.tick_params(axis='both', labelsize=MATH_TEXT_PT)
        panel_label(ax, label)
    axes[0].set_ylabel('MSE of $h\\kappa$')
    handles = [Line2D([0], [0], color=RESOLUTION_COLORS[n], label=f'$N_{{\\mathrm{{train}}}}={n}$') for n in TRAIN_RESOLUTIONS]
    handles.extend(
        [
            Line2D([0], [0], color='black', linestyle='-', label='Mixed-field training'),
            Line2D([0], [0], color='black', linestyle='--', label='SDF-only training'),
            Line2D([0], [0], color='black', linestyle=':', label='FD'),
        ],
    )
    fig.legend(
        handles=handles, loc='upper center', ncol=5, bbox_to_anchor=(0.53, 0.965),
        fontsize=MATH_TEXT_PT, handlelength=2.4, columnspacing=1.2,
    )
    return render_outputs(fig, HERE / 'appendix_b_sdf_only_cell_count')


if __name__ == '__main__':
    for render in (
        render_training_history, render_cross_resolution, render_circle, render_flower_sensitivity,
        render_flower_error_map, render_sdf_ablation,
    ):
        for path in render():
            print(path)
