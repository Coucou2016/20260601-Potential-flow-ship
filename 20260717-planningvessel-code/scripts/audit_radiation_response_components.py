"""Exact operator-change attribution, without reading experimental responses."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def decompose(rigid, restoring, old, new, baseline, omega):
    arrays = [np.asarray(v) for v in (rigid, restoring, old, new)]
    if any(v.shape != (2, 2) or not np.isfinite(v).all() for v in arrays):
        raise ValueError('Expected finite 2 by 2 matrices')
    baseline = np.asarray(baseline)
    if baseline.shape != (2,) or not np.isfinite(baseline).all():
        raise ValueError('Expected finite two-component baseline')
    if not np.isfinite(omega) or omega <= 0:
        raise ValueError('Encounter frequency must be positive')
    dynamic = restoring - omega**2 * rigid - new
    delta = new - old
    contributions = {}
    for i, row in enumerate((3, 5)):
        for j, col in enumerate((3, 5)):
            for kind, value in [('A', delta[i, j].real), ('B', 1j*delta[i, j].imag)]:
                forcing = np.zeros(2, complex)
                forcing[i] = value * baseline[j]
                contributions[f'{kind}{row}{col}'] = np.linalg.solve(dynamic, forcing)
    return contributions


def run(source, config, out):
    raw = json.loads(config.read_text(encoding='utf-8'))
    length = float(raw['boat']['length_m'])
    if not np.isfinite(length) or length <= 0:
        raise ValueError('Positive reference length required')
    expected = [f"{c['id']}_frequency{i}.npz" for c in raw['cases']
                for i in range(len(c['encounter_omega_rad_s']))]
    if len(expected) != 24 or set(p.name for p in source.glob('*.npz')) != set(expected):
        raise ValueError('Expected exactly the frozen 24 saved cases')
    scale = np.array([1., length])
    rows, checks, hashes = [], [], {}
    for name in expected:
        path = source/name
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path, allow_pickle=False) as data:
            omega = float(data['omega'])
            case, index_text = path.stem.split('_frequency')
            index = int(index_text)
            frozen = next(c for c in raw['cases'] if c['id'] == case)
            if not np.isclose(omega, frozen['encounter_omega_rad_s'][index], rtol=0, atol=1e-12):
                raise ValueError('Saved frequency differs from frozen case')
            old, new = data['old_radiation'], data['new_radiation']
            parts = decompose(data['rigid_mass'], data['restoring'], old, new,
                              data['paired_baseline'], omega)
            summed = sum(parts.values())
            target = data['paired_radiation_increment']
            residual = np.linalg.norm(scale*(summed-target))/max(np.linalg.norm(scale*target), 1e-12)
            total = data['paired_combined']-data['paired_baseline']
            closure = np.linalg.norm(scale*(summed+data['paired_excitation_increment']-total))/max(np.linalg.norm(scale*total), 1e-12)
            if not np.isfinite([residual, closure]).all() or max(residual, closure) > 1e-10:
                raise ValueError('Response decomposition failed closure')
            checks.append(dict(case=case, frequency_index=index, radiation_residual=residual,
                               total_residual=closure))
            for label, response in parts.items():
                i, j = (0 if c == '3' else 1 for c in label[1:])
                factor = omega**2 if label[0] == 'A' else -omega
                extract = np.real if label[0] == 'A' else np.imag
                rows.append(dict(case=case, frequency_index=index, omega=omega, coefficient=label,
                    old_value=float(extract(old[i,j])/factor), new_value=float(extract(new[i,j])/factor),
                    heave_real=response[0].real, heave_imag=response[0].imag,
                    pitch_real=response[1].real, pitch_imag=response[1].imag,
                    scaled_response_norm=float(np.linalg.norm(scale*response))))
    out.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(rows).to_csv(out/'components.csv', index=False)
    pd.DataFrame(checks).to_csv(out/'closure.csv', index=False)
    summary = dict(stage_acceptance='NOT_PASSED', diagnostic_cases=24, components_per_case=8,
        max_radiation_residual=max(c['radiation_residual'] for c in checks),
        max_total_residual=max(c['total_residual'] for c in checks),
        interpretation='Exact finite operator-change decomposition using new dynamic inverse and old response; not experimental error attribution, energy fractions, or coefficient calibration',
        ranking_metric='Euclidean norm of [delta_heave, length*delta_pitch]; complex contributions may cancel',
        length_m=length, input_hashes=hashes,
        config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.config, args.out), indent=2))
