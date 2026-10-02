"""Draw the manuscript schematic for the local level-set curvature MLP."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (
    BODY_TEXT_PT, MATH_TEXT_PT, PANEL_LABEL_PT, TITLE_TEXT_PT, apply_cfd_style, figure_size,
    save_figure,
)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle
OUTPUT_STEM = HERE / 'model_structure'
FIGURE_WIDTH_MM = 190.0
FIGURE_HEIGHT_MM = 65.0
FLOW_Y = 0.505
FLOW_ARROW_LENGTH = 0.034
INK = '#222222'
MUTED = '#686868'
GRID = '#B8BDC2'
BACKGROUND_NODE = '#C7CBCF'
BLUE = '#4477AA'
BLUE_DARK = '#2F5F88'
BLUE_LIGHT = '#EAF0F6'
PHASE_FILL = '#F0F3F5'
TARGET = '#946600'

def axes_arrow(ax, start, end, *, color=INK, linewidth=0.75, mutation_scale=7.0, zorder=10):
    ax.add_patch(
        FancyArrowPatch(
            start, end, transform=ax.transAxes, arrowstyle='-|>', mutation_scale=mutation_scale,
            linewidth=linewidth, color=color, shrinkA=0.0, shrinkB=0.0, clip_on=False, zorder=zorder,
        ),
    )

def interface_height(x):
    xi = np.asarray(x) - 2.0
    return 2.13 + 0.36 * xi + 0.075 * xi ** 2

def closest_interface_point():
    candidates = np.linspace(1.55, 2.35, 6001)
    heights = interface_height(candidates)
    distances = (candidates - 2.0) ** 2 + (heights - 2.0) ** 2
    index = int(np.argmin(distances))
    return (float(candidates[index]), float(heights[index]))

def draw_local_geometry(fig):
    """Draw the local nodal level-set geometry using the Elsevier figure semantics."""
    ax = fig.add_axes([0.018, 0.095, 0.275, 0.79])
    ax.set_xlim(-0.14, 4.14)
    ax.set_ylim(-0.18, 4.2)
    ax.set_aspect('equal', adjustable='box')
    ax.set_axis_off()
    curve_x = np.linspace(0.0, 4.0, 601)
    curve_y = interface_height(curve_x)
    ax.fill_between(curve_x, 0.0, curve_y, color=PHASE_FILL, linewidth=0.0, zorder=0)
    for coordinate in np.arange(0.5, 4.0, 1.0):
        ax.plot([coordinate, coordinate], [0.0, 4.0], color=GRID, linewidth=0.52, zorder=1)
        ax.plot([0.0, 4.0], [coordinate, coordinate], color=GRID, linewidth=0.52, zorder=1)
    for x_node in range(5):
        for y_node in range(5):
            ax.scatter(
                [x_node], [y_node], s=7.5, facecolor=BACKGROUND_NODE, edgecolor='white',
                linewidth=0.35, zorder=3,
            )
    for x_node in (1.0, 2.0, 3.0):
        for y_node in (1.0, 2.0, 3.0):
            central = x_node == 2.0 and y_node == 2.0
            ax.scatter(
                [x_node], [y_node], s=27.0 if central else 19.0, facecolor=INK if central else BLUE,
                edgecolor='white', linewidth=0.55, zorder=8,
            )
    ax.plot(curve_x, curve_y, color=INK, linewidth=0.92, zorder=6)
    closest = closest_interface_point()
    ax.plot(
        [2.0, closest[0]], [2.0, closest[1]], color=TARGET, linewidth=0.72, linestyle=(0, (2.0, 1.5)),
        zorder=7,
    )
    ax.scatter(
        [closest[0]], [closest[1]], s=30.0, facecolor='white', edgecolor=TARGET, linewidth=1.0,
        zorder=9,
    )
    tangent_slope = 0.36 + 0.15 * (closest[0] - 2.0)
    normal = np.array([-tangent_slope, 1.0], dtype=float)
    normal /= np.linalg.norm(normal)
    normal_end = np.asarray(closest) + 0.52 * normal
    ax.add_patch(
        FancyArrowPatch(
            closest, tuple(normal_end), arrowstyle='-|>', mutation_scale=6.0, linewidth=0.7, color=INK,
            shrinkA=2.0, shrinkB=0.0, zorder=9,
        ),
    )
    ax.text(0.18, 3.63, '$\\phi>0$', fontsize=BODY_TEXT_PT, ha='left', va='center')
    ax.text(0.18, 0.35, '$\\phi<0$', fontsize=BODY_TEXT_PT, ha='left', va='center')
    ax.text(0.2, 2.44, '$\\Gamma:\\ \\phi=0$', fontsize=BODY_TEXT_PT, ha='left', va='center')
    ax.annotate(
        '$(i,j)$', xy=(2.0, 2.0), xytext=(2.37, 1.72), fontsize=BODY_TEXT_PT, ha='left', va='top',
        arrowprops={'arrowstyle': '-', 'linewidth': 0.52, 'color': INK, 'shrinkA': 2.0, 'shrinkB': 3.0},
        zorder=10,
    )
    ax.text(
        normal_end[0] - 0.02, normal_end[1] + 0.06, '$\\mathbf{n}$', fontsize=BODY_TEXT_PT,
        ha='center', va='bottom',
    )
    dimension_y = 0.52
    ax.plot([1.5, 1.5], [0.32, 0.68], color=INK, linewidth=0.52, zorder=9)
    ax.plot([2.5, 2.5], [0.32, 0.68], color=INK, linewidth=0.52, zorder=9)
    ax.add_patch(
        FancyArrowPatch(
            (1.5, dimension_y), (2.5, dimension_y), arrowstyle='<|-|>', mutation_scale=5.3,
            linewidth=0.58, color=INK, shrinkA=0.0, shrinkB=0.0, zorder=10,
        ),
    )
    ax.text(2.0, 0.35, '$h$', fontsize=BODY_TEXT_PT, ha='center', va='top')

def draw_feature_tensor(ax):
    axes_arrow(ax, (0.3, FLOW_Y), (0.334, FLOW_Y), mutation_scale=6.8)
    (x, y, width) = (0.35, 0.355, 0.095)
    height = width * FIGURE_WIDTH_MM / FIGURE_HEIGHT_MM
    ax.add_patch(
        Rectangle(
            (x, y), width, height, transform=ax.transAxes, facecolor='white', edgecolor=GRID,
            linewidth=0.65,
        ),
    )
    for f in (1 / 3, 2 / 3):
        ax.plot([x + f * width] * 2, [y, y + height], transform=ax.transAxes, color=GRID, lw=0.5)
        ax.plot([x, x + width], [y + f * height] * 2, transform=ax.transAxes, color=GRID, lw=0.5)
    for row in range(3):
        for col in range(3):
            ax.scatter(
                [x + (col + 0.5) * width / 3], [y + (row + 0.5) * height / 3], transform=ax.transAxes,
                s=10, color=BLUE, zorder=4,
            )
    ax.text(
        0.402, 0.708, '$(\\phi/h,\\ n_x,\\ n_y)_{3\\times3}$', transform=ax.transAxes,
        fontsize=MATH_TEXT_PT, color=MUTED, ha='center', va='bottom',
    )
    ax.text(
        0.402, 0.232, '$\\mathbf{s}_{i,j}\\in\\mathbb{R}^{27}$', transform=ax.transAxes,
        fontsize=MATH_TEXT_PT, color=INK, ha='center', va='center',
    )

def draw_network_column(ax, x, y_values, *, facecolor, edgecolor, size):
    """Draw representative neurons and an ellipsis for a wider layer."""
    ax.scatter(
        [x] * len(y_values), list(y_values), transform=ax.transAxes, s=size, marker='o',
        facecolor=facecolor, edgecolor=edgecolor, linewidth=0.78, zorder=6,
    )
    ax.text(
        x, 0.505, '$\\vdots$', transform=ax.transAxes, fontsize=BODY_TEXT_PT, color=edgecolor,
        ha='center', va='center', zorder=7,
    )

def connect_network_columns(ax, x_left, y_left, x_right, y_right):
    """Use faint representative connections without a dense spiderweb."""
    for (left_index, left_y) in enumerate(y_left):
        right_indices = {left_index, max(0, left_index - 1), min(len(y_right) - 1, left_index + 1)}
        for right_index in sorted(right_indices):
            ax.plot(
                [x_left, x_right], [left_y, y_right[right_index]], transform=ax.transAxes,
                color='#B7BBC0', linewidth=0.32, alpha=0.62, zorder=2,
            )

def draw_mlp(ax):
    """Draw an intuitive node-based MLP for a broad fluids readership."""
    axes_arrow(ax, (0.474, FLOW_Y), (0.474 + FLOW_ARROW_LENGTH, FLOW_Y), mutation_scale=6.8)
    input_x = 0.535
    hidden_x = (0.6, 0.655, 0.71, 0.765)
    output_x = 0.83
    input_y = (0.385, 0.445, 0.565, 0.625)
    hidden_y = (0.355, 0.425, 0.585, 0.655)
    connect_network_columns(ax, input_x, input_y, hidden_x[0], hidden_y)
    for (left, right) in zip(hidden_x, hidden_x[1:]):
        connect_network_columns(ax, left, hidden_y, right, hidden_y)
    for hidden_value in hidden_y:
        ax.plot(
            [hidden_x[-1], output_x], [hidden_value, FLOW_Y], transform=ax.transAxes, color='#B7BBC0',
            linewidth=0.36, alpha=0.68, zorder=2,
        )
    draw_network_column(ax, input_x, input_y, facecolor='white', edgecolor=GRID, size=26.0)
    for x in hidden_x:
        draw_network_column(ax, x, hidden_y, facecolor=BLUE_LIGHT, edgecolor=BLUE, size=30.0)
    ax.scatter(
        [output_x], [FLOW_Y], transform=ax.transAxes, s=43.0, marker='o', facecolor='white',
        edgecolor=INK, linewidth=0.9, zorder=7,
    )
    ax.text(
        input_x, 0.74, '27 inputs', transform=ax.transAxes, fontsize=BODY_TEXT_PT, color=MUTED,
        ha='center', va='center',
    )
    bracket_y = 0.745
    bracket_left = hidden_x[0] - 0.017
    bracket_right = hidden_x[-1] + 0.017
    ax.plot(
        [bracket_left, bracket_right], [bracket_y, bracket_y], transform=ax.transAxes, color=BLUE,
        linewidth=0.62, zorder=5,
    )
    for x in (bracket_left, bracket_right):
        ax.plot(
            [x, x], [bracket_y, bracket_y - 0.02], transform=ax.transAxes, color=BLUE, linewidth=0.62,
            zorder=5,
        )
    ax.text(
        float(np.mean(hidden_x)), 0.84, '4 hidden layers', transform=ax.transAxes,
        fontsize=BODY_TEXT_PT, color=INK, ha='center', va='center',
    )
    ax.text(
        float(np.mean(hidden_x)), 0.79, '128 neurons, ReLU', transform=ax.transAxes,
        fontsize=BODY_TEXT_PT, color=BLUE_DARK, ha='center', va='center',
    )
    ax.text(
        output_x, 0.42, 'linear', transform=ax.transAxes, fontsize=BODY_TEXT_PT, color=MUTED,
        ha='center', va='center',
    )
    axes_arrow(ax, (0.852, FLOW_Y), (0.852 + FLOW_ARROW_LENGTH, FLOW_Y), mutation_scale=6.8)
    ax.text(
        0.93, FLOW_Y, '$h\\kappa^{\\mathrm{NN}}_{i,j}$', transform=ax.transAxes,
        fontsize=TITLE_TEXT_PT, color=TARGET, ha='center', va='center',
    )

def build_figure():
    fig = plt.figure(figsize=figure_size('double', FIGURE_HEIGHT_MM))
    canvas = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    canvas.set_xlim(0.0, 1.0)
    canvas.set_ylim(0.0, 1.0)
    canvas.set_axis_off()
    canvas.text(
        0.018, 0.92, '(a)', transform=canvas.transAxes, fontsize=PANEL_LABEL_PT, fontweight='bold',
        ha='left', va='center',
    )
    canvas.text(
        0.06, 0.92, 'Local level-set geometry', transform=canvas.transAxes, fontsize=BODY_TEXT_PT,
        ha='left', va='center',
    )
    canvas.text(
        0.315, 0.92, '(b)', transform=canvas.transAxes, fontsize=PANEL_LABEL_PT, fontweight='bold',
        ha='left', va='center',
    )
    canvas.text(
        0.357, 0.92, 'Feature-to-curvature mapping', transform=canvas.transAxes, fontsize=BODY_TEXT_PT,
        ha='left', va='center',
    )
    draw_local_geometry(fig)
    draw_feature_tensor(canvas)
    draw_mlp(canvas)
    return fig

def main():
    apply_cfd_style()
    fig = build_figure()
    for path in save_figure(fig, OUTPUT_STEM):
        print(path)
    plt.close(fig)


if __name__ == '__main__':
    main()
