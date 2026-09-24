"""Fixed-section smooth prescribed velocity: implicit history-coupled time convergence."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.audit_kang_local_marching_spectrum import local_operator
from planing_seakeeping.kernels.linear_2p5d import formulation as f
from planing_seakeeping.kernels.linear_2p5d.implicit_free_surface import ImplicitFreeSurfaceStep


def ramp(t, duration):
    if not np.isfinite(duration) or duration <= 0 or not np.isfinite(t).all():
        raise ValueError('Finite time and positive ramp duration required')
    u=np.clip(np.asarray(t)/duration,0.,1.)
    return u**3*(10-15*u+6*u*u)


def run(out):
    root=Path(__file__).resolve().parents[1]
    sources=[Path(__file__),Path(__file__).with_name('audit_kang_local_marching_spectrum.py'),
        *sorted((root/'planing_seakeeping/kernels/linear_2p5d').glob('*.py'))]
    out.mkdir(parents=True,exist_ok=False)
    base_dt=3*(1-2e-6)/80/(.2*np.sqrt(9.80665*3))
    omega=3*np.sqrt(9.80665/3)
    duration=64*base_dt
    ramp_duration=duration/4
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,
        scope='Fixed midship section prescribed normal velocity, not whole-ship diffraction',
        stations_for_dt=[81,161,321],radius_beams=3,free_panels=128,control_panels=192,
        omega_rad_s=omega,velocity_amplitude_m_s=.001,ramp_duration_s=ramp_duration,
        duration_s=duration,history_duration_s=128*base_dt,
        reference='Finer time grid only; no experimental reference',relative_screening_limit=.05,
        force='-rho time derivative of integrated body potential times raw A1 heave measure; fixed-section N/m',
        comparison='Common times after ramp, excluding endpoints; complex L2 and maximum differences',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2))
    data,system,rhs_map,_=local_operator(3.,128,192,return_system=True)
    body_profile=.001*data.body.normal_z
    forced=f.assemble_matched_section_system(replace(data,body_normal_velocity=body_profile))
    body_rhs=forced.rhs
    runs={}
    for stations in (81,161,321):
        refinement=(stations-1)//80
        dt=base_dt/refinement
        steps,memory=64*refinement,128*refinement
        history=f.build_transient_free_surface_history(data.control,dt,memory,quadrature_count=64,k_max=25.)
        coupling=ImplicitFreeSurfaceStep(system.matrix,rhs_map,64,dt)
        phi,eta,q=[np.zeros(128,complex) for _ in range(3)]
        pp,pn=[np.zeros((memory,192),complex) for _ in range(2)]
        times=np.arange(steps+1)*dt
        integrated=[0j]
        max_error=0.
        for index,t in enumerate(times[1:]):
            amplitude=ramp(t,ramp_duration)*np.exp(1j*omega*t)
            h=body_rhs*amplitude
            h[-192:]+=history.convolution_rhs(pp,pn)
            state=coupling.advance(phi,eta,q,h)
            phi,eta,q=state['phi'],state['eta'],state['q']
            values=state['values']
            if index in (0,1,steps-1):
                check=f.assemble_matched_section_system(replace(data,history=history,
                    free_surface_potential=phi,body_normal_velocity=body_profile*amplitude,
                    past_control_potential=pp,past_control_normal_derivative=pn))
                err=np.linalg.norm(check.matrix@values-check.rhs)/max(np.linalg.norm(check.rhs),1e-30)
                max_error=max(max_error,float(err))
            solved=f.split_matched_section_solution(data,values)
            pp,pn=f._prepend_control_history(pp,pn,solved)
            integrated.append(np.sum(solved.body_potential*(-data.body.normal_z*data.body.length_m)))
        integral=np.asarray(integrated)
        force=-1000*np.gradient(integral,dt,edge_order=2)
        if not np.isfinite(force).all() or not np.isfinite(max_error) or max_error>1e-10:
            raise ValueError('Nonfinite load or failed actual equation replay')
        runs[stations]=(times,integral,force)
        np.savez_compressed(out/f'states_{stations}.npz',time_s=times,integrated_potential=integral,
            force_per_length=force,final_free_phi=phi,final_free_eta=eta,dt_s=dt)
        pd.DataFrame(dict(time_s=times,force_real=force.real,force_imag=force.imag)).to_csv(out/f'force_{stations}.csv',index=False)
        print(dict(stations=stations,max_force=float(max(abs(force))),equation_error=max_error),flush=True)
    rows=[]
    for coarse,fine in ((81,161),(161,321)):
        t,ic,fc=runs[coarse]
        tf,ifine,ffine=runs[fine]
        if not np.allclose(t,tf[::2],atol=1e-13,rtol=0):
            raise ValueError('Time grids do not nest')
        mask=(t>=ramp_duration)&(t<t[-1])
        for field,a,b in (('integrated_potential',ic,ifine[::2]),('force_per_length',fc,ffine[::2])):
            scale=np.linalg.norm(b[mask])
            if scale<1e-12:
                raise ValueError('Near-zero scale requires an independently frozen absolute tolerance')
            error=np.linalg.norm(a[mask]-b[mask])/scale
            rows.append(dict(coarse=coarse,fine=fine,field=field,relative_complex_l2=float(error),
                max_abs_difference=float(max(abs(a[mask]-b[mask]))),within_screening=bool(error<=.05)))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'convergence.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        diagnostic_screening_pass=bool(frame.within_screening.all()),production_changed=False,
        limitations=['One fixed section and prescribed frequency','Transient, not steady RAO',
                    'Time-grid comparison, not physical validation','Moving geometry not implemented']),indent=2))
    print(frame.to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
