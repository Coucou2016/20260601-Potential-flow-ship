"""Summarize a non-invasive auxiliary BVP diagnostic, not physical validation."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def summarize(run, baseline):
    with np.load(run/'fields.npz') as actual, np.load(baseline/'fields.npz') as old:
        identical=(set(actual.files)==set(old.files) and
                   all(np.array_equal(actual[k],old[k]) for k in old.files))
    if not identical:
        raise ValueError('Diagnostic changed baseline fields')
    frame=pd.read_csv(run/'old_velocity_diagnostic.csv')
    q=frame.transferred_real.to_numpy()+1j*frame.transferred_imag.to_numpy()
    refreshed=frame.refreshed_real.to_numpy()+1j*frame.refreshed_imag.to_numpy()
    delta=refreshed-q
    masks={'fore':frame.x_m>=1.5,'aft':frame.x_m<1.5,
           'exposed':frame.newly_exposed,'supported':~frame.newly_exposed}
    rows=[]
    for name,mask in masks.items():
        rows.append(dict(region=name,point_visits=int(mask.sum()),
            relative_l2_gap=float(np.linalg.norm(delta[mask])/max(np.linalg.norm(refreshed[mask]),1e-30)),
            squared_gap_fraction=float(np.linalg.norm(delta[mask])**2/max(np.linalg.norm(delta)**2,1e-30))))
    result=dict(stage_acceptance=False,baseline_arrays_identical=identical,
        auxiliary_equation_residual_max=float(frame.equation_residual.max()),groups=rows,
        interpretation='Frozen-new-geometry old-time BVP discrepancy; not an error against physical truth. Groups overlap.')
    (run/'velocity_audit_summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    args=parser.parse_args()
    summarize(args.run,args.baseline)
