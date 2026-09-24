"""Reference-blind, prescribed-state longitudinal research run.

This connects the existing matched kernel, not a newly validated physical model.
Experimental response files are deliberately absent from this module's inputs.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
import scipy
import yaml

from .coefficients import compute_hydro_matrices
from .config import BoatConfig, PrescribedRunningStateConfig
from .equilibrium import make_prescribed_equilibrium
from .longitudinal_response import (
    build_faltinsen_planing_model, solve_longitudinal_frequency_response, frequency_time_consistency,
)
from .planing_frequency_correction import (
    apply_frequency_correction, build_planing_wetted_station_hull,
    compute_matched_bie_frequency_correction, head_sea_wavenumber_from_encounter_frequency,
)
from .kernels.linear_2p5d.panel_integrals import panel_integration_route

MODEL = "matched_bie_longitudinal_research"
EXCITATION_ROUTES = {"equivalent_radiation", "matched_domain_incident_diffraction"}
PANEL_ROUTES = {"midpoint", "analytic_straight_midpoint_curved", "reconstructed_symmetric"}


def validate_discretization(route, grading):
    if not isinstance(route, str) or route not in PANEL_ROUTES:
        raise ValueError('Unsupported panel integration route')
    if type(grading) not in (int,float) or not np.isfinite(grading) or not 1. <= grading <= 2.:
        raise ValueError('waterline_grading_exponent must be a number between 1 and 2')


def _keys(data, expected, name):
    if not isinstance(data, dict) or set(data) != set(expected):
        raise ValueError(f"{name} requires exactly these fields: {sorted(expected)}")


def load_linear_case(path):
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {"model", "boat", "cases", "mesh", "provenance"}
    if isinstance(raw, dict) and "hydrodynamics" in raw:
        expected.add("hydrodynamics")
    _keys(raw, expected, "linear case")
    if "hydrodynamics" in raw:
        hydro_keys = {"head_sea_excitation_formulation"}
        if isinstance(raw["hydrodynamics"], dict) and "cutoff_quadrature" in raw["hydrodynamics"]:
            hydro_keys.add("cutoff_quadrature")
        if isinstance(raw["hydrodynamics"], dict):
            hydro_keys |= set(raw['hydrodynamics']) & {'panel_integration_route','waterline_grading_exponent'}
        _keys(raw["hydrodynamics"], hydro_keys, "hydrodynamics")
        route = raw["hydrodynamics"]["head_sea_excitation_formulation"]
        if not isinstance(route, str) or route not in EXCITATION_ROUTES:
            raise ValueError("Unsupported head-sea excitation formulation")
        quadrature = raw["hydrodynamics"].get("cutoff_quadrature", "nodal_mask")
        if not isinstance(quadrature, str) or quadrature not in {"nodal_mask", "clipped_linear"}:
            raise ValueError("Unsupported cutoff quadrature")
        if quadrature == "clipped_linear" and route != "matched_domain_incident_diffraction":
            raise ValueError("clipped_linear requires direct matched excitation")
        validate_discretization(raw['hydrodynamics'].get('panel_integration_route','midpoint'),
                                raw['hydrodynamics'].get('waterline_grading_exponent',1.))
    if raw["model"] != MODEL:
        raise ValueError("Unsupported model")
    required = {"length_m", "beam_m", "deadrise_deg", "mass_kg", "lcg_m", "vcg_m",
                "pitch_radius_gyration_m", "rho_water_kg_m3", "gravity_m_s2"}
    _keys(raw["boat"], required, "boat")
    if any(not np.isfinite(v) or v <= 0 for v in raw["boat"].values()):
        raise ValueError("Boat values must be finite and positive")
    boat = BoatConfig(**raw["boat"])
    if not 0 < boat.deadrise_deg < 90 or boat.lcg_m >= boat.length_m:
        raise ValueError("Invalid deadrise or CG position")
    mesh_keys = {"station_count", "body_panels_per_section", "free_surface_inner_panels",
                 "free_surface_outer_panels", "frequency_samples"}
    optional_mesh = {"frequency_sampling", "history_steps", "history_quadrature_count", "history_k_max"}
    if isinstance(raw["mesh"], dict):
        mesh_keys |= set(raw["mesh"]) & optional_mesh
    _keys(raw["mesh"], mesh_keys, "mesh")
    for key, value in raw["mesh"].items():
        if key == "frequency_sampling":
            if not isinstance(value, str) or value not in {"geometric", "case_frequencies"}:
                raise ValueError("Unsupported frequency_sampling")
            continue
        if key == "history_k_max":
            if type(value) not in (int, float) or not np.isfinite(value) or value <= 0:
                raise ValueError("history_k_max must be finite and positive")
            continue
        minimum = 9 if key == "station_count" else 3
        if key == "history_quadrature_count":
            minimum = 16
        if type(value) is not int or value < minimum:
            raise ValueError(f"{key} must be an integer >= {minimum}")
    if not isinstance(raw["provenance"], dict) or not raw["provenance"]:
        raise ValueError("Nonempty provenance required")
    hashes = raw["provenance"].get("source_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("provenance.source_hashes is required")
    for filename, expected in hashes.items():
        source = Path(filename)
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source hash mismatch or missing source: {filename}")
    if not isinstance(raw["cases"], list) or not raw["cases"]:
        raise ValueError("Nonempty cases required")
    identifiers = set()
    for case in raw["cases"]:
        _keys(case, {"id", "speed_mps", "trim_deg", "lambda_w", "encounter_omega_rad_s",
                     "wave_amplitude_m"}, "case")
        identifier = case["id"]
        if not isinstance(identifier, str) or not identifier.isalnum() or identifier in identifiers:
            raise ValueError("Case IDs must be unique alphanumeric strings")
        identifiers.add(identifier)
        for key in ("speed_mps", "trim_deg", "lambda_w"):
            if not np.isfinite(case[key]) or case[key] <= 0:
                raise ValueError(f"{key} must be finite and positive")
        omega = np.asarray(case["encounter_omega_rad_s"], dtype=float)
        amplitude = np.asarray(case["wave_amplitude_m"], dtype=float)
        if omega.ndim != 1 or omega.size < 3 or amplitude.shape != omega.shape:
            raise ValueError("At least three frequencies with matching amplitudes required")
        if not np.isfinite(omega).all() or not np.isfinite(amplitude).all() or np.any(omega <= 0) or np.any(amplitude <= 0):
            raise ValueError("Frequencies and amplitudes must be finite and positive")
        if len(np.unique(omega)) != len(omega):
            raise ValueError("Duplicate frequencies")
    return raw, boat


def build_case_model(boat, case, mesh, *, head_sea_excitation_formulation="equivalent_radiation",
                     cutoff_quadrature="nodal_mask", panel_route="midpoint", waterline_grading_exponent=1.):
    validate_discretization(panel_route,waterline_grading_exponent)
    with panel_integration_route(panel_route):
        result = _build_case_model(boat,case,mesh,head_sea_excitation_formulation=head_sea_excitation_formulation,
            cutoff_quadrature=cutoff_quadrature,waterline_grading_exponent=waterline_grading_exponent)
    result[1].metadata.update(panel_integration_route=panel_route,
        panel_route_physical_acceptance='NOT_VALIDATED', waterline_grading_exponent=waterline_grading_exponent)
    return result


def _build_case_model(boat, case, mesh, *, head_sea_excitation_formulation="equivalent_radiation",
                     waterline_grading_exponent=1.,
                     cutoff_quadrature="nodal_mask"):
    if head_sea_excitation_formulation not in EXCITATION_ROUTES:
        raise ValueError("Unsupported head-sea excitation formulation")
    eq = make_prescribed_equilibrium(boat, case["speed_mps"], PrescribedRunningStateConfig(
        enabled=True, trim_deg=case["trim_deg"], lambda_w=case["lambda_w"]))
    # This also checks that the prescribed wetted keel lies within the real length.
    hull = build_planing_wetted_station_hull(boat, eq, station_count=mesh["station_count"])
    k, _ = head_sea_wavenumber_from_encounter_frequency(
        np.asarray(case["encounter_omega_rad_s"]), case["speed_mps"], boat.gravity_m_s2)
    base = build_faltinsen_planing_model(
        boat, eq, compute_hydro_matrices(boat, eq), 2 * np.pi / k,
        np.asarray(case["wave_amplitude_m"]), point_x_forward_m=boat.length_m - boat.lcg_m,
        phase_length_m=case["lambda_w"] * boat.beam_m)
    omega = base.hydrodynamics.solver_omega_rad_s
    sampling = mesh.get("frequency_sampling", "geometric")
    sample = np.unique(omega) if sampling == "case_frequencies" else np.geomspace(
        omega.min(), omega.max(), mesh["frequency_samples"])
    correction = compute_matched_bie_frequency_correction(
        boat, eq, sample, high_frequency_reference_rad_s=1.8 * omega.max(),
        **{k: v for k, v in mesh.items() if k not in {"frequency_samples", "frequency_sampling"}},
        restoring_matrix=base.restoring[0], transom_force_cutoff_length_beams=0.5,
        head_sea_excitation_formulation=head_sea_excitation_formulation,
        waterline_grading_exponent=waterline_grading_exponent,
        cutoff_quadrature=cutoff_quadrature)
    model = apply_frequency_correction(base, correction, application_mode="replace_with_matched_bie",
                                       use_phase_resolved_excitation=True)
    return model, correction, hull, eq


def steady_series(model, index, cycles=8, samples=96):
    """Exact harmonic reconstruction; not a free-running transient calculation."""
    omega = model.hydrodynamics.solver_omega_rad_s[index]
    amplitude = model.wave_amplitude_m[index]
    q = np.linalg.solve(model.dynamic_stiffness[index], model.excitation_per_wave_amplitude[index]) * amplitude
    time = np.arange(cycles * samples + 1) * (2 * np.pi / omega / samples)
    response = np.real(np.exp(1j * omega * time[:, None]) * q)
    acceleration = -omega**2 * response
    return pd.DataFrame({"time_s": time, "wave_elevation_m": amplitude * np.sin(omega * time),
        "surge_m": 0.0, "sway_m": 0.0, "heave_m": response[:, 0], "roll_rad": 0.0,
        "pitch_rad": response[:, 1], "yaw_rad": 0.0, "cg_accel_mps2": acceleration[:, 0],
        "bow_accel_mps2": acceleration[:, 0] + model.point_x_forward_m * acceleration[:, 1]})


def _json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
        default=lambda x: x.tolist() if isinstance(x, np.ndarray) else x.item(), allow_nan=False), encoding="utf-8")


def run_linear_case(config_path, out_dir):
    raw, boat = load_linear_case(config_path)
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a clean output directory; previous evidence will not be overwritten")
    out.mkdir(parents=True, exist_ok=True)
    _json(out / "input_snapshot.json", raw)
    source_root = Path(__file__).resolve().parent
    _json(out / "source_hashes.json", {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(source_root.rglob("*.py"))})
    _json(out / "environment.json", {"python": platform.python_version(), "numpy": np.__version__,
                                    "scipy": scipy.__version__})
    results = []
    excitation_route = raw.get("hydrodynamics", {}).get("head_sea_excitation_formulation", "equivalent_radiation")
    cutoff_quadrature = raw.get("hydrodynamics", {}).get("cutoff_quadrature", "nodal_mask")
    for case in raw["cases"]:
        directory = out / case["id"]
        directory.mkdir()
        model, correction, hull, eq = build_case_model(boat, case, raw["mesh"],
            head_sea_excitation_formulation=excitation_route, cutoff_quadrature=cutoff_quadrature,
            panel_route=raw.get('hydrodynamics',{}).get('panel_integration_route','midpoint'),
            waterline_grading_exponent=raw.get('hydrodynamics',{}).get('waterline_grading_exponent',1.))
        rao = solve_longitudinal_frequency_response(model)
        rao.to_csv(directory / "rao.csv", index=False)
        pd.DataFrame([asdict(s) for s in hull.stations]).to_csv(directory / "computed_wetted_stations.csv", index=False)
        rows = []
        balance_rows = []
        time_checks = []
        for n, omega in enumerate(model.hydrodynamics.solver_omega_rad_s):
            for i in range(2):
                for j in range(2):
                    rows.append({"frequency_index": n, "omega_e_rad_s": omega, "i": [3, 5][i], "j": [3, 5][j],
                        "A": model.hydrodynamics.added_mass[n, i, j], "B": model.hydrodynamics.radiation_damping[n, i, j],
                        "C": model.restoring[n, i, j], "M": model.rigid_mass[i, j]})
            steady_series(model, n).to_csv(directory / f"timeseries_{n:03d}.csv", index=False)
            q = np.linalg.solve(model.dynamic_stiffness[n], model.excitation_per_wave_amplitude[n])
            for name, operator in (("rigid_inertia", -omega**2 * model.rigid_mass),
                    ("added_inertia", -omega**2 * model.hydrodynamics.added_mass[n]),
                    ("radiation_damping", 1j * omega * model.hydrodynamics.radiation_damping[n]),
                    ("restoring", model.restoring[n])):
                value = operator @ q
                balance_rows.append({"frequency_index": n, "term": name, "F3_real": value[0].real,
                    "F3_imag": value[0].imag, "M5_real": value[1].real, "M5_imag": value[1].imag})
            try:
                check = frequency_time_consistency(model, n)
                passed = all(np.isfinite(v) for v in check.values()) and all(
                    check[key] <= (5.0 if "phase" in key else 0.05)
                    for key in check if "kinematic" not in key)
                time_checks.append({"frequency_index": n, "status": "PASS" if passed else "FAIL", **check})
            except (ValueError, RuntimeError, np.linalg.LinAlgError) as error:
                time_checks.append({"frequency_index": n, "status": "FAIL", "reason": str(error)})
        pd.DataFrame(rows).to_csv(directory / "matrices.csv", index=False)
        pd.DataFrame(balance_rows).to_csv(directory / "complex_force_balance.csv", index=False)
        pd.DataFrame(time_checks).to_csv(directory / "frequency_time_checks.csv", index=False)
        force = model.excitation_per_wave_amplitude
        pd.DataFrame({"omega_e_rad_s": model.hydrodynamics.solver_omega_rad_s, "F3_real": force[:, 0].real,
            "F3_imag": force[:, 0].imag, "M5_real": force[:, 1].real, "M5_imag": force[:, 1].imag}).to_csv(directory / "excitation.csv", index=False)
        _json(directory / "kernel_metadata.json", correction.metadata)
        for name, component in correction.excitation_components.items():
            pd.DataFrame({"omega_e_rad_s": correction.sample_omega_rad_s,
                "F3_real": component[:, 0].real, "F3_imag": component[:, 0].imag,
                "M5_real": component[:, 1].real, "M5_imag": component[:, 1].imag}).to_csv(directory / f"excitation_component_{name}.csv", index=False)
        amplitude = model.wave_amplitude_m
        excursion = np.maximum(rao.heave_rao_m_per_m.to_numpy(), rao.point_vertical_rao_m_per_m.to_numpy()) * amplitude
        results.append({"id": case["id"], "status": "NOT_VALIDATED", "equilibrium": "prescribed_not_predicted",
            "keel_wetted_length_m": eq.geometry.keel_wetted_length_m,
            "max_equation_residual": float(rao.equation_relative_residual.max()),
            "frequency_time_check": "PASS" if all(c["status"] == "PASS" for c in time_checks) else "FAIL",
            "large_motion_screen": bool(np.any(excursion > max(s.draft_m for s in hull.stations))),
            "stability": "NOT_EVALUATED_for_frequency_dependent_system"})
    status = {"software_run": "COMPLETE", "stage_acceptance": "NOT_PASSED", "production": False,
        "reference_response_read": False, "cases": results,
        "pending": ["full_band_grid_and_excitation_validation", "independent_experimental_accuracy", "frequency_dependent_stability"],
        "time_method": "linear_steady_harmonic_reconstruction_not_transient",
        "time_check_method": "single_frequency_frozen_matrices_IVP_with_exact_steady_initial_state_not_memory_model",
        "geometry": "parameterized_mean_wetted_contour_not_complete_measured_offsets",
        "dof_status": {"heave": "solved", "pitch": "solved", "surge": "prescribed_speed_constraint",
                       "sway": "head_sea_symmetry_constraint", "roll": "head_sea_symmetry_constraint", "yaw": "head_sea_symmetry_constraint"},
        "excitation_route": excitation_route,
        "cutoff_quadrature": cutoff_quadrature,
        "wave_reference": "eta_CG=amplitude*sin(omega_e*time); real(qhat*exp(i*omega_e*time))",
        "empirical_load_treatment": "0.5B hard transom cutoff; inherited recovery length; excitation=" + excitation_route}
    _json(out / "acceptance.json", status)
    (out / "run_report.md").write_text(
        "# Unified longitudinal research run\n\nSoftware completed; stage acceptance NOT PASSED.\n\n"
        "One matched-BIE candidate supplies matrices, complex excitation and steady time histories. "
        "Mean attitude is prescribed. Geometry is the computed wetted contour, not complete measured hull offsets. "
        "No experimental responses were read. Grid, excitation and experimental gates remain open. "
        "Zero constrained DOFs are not independent predictions. See acceptance.json and per-case CSV files.\n", encoding="utf-8")
    print(f"Research run complete: {out.resolve()}; stage acceptance NOT PASSED (exit 2)")
    return 2
