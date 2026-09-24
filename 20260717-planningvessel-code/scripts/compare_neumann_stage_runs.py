"""Audit a sign-only diffraction change without fitting experimental responses."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def compare(before, after, out):
    before, after, out = map(Path, (before, after, out))
    names = ['input_snapshot.json']
    old = json.loads((before / names[0]).read_text())
    new = json.loads((after / names[0]).read_text())
    if old != new:
        raise ValueError('Input snapshots differ; not a controlled sign comparison')
    rows = []
    columns = ['F3_real', 'F3_imag', 'M5_real', 'M5_imag']
    for case in new['cases']:
        key = case['id']
        files = ['matrices.csv', 'excitation.csv'] + [
            f'excitation_component_matched_domain_{component}.csv'
            for component in ('froude_krylov', 'diffraction', 'incident_plus_diffraction')]
        names.extend(f'{key}/{name}' for name in files)
        data = {}
        for name in files:
            a, b = [pd.read_csv(root / key / name) for root in (before, after)]
            if a.shape != b.shape or list(a.columns) != list(b.columns):
                raise ValueError('Output shape mismatch')
            if not np.allclose(a.omega_e_rad_s, b.omega_e_rad_s, rtol=0, atol=1e-12):
                raise ValueError('Frequency mismatch')
            data[name] = (a, b)
        a, b = data['matrices.csv']
        matrix_change = float(np.max(np.abs(a[['A', 'B', 'C', 'M']].values-b[['A', 'B', 'C', 'M']].values)))
        row = dict(case=key, matrix_max_abs_change=matrix_change)
        for component, sign in (('froude_krylov', 1), ('diffraction', -1)):
            a, b = data[f'excitation_component_matched_domain_{component}.csv']
            av, bv = a[columns].values, b[columns].values
            row[component+'_expected_change_residual'] = float(np.linalg.norm(bv-sign*av)/max(np.linalg.norm(av), 1e-30))
        row['controlled_sign_change_confirmed'] = bool(matrix_change <= 1e-10 and
            row['froude_krylov_expected_change_residual'] <= 1e-10 and
            row['diffraction_expected_change_residual'] <= 1e-10)
        rows.append(row)
    out.mkdir(parents=True, exist_ok=False)
    hashes = {str(root / name): hashlib.sha256((root / name).read_bytes()).hexdigest()
              for root in (before, after) for name in names}
    hashes[str(Path(__file__))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (out/'audit.json').write_text(json.dumps(dict(stage_acceptance=False,
        response_fitting=False, hashes=hashes, rows=rows), indent=2))
    pd.DataFrame(rows).to_csv(out/'component_audit.csv', index=False)
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', type=Path, required=True)
    p.add_argument('--after', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    compare(args.before, args.after, args.out)
