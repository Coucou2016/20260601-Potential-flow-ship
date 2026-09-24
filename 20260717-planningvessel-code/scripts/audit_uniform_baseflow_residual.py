"""Measure uniform-flow impermeability defect on saved V-shaped mean surfaces."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def graph_metrics(x, y, z, speed):
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    if (x.ndim != 1 or len(x) < 3 or y.ndim != 2 or y.shape != z.shape
            or y.shape[0] != len(x) or y.shape[1] < 6 or y.shape[1] % 2
            or not all(np.isfinite(a).all() for a in (x, y, z))
            or np.any(np.diff(x) <= 0) or not np.isfinite(speed) or speed <= 0):
        raise ValueError('Finite increasing stations, matching V traces and positive speed required')
    fy = np.empty_like(y)
    for part in (slice(None, y.shape[1]//2), slice(y.shape[1]//2, None)):
        yy, zz = y[:, part], z[:, part]
        if np.any(np.diff(yy, axis=1) >= 0):
            raise ValueError('Expected right-to-left ordering on both sides')
        fy[:, part] = np.gradient(zz, axis=1)/np.gradient(yy, axis=1)
        if not np.allclose(fy[:, part], fy[:, part][:, :1], rtol=1e-9, atol=1e-10):
            raise ValueError('Only straight V sides supported')
    fx = np.gradient(z, x, axis=0, edge_order=2)-fy*np.gradient(y, x, axis=0, edge_order=2)
    normalizer = np.sqrt(1+fx**2+fy**2)
    # Graph normal points toward increasing z; uniform hull-frame velocity is (-U,0,0).
    return dict(fx=fx, fy=fy, area_factor=normalizer,
                normal_velocity=speed*fx/normalizer,
                required_transverse_normal_velocity=-speed*fx/np.sqrt(1+fy**2))


def run(config, saved, out):
    raw = json.loads(config.read_text(encoding='utf-8'))
    contract = json.loads((saved/'contract.json').read_text(encoding='utf-8'))
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if digest(config) not in contract['hashes'].values():
        raise ValueError('Saved configuration hash mismatch')
    rows, station_rows, hashes = [], [], {}
    for case in raw['cases']:
        path = saved/f"boundary_{case['id']}_radiation3.npz"
        hashes[str(path)] = digest(path)
        with np.load(path, allow_pickle=False) as data:
            x = data['x']
            result = graph_metrics(x, data['y'], data['z'], case['speed_mps'])
            projected_width = -data['measure'][:, :, 0]
            if np.any(projected_width <= 0):
                raise ValueError('Negative vertical projected measures required')
            area_density = projected_width*result['area_factor']
            section_area = np.sum(area_density, axis=1)
            area = np.trapezoid(section_area, x)
            squared = np.sum(area_density*result['normal_velocity']**2, axis=1)
            rms = np.sqrt(np.trapezoid(squared, x)/area)
            rows.append(dict(case=case['id'], speed_mps=case['speed_mps'], area_m2=area,
                normal_velocity_rms_mps=rms, rms_over_speed=rms/case['speed_mps'],
                normal_velocity_abs_max_mps=np.max(abs(result['normal_velocity'])),
                fx_abs_max=np.max(abs(result['fx']))))
            for i, station in enumerate(x):
                station_rows.append(dict(case=case['id'], x_m=station,
                    fx_mean=np.mean(result['fx'][i]),
                    normal_velocity_rms_mps=np.sqrt(squared[i]/section_area[i]),
                    required_transverse_normal_velocity_mean_mps=np.mean(
                        result['required_transverse_normal_velocity'][i])))
    if len(rows) != 3:
        raise ValueError('Expected three frozen speeds')
    out.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(rows).to_csv(out/'baseflow_residual.csv', index=False)
    pd.DataFrame(station_rows).to_csv(out/'station_residual.csv', index=False)
    (out/'summary.json').write_text(json.dumps(dict(
        physical_acceptance='NOT_PASSED', production_changed=False,
        scope='Uniform-flow defect on saved mean V surface; not a solved steady flow or response error estimate',
        normal_convention='x forward, z down; graph normal (-fx,-fy,1), uniform velocity (-U,0,0)',
        endpoint_scope='saved active domain, no transom extrapolation',
        experiment_read=False, hashes={**hashes, str(config):digest(config),
            str(saved/'contract.json'):digest(saved/'contract.json'), str(Path(__file__)):digest(Path(__file__))}), indent=2), encoding='utf-8')
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'saved', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.config, args.saved, args.out)
