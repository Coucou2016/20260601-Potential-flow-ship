"""Compare actual response inputs with the completed fine-grid numerical audit.

This verifies wiring, not experimental accuracy or independent diffraction.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def verify_routes(hydro, contract):
    from planing_seakeeping.linear_case import validate_discretization
    for record in (hydro,contract):
        validate_discretization(record.get('panel_integration_route','midpoint'),
                                record.get('waterline_grading_exponent',1.))
    allowed = {'head_sea_excitation_formulation','cutoff_quadrature',
               'panel_integration_route','waterline_grading_exponent'}
    if (set(hydro)-allowed or hydro.get('head_sea_excitation_formulation') != 'matched_domain_incident_diffraction'
            or hydro.get('cutoff_quadrature') != contract['cutoff_quadrature']
            or hydro.get('panel_integration_route','midpoint') != contract.get('panel_integration_route','midpoint')
            or hydro.get('waterline_grading_exponent',1.) != contract.get('waterline_grading_exponent',1.)):
        raise ValueError('Excitation, cutoff, panel integration or grading route mismatch')


def verify(run, grid_run):
    run, grid_run = Path(run), Path(grid_run)
    config = json.loads((run / "input_snapshot.json").read_text(encoding="utf-8"))
    contract = json.loads((grid_run / "contract.json").read_text())
    result = json.loads((grid_run / "results.json").read_text())
    if result.get("passed") is not True or result.get("checks") != 240:
        raise ValueError("Requires a complete passing 240-check grid audit")
    mesh = config["mesh"]
    expected = dict(contract["grids"][-1], history_steps=contract["history_steps"],
        history_quadrature_count=contract["history_quadrature_counts_by_grid"][-1],
        history_k_max=contract["history_k_max"], frequency_sampling="case_frequencies")
    if any(mesh.get(k) != v for k, v in expected.items()):
        raise ValueError("Run mesh does not match audited fine grid")
    verify_routes(config['hydrodynamics'],contract)
    reference = pd.read_csv(grid_run / "dimensionless_coefficients.csv")
    reference = reference[reference.level == 2].copy()
    if len(reference) != 240 or reference.duplicated(["case", "omega", "component"]).any():
        raise ValueError("Incomplete or duplicate fine-grid records")
    boat = config["boat"]
    rho, length, beam, gravity = [boat[k] for k in
        ("rho_water_kg_m3", "length_m", "beam_m", "gravity_m_s2")]
    scales = {"A": rho*length*beam**2, "B": rho*length*beam**2*np.sqrt(gravity/length),
              "F": rho*gravity*length*beam}
    rows = []
    if {c["id"] for c in config["cases"]} != set(reference.case):
        raise ValueError("Case coverage mismatch")
    for case in config["cases"]:
        matrices = pd.read_csv(run / case["id"] / "matrices.csv")
        force = pd.read_csv(run / case["id"] / "excitation.csv")
        frequencies = np.asarray(case["encounter_omega_rad_s"])
        if len(matrices) != 32 or len(force) != 8:
            raise ValueError("Incomplete response matrices or excitation")
        for item in reference[reference.case == case["id"]].itertuples():
            matches = np.flatnonzero(np.isclose(frequencies, item.omega, rtol=1e-10, atol=1e-12))
            if len(matches) != 1:
                raise ValueError("Frequency is missing or ambiguous")
            index = int(matches[0])
            if item.component[0] in ("A", "B"):
                i, j = int(item.component[1]), int(item.component[2])
                selected = matrices[(matrices.frequency_index == index) & (matrices.i == i) & (matrices.j == j)]
                if len(selected) != 1 or not np.isclose(selected.iloc[0].omega_e_rad_s, item.omega, rtol=1e-10):
                    raise ValueError("Matrix row mismatch")
                value = float(selected.iloc[0][item.component[0]]) / (
                    scales[item.component[0]] * length**((i-3)//2 + (j-3)//2))
            else:
                selected = force.iloc[index]
                if not np.isclose(selected.omega_e_rad_s, item.omega, rtol=1e-10):
                    raise ValueError("Excitation row mismatch")
                name = "F3" if item.component == "F3" else "M5"
                value = complex(selected[name+"_real"], selected[name+"_imag"]) / (
                    scales["F"] * (length if name == "M5" else 1))
            target = complex(item.real, item.imag)
            difference = abs(value-target)
            tolerance = 1e-10 + 1e-8*abs(target)
            rows.append(dict(case=case["id"], omega=item.omega, component=item.component,
                absolute_difference=difference, tolerance=tolerance,
                passed=bool(np.isfinite(difference) and difference <= tolerance)))
    frame = pd.DataFrame(rows)
    destination = run / "kernel_connection"
    destination.mkdir(exist_ok=False)
    frame.to_csv(destination / "checks.csv", index=False)
    summary = dict(checks=len(frame), passed_count=int(frame.passed.sum()),
        passed=bool(len(frame) == 240 and frame.passed.all()),
        maximum_absolute_difference=float(frame.absolute_difference.max()),
        scope="response A/B and complex excitation equal numerical-audit fine grid; not physical validation")
    (destination / "result.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--grid-run", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(verify(args.run, args.grid_run))
