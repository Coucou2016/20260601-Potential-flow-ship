"""Report every frozen domain trial with complex-force changes, not selected winners."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def compare(base, candidate):
    if base.shape != (2,) or candidate.shape != (2,) or not (
            np.isfinite(base).all() and np.isfinite(candidate).all()):
        raise ValueError('Finite two-component complex forces required')
    if np.any(abs(base) < 1e-10):
        raise ValueError('Near-zero reference requires an independently frozen absolute tolerance')
    return abs(candidate-base)/abs(base)


def run(out):
    root = Path(__file__).resolve().parents[1]
    folder = root/'benchmarks/kang_domain_sensitivity_20260924'
    contracts = [folder/'contract.json', folder/'fine_followup.json']
    files = [Path(__file__), *contracts]
    rows = []
    for path in contracts:
        contract = json.loads(path.read_text())
        base = root/contract['baseline']
        base_config = json.loads((base/'contract.json').read_text())
        files.append(base/'contract.json')
        for variant in contract['runs']:
            candidate = root/variant['out']
            files.append(candidate/'contract.json')
            cfg = json.loads((candidate/'contract.json').read_text())
            for key in ('length', 'beam', 'draft', 'froude_length', 'rho', 'gravity',
                        'frequencies', 'preset', 'endpoint_fraction', 'moment_origin'):
                if cfg[key] != base_config[key]:
                    raise ValueError(f'Incompatible physical or discretization input: {key}')
            if (cfg['config']['control_surface_radius_beams'] != variant['radius_beams']
                    or cfg['options']['history_k_max'] != variant['k_max']):
                raise ValueError('Run does not match frozen variant')
            for frequency in contract['frequencies']:
                paths = [p/f'fields_{frequency:g}.npz' for p in (base, candidate)]
                files.extend(paths)
                with np.load(paths[0]) as left, np.load(paths[1]) as right:
                    if not np.array_equal(left['x_m'], right['x_m']):
                        raise ValueError('Station coordinates changed in domain-only comparison')
                    for component in ('incident', 'diffraction', 'total'):
                        changes = compare(left[component], right[component])
                        for j, mode in enumerate(('heave', 'geometric_pitch')):
                            rows.append(dict(baseline=base.name, variant=candidate.name,
                                frequency=frequency, component=component, mode=mode,
                                complex_relative_change=changes[j],
                                within_screening=bool(changes[j] <= contract['screening_relative_change'])))
    out.mkdir(parents=True, exist_ok=False)
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'comparison.csv', index=False)
    summary = dict(stage_acceptance=False, all_domain_screening_pass=bool(frame.within_screening.all()),
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        limitations=['Only three frequencies', 'Domain and panel spacing coupled',
                    'No experimental pivot asserted', 'Not independent physical validation'])
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    print(frame[(frame.component=='diffraction') & (frame['mode']=='heave')].to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
