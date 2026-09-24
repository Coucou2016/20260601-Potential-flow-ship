"""Manufactured harmonic-field test of the production pressure x derivative.

No body solve, experiment, or fitted response is involved. Transverse field
gradients are analytic, so the corrected result is not yet a BEM implementation.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.kernels.linear_2p5d.formulation import (
    estimate_local_time_phase_body_potential_x_gradient,
)


def measure(count, moving=True):
    x = np.linspace(0, 2, count)
    eta = np.linspace(-.95, .95, 24)
    slope_y, slope_z = (.2, .1) if moving else (0., 0.)
    y = (1+slope_y*x[:,None])*eta
    z = (.3+slope_z*x[:,None])*abs(eta)
    ay, az = 1+.4j, -.3+.7j
    # Linear in y,z, independent of x: exact transverse Laplace solution.
    phi = ay*y+az*z
    omega, speed, rho = 2., 3., 1000.
    phase = np.exp(-1j*omega*x/speed)
    observed = estimate_local_time_phase_body_potential_x_gradient(x, phi*phase[:,None],
        omega_rad_s=omega, speed_mps=speed, phase_factor=phase).body_potential_x_gradient
    geometric_term = ay*slope_y*eta + az*slope_z*abs(eta)
    corrected = observed-geometric_term[None,:]
    exact_pressure = -rho*1j*omega*phi
    computed_pressure = -rho*(1j*omega*phi-speed*observed)
    return dict(stations=count, moving=moving,
        max_uncorrected_x_gradient=float(abs(observed).max()),
        max_analytic_geometry_corrected_x_gradient=float(abs(corrected).max()),
        pressure_relative_error=float(np.linalg.norm(computed_pressure-exact_pressure)/np.linalg.norm(exact_pressure)),
        corrected_pressure_relative_error=float(rho*speed*np.linalg.norm(corrected)/np.linalg.norm(exact_pressure)))


def run(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    contract = dict(stations=[33,65,129], panels=24, omega=2., speed=3., rho=1000.,
        exact_potential="(1+0.4i)*y+(-0.3+0.7i)*z, fixed-space phi_x=0",
        moving_geometry="y=(1+0.2x)*eta; z=(0.3+0.1x)*abs(eta)",
        relative_pressure_limit=.001, independent_of_experiments=True,
        scope="manufactured derivative/pressure verification, not diffraction benchmark")
    (out/"contract.json").write_text(json.dumps(contract, indent=2))
    root = Path(__file__).resolve().parents[1]
    sources=[Path(__file__),root/"planing_seakeeping/kernels/linear_2p5d/formulation.py"]
    (out/"source_hashes.json").write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2))
    frame=pd.DataFrame([measure(n,moving) for moving in (False,True) for n in contract["stations"]])
    frame.to_csv(out/"pressure_checks.csv",index=False)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    run(parser.parse_args().out)
