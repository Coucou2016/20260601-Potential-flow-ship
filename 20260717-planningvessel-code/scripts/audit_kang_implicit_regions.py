"""Locate variable-section candidate discrepancy; never tune or select by response."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def run(out):
    root=Path(__file__).resolve().parents[1]
    folders=[root/f'outputs/kang_implicit_anchored_{n}_20260924' for n in (161,321)]
    files=[Path(__file__),*[p/name for p in folders for name in ('contract.json','fields.npz','stations.csv')]]
    contracts=[json.loads((p/'contract.json').read_text()) for p in folders]
    for key in ('route','omega_e_sqrt_L_g','speed_m_s','radius_beams','body_panels','control_panels',
                'inner_nodes_per_side','outer_panels_per_side','exposure_policy','maximum_spacing_ratio','pressure_route'):
        if contracts[0][key]!=contracts[1][key]:
            raise ValueError(f'Unpaired candidate input: {key}')
    rows=[]
    with np.load(folders[0]/'fields.npz') as a,np.load(folders[1]/'fields.npz') as b:
        if not np.allclose(a['x_m'],b['x_m'][::2],atol=1e-13,rtol=0):
            raise ValueError('Station grids do not nest')
        for component in ('incident_density','diffraction_density'):
            for name,mask in [('fore',lambda x:x>=1.5-1e-12),('aft',lambda x:x<=1.5+1e-12)]:
                ma,mb=mask(a['x_m']),mask(b['x_m'])
                ca=np.trapezoid(a[component][ma],a['x_m'][ma],axis=0)
                cb=np.trapezoid(b[component][mb],b['x_m'][mb],axis=0)
                if np.any(abs(cb)<1e-10):
                    raise ValueError('Near-zero region load needs a separately frozen absolute tolerance')
                for j,mode in enumerate(('heave','geometric_pitch')):
                    rows.append(dict(component=component,region=name,mode=mode,
                        coarse_real=ca[j].real,coarse_imag=ca[j].imag,
                        fine_real=cb[j].real,fine_imag=cb[j].imag,
                        relative_complex_difference=float(abs(ca[j]-cb[j])/abs(cb[j]))))
    out.mkdir(parents=True,exist_ok=False)
    pd.DataFrame(rows).to_csv(out/'regions.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        scope='Fore/aft diagnostic partition only, not change of force integration or acceptance region',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
