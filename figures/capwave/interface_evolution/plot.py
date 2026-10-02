"""The first three post-initial amplitude peaks of the FP64/C2/N128 run."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FIGURES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FIGURES_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import cfd_style

def main():
    work = HERE / 'peak_observations'
    peaks = (100, 203, 305)
    cfd_style.apply_cfd_style()
    (fig, axes) = plt.subplots(1, 3, figsize=cfd_style.figure_size('double', 51), sharey=True)
    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.24, top=0.87, wspace=0.17)
    ymax = 0.02
    for (col, index) in enumerate(peaks):
        frame = pd.read_csv(work / f'peak-{index}.csv')
        x = np.r_[0, frame.x, 2]
        y = np.r_[frame.eta.iloc[0], frame.eta, frame.eta.iloc[-1]]
        ax = axes[col]
        ax.plot(x, y, color='#D62728', lw=1.2)
        ax.set(
            xlim=(0, 2), ylim=(-ymax, ymax), xlabel='$x$', xticks=[0, 0.5, 1, 1.5, 2],
            yticks=np.linspace(-ymax, ymax, 5),
        )
        ax.text(s=f'({chr(97 + col)})', transform=ax.transAxes, **cfd_style.PANEL_LABEL_STYLE)
    axes[0].set_ylabel('$y$')
    stem = HERE / 'capwave_interface_evolution_float64-forward'
    print(cfd_style.save_figure(fig, stem))
    plt.close(fig)


if __name__ == '__main__':
    main()
