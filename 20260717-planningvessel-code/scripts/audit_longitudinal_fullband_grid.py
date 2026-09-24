"""Frozen three-grid audit of every requested frequency, without experimental responses."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.planing_frequency_correction import compute_matched_bie_frequency_correction
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


def run(config_path, out, cutoff_quadrature="nodal_mask", selected_case=None, refined=False,
        integration_route='midpoint', grading_exponent=1.):
    if not np.isfinite(grading_exponent) or not 1. <= grading_exponent <= 2.:
        raise ValueError('Grading exponent must be finite and between 1 and 2')
    with panel_integration_route(integration_route):
        return _run(config_path, out, cutoff_quadrature, selected_case, refined, integration_route, grading_exponent)


def _run(config_path, out, cutoff_quadrature, selected_case, refined, integration_route, grading_exponent):
    raw, boat = load_linear_case(config_path)
    if selected_case is not None:
        cases = [c for c in raw["cases"] if c["id"] == selected_case]
        if len(cases) != 1:
            raise ValueError("Expected one existing selected case")
        raw["cases"] = [dict(cases[0], encounter_omega_rad_s=[cases[0]["encounter_omega_rad_s"][i] for i in (0,7)])]
    out.mkdir(parents=True, exist_ok=False)
    grids = [dict(station_count=n, body_panels_per_section=b,
                  free_surface_inner_panels=f, free_surface_outer_panels=2*f)
             for n, b, f in ((15, 24, 12), (29, 36, 18), (57, 48, 24))]
    if refined:
        if selected_case is not None or cutoff_quadrature != "clipped_linear":
            raise ValueError("Refined acceptance requires full cases and clipped_linear")
        grids = [dict(station_count=n, body_panels_per_section=b,
                      free_surface_inner_panels=f, free_surface_outer_panels=c)
                 for n,b,f,c in ((57,48,48,72),(85,60,72,96),(113,72,96,120))]
    contract = dict(input_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(), grids=grids,
                    panel_integration_route=integration_route, waterline_grading_exponent=grading_exponent,
                    diffraction_pressure_route='existing_eq31_index_gradient_without_geometry_chain_correction',
                    frequencies={c["id"]: c["encounter_omega_rad_s"] for c in raw["cases"]},
                    relative_limit=0.05, dimensionless_absolute_limit=0.001,
                    near_zero_dimensionless_threshold=0.02,
                    normalization="A=rho*L*B^2 times L^(i+j); B=A*sqrt(g/L); F=rho*g*L*B times L^i; i,j=0,1",
                    acceptance="fine two grids, each frequency and each component; absolute limit only near zero",
                    scope="coupled station and panel refinement; history spectral quadrature/domain held fixed",
                    limitation="not independent history-quadrature or domain convergence")
    contract["history_steps"] = 128 if refined else 64
    contract["history_quadrature_counts_by_grid"] = [32,48,64] if refined else [32,32,32]
    contract["refined_full_case_protocol"] = refined
    contract["cutoff_quadrature"] = cutoff_quadrature
    contract["selected_case_endpoint_diagnostic"] = selected_case
    contract["history_quadrature_count"] = 32
    contract["history_k_max"] = 25.0
    if refined:
        contract.pop("history_quadrature_count")
        contract["scope"] = "joint station, boundary panel, and history spectral quadrature refinement"
        contract["limitation"] = "not independent spectral-cutoff or control-domain convergence"
    data = json.dumps(contract, indent=2).encode()
    (out / "contract.json").write_bytes(data)
    (out / "contract.sha256").write_text(hashlib.sha256(data).hexdigest())
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), root/"planing_seakeeping/planing_frequency_correction.py",
               root/"planing_seakeeping/quadrature.py", root/"planing_seakeeping/kernels/linear_2p5d/formulation.py"]
    sources += [root/f'planing_seakeeping/kernels/linear_2p5d/{name}.py' for name in
                ('panel_integrals','reconstructed_operators','reconstructed_history','arc_integrals')]
    (out/"source_hashes.json").write_text(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sources},indent=2))
    all_rows = []
    L, B, rho, g = boat.length_m, boat.beam_m, boat.rho_water_kg_m3, boat.gravity_m_s2
    scales = {"A":rho*L*B**2, "B":rho*L*B**2*np.sqrt(g/L), "F":rho*g*L*B}
    for level, mesh in enumerate(grids):
        for case in raw["cases"]:
            eq = make_prescribed_equilibrium(boat, case["speed_mps"], PrescribedRunningStateConfig(
                enabled=True, trim_deg=case["trim_deg"], lambda_w=case["lambda_w"]))
            omega = np.asarray(case["encounter_omega_rad_s"])
            correction = compute_matched_bie_frequency_correction(boat, eq, omega,
                high_frequency_reference_rad_s=1.8*omega.max(), **mesh,
                restoring_matrix=compute_hydro_matrices(boat, eq).restoring,
                history_steps=contract["history_steps"],
                history_quadrature_count=contract["history_quadrature_counts_by_grid"][level],
                history_k_max=contract["history_k_max"],
                waterline_grading_exponent=grading_exponent,
                cutoff_quadrature=cutoff_quadrature,
                transom_force_cutoff_length_beams=0.5,
                head_sea_excitation_formulation="matched_domain_incident_diffraction")
            for frequency in omega:
                index = int(np.flatnonzero(np.isclose(correction.sample_omega_rad_s, frequency, rtol=1e-12))[0])
                for name, array in (("A", correction.raw_added_mass), ("B", correction.raw_radiation_damping)):
                    for i in range(2):
                        for j in range(2):
                            value = complex(array[index, i, j]) / (scales[name]*L**(i+j))
                            all_rows.append(dict(level=level, case=case["id"], omega=frequency,
                                component=f"{name}{[3,5][i]}{[3,5][j]}", real=value.real, imag=value.imag))
                excitation = correction.excitation_components["matched_domain_incident_plus_diffraction"]
                for i in range(2):
                    value = excitation[index, i] / (scales["F"]*L**i)
                    all_rows.append(dict(level=level, case=case["id"], omega=frequency,
                        component=f"F{[3,5][i]}", real=value.real, imag=value.imag))
            pd.DataFrame(all_rows).to_csv(out / "dimensionless_coefficients.csv", index=False)
            print(f"grid {level+1}/3 {case['id']} complete", flush=True)
    frame = pd.DataFrame(all_rows)
    pairs = frame[frame.level == 1].merge(frame[frame.level == 2], on=["case", "omega", "component"], suffixes=("_mid", "_fine"), validate="one_to_one")
    mid = pairs.real_mid + 1j*pairs.imag_mid
    fine = pairs.real_fine + 1j*pairs.imag_fine
    pairs["absolute_change"] = abs(mid-fine)
    pairs["tolerance"] = np.where(abs(fine) < contract["near_zero_dimensionless_threshold"],
        contract["dimensionless_absolute_limit"], contract["relative_limit"]*abs(fine))
    pairs["passed"] = pairs.absolute_change <= pairs.tolerance
    pairs.to_csv(out / "fine_grid_checks.csv", index=False)
    report = dict(passed=bool(pairs.passed.all()), checks=len(pairs), passed_count=int(pairs.passed.sum()),
                  full_stage_passed=False, history_quadrature_convergence="NOT_EVALUATED")
    (out / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cutoff-quadrature", choices=("nodal_mask", "clipped_linear"), default="nodal_mask")
    p.add_argument("--selected-case")
    p.add_argument("--refined",action="store_true")
    p.add_argument('--integration-route', choices=('midpoint','analytic_straight_midpoint_curved','reconstructed_symmetric'), default='midpoint')
    p.add_argument('--grading-exponent', type=float, default=1.)
    a = p.parse_args()
    raise SystemExit(run(a.config, a.out, a.cutoff_quadrature, a.selected_case, a.refined, a.integration_route, a.grading_exponent))
