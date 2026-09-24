"""Record actual station-step refinement without treating unstable values as truth."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def run(out):
    root = Path(__file__).resolve().parents[1]
    source = root/'benchmarks/kang_domain_sensitivity_20260924/marching_refinement.json'
    frozen = json.loads(source.read_text())
    paths = [root/frozen['baseline'], root/frozen['out']]
    contracts = [json.loads((p/'contract.json').read_text()) for p in paths]
    left, right = contracts
    for key in ('length', 'beam', 'draft', 'rho', 'gravity', 'froude_length', 'frequencies',
                'endpoint_fraction', 'input_points_per_side', 'moment_origin'):
        if left[key] != right[key]:
            raise ValueError(f'Fixed input mismatch: {key}')
    for key, val in left['config'].items():
        if right['config'][key] != (2*val-1 if key=='hull_stations' else val):
            raise ValueError(f'Unexpected geometry change: {key}')
    for key, val in left['options'].items():
        if right['options'][key] != (2*val if key=='history_steps' else val):
            raise ValueError(f'Unexpected history change: {key}')
    files = [Path(__file__), source, *[p/'contract.json' for p in paths]]
    rows = []
    durations = []
    for p, c in zip(paths, contracts, strict=True):
        speed = c['froude_length']*np.sqrt(c['gravity']*c['length'])
        dt = c['length']*(1-2*c['endpoint_fraction'])/(c['config']['hull_stations']-1)/speed
        durations.append(dt*c['options']['history_steps'])
        for frequency in frozen['frequencies']:
            file = p/f'fields_{frequency:g}.npz'
            files.append(file)
            with np.load(file) as data:
                density = abs(data['diffraction_density'][:, 0])
                if not np.isfinite(density).all():
                    raise ValueError('Nonfinite station loads')
                scale = c['rho']*c['gravity']*(29144/51975*c['length']*c['beam']*c['draft'])/c['length']
                rows.append(dict(run=p.name, frequency=frequency, dt_s=dt,
                    history_duration_s=durations[-1],
                    total_heave_amplitude=abs(data['total'][0])/scale,
                    max_heave_density=float(density.max()),
                    x_at_max_m=data['x_m'][density.argmax()]))
    if not np.isclose(*durations, rtol=1e-12, atol=0.):
        raise ValueError('Physical history duration changed')
    out.mkdir(parents=True, exist_ok=False)
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'comparison.csv', index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        note='No convergence ratio against unstable baseline; finite output is not stability proof',
        history_duration_preserved=True,
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), indent=2))
    print(frame.to_string(index=False))


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    run(p.parse_args().out)
