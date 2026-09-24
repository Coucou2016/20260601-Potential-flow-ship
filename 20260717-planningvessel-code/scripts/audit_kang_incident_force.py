"""Independent Gauss-volume identity for Kang incident pressure, not diffraction."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.polynomial.legendre import leggauss


def incident_force(k, *, order=48, length=3., beam=.3, draft=.1875,
                   origin=1.5, rho=1000., gravity=9.80665):
    """Raw A1 rows: minus upward force, pitch lever origin-x, unit elevation amplitude.

    Divergence theorem: upward wetted-pressure force = waterplane pressure
    integral minus k times submerged-volume pressure integral. No BEM geometry
    or production pressure helper is used here.
    """
    if (not np.isfinite([k, length, beam, draft, origin, rho, gravity]).all()
            or k < 0 or min(length, beam, draft, rho, gravity) <= 0
            or not isinstance(order, int) or order < 8):
        raise ValueError('Finite physical inputs and integer quadrature order >= 8 required')
    u, w = leggauss(order)
    x, wx = (u+1)*length/2, w*length/2
    d, wd = (u+1)*draft/2, w*draft/2
    X, Z = u[:, None], (d/draft)[None, :]
    a = (1-X**2)*(1+.2*X**2)
    b = (1-X**2)**4
    width = beam*((1-Z**2)*a + (Z**2-Z**10)*b)
    volume_column = np.sum(width*np.exp(-k*d)[None, :]*wd[None, :], axis=1)
    waterplane = beam*(1-u**2)*(1+.2*u**2)
    phase = np.exp(1j*k*(x-origin))
    density = -rho*gravity*phase*(waterplane-k*volume_column)
    # Separate analytic depth derivative gives the same pressure integral.
    width_depth = beam/draft*(-2*Z*a+(2*Z-10*Z**9)*b)
    direct = rho*gravity*phase*np.sum(width_depth*np.exp(-k*d)[None, :]*wd, axis=1)
    lever = np.stack((np.ones_like(x), origin-x), axis=1)
    return np.sum(density[:, None]*lever*wx[:, None], axis=0), np.sum(
        direct[:, None]*lever*wx[:, None], axis=0)


def run(out):
    root = Path(__file__).resolve().parents[1]
    source = root/'benchmarks/excitation_reference_candidates_20260924/sources/Kang2009.pdf'
    if hashlib.sha256(source.read_bytes()).hexdigest() != (
            '82c16b2b268679b86dfb0b6ec1fc4e7e24dd4e7e5dd517d3596fdc63eecc29e5'):
        raise ValueError('Kang source hash mismatch')
    paths = [root/'outputs'/f'kang_heave_{p}_20260924' for p in ('medium', 'fine')]
    files = [Path(__file__), source] + [p/name for p in paths for name in
        ('contract.json', 'fields_2.npz', 'fields_3.npz', 'fields_4.npz')]
    contracts = [json.loads((p/'contract.json').read_text()) for p in paths]
    for c in contracts:
        if any(c.get(key) != val for key, val in dict(length=3., beam=.3,
                draft=.1875, froude_length=.2, rho=1000., gravity=9.80665,
                frequencies=[2., 3., 4.]).items()):
            raise ValueError('Saved run physical inputs do not match independent audit')
    out.mkdir(parents=True, exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(
        scope='Incident pressure only; geometric midship moment; not experimental validation',
        normalization='Unit wave elevation amplitude, raw A1 generalized-force signs',
        orders=[24, 48], frozen_relative_tolerance=.005,
        hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), indent=2))
    rows = []
    for omega_nd in (2., 3., 4.):
        # Deep-water head-sea encounter: omega_e = omega_0 + U omega_0^2/g.
        omega_e = omega_nd*np.sqrt(9.80665/3)
        speed = .2*np.sqrt(9.80665*3)
        omega_0 = 2*omega_e/(1+np.sqrt(1+4*speed*omega_e/9.80665))
        k = omega_0**2/9.80665
        exact, derivative = incident_force(k)
        coarse, _ = incident_force(k, order=24)
        for p in paths:
            with np.load(p/f'fields_{omega_nd:g}.npz') as data:
                saved = data['incident']
            if saved.shape != (2,) or not np.isfinite(saved).all():
                raise ValueError('Invalid saved incident forces')
            for j, mode in enumerate(('heave', 'geometric_pitch')):
                rows.append(dict(grid=p.name, omega=omega_nd, mode=mode,
                    reference_real=exact[j].real, reference_imag=exact[j].imag,
                    computed_real=saved[j].real, computed_imag=saved[j].imag,
                    relative_error=abs(saved[j]-exact[j])/abs(exact[j]),
                    identity_error=abs(derivative[j]-exact[j])/abs(exact[j]),
                    quadrature_error=abs(coarse[j]-exact[j])/abs(exact[j])))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'comparison.csv', index=False)
    passed = bool((frame.relative_error <= .005).all()
        and (frame.identity_error < 1e-11).all() and (frame.quadrature_error < 1e-11).all())
    summary = dict(incident_only_pass=passed, stage_acceptance=False,
        max_relative_error=float(frame.relative_error.max()),
        max_identity_error=float(frame.identity_error.max()),
        max_quadrature_error=float(frame.quadrature_error.max()),
        limitations=['No diffraction validation', 'No experimental pitch origin assumed',
                    'Same analytic geometry, independent integration, not independent experiment'])
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    print(frame.to_string(index=False))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
