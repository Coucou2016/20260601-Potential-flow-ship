"""Verify frozen boundary-only refinement and report complex force changes."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.summarize_kang_domain_sensitivity import compare


def validate_pair(base, dense):
    for key in ('frequencies', 'length', 'beam', 'draft', 'froude_length', 'rho',
                'gravity', 'options', 'input_points_per_side', 'endpoint_fraction', 'moment_origin'):
        if key not in base or key not in dense or base[key] != dense[key]:
            raise ValueError(f'Changed or missing fixed input: {key}')
    if base.get('preset') != 'fine' or dense.get('preset') != 'boundary_dense':
        raise ValueError('Unexpected preset')
    bc, dc = base['config'], dense['config']
    if bc.keys() != dc.keys():
        raise ValueError('Config field mismatch')
    for key, value in bc.items():
        expected = 2*value if key in ('free_surface_inner_panels', 'free_surface_outer_panels') else value
        if dc[key] != expected:
            raise ValueError(f'Unexpected config change: {key}')


def run(out):
    root = Path(__file__).resolve().parents[1]
    contract_path = root/'benchmarks/kang_domain_sensitivity_20260924/boundary_refinement.json'
    contract = json.loads(contract_path.read_text())
    files = [Path(__file__), contract_path, Path(__file__).with_name('summarize_kang_domain_sensitivity.py')]
    rows = []
    station_rows = []
    dense_paths = []
    for variant in contract['runs']:
        base, dense = root/variant['baseline'], root/variant['out']
        paths = [p/'contract.json' for p in (base, dense)]
        files.extend(paths)
        configs = [json.loads(p.read_text()) for p in paths]
        validate_pair(*configs)
        if configs[1]['config']['control_surface_radius_beams'] != variant['radius_beams']:
            raise ValueError('Radius differs from frozen run')
        dense_paths.append((variant['radius_beams'], dense))
        for frequency in contract['frequencies']:
            paths = [p/f'fields_{frequency:g}.npz' for p in (base, dense)]
            files.extend(paths)
            with np.load(paths[0]) as left, np.load(paths[1]) as right:
                if not np.array_equal(left['x_m'], right['x_m']):
                    raise ValueError('Stations changed')
                for label, data in (('fine', left), ('boundary_dense', right)):
                    for x, force in zip(data['x_m'], data['diffraction_density'], strict=True):
                        station_rows.append(dict(radius=variant['radius_beams'],
                            frequency=frequency, discretization=label, x_m=x,
                            heave_density_real=force[0].real, heave_density_imag=force[0].imag,
                            heave_density_abs=abs(force[0])))
                for component in ('incident', 'diffraction', 'total'):
                    for j, mode in enumerate(('heave', 'geometric_pitch')):
                        delta = compare(left[component], right[component])[j]
                        rows.append(dict(comparison='boundary_refinement', radius=variant['radius_beams'],
                            frequency=frequency, component=component, mode=mode, relative_change=delta))
    for radius, dense in dense_paths[1:]:
        for frequency in contract['frequencies']:
            with np.load(dense_paths[0][1]/f'fields_{frequency:g}.npz') as left, np.load(dense/f'fields_{frequency:g}.npz') as right:
                for component in ('incident', 'diffraction', 'total'):
                    for j, mode in enumerate(('heave', 'geometric_pitch')):
                        rows.append(dict(comparison='dense_radius_vs_3', radius=radius,
                            frequency=frequency, component=component, mode=mode,
                            relative_change=compare(left[component], right[component])[j]))
    frame = pd.DataFrame(rows)
    frame['within_screening'] = frame.relative_change <= contract['screening_relative_change']
    out.mkdir(parents=True, exist_ok=False)
    frame.to_csv(out/'comparison.csv', index=False)
    pd.DataFrame(station_rows).to_csv(out/'station_density.csv', index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        screening_pass=bool(frame.within_screening.all()),
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), indent=2))
    print(frame[(frame.component=='diffraction') & (frame['mode']=='heave')].to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
