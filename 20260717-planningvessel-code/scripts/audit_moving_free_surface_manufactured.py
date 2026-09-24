"""Manufactured moving cut-grid/remap/implicit integration; no ship BEM or contact model."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.kernels.linear_2p5d.anchored_free_surface import build_anchored_free_surface
from planing_seakeeping.kernels.linear_2p5d.free_surface_transfer import transfer_fields,bounded_trace_transfer,exposure_linear_bounded_edge_transfer,limited_linear_exposure
from planing_seakeeping.kernels.linear_2p5d.implicit_free_surface import ImplicitFreeSurfaceStep


def exact_fields(y,t):
    k,g=3.,9.80665
    omega=np.sqrt(g*k)
    shape=(1+.2j)*np.cos(k*np.asarray(y))
    phi=shape*np.cos(omega*t)
    eta=omega/g*shape*np.sin(omega*t)
    return np.c_[phi,eta,k*phi]


def simulate(refinement,policy='exact_exposure'):
    if not isinstance(refinement,int) or refinement<1:
        raise ValueError('Positive integer refinement required')
    if policy not in ('exact_exposure','bounded_nearest_unvalidated',
                      'exact_exposure_bounded_edges','bounded_exposure_linear_edges',
                      'linear_exposure_bounded_edges_unvalidated','linear_all_unvalidated'):
        raise ValueError('Explicit supported transfer policy required')
    duration=1.
    steps=40*refinement
    dt=duration/steps
    def half(t):
        return .097+.031*np.sin(2*np.pi*t/duration)
    def grid(t):
        return build_anchored_free_surface(.9,.15,half(t),8*refinement,16*refinement)
    previous=grid(0.)
    values=exact_fields(previous.mid_y_m,0.)
    cache={}
    rows=[]
    maximum_equation_error=0.
    for i in range(steps):
        old_t=i*dt
        new_t=(i+1)*dt
        new=grid(new_t)
        newly_exposed=abs(new.mid_y_m)<half(old_t)
        kwargs={}
        if newly_exposed.any():
            kwargs=dict(exposed_values=exact_fields(new.mid_y_m,old_t),
                exposed_source='Analytic manufactured solution at OLD time; not ship contact-line physics')
        if policy=='linear_all_unvalidated' and newly_exposed.any():
            fill,_=limited_linear_exposure(previous.mid_y_m,new.mid_y_m,values,half(old_t),
                maximum_spacing_ratio=1.)
            kwargs=dict(exposed_values=fill,exposed_source='Linear continuation; not exact contact data')
        if policy in ('exact_exposure','linear_all_unvalidated'):
            transferred=transfer_fields(previous.mid_y_m,new.mid_y_m,values,
                previous_half_beam=half(old_t),control_radius=.9,**kwargs)
        elif policy=='linear_exposure_bounded_edges_unvalidated':
            transferred=exposure_linear_bounded_edge_transfer(previous.mid_y_m,new.mid_y_m,values,
                previous_half_beam=half(old_t),control_radius=.9,maximum_spacing_ratio=1.)
        else:
            transferred=bounded_trace_transfer(previous.mid_y_m,new.mid_y_m,values,
                previous_half_beam=half(old_t),control_radius=.9,maximum_spacing_ratio=1.)
            if policy=='exact_exposure_bounded_edges':
                transferred.values[newly_exposed]=exact_fields(new.mid_y_m[newly_exposed],old_t)
            elif policy=='bounded_exposure_linear_edges':
                supplied={} if not newly_exposed.any() else dict(
                    exposed_values=transferred.values,
                    exposed_source='Nearest-state exposure with linear old-free edges; diagnostic only')
                transferred=transfer_fields(previous.mid_y_m,new.mid_y_m,values,
                    previous_half_beam=half(old_t),control_radius=.9,**supplied)
        n=new.panel_count
        if n not in cache:
            cache[n]=ImplicitFreeSurfaceStep(np.eye(n),3*np.eye(n),0,dt)
        phi,eta,q=transferred.values.T
        updated=cache[n].advance(phi,eta,q,np.zeros(n))
        values=np.c_[updated['phi'],updated['eta'],updated['q']]
        maximum_equation_error=max(maximum_equation_error,updated['residual'])
        reference=exact_fields(new.mid_y_m,new_t)
        weights=new.length_m[:,None]
        scales=np.array([abs(1+.2j),abs(1+.2j)*np.sqrt(9.80665*3)/9.80665])
        relative=float(np.sqrt(np.sum(weights*abs((values[:,:2]-reference[:,:2])/scales)**2)/
            np.sum(weights*abs(reference[:,:2]/scales)**2)))
        rows.append(dict(step=i+1,time_s=new_t,panels=n,
            newly_exposed=int(transferred.newly_exposed.sum()),
            edge_extrapolated=int(transferred.edge_extrapolated.sum()),
            relative_phi_eta_error=relative,
            maximum_scaled_point_error=float(np.max(abs((values[:,:2]-reference[:,:2])/scales)))))
        previous=new
    return dict(rows=rows,final_y=previous.mid_y_m,final_values=values,
        final_exact=exact_fields(previous.mid_y_m,duration),maximum_equation_error=maximum_equation_error)


def run(out):
    root=Path(__file__).resolve().parents[1]
    paths=[Path(__file__),*[root/'planing_seakeeping/kernels/linear_2p5d'/name for name in
        ('anchored_free_surface.py','free_surface_transfer.py','implicit_free_surface.py')]]
    out.mkdir(parents=True,exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,
        scope='Manufactured Fourier oscillator on moving sampling domain. Diagonal q=k*phi, NOT a moving-ship BEM.',
        k=3.,gravity=9.80665,duration_s=1.,waterline='.097+.031*sin(2*pi*t)',
        refinements=[1,2,4],coarsest_steps=40,coarsest_zones=[8,16],
        exposed_data='Exact OLD-time analytic state, never a production default',
        error_norm='Panel-length weighted relative L2 of [phi/abs(A), eta/(abs(A)*omega/g)], dimensionless; A=1+0.2j',
        finest_relative_error_limit=.01,algebra_limit=1e-10,
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2))
    summary=[]
    for refinement in (1,2,4):
        result=simulate(refinement)
        frame=pd.DataFrame(result['rows'])
        frame.to_csv(out/f'trace_{refinement}.csv',index=False)
        np.savez_compressed(out/f'fields_{refinement}.npz',y=result['final_y'],
            values=result['final_values'],exact=result['final_exact'])
        summary.append(dict(refinement=refinement,min_panels=int(frame.panels.min()),
            max_panels=int(frame.panels.max()),exposed_visits=int(frame.newly_exposed.sum()),
            final_error=float(frame.relative_phi_eta_error.iloc[-1]),
            maximum_error=float(frame.relative_phi_eta_error.max()),
            maximum_equation_error=result['maximum_equation_error']))
    passed=bool(summary[-1]['maximum_error']<.01 and
        all(r['maximum_equation_error']<1e-10 for r in summary) and
        all(b['final_error']<a['final_error'] for a,b in zip(summary[:-1],summary[1:])))
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        manufactured_integration_pass=passed,rows=summary,
        physical_contact_state_validated=False,moving_body_BEM_implemented=False),indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
