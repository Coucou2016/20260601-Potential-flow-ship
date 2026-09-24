"""Resolve saved radiation assembly gaps without fitting or rerunning the solver."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.weighted_transport import clipped_pressure_identity
from scripts.audit_conservative_pressure_replay import recover_v_sweep


def bow_up_coefficients(raw_force, force_mode, radiation_mode, omega):
    """Apply row and column coordinate transforms; R=omega^2*A-i*omega*B."""
    if force_mode not in (3, 5) or radiation_mode not in (3, 5):
        raise ValueError('Only heave and pitch are supported')
    if not np.isfinite(omega) or omega <= 0 or not np.isfinite(raw_force):
        raise ValueError('Finite force and positive frequency required')
    sign = (1 if force_mode == 3 else -1)*(1 if radiation_mode == 3 else -1)
    value = sign*raw_force
    return dict(A=value.real/omega**2, B=-value.imag/omega)


def geometry_and_stokes(x, phi, j3, lcg, cutoff):
    """Integrate -phi*J3'*(1,lcg-x) and (0,phi*J3) exactly on linear traces."""
    geometry, stokes = np.zeros(2, complex), np.zeros(2, complex)
    for i, dx in enumerate(np.diff(x)):
        lo, hi = max(cutoff, x[i]), x[i+1]
        if hi <= lo:
            continue
        q = (lo+hi)/2 + (hi-lo)/(2*np.sqrt(3))*np.array([-1., 1.])
        t = (q-x[i])/dx
        p = phi[i]+t[:, None]*(phi[i+1]-phi[i])
        j = j3[i]+t[:, None]*(j3[i+1]-j3[i])
        dj = (j3[i+1]-j3[i])/dx
        levers = np.column_stack((np.ones(2), lcg-q))
        geometry -= (hi-lo)/2*np.sum(np.sum(p*dj, axis=1)[:, None]*levers, axis=0)
        stokes[1] += (hi-lo)/2*np.sum(p*j)
    return geometry, stokes


