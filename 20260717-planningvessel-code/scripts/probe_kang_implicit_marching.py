"""Actual variable-section matched BEM candidate; explicitly unvalidated exposure closure."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.kang_reference_geometry import build_hull
from planing_seakeeping.kernels.linear_2p5d import formulation as f
from planing_seakeeping.kernels.linear_2p5d.anchored_free_surface import build_anchored_free_surface
from planing_seakeeping.kernels.linear_2p5d.free_surface_transfer import transfer_fields,limited_linear_exposure,bounded_trace_transfer,exposure_linear_bounded_edge_transfer
from planing_seakeeping.kernels.linear_2p5d.implicit_free_surface import ImplicitFreeSurfaceStep
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import current_panel_integration_route,panel_integration_route


def old_time_boundary_data(data,phi,omega0,dt):
    """Freeze new geometry at the previous time; remove the newest history entry."""
    def older(values):
        return np.concatenate((values[1:],np.zeros_like(values[:1])),axis=0)
    return replace(data,free_surface_potential=np.array(phi,copy=True),
        body_normal_velocity=data.body_normal_velocity*np.exp(-1j*omega0*dt),
        past_control_potential=older(data.past_control_potential),
        past_control_normal_derivative=older(data.past_control_normal_derivative))


def run(out,stations,exposed_policy,audit_old_velocity=False,old_velocity_policy='transferred',history_policy='full',frequency=3.,transverse_refinement=1,body_panel_count=64,control_panel_count=96,radius_beams=3.,history_quadrature_count=64,history_k_max=25.):
    if stations not in (81,161,321,641) or exposed_policy not in ('limited_linear_unvalidated','bounded_nearest_unvalidated','linear_exposure_bounded_edges_unvalidated'):
        raise ValueError('Frozen station level and explicit unvalidated exposure policy required')
    if old_velocity_policy not in ('transferred','refreshed_frozen_geometry_unvalidated'):
        raise ValueError('Explicit supported old-velocity policy required')
    if history_policy not in ('full','zero_feedback_diagnostic'):
        raise ValueError('Explicit supported history policy required')
    if frequency not in (2.,3.,4.):
        raise ValueError('Frozen diagnostic frequency must be 2, 3, or 4')
    if type(transverse_refinement) is not int or transverse_refinement not in (1,2):
        raise ValueError('Frozen transverse refinement must be 1 or 2')
    if (type(body_panel_count) is not int or body_panel_count not in (64,128)
            or type(control_panel_count) is not int or control_panel_count not in (96,128,192)):
        raise ValueError('Frozen body/control panel counts required')
    if isinstance(radius_beams,bool) or radius_beams not in (3.,4.):
        raise ValueError('Frozen control radius must be 3 or 4 beams')
    if type(history_quadrature_count) is not int or history_quadrature_count not in (64,128,256,512):
        raise ValueError('Frozen history quadrature count required')
    if isinstance(history_k_max,bool) or history_k_max not in (25.,50.,100.):
        raise ValueError('Frozen history cutoff required')
    radius=.3*radius_beams
    outer_count=int(np.ceil(44*(radius-.15)/.75-1e-12))*transverse_refinement
    nb,nc=body_panel_count,control_panel_count
    root=Path(__file__).resolve().parents[1]
    sources=[Path(__file__),root/'scripts/kang_reference_geometry.py',
        *sorted((root/'planing_seakeeping/kernels/linear_2p5d').glob('*.py'))]
    out.mkdir(parents=True,exist_ok=False)
    speed=.2*np.sqrt(9.80665*3); omega=frequency*np.sqrt(9.80665/3)
    omega0=2*omega/(1+np.sqrt(1+4*speed*omega/9.80665)); k=omega0**2/9.80665
    hull=build_hull(stations,161,moment_reference_x=1.5)
    x=np.array([s.x_m for s in hull.stations]); dt=(x[1]-x[0])/speed
    memory=128*((stations-1)//80)
    contract=dict(stage_acceptance=False,route='experimental_implicit_anchored_matched_diffraction',
        stations=stations,omega_e_sqrt_L_g=frequency,speed_m_s=speed,dt_s=dt,history_steps=memory,
        history_quadrature_count=history_quadrature_count,history_k_max=history_k_max,
        radius_beams=radius_beams,body_panels=nb,control_panels=nc,inner_nodes_per_side=20*transverse_refinement,outer_panels_per_side=outer_count,
        exposure_policy=exposed_policy,maximum_spacing_ratio=1.,
        body_neumann_convention='fluid_domain_outward_diffraction_minus_incident',
        old_free_edge_policy='linear_extrapolation' if exposed_policy=='limited_linear_unvalidated' else 'nearest',
        audit_old_velocity=audit_old_velocity,
        old_velocity_policy=old_velocity_policy,
        history_policy=history_policy,physical_history_retained=history_policy=='full',
        panel_integration=current_panel_integration_route(),
        pressure_route='Legacy phase derivative at material-indexed panels, no curve-chain correction',
        limitations=['Exposure continuation unvalidated','Single frequency','No experiment read',
                    'Finite tip exclusion','Raw geometric-midship moment, not experimental CG'],
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'contract.json').write_text(json.dumps(contract,indent=2))
    control=f.build_control_surface_geometry(radius_m=radius,panel_count=nc)
    history=f.build_transient_free_surface_history(control,dt,memory,quadrature_count=history_quadrature_count,k_max=history_k_max)
    pp,pn=[np.zeros((memory,nc),complex) for _ in range(2)]
    previous=None; previous_half=None; state=None
    bodies=[]; psi=[]; rows=[]; free_fields=[]; free_offsets=[0]; velocity_audit=[]
    for index in range(stations-1,-1,-1):
        station=hull.stations[index]
        half=station.waterplane_beam_m()/2
        body=f.build_inner_domain_panel_geometry(station.section_offsets(),body_panel_count=nb)
        free=build_anchored_free_surface(radius,.15,half,20*transverse_refinement,outer_count)
        nf=free.panel_count
        local_time=(x[-1]-x[index])/speed
        incident_phi=1j*9.80665/omega0*np.exp(-k*body.mid_z_down_m)*np.exp(1j*k*(x[index]-1.5))
        q_body=-k*incident_phi*body.normal_z*np.exp(1j*omega*local_time)
        supplied_pp,supplied_pn=(pp,pn) if history_policy=='full' else (np.zeros_like(pp),np.zeros_like(pn))
        data=f.MatchedSectionBoundaryData(body=body,inner_free_surface=free,control=control,
            history=history,body_normal_velocity=q_body,free_surface_potential=np.zeros(nf,complex),
            past_control_potential=supplied_pp,past_control_normal_derivative=supplied_pn)
        system=f.assemble_matched_section_system(data)
        rhs_map=np.vstack([-f._inner_a_matrix(geometry,free,same_boundary=(j==1),diagonal_sign=-1.)
            for j,geometry in enumerate((body,free,control))]+[np.zeros((nc,nf))])
        exposure_count=0; exposure_ratio=0.; edge_count=0
        if previous is None:
            values=np.linalg.solve(system.matrix,system.rhs)
            phi,eta=np.zeros(nf,complex),np.zeros(nf,complex)
            q=values[nb:nb+nf]
        else:
            kwargs={}
            if np.any(abs(free.mid_y_m)<previous_half):
                try:
                    fill,exposure_ratio=limited_linear_exposure(previous.mid_y_m,free.mid_y_m,state,
                        previous_half,maximum_spacing_ratio=1.)
                except ValueError as error:
                    pd.DataFrame(rows).to_csv(out/'partial_stations.csv',index=False)
                    (out/'failure.json').write_text(json.dumps(dict(stage_acceptance=False,
                        status='EXPOSURE_POLICY_REJECTED',station_index=index,x_m=x[index],
                        completed_stations=len(rows),reason=str(error)),indent=2))
                    raise
                kwargs=dict(exposed_values=fill,exposed_source=exposed_policy)
            migrated=transfer_fields(previous.mid_y_m,free.mid_y_m,state,
                previous_half_beam=previous_half,control_radius=radius,**kwargs)
            if exposed_policy=='bounded_nearest_unvalidated':
                migrated=bounded_trace_transfer(previous.mid_y_m,free.mid_y_m,state,
                    previous_half_beam=previous_half,control_radius=radius,maximum_spacing_ratio=1.)
            elif exposed_policy=='linear_exposure_bounded_edges_unvalidated':
                migrated=exposure_linear_bounded_edge_transfer(previous.mid_y_m,free.mid_y_m,state,
                    previous_half_beam=previous_half,control_radius=radius,maximum_spacing_ratio=1.)
            exposure_count=int(migrated.newly_exposed.sum()); edge_count=int(migrated.edge_extrapolated.sum())
            if audit_old_velocity or old_velocity_policy=='refreshed_frozen_geometry_unvalidated':
                old_data=old_time_boundary_data(data,migrated.values[:,0],omega0,dt)
                old_system=f.assemble_matched_section_system(old_data)
                old_values=np.linalg.solve(old_system.matrix,old_system.rhs)
                old_residual=np.linalg.norm(old_system.matrix@old_values-old_system.rhs)/max(np.linalg.norm(old_system.rhs),1e-30)
                if not np.isfinite(old_residual) or old_residual>1e-10:
                    raise ValueError('Auxiliary old-time BVP failed reconstruction')
                refreshed=old_values[nb:nb+nf]
                for j,y in enumerate(free.mid_y_m):
                    velocity_audit.append(dict(x_m=x[index],y_m=y,
                        newly_exposed=bool(migrated.newly_exposed[j]),
                        edge_extrapolated=bool(migrated.edge_extrapolated[j]),
                        transferred_real=migrated.values[j,2].real,transferred_imag=migrated.values[j,2].imag,
                        refreshed_real=refreshed[j].real,refreshed_imag=refreshed[j].imag,
                        equation_residual=old_residual))
            coupling=ImplicitFreeSurfaceStep(system.matrix,rhs_map,nb,dt)
            old_q=(refreshed if old_velocity_policy=='refreshed_frozen_geometry_unvalidated'
                   else migrated.values[:,2])
            result=coupling.advance(migrated.values[:,0],migrated.values[:,1],old_q,system.rhs)
            values,phi,eta,q=result['values'],result['phi'],result['eta'],result['q']
        actual=f.assemble_matched_section_system(replace(data,free_surface_potential=phi))
        residual=np.linalg.norm(actual.matrix@values-actual.rhs)/max(np.linalg.norm(actual.rhs),1e-30)
        if not np.isfinite(residual) or residual>1e-10:
            raise ValueError('Actual new-station equations failed reconstruction')
        solved=f.split_matched_section_solution(data,values)
        pp,pn=f._prepend_control_history(pp,pn,solved)
        bodies.append(body); psi.append(solved.body_potential)
        rows.append(dict(x_m=x[index],local_time_s=local_time,free_panels=nf,
            newly_exposed=exposure_count,edge_extrapolated=edge_count,exposure_ratio=exposure_ratio,
            equation_residual=float(residual),history_norm=float(np.linalg.norm(pp)),
            free_phi_norm=float(np.linalg.norm(phi)),free_eta_norm=float(np.linalg.norm(eta))))
        state=np.c_[phi,eta,q]; previous=free; previous_half=half
        free_fields.append(np.c_[free.mid_y_m,phi,eta,q]); free_offsets.append(free_offsets[-1]+nf)
    # Keep original pressure convention so integrator/grid changes are not mixed
    # with the independent curved-trace pressure candidate.
    bodies=bodies[::-1]; psi=np.asarray(psi[::-1]); times=(x[-1]-x)/speed
    phase=np.exp(1j*omega*times); phi=psi/phase[:,None]
    gradient=f.estimate_local_time_phase_body_potential_x_gradient(x,psi,
        omega_rad_s=omega,speed_mps=speed,phase_factor=phase).body_potential_x_gradient
    pressure=-1000j*omega*phi+1000*speed*gradient
    measure=np.asarray([-b.normal_z*b.length_m for b in bodies])
    heave=np.sum(pressure*measure,axis=1)
    diffraction_density=np.c_[heave,heave*(1.5-x)]
    incident_pressure=np.asarray([1000*9.80665*np.exp(-k*b.mid_z_down_m)*np.exp(1j*k*(xx-1.5))
        for xx,b in zip(x,bodies,strict=True)])
    fk=np.sum(incident_pressure*measure,axis=1)
    incident_density=np.c_[fk,fk*(1.5-x)]
    diffraction=np.trapezoid(diffraction_density,x,axis=0)
    incident=np.trapezoid(incident_density,x,axis=0)
    if not np.isfinite(diffraction).all():
        raise ValueError('Nonfinite integrated excitation')
    np.savez_compressed(out/'fields.npz',x_m=x,psi=psi,phi=phi,pressure=pressure,
        y=np.asarray([b.mid_y_m for b in bodies]),z_down=np.asarray([b.mid_z_down_m for b in bodies]),
        normal_y=np.asarray([b.normal_y for b in bodies]),normal_z=np.asarray([b.normal_z for b in bodies]),
        length=np.asarray([b.length_m for b in bodies]),pressure_gradient=gradient,
        incident_density=incident_density,diffraction_density=diffraction_density,
        incident=incident,diffraction=diffraction,total=incident+diffraction,
        free_station_x=x[::-1],free_offsets=free_offsets,free_fields=np.concatenate(free_fields))
    frame=pd.DataFrame(rows); frame.to_csv(out/'stations.csv',index=False)
    if velocity_audit:
        pd.DataFrame(velocity_audit).to_csv(out/'old_velocity_diagnostic.csv',index=False)
    summary=dict(stage_acceptance=False,stations_completed=len(rows),
        total_heave_amplitude=float(abs((incident+diffraction)[0])/(1000*9.80665*(29144/51975*3*.3*.1875)/3)),
        max_equation_residual=float(frame.equation_residual.max()),
        exposure_visits=int(frame.newly_exposed.sum()),max_exposure_ratio=float(frame.exposure_ratio.max()),
        physical_exposure_model_validated=False,production_changed=False,
        history_policy=history_policy,physical_history_retained=history_policy=='full')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--stations',type=int,choices=(81,161,321,641),required=True)
    p.add_argument('--exposed-policy',choices=('limited_linear_unvalidated','bounded_nearest_unvalidated','linear_exposure_bounded_edges_unvalidated'),required=True)
    p.add_argument('--audit-old-velocity',action='store_true')
    p.add_argument('--old-velocity-policy',choices=('transferred','refreshed_frozen_geometry_unvalidated'),default='transferred')
    p.add_argument('--history-policy',choices=('full','zero_feedback_diagnostic'),default='full')
    p.add_argument('--frequency',type=float,choices=(2.,3.,4.),default=3.)
    p.add_argument('--transverse-refinement',type=int,choices=(1,2),default=1)
    p.add_argument('--panel-integration',choices=('midpoint','analytic_straight_midpoint_curved'),default='midpoint')
    p.add_argument('--body-panels',type=int,choices=(64,128),default=64)
    p.add_argument('--control-panels',type=int,choices=(96,128,192),default=96)
    p.add_argument('--radius-beams',type=float,choices=(3.,4.),default=3.)
    p.add_argument('--history-quadrature-count',type=int,choices=(64,128,256,512),default=64)
    p.add_argument('--history-k-max',type=float,choices=(25.,50.,100.),default=25.)
    args=p.parse_args()
    with panel_integration_route(args.panel_integration):
        run(args.out,args.stations,args.exposed_policy,args.audit_old_velocity,args.old_velocity_policy,args.history_policy,args.frequency,args.transverse_refinement,args.body_panels,args.control_panels,args.radius_beams,args.history_quadrature_count,args.history_k_max)
