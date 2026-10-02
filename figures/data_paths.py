"""The paper's three methods in the existing classified data directories."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def run_dir(case, resolution, method, *, case_id=None, precision='float64-forward', domain='half'):
    if domain == 'whole':
        if case != 'rising_bubble' or precision != 'float64-forward':
            raise ValueError('Whole-domain data are available for rising_bubble at float64-forward only.')
        return ROOT / 'tem/rising_full_domain/data' / f'case{case_id}' / f'N{resolution:04d}' / method
    steps = '00' if case == 'stationary_bubble' else '03'
    native_policy = 'steps' if case == 'capwave' else 'imax'
    suffix = {'float32': '', 'float64-forward': '-FP64'}[precision]
    (mode, leaf) = {
        'VOF-HF': ('comparators', 'VOF-HF'), 'CLSVOF': ('crossing', f'{native_policy}{steps}/CLSVOF-native-C2'),
        'CLSVOF-NN': ('crossing', f'steps{steps}/Cell-NN-C2{suffix}'),
    }[method]
    path = ROOT / 'data' / case / mode
    if case_id is not None:
        path /= f'case{case_id}'
    return path / 'uniform' / f'N{resolution:04d}' / leaf
