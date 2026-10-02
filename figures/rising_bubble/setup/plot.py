"""Draw the shared Hysing rising-bubble setup schematic."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import BODY_TEXT_PT, apply_cfd_style, figure_size, save_figure
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
OUTPUT_STEM = HERE / 'rising_bubble_cases_setup'
FIGURE_HEIGHT_MM = 115.0
GEOMETRY = {'width': 1.0, 'height': 2.0, 'bubble_diameter': 0.5, 'bubble_center': (0.5, 0.5), 'gravity': 0.98}
PAPER_COORDINATES = {'horizontal': 'x', 'vertical': 'y', 'gravity_direction': 'negative_y'}
INK = '#000000'
LIQUID_FILL = '#D3D3D3'
BUBBLE_FILL = '#FFFFFF'

def setup_style():
    apply_cfd_style()

def double_arrow(ax, start, end, *, linewidth=0.75):
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle='<|-|>', mutation_scale=6.3, linewidth=linewidth, color=INK,
            shrinkA=0, shrinkB=0, clip_on=False, zorder=5,
        ),
    )

def single_arrow(ax, start, end, *, linewidth=0.8, scale=7.0):
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle='-|>', mutation_scale=scale, linewidth=linewidth, color=INK,
            shrinkA=0, shrinkB=0, clip_on=False, zorder=5,
        ),
    )

def draw_dimensions(ax):
    width_y = 2.105
    ax.plot([0.0, 0.0], [2.0, width_y + 0.025], color=INK, lw=0.65, clip_on=False)
    ax.plot([1.0, 1.0], [2.0, width_y + 0.025], color=INK, lw=0.65, clip_on=False)
    double_arrow(ax, (0.0, width_y), (1.0, width_y))
    ax.text(0.5, width_y + 0.035, '1', ha='center', va='bottom', fontsize=BODY_TEXT_PT)
    height_x = 1.4
    ax.plot([1.0, height_x + 0.025], [0.0, 0.0], color=INK, lw=0.65, clip_on=False)
    ax.plot([1.0, height_x + 0.025], [2.0, 2.0], color=INK, lw=0.65, clip_on=False)
    double_arrow(ax, (height_x, 0.0), (height_x, 2.0))
    ax.text(height_x + 0.045, 1.0, '2', ha='left', va='center', rotation=90, fontsize=BODY_TEXT_PT)
    (center_x, center_y) = GEOMETRY['bubble_center']
    radius = GEOMETRY['bubble_diameter'] / 2.0
    double_arrow(ax, (0.015, center_y), (center_x, center_y), linewidth=0.62)
    ax.text(0.13, center_y + 0.035, '0.5', ha='center', va='bottom', fontsize=BODY_TEXT_PT, zorder=6)
    center_height_x = 0.12
    double_arrow(ax, (center_height_x, 0.015), (center_height_x, center_y), linewidth=0.62)
    ax.text(
        center_height_x - 0.035, center_y / 2.0, '0.5', ha='right', va='center', rotation=90,
        fontsize=BODY_TEXT_PT, zorder=6,
    )
    diameter_x = 0.82
    ax.plot([center_x, diameter_x + 0.015], [center_y - radius] * 2, color=INK, lw=0.55)
    ax.plot([center_x, diameter_x + 0.015], [center_y + radius] * 2, color=INK, lw=0.55)
    double_arrow(ax, (diameter_x, center_y - radius), (diameter_x, center_y + radius), linewidth=0.62)
    ax.text(diameter_x + 0.04, center_y, '0.5', ha='left', va='center', fontsize=BODY_TEXT_PT)

def draw_coordinates_and_gravity(ax):
    origin = (0.45, 1.35)
    single_arrow(ax, origin, (0.67, origin[1]), linewidth=0.75, scale=6.5)
    single_arrow(ax, origin, (origin[0], 1.6), linewidth=0.75, scale=6.5)
    ax.text(
        0.695, origin[1] - 0.01, f"${PAPER_COORDINATES['horizontal']}$", ha='left', va='center',
        fontsize=BODY_TEXT_PT,
    )
    ax.text(
        origin[0] - 0.015, 1.63, f"${PAPER_COORDINATES['vertical']}$", ha='center', va='bottom',
        fontsize=BODY_TEXT_PT,
    )
    single_arrow(ax, (0.5, 1.84), (0.5, 1.64), linewidth=0.8, scale=7.0)
    ax.text(0.54, 1.74, '$g$', ha='left', va='center', fontsize=BODY_TEXT_PT)

def draw_setup(ax):
    ax.set_xlim(-0.23, 1.5)
    ax.set_ylim(-0.14, 2.34)
    ax.set_aspect('equal', adjustable='box')
    ax.axis('off')
    ax.add_patch(
        Rectangle(
            (0.0, 0.0), GEOMETRY['width'], GEOMETRY['height'], facecolor=LIQUID_FILL, edgecolor=INK,
            linewidth=1.15, joinstyle='miter', zorder=1,
        ),
    )
    ax.add_patch(
        Circle(
            GEOMETRY['bubble_center'], radius=GEOMETRY['bubble_diameter'] / 2.0, facecolor=BUBBLE_FILL,
            edgecolor=INK, linewidth=1.05, zorder=3,
        ),
    )
    ax.text(
        0.5, 1.08, 'fluid 1', ha='center', va='center', fontsize=BODY_TEXT_PT, fontstyle='italic',
        fontweight='bold',
    )
    ax.text(
        0.5, 0.63, 'fluid 2', ha='center', va='center', fontsize=BODY_TEXT_PT, fontstyle='italic',
        fontweight='bold', zorder=4,
    )
    ax.text(0.5, 1.94, 'no slip', ha='center', va='center', fontsize=BODY_TEXT_PT)
    ax.text(0.5, -0.07, 'no slip', ha='center', va='center', fontsize=BODY_TEXT_PT)
    ax.text(-0.19, 1.0, 'free slip', ha='center', va='center', rotation=90, fontsize=BODY_TEXT_PT)
    ax.text(1.19, 1.0, 'free slip', ha='center', va='center', rotation=-90, fontsize=BODY_TEXT_PT)
    draw_dimensions(ax)
    draw_coordinates_and_gravity(ax)

def main():
    setup_style()
    (fig, ax) = plt.subplots(figsize=figure_size('single', FIGURE_HEIGHT_MM))
    fig.subplots_adjust(left=0.04, right=0.96, bottom=0.03, top=0.97)
    draw_setup(ax)
    paths = save_figure(fig, OUTPUT_STEM)
    plt.close(fig)
    for path in paths:
        print(path)


if __name__ == '__main__':
    main()
