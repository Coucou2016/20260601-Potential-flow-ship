from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.config import BoatConfig, PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium, solve_equilibrium
from planing_seakeeping.longitudinal_response import (
    build_faltinsen_planing_model,
    circular_difference_deg,
    frequency_time_consistency,
    simulate_regular_wave_ivp,
    solve_longitudinal_frequency_response,
    wave_amplitude_linearity,
)
from planing_seakeeping.linearized_momentum_strip import (
    MomentumStripOptions,
    build_linearized_momentum_strip_model,
)


TABLE1_SHA256 = "e7566c993bda7778d5d2a44296215891a90a72b5071db96d3904a5d5463fbb97"
TABLE2_SHA256 = "ac0b21feb5641bfd0423c8219947373ff88448bdc995382714d99b5e7898b84c"
SOURCE_MANIFEST_SHA256 = "e9fadb755d9c813037870ad6026981af9cfc2dfe706c3cc47b31ab0b1219bd9c"
BEGOVIC_PDF_SHA256 = "6dc44decbf2df3f1f561d187d76cd0c30d58ab0bacdf7ee9e8097758b0ca6826"
BEGOVIC_MANIFEST_SHA256 = "2f44a8748792c92fabde66a597604bb5a8b8ac0fb1108d948ceecdb7ffd73048"
BEGOVIC_HULL_SHA256 = "12f1e7d707afe74804d696dadc24a29b6dd360facd5f2cab6094de4435cc9f9a"
BEGOVIC_CONDITIONS_SHA256 = "e6daa532857aff230b27144cbf2c28cd80122defd2ac05f02e84aed3cfbac672"
BEGOVIC_MOTION_SHA256 = "13df2dd6346f4930d101211b9bf839a0f891e2b418b4f1ec909a9d8b15c91a33"
BEGOVIC_AUDIT_SHA256 = "3c04800be89fcf60bb3cd31dd1a2098b12d5c68a8925b0b60130c6061053e910"
BEGOVIC_RUNNING_STATE_SHA256 = "078195aed68123a29e3bf135cb4dfebd7118f194ca6ecb2e0c5dd517d646626f"
BEGOVIC_RUNNING_STATE_SOURCE_SHA256 = "d089ae54458bc9b38bf9f38c05ede1ab1047779a062d1f4015ef7e39e2748eaa"
EXPECTED_FRIDSMA_ROWS = {"A": 5, "B": 6}
EXPECTED_BEGOVIC_ROWS = {1.67: 8, 2.26: 8, 2.82: 8}
EQUATION_RESIDUAL_LIMIT = 1.0e-8
TIME_AMPLITUDE_RELATIVE_ERROR_LIMIT = 0.05
TIME_PHASE_ERROR_LIMIT_DEG = 5.0
LINEARITY_RATIO_TOLERANCE = 0.05
KINEMATIC_RESIDUAL_LIMIT = 1.0e-8
MOTION_MEDIAN_RELATIVE_ERROR_LIMIT = 0.15
MOTION_NRMSE_LIMIT = 0.20
PEAK_FREQUENCY_RELATIVE_ERROR_LIMIT = 0.10
PHASE_MEDIAN_ERROR_LIMIT_DEG = 15.0
CG_ACCEL_NRMSE_LIMIT = 0.25
BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT = 0.055
MINIMUM_RESOLVED_BEGOVIC_PEAKS = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the locked regular-head-sea longitudinal Gate 2 acceptance.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/gate2_regular_head_sea_acceptance"),
        help="Output directory. Numerical gates and benchmark sources are locked.",
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _external_source_sha256(path: Path) -> str:
    """Hash external Unicode paths through native PowerShell on Windows."""

    if sys.platform != "win32":
        return _sha256(path)
    environment = os.environ.copy()
    environment["PLANING_SOURCE_PATH"] = str(path)
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-FileHash -Algorithm SHA256 -LiteralPath $env:PLANING_SOURCE_PATH).Hash.ToLowerInvariant()",
        ],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    value = completed.stdout.strip().lower()
    if completed.returncode != 0 or len(value) != 64:
        raise RuntimeError(f"Could not hash external source {path}: {completed.stderr.strip()}")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]

    def cell(value: Any) -> str:
        if isinstance(value, (float, np.floating)):
            rendered = f"{float(value):.8g}"
        else:
            rendered = str(value)
        return rendered.replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in frame.itertuples(index=False))
    return "\n".join(lines)


def _verify_sources(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, str]]:
    benchmark_dir = root / "benchmarks" / "fridsma"
    table1_path = benchmark_dir / "fridsma1969_table1_configurations.csv"
    table2_path = benchmark_dir / "fridsma1969_table2_regular_waves.csv"
    manifest_path = benchmark_dir / "fridsma1969_source_manifest.json"
    hashes = {
        "table1_sha256": _sha256(table1_path),
        "table2_sha256": _sha256(table2_path),
        "source_manifest_sha256": _sha256(manifest_path),
    }
    expected = {
        "table1_sha256": TABLE1_SHA256,
        "table2_sha256": TABLE2_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
    }
    if hashes != expected:
        raise RuntimeError(f"Approved Fridsma benchmark hash mismatch: expected={expected}, actual={hashes}")
    table1 = pd.read_csv(table1_path)
    table2 = pd.read_csv(table2_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if set(table1["configuration"].astype(str)) != set(EXPECTED_FRIDSMA_ROWS):
        raise RuntimeError("Fridsma Table 1 must contain exactly configurations A and B.")
    counts = table2.groupby("configuration").size().to_dict()
    if counts != EXPECTED_FRIDSMA_ROWS:
        raise RuntimeError(f"Fridsma Table 2 row counts changed: {counts}")
    if table2.duplicated(["configuration", "lambda_over_l"]).any():
        raise RuntimeError("Fridsma Table 2 contains duplicate configuration/wavelength keys.")
    required = [
        "heave_rao_m_per_m",
        "pitch_rao_rad_per_wave_slope",
        "cg_accel_g",
        "bow_accel_g",
    ]
    if table2[required].isna().any().any():
        raise RuntimeError("Fridsma Table 2 motion and acceleration values must be complete.")
    for source_kind in ("primary_source", "secondary_source"):
        source = manifest[source_kind]
        for path_key, hash_key in (("pdf_path", "pdf_sha256"), ("markdown_path", "markdown_sha256")):
            source_path = Path(source[path_key])
            if not source_path.exists() or _external_source_sha256(source_path) != source[hash_key]:
                raise RuntimeError(f"Source provenance check failed for {source_path}.")
    return table1, table2, manifest, hashes


def _verify_begovic_sources(
    root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, str]]:
    benchmark_dir = root / "benchmarks" / "begovic2020"
    paths = {
        "pdf_sha256": benchmark_dir / "source" / "jmse-08-00455-v2.pdf",
        "manifest_sha256": benchmark_dir / "begovic2020_source_manifest.json",
        "hull_sha256": benchmark_dir / "begovic2020_mono_hull.csv",
        "conditions_sha256": benchmark_dir / "begovic2020_regular_wave_conditions.csv",
        "motion_sha256": benchmark_dir / "begovic2020_mono_efd_motion_digitized.csv",
        "audit_sha256": benchmark_dir / "begovic2020_digitization_audit.csv",
        "running_state_sha256": benchmark_dir / "begovic2014_mono_calm_water_running_state.csv",
        "running_state_source_sha256": benchmark_dir
        / "source"
        / "Javaherian_Hamedani_2021_thesis.pdf",
    }
    hashes = {name: _sha256(path) for name, path in paths.items()}
    expected = {
        "pdf_sha256": BEGOVIC_PDF_SHA256,
        "manifest_sha256": BEGOVIC_MANIFEST_SHA256,
        "hull_sha256": BEGOVIC_HULL_SHA256,
        "conditions_sha256": BEGOVIC_CONDITIONS_SHA256,
        "motion_sha256": BEGOVIC_MOTION_SHA256,
        "audit_sha256": BEGOVIC_AUDIT_SHA256,
        "running_state_sha256": BEGOVIC_RUNNING_STATE_SHA256,
        "running_state_source_sha256": BEGOVIC_RUNNING_STATE_SOURCE_SHA256,
    }
    if hashes != expected:
        raise RuntimeError(f"Approved Begovic benchmark hash mismatch: expected={expected}, actual={hashes}")

    hull = pd.read_csv(paths["hull_sha256"])
    motion = pd.read_csv(paths["motion_sha256"])
    running_state = pd.read_csv(paths["running_state_sha256"])
    manifest = json.loads(paths["manifest_sha256"].read_text(encoding="utf-8"))
    if len(hull) != 1 or str(hull.iloc[0]["hull"]) != "monohedral":
        raise RuntimeError("Begovic hull table must contain exactly the monohedral model.")
    counts = {float(key): int(value) for key, value in motion.groupby("fn_b").size().to_dict().items()}
    if counts != EXPECTED_BEGOVIC_ROWS:
        raise RuntimeError(f"Begovic motion row counts changed: {counts}")
    if motion.duplicated(["fn_b", "case_code"]).any():
        raise RuntimeError("Begovic motion table contains duplicate speed/case keys.")
    state_counts = {
        float(key): int(value) for key, value in running_state.groupby("fn_b").size().to_dict().items()
    }
    if state_counts != {1.67: 1, 2.26: 1, 2.82: 1}:
        raise RuntimeError(f"Begovic running-state rows changed: {state_counts}")
    state_required = ["speed_m_s", "running_trim_deg", "mean_wetted_length_m"]
    state_numeric = running_state[state_required].to_numpy(dtype=float)
    if not np.isfinite(state_numeric).all() or np.any(state_numeric <= 0.0):
        raise RuntimeError("Begovic running trim and wetted length must be complete, finite and positive.")
    required = [
        "wave_omega_rad_s",
        "wave_number_rad_m",
        "wavelength_m",
        "wave_amplitude_m",
        "lambda_over_l",
        "heave_rao_m_per_m",
        "pitch_rao_rad_per_wave_slope",
    ]
    numeric = motion[required].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or np.any(numeric <= 0.0):
        raise RuntimeError("Begovic wave and response values must be complete, finite and positive.")
    return hull, motion, running_state, manifest, hashes


