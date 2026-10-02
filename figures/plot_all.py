"""Regenerate the 20 selected paper figures as PNG and vector PDF."""
from pathlib import Path
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PLOTS = (
    'model/model_structure/plot.py', 'model/plot_cell_count_figures.py',
    'stationary_bubble/setup/plot.py', 'stationary_bubble/ca_terminal_vs_grid/plot.py',
    'stationary_bubble/ca_time_n32_n128/plot.py', 'stationary_bubble/velocity_fields/plot.py',
    'capwave/interface_evolution/plot.py', 'capwave/amplitude_histories/plot.py',
    'capwave/e2_grid_convergence/plot.py', 'rising_bubble/setup/plot.py',
    'rising_bubble/interfaces_imax3/plot.py', 'rising_bubble/histories_imax3/plot.py',
    'model/feature_ablation/plot.py',
)


if __name__ == '__main__':
    env = dict(os.environ, MPLBACKEND='Agg', PYTHONDONTWRITEBYTECODE='1')
    for script in PLOTS:
        subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, env=env, check=True)
