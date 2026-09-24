"""Locate squared field discrepancies; these norms are not physical energy."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scripts.audit_free_surface_fields import common_side_samples


def region_weights(y,length):
    y,length=np.asarray(y),np.asarray(length)
    if y.shape != length.shape or not np.isfinite(y).all() or not np.isfinite(length).all() or np.any(length<=0):
        raise ValueError('Finite positions and positive matching lengths required')
    low,high=np.abs(y)-length/2,np.abs(y)+length/2
    inner,outer=np.min(low),np.max(high)
    if outer<=inner:
        raise ValueError('Positive free-surface span required')
    boundaries=inner+(outer-inner)*np.array([0,.1,.9,1])
    return {name:np.maximum(0,np.minimum(high,b)-np.maximum(low,a))
            for name,a,b in zip(('waterline','interior','control'),boundaries[:-1],boundaries[1:])}


def run(mid,fine,out):
    paths=sorted(mid.glob('free_surface_*.npz'))
    if len(paths)!=3:
        raise ValueError('Three cases required')
    sources=[Path(__file__),Path('scripts/audit_free_surface_fields.py'),*paths,*[fine/p.name for p in paths]]
    out.mkdir(parents=True,exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        regions='Each side: first 10% span from waterline, middle 80%, last 10% near control',
        method='Separate-side interpolation; squared complex discrepancy weighted by panel overlap and x trapezoid',
        scope='Numerical field localization, not energy or physical validation'),indent=2))
    rows=[]
    for path in paths:
        with np.load(path) as a,np.load(fine/path.name) as b:
            if not np.array_equal(a['x'],b['x']) or not np.array_equal(a['local_time'],b['local_time']):
                raise ValueError('Matching station/time grids required')
            for field in ('phi_local','normal_derivative_local','elevation_local'):
                for i,x in enumerate(a['x']):
                    ids,ref=common_side_samples(a['y'][i],a[field][i],b['y'][i],b[field][i])
                    squared=np.abs(a[field][i,ids]-ref)**2
                    weights=region_weights(a['y'][i],a['length'][i])
                    for region,w in weights.items():
                        rows.append(dict(case=path.stem,field=field,x=x,region=region,
                            discrepancy_sq=float(np.sum(w[ids]*squared)),
                            reference_sq=float(np.sum(w[ids]*np.abs(ref)**2))))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'station_regions.csv',index=False)
    summary=[]
    for (case,field,region),group in frame.groupby(['case','field','region']):
        group=group.sort_values('x')
        summary.append(dict(case=case,field=field,region=region,
            integrated_discrepancy_sq=float(np.trapezoid(group.discrepancy_sq,group.x)),
            integrated_reference_sq=float(np.trapezoid(group.reference_sq,group.x))))
    result=pd.DataFrame(summary)
    total=result.groupby(['case','field']).integrated_discrepancy_sq.transform('sum')
    result['discrepancy_share']=result.integrated_discrepancy_sq/total
    result.to_csv(out/'region_summary.csv',index=False)
    print(result.to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mid',type=Path,required=True)
    p.add_argument('--fine',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.mid,a.fine,a.out)
