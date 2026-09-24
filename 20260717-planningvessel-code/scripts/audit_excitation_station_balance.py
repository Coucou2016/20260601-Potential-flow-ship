"""Export direct-load stations and verify the independent change-of-origin law."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.planing_frequency_correction import build_planing_wetted_station_hull
from planing_seakeeping.schema import Linear2p5DProviderConfig
from planing_seakeeping.kernels.linear_2p5d.formulation import solve_station_hull_head_sea_excitation_matched_sweep


def response_density(raw):
    return np.asarray(raw, dtype=complex) * np.array([1j, -1j])


def origin_reference(force, shift, k):
    """Physical lever transport plus the changed CG wave-phase reference."""
    return np.exp(-1j * k * shift) * np.array([force[0], force[1] - shift * force[0]])


def run(config_path, out):
    raw, boat = load_linear_case(config_path)
    out.mkdir(parents=True, exist_ok=False)
    contract = dict(input_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
                    case_ids=[c["id"] for c in raw["cases"]], frequency_index=4,
                    reference_shift_beams=0.1, relative_limit=1e-8, absolute_limit=1e-8,
                    scope="station integration and moment-origin invariance; not physical diffraction validation",
                    reference="F'=exp(-ik*d)*F; M'=exp(-ik*d)*(M-d*F)",
                    transom_cutoff_beams=0.5)
    frozen = json.dumps(contract, indent=2).encode()
    (out / "contract.json").write_bytes(frozen)
    (out / "contract.sha256").write_text(hashlib.sha256(frozen).hexdigest())
    rows, checks = [], []
    mesh = raw["mesh"]
    config = Linear2p5DProviderConfig(formulation="matched_bie", hull_stations=mesh["station_count"],
        body_panels_per_section=mesh["body_panels_per_section"],
        free_surface_inner_panels=mesh["free_surface_inner_panels"],
        free_surface_outer_panels=mesh["free_surface_outer_panels"], control_surface_radius_beams=3.,
        include_steady_perturbation=True, include_end_terms=True)
    for case in raw["cases"]:
        eq = make_prescribed_equilibrium(boat, case["speed_mps"], PrescribedRunningStateConfig(
            enabled=True, trim_deg=case["trim_deg"], lambda_w=case["lambda_w"]))
        hull = build_planing_wetted_station_hull(boat, eq, station_count=mesh["station_count"])
        omega = case["encounter_omega_rad_s"][contract["frequency_index"]]
        shift = contract["reference_shift_beams"] * boat.beam_m
        results = [solve_station_hull_head_sea_excitation_matched_sweep(h, omega, case["speed_mps"],
            config=config, rho_water_kg_m3=boat.rho_water_kg_m3, gravity_m_s2=boat.gravity_m_s2,
            parametric_section_shape="hard_chine_v") for h in (hull, replace(hull, lcg_from_transom_m=hull.lcg_m + shift))]
        original, shifted = results
        x = np.asarray(original.x_m)
        weight = (x > contract["transom_cutoff_beams"] * boat.beam_m).astype(float)
        for component, field in (("incident", "froude_krylov_force_density_by_station"),
                                 ("diffraction", "diffraction_force_density_by_station"),
                                 ("total", "total_force_density_by_station")):
            density = response_density(getattr(original, field))
            moved = response_density(getattr(shifted, field))
            for cutoff, weights in (("uncut", np.ones_like(x)), ("cut", weight)):
                force = np.trapezoid(density * weights[:, None], x, axis=0)
                actual = np.trapezoid(moved * weights[:, None], x, axis=0)
                expected = origin_reference(force, shift, original.wavenumber_rad_m)
                for mode in range(2):
                    error = abs(actual[mode] - expected[mode])
                    tolerance = contract["absolute_limit"] + contract["relative_limit"] * abs(expected[mode])
                    checks.append(dict(case=case["id"], component=component, cutoff=cutoff, mode=[3, 5][mode],
                        absolute_error=error, tolerance=tolerance, passed=bool(error <= tolerance),
                        original_real=force[mode].real, original_imag=force[mode].imag,
                        shifted_real=actual[mode].real, shifted_imag=actual[mode].imag))
            for n, pos in enumerate(x):
                rows.append(dict(case=case["id"], omega_e_rad_s=omega, x_m=pos,
                    lever_forward_m=pos - hull.lcg_m, component=component, transom_weight=weight[n],
                    F3_density_real=density[n, 0].real, F3_density_imag=density[n, 0].imag,
                    M5_density_real=density[n, 1].real, M5_density_imag=density[n, 1].imag))
        print(f"{case['id']}: station/origin solves complete", flush=True)
    pd.DataFrame(rows).to_csv(out / "station_loads.csv", index=False)
    pd.DataFrame(checks).to_csv(out / "origin_checks.csv", index=False)
    result = dict(passed=all(c["passed"] for c in checks), check_count=len(checks),
                  passed_count=sum(c["passed"] for c in checks), diffraction_physical_validation="NOT_EVALUATED",
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.config, args.out))
