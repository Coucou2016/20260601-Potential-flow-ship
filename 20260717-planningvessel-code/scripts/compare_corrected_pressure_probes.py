"""Compare corrected-normal pressure diagnostics using existing frozen grid limits."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from scripts.audit_eulerian_diffraction_grid import compare
from planing_seakeeping.linear_case import load_linear_case


def run(config, mid, fine, out):
    raw, boat = load_linear_case(config)
    frames = []
    hashes = {}
    contracts = []
    for directory in (mid, fine):
        contract = json.loads((directory/'contract.json').read_text())
        if (contract.get('normal_derivative_conversion') != -1
                or contract.get('gradient_normal_convention') != 'stored_hull_outward'
                or contract.get('solver_normal_convention') != 'fluid_domain_outward'):
            raise ValueError('Explicit corrected normal conventions required')
        if contract['config_sha256'] != hashlib.sha256(config.read_bytes()).hexdigest():
            raise ValueError('Configuration hash mismatch')
        sources = json.loads((directory/'source_hashes.json').read_text())
        for path, digest in sources.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ValueError(f'Source changed: {path}')
        frame = pd.read_csv(directory/'force_changes.csv')
        expected = {(c['id'], c['encounter_omega_rad_s'][4], mode)
                    for c in raw['cases'] for mode in (3, 5)}
        if len(frame) != 6 or set(frame[['case','omega','mode']].itertuples(index=False, name=None)) != expected:
            raise ValueError('Incomplete or duplicate representative cases')
        frames.append(frame)
        contracts.append(contract)
        for name in ('contract.json','source_hashes.json','force_changes.csv'):
            p = directory/name
            hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    varying = {'stations','body','free','control','history_quadrature_count','corner_node'}
    if {k:v for k,v in contracts[0].items() if k not in varying} != {
            k:v for k,v in contracts[1].items() if k not in varying}:
        raise ValueError('Non-grid configuration changed')
    if [(c['stations'],c['body'],c['free'],c['control'],c['history_quadrature_count'])
            for c in contracts] != [(85,60,72,96,48),(113,72,96,120,64)]:
        raise ValueError('Expected original middle/fine grid contract')
    pair = frames[0].merge(frames[1], on=['case','omega','mode'],
                           suffixes=('_mid','_fine'), validate='one_to_one')
    rows = []
    for r in pair.to_dict('records'):
        scale = boat.rho_water_kg_m3*boat.gravity_m_s2*boat.length_m*boat.beam_m
        if r['mode'] == 5:
            scale *= boat.length_m
        for component in ('original','delta','candidate','normal','tangent'):
            values = [complex(r[f'{component}_real_{level}'],r[f'{component}_imag_{level}'])
                      for level in ('mid','fine')]
            change, tolerance, passed = compare(*values, scale)
            rows.append(dict(case=r['case'], mode=r['mode'], component=component,
                dimensionless_change=change, tolerance=tolerance, passed=passed))
    checks = pd.DataFrame(rows)
    out.mkdir(parents=True, exist_ok=False)
    checks.to_csv(out/'checks.csv',index=False)
    result = dict(checks=len(checks), passed=int(checks.passed.sum()),
        full_band_acceptance=False, physical_acceptance=False, hashes=hashes,
        thresholds_source='scripts/audit_eulerian_diffraction_grid.py: existing 5%/0.001/0.02 rules')
    (out/'results.json').write_text(json.dumps(result,indent=2))
    print(checks.to_string(index=False))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('config','mid','fine','out'):
        p.add_argument('--'+name,type=Path,required=True)
    args = p.parse_args()
    run(args.config,args.mid,args.fine,args.out)
