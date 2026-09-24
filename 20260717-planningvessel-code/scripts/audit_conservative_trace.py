"""Replay compatible tangential transport on saved radiation traces."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from planing_seakeeping.kernels.linear_2p5d.trace_transport import integrate_trace_transport


def run(saved, out):
    paths = sorted(saved.glob('boundary_*_radiation*.npz'))
    if len(paths) != 6:
        raise ValueError('Expected six saved radiation fields')
    out.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parents[1]/'planing_seakeeping/kernels/linear_2p5d/trace_transport.py'
    files = [Path(__file__), source, saved/'contract.json', *paths]
    (out/'contract.json').write_text(json.dumps(dict(
        conservation_tolerance=1e-12, smooth_error_limit=1e-3,
        smooth_refinement_ratio_minimum=3.8, counts=[20, 40, 80],
        scope='Reconstructed trace numerical verification, not a new pressure/response solution',
        hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), indent=2))
    rows = []
    for path in paths:
        with np.load(path) as data:
            x, y, phi = data['x'], data['y'], data['phi']
            widths = -data['measure'][:, :, 0]
            if np.any(widths <= 0) or y.shape[1] % 2:
                raise ValueError('Symmetric V trace with positive projected widths required')
            yx = np.gradient(y, x, axis=0, edge_order=2)
            average = np.zeros_like(phi)
            residuals, average_changes = [], []
            for k in range(len(x)):
                for start, stop in ((0, y.shape[1]//2), (y.shape[1]//2, y.shape[1])):
                    nodes = -y[k, start]-widths[k, start]/2+np.r_[0., np.cumsum(widths[k, start:stop])]
                    if not np.allclose((nodes[:-1]+nodes[1:])/2, -y[k, start:stop], atol=1e-12, rtol=1e-10):
                        raise ValueError('Projected cell geometry is inconsistent')
                    r = integrate_trace_transport(nodes, phi[k, start:stop], yx[k, start:stop])
                    average[k, start:stop] = r['potential_average']
                    scale = max(np.sum(abs(r['derivative_weight_integral']))+
                                np.sum(abs(r['potential_weight_derivative_integral']))+
                                np.sum(abs(r['flux_difference'])), 1e-15)
                    residuals.append(np.sum(abs(r['residual']))/scale)
                    average_changes.append(np.linalg.norm(r['potential_average']-phi[k, start:stop])/
                                           max(np.linalg.norm(phi[k, start:stop]), 1e-15))
            np.savez_compressed(out/(path.stem+'_averages.npz'), x=x, potential_average=average)
            rows.append(dict(field=path.stem, traces_checked=2*len(x),
                             max_relative_cell_conservation_error=max(residuals),
                             max_relative_average_change=max(average_changes)))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'trace_checks.csv', index=False)
    smooth = []
    for count in (20, 40, 80):
        nodes = np.linspace(0, 1, count+1)
        mid = (nodes[:-1]+nodes[1:])/2
        result = integrate_trace_transport(nodes, np.exp(mid), 1+.4*mid)
        value = result['derivative_weight_integral'].sum()
        smooth.append(dict(cells=count, reference=np.e-.6, computed=value.real,
                           absolute_error=abs(value-(np.e-.6))))
    error = [row['absolute_error'] for row in smooth]
    pd.DataFrame(smooth).to_csv(out/'manufactured_accuracy.csv', index=False)
    passed = bool(np.isfinite(frame.select_dtypes(include='number')).all().all()
        and (frame.max_relative_cell_conservation_error <= 1e-12).all()
        and error[-1]/(np.e-.6) <= 1e-3 and min(error[0]/error[1], error[1]/error[2]) >= 3.8)
    (out/'summary.json').write_text(json.dumps(dict(numerical_checks_passed=passed,
        physical_validation='NOT_PASSED', production_kernel_changed=False,
        warning='Cell averages must not be silently substituted for collocation midpoint potentials.'), indent=2))
    print(frame.to_string(index=False))
    print(pd.DataFrame(smooth).to_string(index=False))
    if not passed:
        raise RuntimeError('Conservative trace numerical checks failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.saved, args.out)
