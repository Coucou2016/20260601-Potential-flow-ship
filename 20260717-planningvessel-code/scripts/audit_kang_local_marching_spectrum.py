"""Frozen-section, frozen-history spectrum of the actual matched BEM/free-surface update."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.kang_reference_geometry import build_hull
from planing_seakeeping.kernels.linear_2p5d import formulation as f


def marching_matrix(operator, dt, gravity=9.80665):
    k = np.asarray(operator, complex)
    if (k.ndim != 2 or k.shape[0] != k.shape[1] or not k.size
            or not np.isfinite(k).all() or not np.isfinite([dt, gravity]).all()
            or min(dt, gravity) <= 0):
        raise ValueError('Finite square operator and positive timestep/gravity required')
    identity = np.eye(len(k))
    # State [phi^n, eta^(n-1/2)]; q^n=K phi^n with past outer history held fixed.
    return np.block([[identity-gravity*dt**2*k, -gravity*dt*identity],
                     [dt*k, identity]])


def local_operator(radius_beams, free_count, control_count, *, return_system=False):
    hull = build_hull(5, 161, moment_reference_x=1.5)
    station = hull.stations[2]
    body = f.build_inner_domain_panel_geometry(station.section_offsets(), body_panel_count=64)
    radius = radius_beams*.3
    free = f.build_waterline_clipped_free_surface_geometry(-radius, radius, .15,
        panel_count=free_count, grading_exponent=1.5)
    control = f.build_control_surface_geometry(radius_m=radius, panel_count=control_count)
    # History values are zero and frozen. One lag suffices for the local partial derivative;
    # this intentionally excludes feedback through future stored control states.
    history = f.build_transient_free_surface_history(control, dt_s=.03456841270825927,
        history_steps=1, quadrature_count=64, k_max=25.)
    data = f.MatchedSectionBoundaryData(body=body, inner_free_surface=free, control=control,
        history=history, body_normal_velocity=np.zeros(body.panel_count, complex),
        free_surface_potential=np.zeros(free_count, complex),
        past_control_potential=np.zeros((1, control_count), complex),
        past_control_normal_derivative=np.zeros((1, control_count), complex))
    system = f.assemble_matched_section_system(data)
    rhs_map = np.vstack([
        -f._inner_a_matrix(geometry, free, same_boundary=(j==1), diagonal_sign=-1.)
        for j, geometry in enumerate((body, free, control))] + [np.zeros((control_count, free_count))])
    solution_map = np.linalg.solve(system.matrix, rhs_map)
    operator = solution_map[body.panel_count:body.panel_count+free_count]
    residual = np.linalg.norm(system.matrix@solution_map-rhs_map)/np.linalg.norm(rhs_map)
    rng = np.random.default_rng(24)
    value = rng.normal(size=free_count)+1j*rng.normal(size=free_count)
    check = f.assemble_matched_section_system(replace(data, free_surface_potential=value))
    rhs_error = np.linalg.norm(rhs_map@value-check.rhs)/np.linalg.norm(check.rhs)
    if not np.isfinite([residual, rhs_error]).all() or max(residual, rhs_error) > 1e-10:
        raise ValueError('Extracted free-surface operator does not reproduce assembled system')
    if return_system:
        return data, system, rhs_map, operator
    return operator, residual, rhs_error, min(free.length_m)


def run(out):
    root = Path(__file__).resolve().parents[1]
    files = [Path(__file__), root/'scripts/kang_reference_geometry.py',
        *sorted((root/'planing_seakeeping/kernels/linear_2p5d').glob('*.py')),
        root/'planing_seakeeping/station_2p5d.py', root/'planing_seakeeping/section_bem.py']
    out.mkdir(parents=True, exist_ok=False)
    contract = dict(stage_acceptance=False, scope='Midship local derivative with frozen outer history; not complete marching stability',
        radius_beams=[3., 4.5, 6.], boundary_counts=[[64,96],[128,192]],
        stations_for_dt=[81,161,321], spectral_excess_tolerance=1e-8,
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'contract.json').write_text(json.dumps(contract, indent=2))
    rows = []
    for radius in contract['radius_beams']:
        for free, control in contract['boundary_counts']:
            operator, residual, rhs_error, minimum_length = local_operator(radius, free, control)
            eig = np.linalg.eigvals(operator)
            np.savez_compressed(out/f'operator_r{radius:g}_free{free}.npz', operator=operator, eigenvalues=eig)
            for stations in contract['stations_for_dt']:
                dt = 3*(1-2e-6)/(stations-1)/(.2*np.sqrt(9.80665*3))
                amplification = np.linalg.eigvals(marching_matrix(operator, dt))
                spectral_radius = float(max(abs(amplification)))
                rows.append(dict(radius_beams=radius, free_panels=free, control_panels=control,
                    stations=stations, dt_s=dt, minimum_free_length_m=minimum_length,
                    max_operator_eigenvalue_real=float(max(eig.real)),
                    max_operator_eigenvalue_imag=float(max(abs(eig.imag))),
                    spectral_radius=spectral_radius,
                    local_amplification=spectral_radius>1+contract['spectral_excess_tolerance'],
                    map_residual=residual, rhs_replay_error=rhs_error))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'spectrum.csv', index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        full_history_stability_proved=False, local_amplifying_cases=int(frame.local_amplification.sum()),
        max_map_residual=float(frame.map_residual.max()), max_rhs_replay_error=float(frame.rhs_replay_error.max())), indent=2))
    print(frame[['radius_beams','free_panels','stations','spectral_radius','local_amplification']].to_string(index=False))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
