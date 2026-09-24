"""Frozen single-axis refinement, retaining historical station-only entry point."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.probe_eulerian_diffraction import run as probe
from scripts.audit_eulerian_diffraction_grid import compare
from planing_seakeeping.linear_case import load_linear_case


def run(config, out, axis='stations', integration_route='midpoint', values=None, fixed_free=None, grading_exponent=1., history_steps=128):
    if axis not in ('stations', 'free'):
        raise ValueError('axis must be stations or free')
    if not 1. <= grading_exponent <= 2.:
        raise ValueError('grading_exponent must be finite and between 1 and 2')
    if fixed_free is not None and (axis != 'stations' or type(fixed_free) is not int or fixed_free < 4 or fixed_free % 2):
        raise ValueError('fixed_free requires station axis and an even integer >= 4')
    values = ([57, 85, 113] if axis == 'stations' else [48, 72, 96]) if values is None else list(values)
    if (len(values) != 3 or any(type(v) is not int or v < (3 if axis == 'stations' else 4) for v in values)
            or any(b <= a for a,b in zip(values,values[1:]))
            or (axis == 'free' and any(v % 2 for v in values))):
        raise ValueError('Three increasing valid grid counts required')
    if type(history_steps) is not int or history_steps < (max(values) if axis == 'stations' else 85):
        raise ValueError('history_steps must cover all stations')
    from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route
    with panel_integration_route(integration_route):
        pass
    raw, boat = load_linear_case(config)
    out.mkdir(parents=True, exist_ok=False)
    contract = dict(axis=axis, values=values, stations=85, grid_level=1, body_panels=60,
        integration_route=integration_route,
        waterline_grading_exponent=grading_exponent,
        free=72 if fixed_free is None else fixed_free, control=96, history_steps=history_steps, history_quadrature=48,
        history_k_max=25., frequency_index=4,
        config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        case_ids=[c['id'] for c in raw['cases']],
        relative_limit=.05, near_zero_threshold=.02, absolute_limit=.001,
        scope='Single-axis diagnostic; not full-band or physical acceptance')
    (out/'contract.json').write_text(json.dumps(contract, indent=2))
    sources = [Path(__file__), Path('scripts/probe_eulerian_diffraction.py'),
               Path('scripts/audit_eulerian_diffraction_grid.py')]
    (out/'driver_hashes.json').write_text(json.dumps(
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2))
    levels = []
    for n in values:
        override = {'stations_override' if axis == 'stations' else 'free_panels_override': n}
        if fixed_free is not None:
            override['free_panels_override'] = fixed_free
        if integration_route != 'midpoint':
            override['integration_route'] = integration_route
        if grading_exponent != 1.:
            override['grading_exponent'] = grading_exponent
        if history_steps != 128:
            override['history_steps_override'] = history_steps
        probe(config, out/f'{axis}_{n}', grid_level=1, **override)
        levels.append(pd.read_csv(out/f'{axis}_{n}/force_changes.csv'))
        print(f'{axis} {n} complete', flush=True)
    checks = []
    for pair, left, right in [('coarse_mid', levels[0], levels[1]),
                              ('mid_fine', levels[1], levels[2])]:
        paired = left.merge(right, on=['case', 'omega', 'mode'],
            suffixes=('_left', '_right'), validate='one_to_one')
        if len(paired) != 2*len(raw['cases']):
            raise ValueError('Missing case coverage')
        for row in paired.to_dict('records'):
            scale = boat.rho_water_kg_m3*boat.gravity_m_s2*boat.length_m*boat.beam_m
            if row['mode'] == 5:
                scale *= boat.length_m
            for component in ('original', 'delta', 'candidate', 'normal', 'tangent'):
                mid = complex(row[f'{component}_real_left'], row[f'{component}_imag_left'])
                fine = complex(row[f'{component}_real_right'], row[f'{component}_imag_right'])
                change, tolerance, passed = compare(mid, fine, scale)
                checks.append(dict(pair=pair, case=row['case'], mode=row['mode'], component=component,
                    absolute_change=abs(mid-fine), dimensionless_change=change,
                    tolerance=tolerance, passed=passed))
    frame = pd.DataFrame(checks)
    frame.to_csv(out/'checks.csv', index=False)
    final = frame[frame.pair == 'mid_fine']
    result = dict(checks=len(final), passed_count=int(final.passed.sum()),
        numerical_passed=bool(final.passed.all()), physical_acceptance='NOT_PASSED',
        full_band_acceptance=False)
    (out/'results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--axis', choices=('stations', 'free'), default='stations')
    parser.add_argument('--integration-route',choices=('midpoint','analytic_straight_midpoint_curved','reconstructed_symmetric'),default='midpoint')
    parser.add_argument('--values',type=int,nargs=3)
    parser.add_argument('--fixed-free',type=int)
    parser.add_argument('--grading-exponent',type=float,default=1.)
    parser.add_argument('--history-steps',type=int,default=128)
    args = parser.parse_args()
    run(args.config, args.out, args.axis, args.integration_route, args.values, args.fixed_free, args.grading_exponent, args.history_steps)
