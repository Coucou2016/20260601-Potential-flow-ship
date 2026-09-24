"""Independent total-heave-amplitude diagnostic; never a complex-diffraction gate."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.kang_reference_geometry import build_hull
from planing_seakeeping.schema import Linear2p5DProviderConfig
from planing_seakeeping.kernels.linear_2p5d.formulation import solve_station_hull_head_sea_excitation_matched_sweep


PRESETS = {
    'baseline': (41, 32, 32, 48, 64, 32, 81, 1e-6),
    'medium': (61, 48, 48, 72, 96, 48, 121, 1e-6),
    'fine': (81, 64, 64, 96, 128, 64, 161, 1e-6),
    'boundary_dense': (81, 64, 128, 192, 128, 64, 161, 1e-6),
    'boundary_dense_half_dt': (161, 64, 128, 192, 256, 64, 161, 1e-6),
    'boundary_dense_quarter_dt': (321, 64, 128, 192, 512, 64, 161, 1e-6),
    'history_only': (41, 32, 32, 48, 128, 64, 81, 1e-6),
    'endpoint_only': (41, 32, 32, 48, 64, 32, 81, 1e-4),
}


def run(out, preset='baseline', *, radius_beams=3., k_max=25., save_boundary=False):
    root = Path(__file__).resolve().parents[1]
    reference = root/'benchmarks/kang_excitation_digitization_v4_20260924/amplitudes.csv'
    if preset not in PRESETS:
        raise ValueError('Unknown diagnostic preset')
    if not np.isfinite([radius_beams, k_max]).all() or radius_beams <= 1 or k_max <= 0:
        raise ValueError('Finite radius > one beam and positive spectral cutoff required')
    stations, body, free, control, history, quadrature, points, endpoint = PRESETS[preset]
    cfg = Linear2p5DProviderConfig(enabled=True, hull_stations=stations, body_panels_per_section=body,
        free_surface_inner_panels=free, free_surface_outer_panels=control,
        control_surface_radius_beams=radius_beams, include_steady_perturbation=False)
    options = dict(history_steps=history, history_quadrature_count=quadrature, history_k_max=k_max,
        waterline_grading_exponent=1.5)
    out.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__), root/'scripts/kang_reference_geometry.py', reference,
        root/'planing_seakeeping/station_2p5d.py', root/'planing_seakeeping/section_bem.py',
        root/'planing_seakeeping/schema.py',
        *sorted((root/'planing_seakeeping/kernels/linear_2p5d').glob('*.py'))]
    contract = dict(status='DIAGNOSTIC_NOT_STAGE_ACCEPTANCE', frequencies=[2.,3.,4.],
        length=3., beam=.3, draft=.1875, froude_length=.2, rho=1000., gravity=9.80665,
        preset=preset, input_points_per_side=points, endpoint_fraction=endpoint,
        save_boundary=save_boundary,
        config=asdict(cfg), options=options, moment_origin='Geometric midship; experimental CG unverified',
        screening_rule='Relative amplitude difference <= 15%; reading bounds reported separately, not added to tolerance',
        limitations=['One grid only', 'No phase', 'Numerical reference, not experiment',
                     'Source axis calibration still pending independent review', 'Pitch not evaluated'],
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'contract.json').write_text(json.dumps(contract, indent=2))
    hull = build_hull(stations, points, moment_reference_x=1.5, endpoint_fraction=endpoint)
    speed = .2*np.sqrt(9.80665*3)
    rows=[]
    for omega_nd in contract['frequencies']:
        result = solve_station_hull_head_sea_excitation_matched_sweep(hull,
            omega_nd*np.sqrt(9.80665/3), speed, config=cfg, rho_water_kg_m3=1000.,
            gravity_m_s2=9.80665, matched_sweep_options=options)
        np.savez_compressed(out/f'fields_{omega_nd:g}.npz', x_m=result.x_m,
            incident=result.froude_krylov_force, diffraction=result.diffraction_force,
            total=result.total_excitation, incident_density=result.froude_krylov_force_density_by_station,
            diffraction_density=result.diffraction_force_density_by_station)
        if save_boundary:
            sweep = result.diffraction_sweep
            pressures = sweep.pressure_force_sweep.heave_mode_pressures
            np.savez_compressed(out/f'boundary_{omega_nd:g}.npz', x_m=sweep.x_m,
                local_time_s=sweep.local_time_s_by_station,
                solved_body_potential=np.asarray([s.body_potential for s in sweep.heave_mode_solutions]),
                pressure_body_potential=np.asarray([p.body_potential for p in pressures]),
                pressure_body_x_gradient=np.asarray([p.body_potential_x_gradient for p in pressures]),
                pressure=np.asarray([p.pressure_pa for p in pressures]),
                y=np.asarray([b.mid_y_m for b in sweep.bodies]),
                z_down=np.asarray([b.mid_z_down_m for b in sweep.bodies]),
                normal_y=np.asarray([b.normal_y for b in sweep.bodies]),
                normal_z=np.asarray([b.normal_z for b in sweep.bodies]),
                length=np.asarray([b.length_m for b in sweep.bodies]),
                physical_body_normal_velocity=result.diffraction_body_normal_velocity_by_station,
                free_y=sweep.inner_free_surface_y_by_station,
                free_phi_before=sweep.heave_free_surface_potential_by_station,
                free_eta_before=sweep.heave_free_surface_elevation_by_station,
                free_phi_after=sweep.heave_free_surface_potential_after_station,
                free_eta_after=sweep.heave_free_surface_elevation_after_station)
        scale=1000*9.80665*(29144/51975*3*.3*.1875)/3
        rows.append(dict(omega_e_sqrt_L_g=omega_nd, amplitude=abs(result.total_excitation[0])/scale,
            incident_amplitude=abs(result.froude_krylov_force[0])/scale,
            diffraction_amplitude=abs(result.diffraction_force[0])/scale,
            condition=result.maximum_condition_number, residual=result.maximum_linear_system_relative_residual))
        print(rows[-1], flush=True)
    computed = pd.DataFrame(rows)
    computed.to_csv(out/'computed.csv',index=False)
    if hashlib.sha256(reference.read_bytes()).hexdigest() != contract['hashes'][str(reference)]:
        raise ValueError('Reference changed during solve')
    refs=pd.read_csv(reference)
    refs=refs[refs.component=='heave']
    comparison=computed.merge(refs, on='omega_e_sqrt_L_g', suffixes=('_computed','_reference'), validate='one_to_one')
    if len(comparison)!=3 or comparison.amplitude_reference.isna().any():
        raise ValueError('Incomplete reference coverage')
    comparison['relative_difference']=abs(comparison.amplitude_computed/comparison.amplitude_reference-1)
    comparison['screening_within_15_percent']=comparison.relative_difference<=.15
    comparison.to_csv(out/'comparison.csv',index=False)
    print(comparison[['omega_e_sqrt_L_g','amplitude_computed','amplitude_reference','relative_difference']].to_string(index=False))
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        scope='Total heave amplitude only; one grid; reference admission remains incomplete',
        screening_pass_count=int(comparison.screening_within_15_percent.sum()), count=3),indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--preset', choices=tuple(PRESETS), default='baseline')
    p.add_argument('--radius-beams', type=float, default=3.)
    p.add_argument('--k-max', type=float, default=25.)
    p.add_argument('--save-boundary', action='store_true')
    a=p.parse_args()
    run(a.out, a.preset, radius_beams=a.radius_beams, k_max=a.k_max, save_boundary=a.save_boundary)
