"""Exact overlap comparison of half-domain constant body-panel fields."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def intervals(data):
    if int(data['symmetry_multiplier']) != 2:
        raise ValueError('Only single-sided half-domain panels supported')
    mask = data['panel_labels'] == 'body'
    y = data['node_y_m']
    lo = np.minimum(y[:-1], y[1:])[mask]
    hi = np.maximum(y[:-1], y[1:])[mask]
    values = np.column_stack((data['pressure_pa'][mask], data['transverse_velocity_mps'][mask]))
    order = np.argsort(lo)
    lo, hi, values = lo[order], hi[order], values[order]
    if not len(lo) or not all(np.isfinite(a).all() for a in (lo, hi, values)):
        raise ValueError('Empty or nonfinite physical body fields')
    if np.any(hi <= lo) or np.any(lo[1:] < hi[:-1] - 1e-12):
        raise ValueError('Body must be single-valued in transverse coordinate')
    return lo, hi, values


def compare(a, b):
    al, ah, av = intervals(a)
    bl, bh, bv = intervals(b)
    widths = np.maximum(0., np.minimum(ah[:, None], bh) - np.maximum(al[:, None], bl))
    common = widths.sum()
    if common <= 0:
        raise ValueError('No common body coverage')
    delta = av[:, None, :] - bv[None, :, :]
    rms = np.sqrt(np.sum(widths[:, :, None] * delta**2, axis=(0, 1)) / common)
    maximum = np.max(np.abs(delta[widths > 0]), axis=0)
    union = (ah-al).sum() + (bh-bl).sum() - common
    return rms, maximum, common / union


def localize(a, b):
    al, ah, av = intervals(a)
    bl, bh, bv = intervals(b)
    left = np.maximum(al[:, None], bl)
    right = np.minimum(ah[:, None], bh)
    valid = right > left
    if not valid.any():
        raise ValueError('No common body coverage')
    delta = av[:, None, :] - bv[None, :, :]
    records = []
    for k in range(3):
        score = np.where(valid, np.abs(delta[:, :, k]), -np.inf)
        i, j = np.unravel_index(np.argmax(score), score.shape)
        y = .5*(left[i, j]+right[i, j])
        records.append(dict(coarse_sorted_panel=int(i), fine_sorted_panel=int(j),
            overlap_left_m=float(left[i, j]), overlap_right_m=float(right[i, j]),
            coarse_value=float(av[i, k]), fine_value=float(bv[j, k]),
            difference=float(delta[i, j, k]),
            coarse_span_fraction=float((y-al.min())/(ah.max()-al.min())),
            fine_span_fraction=float((y-bl.min())/(bh.max()-bl.min()))))
    return records


def run(coarse, fine, out, matched_cut_rule=False, smoothing_sensitivity=False):
    contracts = [json.loads((p/'contract.json').read_text()) for p in (coarse, fine)]
    for key in ('indices', 'rho', 'gravity'):
        if contracts[0][key] != contracts[1][key]:
            raise ValueError('Mismatched replay contracts: ' + key)
    if not contracts[0]['indices']:
        raise ValueError('Empty case set')
    metadata, jet_counts = [], []
    for contract in contracts:
        paths = [Path(p) for p in contract['hashes'] if p.endswith('.npz')]
        if len(paths) != 1:
            raise ValueError('Expected one source surface archive')
        if hashlib.sha256(paths[0].read_bytes()).hexdigest() != contract['hashes'][str(paths[0])]:
            raise ValueError('Source archive hash mismatch')
        with np.load(paths[0], allow_pickle=False) as archive:
            jet_counts.append({i: (int(archive[f'{i}_jet_cut_count']),
                int(archive[f'{i}_jet_cut_count']) - int(archive[f'{i-1}_jet_cut_count']) if i else 0)
                for i in contract['indices']})
        meta_path = paths[0].with_suffix('.json')
        if hashlib.sha256(meta_path.read_bytes()).hexdigest() != contract['hashes'][str(meta_path)]:
            raise ValueError('Source metadata hash mismatch')
        metadata.append(json.loads(meta_path.read_text()))
    for key in ('speed_mps', 'trim_rad', 'length_m', 'initial_draft_m', 'reference_draft_m'):
        if metadata[0][key] != metadata[1][key]:
            raise ValueError('Physical case mismatch: ' + key)
    allowed = {'body_panels_per_side', 'free_surface_panels_per_side'}
    if smoothing_sensitivity:
        if matched_cut_rule:
            raise ValueError('Do not combine cut-rule and smoothing experiments')
        for key in allowed:
            if metadata[0]['config'][key] != metadata[1]['config'][key]:
                raise ValueError('Smoothing sensitivity requires identical panel counts')
        allowed = {'free_surface_smoothing_enabled'}
    if matched_cut_rule:
        configs = [m['config'] for m in metadata]
        if any(c['jet_cut_threshold_m'] is not None for c in configs) or not np.isclose(
            configs[0]['jet_cut_distance_fraction']/configs[0]['body_panels_per_side'],
            configs[1]['jet_cut_distance_fraction']/configs[1]['body_panels_per_side'], rtol=1e-14, atol=0):
            raise ValueError('Matched cut-distance rule required')
        allowed.add('jet_cut_distance_fraction')
    for key, value in metadata[0]['config'].items():
        if key not in allowed and value != metadata[1]['config'][key]:
            raise ValueError('Configuration mismatch: ' + key)
    speed = metadata[0]['speed_mps']
    scale = np.array([contracts[0]['rho'] * speed**2, speed, speed])
    out.mkdir(parents=True, exist_ok=False)
    rows, hashes, locations = [], {}, []
    for i in contracts[0]['indices']:
        paths = [p/f'section_{i}.npz' for p in (coarse, fine)]
        for p in paths:
            hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        with np.load(paths[0], allow_pickle=False) as a, np.load(paths[1], allow_pickle=False) as b:
            for key in ('time_s', 'x_from_transom_m'):
                if not np.isclose(a[key], b[key], rtol=0, atol=1e-12):
                    raise ValueError('Section location mismatch')
            rms, maximum, coverage = compare(a, b)
            for name, location in zip(('pressure', 'velocity_y', 'velocity_z'), localize(a, b)):
                locations.append(dict(index=i, time_s=float(a['time_s']), component=name,
                    coarse_jet_count=jet_counts[0][i][0], fine_jet_count=jet_counts[1][i][0],
                    coarse_jet_increment=jet_counts[0][i][1], fine_jet_increment=jet_counts[1][i][1],
                    **location))
            row = dict(index=i, time_s=float(a['time_s']), coverage=coverage)
            for j, name in enumerate(('pressure', 'velocity_y', 'velocity_z')):
                row[name+'_rms_scaled'] = rms[j]/scale[j]
                row[name+'_max_scaled'] = maximum[j]/scale[j]
            rows.append(row)
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'comparison.csv', index=False)
    pd.DataFrame(locations).to_csv(out/'peak_locations.csv', index=False)
    summary = dict(count=len(rows), minimum_coverage=float(frame.coverage.min()), matched_cut_rule=matched_cut_rule,
        comparison_type='smoothing_sensitivity_not_mesh_convergence' if smoothing_sensitivity else 'spatial_diagnostic',
        maxima={c:float(frame[c].max()) for c in frame if c.endswith('_scaled')},
        pressure_scale='rho U^2 (not half dynamic pressure)', velocity_scale='U',
        measure='Exact constant-panel horizontal overlap; contact nonoverlap excluded',
        physical_acceptance='NOT_PASSED', hashes=hashes)
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k != 'hashes'}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coarse', type=Path, required=True)
    p.add_argument('--fine', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--matched-cut-rule', action='store_true')
    p.add_argument('--smoothing-sensitivity', action='store_true')
    args = p.parse_args()
    run(args.coarse, args.fine, args.out, args.matched_cut_rule, args.smoothing_sensitivity)
