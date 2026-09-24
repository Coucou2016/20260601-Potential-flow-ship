"""Separate frozen experimental regression for the coarse diagnostic candidate."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scripts.evaluate_longitudinal_stage import REFERENCE_SHA256
from scripts.run_regular_head_sea_gate2_acceptance import _motion_metrics


def verify_saved_response(record, data):
    expected = np.array([record['q3_real']+1j*record['q3_imag'], record['q5_real']+1j*record['q5_imag']])
    if not np.allclose(expected,data['response'],rtol=1e-10,atol=1e-12):
        raise ValueError('CSV response differs from saved dynamics')
    if not np.isclose(record['omega'],float(data['omega']),rtol=1e-10,atol=1e-12):
        raise ValueError('CSV frequency differs from saved dynamics')


def evaluate(run, frozen, destination=None, variant='combined'):
    if variant not in ('baseline','radiation_only','excitation_only','combined'):
        raise ValueError('Unknown paired response variant')
    summary = json.loads((run/'summary.json').read_text())
    if summary.get('computation_complete') is not True:
        raise ValueError('Candidate computation is incomplete')
    contract = json.loads((frozen/'contract.json').read_text())
    candidate_contract = json.loads((run/'contract.json').read_text())
    for name,key in (('run.json','input_sha256'),('conditions.csv','conditions_sha256')):
        if hashlib.sha256((frozen/name).read_bytes()).hexdigest() != contract[key]:
            raise ValueError('Frozen contract hash mismatch')
    if contract['input_sha256'] not in candidate_contract['hashes'].values():
        raise ValueError('Candidate does not match frozen input')
    config = json.loads((frozen/'run.json').read_text())
    conditions = pd.read_csv(frozen/'conditions.csv')
    values = pd.read_csv(run/'candidate.csv') if variant=='combined' else pd.read_csv(run/'paired_responses.csv')
    if variant!='combined':
        values=values[values.variant==variant].copy()
    if len(conditions)!=24 or len(values)!=24 or values.duplicated(['case','frequency_index']).any():
        raise ValueError('Missing or duplicate cases')
    source = Path(__file__).resolve().parents[1]/'benchmarks/begovic2020/begovic2020_mono_efd_motion_digitized.csv'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=REFERENCE_SHA256:
        raise ValueError('Experimental reference hash mismatch')
    reference = pd.read_csv(source)
    metrics,comparisons, residuals = [],[],[]
    for case,(fn,group) in zip(config['cases'],conditions.groupby('fn_b',sort=True),strict=True):
        current = values[values.case==case['id']].sort_values('frequency_index').copy()
        if len(current)!=8 or list(current.frequency_index)!=list(range(8)) or not np.allclose(current.omega,group.omega_e_rad_s,rtol=1e-9):
            raise ValueError('Frequency coverage mismatch')
        ref = reference[np.isclose(reference.fn_b,fn)].set_index('case_code').loc[group.case_code]
        current['heave_rao_m_per_m'] = np.hypot(current.q3_real,current.q3_imag)
        current['pitch_rao_rad_per_wave_slope'] = np.hypot(current.q5_real,current.q5_imag)/current.wavenumber
        current['linear_gate_eligible'] = group.linear_eligible.to_numpy()
        for key in ('heave_rao_m_per_m','pitch_rao_rad_per_wave_slope'):
            current['reference_'+key] = ref[key].to_numpy()
        current['case_code'] = group.case_code.to_numpy()
        for index in range(8):
            with np.load(run/f"{case['id']}_frequency{index}.npz") as d:
                q = d['response'] if variant=='combined' else d['paired_'+variant]
                verify_saved_response(current.iloc[index],dict(response=q,omega=d['omega']))
                w = float(d['omega'])
                if variant in ('baseline','excitation_only'):
                    matrix = d['restoring']-w*w*d['rigid_mass']-d['old_radiation']
                else:
                    matrix = d['restoring']-w*w*(d['rigid_mass']+d['added_mass'])+1j*w*d['damping']
                force = d['old_excitation'] if variant in ('baseline','radiation_only') else d['excitation']
                residual = np.linalg.norm(matrix@q-force)/max(np.linalg.norm(force),1e-15)
                residuals.append(residual)
                if not np.isfinite(residual) or residual>1e-10:
                    raise ValueError('Saved candidate dynamics do not reconstruct')
        metrics.append(_motion_metrics(current,scope=case['id']))
        comparisons.append(current)
    destination = run/('experimental_regression' if variant=='combined' else 'experimental_regression_'+variant) if destination is None else destination
    destination.mkdir(exist_ok=False)
    result = pd.concat(metrics,ignore_index=True)
    result.to_csv(destination/'per_speed_metrics.csv',index=False)
    pd.concat(comparisons,ignore_index=True).to_csv(destination/'comparison.csv',index=False)
    (destination/'status.json').write_text(json.dumps(dict(
        stage_acceptance='NOT_PASSED',scope='Coarse diagnostic candidate, not a formal production run',
        variant=variant,evaluator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        per_speed_motion_pass=bool(result.status.eq('PASS').all()),
        reference_sha256=REFERENCE_SHA256,reference_role='regression_not_blind_holdout',
        max_dynamic_reconstruction_residual=max(residuals),
        missing=['independent_excitation','three_grid','long_wave_background','dense_peaks','stability','Fridsma','full_regression']),indent=2))
    print(result.to_string(index=False))
    return 2  # This diagnostic cannot satisfy the full stage contract.


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--frozen',type=Path,required=True)
    p.add_argument('--out',type=Path)
    p.add_argument('--variant',choices=('baseline','radiation_only','excitation_only','combined'),default='combined')
    a=p.parse_args()
    raise SystemExit(evaluate(a.run,a.frozen,a.out,a.variant))