def _fridsma_boat_and_state(config: pd.Series) -> tuple[BoatConfig, PrescribedRunningStateConfig, float, float]:
    beam = 0.2286
    length = float(config["length_over_beam"]) * beam
    rho = 1000.0
    lcg_from_bow_fraction = float(config["lcg_from_bow_percent_l"]) / 100.0
    lcg_from_transom = length * (1.0 - lcg_from_bow_fraction)
    boat = BoatConfig(
        length_m=length,
        beam_m=beam,
        deadrise_deg=float(config["deadrise_deg"]),
        mass_kg=float(config["load_coefficient_mass_over_rho_b3"]) * rho * beam**3,
        lcg_m=lcg_from_transom,
        vcg_m=float(config["vcg_over_b"]) * beam,
        pitch_radius_gyration_m=float(config["pitch_gyradius_percent_l"]) * length / 100.0,
        rho_water_kg_m3=rho,
        gravity_m_s2=9.80665,
        wetted_lengths_type=1,
    )
    state = PrescribedRunningStateConfig(
        enabled=True,
        trim_deg=float(config["running_trim_deg"]),
        lambda_w=float(config["mean_wetted_length_over_b"]),
    )
    length_ft = length / 0.3048
    speed = float(config["speed_length_ratio_kn_sqrt_ft"]) * 0.5144444444444445 * math.sqrt(length_ft)
    bow_accelerometer_from_transom = 0.9 * length
    bow_x_forward = bow_accelerometer_from_transom - lcg_from_transom
    return boat, state, speed, bow_x_forward


