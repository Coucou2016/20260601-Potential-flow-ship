"""Separate temporal, transverse and panel-integration changes without acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def run(out):
    root=Path(__file__).resolve().parents[1]/'outputs'
    names={
        'base321':'kang_bounded_transfer_321_20260924',
        'base641':'kang_bounded_spatial_r1_641_20260924',
        'fine641':'kang_bounded_spatial_r2_641_20260924',
        'exact321':'kang_bounded_analytic_panels_321_20260924',
        'exactfine641':'kang_bounded_analytic_panels_r2_641_20260924',
        'bodyfine321':'kang_bounded_analytic_b128_c96_321_20260924',
        'controlfine321':'kang_bounded_analytic_b64_c192_321_20260924'}
    data={}; contracts={}; hashes={}
    for key,name in names.items():
        path=root/name
        contracts[key]=json.loads((path/'contract.json').read_text())
        with np.load(path/'fields.npz') as fields:
            data[key]={k:fields[k].copy() for k in ('incident','diffraction','total')}
        for filename in ('contract.json','fields.npz'):
            p=path/filename; hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    for contract in contracts.values():
        if (contract['omega_e_sqrt_L_g']!=3 or contract['history_policy']!='full'
                or contract['exposure_policy']!='bounded_nearest_unvalidated'):
            raise ValueError('Unexpected candidate definition')
    pairs=[('longitudinal_only','base321','base641'),
           ('transverse_only','base641','fine641'),
           ('panel_integration_only','base321','exact321'),
           ('analytic_joint_longitudinal_transverse','exact321','exactfine641'),
           ('body_only','exact321','bodyfine321'),
           ('control_only','exact321','controlfine321')]
    rows=[]
    for label,left,right in pairs:
        a,b=contracts[left],contracts[right]
        allowed={'body_only':{'body_panels'},'control_only':{'control_panels'}}.get(label,set())
        for key in ('radius_beams','body_panels','control_panels','pressure_route','old_velocity_policy','speed_m_s'):
            if a[key]!=b[key] and key not in allowed:
                raise ValueError(f'Unexpected changed invariant: {key}')
        if allowed:
            for key in ('stations','inner_nodes_per_side','outer_panels_per_side','panel_integration'):
                if a[key]!=b[key]:
                    raise ValueError(f'Unexpected changed single-factor configuration: {key}')
        np.testing.assert_allclose(a['dt_s']*a['history_steps'],b['dt_s']*b['history_steps'])
        for component in ('incident','diffraction','total'):
            for j,mode in enumerate(('heave','pitch')):
                first,last=data[left][component][j],data[right][component][j]
                if not np.isfinite([first,last]).all() or abs(first)<1e-12:
                    raise ValueError('Nonfinite or near-zero comparison requires a separate frozen tolerance')
                rows.append(dict(comparison=label,component=component,mode=mode,
                    first_real=float(first.real),first_imag=float(first.imag),
                    last_real=float(last.real),last_imag=float(last.imag),
                    relative_complex_change=float(abs(last-first)/abs(first))))
    out.mkdir(parents=True,exist_ok=False)
    frame=pd.DataFrame(rows); frame.to_csv(out/'comparison.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        all_frequency_spatial_convergence=False,body_and_control_refinement_complete=False,
        independent_complex_reference_complete=False,hashes=hashes),indent=2))
    print(frame[['comparison','component','mode','relative_complex_change']].to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
