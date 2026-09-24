"""Compare solved free-surface fields on common locations, without extrapolation."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def common_side_samples(y, values, fine_y, fine_values):
    if (len(y) != len(values) or len(fine_y) != len(fine_values)
            or not all(np.isfinite(v).all() for v in (y,values,fine_y,fine_values))
            or np.any(np.diff(y) <= 0) or np.any(np.diff(fine_y) <= 0)):
        raise ValueError('Finite increasing grids and matching fields required')
    indices, interpolated = [], []
    for sign in (-1,1):
        source = np.flatnonzero(sign*fine_y > 0)
        targets = np.flatnonzero(sign*y > 0)
        if len(source) < 2:
            raise ValueError('Each fine-grid side needs at least two samples')
        targets = targets[(y[targets] >= fine_y[source[0]]) & (y[targets] <= fine_y[source[-1]])]
        indices.extend(targets)
        interpolated.extend(np.interp(y[targets],fine_y[source],fine_values[source].real)
                            +1j*np.interp(y[targets],fine_y[source],fine_values[source].imag))
    if not indices:
        raise ValueError('No common side coordinates')
    return np.asarray(indices), np.asarray(interpolated)


def common_station_pairs(x, fine_x):
    x,fine_x=np.asarray(x),np.asarray(fine_x)
    if (not np.isfinite(x).all() or not np.isfinite(fine_x).all()
            or np.any(np.diff(x)<=0) or np.any(np.diff(fine_x)<=0)):
        raise ValueError('Increasing finite stations required')
    pairs=[]
    for i,value in enumerate(x):
        found=np.flatnonzero(np.isclose(fine_x,value,atol=1e-12,rtol=1e-12))
        if len(found)>1:
            raise ValueError('Ambiguous station match')
        if len(found)==1:
            pairs.append((i,int(found[0])))
    if len(pairs)<3:
        raise ValueError('At least three common stations required')
    return pairs


def clock_origin_offset(local_time, time_before):
    offset=np.asarray(time_before)-np.asarray(local_time)
    if not np.isfinite(offset).all() or not np.allclose(offset,offset[0],atol=1e-10,rtol=1e-10):
        raise ValueError('Free-surface clock must differ only by a constant origin')
    return float(offset[0])


def run(mid, fine, out, common_stations=False):
    inputs = [*sorted(mid.glob('free_surface_*.npz')), *sorted(fine.glob('free_surface_*.npz'))]
    if len(inputs) != 6:
        raise ValueError('Three speed snapshots required per grid')
    out.mkdir(parents=True,exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*inputs]},
        comparison='Same x and time; separate sides; fine to mid interpolation; no extrapolation',
        common_station_subset=common_stations,
        time_comparison='Equal physical local time and phase; verify each pre-solve clock has only a constant origin offset' if common_stations else 'All recorded times equal',
        scope='Field diagnostic only, no new acceptance threshold'),indent=2))
    rows=[]
    clock_rows=[]
    for path in inputs[:3]:
        with np.load(path) as a, np.load(fine/path.name) as b:
            if common_stations:
                pairs=common_station_pairs(a['x'],b['x'])
                ia,ib=np.asarray(pairs).T
                for key in ('local_time','phase'):
                    if not np.allclose(a[key][ia],b[key][ib],atol=1e-10,rtol=1e-10):
                        raise ValueError('Common station physical times/phases must match')
                for label,data in [('mid',a),('fine',b)]:
                    clock_rows.append(dict(case=path.stem,grid=label,
                        clock_minus_local_time_s=clock_origin_offset(data['local_time'],data['time_before'])))
            else:
                for key in ('x','local_time','time_before','time_after','phase'):
                    if not np.array_equal(a[key],b[key]):
                        raise ValueError('Matching longitudinal and time grids required')
                pairs=list(zip(range(len(a['x'])),range(len(b['x']))))
            for field in ('phi_local','normal_derivative_local','elevation_local'):
                for i,j in pairs:
                    x=a['x'][i]
                    indices, ref = common_side_samples(a['y'][i],a[field][i],b['y'][j],b[field][j])
                    weight=a['length'][i,indices]
                    difference=a[field][i,indices]-ref
                    rms=float(np.sqrt(np.sum(weight*np.abs(difference)**2)/np.sum(weight)))
                    reference_rms=float(np.sqrt(np.sum(weight*np.abs(ref)**2)/np.sum(weight)))
                    rows.append(dict(case=path.stem,field=field,x=x,samples=len(indices),
                        rms_difference=rms,reference_rms=reference_rms,
                        relative_rms=rms/reference_rms if reference_rms>0 else np.nan,
                        reflection_residual=float(np.max(np.abs(a[field][i]-a[field][i,::-1])))))
    frame=pd.DataFrame(rows)
    if clock_rows:
        pd.DataFrame(clock_rows).to_csv(out/'clock_origins.csv',index=False)
    frame.to_csv(out/'station_field_changes.csv',index=False)
    summary=frame.groupby(['case','field'])[['rms_difference','relative_rms','reflection_residual']].agg(['median','max'])
    summary.to_csv(out/'field_summary.csv')
    print(summary.to_string())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mid',type=Path,required=True)
    p.add_argument('--fine',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--common-stations',action='store_true')
    a=p.parse_args()
    run(a.mid,a.fine,a.out,a.common_stations)