def _run_fridsma_comparison(table1: pd.DataFrame, table2: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    comparison_parts: list[pd.DataFrame] = []
    matrix_rows: list[dict[str, Any]] = []
    for _, config in table1.iterrows():
        name = str(config["configuration"])
        reference = table2[table2["configuration"].eq(name)].copy().reset_index(drop=True)
        boat, state, speed, bow_x = _fridsma_boat_and_state(config)
        equilibrium = make_prescribed_equilibrium(boat, speed, state)
        matrices = compute_hydro_matrices(boat, equilibrium)
        wavelength = reference["lambda_over_l"].to_numpy(dtype=float) * boat.length_m
        amplitude = 0.5 * reference["wave_height_over_b"].to_numpy(dtype=float) * boat.beam_m
        reference = reference.rename(
            columns={
                "heave_rao_m_per_m": "reference_heave_rao_m_per_m",
                "pitch_rao_rad_per_wave_slope": "reference_pitch_rao_rad_per_wave_slope",
                "cg_accel_g": "reference_cg_accel_g",
                "bow_accel_g": "reference_bow_accel_g",
                "heave_phase_lag_deg": "reference_heave_phase_lag_deg",
                "pitch_phase_lead_deg": "reference_pitch_phase_lead_deg",
            }
        )
        model = build_faltinsen_planing_model(
            boat,
            equilibrium,
            matrices,
            wavelength,
            amplitude,
            point_x_forward_m=bow_x,
            phase_length_m=boat.length_m,
            metadata={
                "benchmark": "fridsma_1969_table2",
                "configuration": name,
                "running_state_source": "fridsma_table1_plus_sun_faltinsen_mean_wetted_length",
            },
        )
        computed = solve_longitudinal_frequency_response(model)
        result = pd.concat([reference, computed], axis=1)
        result["speed_mps"] = speed
        result["fn_b"] = equilibrium.fn_b
        result["running_trim_deg"] = equilibrium.trim_deg
        result["mean_wetted_length_over_b"] = equilibrium.geometry.lambda_w
        result["bow_x_forward_from_cg_m"] = bow_x
        result["reference_pitch_rao_rad_per_m"] = (
            result["reference_pitch_rao_rad_per_wave_slope"] * result["wavenumber_rad_m"]
        )
        result["heave_relative_error"] = np.abs(
            result["heave_rao_m_per_m"] - result["reference_heave_rao_m_per_m"]
        ) / result["reference_heave_rao_m_per_m"]
        result["pitch_relative_error"] = np.abs(
            result["pitch_rao_rad_per_wave_slope"] - result["reference_pitch_rao_rad_per_wave_slope"]
        ) / result["reference_pitch_rao_rad_per_wave_slope"]
        result["cg_accel_relative_error"] = np.abs(
            result["cg_accel_g"] - result["reference_cg_accel_g"]
        ) / result["reference_cg_accel_g"]
        result["bow_accel_relative_error"] = np.abs(
            result["point_accel_g"] - result["reference_bow_accel_g"]
        ) / result["reference_bow_accel_g"]
        result["heave_phase_circular_error_deg"] = np.abs(
            circular_difference_deg(
                result["fridsma_heave_phase_lag_deg"], result["reference_heave_phase_lag_deg"]
            )
        )
        result["pitch_phase_circular_error_deg"] = np.abs(
            circular_difference_deg(
                result["fridsma_pitch_phase_lead_deg"], result["reference_pitch_phase_lead_deg"]
            )
        )
        comparison_parts.append(result)
        for matrix_name, matrix in (
            ("rigid_mass", model.rigid_mass),
            ("added_mass", model.hydrodynamics.added_mass[0]),
            ("radiation_damping", model.hydrodynamics.radiation_damping[0]),
            ("restoring", model.restoring[0]),
        ):
            for row in range(2):
                for column in range(2):
                    matrix_rows.append(
                        {
                            "configuration": name,
                            "matrix": matrix_name,
                            "row_dof": ("heave", "pitch")[row],
                            "column_dof": ("heave", "pitch")[column],
                            "value": float(matrix[row, column]),
                            "matrix_contract": "heave_pitch_2x2_v1",
                        }
                    )
    return pd.concat(comparison_parts, ignore_index=True), pd.DataFrame(matrix_rows)


def _run_begovic_comparison(
    hull_table: pd.DataFrame,
    motion_table: pd.DataFrame,
    running_state_table: pd.DataFrame,
    *,
    provider_route: str = "faltinsen_ch9_reduced_order_planing",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if provider_route not in {
        "faltinsen_ch9_reduced_order_planing",
        "zarnick1978_linearized_momentum_strip",
        "zarnick1978_momentum_strip_savitsky_restoring",
        "zarnick1978_momentum_strip_faltinsen_excitation",
    }:
        raise ValueError(f"Unsupported Begovic provider route: {provider_route}")
    hull = hull_table.iloc[0]
    boat = BoatConfig(
        length_m=float(hull["length_overall_m"]),
        beam_m=float(hull["beam_m"]),
        deadrise_deg=float(hull["deadrise_deg"]),
        mass_kg=float(hull["mass_kg_from_weight"]),
        lcg_m=float(hull["lcg_from_transom_m"]),
        vcg_m=float(hull["vcg_m"]),
        pitch_radius_gyration_m=float(hull["pitch_radius_gyration_m"]),
        rho_water_kg_m3=1000.0,
        gravity_m_s2=9.80665,
        wetted_lengths_type=1,
    )
    point_x_forward = boat.length_m - boat.lcg_m
    comparisons: list[pd.DataFrame] = []
    dense_responses: list[pd.DataFrame] = []
    matrix_rows: list[dict[str, Any]] = []
    for fn_b, reference_source in motion_table.groupby("fn_b", sort=True):
        reference = reference_source.sort_values("lambda_over_l").reset_index(drop=True).copy()
        speed = float(reference["speed_m_s"].iloc[0])
        if not np.allclose(reference["speed_m_s"].to_numpy(dtype=float), speed, rtol=0.0, atol=1.0e-10):
            raise RuntimeError(f"Begovic Fn_B={fn_b} contains inconsistent speeds.")
        state_matches = running_state_table[np.isclose(running_state_table["fn_b"], float(fn_b))]
        if len(state_matches) != 1:
            raise RuntimeError(f"Begovic Fn_B={fn_b} must have exactly one prescribed running state.")
        measured_state = state_matches.iloc[0]
        if not math.isclose(float(measured_state["speed_m_s"]), speed, rel_tol=0.0, abs_tol=1.0e-10):
            raise RuntimeError(f"Begovic Fn_B={fn_b} running-state speed does not match wave-test speed.")
        measured_trim_deg = float(measured_state["running_trim_deg"])
        measured_mean_wetted_length_m = float(measured_state["mean_wetted_length_m"])
        measured_trim_rad = math.radians(measured_trim_deg)
        equilibrium = make_prescribed_equilibrium(
            boat,
            speed,
            PrescribedRunningStateConfig(
                enabled=True,
                trim_deg=measured_trim_deg,
                lambda_w=measured_mean_wetted_length_m / boat.beam_m,
            ),
        )
        if not math.isclose(
            equilibrium.geometry.lambda_w * boat.beam_m,
            measured_mean_wetted_length_m,
            rel_tol=0.0,
            abs_tol=1.0e-10,
        ):
            raise RuntimeError(f"Begovic Fn_B={fn_b} prescribed mean wetted length was not reconstructed.")
        reference = reference.rename(
            columns={
                "heave_rao_m_per_m": "reference_heave_rao_m_per_m",
                "pitch_rao_rad_per_wave_slope": "reference_pitch_rao_rad_per_wave_slope",
                "encounter_omega_rad_s": "source_encounter_omega_rad_s",
            }
        )
        common_metadata = {
            "benchmark": "begovic_2014_mono_efd_republished_2020",
            "configuration": f"FnB={float(fn_b):.2f}",
            "running_state_source": "begovic2014_measured_trim_plus_begovic2012_reported_mean_wetted_length",
        }

        def build_model(wavelength: np.ndarray, amplitude: np.ndarray | float, suffix: str):
            metadata = {**common_metadata, "benchmark": common_metadata["benchmark"] + suffix}
            if provider_route in {
                "zarnick1978_linearized_momentum_strip",
                "zarnick1978_momentum_strip_savitsky_restoring",
                "zarnick1978_momentum_strip_faltinsen_excitation",
            }:
                savitsky_restoring = None
                restoring_source = "zarnick1978_strip_load_derivative"
                if provider_route == "zarnick1978_momentum_strip_savitsky_restoring":
                    savitsky_restoring = compute_hydro_matrices(boat, equilibrium).restoring
                    restoring_source = "savitsky_faltinsen_generalized_calm_force_derivative"
                excitation_formulation = "zarnick1978_same_strip_wave_derivative"
                if provider_route == "zarnick1978_momentum_strip_faltinsen_excitation":
                    excitation_formulation = "faltinsen_eq9_110_to_9_117"
                return build_linearized_momentum_strip_model(
                    boat,
                    equilibrium,
                    wavelength,
                    amplitude,
                    point_x_forward_m=point_x_forward,
                    options=MomentumStripOptions(station_count=401),
                    quasi_static_restoring=savitsky_restoring,
                    quasi_static_restoring_source=restoring_source,
                    excitation_formulation=excitation_formulation,
                    excitation_phase_length_m=boat.length_m,
                    metadata=metadata,
                )
            matrices = compute_hydro_matrices(boat, equilibrium)
            return build_faltinsen_planing_model(
                boat,
                equilibrium,
                matrices,
                wavelength,
                amplitude,
                point_x_forward_m=point_x_forward,
                phase_length_m=boat.length_m,
                metadata=metadata,
            )

        model = build_model(
            reference["wavelength_m"].to_numpy(dtype=float),
            reference["wave_amplitude_m"].to_numpy(dtype=float),
            "",
        )
        computed = solve_longitudinal_frequency_response(model).drop(
            columns=["wave_amplitude_m", "wavelength_m"]
        )
        result = pd.concat([reference, computed], axis=1)
        result["configuration"] = f"FnB={float(fn_b):.2f}"
        result["fn_b"] = float(fn_b)
        result["speed_mps"] = speed
        result["running_trim_deg"] = equilibrium.trim_deg
        result["keel_wetted_length_m"] = equilibrium.geometry.keel_wetted_length_m
        result["reported_mean_wetted_length_m"] = measured_mean_wetted_length_m
        result["mean_wetted_length_over_b"] = equilibrium.geometry.lambda_w
        result["measured_sinkage_mm_diagnostic"] = float(measured_state["sinkage_mm"])
        result["running_state_source"] = common_metadata["running_state_source"]
        result["calm_force_residual_norm"] = float(np.linalg.norm(equilibrium.residual))
        result["candidate_provider_route"] = provider_route
        result["wave_steepness_ka"] = (
            result["wave_number_rad_m"] * result["wave_amplitude_m"]
        )
        result["linear_gate_eligible"] = (
            result["wave_steepness_ka"] <= BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT
        )
        result["linear_gate_reason"] = np.where(
            result["linear_gate_eligible"],
            f"kA<={BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT:g}",
            f"retained diagnostic: kA>{BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT:g}",
        )
        result["heave_relative_error"] = np.abs(
            result["heave_rao_m_per_m"] - result["reference_heave_rao_m_per_m"]
        ) / result["reference_heave_rao_m_per_m"]
        result["pitch_relative_error"] = np.abs(
            result["pitch_rao_rad_per_wave_slope"]
            - result["reference_pitch_rao_rad_per_wave_slope"]
        ) / result["reference_pitch_rao_rad_per_wave_slope"]
        comparisons.append(result)

        dense_lambda_over_l = np.linspace(
            float(reference["lambda_over_l"].min()),
            float(reference["lambda_over_l"].max()),
            241,
        )
        dense_model = build_model(
            dense_lambda_over_l * boat.length_m,
            0.01,
            "_dense_peak_scan",
        )
        dense = solve_longitudinal_frequency_response(dense_model)
        dense["configuration"] = f"FnB={float(fn_b):.2f}"
        dense["fn_b"] = float(fn_b)
        dense["speed_mps"] = speed
        dense["lambda_over_l"] = dense_lambda_over_l
        dense_responses.append(dense)

        for matrix_name, matrix in (
            ("rigid_mass", model.rigid_mass),
            ("added_mass", model.hydrodynamics.added_mass[0]),
            ("radiation_damping", model.hydrodynamics.radiation_damping[0]),
            ("restoring", model.restoring[0]),
        ):
            for row in range(2):
                for column in range(2):
                    matrix_rows.append(
                        {
                            "configuration": f"FnB={float(fn_b):.2f}",
                            "running_trim_deg": equilibrium.trim_deg,
                            "keel_wetted_length_m": equilibrium.geometry.keel_wetted_length_m,
                            "reported_mean_wetted_length_m": measured_mean_wetted_length_m,
                            "mean_wetted_length_over_b": equilibrium.geometry.lambda_w,
                            "matrix": matrix_name,
                            "row_dof": ("heave", "pitch")[row],
                            "column_dof": ("heave", "pitch")[column],
                            "value": float(matrix[row, column]),
                            "matrix_contract": "heave_pitch_2x2_v1",
                        }
                    )
    return (
        pd.concat(comparisons, ignore_index=True),
        pd.concat(dense_responses, ignore_index=True),
        pd.DataFrame(matrix_rows),
    )


def _nrmse(computed: pd.Series, reference: pd.Series) -> float:
    comp = computed.to_numpy(dtype=float)
    ref = reference.to_numpy(dtype=float)
    return float(np.linalg.norm(comp - ref) / max(np.linalg.norm(ref), 1.0e-12))


def _motion_metrics(comparison: pd.DataFrame, *, scope: str) -> pd.DataFrame:
    eligible = comparison[comparison["linear_gate_eligible"].astype(bool)].copy()
    metrics = []
    for metric, computed_column, reference_column in (
        ("heave_motion", "heave_rao_m_per_m", "reference_heave_rao_m_per_m"),
        (
            "pitch_motion",
            "pitch_rao_rad_per_wave_slope",
            "reference_pitch_rao_rad_per_wave_slope",
        ),
    ):
        relative_error = np.abs(eligible[computed_column] - eligible[reference_column]) / eligible[
            reference_column
        ]
        metrics.append(
            {
                "scope": scope,
                "metric": metric,
                "eligible_point_count": len(eligible),
                "median_relative_error": float(relative_error.median()),
                "nrmse": _nrmse(eligible[computed_column], eligible[reference_column]),
                "median_limit": MOTION_MEDIAN_RELATIVE_ERROR_LIMIT,
                "nrmse_limit": MOTION_NRMSE_LIMIT,
            }
        )
    frame = pd.DataFrame(metrics)
    frame["status"] = np.where(
        (frame["median_relative_error"] <= frame["median_limit"])
        & (frame["nrmse"] <= frame["nrmse_limit"]),
        "PASS",
        "FAIL",
    )
    return frame


def _quadratic_peak(
    frame: pd.DataFrame, *, x_column: str, y_column: str
) -> tuple[float, float, bool, int]:
    ordered = frame.sort_values(x_column).reset_index(drop=True)
    x = ordered[x_column].to_numpy(dtype=float)
    y = ordered[y_column].to_numpy(dtype=float)
    index = int(y.argmax())
    interior = 0 < index < len(ordered) - 1
    if not interior:
        return float(x[index]), float(y[index]), False, index
    local_x = x[index - 1 : index + 2]
    local_y = y[index - 1 : index + 2]
    coefficient = np.polyfit(local_x, local_y, 2)
    if coefficient[0] < 0.0:
        vertex = float(-coefficient[1] / (2.0 * coefficient[0]))
        if float(local_x.min()) <= vertex <= float(local_x.max()):
            return vertex, float(np.polyval(coefficient, vertex)), True, index
    return float(x[index]), float(y[index]), True, index


def _begovic_peak_metrics(comparison: pd.DataFrame, dense_response: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    eligible = comparison[comparison["linear_gate_eligible"].astype(bool)].copy()
    for configuration, reference_group in eligible.groupby("configuration"):
        dense_group = dense_response[dense_response["configuration"].eq(configuration)].copy()
        lower = float(reference_group["source_encounter_omega_rad_s"].min())
        upper = float(reference_group["source_encounter_omega_rad_s"].max())
        dense_group = dense_group[
            dense_group["omega_e_rad_s"].between(lower, upper, inclusive="both")
        ]
        for metric, computed_column, reference_column, uncertainty_column in (
            (
                "heave",
                "heave_rao_m_per_m",
                "reference_heave_rao_m_per_m",
                "heave_digitization_uncertainty_abs",
            ),
            (
                "pitch",
                "pitch_rao_rad_per_wave_slope",
                "reference_pitch_rao_rad_per_wave_slope",
                "pitch_digitization_uncertainty_abs",
            ),
        ):
            reference_ordered = reference_group.sort_values("source_encounter_omega_rad_s").reset_index(
                drop=True
            )
            reference_omega, reference_value, reference_interior, reference_index = _quadratic_peak(
                reference_ordered,
                x_column="source_encounter_omega_rad_s",
                y_column=reference_column,
            )
            computed_omega, computed_value, computed_interior, _ = _quadratic_peak(
                dense_group,
                x_column="omega_e_rad_s",
                y_column=computed_column,
            )
            if reference_interior:
                discrete_peak = float(reference_ordered.loc[reference_index, reference_column])
                neighbor_peak = float(
                    reference_ordered.loc[
                        [reference_index - 1, reference_index + 1], reference_column
                    ].max()
                )
                uncertainty = float(reference_ordered.loc[reference_index, uncertainty_column])
                uncertainty_resolved = (discrete_peak - neighbor_peak) > uncertainty
            else:
                discrete_peak = float(reference_ordered.loc[reference_index, reference_column])
                neighbor_peak = float("nan")
                uncertainty = float(reference_ordered.loc[reference_index, uncertainty_column])
                uncertainty_resolved = False
            peak_is_resolved = reference_interior and uncertainty_resolved
            relative_error = abs(computed_omega - reference_omega) / max(abs(reference_omega), 1.0e-12)
            if not reference_interior:
                status = "UNRESOLVED"
                reason = "experimental maximum is at the measured-range boundary"
            elif not uncertainty_resolved:
                status = "UNRESOLVED"
                reason = "experimental peak prominence does not exceed digitization uncertainty"
            elif not computed_interior:
                status = "FAIL"
                reason = "computed maximum is at the comparison-range boundary"
            else:
                status = "PASS" if relative_error <= PEAK_FREQUENCY_RELATIVE_ERROR_LIMIT else "FAIL"
                reason = "experimental peak is bracketed and uncertainty-resolved"
            rows.append(
                {
                    "configuration": configuration,
                    "metric": metric,
                    "eligible_experimental_points": len(reference_ordered),
                    "dense_computed_points": len(dense_group),
                    "reference_peak_is_interior": reference_interior,
                    "reference_peak_uncertainty_resolved": uncertainty_resolved,
                    "peak_is_resolved": peak_is_resolved,
                    "computed_peak_is_interior": computed_interior,
                    "reference_discrete_peak_rao": discrete_peak,
                    "reference_neighbor_max_rao": neighbor_peak,
                    "digitization_uncertainty_abs": uncertainty,
                    "reference_peak_omega_e_rad_s": reference_omega,
                    "computed_peak_omega_e_rad_s": computed_omega,
                    "reference_peak_rao_quadratic": reference_value,
                    "computed_peak_rao_quadratic": computed_value,
                    "peak_frequency_relative_error": relative_error,
                    "limit": PEAK_FREQUENCY_RELATIVE_ERROR_LIMIT,
                    "status": status,
                    "reason": reason,
                }
            )
    return pd.DataFrame(rows)


def _peak_metrics_for_scope(
    comparison: pd.DataFrame,
    *,
    scope: str,
    minimum_points: int,
    require_interior_reference_peak: bool,
) -> pd.DataFrame:
    peak_rows: list[dict[str, Any]] = []
    for configuration, group in comparison.groupby("configuration"):
        group = group.sort_values("omega_e_rad_s").reset_index(drop=True)
        for metric, computed_column, reference_column in (
            ("heave", "heave_rao_m_per_m", "reference_heave_rao_m_per_m"),
            ("pitch", "pitch_rao_rad_per_wave_slope", "reference_pitch_rao_rad_per_wave_slope"),
        ):
            reference_peak_index = int(group[reference_column].to_numpy().argmax())
            peak_is_interior = 0 < reference_peak_index < len(group) - 1
            peak_is_resolved = len(group) >= minimum_points and (
                peak_is_interior or not require_interior_reference_peak
            )
            computed_peak = group.loc[group[computed_column].idxmax()]
            reference_peak = group.loc[group[reference_column].idxmax()]
            relative_error = abs(
                float(computed_peak["omega_e_rad_s"]) - float(reference_peak["omega_e_rad_s"])
            ) / max(abs(float(reference_peak["omega_e_rad_s"])), 1.0e-12)
            if not peak_is_resolved:
                status = "UNRESOLVED"
                reason = (
                    f"{len(group)} eligible points; reference maximum is "
                    f"{'interior' if peak_is_interior else 'at the scope boundary'}"
                )
            else:
                status = "PASS" if relative_error <= PEAK_FREQUENCY_RELATIVE_ERROR_LIMIT else "FAIL"
                reason = "peak is bracketed inside the declared scope"
            peak_rows.append(
                {
                    "configuration": configuration,
                    "metric": metric,
                    "scope": scope,
                    "eligible_point_count": len(group),
                    "reference_peak_is_interior": peak_is_interior,
                    "peak_is_resolved": peak_is_resolved,
                    "computed_peak_lambda_over_l": float(computed_peak["lambda_over_l"]),
                    "reference_peak_lambda_over_l": float(reference_peak["lambda_over_l"]),
                    "computed_peak_omega_e_rad_s": float(computed_peak["omega_e_rad_s"]),
                    "reference_peak_omega_e_rad_s": float(reference_peak["omega_e_rad_s"]),
                    "peak_frequency_relative_error": relative_error,
                    "limit": PEAK_FREQUENCY_RELATIVE_ERROR_LIMIT,
                    "status": status,
                    "reason": reason,
                }
            )
    return pd.DataFrame(peak_rows)


def _fridsma_metrics(comparison: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eligible = comparison[comparison["linear_gate_eligible"].astype(bool)].copy()
    metrics = [
        {
            "metric": "heave_motion",
            "eligible_point_count": len(eligible),
            "median_relative_error": float(eligible["heave_relative_error"].median()),
            "nrmse": _nrmse(eligible["heave_rao_m_per_m"], eligible["reference_heave_rao_m_per_m"]),
            "median_limit": MOTION_MEDIAN_RELATIVE_ERROR_LIMIT,
            "nrmse_limit": MOTION_NRMSE_LIMIT,
        },
        {
            "metric": "pitch_motion",
            "eligible_point_count": len(eligible),
            "median_relative_error": float(eligible["pitch_relative_error"].median()),
            "nrmse": _nrmse(
                eligible["pitch_rao_rad_per_wave_slope"],
                eligible["reference_pitch_rao_rad_per_wave_slope"],
            ),
            "median_limit": MOTION_MEDIAN_RELATIVE_ERROR_LIMIT,
            "nrmse_limit": MOTION_NRMSE_LIMIT,
        },
    ]
    metric_frame = pd.DataFrame(metrics)
    metric_frame["status"] = np.where(
        (metric_frame["median_relative_error"] <= metric_frame["median_limit"])
        & (metric_frame["nrmse"] <= metric_frame["nrmse_limit"]),
        "PASS",
        "FAIL",
    )

    linear_peak_metrics = _peak_metrics_for_scope(
        eligible,
        scope="predeclared_linear_scope",
        minimum_points=3,
        require_interior_reference_peak=True,
    )
    full_range_peak_diagnostics = _peak_metrics_for_scope(
        comparison,
        scope="full_measured_range_including_nonlinear_resonance",
        minimum_points=1,
        require_interior_reference_peak=False,
    )
    return metric_frame, linear_peak_metrics, full_range_peak_diagnostics


def _standard_three_speed_models() -> tuple[pd.DataFrame, list[tuple[float, Any]]]:
    boat = BoatConfig(
        length_m=6.5,
        beam_m=1.0,
        deadrise_deg=20.0,
        mass_kg=1.28 * 1025.0,
        lcg_m=2.13,
        vcg_m=0.25,
        pitch_radius_gyration_m=1.3,
        rho_water_kg_m3=1025.0,
        gravity_m_s2=9.80665,
        wetted_lengths_type=1,
    )
    state = PrescribedRunningStateConfig(enabled=True, trim_deg=4.0, lambda_w=4.0)
    lambda_over_l = np.linspace(4.0, 12.0, 25)
    wavelength = lambda_over_l * boat.length_m
    rows: list[pd.DataFrame] = []
    models: list[tuple[float, Any]] = []
    for fn_b in (2.0, 3.0, 4.0):
        speed = fn_b * math.sqrt(boat.gravity_m_s2 * boat.beam_m)
        equilibrium = make_prescribed_equilibrium(boat, speed, state)
        matrices = compute_hydro_matrices(boat, equilibrium)
        model = build_faltinsen_planing_model(
            boat,
            equilibrium,
            matrices,
            wavelength,
            0.01,
            point_x_forward_m=boat.length_m - boat.lcg_m,
            phase_length_m=boat.length_m,
            metadata={"benchmark": "faltinsen_ch9_three_speed_coverage", "fn_b": fn_b},
        )
        response = solve_longitudinal_frequency_response(model)
        response["fn_b"] = fn_b
        response["speed_mps"] = speed
        response["lambda_over_l"] = lambda_over_l
        rows.append(response)
        models.append((fn_b, model))
    return pd.concat(rows, ignore_index=True), models


def _time_domain_checks(models: list[tuple[float, Any]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    consistency_rows: list[dict[str, Any]] = []
    linearity_rows: list[dict[str, Any]] = []
    representative = pd.DataFrame()
    for fn_b, model in models:
        lambda_over_l = model.wavelength_m / 6.5
        index = int(np.argmin(np.abs(lambda_over_l - 6.0)))
        consistency_rows.append(
            {
                "fn_b": fn_b,
                "frequency_index": index,
                "lambda_over_l": float(lambda_over_l[index]),
                **frequency_time_consistency(model, index),
            }
        )
        linearity_rows.append(
            {
                "fn_b": fn_b,
                "frequency_index": index,
                "lambda_over_l": float(lambda_over_l[index]),
                **wave_amplitude_linearity(model, index, 0.005),
            }
        )
        if fn_b == 3.0:
            representative = simulate_regular_wave_ivp(model, index, wave_amplitude_m=0.01)
            representative["fn_b"] = fn_b
            representative["lambda_over_l"] = float(lambda_over_l[index])
    return pd.DataFrame(consistency_rows), pd.DataFrame(linearity_rows), representative


def _run_gate1(root: Path, out_dir: Path) -> tuple[bool, str]:
    gate1_out = out_dir / "gate1_regression"
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.run_ma2005_gate1_acceptance", "--out", str(gate1_out)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    log = completed.stdout + completed.stderr
    (out_dir / "gate1_regression.log").write_text(log, encoding="utf-8")
    summary_path = gate1_out / "gate1_acceptance_summary.csv"
    passed = completed.returncode == 0 and summary_path.exists()
    if passed:
        summary = pd.read_csv(summary_path)
        passed = bool(summary.iloc[0]["acceptance_status"] == "PASS")
    return passed, log


def _plot_fridsma(comparison: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.5), constrained_layout=True)
    definitions = (
        ("heave_rao_m_per_m", "reference_heave_rao_m_per_m", "Heave RAO", axes[0, 0]),
        (
            "pitch_rao_rad_per_wave_slope",
            "reference_pitch_rao_rad_per_wave_slope",
            "Pitch / wave-slope amplitude",
            axes[0, 1],
        ),
        ("cg_accel_g", "reference_cg_accel_g", "CG vertical acceleration (g)", axes[1, 0]),
        ("point_accel_g", "reference_bow_accel_g", "Bow vertical acceleration (g)", axes[1, 1]),
    )
    colors = {"A": "#0072B2", "B": "#D55E00"}
    for computed, reference, title, axis in definitions:
        for configuration, group in comparison.groupby("configuration"):
            ordered = group.sort_values("lambda_over_l")
            color = colors[str(configuration)]
            axis.plot(ordered["lambda_over_l"], ordered[computed], color=color, label=f"{configuration} model")
            axis.scatter(
                ordered["lambda_over_l"],
                ordered[reference],
                facecolors="white",
                edgecolors=color,
                marker="o",
                label=f"{configuration} Fridsma",
            )
            eligible = ordered[ordered["linear_gate_eligible"].astype(bool)]
            axis.scatter(eligible["lambda_over_l"], eligible[reference], color=color, marker="s", s=24)
        axis.set_title(title)
        axis.set_xlabel("Wavelength / hull length")
        axis.grid(True, alpha=0.25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=4)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_begovic(
    comparison: pd.DataFrame, dense_response: pd.DataFrame, peak_metrics: pd.DataFrame, path: Path
) -> None:
    configurations = sorted(comparison["configuration"].unique())
    fig, axes = plt.subplots(2, len(configurations), figsize=(13.0, 7.0), constrained_layout=True)
    definitions = (
        ("heave", "heave_rao_m_per_m", "reference_heave_rao_m_per_m", "Heave RAO"),
        (
            "pitch",
            "pitch_rao_rad_per_wave_slope",
            "reference_pitch_rao_rad_per_wave_slope",
            "Pitch / wave-slope amplitude",
        ),
    )
    for column, configuration in enumerate(configurations):
        measured = comparison[comparison["configuration"].eq(configuration)].sort_values("lambda_over_l")
        dense = dense_response[dense_response["configuration"].eq(configuration)].sort_values(
            "lambda_over_l"
        )
        for row, (metric, computed_column, reference_column, ylabel) in enumerate(definitions):
            axis = axes[row, column]
            axis.plot(
                dense["lambda_over_l"],
                dense[computed_column],
                color="#0072B2",
                label="Ch. 9 reduced-order model",
            )
            uncertainty_column = f"{metric}_digitization_uncertainty_abs"
            axis.errorbar(
                measured["lambda_over_l"],
                measured[reference_column],
                yerr=measured[uncertainty_column],
                color="#B22222",
                marker="^",
                linestyle="none",
                capsize=2.5,
                label="Begovic EFD",
            )
            excluded = measured[~measured["linear_gate_eligible"].astype(bool)]
            if not excluded.empty:
                axis.scatter(
                    excluded["lambda_over_l"],
                    excluded[reference_column],
                    facecolors="none",
                    edgecolors="#555555",
                    marker="s",
                    s=70,
                    label="retained outside kA gate",
                )
            peak = peak_metrics[
                peak_metrics["configuration"].eq(configuration) & peak_metrics["metric"].eq(metric)
            ].iloc[0]
            axis.text(
                0.03,
                0.96,
                f"peak: {peak['status']}\nerror={peak['peak_frequency_relative_error']:.1%}",
                transform=axis.transAxes,
                va="top",
                fontsize=8,
            )
            axis.set_title(configuration)
            axis.set_xlabel("Wavelength / hull length")
            axis.set_ylabel(ylabel)
            axis.grid(True, alpha=0.25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="center left", bbox_to_anchor=(1.0, 0.5), ncol=1)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_coverage(coverage: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.5), constrained_layout=True)
    definitions = (
        ("heave_rao_m_per_m", "Heave RAO", axes[0, 0]),
        ("pitch_rao_rad_per_wave_slope", "Pitch / wave-slope amplitude", axes[0, 1]),
        ("cg_accel_rao_mps2_per_m", "CG acceleration RAO", axes[1, 0]),
        ("point_accel_rao_mps2_per_m", "Bow acceleration RAO", axes[1, 1]),
    )
    for column, title, axis in definitions:
        for fn_b, group in coverage.groupby("fn_b"):
            axis.plot(group["lambda_over_l"], group[column], label=f"FnB={fn_b:g}")
        axis.set_title(title)
        axis.set_xlabel("Wavelength / hull length")
        axis.grid(True, alpha=0.25)
    axes[0, 0].legend()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_timeseries(timeseries: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 7.2), sharex=True, constrained_layout=True)
    axes[0].plot(timeseries["time_s"], timeseries["wave_elevation_m"], label="Wave at CG")
    axes[0].plot(timeseries["time_s"], timeseries["heave_m"], label="Heave")
    axes[0].set_ylabel("m")
    axes[0].legend()
    axes[1].plot(timeseries["time_s"], np.degrees(timeseries["pitch_rad"]))
    axes[1].set_ylabel("Pitch (deg)")
    axes[2].plot(timeseries["time_s"], timeseries["heave_accel_mps2"], label="CG")
    axes[2].plot(timeseries["time_s"], timeseries["point_vertical_accel_mps2"], label="Bow")
    axes[2].set_ylabel("m/s2")
    axes[2].set_xlabel("Time (s)")
    axes[2].legend()
    for axis in axes:
        axis.grid(True, alpha=0.25)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    args = _parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    out_dir = args.out.resolve()
    figures = out_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    table1, table2, fridsma_source_manifest, fridsma_source_hashes = _verify_sources(root)
    (
        begovic_hull,
        begovic_motion,
        begovic_running_state,
        begovic_source_manifest,
        begovic_source_hashes,
    ) = (
        _verify_begovic_sources(root)
    )
    gate1_pass, _ = _run_gate1(root, out_dir)
    fridsma_comparison, fridsma_matrix_audit = _run_fridsma_comparison(table1, table2)
    fridsma_motion_metrics, fridsma_linear_peak_metrics, full_range_peak_diagnostics = _fridsma_metrics(
        fridsma_comparison
    )
    begovic_comparison, begovic_dense_response, begovic_matrix_audit = _run_begovic_comparison(
        begovic_hull, begovic_motion, begovic_running_state
    )
    begovic_motion_metrics = _motion_metrics(
        begovic_comparison, scope=f"Begovic EFD kA<={BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT:g}"
    )
    begovic_peak_metrics = _begovic_peak_metrics(begovic_comparison, begovic_dense_response)
    coverage, models = _standard_three_speed_models()
    consistency, linearity, representative = _time_domain_checks(models)

    eligible = fridsma_comparison[fridsma_comparison["linear_gate_eligible"].astype(bool)]
    phase_errors = pd.concat(
        [eligible["heave_phase_circular_error_deg"], eligible["pitch_phase_circular_error_deg"]],
        ignore_index=True,
    ).dropna()
    phase_median = float(phase_errors.median())
    cg_accel_nrmse = _nrmse(eligible["cg_accel_g"], eligible["reference_cg_accel_g"])
    computed_finite_columns = [
        "omega0_rad_s",
        "omega_e_rad_s",
        "wavenumber_rad_m",
        "heave_response_real_m_per_m",
        "heave_response_imag_m_per_m",
        "pitch_response_real_rad_per_m",
        "pitch_response_imag_rad_per_m",
        "heave_rao_m_per_m",
        "pitch_rao_rad_per_wave_slope",
        "cg_accel_rao_mps2_per_m",
        "point_accel_rao_mps2_per_m",
        "dynamic_condition_number",
        "equation_relative_residual",
    ]
    finite_frames = (coverage, fridsma_comparison, begovic_comparison, begovic_dense_response)
    all_finite = all(
        np.isfinite(frame[computed_finite_columns].to_numpy(dtype=float)).all()
        for frame in finite_frames
    )
    max_equation_residual = float(
        max(
            coverage["equation_relative_residual"].max(),
            fridsma_comparison["equation_relative_residual"].max(),
            begovic_comparison["equation_relative_residual"].max(),
            begovic_dense_response["equation_relative_residual"].max(),
        )
    )
    min_excitation = float(
        min(
            np.linalg.norm(model.excitation_per_wave_amplitude, axis=1).min()
            for _, model in models
        )
    )
    max_time_amplitude_error = float(
        consistency[["heave_amplitude_relative_error", "pitch_amplitude_relative_error"]].to_numpy().max()
    )
    max_time_phase_error = float(
        consistency[["heave_phase_circular_error_deg", "pitch_phase_circular_error_deg"]].to_numpy().max()
    )
    max_kinematic_residual = float(consistency["point_acceleration_kinematic_relative_residual"].max())
    max_linearity_deviation = float(
        np.abs(
            linearity[
                ["heave_amplitude_ratio", "pitch_amplitude_ratio", "point_acceleration_amplitude_ratio"]
            ].to_numpy()
            - 2.0
        ).max()
    )
    min_points_per_speed = int(coverage.groupby("fn_b").size().min())
    fridsma_motion_count = int(len(fridsma_comparison))
    fridsma_speed_count = int(fridsma_comparison["configuration"].nunique())
    begovic_motion_count = int(len(begovic_comparison))
    begovic_speed_count = int(begovic_comparison["configuration"].nunique())
    fridsma_linear_peak_resolved = bool(fridsma_linear_peak_metrics["peak_is_resolved"].all())
    fridsma_linear_peak_error_max = float(
        fridsma_linear_peak_metrics["peak_frequency_relative_error"].max()
    )
    full_range_peak_error_max = float(full_range_peak_diagnostics["peak_frequency_relative_error"].max())
    resolved_begovic_peaks = begovic_peak_metrics[begovic_peak_metrics["peak_is_resolved"].astype(bool)]
    begovic_peak_resolved_count = int(len(resolved_begovic_peaks))
    begovic_peak_speed_count = int(resolved_begovic_peaks["configuration"].nunique())
    begovic_peak_metric_count = int(resolved_begovic_peaks["metric"].nunique())
    begovic_peak_coverage_pass = (
        begovic_peak_resolved_count >= MINIMUM_RESOLVED_BEGOVIC_PEAKS
        and begovic_peak_speed_count >= 2
        and begovic_peak_metric_count == 2
    )
    begovic_peak_error_max = (
        float(resolved_begovic_peaks["peak_frequency_relative_error"].max())
        if not resolved_begovic_peaks.empty
        else float("inf")
    )
    begovic_peak_accuracy_pass = begovic_peak_coverage_pass and bool(
        resolved_begovic_peaks["status"].eq("PASS").all()
    )

    machine_rows = [
        ("gate1_regression", gate1_pass, "Ma 2005 10/10 and double-grid Gate 1 must remain PASS."),
        (
            "nonzero_physical_excitation",
            min_excitation > 1.0e-12,
            "Faltinsen Eq. 9.110-9.117 excitation norm must be non-zero at every coverage point.",
        ),
        (
            "equation_relative_residual",
            max_equation_residual <= EQUATION_RESIDUAL_LIMIT,
            f"max={max_equation_residual:.3e}, limit={EQUATION_RESIDUAL_LIMIT:.1e}",
        ),
        (
            "finite_outputs",
            all_finite,
            "All computed coverage, Fridsma and Begovic response fields must be finite.",
        ),
        (
            "three_speed_twenty_frequency_coverage",
            coverage["fn_b"].nunique() >= 3 and min_points_per_speed >= 20,
            f"speed_count={coverage['fn_b'].nunique()}, min_points_per_speed={min_points_per_speed}",
        ),
        (
            "frequency_time_amplitude_consistency",
            max_time_amplitude_error <= TIME_AMPLITUDE_RELATIVE_ERROR_LIMIT,
            f"max={max_time_amplitude_error:.3e}, limit={TIME_AMPLITUDE_RELATIVE_ERROR_LIMIT:.3f}",
        ),
        (
            "frequency_time_phase_consistency",
            max_time_phase_error <= TIME_PHASE_ERROR_LIMIT_DEG,
            f"max={max_time_phase_error:.3e} deg, limit={TIME_PHASE_ERROR_LIMIT_DEG:g} deg",
        ),
        (
            "wave_amplitude_linearity",
            max_linearity_deviation <= LINEARITY_RATIO_TOLERANCE,
            f"max |ratio-2|={max_linearity_deviation:.3e}, limit={LINEARITY_RATIO_TOLERANCE:.3f}",
        ),
        (
            "point_acceleration_kinematics",
            max_kinematic_residual <= KINEMATIC_RESIDUAL_LIMIT,
            f"max={max_kinematic_residual:.3e}, limit={KINEMATIC_RESIDUAL_LIMIT:.1e}",
        ),
        (
            "independent_experiment_coverage",
            fridsma_speed_count >= 2
            and fridsma_motion_count >= 10
            and begovic_speed_count >= 3
            and begovic_motion_count >= 24,
            (
                f"Fridsma: speeds={fridsma_speed_count}, rows={fridsma_motion_count}; "
                f"Begovic: speeds={begovic_speed_count}, rows={begovic_motion_count}."
            ),
        ),
        (
            "fridsma_heave_experiment_accuracy",
            fridsma_motion_metrics.loc[
                fridsma_motion_metrics["metric"].eq("heave_motion"), "status"
            ].iloc[0]
            == "PASS",
            "Fridsma linear long-wave median relative error <=15% and NRMSE <=20%.",
        ),
        (
            "fridsma_pitch_experiment_accuracy",
            fridsma_motion_metrics.loc[
                fridsma_motion_metrics["metric"].eq("pitch_motion"), "status"
            ].iloc[0]
            == "PASS",
            "Fridsma linear long-wave median relative error <=15% and NRMSE <=20%.",
        ),
        (
            "begovic_heave_experiment_accuracy",
            begovic_motion_metrics.loc[
                begovic_motion_metrics["metric"].eq("heave_motion"), "status"
            ].iloc[0]
            == "PASS",
            f"Begovic kA<={BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT:g}: median relative error <=15% and NRMSE <=20%.",
        ),
        (
            "begovic_pitch_experiment_accuracy",
            begovic_motion_metrics.loc[
                begovic_motion_metrics["metric"].eq("pitch_motion"), "status"
            ].iloc[0]
            == "PASS",
            f"Begovic kA<={BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT:g}: median relative error <=15% and NRMSE <=20%.",
        ),
        (
            "phase_experiment_accuracy",
            phase_median <= PHASE_MEDIAN_ERROR_LIMIT_DEG,
            f"median={phase_median:.3f} deg, limit={PHASE_MEDIAN_ERROR_LIMIT_DEG:g} deg",
        ),
        (
            "cg_acceleration_experiment_accuracy",
            cg_accel_nrmse <= CG_ACCEL_NRMSE_LIMIT,
            f"NRMSE={cg_accel_nrmse:.5f}, limit={CG_ACCEL_NRMSE_LIMIT:.2f}; bow peaks remain diagnostic.",
        ),
        (
            "begovic_peak_frequency_resolved",
            begovic_peak_coverage_pass,
            (
                f"resolved={begovic_peak_resolved_count}, speeds={begovic_peak_speed_count}, "
                f"metrics={begovic_peak_metric_count}; require >={MINIMUM_RESOLVED_BEGOVIC_PEAKS}, >=2 speeds and both motions."
            ),
        ),
        (
            "begovic_peak_frequency_accuracy",
            begovic_peak_accuracy_pass,
            (
                f"max resolved-peak error={begovic_peak_error_max:.5f}, "
                f"limit={PEAK_FREQUENCY_RELATIVE_ERROR_LIMIT:.2f}; every hard resolved peak must pass."
            ),
        ),
        (
            "approved_source_hashes",
            True,
            json.dumps(
                {"fridsma": fridsma_source_hashes, "begovic": begovic_source_hashes},
                sort_keys=True,
            ),
        ),
        ("no_empirical_response_scaling", True, "No response multiplier or reference-derived coefficient is used."),
    ]
    machine = pd.DataFrame(
        [
            {"check": name, "status": "PASS" if passed else "FAIL", "evidence": evidence}
            for name, passed, evidence in machine_rows
        ]
    )
    acceptance_status = "PASS" if machine["status"].eq("PASS").all() else "FAIL"

    fridsma_comparison.to_csv(out_dir / "fridsma_table2_comparison.csv", index=False)
    fridsma_motion_metrics.to_csv(out_dir / "fridsma_linear_scope_metrics.csv", index=False)
    fridsma_linear_peak_metrics.to_csv(
        out_dir / "fridsma_linear_scope_peak_frequency_diagnostic.csv", index=False
    )
    full_range_peak_diagnostics.to_csv(
        out_dir / "fridsma_full_range_peak_diagnostic.csv", index=False
    )
    fridsma_matrix_audit.to_csv(out_dir / "fridsma_heave_pitch_matrices.csv", index=False)
    begovic_comparison.to_csv(out_dir / "begovic_efd_comparison.csv", index=False)
    begovic_dense_response.to_csv(out_dir / "begovic_dense_peak_scan.csv", index=False)
    begovic_motion_metrics.to_csv(out_dir / "begovic_linear_scope_metrics.csv", index=False)
    begovic_peak_metrics.to_csv(out_dir / "begovic_peak_frequency.csv", index=False)
    begovic_matrix_audit.to_csv(out_dir / "begovic_heave_pitch_matrices.csv", index=False)
    coverage.to_csv(out_dir / "three_speed_frequency_response.csv", index=False)
    consistency.to_csv(out_dir / "frequency_time_consistency.csv", index=False)
    linearity.to_csv(out_dir / "wave_amplitude_linearity.csv", index=False)
    representative.to_csv(out_dir / "representative_regular_wave_timeseries.csv", index=False)
    machine.to_csv(out_dir / "gate2_machine_acceptance.csv", index=False)

    formula_trace = pd.DataFrame(
        [
            ("wave_kinematics", "Faltinsen Eq. 9.90, 9.107, 9.116", "omega_e=omega0+kU; zeta=zeta_a sin(omega_e t-kx)"),
            ("finite_length_phase", "Faltinsen Eq. 9.95-9.98", "constant-section exact strip integrals / long-wave limits"),
            ("excitation", "Faltinsen Eq. 9.110-9.117", "F_hat=F_c-iF_s; includes generalized FK and diffraction analogy"),
            ("motion_equation", "Faltinsen Eq. 9.119", "[-omega_e^2(M+A)+i omega_e B+C]xi=F_exc"),
            ("response_amplitude", "Faltinsen Eq. 9.120", "RAO_j=abs(xi_j)/zeta_a"),
            ("point_acceleration", "rigid-body small-angle kinematics", "a_z(x)=-omega_e^2(eta3+x eta5), x positive forward"),
        ],
        columns=["implementation_block", "source", "formula_or_convention"],
    )
    formula_trace.to_csv(out_dir / "formula_code_test_trace.csv", index=False)

    _plot_fridsma(fridsma_comparison, figures / "fridsma_table2_comparison.png")
    _plot_begovic(
        begovic_comparison,
        begovic_dense_response,
        begovic_peak_metrics,
        figures / "begovic_efd_peak_comparison.png",
    )
    _plot_coverage(coverage, figures / "three_speed_response.png")
    _plot_timeseries(representative, figures / "representative_time_domain.png")

    input_snapshot = {
        "acceptance_profile": "regular_head_sea_gate2_locked_v2_begovic_peak_gate",
        "source_hashes": {
            "fridsma": fridsma_source_hashes,
            "begovic": begovic_source_hashes,
        },
        "source_manifests": {
            "fridsma": fridsma_source_manifest,
            "begovic": begovic_source_manifest,
        },
        "matrix_contract": "heave_pitch_2x2_v1",
        "provider_route": "faltinsen_ch9_reduced_order_planing",
        "equation": "[-omega_e^2(M+A)+i*omega_e*B+C]xi=F_exc",
        "coverage_fn_b": [2.0, 3.0, 4.0],
        "coverage_frequency_points_per_speed": 25,
        "fridsma_configurations": ["A", "B"],
        "fridsma_linear_gate_definition": "lambda/L >= 4, non-resonant long-wave subset predeclared in benchmark CSV",
        "begovic_configurations_fn_b": [1.67, 2.26, 2.82],
        "begovic_running_state_definition": (
            "measured running trim from Begovic et al. 2014 Table 3 and measured keel wetted length "
            "transcribed in Javaherian 2021 Table 5.2 from Begovic and Bertorello 2012"
        ),
        "begovic_linear_gate_definition": f"wave steepness kA <= {BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT:g}",
        "begovic_peak_definition": (
            "three-point quadratic experimental peak plus 241-point model scan; "
            "experimental prominence must exceed digitization uncertainty"
        ),
        "bow_acceleration_role": "retained nonlinear impact diagnostic; CG acceleration is the linear hard metric",
        "empirical_response_scaling": False,
    }
    _write_json(out_dir / "input_snapshot.json", input_snapshot)

    summary = pd.DataFrame(
        [
            {
                "acceptance_status": acceptance_status,
                "gate1_status": "PASS" if gate1_pass else "FAIL",
                "machine_pass_count": int(machine["status"].eq("PASS").sum()),
                "machine_check_count": int(len(machine)),
                "speed_count": int(coverage["fn_b"].nunique()),
                "min_frequency_points_per_speed": min_points_per_speed,
                "max_equation_relative_residual": max_equation_residual,
                "max_frequency_time_amplitude_relative_error": max_time_amplitude_error,
                "max_frequency_time_phase_error_deg": max_time_phase_error,
                "max_linearity_ratio_deviation": max_linearity_deviation,
                "max_kinematic_relative_residual": max_kinematic_residual,
                "fridsma_speed_count": fridsma_speed_count,
                "fridsma_motion_point_count": fridsma_motion_count,
                "fridsma_phase_median_error_deg": phase_median,
                "fridsma_cg_accel_nrmse": cg_accel_nrmse,
                "fridsma_linear_scope_peak_resolved_diagnostic": fridsma_linear_peak_resolved,
                "fridsma_linear_scope_peak_frequency_relative_error_max_diagnostic": fridsma_linear_peak_error_max,
                "fridsma_full_range_peak_frequency_relative_error_max_diagnostic": full_range_peak_error_max,
                "begovic_speed_count": begovic_speed_count,
                "begovic_motion_point_count": begovic_motion_count,
                "begovic_resolved_peak_count": begovic_peak_resolved_count,
                "begovic_resolved_peak_speed_count": begovic_peak_speed_count,
                "begovic_resolved_peak_metric_count": begovic_peak_metric_count,
                "begovic_peak_frequency_relative_error_max": begovic_peak_error_max,
                "empirical_response_scaling_used": False,
            }
        ]
    )
    summary.to_csv(out_dir / "gate2_acceptance_summary.csv", index=False)

    failures = machine[machine["status"].eq("FAIL")]
    report = f"""# 规则迎浪升沉--纵摇 Gate 2 阶段报告

## 结论

机器验收状态：**{acceptance_status}**（{int(machine['status'].eq('PASS').sum())}/{len(machine)}）。

本次计算首次将冻结的 `(heave, pitch)` 矩阵契约、Faltinsen Eq. 9.110--9.117 非零波浪激励、Eq. 9.119 复数运动方程、刚体点加速度和 `solve_ivp` 小波幅复算放在同一条可追溯路径中。计算未使用响应倍率、参考值反推或逐点拟合。

## 数值闭合

- 三个航速：`Fn_B=2, 3, 4`；每个航速 25 个频率点。
- 最大复数方程相对残差：`{max_equation_residual:.3e}`。
- 最大频域--时域幅值误差：`{max_time_amplitude_error:.3e}`。
- 最大频域--时域相位误差：`{max_time_phase_error:.3e} deg`。
- 最大波幅线性比偏差：`{max_linearity_deviation:.3e}`。
- 最大点加速度运动学残差：`{max_kinematic_residual:.3e}`。

## Fridsma 1969 独立对照

独立数据直接抄录自 Davidson Laboratory Report 1275 的 Table 1 和 Table 2，不是二手曲线拟合。A/B 两个航速共 {fridsma_motion_count} 组完整升沉、纵摇和加速度点；所有短波和共振点均保留在对照表中。

{_markdown_table(fridsma_motion_metrics[['metric', 'eligible_point_count', 'median_relative_error', 'nrmse', 'status']])}

- 线性长波范围相位中位循环误差：`{phase_median:.3f} deg`。
- 线性长波范围重心加速度 NRMSE：`{cg_accel_nrmse:.3%}`。
- Fridsma 线性长波子集主峰是否全部夹持（仅作稀疏数据诊断）：`{fridsma_linear_peak_resolved}`。
- 全测量范围主峰频率最大相对误差（含非线性共振，仅作诊断）：`{full_range_peak_error_max:.3%}`。
- 艏部加速度是试验中的非线性冲击峰值，本阶段完整输出并保留误差，但不以线性谐波幅值冒充冲击峰值通过项。

## Begovic 规则波密集独立对照

Begovic 原始试验的单体滑行艇 EFD 数据由 Kahramanoglu 等（2020）Figures 6--8 重新发表。本验收从冻结 PDF 的红色三角试验标记自动数字化，三航速各 8 个波长点；源 PDF、内嵌图像、坐标标定、候选像素和数字化不确定度均可追溯。`kA>{BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT:g}` 的点保留在全表中但不参加线性幅值统计。

三航速的运行纵倾采用 Begovic 等（2014）Table 3 实测值，龙骨湿长采用 Javaherian（2021）Table 5.2 对 Begovic 和 Bertorello（2012）试验值的逐点抄录。二者仅用于重建试验运行状态，不含任何运动响应信息；程序不再用遗漏拖曳力矩的静水平衡替代已知试验状态。原表 sinkage 因垂向基准与符号定义不足，仅保留为诊断字段，未参与坐标换算。

{_markdown_table(begovic_motion_metrics[['scope', 'metric', 'eligible_point_count', 'median_relative_error', 'nrmse', 'status']])}

{_markdown_table(begovic_peak_metrics[['configuration', 'metric', 'peak_is_resolved', 'computed_peak_is_interior', 'peak_frequency_relative_error', 'status', 'reason']])}

- 可用于硬验收的主峰：`{begovic_peak_resolved_count}` 个，覆盖 `{begovic_peak_speed_count}` 个航速和 `{begovic_peak_metric_count}` 类运动。
- 已解析主峰最大频率相对误差：`{begovic_peak_error_max:.3%}`，限值为 `{PEAK_FREQUENCY_RELATIVE_ERROR_LIMIT:.0%}`。
- 试验边界最大值或峰高不超过数字化不确定度的宽平台均标为 `UNRESOLVED`，不伪装成通过项。

## 未通过项

{_markdown_table(failures[['check', 'evidence']]) if not failures.empty else '无。'}

## 边界

本阶段只处理小幅规则迎浪升沉--纵摇。当前 Faltinsen Chapter 9 紧凑模型采用关于稳态滑行姿态的高频附加质量和动升力阻尼近似；若 Begovic 主峰门槛失败，下一步应补齐与滑行基流相容的频率相关辐射、前进速度交叉项和波浪激励分解。不得直接叠加不相容的排水型 2.5D 阻尼矩阵，也不得加入经验响应倍率。Fridsma 的冲击峰值和强非线性范围留待后续 2D+t 阶段。
"""
    (out_dir / "gate2_stage_report.md").write_text(report, encoding="utf-8")

    print(summary.to_string(index=False))
    print(machine.to_string(index=False))
    return 0 if acceptance_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
