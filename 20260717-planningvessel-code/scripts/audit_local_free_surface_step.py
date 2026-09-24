"""Frozen-section feedback spectrum; excludes changes in exterior history."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    InnerDomainPanelGeometry, MatchedSectionBoundaryData, build_control_surface_geometry,
    build_transient_free_surface_history, assemble_matched_section_system, _inner_a_matrix)
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


def step_matrix(operator, dt, gravity=9.80665):
    """eta_new=eta+dt*K*phi; phi_new=phi-g*dt*eta_new."""
    k = np.asarray(operator)
    if k.ndim != 2 or k.shape[0] != k.shape[1] or not np.isfinite(k).all() or not np.isfinite(dt) or dt <= 0:
        raise ValueError('Finite square operator and positive timestep required')
    identity = np.eye(len(k))
    return np.block([[identity-gravity*dt*dt*k, -gravity*dt*identity], [dt*k, identity]])


def run(saved, out):
    inputs = sorted(saved.glob('*.npz'))
    if len(inputs) != 6:
        raise ValueError('Three body and free-surface snapshots required')
    contract = json.loads((saved/'contract.json').read_text())
    if contract['integration_route'] != 'reconstructed_symmetric':
        raise ValueError('This audit requires the declared reconstructed route')
    out.mkdir(parents=True, exist_ok=False)
    root = Path('planing_seakeeping/kernels/linear_2p5d')
    sources = [Path(__file__), *sorted(root.glob('*.py')), saved/'contract.json', *inputs]
    (out/'contract.json').write_text(json.dumps(dict(
        stations=[12,42,80], scope='Frozen local feedback with exterior history held fixed, not coupled stability acceptance',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}), indent=2))
    rows = []
    with panel_integration_route('reconstructed_symmetric'):
        for body_path in sorted(saved.glob('boundary_*.npz')):
            case = body_path.stem.removeprefix('boundary_')
            with np.load(body_path) as b, np.load(saved/f'free_surface_{case}.npz') as f:
                for i in (12,42,80):
                    body = InnerDomainPanelGeometry(mid_y_m=b['y'][i], mid_z_down_m=b['z'][i],
                        normal_y=b['normal_y'][i], normal_z=b['normal_z'][i], length_m=b['length'][i],
                        node_y_m=b['node_y'][i], node_z_down_m=b['node_z'][i])
                    y, length = f['y'][i], f['length'][i]
                    n = len(y)
                    nodes = np.r_[y[:n//2]-length[:n//2]/2, y[n//2-1]+length[n//2-1]/2,
                                  y[n//2:]-length[n//2:]/2, y[-1]+length[-1]/2]
                    free = InnerDomainPanelGeometry(mid_y_m=y, mid_z_down_m=np.zeros(n), normal_y=np.zeros(n),
                        normal_z=-np.ones(n), length_m=length, node_y_m=nodes, node_z_down_m=np.zeros(n+2))
                    control = build_control_surface_geometry(float(nodes[-1]), contract['control'])
                    dt = float(f['time_after'][i]-f['time_before'][i])
                    history = build_transient_free_surface_history(control, dt, 1,
                        quadrature_count=contract['history_quadrature_count'], k_max=contract['history_k_max'])
                    zeros = np.zeros((1, control.panel_count), complex)
                    data = MatchedSectionBoundaryData(body=body, inner_free_surface=free, control=control,
                        body_normal_velocity=np.zeros(body.panel_count), free_surface_potential=np.zeros(n),
                        history=history, past_control_potential=zeros, past_control_normal_derivative=zeros)
                    system = assemble_matched_section_system(data)
                    rhs = np.vstack([-_inner_a_matrix(g, free, same_boundary=g is free, diagonal_sign=-1.)
                                     for g in (body,free,control)] + [np.zeros((control.panel_count,n))])
                    solution = np.linalg.solve(system.matrix, rhs)
                    k = solution[body.panel_count:body.panel_count+n]
                    eigenvalues = np.linalg.eigvals(k)
                    eigenstep = np.linalg.eigvals(step_matrix(k,dt))
                    rows.append(dict(case=case, station=i, x=float(f['x'][i]), dt=dt,
                        min_real_feedback=float(eigenvalues.real.min()), max_real_feedback=float(eigenvalues.real.max()),
                        max_imag_feedback=float(abs(eigenvalues.imag).max()),
                        max_g_dt2_lambda=float(9.80665*dt*dt*eigenvalues.real.max()),
                        frozen_step_spectral_radius=float(abs(eigenstep).max()),
                        matrix_residual=float(np.linalg.norm(system.matrix@solution-rhs)/np.linalg.norm(rhs))))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'local_feedback.csv', index=False)
    print(frame.to_string(index=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--saved', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    run(a.saved,a.out)
