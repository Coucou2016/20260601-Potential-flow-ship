"""Extrapolated contact traces from saved midpoint fields; not exact endpoint data."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.kang_reference_geometry import build_hull


def endpoint_trace(distances,values):
    distances=np.asarray(distances,float); values=np.asarray(values,complex)
    if (distances.ndim!=1 or values.shape!=distances.shape or len(distances)<2
            or not np.isfinite(distances).all() or not np.isfinite(values).all()
            or min(distances)<=0):
        raise ValueError('Finite positive endpoint distances and matching traces required')
    first,second=np.argsort(distances)[:2]
    a,b=distances[first],distances[second]
    if b-a<=64*np.finfo(float).eps*max(1.,b):
        raise ValueError('Distinct endpoint distances required')
    return (b*values[first]-a*values[second])/(b-a)


def run(directory,out):
    contract=json.loads((directory/'contract.json').read_text())
    if contract['exposure_policy']!='bounded_nearest_unvalidated' or contract['history_policy']!='full':
        raise ValueError('Complete-history bounded candidate required')
    out.mkdir(parents=True,exist_ok=False)
    hull=build_hull(contract['stations'],161,moment_reference_x=1.5)
    omega=contract['omega_e_sqrt_L_g']*np.sqrt(9.80665/3)
    speed=contract['speed_m_s']; omega0=2*omega/(1+np.sqrt(1+4*speed*omega/9.80665))
    scale=9.80665/omega0
    rows=[]
    with np.load(directory/'fields.npz') as fields:
        for order,index in enumerate(range(len(hull.stations)-1,-1,-1)):
            station=hull.stations[index]; half=station.waterplane_beam_m()/2
            np.testing.assert_allclose(station.x_m,fields['x_m'][index],rtol=0,atol=1e-12)
            start,end=fields['free_offsets'][order:order+2]
            free=fields['free_fields'][start:end]
            y=fields['y'][index]; z=fields['z_down'][index]
            for sign in (-1,1):
                body_mask=sign*y>0
                free_mask=sign*free[:,0].real>0
                body_distance=np.hypot(y[body_mask]-sign*half,z[body_mask])
                free_distance=abs(free[free_mask,0].real)-half
                body_trace=endpoint_trace(body_distance,fields['psi'][index,body_mask])
                free_trace=endpoint_trace(free_distance,free[free_mask,1])
                gap=body_trace-free_trace
                rows.append(dict(x_m=station.x_m,side=sign,
                    body_trace_real=body_trace.real,body_trace_imag=body_trace.imag,
                    free_trace_real=free_trace.real,free_trace_imag=free_trace.imag,
                    gap_over_incident_potential=abs(gap)/scale,
                    nearest_body_distance_m=min(body_distance),nearest_free_distance_m=min(free_distance)))
    frame=pd.DataFrame(rows); frame.to_csv(out/'traces.csv',index=False)
    summary=dict(stage_acceptance=False,exact_contact_values_available=False,
        max_gap_over_incident_potential=float(frame.gap_over_incident_potential.max()),
        median_gap_over_incident_potential=float(frame.gap_over_incident_potential.median()),
        limitations=['Two-point extrapolation from constant-panel midpoint potentials',
            'Body distances are chord distances, not exact curved arclength',
            'Not a physical acceptance threshold or residual of collocation equations'],
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),directory/'contract.json',directory/'fields.npz')})
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); run(args.run,args.out)
