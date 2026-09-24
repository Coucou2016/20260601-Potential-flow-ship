"""Compare actual radiation force assemblies on identical solved potentials."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.schema import Linear2p5DProviderConfig
from planing_seakeeping.planing_frequency_correction import build_planing_wetted_station_hull
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    DEFAULT_A1_HEAVE_PITCH_CONVENTION,
    solve_station_hull_heave_pitch_matched_sweep,
    heave_radiation_normal_velocity,
    pitch_radiation_normal_velocity,
    _force_density_matrix_from_section_results,
)
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route
from planing_seakeeping.kernels.linear_2p5d.pressure_gradient import remove_geometry_chain_term
from planing_seakeeping.kernels.linear_2p5d.weighted_transport import clipped_pressure_identity


def run(config, out, grid_level=None):
    raw, boat = load_linear_case(config)
    if grid_level not in (None, 0, 1, 2):
        raise ValueError('grid_level must be 0, 1, 2 or None')
    stations, body_panels, free, control, history, quadrature = (
        (29, 36, 36, 48, 64, 48) if grid_level is None else
        ((57, 48, 48, 72, 128, 32), (85, 60, 72, 96, 128, 48),
         (113, 72, 96, 120, 128, 64))[grid_level])
    if boat.gravity_m_s2 != 9.80665 or len(raw['cases']) != 3:
        raise ValueError('Three cases with the current kernel gravity required')
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), config, *sorted((root/'planing_seakeeping').rglob('*.py'))]
    out.mkdir(parents=True, exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(
        frequency_index=4, stations=stations, body=body_panels, free=free, control=control,
        history_steps=history, history_quadrature=quadrature, k_max=25., grading=1.5,
        cutoff_beams=.5, identity_tolerance=1e-12,
        scope='Three representative radiation solves; NOT full-band or experimental acceptance',
        force_convention='Raw A1 rows/columns; no bow-up or wave phase conversion',
        hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}), indent=2))
    provider = Linear2p5DProviderConfig(formulation='matched_bie', hull_stations=stations,
        body_panels_per_section=body_panels, free_surface_inner_panels=free, free_surface_outer_panels=control,
        control_surface_radius_beams=3., include_steady_perturbation=False, include_end_terms=True)
    rows = []
    with panel_integration_route('reconstructed_symmetric'):
        for case in raw['cases']:
            speed, omega = case['speed_mps'], case['encounter_omega_rad_s'][4]
            eq = make_prescribed_equilibrium(boat, speed, PrescribedRunningStateConfig(
                enabled=True, trim_deg=case['trim_deg'], lambda_w=case['lambda_w']))
            hull = build_planing_wetted_station_hull(boat, eq, station_count=stations)
            sweep = solve_station_hull_heave_pitch_matched_sweep(hull, omega, speed,
                config=provider, rho_water_kg_m3=boat.rho_water_kg_m3,
                parametric_section_shape='hard_chine_v', history_steps=history,
                history_quadrature_count=quadrature, history_k_max=25., waterline_grading_exponent=1.5)
            x, rho, cutoff = sweep.x_m, boat.rho_water_kg_m3, .5*boat.beam_m
            pressure_sweep = sweep.pressure_force_sweep
            time_density = _force_density_matrix_from_section_results(
                pressure_sweep.heave_mode_forces, pressure_sweep.pitch_mode_forces,
                heave_attr='heave_force_time_derivative_per_m',
                pitch_attr='pitch_moment_time_derivative_per_m')
            density = time_density + pressure_sweep.stokes_body_forward_speed.force_density_by_station
            if not sweep.end_station_x_m < cutoff:
                raise ValueError('This diagnostic requires the physical aft end behind the cut')
            production_cut = clipped_piecewise_linear_integral(x, density, cutoff)
            phase = np.exp(1j*omega*sweep.local_time_s_by_station)
            measure = np.asarray([
                DEFAULT_A1_HEAVE_PITCH_CONVENTION.pressure_generalized_rows(
                    body.normal_z, body.length_m, lever_arm_m=hull.lcg_m-position)
                for position, body in zip(x, sweep.bodies, strict=True)]).transpose(0, 2, 1)
            for column, (mode, solutions, gradient) in enumerate((
                (3, sweep.heave_mode_solutions, pressure_sweep.heave_potential_gradient),
                (5, sweep.pitch_mode_solutions, pressure_sweep.pitch_potential_gradient),
            )):
                phi = np.asarray([s.body_potential for s in solutions])*np.conj(phase[:, None])
                qn = np.asarray([
                    heave_radiation_normal_velocity(body, omega) if mode == 3 else
                    pitch_radiation_normal_velocity(body, omega, hull.lcg_m-position,
                                                   forward_speed_mps=speed)
                    for position, body in zip(x, sweep.bodies, strict=True)])
                if mode == 5:
                    stored_qn = (sweep.pitch_body_condition_oscillation_by_station
                                 + sweep.pitch_body_condition_forward_speed_by_station)*np.conj(phase[:, None])
                    if not np.allclose(qn, stored_qn, rtol=1e-12, atol=1e-12):
                        raise ValueError('Pitch body condition phase/convention mismatch')
                replay_time = np.sum((-rho*1j*omega*phi)[:, :, None]*measure, axis=1)
                if not np.allclose(replay_time, time_density[:, :, column], rtol=1e-12, atol=1e-10):
                    raise ValueError('Stored potential does not reconstruct production time term')
                replay_stokes = np.zeros_like(replay_time)
                replay_stokes[:, 1] = rho*speed*np.sum(phi*measure[:, :, 0], axis=1)
                if not np.allclose(replay_time+replay_stokes, density[:, :, column], rtol=1e-12, atol=1e-10):
                    raise ValueError('Stored potential does not reconstruct production body term')
                material = gradient.body_potential_x_gradient
                _, chain = remove_geometry_chain_term(x, sweep.bodies, material, phi, qn,
                                                      corner_nodes=(body_panels//2,))
                result = clipped_pressure_identity(x, phi, measure, chain, cutoff,
                                                  rho=rho, speed=speed, omega=omega)
                nodal_pressure = -rho*1j*omega*phi+rho*speed*(material-chain)
                nodal_force = clipped_piecewise_linear_integral(
                    x, np.sum(nodal_pressure[:, :, None]*measure, axis=1), cutoff)
                np.savez_compressed(out/f"boundary_{case['id']}_radiation{mode}.npz",
                    x=x, phi=phi, normal_derivative=qn, material_gradient=material, chain=chain,
                    measure=measure, production_density=density[:, :, column],
                    y=np.asarray([b.mid_y_m for b in sweep.bodies]),
                    z=np.asarray([b.mid_z_down_m for b in sweep.bodies]))
                for i, force_mode in enumerate((3, 5)):
                    scale = max(sum(abs(result[k][i]) for k in
                                    ('time', 'bulk', 'chain', 'lower_edge', 'upper_edge')), 1e-15)
                    prod = production_cut[i, column]
                    edge_only = prod+result['lower_edge'][i]+result['upper_edge'][i]
                    row = dict(case=case['id'], radiation_mode=mode, force_mode=force_mode,
                        omega=omega, identity_relative_residual=abs(result['residual'][i])/scale,
                        production_difference=abs(prod-result['direct'][i]),
                        edge_only_difference=abs(edge_only-result['direct'][i]),
                        nodal_vs_piecewise_difference=abs(nodal_force[i]-result['direct'][i]),
                        production_real=prod.real, production_imag=prod.imag)
                    for name, value in result.items():
                        row[name+'_real'], row[name+'_imag'] = value[i].real, value[i].imag
                    rows.append(row)
            pd.DataFrame(rows).to_csv(out/'radiation_pressure_routes.csv', index=False)
            print(case['id']+' complete', flush=True)
    frame = pd.DataFrame(rows)
    passed = bool(np.isfinite(frame.select_dtypes(include='number')).all().all()
                  and (frame.identity_relative_residual <= 1e-12).all())
    (out/'summary.json').write_text(json.dumps(dict(identity_passed=passed,
        physical_acceptance='NOT_PASSED', response_reference_read=False,
        production_kernel_changed=False), indent=2))
    print(frame[['case', 'radiation_mode', 'force_mode', 'identity_relative_residual',
                 'production_difference', 'edge_only_difference']].to_string(index=False))
    if not passed:
        raise RuntimeError('Radiation pressure identity failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--grid-level', type=int, choices=(0, 1, 2))
    args = parser.parse_args()
    run(args.config, args.out, args.grid_level)
