"""Re-solve saved steady surface states; export actual pressure-BVP panel fields."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import (
    MovingWedgeConfig, MovingWedgeState, LinearDraftEntryMotion, moving_wedge_load,
)

def integrate_exported_pressure(labels, pressure, normals, lengths, half_domain):
    labels = np.asarray(labels)
    pressure, normals, lengths = map(np.asarray, (pressure, normals, lengths))
    n = labels.size
    if labels.shape != (n,) or pressure.shape != (n,) or normals.shape != (n, 2) or lengths.shape != (n,):
        raise ValueError('Panel arrays must have matching locations')
    if not all(np.isfinite(a).all() for a in (pressure, normals, lengths)) or np.any(lengths <= 0):
        raise ValueError('Finite fields and positive panel lengths required')
    physical = labels == 'body'
    if not physical.any():
        raise ValueError('No physical body panels')
    return float((2 if half_domain else 1) * np.sum(pressure[physical] * normals[physical, 1] * lengths[physical]))


def validate_indices(indices, count):
    if not indices or any(not isinstance(i, (int, np.integer)) or isinstance(i, bool) for i in indices):
        raise ValueError('Nonempty integer state indices required')
    if len(set(indices)) != len(indices) or any(i < 0 or i >= count for i in indices):
        raise ValueError('Unique in-range state indices required')


def run(archive, out, indices, rho, gravity):
    meta_path = archive.with_suffix('.json')
    meta = json.loads(meta_path.read_text())
    if not np.isfinite([rho, gravity]).all() or rho <= 0 or gravity <= 0:
        raise ValueError('Positive density and gravity required explicitly')
    config = MovingWedgeConfig(**{**meta['config'], 'mean_draft_m':meta['reference_draft_m']})
    if config.pressure_interpolation != 'constant_panel':
        raise ValueError('This exporter currently requires panel-centred pressure recovery')
    motion = LinearDraftEntryMotion(reference_draft_m=meta['reference_draft_m'],
        initial_draft_m=meta['initial_draft_m'], draft_rate_mps=meta['speed_mps']*np.tan(meta['trim_rad']))
    with np.load(archive, allow_pickle=False) as data:
        validate_indices(indices, len(data['time_s']))
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    files = [archive,meta_path,Path(__file__),
             *sorted((root/'planing_seakeeping/kernels/nonlinear_2dt').rglob('*.py'))]
    (out/'contract.json').write_text(json.dumps(dict(
        indices=indices,rho=rho,gravity=gravity,force_replay_rtol=1e-10,force_replay_atol=1e-8,
        scope='Saved-field replay at selected sections only, not independent physical validation',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2))
    rows=[]
    with np.load(archive,allow_pickle=False) as data:
        for i in indices:
            values={side+suffix:data[f'{i}_{side}_{key}'] for side in ('left','right')
                for suffix,key in (('_free_y_m','y_m'),('_free_z_up_m','z_up_m'),
                                   ('_free_potential_m2_s','potential_m2_s'))}
            state=MovingWedgeState(**values,time_s=float(data['time_s'][i]),
                                   jet_cut_count=int(data[f'{i}_jet_cut_count']))
            load=moving_wedge_load(config,motion,state,rho_water_kg_m3=rho,gravity_m_s2=gravity)
            pressure,boundary=load.pressure,load.boundary
            labels=np.asarray(boundary.panel_labels,dtype=str)
            if pressure.gauge_pressure_pa.shape != (boundary.panel_count,):
                raise ValueError('Pressure and panel geometry do not share locations')
            actual=pressure.body_vertical_force_per_length_n_m
            integrated=integrate_exported_pressure(labels, pressure.gauge_pressure_pa,
                boundary.panel_normal, boundary.panel_length_m, config.use_symmetry_half_domain)
            expected=float(data['sectional_force_n_m'][i])
            integrated_passed=bool(np.isclose(integrated,actual,rtol=1e-10,atol=1e-8))
            passed=bool(np.isclose(actual,expected,rtol=1e-10,atol=1e-8)) and integrated_passed
            np.savez_compressed(out/f'section_{i}.npz',
                node_y_m=boundary.node_y_m,node_z_up_m=boundary.node_z_up_m,
                panel_y_m=boundary.panel_mid_y_m,panel_z_up_m=boundary.panel_mid_z_up_m,
                panel_length_m=boundary.panel_length_m,panel_normal=boundary.panel_normal,
                panel_labels=labels,pressure_pa=pressure.gauge_pressure_pa,
                transverse_velocity_mps=pressure.velocity_mps,
                potential_time_derivative_m2_s2=pressure.potential_time_derivative_m2_s2,
                time_s=state.time_s,x_from_transom_m=data['x_from_transom_m'][i],
                symmetry_multiplier=2 if config.use_symmetry_half_domain else 1)
            rows.append(dict(index=i,time_s=state.time_s,x_from_transom_m=data['x_from_transom_m'][i],
                saved_force_n_m=expected,replayed_force_n_m=actual,absolute_difference=abs(actual-expected),
                integrated_force_n_m=integrated,integration_passed=integrated_passed,
                replay_passed=passed,potential_bvp_residual=load.potential_bvp_relative_residual,
                pressure_bvp_residual=pressure.auxiliary_solution.relative_residual))
    pd.DataFrame(rows).to_csv(out/'replay.csv',index=False)
    passed=all(r['replay_passed'] for r in rows)
    (out/'summary.json').write_text(json.dumps(dict(replay_passed=passed,
        physical_acceptance='NOT_PASSED',half_domain=config.use_symmetry_half_domain,
        field_scope='Pressure auxiliary BVP transverse velocity, not full 3D steady velocity or Hessian',
        force_scope='Full symmetric force if half_domain is true; saved panels remain half-domain'),indent=2))
    print(pd.DataFrame(rows).to_string(index=False))
    if not passed:
        raise RuntimeError('Saved force replay failed; fields not admitted')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--indices',type=int,nargs='+',required=True)
    p.add_argument('--rho',type=float,required=True)
    p.add_argument('--gravity',type=float,required=True)
    a=p.parse_args()
    run(a.archive,a.out,a.indices,a.rho,a.gravity)
