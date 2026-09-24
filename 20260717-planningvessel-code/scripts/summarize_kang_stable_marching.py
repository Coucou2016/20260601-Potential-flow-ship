"""Compare two nonexplosive marching grids under a frozen diagnostic contract."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.summarize_kang_domain_sensitivity import compare


def run(out):
    root = Path(__file__).resolve().parents[1]
    path = root/'benchmarks/kang_domain_sensitivity_20260924/stable_marching_refinement.json'
    frozen = json.loads(path.read_text())
    directories = [root/frozen['baseline'], root/frozen['out']]
    a, b = [json.loads((d/'contract.json').read_text()) for d in directories]
    for key in ('length', 'beam', 'draft', 'rho', 'gravity', 'froude_length',
                'endpoint_fraction', 'input_points_per_side', 'frequencies', 'moment_origin'):
        if a[key] != b[key]:
            raise ValueError(f'Fixed input changed: {key}')
    for key, value in a['config'].items():
        if b['config'][key] != (2*value-1 if key=='hull_stations' else value):
            raise ValueError(f'Unexpected configuration change: {key}')
    for key, value in a['options'].items():
        if b['options'][key] != (2*value if key=='history_steps' else value):
            raise ValueError(f'Unexpected history change: {key}')
    if b['preset'] != frozen['preset'] or not b.get('save_boundary'):
        raise ValueError('Frozen preset or field export missing')
    files = [Path(__file__), path, Path(__file__).with_name('summarize_kang_domain_sensitivity.py')]
    files += [d/'contract.json' for d in directories]
    rows = []
    for w in frozen['frequencies']:
        paths = [d/f'fields_{w}.npz' for d in directories]
        files += paths
        with np.load(paths[0]) as left, np.load(paths[1]) as right:
            if not np.allclose(left['x_m'], right['x_m'][::2], atol=1e-13, rtol=0.):
                raise ValueError('Refined stations do not nest')
            for component in ('incident', 'diffraction', 'total'):
                delta = compare(left[component], right[component])
                phase = np.degrees(np.angle(right[component]/left[component]))
                for j, mode in enumerate(('heave', 'geometric_pitch')):
                    rows.append(dict(frequency=w, component=component, mode=mode,
                        relative_complex_change=delta[j], phase_change_deg=phase[j],
                        within_screening=bool(delta[j] <= frozen['screening_relative_change'])))
    out.mkdir(parents=True, exist_ok=False)
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'comparison.csv', index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        local_screening_pass=bool(frame.within_screening.all()),
        scope='Three frequencies, two marching grids, no independent physical acceptance',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), indent=2))
    print(frame.to_string(index=False))


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    run(p.parse_args().out)
