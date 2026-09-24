from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from scripts.aggregate_sun2007_forced_motion_acceptance import aggregate


ROOT = Path(__file__).resolve().parents[1]


def _scale(coefficient: str, beam: float, rho: float, gravity: float) -> float:
    power = 3 if coefficient.endswith("33") else 5 if coefficient.endswith("55") else 4
    value = rho * beam**power
    if coefficient.startswith("B"):
        value *= math.sqrt(gravity / beam)
    return value


def _write_source_run(directory: Path, sigma: float, reference: dict[tuple[float, str], float]) -> None:
    directory.mkdir()
    beam = 0.318
    rho = 1000.0
    gravity = 9.80665
    arguments = {
        "target_identifier": "sun2007_troesch_prismatic_planing_hull",
        "beam_m": beam,
        "rho_water_kg_m3": rho,
        "gravity_m_s2": gravity,
        "deadrise_deg": 20.0,
        "trim_deg": 4.0,
        "fn_b": 2.5,
        "mean_wetted_length_over_beam": 3.0,
        "chine_wetting_offset_over_beam": 1.6,
        "keel_wetted_length_over_beam": None,
        "lcg_over_beam": 1.47,
        "vcg_over_beam": 0.65,
        "mean_draft_over_beam": 0.266,
        "heave_amplitude_over_beam": 0.036,
        "pitch_amplitude_deg": 0.43,
        "sigmas": [sigma],
        "cycles": 2.0,
        "discard_cycles": 0.5,
        "retained_cycles": 1.5,
        "section_planes": 11,
        "bem_substeps_per_plane": 16,
        "ground_plane_handoff_mode": "fixed_earth_grid",
        "ground_plane_spacing_rule": "keel_over_nx",
        "body_panels": 12,
        "free_surface_panels": 15,
        "side_panels": 6,
        "bottom_panels": 18,
        "gauss_order": 8,
        "element_interpolation": "linear_node",
        "pressure_interpolation": "constant_panel",
        "symmetry_half_domain": True,
        "transom_correction": False,
        "transom_keel_reduction": False,
        "initial_leading_offset_beams": None,
        "knuckle_separation_model": "artificial_surface",
        "jet_cut": True,
        "jet_cut_distance_fraction": 0.25,
        "jet_cut_threshold_over_beam": None,
        "jet_cut_max_corrective_passes": 8,
        "free_surface_spacing_mode": "body_matched_geometric",
        "free_surface_remesh_updates_per_plane": 8,
        "free_surface_smoothing": True,
        "free_surface_smoothing_node_count": 7,
        "free_surface_smoothing_updates_per_plane": 8,
        "uniform_near_body_panels": 6,
        "restoring_mode": "external",
    }
    (directory / "run_input_snapshot.json").write_text(
        json.dumps({"arguments": arguments, "response_calibration_used": False}),
        encoding="utf-8",
    )
    (directory / "restoring_diagnostics.json").write_text(
        json.dumps({"source_sha256": "a" * 64}),
        encoding="utf-8",
    )
    (directory / "run_diagnostics.json").write_text(
        json.dumps(
            [
                {
                    "heave_max_potential_residual": 1e-12,
                    "heave_max_pressure_residual": 2e-12,
                    "pitch_max_potential_residual": 1e-12,
                    "pitch_max_pressure_residual": 2e-12,
                }
            ]
        ),
        encoding="utf-8",
    )
    rows = []
    omega = sigma * math.sqrt(gravity / beam)
    for coefficient in ("A33", "A35", "A53", "A55", "B33", "B35", "B53", "B55"):
        nondimensional = reference[(sigma, coefficient)]
        rows.append(
            {
                "component": "total",
                "sigma": sigma,
                "omega_rad_s": omega,
                "coefficient": coefficient,
                "value_dimensional": nondimensional * _scale(coefficient, beam, rho, gravity),
                "value_nondimensional": nondimensional,
                "harmonic_fit_residual_nrmse": 0.01,
                "response_calibration_used": False,
            }
        )
    with (directory / "identified_coefficients.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_aggregate_exact_source_runs_pass(tmp_path) -> None:
    benchmark = ROOT / "benchmarks" / "sun2007_troesch_forced_motion_coefficients.csv"
    with benchmark.open("r", encoding="utf-8-sig", newline="") as handle:
        reference = {
            (float(row["omega_sqrt_B_over_g"]), row["coefficient"]): float(
                row["value_nondimensional"]
            )
            for row in csv.DictReader(handle)
            if row["model_variant"] == "sun_2dt_without_stern_3d_correction"
        }
    run_dirs = []
    for sigma in (0.85, 1.13, 1.4, 1.7, 1.95):
        directory = tmp_path / f"sigma_{sigma}"
        _write_source_run(directory, sigma, reference)
        run_dirs.append(directory)

    acceptance = aggregate(
        run_dirs,
        output=tmp_path / "acceptance",
        benchmark=benchmark,
    )

    assert acceptance["passed"] is True
    assert acceptance["frequency_count"] == 5
    assert acceptance["coefficient_count"] == 8
    assert acceptance["benchmark_role"] == "same_model_NUM_reproduction_not_independent_EFD"
    assert acceptance["benchmark_series"] == "Sun_2007_Figs_7.13_7.14_NUM_open_markers"
    assert acceptance["response_calibration_used"] is False
    assert acceptance["restoring_offset_diagnostic_used_for_acceptance"] is False
    assert acceptance["restoring_offset_like_added_mass_coefficients"] == []
    assert acceptance["damping_load_center_diagnostic_used_for_acceptance"] is False
    assert math.isclose(acceptance["heave_damping_center_median_abs_error_over_beam"], 0.0)
    assert math.isclose(acceptance["pitch_damping_center_median_abs_error_over_beam"], 0.0)
    assert (tmp_path / "acceptance" / "coefficient_comparison.csv").exists()
    assert (tmp_path / "acceptance" / "restoring_offset_diagnostics.csv").exists()
    assert (tmp_path / "acceptance" / "restoring_offset_summary.csv").exists()
    assert (tmp_path / "acceptance" / "damping_load_center_diagnostics.csv").exists()
