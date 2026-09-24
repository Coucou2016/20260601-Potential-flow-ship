"""Apply straight-trace conservative pressure recovery to saved solved fields."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.trace_transport import recover_straight_trace_pressure


def recover_v_sweep(x, y, z, phi, qn, material, j3, *, rho, speed, omega):
    """Saved symmetric V traces only; reconstruct arc cells from projected widths."""
    arrays = [np.asarray(a) for a in (y, z, phi, qn, material, j3)]
    if (len(x) < 3 or np.any(np.diff(x) <= 0) or not np.isfinite(x).all()
            or any(a.shape != arrays[0].shape or not np.isfinite(a).all() for a in arrays)
            or y.ndim != 2 or y.shape[0] != len(x) or y.shape[1] < 6
            or y.shape[1] % 2 or np.any(j3 >= 0)):
        raise ValueError('Finite matching symmetric V traces and increasing stations required')
    yx, zx = np.gradient(y, x, axis=0, edge_order=2), np.gradient(z, x, axis=0, edge_order=2)
    pressure = np.empty_like(phi, dtype=complex)
    for start, stop in ((0, y.shape[1]//2), (y.shape[1]//2, y.shape[1])):
        for k in range(len(x)):
            yy, zz = y[k, start:stop], z[k, start:stop]
            dy, dz = np.gradient(yy), np.gradient(zz)
            norm = np.hypot(dy, dz)
            ty, tz = dy/norm, dz/norm
            if np.any(ty >= 0) or not np.allclose(tz/ty, (tz/ty)[0], atol=1e-10, rtol=1e-10):
                raise ValueError('Each side must be straight and ordered right to left')
            widths = -j3[k, start:stop]
            projected_nodes = -yy[0]-widths[0]/2+np.r_[0., np.cumsum(widths)]
            if not np.allclose((projected_nodes[:-1]+projected_nodes[1:])/2, -yy, atol=1e-12, rtol=1e-10):
                raise ValueError('Midpoints and projected widths disagree')
            nodes = np.r_[0., np.cumsum(widths/(-ty))]
            mt = ty*yx[k, start:stop]+tz*zx[k, start:stop]
            mn = tz*yx[k, start:stop]-ty*zx[k, start:stop]
            result = recover_straight_trace_pressure(nodes, phi[k, start:stop], qn[k, start:stop],
                material[k, start:stop], mt, mn, rho=rho, speed=speed, omega=omega)
            pressure[k, start:stop] = result['pressure_average']
    return pressure


def run(config, radiation, diffraction, out):
    raw, boat = load_linear_case(config)
    files = [Path(__file__), config,
             Path(__file__).resolve().parents[1]/'planing_seakeeping/kernels/linear_2p5d/trace_transport.py']
    paths = []
    for case in raw['cases']:
        for label in ('radiation3', 'radiation5', 'diffraction'):
            folder = diffraction if label == 'diffraction' else radiation
            suffix = '' if label == 'diffraction' else '_'+label
            paths.append((case, label, folder/f"boundary_{case['id']}{suffix}.npz"))
    files += [p for _, _, p in paths]+[radiation/'contract.json', diffraction/'contract.json']
    if len(paths) != 9 or not all(p.is_file() for p in files):
        raise ValueError('Three speeds and nine saved fields required')
    contracts = [json.loads((folder/'contract.json').read_text()) for folder in (radiation, diffraction)]
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    if (digest not in contracts[0]['hashes'].values() or digest != contracts[1]['config_sha256']
            or any(c['frequency_index'] != 4 for c in contracts)):
        raise ValueError('Saved configuration or frequency mismatch')
    out.mkdir(parents=True, exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(
        scope='Saved-field pressure postprocess at one frequency per speed; no response acceptance',
        grids={name:{key:c[key] for key in ('stations','body','free','control')}
               for name,c in zip(('radiation','diffraction'),contracts)},
        coordinate='Raw A1 generalized rows; no forcing phase adapter', cutoff_beams=.5,
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), indent=2))
    rows = []
    for case, label, path in paths:
        with np.load(path) as data:
            x, phi = data['x'], data['phi']
            j3 = data['measure'][:, :, 0] if label != 'diffraction' else -data['normal_z']*data['length']
            measure = np.stack((j3, j3*(boat.lcg_m-x[:, None])), axis=2)
            rho, speed, omega = boat.rho_water_kg_m3, case['speed_mps'], case['encounter_omega_rad_s'][4]
            pressure = recover_v_sweep(x, data['y'], data['z'], phi, data['normal_derivative'],
                data['material_gradient'], j3, rho=rho, speed=speed, omega=omega)
            old = -rho*1j*omega*phi+rho*speed*(data['material_gradient']-data['chain'])
            new_force = clipped_piecewise_linear_integral(x, np.sum(pressure[:, :, None]*measure, axis=1), .5*boat.beam_m)
            old_force = clipped_piecewise_linear_integral(x, np.sum(old[:, :, None]*measure, axis=1), .5*boat.beam_m)
            np.savez_compressed(out/(path.stem+'_pressure.npz'), x=x, pressure_average=pressure,
                                old_pressure_midpoint=old, measure=measure)
            for i, mode in enumerate((3, 5)):
                rows.append(dict(case=case['id'], field=label, force_mode=mode,
                    old_real=old_force[i].real, old_imag=old_force[i].imag,
                    new_real=new_force[i].real, new_imag=new_force[i].imag,
                    change_abs=abs(new_force[i]-old_force[i]),
                    change_relative=abs(new_force[i]-old_force[i])/max(abs(old_force[i]), 1e-15)))
    frame = pd.DataFrame(rows)
    if not np.isfinite(frame.select_dtypes(include='number')).all().all():
        raise RuntimeError('Nonfinite replay result')
    frame.to_csv(out/'pressure_changes.csv', index=False)
    (out/'summary.json').write_text(json.dumps(dict(status='DIAGNOSTIC_ONLY',
        physical_acceptance='NOT_PASSED', production_changed=False, response_reference_read=False), indent=2))
    print(frame[['case','field','force_mode','change_abs','change_relative']].to_string(index=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('config','radiation','diffraction','out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    run(a.config, a.radiation, a.diffraction, a.out)
