"""Paired temporal/longitudinal refinement, not complete spatial/physical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def run(out):
    root=Path(__file__).resolve().parents[1]
    out.mkdir(parents=True,exist_ok=False)
    reference=root/'benchmarks/kang_excitation_digitization_v4_20260924/amplitudes.csv'
    ref=pd.read_csv(reference)
    rows=[]; hashes={str(reference):hashlib.sha256(reference.read_bytes()).hexdigest()}
    for frequency in (2,3,4):
        cases=[]
        for n in (161,321):
            prefix='kang_bounded_transfer' if frequency==3 else f'kang_bounded_transfer_w{frequency}'
            path=root/f'outputs/{prefix}_{n}_20260924'
            contract=json.loads((path/'contract.json').read_text())
            if (contract['omega_e_sqrt_L_g']!=frequency or contract['stations']!=n
                    or contract['exposure_policy']!='bounded_nearest_unvalidated'
                    or contract['old_velocity_policy']!='transferred' or contract['history_policy']!='full'):
                raise ValueError('Unexpected candidate configuration')
            with np.load(path/'fields.npz') as data:
                fields={key:data[key].copy() for key in ('x_m','incident','diffraction','total')}
            cases.append((contract,fields))
            for name in ('contract.json','fields.npz'):
                p=path/name
                hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        c,a=cases[0]; d,b=cases[1]
        for key in ('radius_beams','body_panels','control_panels','inner_nodes_per_side','outer_panels_per_side','pressure_route'):
            if c[key]!=d[key]:
                raise ValueError(f'Unpaired invariant: {key}')
        np.testing.assert_allclose(a['x_m'],b['x_m'][::2],rtol=0,atol=1e-12)
        np.testing.assert_allclose(c['history_steps']*c['dt_s'],d['history_steps']*d['dt_s'])
        for index,mode in enumerate(('heave','pitch')):
            norm=1000*9.80665*(29144/51975*3*.3*.1875)/(3 if index==0 else 1)
            amplitude=abs(b['total'][index])/norm
            matched=ref[(ref.component==mode)&(ref.omega_e_sqrt_L_g==frequency)].iloc[0]
            available=bool(pd.notna(matched.amplitude))
            rows.append(dict(frequency=frequency,mode=mode,
                incident_complex_change=float(abs(b['incident'][index]-a['incident'][index])/max(abs(a['incident'][index]),1e-30)),
                diffraction_complex_change=float(abs(b['diffraction'][index]-a['diffraction'][index])/max(abs(a['diffraction'][index]),1e-30)),
                total_complex_change=float(abs(b['total'][index]-a['total'][index])/max(abs(a['total'][index]),1e-30)),
                fine_amplitude=float(amplitude),reference_status=str(matched.status),
                reference_amplitude=float(matched.amplitude) if available else None,
                candidate_reference_relative_difference=float(abs(amplitude-matched.amplitude)/matched.amplitude) if available else None))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'comparison.csv',index=False)
    summary=dict(stage_acceptance=False,complete_spatial_refinement=False,reference_admitted=False,
        frequencies=[2,3,4],max_diffraction_complex_change=float(frame.diffraction_complex_change.max()),
        max_total_complex_change=float(frame.total_complex_change.max()),hashes=hashes,
        limitations=['No phase reference','Figure amplitudes pending visual audit',
                     'No transverse/body/control refinement','Contact-state closure unvalidated',
                     'Raw midship moment not verified experimental CG moment'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(frame.to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
