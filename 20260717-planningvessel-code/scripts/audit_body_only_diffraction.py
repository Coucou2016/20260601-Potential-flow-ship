"""Isolate body-panel refinement; all other numerical settings remain fixed."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.probe_eulerian_diffraction import run as probe
from scripts.audit_eulerian_diffraction_grid import compare
from planing_seakeeping.linear_case import load_linear_case


def run(config, out):
    raw, boat = load_linear_case(config)
    out.mkdir(parents=True, exist_ok=False)
    contract = dict(body_panels=[36, 60, 84], grid_level=1,
        config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        frequency_index=4, case_ids=[c['id'] for c in raw['cases']],
        relative_limit=.05, near_zero_threshold=.02, absolute_limit=.001,
        scope='Body-only diagnostic; not full-band or physical acceptance')
    (out/'contract.json').write_text(json.dumps(contract, indent=2))
    levels = []
    for n in contract['body_panels']:
        probe(config, out/f'body_{n}', grid_level=1, body_panels_override=n)
        levels.append(pd.read_csv(out/f'body_{n}/force_changes.csv'))
        print(f'Body {n} complete', flush=True)
    paired = levels[1].merge(levels[2], on=['case', 'omega', 'mode'],
        suffixes=('_mid', '_fine'), validate='one_to_one')
    if len(paired) != 2*len(raw['cases']):
        raise ValueError('Missing case coverage')
    checks = []
    for row in paired.to_dict('records'):
        scale = boat.rho_water_kg_m3*boat.gravity_m_s2*boat.length_m*boat.beam_m
        if row['mode'] == 5:
            scale *= boat.length_m
        for component in ('original', 'delta', 'candidate', 'normal', 'tangent'):
            mid = complex(row[f'{component}_real_mid'], row[f'{component}_imag_mid'])
            fine = complex(row[f'{component}_real_fine'], row[f'{component}_imag_fine'])
            change, tolerance, passed = compare(mid, fine, scale)
            checks.append(dict(case=row['case'], mode=row['mode'], component=component,
                dimensionless_change=change, tolerance=tolerance, passed=passed))
    frame = pd.DataFrame(checks)
    frame.to_csv(out/'checks.csv', index=False)
    result = dict(checks=len(frame), passed_count=int(frame.passed.sum()),
        numerical_passed=bool(frame.passed.all()), physical_acceptance='NOT_PASSED',
        full_band_acceptance=False)
    (out/'results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.config, args.out)
