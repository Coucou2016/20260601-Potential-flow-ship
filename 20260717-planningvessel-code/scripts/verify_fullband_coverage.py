"""Independent coverage, provenance and arithmetic check for full-band runs."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

COMPONENTS = ('A33','A35','A53','A55','B33','B35','B53','B55','F3','F5')


def verify_values(frame, contract):
    keys = ['level','case','omega','component']
    if frame.duplicated(keys).any():
        raise ValueError('Duplicate coefficient records')
    expected = {(level, case, frequency, component)
        for level in range(3) for case, frequencies in contract['frequencies'].items()
        for frequency in frequencies for component in COMPONENTS}
    actual = set(frame[keys].itertuples(index=False, name=None))
    if actual != expected or len(frame) != len(expected):
        raise ValueError('Missing or unknown coefficient records')
    if not np.isfinite(frame[['real','imag']].to_numpy()).all():
        raise ValueError('Non-finite coefficient values')
    if (contract['relative_limit'], contract['dimensionless_absolute_limit'],
            contract['near_zero_dimensionless_threshold']) != (.05,.001,.02):
        raise ValueError('Frozen thresholds changed')
    pairs = frame[frame.level==1].merge(frame[frame.level==2], on=keys[1:],
        suffixes=('_mid','_fine'), validate='one_to_one')
    left = pairs.real_mid + 1j*pairs.imag_mid
    right = pairs.real_fine + 1j*pairs.imag_fine
    pairs['absolute_change'] = abs(left-right)
    pairs['tolerance'] = np.where(abs(right)<.02, .001, .05*abs(right))
    pairs['passed'] = pairs.absolute_change <= pairs.tolerance
    return pairs


def verify_input_scope(contract, config_path):
    data=Path(config_path).read_bytes()
    if hashlib.sha256(data).hexdigest()!=contract['input_sha256']:
        raise ValueError('Original input hash mismatch')
    config=json.loads(data)
    cases=config.get('cases',[])
    if len(cases)!=3 or len({c['id'] for c in cases})!=3:
        raise ValueError('Full stage requires three distinct speed cases')
    expected={c['id']:c['encounter_omega_rad_s'] for c in cases}
    if any(len(v)!=8 or len(set(v))!=8 for v in expected.values()):
        raise ValueError('Full stage requires eight distinct frequencies per speed')
    if contract.get('selected_case_endpoint_diagnostic') is not None or contract['frequencies']!=expected:
        raise ValueError('Contract does not cover all original input frequencies')
    return expected


def run(directory, out, config_path):
    contract_bytes = (directory/'contract.json').read_bytes()
    if hashlib.sha256(contract_bytes).hexdigest() != (directory/'contract.sha256').read_text().strip():
        raise ValueError('Contract hash mismatch')
    contract = json.loads(contract_bytes)
    verify_input_scope(contract,config_path)
    sources = json.loads((directory/'source_hashes.json').read_text())
    for name, digest in sources.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Source hash mismatch: {name}')
    frame = pd.read_csv(directory/'dimensionless_coefficients.csv', float_precision='round_trip')
    recomputed = verify_values(frame,contract)
    stored = pd.read_csv(directory/'fine_grid_checks.csv', float_precision='round_trip')
    columns = ['case','omega','component','absolute_change','tolerance','passed']
    pd.testing.assert_frame_equal(recomputed[columns].reset_index(drop=True),stored[columns].reset_index(drop=True),
                                  check_exact=False, atol=1e-14, rtol=1e-12)
    result = json.loads((directory/'results.json').read_text())
    if (result['checks'] != len(recomputed) or result['passed_count'] != int(recomputed.passed.sum())
            or result['passed'] is not bool(recomputed.passed.all()) or result['full_stage_passed'] is not False):
        raise ValueError('Reported results inconsistent with full data')
    out.mkdir(parents=True,exist_ok=False)
    report = dict(records=len(frame), fine_checks=len(recomputed),
        checks_passed=int(recomputed.passed.sum()), coverage_and_arithmetic_verified=True,
        source_hashes_verified=True, original_24_case_input_verified=True, full_stage_passed=False,
        limitation='Numerical convergence only; original pressure gradient; no experimental acceptance')
    (out/'verification.json').write_text(json.dumps(report,indent=2))
    recomputed.to_csv(out/'recomputed_checks.csv',index=False)
    summary = recomputed.groupby('case').agg(checks=('passed','size'), passed=('passed','sum'))
    summary.to_csv(out/'by_speed.csv')
    print(json.dumps(report))
    print(summary.to_string())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True)
    a = p.parse_args()
    run(a.run,a.out,a.config)
