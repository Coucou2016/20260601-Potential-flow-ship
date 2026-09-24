"""Check weighted moving-trace integration on saved actual diffraction fields."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.kernels.linear_2p5d.weighted_transport import clipped_transport_identity


def run(config,saved,out):
    raw,boat=load_linear_case(config)
    paths=[saved/f"boundary_{case['id']}.npz" for case in raw['cases']]
    if len(paths)!=3 or not all(p.is_file() for p in paths):
        raise ValueError('All three actual boundary snapshots required')
    out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),config,*paths,Path('planing_seakeeping/kernels/linear_2p5d/weighted_transport.py')]
    (out/'contract.json').write_text(json.dumps(dict(cutoff_beams=.5,tolerance=1e-12,
        scope='Same saved potential, piecewise-linear transport identity; not a new hydrodynamic solution',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2))
    rows=[]
    for case,path in zip(raw['cases'],paths):
        with np.load(path) as data:
            x=data['x']
            # Generalized projection measure in bow-up coordinates; no rho/U or phase adapter.
            base=data['normal_z']*data['length']
            measure=np.stack((base,base*(x[:,None]-boat.lcg_m)),axis=2)
            result=clipped_transport_identity(x,data['phi'],measure,data['chain'],.5*boat.beam_m)
            for i,mode in enumerate((3,5)):
                scale=max(sum(abs(result[key][i]) for key in ('bulk','chain','lower_edge','upper_edge')),1e-15)
                row=dict(case=case['id'],mode=mode,relative_identity_residual=abs(result['residual'][i])/scale,
                    omitted_lower_edge_relative_error=abs(result['lower_edge'][i])/scale)
                for key,value in result.items():
                    row[key+'_real'],row[key+'_imag']=value[i].real,value[i].imag
                rows.append(row)
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'weighted_transport.csv',index=False)
    print(frame[['case','mode','relative_identity_residual','omitted_lower_edge_relative_error']].to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--saved',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.config,a.saved,a.out)
