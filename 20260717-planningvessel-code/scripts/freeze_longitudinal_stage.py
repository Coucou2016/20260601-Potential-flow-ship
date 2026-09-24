"""Freeze response-blind Begovic inputs, without reading EFD response columns."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import platform

import pandas as pd


def freeze(out, excitation_formulation=None, refined=False, panel_route=None, grading_exponent=1.):
    from planing_seakeeping.linear_case import validate_discretization
    validate_discretization('midpoint' if panel_route is None else panel_route,grading_exponent)
    if (panel_route is not None or grading_exponent != 1.) and excitation_formulation is None:
        raise ValueError('Explicit discretization requires explicit excitation formulation')
    if excitation_formulation not in (None, "equivalent_radiation", "matched_domain_incident_diffraction"):
        raise ValueError("Unsupported excitation formulation")
    if refined and excitation_formulation != "matched_domain_incident_diffraction":
        raise ValueError("Refined protocol requires explicit matched_domain_incident_diffraction")
    root = Path(__file__).resolve().parents[1]
    source = root / "benchmarks/begovic2020"
    names = ["begovic2020_mono_hull.csv", "begovic2014_mono_calm_water_running_state.csv",
             "begovic2020_regular_wave_conditions.csv"]
    out = Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("Freeze requires a clean directory")
    out.mkdir(parents=True, exist_ok=True)
    hull, states, waves = [pd.read_csv(source / name) for name in names]
    h = hull.iloc[0]
    boat = dict(length_m=float(h.length_overall_m), beam_m=float(h.beam_m), deadrise_deg=float(h.deadrise_deg),
        mass_kg=float(h.mass_kg_from_weight), lcg_m=float(h.lcg_from_transom_m), vcg_m=float(h.vcg_m),
        pitch_radius_gyration_m=float(h.pitch_radius_gyration_m), rho_water_kg_m3=1000.0, gravity_m_s2=9.80665)
    config = {"model": "matched_bie_longitudinal_research", "boat": boat,
        "mesh": dict(station_count=15, body_panels_per_section=24, free_surface_inner_panels=12,
                     free_surface_outer_panels=24, frequency_samples=9),
        "provenance": {"source_hashes": {str(source / n): hashlib.sha256((source / n).read_bytes()).hexdigest() for n in names},
            "geometry": "parameterized monohedral mean wetted hull, not measured offsets",
            "attitude": "prescribed measured trim and transcribed mean wetted length; towing moment not predicted",
            "coordinate": "heave_up_pitch_bow_up_about_CG; speed_through_water; head_sea_180deg; SI",
            "frequency": "source omega0 + U*k; dispersion-consistent wavelength derived by solver"}, "cases": []}
    rows = []
    if excitation_formulation is not None:
        config["hydrodynamics"] = {"head_sea_excitation_formulation": excitation_formulation}
        if panel_route is not None:
            config['hydrodynamics']['panel_integration_route'] = panel_route
        if grading_exponent != 1.:
            config['hydrodynamics']['waterline_grading_exponent'] = grading_exponent
    if refined:
        config["mesh"] = dict(station_count=113, body_panels_per_section=72,
            free_surface_inner_panels=96, free_surface_outer_panels=120, frequency_samples=9,
            frequency_sampling="case_frequencies", history_steps=128,
            history_quadrature_count=64, history_k_max=25.0)
        config["hydrodynamics"]["cutoff_quadrature"] = "clipped_linear"
        config["provenance"]["numerical_protocol"] = (
            "Fullband 20260921 fine grid; direct case frequencies; frequency_samples unused in this mode")
    for s in states.itertuples(index=False):
        config["cases"].append({"id": f"fn{round(s.fn_b * 100)}", "speed_mps": s.speed_m_s,
            "trim_deg": s.running_trim_deg, "lambda_w": s.mean_wetted_length_m / h.beam_m,
            "encounter_omega_rad_s": (waves.wave_omega_rad_s + s.speed_m_s * waves.wave_number_rad_m).tolist(),
            "wave_amplitude_m": waves.wave_amplitude_m.tolist()})
        for w in waves.itertuples(index=False):
            eligible = w.wave_number_rad_m * w.wave_amplitude_m <= 0.055
            rows.append({"fn_b": s.fn_b, "case_code": w.case_code, "speed_mps": s.speed_m_s,
                "omega_e_rad_s": w.wave_omega_rad_s + s.speed_m_s * w.wave_number_rad_m,
                "wave_amplitude_m": w.wave_amplitude_m, "source_ka": w.wave_number_rad_m * w.wave_amplitude_m,
                "linear_eligible": eligible, "reason": "source_ka<=0.055" if eligible else "diagnostic_only_source_ka>0.055"})
    frame = pd.DataFrame(rows)
    if len(frame) != 24 or int(frame.linear_eligible.sum()) != 21:
        raise ValueError("Frozen contract requires 24 conditions, 21 eligible, 3 diagnostic")
    frame.to_csv(out / "conditions.csv", index=False)
    (out / "run.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    versions = {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "pandas", "matplotlib", "PyYAML", "pytest")}
    (out / "requirements-observed.txt").write_text("\n".join(f"{k}=={v}" for k, v in versions.items()) + "\n", encoding="utf-8")
    contract = {"schema": "longitudinal_stage_20260915_v1", "python": platform.python_version(),
        "environment_lock_scope": "observed direct runtime/test dependencies, not full transitive lock",
        "input_sha256": hashlib.sha256((out / "run.json").read_bytes()).hexdigest(),
        "conditions_sha256": hashlib.sha256((out / "conditions.csv").read_bytes()).hexdigest(),
        "motion_median_limit": 0.15, "motion_nrmse_limit": 0.20, "per_speed_required": True,
        "peak_frequency_limit": 0.10, "cg_acceleration_nrmse_limit": 0.25,
        "physical_validation": "NOT_PASSED", "blind_holdout": "NOT_YET_FROZEN",
        "response_files_read": False, "pending": ["excitation_reference_contract", "near_zero_absolute_tolerances", "full_band_grid_gate"]}
    (out / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    print(out / "run.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--excitation", choices=["equivalent_radiation", "matched_domain_incident_diffraction"])
    parser.add_argument("--refined", action="store_true")
    parser.add_argument('--panel-integration',choices=('midpoint','analytic_straight_midpoint_curved','reconstructed_symmetric'))
    parser.add_argument('--grading-exponent',type=float,default=1.)
    args = parser.parse_args()
    freeze(args.out, args.excitation, args.refined, args.panel_integration, args.grading_exponent)
