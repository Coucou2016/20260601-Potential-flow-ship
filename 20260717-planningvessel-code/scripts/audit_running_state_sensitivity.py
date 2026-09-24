"""Screen prescribed versus calm-water-equilibrium running states.

The comparison is diagnostic only. It does not read experimental responses,
calibrate either state, or replace the frozen prescribed-state contract.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium, solve_equilibrium
from planing_seakeeping.linear_case import build_case_model, load_linear_case
from planing_seakeeping.longitudinal_response import solve_longitudinal_frequency_response


def run(config_path, out):
    raw, boat = load_linear_case(config_path)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    mesh = dict(station_count=29, body_panels_per_section=36, free_surface_inner_panels=18,
        free_surface_outer_panels=36, frequency_samples=9, frequency_sampling="case_frequencies",
        history_steps=64, history_quadrature_count=32, history_k_max=25.0)
    route = raw.get("hydrodynamics", {}).get("head_sea_excitation_formulation", "equivalent_radiation")
    cutoff = raw.get("hydrodynamics", {}).get("cutoff_quadrature", "nodal_mask")
    contract = dict(input_sha256=hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
        mesh=mesh, excitation_route=route, cutoff_quadrature=cutoff,
        response_reference_read=False, recorded_before_solving=True,
        scope="diagnostic calm-water state sensitivity; coarse screening mesh; not acceptance")
    (out / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    (out / "input_snapshot.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), *sorted((root / "planing_seakeeping").rglob("*.py"))]
    (out / "source_hashes.json").write_text(json.dumps({str(p.relative_to(root)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2), encoding="utf-8")
    rows, states = [], []
    for case in raw["cases"]:
        prescribed = make_prescribed_equilibrium(boat, case["speed_mps"], PrescribedRunningStateConfig(
            enabled=True, trim_deg=case["trim_deg"], lambda_w=case["lambda_w"]))
        automatic = solve_equilibrium(boat, case["speed_mps"])
        if not automatic.converged or not np.isfinite(automatic.residual).all():
            raise ValueError("Automatic calm-water equilibrium did not converge")
        for label, eq in (("prescribed", prescribed), ("automatic_calm_water", automatic)):
            state_case = dict(case, trim_deg=eq.trim_deg, lambda_w=eq.geometry.lambda_w)
            model, correction, hull, used_eq = build_case_model(boat, state_case, mesh,
                head_sea_excitation_formulation=route, cutoff_quadrature=cutoff)
            rao = solve_longitudinal_frequency_response(model)
            states.append(dict(case=case["id"], state=label, trim_deg=eq.trim_deg,
                lambda_w=eq.geometry.lambda_w, z_wl_m=eq.z_wl_m,
                residual_vertical=eq.residual[0], residual_pitch=eq.residual[1],
                converged=eq.converged, condition_max=float(rao.dynamic_condition_number.max())))
            for i, omega in enumerate(case["encounter_omega_rad_s"]):
                rows.append(dict(case=case["id"], state=label, index=i, omega=omega,
                    heave_rao=float(rao.heave_rao_m_per_m.iloc[i]),
                    pitch_slope_rao=float(rao.pitch_rao_rad_per_wave_slope.iloc[i])))
    pd.DataFrame(states).to_csv(out / "running_states.csv", index=False)
    response = pd.DataFrame(rows)
    response.to_csv(out / "response_comparison.csv", index=False)
    paired = response.pivot(index=["case", "index", "omega"], columns="state",
        values=["heave_rao", "pitch_slope_rao"]).reset_index()
    for metric in ("heave_rao", "pitch_slope_rao"):
        paired[(metric, "relative_change_auto_vs_prescribed")] = (
            paired[(metric, "automatic_calm_water")] - paired[(metric, "prescribed")]) / \
            paired[(metric, "prescribed")].abs().clip(lower=1e-12)
    paired.columns = ["_".join(str(x) for x in c if x) for c in paired.columns]
    paired.to_csv(out / "paired_state_sensitivity.csv", index=False)
    (out / "summary.json").write_text(json.dumps(dict(status="DIAGNOSTIC_ONLY",
        prescribed_state_retained=True, physical_validation="NOT_PASSED"), indent=2), encoding="utf-8")
    print(pd.DataFrame(states).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.config, args.out)
