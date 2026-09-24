"""Classify actual marching remaps using saved solver grids and states, without invented fills."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.kang_reference_geometry import half_breadth
from planing_seakeeping.kernels.linear_2p5d.formulation import FreeSurfaceMarchingState,resample_free_surface_state
from planing_seakeeping.types import ValidityReport


def run(directory,out):
    contract=json.loads((directory/'contract.json').read_text())
    if not contract.get('save_boundary') or contract['frequencies']!=[2.,3.,4.]:
        raise ValueError('Complete saved boundary states required')
    paths=[directory/f'boundary_{w}.npz' for w in (2,3,4)]
    root=Path(__file__).resolve().parents[1]
    files=[Path(__file__),directory/'contract.json',root/'scripts/kang_reference_geometry.py',
        root/'planing_seakeeping/kernels/linear_2p5d/formulation.py',*paths]
    out.mkdir(parents=True,exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,
        scope='Classify saved explicit marching remaps, no physical replacement state',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2))
    rows=[]
    for w,path in zip((2,3,4),paths,strict=True):
        with np.load(path) as d:
            x=d['x_m']; y=d['free_y']
            if np.any(np.diff(x)<=0) or any(not np.isfinite(d[key]).all() for key in d.files):
                raise ValueError('Invalid saved grids/states')
            previous_beam=half_breadth(x,0.,contract['length'],contract['beam'],contract['draft'])
            exposed_masks=[]
            legacy_phi=[]
            legacy_eta=[]
            for old in range(len(x)-1,0,-1):
                target=old-1
                newly_exposed=abs(y[target])<previous_beam[old]
                outside_midpoints=np.zeros(len(y[target]),bool)
                for sign in (-1,1):
                    source_side=y[old][sign*y[old]>0]
                    selected=sign*y[target]>0
                    outside_midpoints|=selected&((y[target]<source_side.min())|(y[target]>source_side.max()))
                state=FreeSurfaceMarchingState(y_m=y[old],
                    potential_m2_s=d['free_phi_after'][old],elevation_m=d['free_eta_after'][old],
                    time_s=0.,half_step_time_s=0.,
                    validity=ValidityReport(status='saved_state_geometry_audit',reference_cases=(),notes=()))
                result=resample_free_surface_state(state,y[target])
                replay_errors=[]
                for rebuilt,key in ((result.potential_m2_s,'free_phi_before'),(result.elevation_m,'free_eta_before')):
                    expected=d[key][target]
                    replay_errors.append(float(np.linalg.norm(rebuilt-expected)/max(np.linalg.norm(expected),1e-30)))
                if not np.isfinite(replay_errors).all() or max(replay_errors)>1e-10:
                    raise ValueError('Legacy remap did not reconstruct next saved free-surface state')
                exposed_masks.append(newly_exposed)
                legacy_phi.append(result.potential_m2_s)
                legacy_eta.append(result.elevation_m)
                rows.append(dict(frequency=w,source_x_m=x[old],target_x_m=x[target],
                    newly_exposed_count=int(newly_exposed.sum()),
                    old_free_edge_band_count=int((outside_midpoints&~newly_exposed).sum()),
                    target_count=len(y[target]),
                    max_state_replay_error=max(replay_errors),
                    max_newly_exposed_phi=float(max(abs(result.potential_m2_s[newly_exposed]),default=0.)),
                    max_newly_exposed_eta=float(max(abs(result.elevation_m[newly_exposed]),default=0.))))
            np.savez_compressed(out/f'legacy_transfer_{w}.npz',target_x=x[-2::-1],
                target_y=y[-2::-1],newly_exposed=np.asarray(exposed_masks),
                legacy_phi=np.asarray(legacy_phi),legacy_eta=np.asarray(legacy_eta))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'station_transfer.csv',index=False)
    counts=[]
    for frequency,group in frame.groupby('frequency'):
        counts.append(dict(frequency=int(frequency),transfers=len(group),
            transfers_with_new_exposure=int((group.newly_exposed_count>0).sum()),
            exposed_point_visits=int(group.newly_exposed_count.sum()),
            total_point_visits=int(group.target_count.sum()),
            max_new_points_per_transfer=int(group.newly_exposed_count.max()),
            transfers_with_edge_extrapolation=int((group.old_free_edge_band_count>0).sum())))
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        rows=counts,max_state_replay_error=float(frame.max_state_replay_error.max()),
        production_changed=False,new_contact_state_model_implemented=False),indent=2))
    print(json.dumps(counts,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    run(args.run,args.out)
