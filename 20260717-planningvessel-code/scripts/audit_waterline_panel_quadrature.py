"""Compare midpoint and exact straight-panel kernels on saved body geometry."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy.integrate import quad

from planing_seakeeping.kernels.linear_2p5d.formulation import (
    build_waterline_clipped_free_surface_geometry,
    _log_potential_between_raw, _log_normal_derivative_between_raw)
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import straight_log_integrals


def adjacent_pairs(body_y, free_count):
    return [('left',int(np.argmin(body_y)),free_count//2-1),
            ('right',int(np.argmax(body_y)),free_count//2)]


def run(saved, out):
    contract = json.loads((saved/'contract.json').read_text())
    snapshots = sorted(saved.glob('boundary_*.npz'))
    if len(snapshots) != 3:
        raise ValueError('Expected three frozen speed snapshots')
    out.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), Path('planing_seakeeping/kernels/linear_2p5d/panel_integrals.py'),
               saved/'contract.json', *snapshots]
    (out/'contract.json').write_text(json.dumps(dict(
        hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        free_panels=contract['free'], control_radius_beams=3.,
        reference='independent scipy adaptive quadrature of adjacent source panels',
        absolute_tolerance=1e-10, relative_tolerance=1e-10,
        scope='Kernel integration only; not complete diffraction verification'), indent=2))
    rows, references = [], []
    for path in snapshots:
        with np.load(path) as data:
            radius = max(6*np.max(np.abs(data['node_y'])), 1.25*np.max(data['node_z']), 1e-6)
            for i, x in enumerate(data['x']):
                body = SimpleNamespace(mid_y_m=data['y'][i], mid_z_down_m=data['z'][i])
                free = build_waterline_clipped_free_surface_geometry(-radius,radius,
                    np.max(np.abs(data['node_y'][i])),contract['free'])
                exact_p, exact_a = straight_log_integrals(body,free)
                midpoint_p = _log_potential_between_raw(body,free)
                midpoint_a = _log_normal_derivative_between_raw(body,free)
                for side, bi, sj in adjacent_pairs(body.mid_y_m,contract['free']):
                    for name, midpoint, exact in [('potential',midpoint_p,exact_p),('normal',midpoint_a,exact_a)]:
                        rows.append(dict(case=path.stem,station=i,x=x,side=side,kernel=name,
                            midpoint=midpoint[bi,sj],exact=exact[bi,sj],
                            relative_error=abs(midpoint[bi,sj]-exact[bi,sj])/max(abs(exact[bi,sj]),1e-15)))
                    if i in (0,len(data['x'])//2,len(data['x'])-1):
                        fy, fz = body.mid_y_m[bi], body.mid_z_down_m[bi]
                        sy, length = free.mid_y_m[sj], free.length_m[sj]
                        p = quad(lambda s: np.log(np.hypot(fy-sy-s,fz)), -length/2,length/2,
                                 epsabs=1e-12,epsrel=1e-12)[0]
                        a = quad(lambda s: fz/((fy-sy-s)**2+fz**2), -length/2,length/2,
                                 epsabs=1e-12,epsrel=1e-12)[0]
                        for name, value, reference in [('potential',exact_p[bi,sj],p),('normal',exact_a[bi,sj],a)]:
                            references.append(dict(case=path.stem,station=i,side=side,kernel=name,
                                absolute_error=abs(value-reference),passed=bool(np.isclose(value,reference,atol=1e-10,rtol=1e-10))))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'adjacent_kernel_errors.csv',index=False)
    checks = pd.DataFrame(references)
    checks.to_csv(out/'independent_quadrature.csv',index=False)
    stats = frame.groupby('kernel').relative_error.agg(['min','median','max'])
    stats.to_csv(out/'midpoint_error_summary.csv')
    result = dict(reference_checks=len(checks),reference_passed=int(checks.passed.sum()),
        maximum_reference_error=float(checks.absolute_error.max()),physical_acceptance='NOT_PASSED')
    (out/'results.json').write_text(json.dumps(result,indent=2))
    print(stats.to_string())
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--saved',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a = p.parse_args()
    run(a.saved,a.out)
