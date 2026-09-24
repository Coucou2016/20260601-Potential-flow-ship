"""Paired actual-BEM history marches with identical collocated initial states."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.linalg import lu_factor, lu_solve
from scripts.audit_kang_local_marching_spectrum import local_operator
from planing_seakeeping.kernels.linear_2p5d import formulation as f
from planing_seakeeping.kernels.linear_2p5d.implicit_free_surface import ImplicitFreeSurfaceStep


def run(out):
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), Path(__file__).with_name('audit_kang_local_marching_spectrum.py'),
        *sorted((root/'planing_seakeeping/kernels/linear_2p5d').glob('*.py'))]
    out.mkdir(parents=True, exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,
        scope='Fixed Kang midship homogeneous perturbation, actual history, paired collocated initial state; not seakeeping accuracy',
        radius_beams=3., free_panels=128, control_panels=192, stations=[81,161,321],
        methods=['explicit_staggered','implicit_trapezoid'], seed=24,
        reference_steps=64, reference_history_steps=128,
        tolerances={'equation_replay':1e-10}, history_rule='Unchanged production trapezoid history rule',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2))
    data, system, rhs_map, _ = local_operator(3.,128,192,return_system=True)
    lu = lu_factor(system.matrix)
    rows, traces = [], []
    for stations in (81,161,321):
        refinement=(stations-1)//80
        dt=3*(1-2e-6)/(stations-1)/(.2*np.sqrt(9.80665*3))
        steps, memory=64*refinement,128*refinement
        history=f.build_transient_free_surface_history(data.control,dt,memory,quadrature_count=64,k_max=25.)
        for method in ('explicit_staggered','implicit_trapezoid'):
            rng=np.random.default_rng(24)
            phi=rng.normal(size=128)+1j*rng.normal(size=128)
            phi/=np.linalg.norm(phi)
            eta=np.zeros(128,complex)
            value=lu_solve(lu,rhs_map@phi)
            initial=f.split_matched_section_solution(data,value)
            q=initial.inner_free_surface_normal_derivative.copy()
            eta_half=eta-dt*q/2
            pp,pn=f._prepend_control_history(np.zeros((memory,192),complex),np.zeros((memory,192),complex),initial)
            coupling=ImplicitFreeSurfaceStep(system.matrix,rhs_map,64,dt)
            norms=[1.]
            max_error=0.
            for index in range(steps):
                h=np.zeros(len(system.rhs),complex)
                h[-192:]=history.convolution_rhs(pp,pn)
                if method=='implicit_trapezoid':
                    state=coupling.advance(phi,eta,q,h)
                    value,phi,eta,q=state['values'],state['phi'],state['eta'],state['q']
                else:
                    eta_half=eta_half+dt*q
                    phi=phi-9.80665*dt*eta_half
                    value=lu_solve(lu,rhs_map@phi+h)
                    q=value[64:192]
                    eta=eta_half+dt*q/2
                if index in (0,1,steps-1):
                    assembled=f.assemble_matched_section_system(replace(data,history=history,
                        free_surface_potential=phi,past_control_potential=pp,past_control_normal_derivative=pn))
                    residual=np.linalg.norm(assembled.matrix@value-assembled.rhs)/max(np.linalg.norm(assembled.rhs),1e-30)
                    max_error=max(max_error,float(residual))
                solution=f.split_matched_section_solution(data,value)
                pp,pn=f._prepend_control_history(pp,pn,solution)
                norm=float(np.linalg.norm(np.r_[phi,np.sqrt(9.80665*.3)*eta]))
                if not np.isfinite(norm):
                    raise ValueError('Nonfinite paired perturbation state')
                norms.append(norm)
            if not np.isfinite(max_error) or max_error>1e-10:
                raise ValueError('Paired method failed actual equation replay')
            np.savez_compressed(out/f'{method}_{stations}.npz',phi=phi,eta=eta,q=q,
                norm_history=norms,dt_s=dt,free_y=data.inner_free_surface.mid_y_m)
            traces.extend(dict(method=method,stations=stations,time_s=i*dt,state_norm=n) for i,n in enumerate(norms))
            rows.append(dict(method=method,stations=stations,dt_s=dt,duration_s=steps*dt,
                history_duration_s=memory*dt,max_norm=max(norms),final_norm=norms[-1],equation_error=max_error))
            print(rows[-1],flush=True)
    pd.DataFrame(rows).to_csv(out/'summary.csv',index=False)
    pd.DataFrame(traces).to_csv(out/'norm_history.csv',index=False)
    comparisons=[]
    for coarse,fine in ((81,161),(161,321)):
        with np.load(out/f'implicit_trapezoid_{coarse}.npz') as a,np.load(out/f'implicit_trapezoid_{fine}.npz') as b:
            for field in ('phi','eta'):
                comparisons.append(dict(coarse=coarse,fine=fine,field=field,
                    relative_final_state_difference=float(np.linalg.norm(a[field]-b[field])/np.linalg.norm(b[field]))))
    pd.DataFrame(comparisons).to_csv(out/'implicit_state_changes.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,production_changed=False,
        physical_reference_read=False,full_ship_verified=False,final_state_changes=comparisons),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
