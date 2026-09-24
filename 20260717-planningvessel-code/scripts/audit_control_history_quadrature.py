"""Independent adaptive integral of the finite-cutoff A1 history integrand."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.integrate import quad
from planing_seakeeping.kernels.linear_2p5d import formulation as f


def run(out,cutoff=25.):
    if isinstance(cutoff,bool) or cutoff not in (25.,50.,100.):
        raise ValueError('Frozen cutoff required')
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    g=9.80665; dt=(3.-6e-6)/320/(.2*np.sqrt(g*3))
    control=f.build_control_surface_geometry(radius_m=.9,panel_count=96)
    pairs=[(0,0),(0,95),(0,48),(24,48),(48,48),(95,95)]
    lags=[1,128,512]
    paths=[Path(__file__),Path(f.__file__)]
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,
        cutoff=cutoff,counts=[64,128,256,512],pairs=pairs,lags=lags,dt_s=dt,
        scope='Finite spectral interval only; not cutoff convergence or physics validation',
        reference='scipy.integrate.quad in original k coordinate, not s=sqrt(k) trapezoid',
        epsabs=1e-10,epsrel=1e-10,
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2))
    references={}
    for i,j in pairs:
        dy=control.mid_y_m[i]-control.mid_y_m[j]
        depth=control.mid_z_down_m[i]+control.mid_z_down_m[j]
        for lag in lags:
            def base(k):
                # sin(sqrt(g*k)*t)/sqrt(k) has a finite limit at k=0.
                time=2*g*lag*dt if k==0 else 2*np.sqrt(g/k)*np.sin(np.sqrt(g*k)*lag*dt)
                return time*np.exp(-k*depth)*control.length_m[j]
            for mode in ('green','normal'):
                def fun(k):
                    spatial=(np.cos(k*dy) if mode=='green' else
                        k*(np.sin(k*dy)*control.normal_y[j]-np.cos(k*dy)*control.normal_z[j]))
                    return base(k)*spatial
                references[i,j,lag,mode]=quad(fun,0,cutoff,epsabs=1e-10,epsrel=1e-10,limit=300)
    rows=[]
    for count in (64,128,256,512):
        history=f.build_transient_free_surface_history(control,dt,512,quadrature_count=count,k_max=cutoff)
        for (i,j,lag,mode),(reference,error) in references.items():
            matrix=history.green_potential if mode=='green' else history.green_normal_derivative
            value=float(matrix[lag-1,i,j])
            rows.append(dict(count=count,field=i,source=j,lag=lag,mode=mode,
                reference=reference,quad_error_estimate=error,value=value,absolute_error=abs(value-reference)))
    frame=pd.DataFrame(rows); frame.to_csv(out/'entries.csv',index=False)
    summary=frame.groupby(['count','mode']).absolute_error.max().reset_index()
    summary.to_csv(out/'max_errors.csv',index=False); print(summary.to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cutoff',type=float,choices=(25.,50.,100.),default=25.)
    args=p.parse_args(); run(args.out,args.cutoff)
