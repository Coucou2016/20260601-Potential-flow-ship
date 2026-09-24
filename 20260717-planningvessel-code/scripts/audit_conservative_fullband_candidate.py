"""Response-blind all-case conservative pressure candidate; not a production backend."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.schema import Linear2p5DProviderConfig
from planing_seakeeping.planing_frequency_correction import build_planing_wetted_station_hull, matched_bie_matrix_to_bow_up
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    solve_station_hull_heave_pitch_matched_sweep,
    solve_station_hull_head_sea_excitation_matched_sweep,
    heave_radiation_normal_velocity,
    _force_density_matrix_from_section_results,
)
from scripts.audit_conservative_pressure_replay import recover_v_sweep


def paired_responses(rigid, restoring, old_radiation, new_radiation, old_force, new_force, omega):
    old_d = restoring-omega**2*rigid-old_radiation
    new_d = restoring-omega**2*rigid-new_radiation
    baseline = np.linalg.solve(old_d,old_force)
    return dict(baseline=baseline, radiation_only=np.linalg.solve(new_d,old_force),
        excitation_only=np.linalg.solve(old_d,new_force), combined=np.linalg.solve(new_d,new_force),
        radiation_increment=np.linalg.solve(new_d,(new_radiation-old_radiation)@baseline),
        excitation_increment=np.linalg.solve(new_d,new_force-old_force))


def integrate_candidate(sweep, phi, qn, material, boat, speed, omega):
    x = sweep.x_m
    y, z = (np.asarray([getattr(b, attr) for b in sweep.bodies])
            for attr in ('mid_y_m', 'mid_z_down_m'))
    j3 = np.asarray([-b.normal_z*b.length_m for b in sweep.bodies])
    pressure = recover_v_sweep(x,y,z,phi,qn,material,j3,
                               rho=boat.rho_water_kg_m3,speed=speed,omega=omega)
    measure = np.stack((j3,j3*(boat.lcg_m-x[:,None])),axis=2)
    density = np.sum(pressure[:,:,None]*measure,axis=1)
    force = clipped_piecewise_linear_integral(x,density,.5*boat.beam_m)
    return force, density


def run(config,out):
    raw,boat = load_linear_case(config)
    if len(raw['cases']) != 3 or any(len(c['encounter_omega_rad_s']) != 8 for c in raw['cases']):
        raise ValueError('Expected the frozen three-speed, eight-frequency cases')
    if boat.gravity_m_s2 != 9.80665:
        raise ValueError('Current radiation sweep uses gravity 9.80665')
    out.mkdir(parents=True,exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__),config,root/'scripts/audit_conservative_pressure_replay.py',
               *sorted((root/'planing_seakeeping').rglob('*.py'))]
    (out/'contract.json').write_text(json.dumps(dict(
        expected_cases=24,stations=29,body=36,free=36,control=48,history_steps=64,
        history_quadrature=48,history_k_max=25.,grading=1.5,cutoff_beams=.5,
        route='reconstructed_symmetric_with_conservative_eulerian_pressure',
        restoring='Unchanged Savitsky derivative; known long-wave background inconsistency remains',
        scope='Diagnostic coarse full-band candidate; NOT grid-independent or physically validated',
        paired_routes=['baseline','radiation_only','excitation_only','combined'],
        input_cases=raw['cases'],hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2))
    provider = Linear2p5DProviderConfig(formulation='matched_bie',hull_stations=29,
        body_panels_per_section=36,free_surface_inner_panels=36,free_surface_outer_panels=48,
        control_surface_radius_beams=3.,include_steady_perturbation=False,include_end_terms=True)
    options = dict(parametric_section_shape='hard_chine_v',history_steps=64,
                   history_quadrature_count=48,history_k_max=25.,waterline_grading_exponent=1.5)
    records,paired_records = [],[]
    with panel_integration_route('reconstructed_symmetric'):
        for case in raw['cases']:
            speed = case['speed_mps']
            eq = make_prescribed_equilibrium(boat,speed,PrescribedRunningStateConfig(
                enabled=True,trim_deg=case['trim_deg'],lambda_w=case['lambda_w']))
            hull = build_planing_wetted_station_hull(boat,eq,station_count=29)
            restoring = compute_hydro_matrices(boat,eq).restoring
            rigid = np.diag([boat.mass_kg,boat.mass_kg*boat.pitch_radius_gyration_m**2])
            for index,omega in enumerate(case['encounter_omega_rad_s']):
                sweep = solve_station_hull_heave_pitch_matched_sweep(hull,omega,speed,
                    config=provider,rho_water_kg_m3=boat.rho_water_kg_m3,**options)
                phase = np.exp(-1j*omega*sweep.local_time_s_by_station)[:,None]
                forces, densities = [], []
                for mode,solutions,gradient in (
                    (3,sweep.heave_mode_solutions,sweep.pressure_force_sweep.heave_potential_gradient),
                    (5,sweep.pitch_mode_solutions,sweep.pressure_force_sweep.pitch_potential_gradient)):
                    phi = np.asarray([s.body_potential for s in solutions])*phase
                    qn = (np.asarray([heave_radiation_normal_velocity(b,omega) for b in sweep.bodies])
                          if mode == 3 else (sweep.pitch_body_condition_oscillation_by_station+
                                             sweep.pitch_body_condition_forward_speed_by_station)*phase)
                    force,density = integrate_candidate(sweep,phi,qn,gradient.body_potential_x_gradient,boat,speed,omega)
                    forces.append(force)
                    densities.append(density)
                radiation = matched_bie_matrix_to_bow_up(np.column_stack(forces))
                ps = sweep.pressure_force_sweep
                old_density = _force_density_matrix_from_section_results(
                    ps.heave_mode_forces,ps.pitch_mode_forces,
                    heave_attr='heave_force_time_derivative_per_m',pitch_attr='pitch_moment_time_derivative_per_m')
                old_density += ps.stokes_body_forward_speed.force_density_by_station
                if not sweep.end_station_x_m < .5*boat.beam_m:
                    raise ValueError('Baseline requires physical aft contour behind the cut')
                old_radiation = matched_bie_matrix_to_bow_up(clipped_piecewise_linear_integral(
                    sweep.x_m,old_density,.5*boat.beam_m))
                added,damping = radiation.real/omega**2,-radiation.imag/omega
                excitation = solve_station_hull_head_sea_excitation_matched_sweep(hull,omega,speed,
                    config=provider,rho_water_kg_m3=boat.rho_water_kg_m3,gravity_m_s2=boat.gravity_m_s2,
                    parametric_section_shape='hard_chine_v',matched_sweep_options={
                        k:v for k,v in options.items() if k != 'parametric_section_shape'})
                ds = excitation.diffraction_sweep
                phi = np.asarray([s.body_potential for s in ds.heave_mode_solutions])*np.exp(-1j*omega*ds.local_time_s_by_station)[:,None]
                diff,diff_density = integrate_candidate(ds,phi,excitation.diffraction_body_normal_velocity_by_station,
                    ds.pressure_force_sweep.heave_potential_gradient.body_potential_x_gradient,boat,speed,omega)
                incident = clipped_piecewise_linear_integral(ds.x_m,excitation.froude_krylov_force_density_by_station,.5*boat.beam_m)
                adapter = np.array([1j,-1j])
                total = (incident+diff)*adapter
                old_force = clipped_piecewise_linear_integral(ds.x_m,
                    excitation.total_force_density_by_station,.5*boat.beam_m)*adapter
                paired = paired_responses(rigid,restoring,old_radiation,radiation,old_force,total,omega)
                dynamic = restoring-omega**2*rigid-radiation
                response = np.linalg.solve(dynamic,total)
                np.savez_compressed(out/f"{case['id']}_frequency{index}.npz",omega=omega,
                    x=sweep.x_m,radiation_density_raw=np.stack(densities,axis=2),
                    diffraction_density_raw=diff_density,incident_density_raw=excitation.froude_krylov_force_density_by_station,
                    added_mass=added,damping=damping,restoring=restoring,rigid_mass=rigid,
                    excitation=total,incident=incident*adapter,diffraction=diff*adapter,response=response,
                    old_radiation=old_radiation,new_radiation=radiation,old_excitation=old_force,
                    **{'paired_'+name:value for name,value in paired.items()})
                scale = np.diag([1.,1/boat.length_m])
                for name,q in paired.items():
                    pair = dict(case=case['id'],frequency_index=index,omega=omega,
                        wavenumber=excitation.wavenumber_rad_m,variant=name,
                        old_dynamic_condition=np.linalg.cond(scale@(restoring-omega**2*rigid-old_radiation)@scale),
                        new_dynamic_condition=np.linalg.cond(scale@dynamic@scale))
                    for i,mode in enumerate((3,5)):
                        pair[f'q{mode}_real'],pair[f'q{mode}_imag'] = q[i].real,q[i].imag
                    paired_records.append(pair)
                row = dict(case=case['id'],frequency_index=index,omega=omega,wavenumber=excitation.wavenumber_rad_m)
                for i,mode in enumerate((3,5)):
                    row[f'q{mode}_real'],row[f'q{mode}_imag'] = response[i].real,response[i].imag
                    row[f'F{mode}_real'],row[f'F{mode}_imag'] = total[i].real,total[i].imag
                    for j,column in enumerate((3,5)):
                        row[f'A{mode}{column}'],row[f'B{mode}{column}'] = added[i,j],damping[i,j]
                records.append(row)
                pd.DataFrame(records).to_csv(out/'candidate.csv',index=False)
                pd.DataFrame(paired_records).to_csv(out/'paired_responses.csv',index=False)
                print(f"{case['id']} {index+1}/8 complete",flush=True)
    frame = pd.DataFrame(records)
    complete = len(frame)==24 and np.isfinite(frame.select_dtypes(include='number')).all().all()
    (out/'summary.json').write_text(json.dumps(dict(computation_complete=bool(complete),
        physical_acceptance='NOT_PASSED',response_reference_read=False,production_changed=False,
        long_wave_consistency='NOT_PASSED',stability='NOT_EVALUATED',grid_independence='NOT_EVALUATED'),indent=2))
    if not complete:
        raise RuntimeError('Incomplete or nonfinite candidate computation')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.config,a.out)
