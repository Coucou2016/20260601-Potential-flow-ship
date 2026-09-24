"""Independent quadrature audit for a fixed hard transom cutoff."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def clipped_piecewise_linear_integral(x, values, cutoff):
    """Integrate the piecewise-linear interpolant strictly above a fixed cutoff."""
    x, values = np.asarray(x, dtype=float), np.asarray(values)
    if x.ndim != 1 or len(x) < 2 or values.shape[0] != len(x):
        raise ValueError("Expected one-dimensional stations and matching leading value axis")
    if not np.isfinite(x).all() or not np.isfinite(values).all() or np.any(np.diff(x) <= 0):
        raise ValueError("Station coordinates must increase and all data must be finite")
    if not np.isfinite(cutoff):
        raise ValueError("Cutoff must be finite")
    if cutoff >= x[-1]:
        return np.zeros(values.shape[1:], dtype=values.dtype)
    if cutoff <= x[0]:
        return np.trapezoid(values, x, axis=0)
    right = int(np.searchsorted(x, cutoff, side="right"))
    fraction = (cutoff-x[right-1])/(x[right]-x[right-1])
    edge = values[right-1] + fraction*(values[right]-values[right-1])
    return np.trapezoid(np.concatenate((edge[None], values[right:]), axis=0),
                        np.concatenate(([cutoff], x[right:])), axis=0)


def run(source, out):
    out.mkdir(parents=True, exist_ok=False)
    contract = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), cutoff_m=.212,
        analytic_absolute_tolerance=1e-12, scope="quadrature only, same fixed physical cutoff",
        interpolation="linear on original stations; no new BEM solve; no experimental fitting")
    data = json.dumps(contract, indent=2).encode()
    (out/'contract.json').write_bytes(data)
    (out/'contract.sha256').write_text(hashlib.sha256(data).hexdigest())
    analytic = []
    c = contract['cutoff_m']
    for count in (15, 29, 57):
        x = np.linspace(0, 1.79, count)
        for slope in (0., 2+3j):
            values = 1-2j+slope*x
            reference = (1-2j)*(x[-1]-c)+slope*(x[-1]**2-c**2)/2
            exact = clipped_piecewise_linear_integral(x, values, c)
            old = np.trapezoid(values*(x>c), x)
            analytic.append(dict(stations=count, slope_real=complex(slope).real,
                slope_imag=complex(slope).imag, clipped_error=abs(exact-reference),
                masked_error=abs(old-reference), passed=bool(abs(exact-reference)<=1e-12)))
    pd.DataFrame(analytic).to_csv(out/'analytic_checks.csv', index=False)
    frame = pd.read_csv(source)
    rows=[]
    for (case, component), group in frame.groupby(['case','component']):
        x=group.x_m.to_numpy()
        for mode in ('F3','M5'):
            values=group[mode+'_density_real'].to_numpy()+1j*group[mode+'_density_imag'].to_numpy()
            old=np.trapezoid(values*(x>c),x)
            exact=clipped_piecewise_linear_integral(x,values,c)
            rows.append(dict(case=case,component=component,mode=mode,
                masked_real=old.real,masked_imag=old.imag,clipped_real=exact.real,clipped_imag=exact.imag,
                complex_relative_difference=abs(exact-old)/max(abs(exact),1e-30)))
    pd.DataFrame(rows).to_csv(out/'load_differences.csv',index=False)
    result=dict(analytic_passed=all(r['passed'] for r in analytic),analytic_checks=len(analytic),
        physical_cutoff_validated=False,production_changed=False,
        source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    print(pd.DataFrame(rows).query('component == "total"').to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.source,a.out)