def graph_boundary_terms(x, y, z, phi, qn, j3):
    """Diagnostic for two straight V traces with z=f(x,y), J3=-abs(dy).

    Returns waterline endpoint and submerged graph-slope densities. Midpoint
    potentials are extrapolated linearly to the two waterline endpoints.
    This is not a general hull/overhang reconstruction.
    """
    count = y.shape[1]
    if count < 6 or count % 2 or np.any(j3 >= 0):
        raise ValueError('Two equally sized V traces with negative J3 required')
    vz, slope = np.empty_like(phi), np.empty_like(y)
    for start, stop in ((0, count//2), (count//2, count)):
        yy, zz, pp = y[:, start:stop], z[:, start:stop], phi[:, start:stop]
        dy, dz = np.gradient(yy, axis=1), np.gradient(zz, axis=1)
        ds = np.hypot(dy, dz)
        ty, tz = dy/ds, dz/ds
        if np.any(ty >= 0):
            raise ValueError('Expected right-to-left trace ordering')
        local_slope = dz/dy
        if not np.allclose(local_slope, local_slope[:, :1], atol=1e-10, rtol=1e-10):
            raise ValueError('Graph diagnostic only supports straight V sides')
        slope[:, start:stop] = local_slope
        for k in range(len(x)):
            arc = np.r_[0., np.cumsum(np.hypot(np.diff(yy[k]), np.diff(zz[k])))]
            tangent_derivative = np.gradient(pp[k], arc, edge_order=2)
            # Normal=(tz,-ty), with positive downward component on both sides.
            vz[k, start:stop] = tz[k]*tangent_derivative-ty[k]*qn[k, start:stop]
    graph_x = np.gradient(z, x, axis=0, edge_order=2)-slope*np.gradient(y, x, axis=0, edge_order=2)
    interior = -np.sum(vz*graph_x*j3, axis=1)
    width = -np.sum(j3, axis=1)
    right = y[:, 0]-j3[:, 0]/2
    left = y[:, -1]+j3[:, -1]/2
    p_right = phi[:, 0]+(phi[:, 0]-phi[:, 1])/(y[:, 0]-y[:, 1])*(right-y[:, 0])
    p_left = phi[:, -1]+(phi[:, -1]-phi[:, -2])/(y[:, -1]-y[:, -2])*(left-y[:, -1])
    edge = .5*np.gradient(width, x, edge_order=2)*(p_right+p_left)
    return edge, interior


def tangential_transport_defect(x, y, phi, j3, waterline):
    """Discrete product-rule defect, independent of normal boundary velocity.

    For J3=-abs(dy), -sum(phi*J3_x + phi_y_along_surface*y_x*J3)
    should equal the two moving waterline endpoint contributions. Pointwise
    gradients and midpoint integration need not satisfy this identity.
    """
    count = y.shape[1]
    derivative = np.empty_like(phi)
    for start, stop in ((0, count//2), (count//2, count)):
        for k in range(len(x)):
            derivative[k, start:stop] = np.gradient(
                phi[k, start:stop], y[k, start:stop], edge_order=2)
    yx = np.gradient(y, x, axis=0, edge_order=2)
    jx = np.gradient(j3, x, axis=0, edge_order=2)
    geometry_density = -np.sum(phi*jx, axis=1)
    defect = geometry_density-np.sum(derivative*yx*j3, axis=1)-waterline
    return geometry_density, defect


def run(config, saved, out, full_domain=False):
    raw, boat = load_linear_case(config)
    contract = json.loads((saved/'contract.json').read_text())
    config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    if config_hash not in contract['hashes'].values():
        raise ValueError('Saved run does not contain this configuration hash')
    paths = [saved/f"boundary_{case['id']}_radiation{mode}.npz"
             for case in raw['cases'] for mode in (3, 5)]
    if len(paths) != 6 or not all(p.is_file() for p in paths):
        raise ValueError('Six radiation snapshots required')
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    files = [Path(__file__), config, saved/'contract.json', *paths,
             root/'scripts/audit_conservative_pressure_replay.py',
             root/'planing_seakeeping/kernels/linear_2p5d/weighted_transport.py',
             root/'planing_seakeeping/kernels/linear_2p5d/trace_transport.py',
             root/'planing_seakeeping/quadrature.py']
    (out/'contract.json').write_text(json.dumps(dict(
        scope='Term attribution on saved fields only; no physical model approval',
        integration_domain='full_saved_domain' if full_domain else 'half_beam_cut',
        aft_endpoint='saved first station, not extrapolated physical transom',
        closure_tolerance=1e-12, graph_closure_tolerance=1e-12,
        hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), indent=2))
    rows, coefficient_rows = [], []
    for case in raw['cases']:
        omega = case['encounter_omega_rad_s'][contract['frequency_index']]
        rho, speed, cutoff = boat.rho_water_kg_m3, case['speed_mps'], .5*boat.beam_m
        for mode in (3, 5):
            with np.load(saved/f"boundary_{case['id']}_radiation{mode}.npz") as data:
                x, phi, measure = data['x'], data['phi'], data['measure']
                if full_domain:
                    cutoff = float(x[0])
                result = clipped_pressure_identity(x, phi, measure, data['chain'], cutoff,
                                                  rho=rho, speed=speed, omega=omega)
                body_production = clipped_piecewise_linear_integral(x, data['production_density'], cutoff)
                # Eq32 end helper uses -rho*U*sum(phi*generalized_rows) at the aft station.
                end = (-rho*speed*np.sum(phi[0, :, None]*measure[0], axis=0)
                       if full_domain else np.zeros(2, complex))
                production = body_production+end
                time = clipped_piecewise_linear_integral(x,
                    np.sum((-rho*1j*omega*phi)[:, :, None]*measure, axis=1), cutoff)
                geometry, stokes = geometry_and_stokes(x, phi, measure[:, :, 0], boat.lcg_m, cutoff)
                geometry, stokes = rho*speed*geometry, rho*speed*stokes
                waterline, submerged = graph_boundary_terms(
                    x, data['y'], data['z'], phi, data['normal_derivative'], measure[:, :, 0])
                geometry_density, tangent_defect = tangential_transport_defect(
                    x, data['y'], phi, measure[:, :, 0], waterline)
                lever = np.column_stack((np.ones(len(x)), boat.lcg_m-x))
                geometry_nodal = rho*speed*clipped_piecewise_linear_integral(x, geometry_density[:, None]*lever, cutoff)
                chain_nodal = -rho*speed*clipped_piecewise_linear_integral(
                    x, np.sum(data['chain']*measure[:, :, 0], axis=1)[:, None]*lever, cutoff)
                tangent_defect = rho*speed*clipped_piecewise_linear_integral(x, tangent_defect[:, None]*lever, cutoff)
                waterline = rho*speed*clipped_piecewise_linear_integral(x, waterline[:, None]*lever, cutoff)
                submerged = rho*speed*clipped_piecewise_linear_integral(x, submerged[:, None]*lever, cutoff)
                graph_residual = geometry+result['chain']-waterline-submerged
                predicted_residual = geometry-geometry_nodal+result['chain']-chain_nodal+tangent_defect
                terms = dict(time_quadrature=result['time']-time,
                    geometry=geometry, moment_product=result['bulk']-geometry-stokes,
                    stokes_quadrature=stokes-(body_production-time), chain=result['chain'],
                    lower_edge=result['lower_edge']-end, upper_edge=result['upper_edge'])
                gap = result['direct']-production
                residual = gap-sum(terms.values())
                pressure = recover_v_sweep(x, data['y'], data['z'], phi,
                    data['normal_derivative'], data['material_gradient'], measure[:, :, 0],
                    rho=rho, speed=speed, omega=omega)
                conservative = clipped_piecewise_linear_integral(x,
                    np.sum(pressure[:, :, None]*measure, axis=1), cutoff)
                all_terms = dict(terms, conservative_reconstruction=conservative-result['direct'])
                for i, force in enumerate((3, 5)):
                    converted = {name: bow_up_coefficients(value[i], force, mode, omega)
                                 for name, value in all_terms.items()}
                    old_ab = bow_up_coefficients(production[i], force, mode, omega)
                    new_ab = bow_up_coefficients(conservative[i], force, mode, omega)
                    for kind in ('A', 'B'):
                        contributions = {name: values[kind] for name, values in converted.items()}
                        graph_terms = {name: bow_up_coefficients(value[i], force, mode, omega)[kind]
                            for name, value in dict(graph_waterline=waterline,
                                graph_submerged=submerged,
                                graph_discrete_residual=graph_residual).items()}
                        delta = new_ab[kind]-old_ab[kind]
                        closure = abs(delta-sum(contributions.values()))/max(
                            sum(abs(v) for v in contributions.values()), abs(delta), 1e-15)
                        coefficient_rows.append(dict(case=case['id'], omega=omega,
                            cutoff_m=cutoff, aft_saved_station_m=float(x[0]),
                            coefficient=f'{kind}{force}{mode}', old_value=old_ab[kind],
                            new_value=new_ab[kind], delta=delta,
                            closure_relative_residual=closure, **contributions, **graph_terms))
                    scale = max(sum(abs(value[i]) for value in terms.values()), 1e-15)
                    row = dict(case=case['id'], radiation_mode=mode, force_mode=force,
                        gap_abs=abs(gap[i]), geometry_plus_chain_abs=abs(geometry[i]+result['chain'][i]),
                        graph_waterline_abs=abs(waterline[i]), graph_submerged_abs=abs(submerged[i]),
                        graph_reconstruction_difference=abs(geometry[i]+result['chain'][i]-waterline[i]-submerged[i]),
                        tangent_product_defect_abs=abs(tangent_defect[i]),
                        geometry_quadrature_difference=abs(geometry[i]-geometry_nodal[i]),
                        chain_quadrature_difference=abs(result['chain'][i]-chain_nodal[i]),
                        unexplained_graph_difference=abs(graph_residual[i]-predicted_residual[i]),
                        graph_closure_relative_residual=abs(graph_residual[i]-predicted_residual[i])/max(
                            abs(geometry[i])+abs(result['chain'][i])+abs(waterline[i])+abs(submerged[i]), 1e-15),
                        closure_relative_residual=abs(residual[i])/scale)
                    for name, value in terms.items():
                        row[name+'_real'], row[name+'_imag'], row[name+'_abs'] = value[i].real, value[i].imag, abs(value[i])
                    rows.append(row)
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'gap_components.csv', index=False)
    coefficient_frame = pd.DataFrame(coefficient_rows)
    coefficient_frame.to_csv(out/'coefficient_components.csv', index=False)
    coefficients_passed = bool(np.isfinite(coefficient_frame.select_dtypes(include='number')).all().all()
        and (coefficient_frame.closure_relative_residual <= 1e-12).all())
    passed = bool(np.isfinite(frame.select_dtypes(include='number')).all().all()
                  and (frame.closure_relative_residual <= 1e-12).all())
    graph_passed = bool(np.isfinite(frame.graph_closure_relative_residual).all()
                        and (frame.graph_closure_relative_residual <= 1e-12).all())
    (out/'summary.json').write_text(json.dumps(dict(algebra_closed=passed,
        graph_attribution_closed=graph_passed,
        coefficient_attribution_closed=coefficients_passed,
        coefficient_scope='Three representative frequencies on saved grid, not fullband; conservative pressure minus old Eq32 assembly',
        integration_domain='full_saved_domain' if full_domain else 'half_beam_cut',
        physical_acceptance='NOT_PASSED', response_reference_read=False), indent=2))
    print(frame[['case', 'radiation_mode', 'force_mode', 'gap_abs', 'geometry_plus_chain_abs',
                 'moment_product_abs', 'time_quadrature_abs', 'stokes_quadrature_abs']].to_string(index=False))
    if not passed or not graph_passed or not coefficients_passed:
        raise RuntimeError('Gap attribution does not close')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'saved', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--full-domain', action='store_true')
    a = p.parse_args()
    run(a.config, a.saved, a.out, a.full_domain)
