"""Replay actual free-surface transfers and locate endpoint extrapolation."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from planing_seakeeping.kernels.linear_2p5d.formulation import initialize_free_surface_state, resample_free_surface_state


def side_extrapolation(source, target):
    source, target = np.asarray(source), np.asarray(target)
    if (source.ndim != 1 or target.ndim != 1 or not np.isfinite(source).all()
            or not np.isfinite(target).all() or np.any(np.diff(source) <= 0)
            or np.any(np.diff(target) <= 0) or np.any(target == 0)):
        raise ValueError('Finite increasing two-sided grids required')
    inner = np.zeros(len(target), bool)
    outer = inner.copy()
    distance = np.zeros(len(target))
    for sign in (-1, 1):
        s = np.abs(source[source*sign > 0])
        index = np.flatnonzero(target*sign > 0)
        if len(s) < 2:
            raise ValueError('Two source samples required on each side')
        t = np.abs(target[index])
        inner[index] = t < s.min()
        outer[index] = t > s.max()
        distance[index] = np.maximum(s.min()-t, 0) + np.maximum(t-s.max(), 0)
    return inner, outer, distance


def run(saved, out, fields=None):
    files = sorted(saved.glob('free_surface_*.npz'))
    if len(files) != 3:
        raise ValueError('Three speed snapshots required')
    out.mkdir(parents=True, exist_ok=False)
    implementation = Path('planing_seakeeping/kernels/linear_2p5d/formulation.py')
    references = [] if fields is None else [fields]
    (out/'contract.json').write_text(json.dumps(dict(
        scope='Transfer replay and manufactured affine data; not physical validation',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), implementation, *files, *references]}), indent=2))
    rows = []
    for path in files:
        with np.load(path) as data:
            x, y = data['x'], data['y']
            for i in range(len(x)-2, -1, -1):
                old, new = y[i+1], y[i]
                state = initialize_free_surface_state(old, np.zeros(len(old)), dt_s=1.)
                state = replace(state, potential_m2_s=data['phi_after_local'][i+1])
                replay = resample_free_surface_state(state, new)
                inner, outer, distance = side_extrapolation(old, new)
                affine = (1.+2j)*old + .4j
                manufactured = resample_free_surface_state(replace(state, potential_m2_s=affine), new)
                error = manufactured.potential_m2_s - ((1.+2j)*new + .4j)
                same = np.array_equal(old, new)
                inner_edge = np.min(np.abs(new)-data['length'][i]/2)
                old_edge = np.min(np.abs(old)-data['length'][i+1]/2)
                rows.append(dict(case=path.stem, x=float(x[i]),
                    grid_changed=not same, waterline_shift=float(inner_edge-old_edge),
                    near_equal_skipped=not same and np.allclose(old,new),
                    inner_extrapolated=int(inner.sum()), outer_extrapolated=int(outer.sum()),
                    max_extrapolation_m=float(distance.max()),
                    replay_max_abs=float(np.max(np.abs(replay.potential_m2_s-data['phi_local'][i]))),
                    affine_max_abs=float(np.max(np.abs(error))),
                    affine_interior_max_abs=float(np.max(np.abs(error[~(inner|outer)]),initial=0.))))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'transfers.csv', index=False)
    summary = frame.groupby('case').agg(
        transfers=('x','size'), changed=('grid_changed','sum'),
        near_equal_skipped=('near_equal_skipped','sum'),
        inner_extrapolated=('inner_extrapolated','sum'), outer_extrapolated=('outer_extrapolated','sum'),
        max_extrapolation_m=('max_extrapolation_m','max'), replay_max_abs=('replay_max_abs','max'),
        affine_max_abs=('affine_max_abs','max'), affine_interior_max_abs=('affine_interior_max_abs','max'))
    summary.to_csv(out/'summary.csv')
    print(summary.to_string())
    if fields is not None:
        errors = pd.read_csv(fields, float_precision='round_trip')
        joined = errors.merge(frame[['case','x','grid_changed']], on=['case','x'],
                              validate='many_to_one', how='inner')
        if len(joined) != 3*len(frame):
            raise ValueError('Field diagnostic must match all transferred stations and three fields')
        grouped = joined.groupby(['case','field','grid_changed']).agg(
            stations=('x','size'), relative_median=('relative_rms','median'),
            relative_max=('relative_rms','max'), absolute_median=('rms_difference','median'))
        grouped.to_csv(out/'moving_vs_fixed.csv')
        print(grouped.to_string())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--saved', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--fields', type=Path)
    a = p.parse_args()
    run(a.saved, a.out, a.fields)
