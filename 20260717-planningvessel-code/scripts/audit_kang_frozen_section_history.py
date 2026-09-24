"""Actual history-coupled homogeneous perturbation march on a fixed Kang midship section."""
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
from planing_seakeeping.types import ValidityReport


def run(out):
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), Path(__file__).with_name('audit_kang_local_marching_spectrum.py'),
        *sorted((root/'planing_seakeeping/kernels/linear_2p5d').glob('*.py'))]
    out.mkdir(parents=True, exist_ok=False)
    contract = dict(stage_acceptance=False, scope='Fixed midship section, zero body forcing, actual outer history, finite-time perturbation growth; not ship solution',
        radii=[3.,6.], free_panels=128, control_panels=192, body_panels=64,
        station_counts_for_dt=[81,161], initial_seed=24,
        reference_steps=64, reference_history_steps=128,
        state_norm='norm([phi, sqrt(g*B)*eta]) / initial norm; not conserved physical energy',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'contract.json').write_text(json.dumps(contract, indent=2))
    rows, histories = [], []
    for radius in contract['radii']:
        data, system, rhs_map, _ = local_operator(radius, 128, 192, return_system=True)
        lu = lu_factor(system.matrix)
        for stations in contract['station_counts_for_dt']:
            refinement = (stations-1)//80
            dt = 3*(1-2e-6)/(stations-1)/(.2*np.sqrt(9.80665*3))
            steps, history_steps = 64*refinement, 128*refinement
            history = f.build_transient_free_surface_history(data.control, dt,
                history_steps, quadrature_count=64, k_max=25.)
            pp = np.zeros((history_steps,192), complex)
            pn = np.zeros_like(pp)
            dynamic_data = replace(data, history=history, past_control_potential=pp,
                past_control_normal_derivative=pn)
            check = f.assemble_matched_section_system(dynamic_data)
            if not np.array_equal(check.matrix, system.matrix):
                raise ValueError('Cannot reuse matrix: history timestep changed instantaneous system')
            rng = np.random.default_rng(24)
            phi = rng.normal(size=128)+1j*rng.normal(size=128)
            phi /= np.linalg.norm(phi)
            state = f.FreeSurfaceMarchingState(y_m=data.inner_free_surface.mid_y_m,
                potential_m2_s=phi, elevation_m=np.zeros(128,complex), time_s=0.,
                half_step_time_s=-dt/2, validity=ValidityReport(status='perturbation', reference_cases=(), notes=()))
            norms = [1.]
            max_residual, max_rhs_error = 0., 0.
            for step in range(steps):
                rhs = rhs_map@state.potential_m2_s
                rhs[-192:] += history.convolution_rhs(pp, pn)
                if step in (0,1,steps-1):
                    assembled = f.assemble_matched_section_system(replace(dynamic_data,
                        free_surface_potential=state.potential_m2_s,
                        past_control_potential=pp, past_control_normal_derivative=pn))
                    err = np.linalg.norm(rhs-assembled.rhs)/max(np.linalg.norm(rhs),1e-30)
                    max_rhs_error = max(max_rhs_error,float(err))
                value = lu_solve(lu, rhs)
                residual = np.linalg.norm(system.matrix@value-rhs)/max(np.linalg.norm(rhs),1e-30)
                max_residual = max(max_residual,float(residual))
                solution = f.split_matched_section_solution(dynamic_data, value)
                pp, pn = f._prepend_control_history(pp, pn, solution)
                state = f.advance_free_surface_state(state, solution.inner_free_surface_normal_derivative, dt)
                norm = float(np.linalg.norm(np.r_[state.potential_m2_s, np.sqrt(9.80665*.3)*state.elevation_m]))
                if not np.isfinite(norm):
                    raise ValueError('Nonfinite perturbation propagation')
                norms.append(norm)
            if max(max_rhs_error,max_residual)>1e-10:
                raise ValueError('History march does not reproduce assembled equations')
            for step, norm in enumerate(norms):
                histories.append(dict(radius=radius, stations=stations, time_s=step*dt, state_norm=norm))
            rows.append(dict(radius=radius, stations=stations, dt_s=dt, duration_s=steps*dt,
                history_duration_s=history_steps*dt, max_norm=max(norms), final_norm=norms[-1],
                max_solve_residual=max_residual, max_rhs_replay_error=max_rhs_error))
            print(rows[-1],flush=True)
    pd.DataFrame(histories).to_csv(out/'norm_history.csv',index=False)
    pd.DataFrame(rows).to_csv(out/'summary.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        scope='One initial perturbation, fixed section; growth evidence only, no general stability pass', rows=rows),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
