"""Draw the stationary-bubble setup as editable vector artwork."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import apply_cfd_style, figure_size, save_figure
import math
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle, Wedge
OUTPUT_STEM = HERE / 'stationary_bubble_setup'
FIGURE_HEIGHT_MM = 80.0
DOMAIN = 1.0
RADIUS = 0.4
INK = '#222222'
FLUID_1 = '#FFFFFF'
FLUID_2 = '#D9D9D9'

def arrow(ax, start, end, *, both=False, linewidth=0.8):
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle='<|-|>' if both else '-|>', mutation_scale=7.0, linewidth=linewidth,
            color=INK, shrinkA=0.0, shrinkB=0.0, clip_on=False,
        ),
    )

def draw_setup(ax):
    ax.set_xlim(-0.11, 1.15)
    ax.set_ylim(-0.11, 1.15)
    ax.set_aspect('equal', adjustable='box')
    ax.axis('off')
    ax.add_patch(Rectangle((0.0, 0.0), DOMAIN, DOMAIN, facecolor=FLUID_2, edgecolor=INK, linewidth=1.0))
    ax.add_patch(Wedge((0.0, 0.0), RADIUS, 0.0, 90.0, facecolor=FLUID_1, edgecolor=INK, linewidth=1.1))
    ax.text(0.12, 0.22, 'fluid 1', ha='center', va='center', fontstyle='italic')
    ax.text(0.62, 0.6, 'fluid 2', ha='center', va='center', fontstyle='italic')
    angle = 0.57
    end = (RADIUS * math.cos(angle), RADIUS * math.sin(angle))
    arrow(ax, (0.015, 0.015), end)
    ax.text(0.34, 0.2, '$R=0.4$', ha='left', va='center')
    y_dimension = 1.04
    ax.plot([0.0, 0.0], [1.0, y_dimension + 0.025], color=INK, lw=0.7)
    ax.plot([1.0, 1.0], [1.0, y_dimension + 0.025], color=INK, lw=0.7)
    arrow(ax, (0.0, y_dimension), (1.0, y_dimension), both=True, linewidth=0.7)
    ax.text(0.5, y_dimension + 0.035, '1', ha='center', va='bottom')
    x_dimension = 1.08
    ax.plot([1.0, x_dimension + 0.025], [0.0, 0.0], color=INK, lw=0.7)
    ax.plot([1.0, x_dimension + 0.025], [1.0, 1.0], color=INK, lw=0.7)
    arrow(ax, (x_dimension, 0.0), (x_dimension, 1.0), both=True, linewidth=0.7)
    ax.text(x_dimension + 0.035, 0.5, '1', rotation=90, ha='left', va='center')
    origin = (-0.08, -0.07)
    arrow(ax, origin, (0.1, origin[1]), linewidth=0.75)
    arrow(ax, origin, (origin[0], 0.11), linewidth=0.75)
    ax.text(0.125, origin[1], '$x$', ha='left', va='center')
    ax.text(origin[0], 0.135, '$y$', ha='center', va='bottom')

def main():
    apply_cfd_style()
    (fig, ax) = plt.subplots(figsize=figure_size('single', FIGURE_HEIGHT_MM))
    fig.subplots_adjust(left=0.03, right=0.97, bottom=0.025, top=0.975)
    draw_setup(ax)
    paths = save_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)


if __name__ == '__main__':
    main()
