"""Compare pressure routes on identical stored fields, without reading responses."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.formulation import DEFAULT_A1_HEAVE_PITCH_CONVENTION
from planing_seakeeping.kernels.linear_2p5d.weighted_transport import clipped_pressure_identity


def run(config, saved, out):
    raw, boat = load_linear_case(config)
    contract_path = saved/'contract.json'
    original_contract = json.loads(contract_path.read_text())
    if hashlib.sha256(config.read_bytes()).hexdigest() != original_contract['config_sha256']:
        raise ValueError('Snapshot configuration hash mismatch')
    paths = [saved/f"boundary_{case['id']}.npz" for case in raw['cases']]
    if len(paths) != 3 or not all(path.is_file() for path in paths):
        raise ValueError('Three saved speed cases required')
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), config, contract_path, *paths,
               root/'planing_seakeeping/kernels/linear_2p5d/weighted_transport.py',
               root/'planing_seakeeping/kernels/linear_2p5d/formulation.py',
               root/'planing_seakeeping/quadrature.py']
    out.mkdir(parents=True, exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(
        scope='Stored diffraction potentials only; Eq32-like term diagnostic is NOT radiation validation',
        phase='Raw A1 generalized force, no response sine-phase adapter',
        cutoff_beams=.5, identity_tolerance=1e-12,
        hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}), indent=2))
    rows = []
    for case, path in zip(raw['cases'], paths, strict=True):
        omega = case['encounter_omega_rad_s'][original_contract['frequency_index']]
        rho, speed, cutoff = boat.rho_water_kg_m3, case['speed_mps'], .5*boat.beam_m
        with np.load(path) as data:
            x, phi = data['x'], data['phi']
            # Match the existing A1 pressure integral exactly: upward heave,
            # lever=lcg-x; application bow-up conversion occurs downstream.
            measure = np.asarray([
                DEFAULT_A1_HEAVE_PITCH_CONVENTION.pressure_generalized_rows(
                    nz, ds, lever_arm_m=boat.lcg_m-position)
                for position, nz, ds in zip(x, data['normal_z'], data['length'], strict=True)
            ]).transpose(0, 2, 1)
            result = clipped_pressure_identity(x, phi, measure, data['chain'], cutoff,
                                              rho=rho, speed=speed, omega=omega)
            pressure = -rho*1j*omega*phi + rho*speed*data['material_gradient']
            density = np.sum(pressure[:, :, None]*measure, axis=1)
            index_force = clipped_piecewise_linear_integral(x, density, cutoff)
            corrected_pressure = pressure - rho*speed*data['chain']
            corrected_density = np.sum(corrected_pressure[:, :, None]*measure, axis=1)
            nodal_eulerian = clipped_piecewise_linear_integral(x, corrected_density, cutoff)
            time_density = np.sum((-rho*1j*omega*phi)[:, :, None]*measure, axis=1)
            stokes_density = np.zeros_like(time_density)
            stokes_density[:, 1] = rho*speed*np.sum(phi*measure[:, :, 0], axis=1)
            # Existing cut drops the original aft end. This emulates that
            # algebra on a diffraction field, not the radiation solution.
            eq32_like = clipped_piecewise_linear_integral(x, time_density+stokes_density, cutoff)
            result.update(index_gradient_nodal=index_force, eulerian_nodal=nodal_eulerian,
                          eq32_like_cut=eq32_like, eq32_like_with_edges=eq32_like+
                          result['lower_edge']+result['upper_edge'])
            for i, mode in enumerate((3, 5)):
                scale = max(sum(abs(result[k][i]) for k in
                                ('time', 'bulk', 'chain', 'lower_edge', 'upper_edge')), 1e-15)
                row = dict(case=case['id'], mode=mode, omega=omega,
                           unit='N/m_wave_amplitude' if mode == 3 else 'N_m/m_wave_amplitude',
                           identity_relative_residual=abs(result['residual'][i])/scale,
                           nodal_vs_piecewise_force_difference=abs(nodal_eulerian[i]-result['direct'][i]),
                           eq32_like_vs_direct_difference=abs(eq32_like[i]-result['direct'][i]),
                           edge_only_vs_direct_difference=abs(result['eq32_like_with_edges'][i]-result['direct'][i]))
                for key, value in result.items():
                    row[key+'_real'], row[key+'_imag'] = value[i].real, value[i].imag
                rows.append(row)
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'pressure_routes.csv', index=False)
    passed = bool(np.isfinite(frame.select_dtypes(include='number')).all().all()
                  and (frame.identity_relative_residual <= 1e-12).all())
    (out/'summary.json').write_text(json.dumps(dict(
        identity_passed=passed, physical_acceptance='NOT_PASSED',
        response_reference_read=False, production_kernel_changed=False,
        warning='Differences concern saved diffraction fields at one frequency per speed, not total response error.'), indent=2))
    print(frame[['case', 'mode', 'identity_relative_residual',
                 'eq32_like_vs_direct_difference', 'edge_only_vs_direct_difference']].to_string(index=False))
    if not passed:
        raise RuntimeError('Pressure integration identity failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'saved', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.config, args.saved, args.out)
