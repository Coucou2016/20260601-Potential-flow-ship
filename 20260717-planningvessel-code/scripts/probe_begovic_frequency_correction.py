from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.config import BoatConfig, PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.linearized_momentum_strip import (
    MomentumStripOptions,
    build_linearized_momentum_strip_model,
    linearize_momentum_strip,
    momentum_strip_wave_excitation_per_amplitude,
)
from planing_seakeeping.longitudinal_response import (
    build_faltinsen_planing_model,
    solve_longitudinal_frequency_response,
)
from planing_seakeeping.planing_frequency_correction import (
    PlaningFrequencyCorrection,
    apply_frequency_correction,
    assemble_planing_wetted_hydrostatic_restoring,
    compute_matched_bie_frequency_correction,
    compute_section_bem_frequency_correction,
    head_sea_wavenumber_from_encounter_frequency,
    load_nonlinear_2dt_forced_motion_correction,
)
from scripts.run_regular_head_sea_gate2_acceptance import (
    BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT,
    _begovic_peak_metrics,
    _motion_metrics,
    _verify_begovic_sources,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe a response-independent matched-BIE dynamic correction on the Begovic mono hull."
    )
    parser.add_argument("--fn-b", type=float, default=2.82, choices=[1.67, 2.26, 2.82])
    parser.add_argument(
        "--case-code",
        action="append",
        default=[],
        help=(
            "Restrict a predeclared screening run to explicit frozen Begovic case codes. "
            "Repeat the option; omitted means all eight cases."
        ),
    )
    parser.add_argument("--out", type=Path, default=Path("outputs/begovic_frequency_correction_probe"))
    parser.add_argument("--frequency-samples", type=int, default=5)
    parser.add_argument("--station-count", type=int, default=15)
    parser.add_argument("--body-panels", type=int, default=24)
    parser.add_argument("--inner-panels", type=int, default=12)
    parser.add_argument("--outer-panels", type=int, default=24)
    parser.add_argument(
        "--wagner-pileup-factor",
        type=float,
        default=1.0,
        help=(
            "Matched-BIE mean-wetted-contour scale. The default 1.0 preserves the equilibrium "
            "keel/chine wetted lengths; other values are explicit sensitivity cases only."
        ),
    )
    parser.add_argument(
        "--transom-force-cutoff-length-beams",
        type=float,
        default=0.0,
        help=(
            "Diagnostic Sun--Faltinsen dry-transom 3D correction. Use 0.5 to zero "
            "the Eq.32 sectional force over the aft 0.5B; zero disables it."
        ),
    )
    parser.add_argument(
        "--transom-force-recovery-profile",
        choices=("hard_zero", "linear_ramp", "square_root_ramp"),
        default="hard_zero",
        help=(
            "Use the source coarse hard-zero correction, a continuous linear recovery, "
            "or the local dry-transom square-root pressure asymptotic over the same "
            "fixed stern length."
        ),
    )
    parser.add_argument(
        "--momentum-rate-formulation",
        choices=(
            "relative_velocity_squared",
            "sun_faltinsen_2007_eq7_36_to_7_45",
        ),
        default="relative_velocity_squared",
    )
    parser.add_argument(
        "--base-route",
        choices=("zarnick_full", "faltinsen_ch9", "faltinsen_ch9_zarnick_damping"),
        default="faltinsen_ch9_zarnick_damping",
    )
    parser.add_argument(
        "--phase-length-route",
        choices=("overall", "keel", "mean", "chine"),
        default="mean",
    )
    parser.add_argument(
        "--frequency-coordinate-route",
        choices=("wavelength_dispersion", "source_encounter"),
        default="wavelength_dispersion",
        help=(
            "Build the response grid from rounded wavelength data or from the frozen "
            "source encounter frequency using the head-sea dispersion relation."
        ),
    )
    parser.add_argument(
        "--restoring-route",
        choices=(
            "savitsky_dynamic_lift",
            "mean_wetted_hydrostatic",
            "savitsky_plus_mean_wetted_hydrostatic",
        ),
        default="savitsky_dynamic_lift",
        help=(
            "Response-independent restoring formulation. The hydrostatic routes integrate "
            "the reconstructed mean-wetted volume and linearize buoyancy about the prescribed "
            "running state."
        ),
    )
    parser.add_argument(
        "--force-component-route",
        choices=(
            "total_eq32_stokes_body_plus_end",
            "time_derivative_only",
            "stokes_body_forward_speed_only",
            "end_term_only",
            "time_plus_stokes_body_forward_speed",
            "time_plus_end_term",
        ),
        default="time_derivative_only",
    )
    parser.add_argument(
        "--excitation-route",
        choices=(
            "faltinsen_global",
            "momentum_station_phase",
            "matched_bie_station_phase",
            "section_bem_station_phase",
            "matched_domain_station_phase",
            "direct_2dt_wave_csv",
        ),
        default="faltinsen_global",
        help=(
            "Use the global long-wave analogy, the local momentum-strip wave load, or "
            "the matched-BIE equivalent diffraction route, direct section-BEM, or "
            "A1 matched-domain incident-plus-diffraction pressures."
        ),
    )
    parser.add_argument(
        "--hydrodynamic-correction-source",
        choices=(
            "none",
            "matched_bie",
            "section_bem",
            "nonlinear_2dt_csv",
            "sun2007_uncorrected",
            "sun2007_stern_3d_corrected",
        ),
        default="matched_bie",
    )
    parser.add_argument(
        "--phase-resolved-matrix-application",
        choices=(
            "replace_with_matched_bie",
            "planing_base_plus_matched_radiation",
            "delta_from_high_frequency",
            "planing_high_frequency_added_plus_matched_damping",
        ),
        default="replace_with_matched_bie",
        help=(
            "Complete A/B matrix formulation used with a phase-resolved matched-domain "
            "excitation. The planing-base route retains the Chapter 9 dynamic-lift base "
            "and adds the independently computed matched radiation contribution."
        ),
    )
    parser.add_argument(
        "--forced-motion-csv",
        type=Path,
        action="append",
        default=[],
        help=(
            "Accepted physical-restoring forced-motion CSV. Repeat for separate heave and "
            "pitch files. Required when --hydrodynamic-correction-source=nonlinear_2dt_csv."
        ),
    )
    parser.add_argument(
        "--forced-motion-restoring-csv",
        type=Path,
        default=None,
        help=(
            "Target 2D+t restoring-matrix CSV. When supplied, A, B, and C are "
            "replaced together and the final matrices define the wave excitation."
        ),
    )
    parser.add_argument(
        "--direct-wave-excitation-csv",
        type=Path,
        action="append",
        default=[],
        help=(
            "Direct fixed-hull Sun--Faltinsen 2D+t excitation CSV. Repeat for "
            "separate frequencies when --excitation-route=direct_2dt_wave_csv."
        ),
    )
    return parser


