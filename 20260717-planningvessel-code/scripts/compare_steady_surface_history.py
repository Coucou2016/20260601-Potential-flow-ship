"""Compare saved surfaces at matching times and common horizontal positions."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def run(coarse, fine, out, spatial_refinement=False):
    meta = [json.loads(p.with_suffix('.json').read_text()) for p in (coarse, fine)]
    changes = {key: [meta[0]['config'].get(key), meta[1]['config'].get(key)]
               for key in set(meta[0]['config']) | set(meta[1]['config'])
               if meta[0]['config'].get(key) != meta[1]['config'].get(key)}
    allowed = {'body_panels_per_side','free_surface_panels_per_side'} if spatial_refinement else set()
    if set(changes)-allowed:
        raise ValueError('Disallowed configuration changes: '+str(sorted(set(changes)-allowed)))
    for key in ('speed_mps','trim_rad','length_m','initial_draft_m'):
        if meta[0][key] != meta[1][key]:
            raise ValueError('Snapshot physical configuration mismatch: '+key)
    beam = 2*meta[0]['config']['chine_half_beam_m']
    speed = meta[0]['speed_mps']
    rows = []
    with np.load(coarse, allow_pickle=False) as a, np.load(fine, allow_pickle=False) as b:
        if spatial_refinement and (a['time_s'].shape != b['time_s'].shape or
                not np.allclose(a['time_s'], b['time_s'], rtol=0, atol=1e-10)):
            raise ValueError('Spatial comparison requires identical time grids')
        for i, time in enumerate(a['time_s']):
            matches = np.flatnonzero(np.isclose(b['time_s'], time, rtol=0, atol=1e-10))
            for side in ('left','right'):
                row = dict(time_s=time, x_from_transom_m=a['x_from_transom_m'][i], side=side)
                if len(matches) != 1:
                    rows.append(dict(row, status='NO_UNIQUE_MATCHING_TIME'))
                    continue
                j = int(matches[0])
                traces = []
                for data, index in ((a,i),(b,j)):
                    y,z,p = (data[f'{index}_{side}_{key}'] for key in ('y_m','z_up_m','potential_m2_s'))
                    if not (np.all(np.diff(y)>0) or np.all(np.diff(y)<0)):
                        break
                    py = y if len(p)==len(y) else (y[:-1]+y[1:])/2
                    if y[0]>y[-1]:
                        y,z,py,p = y[::-1],z[::-1],py[::-1],p[::-1]
                    traces.append((y,z,py,p))
                if len(traces)!=2:
                    rows.append(dict(row,status='NON_SINGLE_VALUED_SURFACE'))
                    continue
                lo = max(t[0][0] for t in traces)
                lo = max(lo, *(t[2][0] for t in traces))
                hi = min(t[0][-1] for t in traces)
                hi = min(hi, *(t[2][-1] for t in traces))
                if hi<=lo:
                    rows.append(dict(row,status='NO_COMMON_DOMAIN'))
                    continue
                yq = np.linspace(lo,hi,101)
                dz = np.interp(yq,traces[1][0],traces[1][1])-np.interp(yq,traces[0][0],traces[0][1])
                dp = np.interp(yq,traces[1][2],traces[1][3])-np.interp(yq,traces[0][2],traces[0][3])
                rows.append(dict(row,status='COMPARED',common_width_m=hi-lo,
                    common_fraction_of_union=(hi-lo)/(max(t[0][-1] for t in traces)-min(t[0][0] for t in traces)),
                    elevation_rms_over_beam=np.sqrt(np.mean(dz**2))/beam,
                    elevation_max_over_beam=np.max(abs(dz))/beam,
                    potential_rms_over_speed_beam=np.sqrt(np.mean(dp**2))/(speed*beam)))
    out.mkdir(parents=True,exist_ok=False)
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'surface_comparison.csv',index=False)
    summary=dict(physical_acceptance='NOT_PASSED', counts=frame.status.value_counts().to_dict(),
        refinement='spatial' if spatial_refinement else 'temporal', config_changes=changes,
        scope='Common-domain surface comparison only; excluded contact zones and unmatched states are not validated',
        metrics='RMS uses 101 equally spaced horizontal samples per side; no potential gauge alignment fitted',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                (coarse,fine,coarse.with_suffix('.json'),fine.with_suffix('.json'),Path(__file__))})
    selected = frame[frame.status == 'COMPARED']
    summary['maxima'] = ({key:float(selected[key].max()) for key in (
        'elevation_rms_over_beam','elevation_max_over_beam','potential_rms_over_speed_beam')}
        if len(selected) else None)
    summary['minimum_common_fraction_of_union'] = (
        float(selected.common_fraction_of_union.min()) if len(selected) else None)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(frame.status.value_counts().to_string())
    print(frame.select_dtypes('number').max().to_string())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('coarse','fine','out'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--spatial-refinement', action='store_true')
    args=parser.parse_args()
    run(args.coarse,args.fine,args.out,args.spatial_refinement)
