"""Analytic derivative audit of the existing wet-chine Savitsky closure.

This checks implementation of that closure, not its experimental accuracy.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from planing_seakeeping.coefficients import _restoring_matrix
from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import generalized_calm_force, make_prescribed_equilibrium, zmax_ratio
from planing_seakeeping.linear_case import load_linear_case


def analytic_restoring(boat, eq):
    if boat.wetted_lengths_type != 1:
        raise ValueError("Analytic audit supports only wetted_lengths_type=1")
    b, tau, z = boat.beam_m, eq.trim_rad, eq.z_wl_m
    if tau <= np.radians(.05):
        raise ValueError("Trim clamp is not a differentiable interior point")
    lk = boat.lcg_m + boat.vcg_m / np.tan(tau) - z / np.sin(tau)
    xs = .5*b*np.tan(np.radians(boat.deadrise_deg)) / ((1+zmax_ratio(boat.deadrise_deg))*tau)
    if lk <= xs:
        raise ValueError("Wet-chine analytic branch requires positive chine length")
    lam = (lk-.5*xs)/b
    d_lk = np.array([-1/np.sin(tau), -boat.vcg_m/np.sin(tau)**2 + z*np.cos(tau)/np.sin(tau)**2])
    d_lam = (d_lk-np.array([0., -.5*xs/tau]))/b
    tau_deg = np.degrees(tau)
    fn2 = eq.speed_through_water_mps**2 / (boat.gravity_m_s2*b)
    bracket = .012*np.sqrt(lam)+.0055*lam**2.5/fn2
    cl0 = tau_deg**1.1*bracket
    d_cl0 = tau_deg**1.1*(.006/np.sqrt(lam)+.01375*lam**1.5/fn2)*d_lam
    d_cl0[1] += 1.1*tau_deg**.1*(180/np.pi)*bracket
    clb = cl0-.0065*boat.deadrise_deg*cl0**.6
    if clb <= 0:
        raise ValueError("Lift clamp is not an interior point")
    scale = .5*boat.rho_water_kg_m3*eq.speed_through_water_mps**2*b**2
    lift = scale*clb
    d_lift = scale*(1-.0039*boat.deadrise_deg*cl0**(-.4))*d_cl0
    k = 5.21*fn2
    e = k/lam**2+2.39
    cp = b*lam*(.75-1/e)
    d_cp = b*(.75-1/e-2*k/(lam**2*e**2))*d_lam
    arm = cp-boat.lcg_m
    d_moment = (arm*d_lift+lift*d_cp)/np.cos(tau)
    d_moment[1] += lift*arm*np.tan(tau)/np.cos(tau)
    return -np.vstack((d_lift, d_moment))


def run(config, out):
    import pandas as pd
    raw, boat = load_linear_case(config)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    contract = dict(input_sha256=hashlib.sha256(Path(config).read_bytes()).hexdigest(),
        perturbation_factors=[1e-4, 5e-5, 1e-5], relative_tolerance=1e-5,
        absolute_dimensionless_tolerance=1e-8,
        scope="derivatives of existing wet-chine closure, not independent physical validation")
    (out/"contract.json").write_text(json.dumps(contract, indent=2))
    root = Path(__file__).resolve().parents[1]
    files = [Path(__file__), root/"planing_seakeeping/equilibrium.py", root/"planing_seakeeping/coefficients.py"]
    (out/"source_hashes.json").write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2))
    rows, mean_rows = [], []
    weight = boat.mass_kg*boat.gravity_m_s2
    normalize = np.diag([1, 1/boat.length_m])
    def nondim(matrix):
        return normalize @ matrix @ normalize * boat.beam_m/weight
    for case in raw["cases"]:
        eq = make_prescribed_equilibrium(boat, case["speed_mps"], PrescribedRunningStateConfig(
            enabled=True, trim_deg=case["trim_deg"], lambda_w=case["lambda_w"]))
        def force(z, theta):
            return generalized_calm_force(boat, eq.speed_through_water_mps, eq.z_wl_m,
                                         eq.trim_rad, z, theta)[0]
        net = force(0,0)
        mean_rows.append(dict(case=case["id"], net_vertical_force_n=net[0], moment_nm=net[1],
            net_force_per_weight=net[0]/weight, moment_per_weight_length=net[1]/(weight*boat.length_m)))
        reference = nondim(analytic_restoring(boat, eq))
        candidates = {"production": nondim(_restoring_matrix(boat, eq))}
        for step in contract["perturbation_factors"]:
            h = step*boat.beam_m
            candidates[str(step)] = nondim(-np.column_stack(((force(h,0)-force(-h,0))/(2*h),
                                                            (force(0,step)-force(0,-step))/(2*step))))
        for name, value in candidates.items():
            for i in range(2):
                for j in range(2):
                    error = abs(value[i,j]-reference[i,j])
                    tolerance = 1e-8+1e-5*abs(reference[i,j])
                    rows.append(dict(case=case["id"], method=name, coefficient=f"C{[3,5][i]}{[3,5][j]}",
                        analytic=reference[i,j], numerical=value[i,j], error=error,
                        tolerance=tolerance, passed=bool(error<=tolerance)))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/"derivative_checks.csv", index=False)
    pd.DataFrame(mean_rows).to_csv(out/"mean_load_residuals.csv", index=False)
    result = dict(checks=len(frame), passed=int(frame.passed.sum()),
        max_tolerance_usage=float((frame.error/frame.tolerance).max()), physical_validation="NOT_PASSED")
    (out/"results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0 if frame.passed.all() else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.config, args.out))