def _boat(hull: pd.Series) -> BoatConfig:
    return BoatConfig(
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


def _comparison(reference_source: pd.DataFrame, response: pd.DataFrame) -> pd.DataFrame:
    reference = reference_source.sort_values("lambda_over_l").reset_index(drop=True).rename(
        columns={
            "heave_rao_m_per_m": "reference_heave_rao_m_per_m",
            "pitch_rao_rad_per_wave_slope": "reference_pitch_rao_rad_per_wave_slope",
            "encounter_omega_rad_s": "source_encounter_omega_rad_s",
        }
    )
    computed = response.drop(columns=["wave_amplitude_m", "wavelength_m"])
    result = pd.concat([reference, computed], axis=1)
    result["configuration"] = f"FnB={float(reference['fn_b'].iloc[0]):.2f}"
    result["linear_gate_eligible"] = (
        result["wave_number_rad_m"] * result["wave_amplitude_m"]
        <= BEGOVIC_LINEAR_WAVE_STEEPNESS_LIMIT
    )
    return result


def _model_term_rows(
    route: str,
    configuration: str,
    model,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    n_frequency = len(model.hydrodynamics.solver_omega_rad_s)
    rigid = np.asarray(model.rigid_mass, dtype=float)
    if rigid.shape == (2, 2):
        rigid = np.repeat(rigid[None, :, :], n_frequency, axis=0)
    terms = {
        "rigid_mass": rigid,
        "added_mass": np.asarray(model.hydrodynamics.added_mass, dtype=float),
        "radiation_damping": np.asarray(
            model.hydrodynamics.radiation_damping,
            dtype=float,
        ),
        "restoring": np.asarray(model.restoring, dtype=float),
    }
    labels = ("heave", "pitch")
    for index in range(n_frequency):
        common = {
            "route": route,
            "configuration": configuration,
            "frequency_index": index,
            "omega_0_rad_s": float(model.omega0_rad_s[index]),
            "omega_e_rad_s": float(model.hydrodynamics.encounter_omega_rad_s[index]),
        }
        for term, matrix in terms.items():
            for row in range(2):
                for column in range(2):
                    rows.append(
                        {
                            **common,
                            "term": term,
                            "row": labels[row],
                            "column": labels[column],
                            "value_real": float(matrix[index, row, column]),
                            "value_imag": 0.0,
                        }
                    )
        excitation = model.excitation_per_wave_amplitude[index]
        for row in range(2):
            rows.append(
                {
                    **common,
                    "term": "excitation_per_wave_amplitude",
                    "row": labels[row],
                    "column": "wave_amplitude",
                    "value_real": float(np.real(excitation[row])),
                    "value_imag": float(np.imag(excitation[row])),
                }
            )
    return rows


def _modal_diagnostic_rows(
    route: str,
    configuration: str,
    model,
) -> list[dict[str, object]]:
    """Return response-independent second-order system health diagnostics.

    The poles are computed only from the complete M+A, B, and C matrices.  No
    measured response ordinate or fitted response quantity enters this audit.
    """

    omega = np.asarray(model.hydrodynamics.encounter_omega_rad_s, dtype=float)
    n_frequency = len(omega)
    rigid = np.asarray(model.rigid_mass, dtype=float)
    if rigid.shape == (2, 2):
        rigid = np.repeat(rigid[None, :, :], n_frequency, axis=0)
    added = np.asarray(model.hydrodynamics.added_mass, dtype=float)
    damping = np.asarray(model.hydrodynamics.radiation_damping, dtype=float)
    restoring = np.asarray(model.restoring, dtype=float)
    rows: list[dict[str, object]] = []
    identity = np.eye(2)
    zeros = np.zeros((2, 2))

    for frequency_index, omega_e in enumerate(omega):
        total_mass = rigid[frequency_index] + added[frequency_index]
        mass_symmetric = 0.5 * (total_mass + total_mass.T)
        mass_symmetric_eigenvalues = np.linalg.eigvalsh(mass_symmetric)
        state_matrix = np.block(
            [
                [zeros, identity],
                [
                    -np.linalg.solve(total_mass, restoring[frequency_index]),
                    -np.linalg.solve(total_mass, damping[frequency_index]),
                ],
            ]
        )
        poles = np.linalg.eigvals(state_matrix)
        pole_order = np.lexsort((poles.real, poles.imag))
        poles = poles[pole_order]
        harmonic_operator = (
            -omega_e**2 * total_mass
            + 1j * omega_e * damping[frequency_index]
            + restoring[frequency_index]
        )
        harmonic_singular_values = np.linalg.svd(
            harmonic_operator,
            compute_uv=False,
        )
        common = {
            "route": route,
            "configuration": configuration,
            "frequency_index": frequency_index,
            "omega_0_rad_s": float(model.omega0_rad_s[frequency_index]),
            "omega_e_rad_s": float(omega_e),
            "total_mass_determinant": float(np.linalg.det(total_mass)),
            "total_mass_condition_number": float(np.linalg.cond(total_mass)),
            "symmetric_mass_min_eigenvalue": float(mass_symmetric_eigenvalues[0]),
            "symmetric_mass_max_eigenvalue": float(mass_symmetric_eigenvalues[-1]),
            "symmetric_mass_positive_definite": bool(
                mass_symmetric_eigenvalues[0] > 0.0
            ),
            "harmonic_operator_condition_number": float(
                harmonic_singular_values[0] / harmonic_singular_values[-1]
            ),
            "harmonic_operator_min_singular_value": float(
                harmonic_singular_values[-1]
            ),
            "system_max_pole_real_1_s": float(np.max(poles.real)),
            "system_asymptotically_stable": bool(np.max(poles.real) < 0.0),
            "response_calibration_used": False,
        }
        for pole_index, pole in enumerate(poles):
            pole_magnitude = float(abs(pole))
            rows.append(
                {
                    **common,
                    "pole_index": pole_index,
                    "pole_real_1_s": float(pole.real),
                    "pole_imag_rad_s": float(pole.imag),
                    "damped_natural_frequency_rad_s": float(abs(pole.imag)),
                    "pole_magnitude_rad_s": pole_magnitude,
                    "modal_damping_ratio": (
                        float(-pole.real / pole_magnitude)
                        if pole_magnitude > np.finfo(float).eps
                        else np.nan
                    ),
                    "pole_stable": bool(pole.real < 0.0),
                }
            )
    return rows


def _sun2007_troesch_diagnostic_correction(
    root: Path,
    boat: BoatConfig,
    variant: str,
) -> PlaningFrequencyCorrection:
    table = pd.read_csv(root / "benchmarks" / "sun2007_troesch_forced_motion_coefficients.csv")
    selected = table[table["model_variant"].eq(variant)].copy()
    frequencies = np.sort(selected["omega_sqrt_B_over_g"].unique())
    if len(frequencies) != 5:
        raise RuntimeError("Sun 2007 forced-motion diagnostic requires five frequencies.")
    values = {
        coefficient: selected[selected["coefficient"].eq(coefficient)]
        .set_index("omega_sqrt_B_over_g")
        .loc[frequencies, "value_nondimensional"]
        .to_numpy(dtype=float)
        for coefficient in ("A33", "A35", "A53", "A55", "B33", "B35", "B53", "B55")
    }
    rho = boat.rho_water_kg_m3
    beam = boat.beam_m
    frequency_scale = math.sqrt(boat.gravity_m_s2 / beam)
    omega = frequencies * frequency_scale
    added = np.empty((len(omega), 2, 2), dtype=float)
    damping = np.empty_like(added)
    added[:, 0, 0] = values["A33"] * rho * beam**3
    added[:, 0, 1] = values["A35"] * rho * beam**4
    added[:, 1, 0] = values["A53"] * rho * beam**4
    added[:, 1, 1] = values["A55"] * rho * beam**5
    damping[:, 0, 0] = values["B33"] * rho * beam**3 * frequency_scale
    damping[:, 0, 1] = values["B35"] * rho * beam**4 * frequency_scale
    damping[:, 1, 0] = values["B53"] * rho * beam**4 * frequency_scale
    damping[:, 1, 1] = values["B55"] * rho * beam**5 * frequency_scale
    return PlaningFrequencyCorrection(
        sample_omega_rad_s=omega,
        high_frequency_reference_rad_s=float(omega[-1]),
        delta_added_mass=added - added[-1][None, :, :],
        delta_radiation_damping=damping - damping[-1][None, :, :],
        raw_added_mass=added,
        raw_radiation_damping=damping,
        metadata={
            "source": "Sun_2007_Figs7.13_7.14_digitized_for_sensitivity_only",
            "source_variant": variant,
            "source_condition": "FnB=2.5,beta=20deg,trim=4deg,lambda_w=3",
            "target_condition": "Begovic_beta=16.7deg_and_measured_running_states",
            "validity_status": "cross_condition_diagnostic_not_admissible_for_gate",
            "coordinate_convention": "heave_up_pitch_bow_up",
            "response_calibration_used": False,
        },
    )


def _correction_route_specs(
    correction: PlaningFrequencyCorrection | None,
) -> tuple[tuple[str, bool, bool, str], ...]:
    """Return admissible matrix applications for a correction source.

    Accepted nonlinear 2D+t forced-motion matrices are a production contract:
    both complete matrices replace the reduced-order matrices together.  The
    component-only and high-frequency-delta routes remain diagnostic options
    for the older comparison sources, but are not allowed to select a favorable
    subset from the independently identified matrix.
    """

    if correction is None:
        return ()
    if correction.metadata.get("application_contract") == "replace_with_matched_bie":
        return (("nonlinear_2dt_raw_added_and_damping", True, True, "replace_with_matched_bie"),)
    return (
        ("matched_delta_added_only", True, False, "delta_from_high_frequency"),
        ("matched_delta_damping_only", False, True, "delta_from_high_frequency"),
        ("matched_delta_added_and_damping", True, True, "delta_from_high_frequency"),
        ("matched_raw_added_only", True, False, "replace_with_matched_bie"),
        ("matched_raw_damping_only", False, True, "replace_with_matched_bie"),
        ("matched_raw_added_and_damping", True, True, "replace_with_matched_bie"),
        (
            "planing_base_plus_matched_radiation",
            True,
            True,
            "planing_base_plus_matched_radiation",
        ),
    )


def _attach_phase_resolved_excitation(
    matrix_correction: PlaningFrequencyCorrection,
    excitation_correction: PlaningFrequencyCorrection,
) -> PlaningFrequencyCorrection:
    if excitation_correction.excitation_per_wave_amplitude is None:
        raise ValueError("The excitation correction does not contain phase-resolved loads.")
    target = matrix_correction.sample_omega_rad_s
    source = excitation_correction.sample_omega_rad_s

    def interpolate(values: np.ndarray) -> np.ndarray:
        source_values = np.asarray(values, dtype=complex)
        result = np.empty((len(target), 2), dtype=complex)
        for column in range(2):
            result[:, column] = np.interp(
                target, source, source_values[:, column].real
            ) + 1j * np.interp(target, source, source_values[:, column].imag)
        return result

    components = {
        name: interpolate(values)
        for name, values in excitation_correction.excitation_components.items()
    }
    return replace(
        matrix_correction,
        excitation_per_wave_amplitude=interpolate(
            excitation_correction.excitation_per_wave_amplitude
        ),
        excitation_components=components,
        metadata={
            **matrix_correction.metadata,
            "head_sea_excitation_available": True,
            "head_sea_excitation_formulation": excitation_correction.metadata.get(
                "head_sea_excitation_formulation", "unknown"
            ),
            "head_sea_excitation_source": excitation_correction.metadata.get(
                "source", "unknown"
            ),
            "head_sea_excitation_source_metadata": excitation_correction.metadata,
            "response_calibration_used": False,
        },
    )


def _load_direct_2dt_wave_excitation(
    paths: list[Path],
) -> PlaningFrequencyCorrection:
    if not paths:
        raise ValueError(
            "--excitation-route=direct_2dt_wave_csv requires at least one "
            "--direct-wave-excitation-csv path."
        )
    resolved = [Path(path).resolve() for path in paths]
    frames = [pd.read_csv(path) for path in resolved]
    table = pd.concat(frames, ignore_index=True)
    required = {
        "case_code",
        "omega_e_rad_s",
        "component",
        "heave_force_real_n_per_m",
        "heave_force_imag_n_per_m",
        "pitch_moment_real_nm_per_m",
        "pitch_moment_imag_nm_per_m",
        "wave_amplitude_scale",
        "response_calibration_used",
    }
    missing = sorted(required - set(table.columns))
    if missing:
        raise ValueError(f"Direct-wave excitation CSV is missing columns: {missing}")
    calibrated = table["response_calibration_used"].astype(str).str.lower().isin(
        {"1", "true", "yes", "y"}
    )
    if calibrated.any():
        raise ValueError("Direct-wave excitation CSV must not use response calibration.")
    if table.duplicated(["component", "omega_e_rad_s"]).any():
        raise ValueError("Direct-wave excitation contains duplicate component-frequency rows.")
    total = table[table["component"].astype(str) == "total"].copy()
    total = total.sort_values("omega_e_rad_s")
    omega = total["omega_e_rad_s"].to_numpy(dtype=float)
    if len(omega) < 3 or np.any(np.diff(omega) <= 0.0):
        raise ValueError(
            "Direct-wave excitation needs at least three strictly increasing frequencies."
        )

    def complex_load(frame: pd.DataFrame) -> np.ndarray:
        ordered = frame.sort_values("omega_e_rad_s")
        component_omega = ordered["omega_e_rad_s"].to_numpy(dtype=float)
        if not np.allclose(component_omega, omega, rtol=0.0, atol=1.0e-10):
            raise ValueError("Every direct-wave component must cover the same frequencies.")
        return np.column_stack(
            (
                ordered["heave_force_real_n_per_m"].to_numpy(dtype=float)
                + 1j * ordered["heave_force_imag_n_per_m"].to_numpy(dtype=float),
                ordered["pitch_moment_real_nm_per_m"].to_numpy(dtype=float)
                + 1j * ordered["pitch_moment_imag_nm_per_m"].to_numpy(dtype=float),
            )
        )

    components = {
        str(name): complex_load(frame)
        for name, frame in table.groupby("component", sort=True)
    }
    excitation = components["total"]
    scales = sorted(set(table["wave_amplitude_scale"].to_numpy(dtype=float)))
    if len(scales) != 1 or not np.isfinite(scales[0]) or scales[0] <= 0.0:
        raise ValueError("Direct-wave excitation files must use one positive wave-amplitude scale.")
    hashes = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in resolved
    }
    zeros = np.zeros((len(omega), 2, 2), dtype=float)
    return PlaningFrequencyCorrection(
        sample_omega_rad_s=omega,
        high_frequency_reference_rad_s=float(omega[-1]),
        delta_added_mass=zeros,
        delta_radiation_damping=zeros,
        raw_added_mass=zeros,
        raw_radiation_damping=zeros,
        excitation_per_wave_amplitude=excitation,
        excitation_components=components,
        metadata={
            "source": "sun_faltinsen_direct_fixed_hull_2dt_wave_csv",
            "head_sea_excitation_formulation": (
                "Sun_Faltinsen_Eq3_11_to_18_21_to_22_direct_cross_plane"
            ),
            "complex_load_convention": "Re(F_hat*exp(i*omega_e*t))",
            "coordinate_convention": "heave_up_pitch_bow_up",
            "wave_amplitude_scale": scales[0],
            "linearization_role": (
                "quarter_source_amplitude_resolved_linearization_sample"
                if np.isclose(scales[0], 0.25)
                else "user_supplied_direct_wave_amplitude"
            ),
            "source_csv_sha256": hashes,
            "response_calibration_used": False,
        },
    )


def main() -> int:
    args = _parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    hull_table, motion_table, running_state_table, _, _ = _verify_begovic_sources(root)
    reference = motion_table[np.isclose(motion_table["fn_b"], args.fn_b)].copy()
    if args.case_code:
        requested_codes = [str(value) for value in args.case_code]
        if len(set(requested_codes)) != len(requested_codes):
            raise ValueError("--case-code values must be unique.")
        available_codes = set(reference["case_code"].astype(str))
        missing_codes = sorted(set(requested_codes) - available_codes)
        if missing_codes:
            raise ValueError(f"Unknown Begovic case codes for Fn_B={args.fn_b:g}: {missing_codes}.")
        reference = reference[reference["case_code"].astype(str).isin(requested_codes)].copy()
        if len(reference) < 3:
            raise ValueError("A frequency-correction screening requires at least three cases.")
    boat = _boat(hull_table.iloc[0])
    speed = float(reference["speed_m_s"].iloc[0])
    if args.frequency_coordinate_route == "source_encounter":
        source_encounter = reference["encounter_omega_rad_s"].to_numpy(dtype=float)
        consistent_wavenumber, _ = head_sea_wavenumber_from_encounter_frequency(
            source_encounter,
            speed,
            boat.gravity_m_s2,
        )
        reference["response_wavelength_m"] = 2.0 * np.pi / consistent_wavenumber
    else:
        reference["response_wavelength_m"] = reference["wavelength_m"].to_numpy(
            dtype=float
        )
    running_row = running_state_table[np.isclose(running_state_table["fn_b"], args.fn_b)].iloc[0]
    equilibrium = make_prescribed_equilibrium(
        boat,
        speed,
        PrescribedRunningStateConfig(
            enabled=True,
            trim_deg=float(running_row["running_trim_deg"]),
            lambda_w=float(running_row["mean_wetted_length_m"]) / boat.beam_m,
        ),
    )
    options = MomentumStripOptions(
        station_count=401,
        momentum_rate_formulation=args.momentum_rate_formulation,
    )
    response_lambda_over_l = reference["response_wavelength_m"].to_numpy(dtype=float) / boat.length_m
    dense_lambda_over_l = np.linspace(
        float(response_lambda_over_l.min()),
        float(response_lambda_over_l.max()),
        241,
    )

    phase_length = {
        "overall": boat.length_m,
        "keel": equilibrium.geometry.keel_wetted_length_m,
        "mean": equilibrium.geometry.lambda_w * boat.beam_m,
        "chine": max(equilibrium.geometry.chine_wetted_length_m, 1.0e-6),
    }[args.phase_length_route]

    def build_base(wavelength_m: np.ndarray, wave_amplitude_m: np.ndarray | float):
        if args.base_route == "zarnick_full":
            return build_linearized_momentum_strip_model(
                boat,
                equilibrium,
                wavelength_m,
                wave_amplitude_m,
                point_x_forward_m=boat.length_m - boat.lcg_m,
                options=options,
            )
        matrices = compute_hydro_matrices(boat, equilibrium)
        if args.restoring_route != "savitsky_dynamic_lift":
            hydrostatic_restoring = assemble_planing_wetted_hydrostatic_restoring(
                boat,
                equilibrium,
                station_count=max(args.station_count * 8 + 1, 121),
                wagner_pileup_factor=args.wagner_pileup_factor,
            )
            restoring = hydrostatic_restoring
            if args.restoring_route == "savitsky_plus_mean_wetted_hydrostatic":
                restoring = matrices.restoring + hydrostatic_restoring
            matrices = replace(matrices, restoring=restoring)
        if args.base_route == "faltinsen_ch9_zarnick_damping":
            zarnick = linearize_momentum_strip(boat, equilibrium, options)
            matrices = replace(matrices, damping=zarnick.damping)
        model = build_faltinsen_planing_model(
            boat,
            equilibrium,
            matrices,
            wavelength_m,
            wave_amplitude_m,
            point_x_forward_m=boat.length_m - boat.lcg_m,
            phase_length_m=phase_length,
            metadata={"diagnostic_base_route": args.base_route},
        )
        if args.excitation_route == "momentum_station_phase":
            excitation = momentum_strip_wave_excitation_per_amplitude(
                boat,
                equilibrium,
                options,
                linearize_momentum_strip(boat, equilibrium, options).station_x_from_transom_m,
                model.wavenumber_rad_m,
                model.omega0_rad_s,
                model.hydrodynamics.encounter_omega_rad_s,
            )
            model = replace(
                model,
                excitation_per_wave_amplitude=excitation,
                metadata={
                    **model.metadata,
                    "excitation_formulation": "zarnick1978_local_strip_wave_amplitude_derivative",
                    "excitation_station_phase_retained": True,
                    "wave_vertical_acceleration_frequency_product": "omega_0_times_omega_e",
                    "response_calibration_used": False,
                },
            )
        return model

    base_reference = build_base(
        reference.sort_values("lambda_over_l")["response_wavelength_m"].to_numpy(dtype=float),
        reference.sort_values("lambda_over_l")["wave_amplitude_m"].to_numpy(dtype=float),
    )
    base_dense = build_base(dense_lambda_over_l * boat.length_m, 0.01)
    min_omega = float(base_dense.hydrodynamics.solver_omega_rad_s.min())
    max_omega = float(base_dense.hydrodynamics.solver_omega_rad_s.max())
    sample_omega = np.geomspace(min_omega, max_omega, args.frequency_samples)
    high_omega = 1.8 * max_omega
    correction = None
    if args.hydrodynamic_correction_source == "matched_bie":
        correction = compute_matched_bie_frequency_correction(
            boat,
            equilibrium,
            sample_omega,
            high_frequency_reference_rad_s=high_omega,
            station_count=args.station_count,
            body_panels_per_section=args.body_panels,
            free_surface_inner_panels=args.inner_panels,
            free_surface_outer_panels=args.outer_panels,
            force_component_route=args.force_component_route,
            wagner_pileup_factor=args.wagner_pileup_factor,
            restoring_matrix=(
                base_reference.restoring[0]
                if args.excitation_route
                in {
                    "matched_bie_station_phase",
                    "section_bem_station_phase",
                    "matched_domain_station_phase",
                }
                else None
            ),
            transom_force_cutoff_length_beams=args.transom_force_cutoff_length_beams,
            transom_force_recovery_profile=args.transom_force_recovery_profile,
            head_sea_excitation_formulation=(
                "section_bem_incident_diffraction"
                if args.excitation_route == "section_bem_station_phase"
                else (
                    "matched_domain_incident_diffraction"
                    if args.excitation_route == "matched_domain_station_phase"
                    else "equivalent_radiation"
                )
            ),
        )
    elif args.hydrodynamic_correction_source == "section_bem":
        correction = compute_section_bem_frequency_correction(
            boat,
            equilibrium,
            sample_omega,
            high_frequency_reference_rad_s=high_omega,
            station_count=args.station_count,
            body_panels_per_section=args.body_panels,
            free_surface_panels_per_side=args.inner_panels,
            wagner_pileup_factor=args.wagner_pileup_factor,
        )
    elif args.hydrodynamic_correction_source == "nonlinear_2dt_csv":
        if not args.forced_motion_csv:
            raise ValueError(
                "--hydrodynamic-correction-source=nonlinear_2dt_csv requires at least one "
                "--forced-motion-csv path."
            )
        correction = load_nonlinear_2dt_forced_motion_correction(
            args.forced_motion_csv,
            restoring_matrices_path=args.forced_motion_restoring_csv,
            require_target_context=True,
        )
        if args.excitation_route == "direct_2dt_wave_csv":
            correction = _attach_phase_resolved_excitation(
                correction,
                _load_direct_2dt_wave_excitation(args.direct_wave_excitation_csv),
            )
        if args.excitation_route in {
            "matched_bie_station_phase",
            "section_bem_station_phase",
            "matched_domain_station_phase",
        }:
            final_restoring = (
                correction.raw_restoring[0]
                if correction.raw_restoring is not None
                else base_reference.restoring[0]
            )
            excitation_correction = compute_matched_bie_frequency_correction(
                boat,
                equilibrium,
                correction.sample_omega_rad_s,
                high_frequency_reference_rad_s=(
                    1.8 * float(correction.sample_omega_rad_s.max())
                ),
                station_count=args.station_count,
                body_panels_per_section=args.body_panels,
                free_surface_inner_panels=args.inner_panels,
                free_surface_outer_panels=args.outer_panels,
                force_component_route="total_eq32_stokes_body_plus_end",
                wagner_pileup_factor=args.wagner_pileup_factor,
                restoring_matrix=final_restoring,
                transom_force_cutoff_length_beams=args.transom_force_cutoff_length_beams,
                transom_force_recovery_profile=args.transom_force_recovery_profile,
                head_sea_excitation_formulation=(
                    "section_bem_incident_diffraction"
                    if args.excitation_route == "section_bem_station_phase"
                    else (
                        "matched_domain_incident_diffraction"
                        if args.excitation_route == "matched_domain_station_phase"
                        else "equivalent_radiation"
                    )
                ),
            )
            correction = _attach_phase_resolved_excitation(
                correction,
                excitation_correction,
            )
    elif args.hydrodynamic_correction_source.startswith("sun2007_"):
        variant = (
            "sun_2dt_without_stern_3d_correction"
            if args.hydrodynamic_correction_source == "sun2007_uncorrected"
            else "sun_2dt_with_stern_3d_correction"
        )
        correction = _sun2007_troesch_diagnostic_correction(root, boat, variant)
    base_reference_response = solve_longitudinal_frequency_response(base_reference)
    base_dense_response = solve_longitudinal_frequency_response(base_dense)
    base_comparison = _comparison(reference, base_reference_response)
    base_metrics = _motion_metrics(base_comparison, scope=args.base_route)
    base_dense_response["configuration"] = f"FnB={args.fn_b:.2f}"
    base_dense_response["lambda_over_l"] = dense_lambda_over_l
    base_peaks = _begovic_peak_metrics(base_comparison, base_dense_response)

    route_specs = _correction_route_specs(correction)
    if args.excitation_route in {
        "matched_bie_station_phase",
        "section_bem_station_phase",
        "matched_domain_station_phase",
        "direct_2dt_wave_csv",
    }:
        matrix_application = args.phase_resolved_matrix_application
        matrix_route_suffix = {
            "replace_with_matched_bie": "matched_raw",
            "planing_base_plus_matched_radiation": "planing_base_plus_matched_radiation",
            "delta_from_high_frequency": "planing_base_plus_matched_delta",
            "planing_high_frequency_added_plus_matched_damping": (
                "planing_high_frequency_added_plus_matched_damping"
            ),
        }[matrix_application]
        corrected_route = (
            f"{matrix_route_suffix}_direct_2dt_wave_excitation"
            if args.excitation_route == "direct_2dt_wave_csv"
            else
            f"{matrix_route_suffix}_section_bem_excitation"
            if args.excitation_route == "section_bem_station_phase"
            else (
                f"{matrix_route_suffix}_matched_domain_excitation"
                if args.excitation_route == "matched_domain_station_phase"
                else f"{matrix_route_suffix}_station_phase_excitation"
            )
        )
        route_specs = (
            (
                corrected_route,
                True,
                True,
                matrix_application,
            ),
        )
    comparisons = {args.base_route: base_comparison}
    dense_responses = {args.base_route: base_dense_response}
    reference_models = {args.base_route: base_reference}
    metric_frames = [base_metrics]
    peak_frames = [base_peaks.assign(route=args.base_route)]
    if correction is not None:
        for route, include_added, include_damping, application_mode in route_specs:
            corrected_reference = apply_frequency_correction(
                base_reference,
                correction,
                include_added_mass=include_added,
                include_radiation_damping=include_damping,
                application_mode=application_mode,
                recompute_faltinsen_excitation=args.excitation_route == "faltinsen_global",
                use_phase_resolved_excitation=(
                    args.excitation_route
                    in {
                        "matched_bie_station_phase",
                        "section_bem_station_phase",
                        "matched_domain_station_phase",
                        "direct_2dt_wave_csv",
                    }
                ),
            )
            corrected_dense = apply_frequency_correction(
                base_dense,
                correction,
                include_added_mass=include_added,
                include_radiation_damping=include_damping,
                application_mode=application_mode,
                recompute_faltinsen_excitation=args.excitation_route == "faltinsen_global",
                use_phase_resolved_excitation=(
                    args.excitation_route
                    in {
                        "matched_bie_station_phase",
                        "section_bem_station_phase",
                        "matched_domain_station_phase",
                        "direct_2dt_wave_csv",
                    }
                ),
            )
            reference_response = solve_longitudinal_frequency_response(corrected_reference)
            dense_response = solve_longitudinal_frequency_response(corrected_dense)
            dense_response["configuration"] = f"FnB={args.fn_b:.2f}"
            dense_response["lambda_over_l"] = dense_lambda_over_l
            comparison = _comparison(reference, reference_response)
            comparisons[route] = comparison
            dense_responses[route] = dense_response
            reference_models[route] = corrected_reference
            metric_frames.append(_motion_metrics(comparison, scope=route))
            peak_frames.append(_begovic_peak_metrics(comparison, dense_response).assign(route=route))

    base_comparison.to_csv(output / "base_comparison.csv", index=False)
    base_dense_response.to_csv(output / "base_dense_response.csv", index=False)
    for route, frame in comparisons.items():
        if route != args.base_route:
            frame.to_csv(output / f"{route}_comparison.csv", index=False)
    for route, frame in dense_responses.items():
        if route != args.base_route:
            frame.to_csv(output / f"{route}_dense_response.csv", index=False)
    all_metrics = pd.concat(metric_frames, ignore_index=True)
    all_peaks = pd.concat(peak_frames, ignore_index=True)
    all_metrics.to_csv(output / "motion_metrics.csv", index=False)
    all_peaks.to_csv(output / "peak_metrics.csv", index=False)
    model_term_rows: list[dict[str, object]] = []
    modal_diagnostic_rows: list[dict[str, object]] = []
    configuration = f"FnB={args.fn_b:.2f}"
    for route, model in reference_models.items():
        model_term_rows.extend(_model_term_rows(route, configuration, model))
        modal_diagnostic_rows.extend(
            _modal_diagnostic_rows(route, configuration, model)
        )
    pd.DataFrame(model_term_rows).to_csv(output / "response_model_terms.csv", index=False)
    pd.DataFrame(modal_diagnostic_rows).to_csv(
        output / "modal_diagnostics.csv",
        index=False,
    )
    if correction is not None:
        rows = []
        for index, omega in enumerate(correction.sample_omega_rad_s):
            for matrix_name, matrix in (
                ("raw_added_mass", correction.raw_added_mass[index]),
                ("raw_radiation_damping", correction.raw_radiation_damping[index]),
                ("delta_added_mass", correction.delta_added_mass[index]),
                ("delta_radiation_damping", correction.delta_radiation_damping[index]),
            ):
                for row in range(2):
                    for column in range(2):
                        rows.append(
                            {
                                "omega_e_rad_s": omega,
                                "matrix": matrix_name,
                                "row": ("heave", "pitch")[row],
                                "column": ("heave", "pitch")[column],
                                "value": float(matrix[row, column]),
                            }
                        )
        pd.DataFrame(rows).to_csv(output / "frequency_correction.csv", index=False)
    summary = {
        "fn_b": args.fn_b,
        "speed_mps": speed,
        "running_trim_deg": equilibrium.trim_deg,
        "mean_wetted_length_over_b": equilibrium.geometry.lambda_w,
        "keel_wetted_length_m": equilibrium.geometry.keel_wetted_length_m,
        "reported_mean_wetted_length_m": float(running_row["mean_wetted_length_m"]),
        "base_route": args.base_route,
        "phase_length_route": args.phase_length_route,
        "frequency_coordinate_route": args.frequency_coordinate_route,
        "phase_length_m": phase_length,
        "restoring_route": args.restoring_route,
        "force_component_route": args.force_component_route,
        "hydrodynamic_correction_source": args.hydrodynamic_correction_source,
        "forced_motion_csv": [str(path.resolve()) for path in args.forced_motion_csv],
        "direct_wave_excitation_csv": [
            str(path.resolve()) for path in args.direct_wave_excitation_csv
        ],
        "excitation_route": args.excitation_route,
        "phase_resolved_matrix_application": args.phase_resolved_matrix_application,
        "wagner_pileup_factor": args.wagner_pileup_factor,
        "transom_force_cutoff_length_beams": args.transom_force_cutoff_length_beams,
        "transom_force_recovery_profile": args.transom_force_recovery_profile,
        "momentum_rate_formulation": args.momentum_rate_formulation,
        "sample_omega_rad_s": (
            correction.sample_omega_rad_s.tolist() if correction is not None else []
        ),
        "high_frequency_reference_rad_s": high_omega if correction is not None else None,
        "correction_metadata": correction.metadata if correction is not None else None,
        "response_calibration_used": False,
    }
    (output / "probe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(all_metrics.to_string(index=False))
    print(
        all_peaks[
            ["route", "configuration", "metric", "peak_frequency_relative_error", "status"]
        ].to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
