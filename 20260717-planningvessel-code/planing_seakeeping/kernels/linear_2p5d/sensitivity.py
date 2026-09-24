from __future__ import annotations

from dataclasses import dataclass, replace
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

from ...schema import Linear2p5DProviderConfig
from ...station_2p5d import RigidBody6DOF, make_wigley_iii_hull
from .formulation import (
    DEFAULT_A1_HEAVE_PITCH_CONVENTION,
    assemble_frequency_domain_from_matched_station_hull,
    audit_closed_cylinder_heave_added_mass,
    audit_control_history_inheritance,
    audit_free_surface_oscillator_marching,
    audit_inner_free_surface_state_scale,
    audit_inner_kernel_green_identity,
    audit_inner_mixed_boundary_green_identity,
    audit_heave_pitch_a1_convention,
    audit_history_rhs_quadrature_convergence,
    audit_outer_control_balance,
    audit_outer_control_surface_green_identity,
    audit_rhs_source_decomposition,
    audit_transient_history_kernel_normal_derivative,
    build_closed_ellipse_inner_boundary,
    build_control_surface_geometry,
    closed_boundary_three_part_panel_counts,
    heave_radiation_normal_velocity,
    solve_station_hull_heave_pitch_matched_sweep,
    split_inner_boundary_geometry_by_panel_counts,
)


MATCHED_WIGLEY_SENSITIVITY_STATUS = "diagnostic_matched_wigley_sensitivity_not_hard_gate"
A1_CONVENTION_CANDIDATE_STATUS = "diagnostic_a1_convention_candidate_not_hard_gate"
A1_CONTROL_SURFACE_CANDIDATE_STATUS = "diagnostic_a1_control_surface_candidate_not_hard_gate"
A1_INNER_KERNEL_CANDIDATE_STATUS = "diagnostic_a1_inner_kernel_candidate_not_hard_gate"
A1_POTENTIAL_UNIT_CLOSURE_STATUS = "diagnostic_a1_potential_unit_closure_not_hard_gate"
A1_INNER_KERNEL_GREEN_IDENTITY_STATUS = "diagnostic_a1_inner_kernel_green_identity_not_hard_gate"
A1_CLOSED_CYLINDER_ADDED_MASS_STATUS = "diagnostic_a1_closed_cylinder_added_mass_not_hard_gate"
A1_INNER_MIXED_BOUNDARY_STATUS = "diagnostic_a1_inner_mixed_boundary_identity_not_hard_gate"
A1_FREE_SURFACE_OSCILLATOR_STATUS = "diagnostic_a1_free_surface_eq19_22_oscillator_not_hard_gate"
A1_CONTROL_SURFACE_GREEN_IDENTITY_STATUS = "diagnostic_a1_eq24_outer_control_green_identity_not_hard_gate"
A1_HISTORY_KERNEL_DERIVATIVE_STATUS = "diagnostic_a1_eq28_history_kernel_normal_derivative_not_hard_gate"
A1_HISTORY_RHS_CONVERGENCE_STATUS = "diagnostic_a1_eq24_history_rhs_quadrature_convergence_not_hard_gate"
A1_INNER_FREE_SURFACE_STATE_STATUS = "diagnostic_a1_inner_free_surface_state_scale_marching_not_hard_gate"
A1_CONTROL_HISTORY_INHERITANCE_STATUS = "diagnostic_a1_eq24_station_control_history_inheritance_not_hard_gate"
A1_OUTER_CONTROL_BALANCE_STATUS = "diagnostic_a1_eq24_outer_control_balance_scale_phase_not_hard_gate"
A1_RHS_SOURCE_DECOMPOSITION_STATUS = "diagnostic_a1_eq23_eq24_rhs_source_decomposition_not_hard_gate"
A1_RECOMMENDED_CONTROL_RADIUS_BEAMS = 3.0
A1_MIN_INNER_FREE_SURFACE_PANELS = 11
A1_MIN_OUTER_OR_CONTROL_PANELS = 9
A1_LOW_FN_STATION_MIN = 60
A1_MODERATE_FN_STATION_MIN = 40

_SUMMARY_NUMERIC_COLUMNS = (
    "gate_error_ratio",
    "abs_error",
    "rel_error",
    "max_heave_residual",
    "max_pitch_residual",
    "max_heave_condition_number",
    "max_pitch_condition_number",
)


@dataclass(frozen=True)
class MatchedWigleySensitivityCase:
    name: str
    station_count: int = 5
    body_panels_per_section: int = 8
    free_surface_inner_panels: int = 4
    free_surface_outer_panels: int = 4
    control_surface_radius_beams: float = 2.0
    history_steps: int = 2
    history_quadrature_count: int = 16
    history_k_max: float = 15.0
    include_end_term: bool = True
    end_station: str = "aft"
    end_term_scale: float = 1.0
    pitch_radiation_sign: float = 1.0
    pitch_radiation_lever_sign: float = 1.0
    pitch_forward_speed_sign: float = 1.0
    pitch_moment_sign: float = 1.0
    time_step_scale: float = 1.0
    free_surface_velocity_scale: float = 1.0
    history_rhs_scale: float = 1.0
    history_convolution_rule: str = "trapezoid"
    history_potential_kernel_scale: float = 1.0
    history_normal_derivative_kernel_scale: float = 1.0
    control_image_scale: float = 1.0
    control_potential_kernel_scale: float = 1.0
    control_normal_derivative_kernel_scale: float = 1.0
    control_diagonal_sign: float = 1.0
    inner_a_scale: float = 1.0
    inner_b_scale: float = 1.0
    inner_diagonal_sign: float = -1.0
    pressure_gradient_scheme: str = "central"
    pressure_gradient_scale: float = 1.0
    force_assembly_route: str = "current_hybrid_pressure_gradient_plus_end"
    apply_local_time_phase: bool = False
    local_time_phase_gradient_correction: bool = False
    clip_inner_free_surface_to_waterline: bool = False
    two_zone_inner_free_surface: bool = False
    use_free_surface_marching: bool = True

    def config(self) -> Linear2p5DProviderConfig:
        return Linear2p5DProviderConfig(
            hull_stations=int(self.station_count),
            body_panels_per_section=int(self.body_panels_per_section),
            free_surface_inner_panels=int(self.free_surface_inner_panels),
            free_surface_outer_panels=int(self.free_surface_outer_panels),
            control_surface_radius_beams=float(self.control_surface_radius_beams),
            include_end_terms=bool(self.include_end_term),
        )


@dataclass(frozen=True)
class A1ConventionCandidate:
    """One controlled paper-to-package heave/pitch convention hypothesis.

    The candidate wraps the existing sensitivity case switches and gives them a
    narrower interpretation: each candidate corresponds to a documented change
    in the A1 mapping table, not an arbitrary tuning knob. These rows remain
    diagnostic until the four Wigley III Gate 1 coefficients pass together.
    """

    name: str
    case: MatchedWigleySensitivityCase
    changed_mapping_rows: tuple[str, ...]
    hypothesis: str
    description: str
    status: str = A1_CONVENTION_CANDIDATE_STATUS

    def metadata_row(self) -> dict[str, str | float | int | bool]:
        """Return one CSV-friendly metadata row."""

        return {
            "a1_convention_candidate_name": self.name,
            "a1_convention_candidate_status": self.status,
            "a1_convention_changed_mapping_rows": ";".join(self.changed_mapping_rows),
            "a1_convention_hypothesis": self.hypothesis,
            "a1_convention_description": self.description,
            "case_name": self.case.name,
            "pitch_radiation_sign": float(self.case.pitch_radiation_sign),
            "pitch_radiation_lever_sign": float(self.case.pitch_radiation_lever_sign),
            "pitch_forward_speed_sign": float(self.case.pitch_forward_speed_sign),
            "pitch_moment_sign": float(self.case.pitch_moment_sign),
            "default_convention_name": DEFAULT_A1_HEAVE_PITCH_CONVENTION.name,
            "default_convention_status": DEFAULT_A1_HEAVE_PITCH_CONVENTION.validity.status,
        }


@dataclass(frozen=True)
class A1ControlSurfaceCandidate:
    """One controlled A1 Eq. (24) instantaneous control-surface hypothesis."""

    name: str
    case: MatchedWigleySensitivityCase
    changed_eq24_terms: tuple[str, ...]
    hypothesis: str
    description: str
    status: str = A1_CONTROL_SURFACE_CANDIDATE_STATUS

    def metadata_row(self) -> dict[str, str | float | int | bool]:
        """Return one CSV-friendly metadata row."""

        return {
            "a1_control_candidate_name": self.name,
            "a1_control_candidate_status": self.status,
            "a1_control_changed_eq24_terms": ";".join(self.changed_eq24_terms),
            "a1_control_hypothesis": self.hypothesis,
            "a1_control_description": self.description,
            "case_name": self.case.name,
            "control_image_scale": float(self.case.control_image_scale),
            "control_potential_kernel_scale": float(self.case.control_potential_kernel_scale),
            "control_normal_derivative_kernel_scale": float(self.case.control_normal_derivative_kernel_scale),
            "control_diagonal_sign": float(self.case.control_diagonal_sign),
            "history_convolution_rule": str(self.case.history_convolution_rule).strip().lower(),
        }


@dataclass(frozen=True)
class A1InnerKernelCandidate:
    """One controlled A1 Eq. (23) inner-domain kernel normalization hypothesis."""

    name: str
    case: MatchedWigleySensitivityCase
    changed_eq23_terms: tuple[str, ...]
    hypothesis: str
    description: str
    status: str = A1_INNER_KERNEL_CANDIDATE_STATUS

    def metadata_row(self) -> dict[str, str | float | int | bool]:
        """Return one CSV-friendly metadata row."""

        return {
            "a1_inner_candidate_name": self.name,
            "a1_inner_candidate_status": self.status,
            "a1_inner_changed_eq23_terms": ";".join(self.changed_eq23_terms),
            "a1_inner_hypothesis": self.hypothesis,
            "a1_inner_description": self.description,
            "case_name": self.case.name,
            "inner_a_scale": float(self.case.inner_a_scale),
            "inner_b_scale": float(self.case.inner_b_scale),
            "inner_diagonal_sign": float(self.case.inner_diagonal_sign),
        }


def a1_convention_candidate_cases(
    base_case: MatchedWigleySensitivityCase | None = None,
) -> tuple[A1ConventionCandidate, ...]:
    """Return a small controlled set of A1 heave/pitch mapping candidates.

    The candidates are deliberately few. They cover the sign/lever rows that
    prior diagnostics showed can move A35/A55, while leaving the default
    production path untouched.
    """

    base = base_case or MatchedWigleySensitivityCase(
        name="a1conv_base",
        station_count=41,
        body_panels_per_section=8,
        free_surface_inner_panels=12,
        free_surface_outer_panels=10,
        control_surface_radius_beams=3.0,
        history_steps=2,
        history_quadrature_count=16,
        history_k_max=15.0,
        clip_inner_free_surface_to_waterline=True,
    )
    prefix = str(base.name).strip() or "a1conv_base"

    def candidate(
        suffix: str,
        *,
        changed_rows: tuple[str, ...],
        hypothesis: str,
        description: str,
        **case_updates: float | bool | int | str,
    ) -> A1ConventionCandidate:
        return A1ConventionCandidate(
            name=suffix,
            case=replace(base, name=f"{prefix}__{suffix}", **case_updates),
            changed_mapping_rows=changed_rows,
            hypothesis=hypothesis,
            description=description,
        )

    return (
        candidate(
            "default_mapping",
            changed_rows=(),
            hypothesis="Use the current z-down/heave-up/LCG-minus-x mapping exactly as implemented.",
            description="Neutral control case. It proves that the candidate workflow does not alter the default result.",
        ),
        candidate(
            "reverse_n5_and_pitch_row",
            changed_rows=("N5", "pitch pressure row", "Eq.32 end contour term"),
            hypothesis="Treat the A1 pitch lever row as opposite to the current package lever convention.",
            description=(
                "Flips both the pitch body-condition lever and the pitch generalized force row, so N5 and "
                "the pressure moment remain internally paired."
            ),
            pitch_radiation_lever_sign=-1.0,
            pitch_moment_sign=-1.0,
        ),
        candidate(
            "reverse_m5_forward_speed",
            changed_rows=("m5",),
            hypothesis="Treat the A1 m5 forward-speed body-condition sign as opposite to the current mapping.",
            description=(
                "Only the pitch forward-speed term in the body condition is reversed. The pressure moment row "
                "is kept at the default sign, isolating the m5 channel."
            ),
            pitch_forward_speed_sign=-1.0,
        ),
        candidate(
            "reverse_pitch_force_row",
            changed_rows=("pitch pressure row", "Eq.32 body term", "Eq.32 end contour term"),
            hypothesis="Treat the package-reported pitch moment as the negative of the current generalized row.",
            description=(
                "Flips the pressure-integration pitch row and Stokes pitch row without changing the pitch body "
                "condition, isolating output moment convention from radiation boundary data."
            ),
            pitch_moment_sign=-1.0,
        ),
        candidate(
            "reverse_all_pitch_rows",
            changed_rows=("N5", "m5", "pitch pressure row", "Eq.32 body term", "Eq.32 end contour term"),
            hypothesis="Treat all pitch-related A1 rows as reversed relative to the current package mapping.",
            description=(
                "A deliberately broad sign candidate for auditing only. It should not be adopted unless the "
                "joint A33/A35/A53/A55 gate passes and the paper mapping rows justify it."
            ),
            pitch_radiation_lever_sign=-1.0,
            pitch_forward_speed_sign=-1.0,
            pitch_moment_sign=-1.0,
        ),
    )


def a1_inner_kernel_candidate_cases(
    base_case: MatchedWigleySensitivityCase | None = None,
) -> tuple[A1InnerKernelCandidate, ...]:
    """Return controlled A1 Eq. (23) inner-kernel normalization candidates."""

    base = base_case or MatchedWigleySensitivityCase(
        name="a1inner_base",
        station_count=41,
        body_panels_per_section=8,
        free_surface_inner_panels=12,
        free_surface_outer_panels=10,
        control_surface_radius_beams=3.0,
        history_steps=2,
        history_quadrature_count=16,
        history_k_max=15.0,
        clip_inner_free_surface_to_waterline=True,
    )
    prefix = str(base.name).strip() or "a1inner_base"
    inv_2pi = 1.0 / (2.0 * math.pi)

    def candidate(
        suffix: str,
        *,
        changed_terms: tuple[str, ...],
        hypothesis: str,
        description: str,
        **case_updates: float | bool | int | str,
    ) -> A1InnerKernelCandidate:
        return A1InnerKernelCandidate(
            name=suffix,
            case=replace(base, name=f"{prefix}__{suffix}", **case_updates),
            changed_eq23_terms=changed_terms,
            hypothesis=hypothesis,
            description=description,
        )

    return (
        candidate(
            "raw_eq25_default",
            changed_terms=(),
            hypothesis="Use A1 Eq. (25) raw log kernels and Eq. (23) alpha=1 self term -pi.",
            description="Neutral control case matching the paper's written Aij/Bij definitions.",
        ),
        candidate(
            "normalize_a_and_b_by_2pi",
            changed_terms=("Aij", "Bij", "Eq.23 self term"),
            hypothesis="Apply the simple-Green 1/(2*pi) normalization to all Eq. (23) A/B kernels.",
            description=(
                "This should mostly behave like row scaling if applied consistently; it checks whether "
                "the raw-vs-normalized convention alone can explain coefficient magnitude."
            ),
            inner_a_scale=inv_2pi,
            inner_b_scale=inv_2pi,
        ),
        candidate(
            "normalize_a_only_by_2pi",
            changed_terms=("Aij", "Eq.23 self term"),
            hypothesis="Only the normal-derivative Aij block was accidentally normalized by 1/(2*pi).",
            description="Changes the relative scale between potential and normal-derivative unknowns in Eq. (23).",
            inner_a_scale=inv_2pi,
        ),
        candidate(
            "normalize_b_only_by_2pi",
            changed_terms=("Bij",),
            hypothesis="Only the potential Bij block was accidentally normalized by 1/(2*pi).",
            description="Changes the relative scale between Aij and Bij while leaving the Eq. (23) self term raw.",
            inner_b_scale=inv_2pi,
        ),
        candidate(
            "positive_eq23_self_term",
            changed_terms=("Eq.23 self term",),
            hypothesis="Use +pi instead of -pi for Eq. (23), as if alpha were interpreted like Eq. (24).",
            description="Diagnostic for a self-term sign mismatch; A1 text says alpha=1 in Eq. (23), so this is not default.",
            inner_diagonal_sign=1.0,
        ),
        candidate(
            "reverse_a_operator",
            changed_terms=("Aij", "Eq.23 self term"),
            hypothesis="Reverse the Eq. (23) normal-derivative operator sign.",
            description="Checks a broad normal-direction sign mismatch in the inner A block.",
            inner_a_scale=-1.0,
        ),
        candidate(
            "reverse_b_operator",
            changed_terms=("Bij",),
            hypothesis="Reverse the Eq. (23) log-potential operator sign.",
            description="Checks a broad sign mismatch in the inner B block.",
            inner_b_scale=-1.0,
        ),
    )


def a1_inner_kernel_green_identity_rows(
    *,
    candidates: tuple[A1InnerKernelCandidate, ...] | None = None,
    panel_counts: tuple[int, ...] | list[int] = (32, 64, 128),
    potential_names: tuple[str, ...] | list[str] = ("linear_y", "linear_z", "quadratic_y2_minus_z2", "cross_yz"),
    semiaxis_y_m: float = 1.0,
    semiaxis_z_m: float = 0.5,
    relative_tolerance: float = 0.08,
) -> list[dict[str, float | int | str | bool]]:
    """Return closed-boundary Green-identity rows for A1 Eq. (23) inner kernels."""

    candidate_set = candidates or a1_inner_kernel_candidate_cases(
        MatchedWigleySensitivityCase(name="inner_green_identity_base")
    )
    counts = tuple(int(value) for value in panel_counts)
    if not counts or any(value < 12 for value in counts):
        raise ValueError("panel_counts must contain values of at least 12.")
    potentials = tuple(str(value).strip().lower() for value in potential_names)
    if not potentials:
        raise ValueError("At least one potential_name is required.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    rows: list[dict[str, float | int | str | bool]] = []
    for panel_count in counts:
        geometry = build_closed_ellipse_inner_boundary(
            semiaxis_y_m=float(semiaxis_y_m),
            semiaxis_z_m=float(semiaxis_z_m),
            panel_count=panel_count,
        )
        for potential in potentials:
            for candidate in candidate_set:
                audit = audit_inner_kernel_green_identity(
                    geometry,
                    potential_name=potential,
                    geometry_name="closed_ellipse",
                    inner_a_scale=float(candidate.case.inner_a_scale),
                    inner_b_scale=float(candidate.case.inner_b_scale),
                    inner_diagonal_sign=float(candidate.case.inner_diagonal_sign),
                )
                passed = bool(audit.relative_residual <= tolerance)
                rows.append(
                    {
                        "a1_inner_candidate_name": candidate.name,
                        "a1_inner_candidate_status": candidate.status,
                        "a1_inner_green_identity_status": A1_INNER_KERNEL_GREEN_IDENTITY_STATUS,
                        "a1_inner_green_identity_validity_status": audit.validity.status,
                        "a1_inner_changed_eq23_terms": ";".join(candidate.changed_eq23_terms),
                        "a1_inner_hypothesis": candidate.hypothesis,
                        "geometry_name": audit.geometry_name,
                        "potential_name": audit.potential_name,
                        "panel_count": int(audit.panel_count),
                        "semiaxis_y_m": float(semiaxis_y_m),
                        "semiaxis_z_m": float(semiaxis_z_m),
                        "inner_a_scale": float(audit.inner_a_scale),
                        "inner_b_scale": float(audit.inner_b_scale),
                        "inner_diagonal_sign": float(audit.inner_diagonal_sign),
                        "residual_norm": float(audit.residual_norm),
                        "relative_residual": float(audit.relative_residual),
                        "max_abs_residual": float(audit.max_abs_residual),
                        "phi_norm": float(audit.phi_norm),
                        "phi_n_norm": float(audit.phi_n_norm),
                        "a_phi_norm": float(audit.a_phi_norm),
                        "b_phi_n_norm": float(audit.b_phi_n_norm),
                        "relative_tolerance": tolerance,
                        "diagnostic_status": "PASS" if passed else "FAIL",
                        "gate_role": A1_INNER_KERNEL_GREEN_IDENTITY_STATUS,
                        "is_hard_gate": False,
                    }
                )
    return rows


def a1_closed_cylinder_added_mass_rows(
    *,
    panel_counts: tuple[int, ...] | list[int] = (64, 128, 256),
    radius_m: float = 1.0,
    omega_rad_s: float = 2.0,
    rho_water_kg_m3: float = 1000.0,
    corrected_relative_tolerance: float = 0.02,
) -> list[dict[str, float | int | str | bool]]:
    """Return closed-cylinder added-mass rows for the inner pressure chain."""

    counts = tuple(int(value) for value in panel_counts)
    if not counts or any(value < 24 for value in counts):
        raise ValueError("panel_counts must contain values of at least 24.")
    tolerance = float(corrected_relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("corrected_relative_tolerance must be positive and finite.")
    rows: list[dict[str, float | int | str | bool]] = []
    for panel_count in counts:
        audit = audit_closed_cylinder_heave_added_mass(
            radius_m=float(radius_m),
            panel_count=panel_count,
            omega_rad_s=float(omega_rad_s),
            rho_water_kg_m3=float(rho_water_kg_m3),
        )
        corrected_pass = bool(audit.pressure_sign_corrected_relative_error <= tolerance)
        raw_sign = "negative" if audit.computed_added_mass_ratio < 0.0 else "positive"
        rows.append(
            {
                "a1_closed_cylinder_added_mass_status": A1_CLOSED_CYLINDER_ADDED_MASS_STATUS,
                "a1_closed_cylinder_added_mass_validity_status": audit.validity.status,
                "radius_m": float(audit.radius_m),
                "panel_count": int(audit.panel_count),
                "omega_rad_s": float(audit.omega_rad_s),
                "rho_water_kg_m3": float(audit.rho_water_kg_m3),
                "expected_added_mass_per_m": float(audit.expected_added_mass_per_m),
                "computed_added_mass_per_m": float(audit.computed_added_mass_per_m),
                "computed_added_mass_ratio": float(audit.computed_added_mass_ratio),
                "computed_added_mass_relative_error": float(audit.computed_added_mass_relative_error),
                "pressure_sign_corrected_added_mass_per_m": float(
                    audit.pressure_sign_corrected_added_mass_per_m
                ),
                "pressure_sign_corrected_added_mass_ratio": float(audit.pressure_sign_corrected_added_mass_ratio),
                "pressure_sign_corrected_relative_error": float(audit.pressure_sign_corrected_relative_error),
                "computed_radiation_damping_per_m": float(audit.computed_radiation_damping_per_m),
                "pressure_sign_corrected_radiation_damping_per_m": float(
                    audit.pressure_sign_corrected_radiation_damping_per_m
                ),
                "source_system_condition_number": float(audit.source_system_condition_number),
                "source_system_relative_residual": float(audit.source_system_relative_residual),
                "potential_alignment_scale_to_analytic": float(audit.potential_alignment_scale_to_analytic),
                "potential_alignment_relative_residual": float(audit.potential_alignment_relative_residual),
                "heave_force_row_norm": float(audit.heave_force_row_norm),
                "body_normal_velocity_norm": float(audit.body_normal_velocity_norm),
                "corrected_relative_tolerance": tolerance,
                "raw_added_mass_sign": raw_sign,
                "diagnostic_status": "PASS" if corrected_pass else "FAIL",
                "diagnostic_conclusion": (
                    "raw_chain_sign_reversed_but_pressure_sign_corrected_magnitude_matches_closed_cylinder"
                    if corrected_pass and raw_sign == "negative"
                    else "closed_cylinder_pressure_chain_needs_amplitude_or_sign_review"
                ),
                "gate_role": A1_CLOSED_CYLINDER_ADDED_MASS_STATUS,
                "is_hard_gate": False,
            }
        )
    return rows


def a1_inner_mixed_boundary_identity_rows(
    *,
    candidates: tuple[A1InnerKernelCandidate, ...] | None = None,
    panel_counts: tuple[int, ...] | list[int] = (66, 132, 264),
    potential_names: tuple[str, ...] | list[str] = ("linear_y", "linear_z", "quadratic_y2_minus_z2", "cross_yz"),
    semiaxis_y_m: float = 1.0,
    semiaxis_z_m: float = 0.5,
    relative_tolerance: float = 0.08,
) -> list[dict[str, float | int | str | bool]]:
    """Return Eq. (23) mixed body/free/control identity rows."""

    candidate_set = candidates or a1_inner_kernel_candidate_cases(
        MatchedWigleySensitivityCase(name="inner_mixed_boundary_base")
    )
    counts = tuple(int(value) for value in panel_counts)
    if not counts or any(value < 12 for value in counts):
        raise ValueError("panel_counts must contain values of at least 12.")
    potentials = tuple(str(value).strip().lower() for value in potential_names)
    if not potentials:
        raise ValueError("At least one potential_name is required.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    rows: list[dict[str, float | int | str | bool]] = []
    for panel_count in counts:
        closed = build_closed_ellipse_inner_boundary(
            semiaxis_y_m=float(semiaxis_y_m),
            semiaxis_z_m=float(semiaxis_z_m),
            panel_count=panel_count,
        )
        body, free, control = split_inner_boundary_geometry_by_panel_counts(
            closed,
            closed_boundary_three_part_panel_counts(panel_count),
        )
        for potential in potentials:
            for candidate in candidate_set:
                audit = audit_inner_mixed_boundary_green_identity(
                    body,
                    free,
                    control,
                    potential_name=potential,
                    geometry_name="closed_ellipse_body_free_control_split",
                    inner_a_scale=float(candidate.case.inner_a_scale),
                    inner_b_scale=float(candidate.case.inner_b_scale),
                    inner_diagonal_sign=float(candidate.case.inner_diagonal_sign),
                )
                passed = bool(audit.total_relative_residual <= tolerance)
                rows.append(
                    {
                        "a1_inner_candidate_name": candidate.name,
                        "a1_inner_candidate_status": candidate.status,
                        "a1_inner_mixed_boundary_status": A1_INNER_MIXED_BOUNDARY_STATUS,
                        "a1_inner_mixed_boundary_validity_status": audit.validity.status,
                        "a1_inner_changed_eq23_terms": ";".join(candidate.changed_eq23_terms),
                        "a1_inner_hypothesis": candidate.hypothesis,
                        "geometry_name": audit.geometry_name,
                        "potential_name": audit.potential_name,
                        "panel_count": int(audit.panel_count),
                        "body_panel_count": int(audit.body_panel_count),
                        "free_panel_count": int(audit.free_panel_count),
                        "control_panel_count": int(audit.control_panel_count),
                        "semiaxis_y_m": float(semiaxis_y_m),
                        "semiaxis_z_m": float(semiaxis_z_m),
                        "inner_a_scale": float(audit.inner_a_scale),
                        "inner_b_scale": float(audit.inner_b_scale),
                        "inner_diagonal_sign": float(audit.inner_diagonal_sign),
                        "total_residual_norm": float(audit.total_residual_norm),
                        "total_relative_residual": float(audit.total_relative_residual),
                        "body_relative_residual": float(audit.body_relative_residual),
                        "free_relative_residual": float(audit.free_relative_residual),
                        "control_relative_residual": float(audit.control_relative_residual),
                        "max_abs_residual": float(audit.max_abs_residual),
                        "solution_norm": float(audit.solution_norm),
                        "rhs_norm": float(audit.rhs_norm),
                        "relative_tolerance": tolerance,
                        "diagnostic_status": "PASS" if passed else "FAIL",
                        "gate_role": A1_INNER_MIXED_BOUNDARY_STATUS,
                        "is_hard_gate": False,
                    }
                )
    return rows


def a1_free_surface_oscillator_rows(
    *,
    dt_values: tuple[float, ...] | list[float] = (0.08, 0.04, 0.02, 0.01),
    sample_count: int = 9,
    gravity_m_s2: float = 9.80665,
    wavenumber_rad_m: float = 1.0,
    amplitude_m: float = 1.0,
    phase_rad: float = 0.37,
    phase_gradient_rad_m: float = 0.25,
    period_count: float = 1.0,
    normalized_error_tolerance: float = 0.08,
) -> list[dict[str, float | int | str | bool]]:
    """Return analytic oscillator rows for the A1 Eq. (19)-(22) marching state."""

    values = tuple(float(value) for value in dt_values)
    if not values or any(value <= 0.0 or not np.isfinite(value) for value in values):
        raise ValueError("dt_values must contain positive finite values.")
    periods = float(period_count)
    if periods <= 0.0 or not np.isfinite(periods):
        raise ValueError("period_count must be positive and finite.")
    tolerance = float(normalized_error_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("normalized_error_tolerance must be positive and finite.")
    gravity = float(gravity_m_s2)
    wavenumber = float(wavenumber_rad_m)
    omega = float(np.sqrt(gravity * wavenumber))
    target_duration = periods * 2.0 * math.pi / omega
    rows: list[dict[str, float | int | str | bool]] = []
    for dt in values:
        step_count = max(1, int(round(target_duration / dt)))
        audit = audit_free_surface_oscillator_marching(
            dt_s=dt,
            step_count=step_count,
            sample_count=int(sample_count),
            gravity_m_s2=gravity,
            wavenumber_rad_m=wavenumber,
            amplitude_m=float(amplitude_m),
            phase_rad=float(phase_rad),
            phase_gradient_rad_m=float(phase_gradient_rad_m),
        )
        max_normalized_error = max(
            float(audit.max_elevation_normalized_error),
            float(audit.max_potential_normalized_error),
        )
        rms_normalized_error = max(
            float(audit.rms_elevation_normalized_error),
            float(audit.rms_potential_normalized_error),
        )
        passed = bool(max_normalized_error <= tolerance)
        rows.append(
            {
                "a1_free_surface_oscillator_status": A1_FREE_SURFACE_OSCILLATOR_STATUS,
                "a1_free_surface_oscillator_validity_status": audit.validity.status,
                "sample_count": int(audit.sample_count),
                "dt_s": float(audit.dt_s),
                "step_count": int(audit.step_count),
                "target_duration_s": float(target_duration),
                "final_time_s": float(audit.final_time_s),
                "final_half_step_time_s": float(audit.final_half_step_time_s),
                "gravity_m_s2": float(audit.gravity_m_s2),
                "wavenumber_rad_m": float(audit.wavenumber_rad_m),
                "omega_rad_s": float(audit.omega_rad_s),
                "amplitude_m": float(audit.amplitude_m),
                "phase_rad": float(audit.phase_rad),
                "phase_gradient_rad_m": float(audit.phase_gradient_rad_m),
                "potential_amplitude_m2_s": float(audit.potential_amplitude_m2_s),
                "max_elevation_abs_error_m": float(audit.max_elevation_abs_error_m),
                "rms_elevation_abs_error_m": float(audit.rms_elevation_abs_error_m),
                "max_elevation_normalized_error": float(audit.max_elevation_normalized_error),
                "rms_elevation_normalized_error": float(audit.rms_elevation_normalized_error),
                "final_elevation_abs_error_m": float(audit.final_elevation_abs_error_m),
                "max_potential_abs_error_m2_s": float(audit.max_potential_abs_error_m2_s),
                "rms_potential_abs_error_m2_s": float(audit.rms_potential_abs_error_m2_s),
                "max_potential_normalized_error": float(audit.max_potential_normalized_error),
                "rms_potential_normalized_error": float(audit.rms_potential_normalized_error),
                "final_potential_abs_error_m2_s": float(audit.final_potential_abs_error_m2_s),
                "max_normalized_error": float(max_normalized_error),
                "rms_normalized_error": float(rms_normalized_error),
                "normalized_error_tolerance": float(tolerance),
                "diagnostic_status": "PASS" if passed else "FAIL",
                "gate_role": A1_FREE_SURFACE_OSCILLATOR_STATUS,
                "is_hard_gate": False,
            }
        )
    return rows


def a1_convention_candidate_mapping_rows(
    candidates: tuple[A1ConventionCandidate, ...],
) -> list[dict[str, str | bool]]:
    """Return one mapping-table row per default mapping row and candidate."""

    mapping_rows = DEFAULT_A1_HEAVE_PITCH_CONVENTION.paper_to_package_mapping_table()
    rows: list[dict[str, str | bool]] = []
    for candidate in candidates:
        changed = set(candidate.changed_mapping_rows)
        for row in mapping_rows:
            symbol = str(row["a1_symbol"])
            rows.append(
                {
                    **row,
                    "a1_convention_candidate_name": candidate.name,
                    "a1_convention_candidate_status": candidate.status,
                    "candidate_changes_this_row": bool(symbol in changed),
                    "a1_convention_changed_mapping_rows": ";".join(candidate.changed_mapping_rows),
                    "a1_convention_hypothesis": candidate.hypothesis,
                }
            )
    return rows


def a1_control_surface_candidate_cases(
    base_case: MatchedWigleySensitivityCase | None = None,
) -> tuple[A1ControlSurfaceCandidate, ...]:
    """Return a controlled set of A1 Eq. (24) instantaneous control-surface candidates."""

    base = base_case or MatchedWigleySensitivityCase(
        name="a1control_base",
        station_count=41,
        body_panels_per_section=8,
        free_surface_inner_panels=12,
        free_surface_outer_panels=10,
        control_surface_radius_beams=3.0,
        history_steps=2,
        history_quadrature_count=16,
        history_k_max=15.0,
        clip_inner_free_surface_to_waterline=True,
    )
    prefix = str(base.name).strip() or "a1control_base"

    def candidate(
        suffix: str,
        *,
        changed_terms: tuple[str, ...],
        hypothesis: str,
        description: str,
        **case_updates: float | bool | int | str,
    ) -> A1ControlSurfaceCandidate:
        return A1ControlSurfaceCandidate(
            name=suffix,
            case=replace(base, name=f"{prefix}__{suffix}", **case_updates),
            changed_eq24_terms=changed_terms,
            hypothesis=hypothesis,
            description=description,
        )

    return (
        candidate(
            "default_control_terms",
            changed_terms=(),
            hypothesis="Use the current Eq. (24) instantaneous control-surface terms.",
            description="Neutral control case for the current image, column, and diagonal signs.",
        ),
        candidate(
            "reverse_image_terms",
            changed_terms=("A-Abar image term", "B-Bbar image term"),
            hypothesis="Reverse the instantaneous image contribution in Eq. (24).",
            description="Tests whether the mirrored control-surface kernels use the opposite sign convention.",
            control_image_scale=-1.0,
        ),
        candidate(
            "reverse_potential_column",
            changed_terms=("C potential column",),
            hypothesis="Reverse the instantaneous potential-column contribution.",
            description="Isolates the Eq. (24) column multiplying the current control-surface potential.",
            control_potential_kernel_scale=-1.0,
        ),
        candidate(
            "reverse_normal_derivative_column",
            changed_terms=("B normal-derivative column",),
            hypothesis="Reverse the instantaneous normal-derivative column contribution.",
            description="Isolates the Eq. (24) column multiplying the current control-surface normal derivative.",
            control_normal_derivative_kernel_scale=-1.0,
        ),
        candidate(
            "reverse_both_columns",
            changed_terms=("C potential column", "B normal-derivative column"),
            hypothesis="Reverse both instantaneous control-surface unknown columns together.",
            description="Tests a paired left-hand-side column sign convention while keeping image terms unchanged.",
            control_potential_kernel_scale=-1.0,
            control_normal_derivative_kernel_scale=-1.0,
        ),
        candidate(
            "reverse_image_and_both_columns",
            changed_terms=("A-Abar image term", "B-Bbar image term", "C potential column", "B normal-derivative column"),
            hypothesis="Reverse image and both instantaneous control-surface columns together.",
            description="Broad Eq. (24) sign audit. It is diagnostic only unless the joint gate passes.",
            control_image_scale=-1.0,
            control_potential_kernel_scale=-1.0,
            control_normal_derivative_kernel_scale=-1.0,
        ),
        candidate(
            "reverse_diagonal",
            changed_terms=("control-surface diagonal term",),
            hypothesis="Reverse the instantaneous control-surface diagonal convention.",
            description="Checks whether the collocation self-term sign is responsible for the diagonal coefficient gap.",
            control_diagonal_sign=-1.0,
        ),
    )


def a1_control_surface_green_identity_rows(
    *,
    candidates: tuple[A1ControlSurfaceCandidate, ...] | None = None,
    panel_counts: tuple[int, ...] | list[int] = (16, 32, 64, 128, 256),
    radius_m: float = 1.0,
    source_points: tuple[tuple[float, float], ...] | list[tuple[float, float]] = ((0.2, 0.3), (-0.25, 0.45)),
    relative_tolerance: float = 0.02,
) -> list[dict[str, float | int | str | bool]]:
    """Return half-plane Green-identity rows for the A1 Eq. (24) instantaneous block."""

    candidate_set = candidates or a1_control_surface_candidate_cases(
        MatchedWigleySensitivityCase(name="outer_control_identity_base")
    )
    counts = tuple(int(value) for value in panel_counts)
    if not counts or any(value < 4 for value in counts):
        raise ValueError("panel_counts must contain values of at least 4.")
    radius = float(radius_m)
    if radius <= 0.0 or not np.isfinite(radius):
        raise ValueError("radius_m must be positive and finite.")
    points = tuple((float(y), float(z)) for y, z in source_points)
    if not points:
        raise ValueError("At least one source point is required.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    rows: list[dict[str, float | int | str | bool]] = []
    for panel_count in counts:
        control = build_control_surface_geometry(radius_m=radius, panel_count=panel_count)
        for source_y, source_z in points:
            for candidate in candidate_set:
                audit = audit_outer_control_surface_green_identity(
                    control,
                    geometry_name="half_cylinder_control_surface",
                    source_y_m=source_y,
                    source_z_down_m=source_z,
                    control_image_scale=float(candidate.case.control_image_scale),
                    control_potential_kernel_scale=float(candidate.case.control_potential_kernel_scale),
                    control_normal_derivative_kernel_scale=float(candidate.case.control_normal_derivative_kernel_scale),
                    control_diagonal_sign=float(candidate.case.control_diagonal_sign),
                )
                passed = bool(audit.relative_residual <= tolerance)
                rows.append(
                    {
                        "a1_control_candidate_name": candidate.name,
                        "a1_control_candidate_status": candidate.status,
                        "a1_control_green_identity_status": A1_CONTROL_SURFACE_GREEN_IDENTITY_STATUS,
                        "a1_control_green_identity_validity_status": audit.validity.status,
                        "a1_control_changed_eq24_terms": ";".join(candidate.changed_eq24_terms),
                        "a1_control_hypothesis": candidate.hypothesis,
                        "geometry_name": audit.geometry_name,
                        "potential_name": audit.potential_name,
                        "panel_count": int(audit.panel_count),
                        "radius_m": float(audit.radius_m),
                        "source_y_m": float(audit.source_y_m),
                        "source_z_down_m": float(audit.source_z_down_m),
                        "control_image_scale": float(audit.control_image_scale),
                        "control_potential_kernel_scale": float(audit.control_potential_kernel_scale),
                        "control_normal_derivative_kernel_scale": float(audit.control_normal_derivative_kernel_scale),
                        "control_diagonal_sign": float(audit.control_diagonal_sign),
                        "residual_norm": float(audit.residual_norm),
                        "relative_residual": float(audit.relative_residual),
                        "max_abs_residual": float(audit.max_abs_residual),
                        "potential_norm": float(audit.potential_norm),
                        "normal_derivative_norm": float(audit.normal_derivative_norm),
                        "potential_term_norm": float(audit.potential_term_norm),
                        "normal_derivative_term_norm": float(audit.normal_derivative_term_norm),
                        "relative_tolerance": tolerance,
                        "diagnostic_status": "PASS" if passed else "FAIL",
                        "gate_role": A1_CONTROL_SURFACE_GREEN_IDENTITY_STATUS,
                        "is_hard_gate": False,
                    }
                )
    return rows


def a1_history_kernel_derivative_rows(
    *,
    panel_counts: tuple[int, ...] | list[int] = (8, 16, 32),
    lag_values_s: tuple[float, ...] | list[float] = (0.02, 0.05, 0.10),
    radius_m: float = 1.0,
    finite_difference_epsilon_m: float = 1.0e-4,
    gravity_m_s2: float = 9.80665,
    quadrature_count: int = 256,
    k_max: float = 50.0,
    relative_tolerance: float = 1.0e-3,
) -> list[dict[str, float | int | str | bool]]:
    """Return Eq. (28) transient-kernel derivative consistency rows."""

    counts = tuple(int(value) for value in panel_counts)
    if not counts or any(value < 4 for value in counts):
        raise ValueError("panel_counts must contain values of at least 4.")
    lags = tuple(float(value) for value in lag_values_s)
    if not lags or any(value <= 0.0 or not np.isfinite(value) for value in lags):
        raise ValueError("lag_values_s must contain positive finite values.")
    radius = float(radius_m)
    if radius <= 0.0 or not np.isfinite(radius):
        raise ValueError("radius_m must be positive and finite.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    rows: list[dict[str, float | int | str | bool]] = []
    for panel_count in counts:
        control = build_control_surface_geometry(radius_m=radius, panel_count=panel_count)
        for lag in lags:
            audit = audit_transient_history_kernel_normal_derivative(
                control,
                lag_s=lag,
                finite_difference_epsilon_m=float(finite_difference_epsilon_m),
                gravity_m_s2=float(gravity_m_s2),
                quadrature_count=int(quadrature_count),
                k_max=float(k_max),
            )
            passed = bool(audit.relative_residual <= tolerance)
            rows.append(
                {
                    "a1_history_kernel_derivative_status": A1_HISTORY_KERNEL_DERIVATIVE_STATUS,
                    "a1_history_kernel_derivative_validity_status": audit.validity.status,
                    "geometry_name": audit.geometry_name,
                    "panel_count": int(audit.panel_count),
                    "radius_m": float(audit.radius_m),
                    "lag_s": float(audit.lag_s),
                    "finite_difference_epsilon_m": float(audit.finite_difference_epsilon_m),
                    "gravity_m_s2": float(audit.gravity_m_s2),
                    "quadrature_count": int(audit.quadrature_count),
                    "k_max": float(audit.k_max),
                    "green_potential_norm": float(audit.green_potential_norm),
                    "green_normal_derivative_norm": float(audit.green_normal_derivative_norm),
                    "finite_difference_norm": float(audit.finite_difference_norm),
                    "residual_norm": float(audit.residual_norm),
                    "relative_residual": float(audit.relative_residual),
                    "max_abs_residual": float(audit.max_abs_residual),
                    "relative_tolerance": tolerance,
                    "diagnostic_status": "PASS" if passed else "FAIL",
                    "gate_role": A1_HISTORY_KERNEL_DERIVATIVE_STATUS,
                    "is_hard_gate": False,
                }
            )
    return rows


def a1_history_rhs_convergence_rows(
    *,
    panel_count: int = 10,
    radius_m: float = 1.0,
    dt_s: float = 0.05,
    history_steps: int = 4,
    quadrature_cases: tuple[tuple[int, float], ...] | list[tuple[int, float]] = (
        (48, 40.0),
        (96, 50.0),
        (192, 70.0),
        (256, 80.0),
    ),
    reference_quadrature_count: int = 768,
    reference_k_max: float = 120.0,
    gravity_m_s2: float = 9.80665,
    quadrature_rule: str = "trapezoid",
    relative_tolerance: float = 1.0e-3,
) -> list[dict[str, float | int | str | bool]]:
    """Return Eq. (24) history-RHS quadrature/cutoff convergence rows."""

    panel = int(panel_count)
    if panel < 4:
        raise ValueError("panel_count must be at least 4.")
    cases = tuple((int(q), float(k)) for q, k in quadrature_cases)
    if not cases or any(q < 16 or k <= 0.0 or not np.isfinite(k) for q, k in cases):
        raise ValueError("quadrature_cases must contain (quadrature_count >= 16, positive k_max) pairs.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    control = build_control_surface_geometry(radius_m=float(radius_m), panel_count=panel)
    rows: list[dict[str, float | int | str | bool]] = []
    for quadrature_count, cutoff in cases:
        audit = audit_history_rhs_quadrature_convergence(
            control,
            dt_s=float(dt_s),
            history_steps=int(history_steps),
            quadrature_count=quadrature_count,
            k_max=cutoff,
            reference_quadrature_count=int(reference_quadrature_count),
            reference_k_max=float(reference_k_max),
            gravity_m_s2=float(gravity_m_s2),
            quadrature_rule=str(quadrature_rule),
        )
        passed = bool(audit.max_channel_relative_residual <= tolerance)
        rows.append(
            {
                "a1_history_rhs_convergence_status": A1_HISTORY_RHS_CONVERGENCE_STATUS,
                "a1_history_rhs_convergence_validity_status": audit.validity.status,
                "geometry_name": audit.geometry_name,
                "panel_count": int(audit.panel_count),
                "radius_m": float(audit.radius_m),
                "dt_s": float(audit.dt_s),
                "history_steps": int(audit.history_steps),
                "quadrature_rule": audit.quadrature_rule,
                "quadrature_count": int(audit.quadrature_count),
                "k_max": float(audit.k_max),
                "reference_quadrature_count": int(audit.reference_quadrature_count),
                "reference_k_max": float(audit.reference_k_max),
                "total_rhs_norm": float(audit.total_rhs_norm),
                "reference_total_rhs_norm": float(audit.reference_total_rhs_norm),
                "total_residual_norm": float(audit.total_residual_norm),
                "total_relative_residual": float(audit.total_relative_residual),
                "total_max_abs_residual": float(audit.total_max_abs_residual),
                "potential_channel_relative_residual": float(audit.potential_channel_relative_residual),
                "normal_derivative_channel_relative_residual": float(
                    audit.normal_derivative_channel_relative_residual
                ),
                "max_channel_relative_residual": float(audit.max_channel_relative_residual),
                "past_potential_norm": float(audit.past_potential_norm),
                "past_normal_derivative_norm": float(audit.past_normal_derivative_norm),
                "relative_tolerance": tolerance,
                "diagnostic_status": "PASS" if passed else "FAIL",
                "gate_role": A1_HISTORY_RHS_CONVERGENCE_STATUS,
                "is_hard_gate": False,
            }
        )
    return rows


def a1_control_history_inheritance_rows(
    reference_csv: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    modes: tuple[str, ...] | list[str] = ("heave", "pitch"),
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    relative_tolerance: float = 1.0e-10,
) -> list[dict[str, float | str | int | bool]]:
    """Return real station-sweep Eq. (24) control-history inheritance audit rows."""

    if not cases:
        raise ValueError("At least one sensitivity case is required.")
    mode_set = tuple(str(mode).strip().lower() for mode in modes)
    if not mode_set or any(mode not in {"heave", "pitch"} for mode in mode_set):
        raise ValueError("modes must contain 'heave' and/or 'pitch'.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    data = _selected_reference_rows(
        reference_csv,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
    )
    rows: list[dict[str, float | str | int | bool]] = []
    cache: dict[tuple[object, ...], object] = {}
    for row_index, item in data.iterrows():
        coefficient = str(item["coefficient"]).strip().upper()
        length = float(item.get("length_m", 3.0))
        beam = float(item.get("beam_m", 0.3))
        draft = float(item.get("draft_m", 0.1875))
        omega_hat = float(item["omega_e_sqrt_l_over_g"])
        omega = omega_hat * math.sqrt(float(gravity_m_s2) / length)
        speed_mps, fn_l = _speed_from_row(item, length, gravity_m_s2)
        if speed_mps <= 0.0:
            for case in cases:
                for mode in mode_set:
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "mode_name": mode,
                            "diagnostic_status": "ERROR",
                            "solver_status": "speed_mps could not be inferred from Ma row",
                            "gate_role": A1_CONTROL_HISTORY_INHERITANCE_STATUS,
                            "is_hard_gate": False,
                        }
                    )
            continue
        for case in cases:
            cache_key = (
                case,
                round(omega, 12),
                round(speed_mps, 12),
                length,
                beam,
                draft,
                rho_water_kg_m3,
                gravity_m_s2,
            )
            try:
                if cache_key not in cache:
                    hull = make_wigley_iii_hull(
                        length_m=length,
                        beam_m=beam,
                        draft_m=draft,
                        station_count=int(case.station_count),
                    )
                    cache[cache_key] = solve_station_hull_heave_pitch_matched_sweep(
                        hull,
                        omega,
                        speed_mps,
                        config=case.config(),
                        rho_water_kg_m3=float(rho_water_kg_m3),
                        history_steps=int(case.history_steps),
                        history_quadrature_count=int(case.history_quadrature_count),
                        history_k_max=float(case.history_k_max),
                        include_end_term=bool(case.include_end_term),
                        end_station=str(case.end_station),
                        end_term_scale=float(case.end_term_scale),
                        pitch_radiation_sign=float(case.pitch_radiation_sign),
                        pitch_radiation_lever_sign=float(case.pitch_radiation_lever_sign),
                        pitch_forward_speed_sign=float(case.pitch_forward_speed_sign),
                        pitch_moment_sign=float(case.pitch_moment_sign),
                        time_step_scale=float(case.time_step_scale),
                        free_surface_velocity_scale=float(case.free_surface_velocity_scale),
                        history_rhs_scale=float(case.history_rhs_scale),
                        history_convolution_rule=str(case.history_convolution_rule),
                        history_potential_kernel_scale=float(case.history_potential_kernel_scale),
                        history_normal_derivative_kernel_scale=float(case.history_normal_derivative_kernel_scale),
                        control_image_scale=float(case.control_image_scale),
                        control_potential_kernel_scale=float(case.control_potential_kernel_scale),
                        control_normal_derivative_kernel_scale=float(case.control_normal_derivative_kernel_scale),
                        control_diagonal_sign=float(case.control_diagonal_sign),
                        inner_a_scale=float(case.inner_a_scale),
                        inner_b_scale=float(case.inner_b_scale),
                        inner_diagonal_sign=float(case.inner_diagonal_sign),
                        pressure_gradient_scheme=str(case.pressure_gradient_scheme),
                        pressure_gradient_scale=float(case.pressure_gradient_scale),
                        force_assembly_route=str(case.force_assembly_route),
                        apply_local_time_phase=bool(case.apply_local_time_phase),
                        local_time_phase_gradient_correction=bool(case.local_time_phase_gradient_correction),
                        clip_inner_free_surface_to_waterline=bool(case.clip_inner_free_surface_to_waterline),
                        two_zone_inner_free_surface=bool(case.two_zone_inner_free_surface),
                        use_free_surface_marching=bool(case.use_free_surface_marching),
                    )
                sweep = cache[cache_key]
                grid_audit = a1_grid_recommendation(case, fn_l)
                for mode in mode_set:
                    audits = audit_control_history_inheritance(sweep, mode_name=mode)
                    for audit in audits:
                        max_lag0_relative = max(
                            float(audit.lag0_potential_relative_residual),
                            float(audit.lag0_normal_derivative_relative_residual),
                        )
                        passed = bool(
                            float(audit.rhs_relative_residual) <= tolerance and max_lag0_relative <= tolerance
                        )
                        rows.append(
                            {
                                "row": int(row_index),
                                "case_name": case.name,
                                "coefficient": coefficient,
                                "hull": str(item.get("hull", "wigley_iii")),
                                "speed_case": str(item.get("speed_case", "")),
                                "fn_l": float(fn_l),
                                "speed_mps": float(speed_mps),
                                "omega_e_sqrt_l_over_g": float(omega_hat),
                                "omega_rad_s": float(omega),
                                "mode_name": audit.mode_name,
                                "station_local_index": int(audit.station_local_index),
                                "active_station_index": int(audit.active_station_index),
                                "solve_order_rank": int(audit.solve_order_rank),
                                "expected_previous_station_local_index": int(
                                    audit.expected_previous_station_local_index
                                ),
                                "history_steps": int(audit.history_steps),
                                "history_dt_s": float(audit.history_dt_s),
                                "history_quadrature_count": int(audit.history_quadrature_count),
                                "history_k_max": float(audit.history_k_max),
                                "control_panel_count": int(audit.control_panel_count),
                                "control_radius_m": float(audit.control_radius_m),
                                "history_convolution_rule": audit.quadrature_rule,
                                "stored_rhs_norm": float(audit.stored_rhs_norm),
                                "expected_rhs_norm": float(audit.expected_rhs_norm),
                                "rhs_residual_norm": float(audit.rhs_residual_norm),
                                "rhs_relative_residual": float(audit.rhs_relative_residual),
                                "rhs_max_abs_residual": float(audit.rhs_max_abs_residual),
                                "lag0_potential_norm": float(audit.lag0_potential_norm),
                                "expected_lag0_potential_norm": float(audit.expected_lag0_potential_norm),
                                "lag0_potential_residual_norm": float(audit.lag0_potential_residual_norm),
                                "lag0_potential_relative_residual": float(
                                    audit.lag0_potential_relative_residual
                                ),
                                "lag0_normal_derivative_norm": float(audit.lag0_normal_derivative_norm),
                                "expected_lag0_normal_derivative_norm": float(
                                    audit.expected_lag0_normal_derivative_norm
                                ),
                                "lag0_normal_derivative_residual_norm": float(
                                    audit.lag0_normal_derivative_residual_norm
                                ),
                                "lag0_normal_derivative_relative_residual": float(
                                    audit.lag0_normal_derivative_relative_residual
                                ),
                                "max_lag0_relative_residual": float(max_lag0_relative),
                                "full_history_potential_norm": float(audit.full_history_potential_norm),
                                "full_history_normal_derivative_norm": float(
                                    audit.full_history_normal_derivative_norm
                                ),
                                "a1_control_history_inheritance_status": A1_CONTROL_HISTORY_INHERITANCE_STATUS,
                                "a1_control_history_inheritance_validity_status": audit.validity.status,
                                "relative_tolerance": tolerance,
                                "diagnostic_status": "PASS" if passed else "FAIL",
                                "gate_role": A1_CONTROL_HISTORY_INHERITANCE_STATUS,
                                "is_hard_gate": False,
                                **grid_audit,
                            }
                        )
            except Exception as exc:  # pragma: no cover - exercised through writer smoke tests when failures occur.
                for mode in mode_set:
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "mode_name": mode,
                            "diagnostic_status": "ERROR",
                            "solver_status": str(exc),
                            "gate_role": A1_CONTROL_HISTORY_INHERITANCE_STATUS,
                            "is_hard_gate": False,
                        }
                    )
    return rows


def a1_outer_control_balance_rows(
    reference_csv: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    modes: tuple[str, ...] | list[str] = ("heave", "pitch"),
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    relative_tolerance: float = 1.0e-5,
) -> list[dict[str, float | str | int | bool]]:
    """Return real station-sweep Eq. (24) outer-control scale/phase audit rows."""

    if not cases:
        raise ValueError("At least one sensitivity case is required.")
    mode_set = tuple(str(mode).strip().lower() for mode in modes)
    if not mode_set or any(mode not in {"heave", "pitch"} for mode in mode_set):
        raise ValueError("modes must contain 'heave' and/or 'pitch'.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    data = _selected_reference_rows(
        reference_csv,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
    )
    rows: list[dict[str, float | str | int | bool]] = []
    cache: dict[tuple[object, ...], object] = {}
    for row_index, item in data.iterrows():
        coefficient = str(item["coefficient"]).strip().upper()
        length = float(item.get("length_m", 3.0))
        beam = float(item.get("beam_m", 0.3))
        draft = float(item.get("draft_m", 0.1875))
        omega_hat = float(item["omega_e_sqrt_l_over_g"])
        omega = omega_hat * math.sqrt(float(gravity_m_s2) / length)
        speed_mps, fn_l = _speed_from_row(item, length, gravity_m_s2)
        if speed_mps <= 0.0:
            for case in cases:
                for mode in mode_set:
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "mode_name": mode,
                            "diagnostic_status": "ERROR",
                            "solver_status": "speed_mps could not be inferred from Ma row",
                            "gate_role": A1_OUTER_CONTROL_BALANCE_STATUS,
                            "is_hard_gate": False,
                        }
                    )
            continue
        for case in cases:
            cache_key = (
                case,
                round(omega, 12),
                round(speed_mps, 12),
                length,
                beam,
                draft,
                rho_water_kg_m3,
                gravity_m_s2,
            )
            try:
                if cache_key not in cache:
                    hull = make_wigley_iii_hull(
                        length_m=length,
                        beam_m=beam,
                        draft_m=draft,
                        station_count=int(case.station_count),
                    )
                    cache[cache_key] = solve_station_hull_heave_pitch_matched_sweep(
                        hull,
                        omega,
                        speed_mps,
                        config=case.config(),
                        rho_water_kg_m3=float(rho_water_kg_m3),
                        history_steps=int(case.history_steps),
                        history_quadrature_count=int(case.history_quadrature_count),
                        history_k_max=float(case.history_k_max),
                        include_end_term=bool(case.include_end_term),
                        end_station=str(case.end_station),
                        end_term_scale=float(case.end_term_scale),
                        pitch_radiation_sign=float(case.pitch_radiation_sign),
                        pitch_radiation_lever_sign=float(case.pitch_radiation_lever_sign),
                        pitch_forward_speed_sign=float(case.pitch_forward_speed_sign),
                        pitch_moment_sign=float(case.pitch_moment_sign),
                        time_step_scale=float(case.time_step_scale),
                        free_surface_velocity_scale=float(case.free_surface_velocity_scale),
                        history_rhs_scale=float(case.history_rhs_scale),
                        history_convolution_rule=str(case.history_convolution_rule),
                        history_potential_kernel_scale=float(case.history_potential_kernel_scale),
                        history_normal_derivative_kernel_scale=float(case.history_normal_derivative_kernel_scale),
                        control_image_scale=float(case.control_image_scale),
                        control_potential_kernel_scale=float(case.control_potential_kernel_scale),
                        control_normal_derivative_kernel_scale=float(case.control_normal_derivative_kernel_scale),
                        control_diagonal_sign=float(case.control_diagonal_sign),
                        inner_a_scale=float(case.inner_a_scale),
                        inner_b_scale=float(case.inner_b_scale),
                        inner_diagonal_sign=float(case.inner_diagonal_sign),
                        pressure_gradient_scheme=str(case.pressure_gradient_scheme),
                        pressure_gradient_scale=float(case.pressure_gradient_scale),
                        force_assembly_route=str(case.force_assembly_route),
                        apply_local_time_phase=bool(case.apply_local_time_phase),
                        local_time_phase_gradient_correction=bool(case.local_time_phase_gradient_correction),
                        clip_inner_free_surface_to_waterline=bool(case.clip_inner_free_surface_to_waterline),
                        two_zone_inner_free_surface=bool(case.two_zone_inner_free_surface),
                        use_free_surface_marching=bool(case.use_free_surface_marching),
                    )
                sweep = cache[cache_key]
                grid_audit = a1_grid_recommendation(case, fn_l)
                for mode in mode_set:
                    audits = audit_outer_control_balance(sweep, mode_name=mode)
                    for audit in audits:
                        passed = bool(float(audit.relative_residual) <= tolerance)
                        rows.append(
                            {
                                "row": int(row_index),
                                "case_name": case.name,
                                "coefficient": coefficient,
                                "hull": str(item.get("hull", "wigley_iii")),
                                "speed_case": str(item.get("speed_case", "")),
                                "fn_l": float(fn_l),
                                "speed_mps": float(speed_mps),
                                "omega_e_sqrt_l_over_g": float(omega_hat),
                                "omega_rad_s": float(omega),
                                "mode_name": audit.mode_name,
                                "station_local_index": int(audit.station_local_index),
                                "active_station_index": int(audit.active_station_index),
                                "solve_order_rank": int(audit.solve_order_rank),
                                "history_steps": int(audit.history_steps),
                                "history_dt_s": float(audit.history_dt_s),
                                "control_panel_count": int(audit.control_panel_count),
                                "control_radius_m": float(audit.control_radius_m),
                                "potential_contribution_norm": float(audit.potential_contribution_norm),
                                "normal_derivative_contribution_norm": float(
                                    audit.normal_derivative_contribution_norm
                                ),
                                "instantaneous_lhs_norm": float(audit.instantaneous_lhs_norm),
                                "history_rhs_norm": float(audit.history_rhs_norm),
                                "history_potential_kernel_channel_norm": float(
                                    audit.history_potential_kernel_channel_norm
                                ),
                                "history_normal_derivative_kernel_channel_norm": float(
                                    audit.history_normal_derivative_kernel_channel_norm
                                ),
                                "residual_norm": float(audit.residual_norm),
                                "relative_residual": float(audit.relative_residual),
                                "rhs_to_lhs_norm_ratio": float(audit.rhs_to_lhs_norm_ratio),
                                "potential_to_normal_contribution_norm_ratio": float(
                                    audit.potential_to_normal_contribution_norm_ratio
                                ),
                                "history_potential_to_normal_channel_norm_ratio": float(
                                    audit.history_potential_to_normal_channel_norm_ratio
                                ),
                                "lhs_rhs_real_alignment": float(audit.lhs_rhs_real_alignment),
                                "lhs_rhs_phase_deg": float(audit.lhs_rhs_phase_deg),
                                "potential_normal_real_alignment": float(audit.potential_normal_real_alignment),
                                "potential_normal_phase_deg": float(audit.potential_normal_phase_deg),
                                "history_channel_real_alignment": float(audit.history_channel_real_alignment),
                                "history_channel_phase_deg": float(audit.history_channel_phase_deg),
                                "max_abs_lhs": float(audit.max_abs_lhs),
                                "max_abs_rhs": float(audit.max_abs_rhs),
                                "history_rhs_nonzero": bool(audit.history_rhs_norm > 1.0e-14),
                                "a1_outer_control_balance_status": A1_OUTER_CONTROL_BALANCE_STATUS,
                                "a1_outer_control_balance_validity_status": audit.validity.status,
                                "relative_tolerance": tolerance,
                                "diagnostic_status": "PASS" if passed else "FAIL",
                                "gate_role": A1_OUTER_CONTROL_BALANCE_STATUS,
                                "is_hard_gate": False,
                                **grid_audit,
                            }
                        )
            except Exception as exc:  # pragma: no cover - exercised through writer smoke tests when failures occur.
                for mode in mode_set:
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "mode_name": mode,
                            "diagnostic_status": "ERROR",
                            "solver_status": str(exc),
                            "gate_role": A1_OUTER_CONTROL_BALANCE_STATUS,
                            "is_hard_gate": False,
                        }
                    )
    return rows


def a1_rhs_source_decomposition_rows(
    reference_csv: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    modes: tuple[str, ...] | list[str] = ("heave", "pitch"),
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    relative_tolerance: float = 1.0e-5,
) -> list[dict[str, float | str | int | bool]]:
    """Return real station-sweep Eq.23/Eq.24 RHS-source decomposition rows."""

    if not cases:
        raise ValueError("At least one sensitivity case is required.")
    mode_set = tuple(str(mode).strip().lower() for mode in modes)
    if not mode_set or any(mode not in {"heave", "pitch"} for mode in mode_set):
        raise ValueError("modes must contain 'heave' and/or 'pitch'.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    data = _selected_reference_rows(
        reference_csv,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
    )
    rows: list[dict[str, float | str | int | bool]] = []
    cache: dict[tuple[object, ...], object] = {}
    for row_index, item in data.iterrows():
        coefficient = str(item["coefficient"]).strip().upper()
        length = float(item.get("length_m", 3.0))
        beam = float(item.get("beam_m", 0.3))
        draft = float(item.get("draft_m", 0.1875))
        omega_hat = float(item["omega_e_sqrt_l_over_g"])
        omega = omega_hat * math.sqrt(float(gravity_m_s2) / length)
        speed_mps, fn_l = _speed_from_row(item, length, gravity_m_s2)
        if speed_mps <= 0.0:
            for case in cases:
                for mode in mode_set:
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "mode_name": mode,
                            "diagnostic_status": "ERROR",
                            "solver_status": "speed_mps could not be inferred from Ma row",
                            "gate_role": A1_RHS_SOURCE_DECOMPOSITION_STATUS,
                            "is_hard_gate": False,
                        }
                    )
            continue
        for case in cases:
            cache_key = (
                case,
                round(omega, 12),
                round(speed_mps, 12),
                length,
                beam,
                draft,
                rho_water_kg_m3,
                gravity_m_s2,
            )
            try:
                if cache_key not in cache:
                    hull = make_wigley_iii_hull(
                        length_m=length,
                        beam_m=beam,
                        draft_m=draft,
                        station_count=int(case.station_count),
                    )
                    cache[cache_key] = solve_station_hull_heave_pitch_matched_sweep(
                        hull,
                        omega,
                        speed_mps,
                        config=case.config(),
                        rho_water_kg_m3=float(rho_water_kg_m3),
                        history_steps=int(case.history_steps),
                        history_quadrature_count=int(case.history_quadrature_count),
                        history_k_max=float(case.history_k_max),
                        include_end_term=bool(case.include_end_term),
                        end_station=str(case.end_station),
                        end_term_scale=float(case.end_term_scale),
                        pitch_radiation_sign=float(case.pitch_radiation_sign),
                        pitch_radiation_lever_sign=float(case.pitch_radiation_lever_sign),
                        pitch_forward_speed_sign=float(case.pitch_forward_speed_sign),
                        pitch_moment_sign=float(case.pitch_moment_sign),
                        time_step_scale=float(case.time_step_scale),
                        free_surface_velocity_scale=float(case.free_surface_velocity_scale),
                        history_rhs_scale=float(case.history_rhs_scale),
                        history_convolution_rule=str(case.history_convolution_rule),
                        history_potential_kernel_scale=float(case.history_potential_kernel_scale),
                        history_normal_derivative_kernel_scale=float(case.history_normal_derivative_kernel_scale),
                        control_image_scale=float(case.control_image_scale),
                        control_potential_kernel_scale=float(case.control_potential_kernel_scale),
                        control_normal_derivative_kernel_scale=float(case.control_normal_derivative_kernel_scale),
                        control_diagonal_sign=float(case.control_diagonal_sign),
                        inner_a_scale=float(case.inner_a_scale),
                        inner_b_scale=float(case.inner_b_scale),
                        inner_diagonal_sign=float(case.inner_diagonal_sign),
                        pressure_gradient_scheme=str(case.pressure_gradient_scheme),
                        pressure_gradient_scale=float(case.pressure_gradient_scale),
                        force_assembly_route=str(case.force_assembly_route),
                        apply_local_time_phase=bool(case.apply_local_time_phase),
                        local_time_phase_gradient_correction=bool(case.local_time_phase_gradient_correction),
                        clip_inner_free_surface_to_waterline=bool(case.clip_inner_free_surface_to_waterline),
                        two_zone_inner_free_surface=bool(case.two_zone_inner_free_surface),
                        use_free_surface_marching=bool(case.use_free_surface_marching),
                    )
                sweep = cache[cache_key]
                grid_audit = a1_grid_recommendation(case, fn_l)
                for mode in mode_set:
                    audits = audit_rhs_source_decomposition(sweep, mode_name=mode)
                    for audit in audits:
                        passed = bool(float(audit.source_sum_relative_residual) <= tolerance)
                        rows.append(
                            {
                                "row": int(row_index),
                                "case_name": case.name,
                                "coefficient": coefficient,
                                "hull": str(item.get("hull", "wigley_iii")),
                                "speed_case": str(item.get("speed_case", "")),
                                "fn_l": float(fn_l),
                                "speed_mps": float(speed_mps),
                                "omega_e_sqrt_l_over_g": float(omega_hat),
                                "omega_rad_s": float(omega),
                                "mode_name": audit.mode_name,
                                "station_local_index": int(audit.station_local_index),
                                "active_station_index": int(audit.active_station_index),
                                "solve_order_rank": int(audit.solve_order_rank),
                                "source_name": audit.source_name,
                                "source_rhs_norm": float(audit.source_rhs_norm),
                                "total_rhs_norm": float(audit.total_rhs_norm),
                                "source_rhs_to_total_rhs_norm_ratio": float(
                                    audit.source_rhs_to_total_rhs_norm_ratio
                                ),
                                "full_solution_norm": float(audit.full_solution_norm),
                                "source_solution_norm": float(audit.source_solution_norm),
                                "source_solution_to_full_solution_norm_ratio": float(
                                    audit.source_solution_to_full_solution_norm_ratio
                                ),
                                "body_potential_norm": float(audit.body_potential_norm),
                                "inner_free_surface_normal_derivative_norm": float(
                                    audit.inner_free_surface_normal_derivative_norm
                                ),
                                "control_potential_norm": float(audit.control_potential_norm),
                                "control_normal_derivative_norm": float(audit.control_normal_derivative_norm),
                                "source_to_full_real_alignment": float(audit.source_to_full_real_alignment),
                                "source_to_full_phase_deg": float(audit.source_to_full_phase_deg),
                                "source_sum_residual_norm": float(audit.source_sum_residual_norm),
                                "source_sum_relative_residual": float(audit.source_sum_relative_residual),
                                "a1_rhs_source_decomposition_status": A1_RHS_SOURCE_DECOMPOSITION_STATUS,
                                "a1_rhs_source_decomposition_validity_status": audit.validity.status,
                                "relative_tolerance": tolerance,
                                "diagnostic_status": "PASS" if passed else "FAIL",
                                "gate_role": A1_RHS_SOURCE_DECOMPOSITION_STATUS,
                                "is_hard_gate": False,
                                **grid_audit,
                            }
                        )
            except Exception as exc:  # pragma: no cover - exercised through writer smoke tests when failures occur.
                for mode in mode_set:
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "mode_name": mode,
                            "diagnostic_status": "ERROR",
                            "solver_status": str(exc),
                            "gate_role": A1_RHS_SOURCE_DECOMPOSITION_STATUS,
                            "is_hard_gate": False,
                        }
                    )
    return rows


def a1_inner_free_surface_state_rows(
    reference_csv: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    modes: tuple[str, ...] | list[str] = ("heave", "pitch"),
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    relative_tolerance: float = 1.0e-10,
) -> list[dict[str, float | str | int | bool]]:
    """Return real station-sweep inner-free-surface state marching audit rows."""

    if not cases:
        raise ValueError("At least one sensitivity case is required.")
    mode_set = tuple(str(mode).strip().lower() for mode in modes)
    if not mode_set or any(mode not in {"heave", "pitch"} for mode in mode_set):
        raise ValueError("modes must contain 'heave' and/or 'pitch'.")
    tolerance = float(relative_tolerance)
    if tolerance <= 0.0 or not np.isfinite(tolerance):
        raise ValueError("relative_tolerance must be positive and finite.")
    data = _selected_reference_rows(
        reference_csv,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
    )
    rows: list[dict[str, float | str | int | bool]] = []
    cache: dict[tuple[object, ...], object] = {}
    for row_index, item in data.iterrows():
        coefficient = str(item["coefficient"]).strip().upper()
        length = float(item.get("length_m", 3.0))
        beam = float(item.get("beam_m", 0.3))
        draft = float(item.get("draft_m", 0.1875))
        omega_hat = float(item["omega_e_sqrt_l_over_g"])
        omega = omega_hat * math.sqrt(float(gravity_m_s2) / length)
        speed_mps, fn_l = _speed_from_row(item, length, gravity_m_s2)
        if speed_mps <= 0.0:
            for case in cases:
                for mode in mode_set:
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "mode_name": mode,
                            "diagnostic_status": "ERROR",
                            "solver_status": "speed_mps could not be inferred from Ma row",
                            "gate_role": A1_INNER_FREE_SURFACE_STATE_STATUS,
                            "is_hard_gate": False,
                        }
                    )
            continue
        for case in cases:
            cache_key = (
                case,
                round(omega, 12),
                round(speed_mps, 12),
                length,
                beam,
                draft,
                rho_water_kg_m3,
                gravity_m_s2,
            )
            try:
                if cache_key not in cache:
                    hull = make_wigley_iii_hull(
                        length_m=length,
                        beam_m=beam,
                        draft_m=draft,
                        station_count=int(case.station_count),
                    )
                    cache[cache_key] = solve_station_hull_heave_pitch_matched_sweep(
                        hull,
                        omega,
                        speed_mps,
                        config=case.config(),
                        rho_water_kg_m3=float(rho_water_kg_m3),
                        history_steps=int(case.history_steps),
                        history_quadrature_count=int(case.history_quadrature_count),
                        history_k_max=float(case.history_k_max),
                        include_end_term=bool(case.include_end_term),
                        end_station=str(case.end_station),
                        end_term_scale=float(case.end_term_scale),
                        pitch_radiation_sign=float(case.pitch_radiation_sign),
                        pitch_radiation_lever_sign=float(case.pitch_radiation_lever_sign),
                        pitch_forward_speed_sign=float(case.pitch_forward_speed_sign),
                        pitch_moment_sign=float(case.pitch_moment_sign),
                        time_step_scale=float(case.time_step_scale),
                        free_surface_velocity_scale=float(case.free_surface_velocity_scale),
                        history_rhs_scale=float(case.history_rhs_scale),
                        history_convolution_rule=str(case.history_convolution_rule),
                        history_potential_kernel_scale=float(case.history_potential_kernel_scale),
                        history_normal_derivative_kernel_scale=float(case.history_normal_derivative_kernel_scale),
                        control_image_scale=float(case.control_image_scale),
                        control_potential_kernel_scale=float(case.control_potential_kernel_scale),
                        control_normal_derivative_kernel_scale=float(case.control_normal_derivative_kernel_scale),
                        control_diagonal_sign=float(case.control_diagonal_sign),
                        inner_a_scale=float(case.inner_a_scale),
                        inner_b_scale=float(case.inner_b_scale),
                        inner_diagonal_sign=float(case.inner_diagonal_sign),
                        pressure_gradient_scheme=str(case.pressure_gradient_scheme),
                        pressure_gradient_scale=float(case.pressure_gradient_scale),
                        force_assembly_route=str(case.force_assembly_route),
                        apply_local_time_phase=bool(case.apply_local_time_phase),
                        local_time_phase_gradient_correction=bool(case.local_time_phase_gradient_correction),
                        clip_inner_free_surface_to_waterline=bool(case.clip_inner_free_surface_to_waterline),
                        two_zone_inner_free_surface=bool(case.two_zone_inner_free_surface),
                        use_free_surface_marching=bool(case.use_free_surface_marching),
                    )
                sweep = cache[cache_key]
                grid_audit = a1_grid_recommendation(case, fn_l)
                for mode in mode_set:
                    audits = audit_inner_free_surface_state_scale(sweep, mode_name=mode)
                    for audit in audits:
                        max_relative = max(
                            float(audit.update_relative_residual),
                            float(audit.transfer_relative_residual),
                        )
                        max_time_residual = max(
                            float(audit.time_before_abs_residual_s),
                            float(audit.time_after_abs_residual_s),
                        )
                        passed = bool(max_relative <= tolerance and max_time_residual <= tolerance)
                        rows.append(
                            {
                                "row": int(row_index),
                                "case_name": case.name,
                                "coefficient": coefficient,
                                "hull": str(item.get("hull", "wigley_iii")),
                                "speed_case": str(item.get("speed_case", "")),
                                "fn_l": float(fn_l),
                                "speed_mps": float(speed_mps),
                                "omega_e_sqrt_l_over_g": float(omega_hat),
                                "omega_rad_s": float(omega),
                                "mode_name": audit.mode_name,
                                "station_local_index": int(audit.station_local_index),
                                "active_station_index": int(audit.active_station_index),
                                "solve_order_rank": int(audit.solve_order_rank),
                                "previous_station_local_index": int(audit.previous_station_local_index),
                                "free_surface_update_kind": audit.update_kind,
                                "free_surface_panel_count": int(audit.free_surface_panel_count),
                                "history_dt_s": float(audit.history_dt_s),
                                "free_surface_velocity_scale": float(audit.free_surface_velocity_scale),
                                "gravity_m_s2": float(audit.gravity_m_s2),
                                "y_min_m": float(audit.y_min_m),
                                "y_max_m": float(audit.y_max_m),
                                "potential_before_norm": float(audit.potential_before_norm),
                                "elevation_before_norm": float(audit.elevation_before_norm),
                                "vertical_velocity_norm": float(audit.vertical_velocity_norm),
                                "potential_after_norm": float(audit.potential_after_norm),
                                "elevation_after_norm": float(audit.elevation_after_norm),
                                "expected_potential_after_norm": float(audit.expected_potential_after_norm),
                                "expected_elevation_after_norm": float(audit.expected_elevation_after_norm),
                                "potential_update_increment_norm": float(audit.potential_update_increment_norm),
                                "elevation_update_increment_norm": float(audit.elevation_update_increment_norm),
                                "update_residual_norm": float(audit.update_residual_norm),
                                "update_relative_residual": float(audit.update_relative_residual),
                                "update_max_abs_residual": float(audit.update_max_abs_residual),
                                "transfer_residual_norm": float(audit.transfer_residual_norm),
                                "transfer_relative_residual": float(audit.transfer_relative_residual),
                                "transfer_max_abs_residual": float(audit.transfer_max_abs_residual),
                                "max_state_relative_residual": float(max_relative),
                                "potential_growth_ratio": float(audit.potential_growth_ratio),
                                "elevation_growth_ratio": float(audit.elevation_growth_ratio),
                                "vertical_velocity_to_elevation_increment_ratio": float(
                                    audit.vertical_velocity_to_elevation_increment_ratio
                                ),
                                "potential_increment_to_gravity_elevation_ratio": float(
                                    audit.potential_increment_to_gravity_elevation_ratio
                                ),
                                "velocity_elevation_increment_real_alignment": float(
                                    audit.velocity_elevation_increment_real_alignment
                                ),
                                "velocity_elevation_increment_phase_deg": float(
                                    audit.velocity_elevation_increment_phase_deg
                                ),
                                "elevation_potential_increment_real_alignment": float(
                                    audit.elevation_potential_increment_real_alignment
                                ),
                                "elevation_potential_increment_phase_deg": float(
                                    audit.elevation_potential_increment_phase_deg
                                ),
                                "before_after_potential_real_alignment": float(
                                    audit.before_after_potential_real_alignment
                                ),
                                "before_after_potential_phase_deg": float(
                                    audit.before_after_potential_phase_deg
                                ),
                                "expected_local_time_s": float(audit.expected_local_time_s),
                                "free_surface_state_time_before_s": float(
                                    audit.free_surface_state_time_before_s
                                ),
                                "free_surface_state_time_after_s": float(
                                    audit.free_surface_state_time_after_s
                                ),
                                "time_before_abs_residual_s": float(audit.time_before_abs_residual_s),
                                "time_after_abs_residual_s": float(audit.time_after_abs_residual_s),
                                "max_state_time_abs_residual_s": float(max_time_residual),
                                "a1_inner_free_surface_state_status": A1_INNER_FREE_SURFACE_STATE_STATUS,
                                "a1_inner_free_surface_state_validity_status": audit.validity.status,
                                "relative_tolerance": tolerance,
                                "diagnostic_status": "PASS" if passed else "FAIL",
                                "gate_role": A1_INNER_FREE_SURFACE_STATE_STATUS,
                                "is_hard_gate": False,
                                **grid_audit,
                            }
                        )
            except Exception as exc:  # pragma: no cover - exercised through writer smoke tests when failures occur.
                for mode in mode_set:
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "mode_name": mode,
                            "diagnostic_status": "ERROR",
                            "solver_status": str(exc),
                            "gate_role": A1_INNER_FREE_SURFACE_STATE_STATUS,
                            "is_hard_gate": False,
                        }
                    )
    return rows


def _coefficient_matrix_indices(coefficient: str) -> tuple[str, int, int]:
    name = coefficient.strip().upper()
    if len(name) != 3 or name[0] not in {"A", "B"} or not name[1:].isdigit():
        raise ValueError(f"Unsupported coefficient label {coefficient!r}.")
    dof_map = {"1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5}
    if name[1] not in dof_map or name[2] not in dof_map:
        raise ValueError(f"Unsupported coefficient label {coefficient!r}.")
    return name[0], dof_map[name[1]], dof_map[name[2]]


def _coefficient_scale(
    prefix: str,
    row_idx: int,
    col_idx: int,
    rho: float,
    length: float,
    gravity: float,
    displacement_volume: float,
) -> float:
    rotational = int(row_idx >= 3) + int(col_idx >= 3)
    scale = float(rho) * float(displacement_volume) * float(length) ** rotational
    if prefix == "B":
        scale *= math.sqrt(float(gravity) / float(length))
    return scale


def _ma2005_normalization_formula(prefix: str, row_idx: int, col_idx: int) -> str:
    """Return the Ma 2005 Eq. (34)-style normalization formula label."""

    rotational = int(row_idx >= 3) + int(col_idx >= 3)
    coefficient = f"{prefix}{row_idx + 1}{col_idx + 1}"
    denominator = "rho*displacement_volume"
    if rotational == 1:
        denominator += "*L"
    elif rotational == 2:
        denominator += "*L^2"
    if prefix == "B":
        denominator += "*sqrt(g/L)"
        return (
            f"{coefficient} = raw_{coefficient.lower()} / ({denominator}); "
            "equivalent to raw/(rho*...)*sqrt(L/g)"
        )
    return f"{coefficient} = raw_{coefficient.lower()} / ({denominator})"


def _force_component_to_coefficient(prefix: str, force: complex, omega_rad_s: float) -> float:
    omega = float(omega_rad_s)
    if omega <= 0.0:
        raise ValueError("omega_rad_s must be positive.")
    value = complex(force)
    if prefix == "A":
        return float(np.real(value) / omega**2)
    if prefix == "B":
        return float(-np.imag(value) / omega)
    raise ValueError(f"Unsupported coefficient prefix {prefix!r}.")


def _speed_from_row(row: pd.Series, length_m: float, gravity_m_s2: float) -> tuple[float, float]:
    if "speed_mps" in row and not pd.isna(row["speed_mps"]):
        speed = float(row["speed_mps"])
        return speed, speed / math.sqrt(float(gravity_m_s2) * float(length_m))
    if "fn_l" in row and not pd.isna(row["fn_l"]):
        fn_l = float(row["fn_l"])
        return fn_l * math.sqrt(float(gravity_m_s2) * float(length_m)), fn_l
    match = re.search(r"fn\s*[_=:-]?\s*([0-9]+(?:\.[0-9]+)?)", str(row.get("speed_case", "")), re.IGNORECASE)
    if match:
        fn_l = float(match.group(1))
        return fn_l * math.sqrt(float(gravity_m_s2) * float(length_m)), fn_l
    return 0.0, 0.0


def _error_metrics(
    expected: float,
    actual: float,
    relative_tolerance: float,
    row_idx: int,
    col_idx: int,
    normalization: str,
) -> dict[str, float | str]:
    abs_error = abs(float(actual) - float(expected))
    rel_error = abs_error / max(abs(float(expected)), 1e-12)
    relative_abs_tolerance = float(relative_tolerance) * abs(float(expected))
    nondimensional = normalization.strip().lower() not in {"dimensional", "raw", "si"}
    near_zero_abs_tolerance = 0.0
    if nondimensional and abs(float(expected)) < 0.02:
        near_zero_abs_tolerance = 0.01 if row_idx != col_idx else 0.005
    effective_abs_tolerance = max(relative_abs_tolerance, near_zero_abs_tolerance, 1e-12)
    gate_error_ratio = abs_error / effective_abs_tolerance
    return {
        "abs_error": float(abs_error),
        "rel_error": float(rel_error),
        "near_zero_abs_tolerance": float(near_zero_abs_tolerance),
        "effective_abs_tolerance": float(effective_abs_tolerance),
        "gate_error_ratio": float(gate_error_ratio),
        "error_metric": "absolute_near_zero" if near_zero_abs_tolerance >= relative_abs_tolerance and near_zero_abs_tolerance > 0 else "relative",
        "status": "PASS" if gate_error_ratio <= 1.0 else "FAIL",
    }


def _normalize_coefficients(coefficients: tuple[str, ...] | list[str] | None) -> tuple[str, ...] | None:
    if not coefficients:
        return None
    normalized: list[str] = []
    for coefficient in coefficients:
        for token in str(coefficient).replace(",", " ").split():
            label = token.strip().upper()
            if not label:
                continue
            _coefficient_matrix_indices(label)
            if label not in normalized:
                normalized.append(label)
    return tuple(normalized) if normalized else None


def _selected_reference_rows(
    reference_csv: str | Path,
    *,
    coefficients: tuple[str, ...] | list[str] | None,
    row_limit: int | None,
    row_limit_per_coefficient: int | None,
) -> pd.DataFrame:
    data = pd.read_csv(reference_csv)
    coefficient_filter = _normalize_coefficients(coefficients)
    if coefficient_filter is not None:
        data = data[data["coefficient"].astype(str).str.strip().str.upper().isin(coefficient_filter)].copy()
    if row_limit is not None and row_limit_per_coefficient is not None:
        raise ValueError("Use either row_limit or row_limit_per_coefficient, not both.")
    if row_limit_per_coefficient is not None:
        if int(row_limit_per_coefficient) <= 0:
            raise ValueError("row_limit_per_coefficient must be positive when supplied.")
        coefficient_key = data["coefficient"].astype(str).str.strip().str.upper()
        return data.groupby(coefficient_key, sort=False, group_keys=False).head(int(row_limit_per_coefficient)).copy()
    if row_limit is not None:
        if int(row_limit) <= 0:
            raise ValueError("row_limit must be positive when supplied.")
        return data.head(int(row_limit)).copy()
    return data.copy()


def _complex_norm(values: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(values, dtype=complex)))


def _complex_max_abs(values: np.ndarray) -> float:
    array = np.asarray(values, dtype=complex)
    if array.size == 0:
        return 0.0
    return float(np.max(np.abs(array)))


def _safe_ratio(numerator: float, denominator: float) -> float:
    denom = float(denominator)
    if abs(denom) < 1e-30:
        return math.nan
    return float(numerator) / denom


def _matched_block_audit_fields(audit) -> dict[str, float | str]:
    """Return high-signal scalar fields from a MatchedSystemBlockAudit."""

    max_matrix_label, max_matrix_norm = audit.max_matrix_block()
    max_contribution_label, max_contribution_norm = audit.max_contribution_block()
    eq23_control_rhs = audit.row_rhs_norm("eq23_inner_control")
    eq24_rhs = audit.row_rhs_norm("eq24_outer_control")
    return {
        "a1_matched_block_audit_status": str(audit.validity.status),
        "a1_matched_total_relative_residual": float(audit.total_relative_residual),
        "a1_matched_condition_number": float(audit.condition_number),
        "a1_eq23_body_relative_residual": audit.row_relative_residual("eq23_body"),
        "a1_eq23_free_surface_relative_residual": audit.row_relative_residual("eq23_free_surface"),
        "a1_eq23_inner_control_relative_residual": audit.row_relative_residual("eq23_inner_control"),
        "a1_eq24_outer_control_relative_residual": audit.row_relative_residual("eq24_outer_control"),
        "a1_eq23_body_rhs_norm": audit.row_rhs_norm("eq23_body"),
        "a1_eq23_free_surface_rhs_norm": audit.row_rhs_norm("eq23_free_surface"),
        "a1_eq23_inner_control_rhs_norm": eq23_control_rhs,
        "a1_eq24_outer_control_rhs_norm": eq24_rhs,
        "a1_eq24_to_eq23_control_rhs_norm_ratio": _safe_ratio(eq24_rhs, eq23_control_rhs),
        "a1_unknown_psi_body_norm": audit.unknown_solution_norm("psi_body"),
        "a1_unknown_psi_n_free_surface_norm": audit.unknown_solution_norm("psi_n_free_surface"),
        "a1_unknown_psi_control_norm": audit.unknown_solution_norm("psi_control"),
        "a1_unknown_psi_n_control_norm": audit.unknown_solution_norm("psi_n_control"),
        "a1_max_matrix_block_label": max_matrix_label,
        "a1_max_matrix_block_norm": max_matrix_norm,
        "a1_max_contribution_block_label": max_contribution_label,
        "a1_max_contribution_block_norm": max_contribution_norm,
    }


def _a1_potential_unit_closure_fields(
    body,
    body_condition: np.ndarray,
    solution,
    pressure,
    force,
) -> dict[str, float | str]:
    """Return section-level scale checks linking Eq. (23) unknowns to Eq. (30).

    These values are diagnostic. They do not tune the solution; they expose
    whether a candidate changes the natural length scale between prescribed
    normal velocity, recovered potential, pressure, and integrated force.
    """

    y_span = float(np.ptp(np.asarray(body.mid_y_m, dtype=float))) if body.panel_count else math.nan
    z_span = float(np.ptp(np.asarray(body.mid_z_down_m, dtype=float))) if body.panel_count else math.nan
    mean_panel_length = float(np.mean(np.asarray(body.length_m, dtype=float))) if body.panel_count else math.nan
    characteristic_span = max(y_span, z_span, mean_panel_length, 1e-12)
    body_condition_norm = _complex_norm(body_condition)
    body_potential_norm = _complex_norm(solution.body_potential)
    control_potential_norm = _complex_norm(solution.control_potential)
    control_normal_norm = _complex_norm(solution.control_normal_derivative)
    pressure_time_norm = _complex_norm(pressure.pressure_time_derivative_pa)
    pressure_forward_norm = _complex_norm(pressure.pressure_forward_speed_pa)
    pressure_total_norm = _complex_norm(pressure.pressure_pa)
    rho_omega_phi_norm = (
        float(pressure.rho_water_kg_m3) * float(pressure.omega_rad_s) * body_potential_norm
    )
    body_potential_length = _safe_ratio(body_potential_norm, body_condition_norm)
    control_potential_length = _safe_ratio(control_potential_norm, control_normal_norm)
    force_time = complex(force.heave_force_time_derivative_per_m)
    force_forward = complex(force.heave_force_forward_speed_per_m)
    force_total = complex(force.heave_force_per_m)
    moment_time = complex(force.pitch_moment_time_derivative_per_m)
    moment_forward = complex(force.pitch_moment_forward_speed_per_m)
    moment_total = complex(force.pitch_moment_per_m)
    return {
        "a1_unit_closure_status": A1_POTENTIAL_UNIT_CLOSURE_STATUS,
        "a1_unit_body_characteristic_span_m": float(characteristic_span),
        "a1_unit_body_potential_per_normal_velocity_length_m": body_potential_length,
        "a1_unit_body_potential_per_normal_velocity_over_span": _safe_ratio(
            body_potential_length,
            characteristic_span,
        ),
        "a1_unit_inner_fs_normal_derivative_to_body_condition_norm_ratio": _safe_ratio(
            _complex_norm(solution.inner_free_surface_normal_derivative),
            body_condition_norm,
        ),
        "a1_unit_control_normal_derivative_to_body_condition_norm_ratio": _safe_ratio(
            control_normal_norm,
            body_condition_norm,
        ),
        "a1_unit_control_potential_per_normal_derivative_length_m": control_potential_length,
        "a1_unit_control_potential_per_normal_derivative_over_span": _safe_ratio(
            control_potential_length,
            characteristic_span,
        ),
        "a1_unit_pressure_time_over_rho_omega_phi_norm_ratio": _safe_ratio(
            pressure_time_norm,
            rho_omega_phi_norm,
        ),
        "a1_unit_pressure_forward_to_time_norm_ratio": _safe_ratio(pressure_forward_norm, pressure_time_norm),
        "a1_unit_pressure_total_to_time_norm_ratio": _safe_ratio(pressure_total_norm, pressure_time_norm),
        "a1_unit_heave_force_forward_to_time_abs_ratio": _safe_ratio(abs(force_forward), abs(force_time)),
        "a1_unit_heave_force_total_to_time_abs_ratio": _safe_ratio(abs(force_total), abs(force_time)),
        "a1_unit_pitch_moment_forward_to_time_abs_ratio": _safe_ratio(abs(moment_forward), abs(moment_time)),
        "a1_unit_pitch_moment_total_to_time_abs_ratio": _safe_ratio(abs(moment_total), abs(moment_time)),
    }


def _required_scale_audit(raw: float, reference: float, current_scale: float) -> dict[str, float | str]:
    """Return scale multipliers needed to make raw/current_scale match a reference."""

    ref = float(reference)
    scale = float(current_scale)
    if abs(ref) < 1e-30 or abs(scale) < 1e-30:
        return {
            "required_normalization_scale": math.nan,
            "required_normalization_scale_over_current": math.nan,
            "required_magnitude_scale_over_current": math.nan,
            "normalization_scale_diagnosis": "reference_or_scale_near_zero",
        }
    required = float(raw) / ref
    over_current = required / scale
    magnitude_over_current = abs(over_current)
    if over_current < 0.0:
        diagnosis = "sign_mismatch_not_normalization_only"
    elif 0.5 <= magnitude_over_current <= 2.0:
        diagnosis = "normalization_scale_could_be_plausible_but_requires_source_audit"
    else:
        diagnosis = "normalization_scale_unlikely_as_sole_explanation"
    return {
        "required_normalization_scale": float(required),
        "required_normalization_scale_over_current": float(over_current),
        "required_magnitude_scale_over_current": float(magnitude_over_current),
        "normalization_scale_diagnosis": diagnosis,
    }


def _trapezoid_weights(x_m: np.ndarray) -> np.ndarray:
    x = np.asarray(x_m, dtype=float)
    if x.ndim != 1 or x.size < 2:
        raise ValueError("x_m must be one-dimensional with at least two stations.")
    weights = np.zeros(x.size, dtype=float)
    weights[0] = 0.5 * (x[1] - x[0])
    weights[-1] = 0.5 * (x[-1] - x[-2])
    if x.size > 2:
        weights[1:-1] = 0.5 * (x[2:] - x[:-2])
    return weights


def _cumulative_trapezoid_complex(x_m: np.ndarray, density: np.ndarray) -> np.ndarray:
    x = np.asarray(x_m, dtype=float)
    values = np.asarray(density, dtype=complex)
    cumulative = np.zeros(values.shape, dtype=complex)
    for index in range(1, x.size):
        cumulative[index] = cumulative[index - 1] + 0.5 * (values[index - 1] + values[index]) * (x[index] - x[index - 1])
    return cumulative


def a1_grid_recommendation(case: MatchedWigleySensitivityCase, fn_l: float) -> dict[str, float | int | bool | str]:
    """Return A1 Section 3.3 grid recommendation flags for one case."""

    fn = float(fn_l)
    station_min = A1_LOW_FN_STATION_MIN if fn <= 0.25 else A1_MODERATE_FN_STATION_MIN
    radius_ok = float(case.control_surface_radius_beams) >= A1_RECOMMENDED_CONTROL_RADIUS_BEAMS
    inner_ok = int(case.free_surface_inner_panels) >= A1_MIN_INNER_FREE_SURFACE_PANELS
    outer_ok = int(case.free_surface_outer_panels) >= A1_MIN_OUTER_OR_CONTROL_PANELS
    station_ok = int(case.station_count) >= station_min
    all_ok = bool(radius_ok and inner_ok and outer_ok and station_ok)
    return {
        "a1_recommended_control_radius_beams": A1_RECOMMENDED_CONTROL_RADIUS_BEAMS,
        "a1_min_inner_free_surface_panels": A1_MIN_INNER_FREE_SURFACE_PANELS,
        "a1_min_outer_or_control_panels": A1_MIN_OUTER_OR_CONTROL_PANELS,
        "a1_min_station_count_for_fn": int(station_min),
        "a1_control_radius_ok": bool(radius_ok),
        "a1_inner_free_surface_panels_ok": bool(inner_ok),
        "a1_outer_or_control_panels_ok": bool(outer_ok),
        "a1_station_count_ok": bool(station_ok),
        "a1_grid_recommendation_status": "A1_GRID_RECOMMENDED" if all_ok else "A1_GRID_COARSE_DIAGNOSTIC",
        "a1_grid_recommendation_note": (
            "A1 Section 3.3 recommends control radius about 3B, inner free-surface panels greater than 10, "
            "outer/free-surface proxy panels greater than 8, and roughly 60 stations at Fn=0.2 or 40 at Fn=0.3."
        ),
    }


def matched_wigley_sensitivity_rows(
    reference_csv: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> list[dict[str, float | str | int | bool]]:
    """Return diagnostic Ma 2005 rows using the matched StationHull sweep.

    These rows are sensitivity diagnostics. They intentionally do not replace
    the hard Ma 2005 gate until the full dataset and benchmark-calibrated grid
    choices are run.
    """

    if not cases:
        raise ValueError("At least one sensitivity case is required.")
    data = _selected_reference_rows(
        reference_csv,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
    )

    rows: list[dict[str, float | str | int | bool]] = []
    cache: dict[tuple[object, ...], object] = {}
    for row_index, item in data.iterrows():
        coefficient = str(item["coefficient"]).strip().upper()
        prefix, matrix_i, matrix_j = _coefficient_matrix_indices(coefficient)
        reference = float(item["reference_value"])
        normalization = str(item.get("normalization", "ma2005"))
        length = float(item.get("length_m", 3.0))
        beam = float(item.get("beam_m", 0.3))
        draft = float(item.get("draft_m", 0.1875))
        displacement_volume = float(item.get("displacement_volume_m3", math.nan))
        if not np.isfinite(displacement_volume) or displacement_volume <= 0.0:
            displacement_volume = float(4.0 / 9.0 * length * beam * draft)
        omega_hat = float(item["omega_e_sqrt_l_over_g"])
        omega = omega_hat * math.sqrt(float(gravity_m_s2) / length)
        speed_mps, fn_l = _speed_from_row(item, length, gravity_m_s2)
        if speed_mps <= 0.0:
            rows.append(
                {
                    "row": int(row_index),
                    "case_name": "",
                    "coefficient": coefficient,
                    "diagnostic_status": "ERROR",
                    "solver_status": "speed_mps could not be inferred from Ma row",
                    "gate_role": MATCHED_WIGLEY_SENSITIVITY_STATUS,
                }
            )
            continue
        tolerance = 0.15 if matrix_i == matrix_j else 0.30
        scale = _coefficient_scale(prefix, matrix_i, matrix_j, rho_water_kg_m3, length, gravity_m_s2, displacement_volume)
        for case in cases:
            grid_audit = a1_grid_recommendation(case, fn_l)
            cache_key = (
                case,
                round(omega, 12),
                round(speed_mps, 12),
                length,
                beam,
                draft,
                rho_water_kg_m3,
                gravity_m_s2,
            )
            try:
                if cache_key not in cache:
                    hull = make_wigley_iii_hull(
                        length_m=length,
                        beam_m=beam,
                        draft_m=draft,
                        station_count=int(case.station_count),
                    )
                    body = RigidBody6DOF.from_radii(
                        float(rho_water_kg_m3) * displacement_volume,
                        0.1 * beam,
                        0.25 * length,
                        0.25 * length,
                    )
                    cache[cache_key] = assemble_frequency_domain_from_matched_station_hull(
                        hull,
                        body,
                        np.asarray([omega], dtype=float),
                        speed_mps,
                        config=case.config(),
                        rho_water_kg_m3=float(rho_water_kg_m3),
                        gravity_m_s2=float(gravity_m_s2),
                        history_steps=int(case.history_steps),
                        history_quadrature_count=int(case.history_quadrature_count),
                        history_k_max=float(case.history_k_max),
                        include_end_term=bool(case.include_end_term),
                        end_station=str(case.end_station),
                        end_term_scale=float(case.end_term_scale),
                        pitch_radiation_sign=float(case.pitch_radiation_sign),
                        pitch_radiation_lever_sign=float(case.pitch_radiation_lever_sign),
                        pitch_forward_speed_sign=float(case.pitch_forward_speed_sign),
                        pitch_moment_sign=float(case.pitch_moment_sign),
                        time_step_scale=float(case.time_step_scale),
                        free_surface_velocity_scale=float(case.free_surface_velocity_scale),
                        history_rhs_scale=float(case.history_rhs_scale),
                        history_convolution_rule=str(case.history_convolution_rule),
                        history_potential_kernel_scale=float(case.history_potential_kernel_scale),
                        history_normal_derivative_kernel_scale=float(case.history_normal_derivative_kernel_scale),
                        control_image_scale=float(case.control_image_scale),
                        control_potential_kernel_scale=float(case.control_potential_kernel_scale),
                        control_normal_derivative_kernel_scale=float(case.control_normal_derivative_kernel_scale),
                        control_diagonal_sign=float(case.control_diagonal_sign),
                        inner_a_scale=float(case.inner_a_scale),
                        inner_b_scale=float(case.inner_b_scale),
                        inner_diagonal_sign=float(case.inner_diagonal_sign),
                        pressure_gradient_scheme=str(case.pressure_gradient_scheme),
                        pressure_gradient_scale=float(case.pressure_gradient_scale),
                        force_assembly_route=str(case.force_assembly_route),
                        apply_local_time_phase=bool(case.apply_local_time_phase),
                        local_time_phase_gradient_correction=bool(case.local_time_phase_gradient_correction),
                        clip_inner_free_surface_to_waterline=bool(case.clip_inner_free_surface_to_waterline),
                        two_zone_inner_free_surface=bool(case.two_zone_inner_free_surface),
                        use_free_surface_marching=bool(case.use_free_surface_marching),
                    )
                hydro = cache[cache_key]
                matrix = hydro.added_mass if prefix == "A" else hydro.radiation_damping
                raw = float(matrix[0, matrix_i, matrix_j])
                computed = float(raw / scale)
                metrics = _error_metrics(reference, computed, tolerance, matrix_i, matrix_j, normalization)
                scale_audit = _required_scale_audit(raw, reference, scale)
                heave_residual = np.asarray(hydro.contribution_breakdown["heave_residuals"], dtype=float)
                pitch_residual = np.asarray(hydro.contribution_breakdown["pitch_residuals"], dtype=float)
                heave_condition = np.asarray(hydro.contribution_breakdown["heave_condition_numbers"], dtype=float)
                pitch_condition = np.asarray(hydro.contribution_breakdown["pitch_condition_numbers"], dtype=float)
                local_index = {2: 0, 4: 1}.get(matrix_i)
                local_column = {2: 0, 4: 1}.get(matrix_j)
                raw_total_from_force = raw
                raw_end_term = 0.0
                raw_body_integral = raw
                raw_time_derivative = 0.0
                raw_forward_speed = 0.0
                raw_stokes_body_forward_speed = 0.0
                raw_stokes_forward_speed_with_end_term = 0.0
                raw_stokes_total_with_end_term = 0.0
                if local_index is not None and local_column is not None:
                    force_matrix = np.asarray(
                        hydro.contribution_breakdown.get("heave_pitch_complex_force_matrices", np.zeros((1, 2, 2))),
                        dtype=complex,
                    )
                    end_matrix = np.asarray(
                        hydro.contribution_breakdown.get("heave_pitch_end_term_force_matrices", np.zeros((1, 2, 2))),
                        dtype=complex,
                    )
                    time_matrix = np.asarray(
                        hydro.contribution_breakdown.get(
                            "heave_pitch_time_derivative_force_matrices",
                            np.zeros((1, 2, 2)),
                        ),
                        dtype=complex,
                    )
                    forward_matrix = np.asarray(
                        hydro.contribution_breakdown.get(
                            "heave_pitch_forward_speed_force_matrices",
                            np.zeros((1, 2, 2)),
                        ),
                        dtype=complex,
                    )
                    stokes_body_forward_matrix = np.asarray(
                        hydro.contribution_breakdown.get(
                            "heave_pitch_stokes_body_forward_speed_force_matrices",
                            np.zeros((1, 2, 2)),
                        ),
                        dtype=complex,
                    )
                    raw_total_from_force = _force_component_to_coefficient(
                        prefix,
                        force_matrix[0, local_index, local_column],
                        omega,
                    )
                    raw_end_term = _force_component_to_coefficient(
                        prefix,
                        end_matrix[0, local_index, local_column],
                        omega,
                    )
                    raw_time_derivative = _force_component_to_coefficient(
                        prefix,
                        time_matrix[0, local_index, local_column],
                        omega,
                    )
                    raw_forward_speed = _force_component_to_coefficient(
                        prefix,
                        forward_matrix[0, local_index, local_column],
                        omega,
                    )
                    raw_stokes_body_forward_speed = _force_component_to_coefficient(
                        prefix,
                        stokes_body_forward_matrix[0, local_index, local_column],
                        omega,
                    )
                    raw_body_integral = raw_total_from_force - raw_end_term
                    raw_stokes_forward_speed_with_end_term = raw_stokes_body_forward_speed + raw_end_term
                    raw_stokes_total_with_end_term = raw_time_derivative + raw_stokes_forward_speed_with_end_term
                rows.append(
                    {
                        "row": int(row_index),
                        "case_name": case.name,
                        "hull": str(item.get("hull", "wigley_iii")),
                        "speed_case": str(item.get("speed_case", "")),
                        "fn_l": float(fn_l),
                        "speed_mps": float(speed_mps),
                        "omega_e_sqrt_l_over_g": float(omega_hat),
                        "omega_rad_s": float(omega),
                        "coefficient": coefficient,
                        "reference_value": reference,
                        "raw_computed_value": raw,
                        "raw_total_from_force_value": raw_total_from_force,
                        "raw_body_integral_value": raw_body_integral,
                        "raw_end_term_value": raw_end_term,
                        "raw_time_derivative_value": raw_time_derivative,
                        "raw_forward_speed_value": raw_forward_speed,
                        "raw_stokes_body_forward_speed_value": raw_stokes_body_forward_speed,
                        "raw_stokes_forward_speed_with_end_term_value": raw_stokes_forward_speed_with_end_term,
                        "raw_stokes_total_with_end_term_value": raw_stokes_total_with_end_term,
                        "computed_value": computed,
                        "computed_body_integral_value": float(raw_body_integral / scale),
                        "computed_end_term_value": float(raw_end_term / scale),
                        "computed_time_derivative_value": float(raw_time_derivative / scale),
                        "computed_forward_speed_value": float(raw_forward_speed / scale),
                        "computed_stokes_body_forward_speed_value": float(raw_stokes_body_forward_speed / scale),
                        "computed_stokes_forward_speed_with_end_term_value": float(
                            raw_stokes_forward_speed_with_end_term / scale
                        ),
                        "computed_stokes_total_with_end_term_value": float(raw_stokes_total_with_end_term / scale),
                        "normalization": normalization,
                        "normalization_scale": float(scale),
                        "ma2005_normalization_formula": _ma2005_normalization_formula(prefix, matrix_i, matrix_j),
                        "required_normalization_scale": scale_audit["required_normalization_scale"],
                        "required_normalization_scale_over_current": scale_audit[
                            "required_normalization_scale_over_current"
                        ],
                        "required_magnitude_scale_over_current": scale_audit[
                            "required_magnitude_scale_over_current"
                        ],
                        "normalization_scale_diagnosis": scale_audit["normalization_scale_diagnosis"],
                        "normalization_audit_status": "INFO_NOT_GATE",
                        "abs_error": metrics["abs_error"],
                        "rel_error": metrics["rel_error"],
                        "effective_abs_tolerance": metrics["effective_abs_tolerance"],
                        "gate_error_ratio": metrics["gate_error_ratio"],
                        "error_metric": metrics["error_metric"],
                        "diagnostic_status": metrics["status"],
                        "gate_role": MATCHED_WIGLEY_SENSITIVITY_STATUS,
                        "station_count": int(case.station_count),
                        "body_panels_per_section": int(case.body_panels_per_section),
                        "free_surface_inner_panels": int(case.free_surface_inner_panels),
                        "free_surface_outer_panels": int(case.free_surface_outer_panels),
                        "control_surface_radius_beams": float(case.control_surface_radius_beams),
                        "history_steps": int(case.history_steps),
                        "history_quadrature_count": int(case.history_quadrature_count),
                        "history_k_max": float(case.history_k_max),
                        "include_end_term": bool(case.include_end_term),
                        "end_station": str(case.end_station),
                        "end_term_scale": float(case.end_term_scale),
                        "pitch_radiation_sign": float(case.pitch_radiation_sign),
                        "pitch_radiation_lever_sign": float(case.pitch_radiation_lever_sign),
                        "pitch_forward_speed_sign": float(case.pitch_forward_speed_sign),
                        "pitch_moment_sign": float(case.pitch_moment_sign),
                        "time_step_scale": float(case.time_step_scale),
                        "free_surface_velocity_scale": float(case.free_surface_velocity_scale),
                        "history_rhs_scale": float(case.history_rhs_scale),
                        "history_convolution_rule": str(case.history_convolution_rule).strip().lower(),
                        "history_potential_kernel_scale": float(case.history_potential_kernel_scale),
                        "history_normal_derivative_kernel_scale": float(case.history_normal_derivative_kernel_scale),
                        "control_image_scale": float(case.control_image_scale),
                        "control_potential_kernel_scale": float(case.control_potential_kernel_scale),
                        "control_normal_derivative_kernel_scale": float(case.control_normal_derivative_kernel_scale),
                        "control_diagonal_sign": float(case.control_diagonal_sign),
                        "inner_a_scale": float(case.inner_a_scale),
                        "inner_b_scale": float(case.inner_b_scale),
                        "inner_diagonal_sign": float(case.inner_diagonal_sign),
                        "pressure_gradient_scheme": str(case.pressure_gradient_scheme).strip().lower(),
                        "pressure_gradient_scale": float(case.pressure_gradient_scale),
                        "clip_inner_free_surface_to_waterline": bool(case.clip_inner_free_surface_to_waterline),
                        "two_zone_inner_free_surface": bool(case.two_zone_inner_free_surface),
                        "use_free_surface_marching": bool(case.use_free_surface_marching),
                        "max_heave_residual": float(np.max(heave_residual)),
                        "max_pitch_residual": float(np.max(pitch_residual)),
                        "max_heave_condition_number": float(np.max(heave_condition)),
                        "max_pitch_condition_number": float(np.max(pitch_condition)),
                        "solver_status": str(hydro.validity.status),
                        "source_figure": str(item.get("source_figure", "")),
                        "source_note": str(item.get("source_note", "")),
                        **grid_audit,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "row": int(row_index),
                        "case_name": case.name,
                        "coefficient": coefficient,
                        "reference_value": reference,
                        "diagnostic_status": "ERROR",
                        "solver_status": f"error: {exc}",
                        "gate_role": MATCHED_WIGLEY_SENSITIVITY_STATUS,
                    }
                )
    return rows


def matched_wigley_station_diagnostic_rows(
    reference_csv: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> list[dict[str, float | str | int | bool]]:
    """Return station-level force/free-surface diagnostics for matched Wigley sweeps.

    The rows are diagnostic-only. They expose how a selected heave/pitch
    coefficient is built up along the hull so marching growth can be separated
    from end-term and normalization issues.
    """

    if not cases:
        raise ValueError("At least one sensitivity case is required.")
    data = _selected_reference_rows(
        reference_csv,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
    )
    rows: list[dict[str, float | str | int | bool]] = []
    cache: dict[tuple[object, ...], object] = {}
    for row_index, item in data.iterrows():
        coefficient = str(item["coefficient"]).strip().upper()
        prefix, matrix_i, matrix_j = _coefficient_matrix_indices(coefficient)
        local_row = {2: 0, 4: 1}.get(matrix_i)
        local_col = {2: 0, 4: 1}.get(matrix_j)
        if local_row is None or local_col is None:
            rows.append(
                {
                    "row": int(row_index),
                    "case_name": "",
                    "coefficient": coefficient,
                    "diagnostic_status": "SKIPPED",
                    "solver_status": "station diagnostics currently support only heave/pitch coefficients",
                    "gate_role": MATCHED_WIGLEY_SENSITIVITY_STATUS,
                }
            )
            continue
        reference = float(item["reference_value"])
        length = float(item.get("length_m", 3.0))
        beam = float(item.get("beam_m", 0.3))
        draft = float(item.get("draft_m", 0.1875))
        displacement_volume = float(item.get("displacement_volume_m3", math.nan))
        if not np.isfinite(displacement_volume) or displacement_volume <= 0.0:
            displacement_volume = float(4.0 / 9.0 * length * beam * draft)
        omega_hat = float(item["omega_e_sqrt_l_over_g"])
        omega = omega_hat * math.sqrt(float(gravity_m_s2) / length)
        speed_mps, fn_l = _speed_from_row(item, length, gravity_m_s2)
        if speed_mps <= 0.0:
            rows.append(
                {
                    "row": int(row_index),
                    "case_name": "",
                    "coefficient": coefficient,
                    "diagnostic_status": "ERROR",
                    "solver_status": "speed_mps could not be inferred from Ma row",
                    "gate_role": MATCHED_WIGLEY_SENSITIVITY_STATUS,
                }
            )
            continue
        scale = _coefficient_scale(prefix, matrix_i, matrix_j, rho_water_kg_m3, length, gravity_m_s2, displacement_volume)
        for case in cases:
            grid_audit = a1_grid_recommendation(case, fn_l)
            cache_key = (
                case,
                round(omega, 12),
                round(speed_mps, 12),
                length,
                beam,
                draft,
                rho_water_kg_m3,
                gravity_m_s2,
            )
            try:
                if cache_key not in cache:
                    hull = make_wigley_iii_hull(
                        length_m=length,
                        beam_m=beam,
                        draft_m=draft,
                        station_count=int(case.station_count),
                    )
                    cache[cache_key] = solve_station_hull_heave_pitch_matched_sweep(
                        hull,
                        omega,
                        speed_mps,
                        config=case.config(),
                        rho_water_kg_m3=float(rho_water_kg_m3),
                        history_steps=int(case.history_steps),
                        history_quadrature_count=int(case.history_quadrature_count),
                        history_k_max=float(case.history_k_max),
                        include_end_term=bool(case.include_end_term),
                        end_station=str(case.end_station),
                        end_term_scale=float(case.end_term_scale),
                        pitch_radiation_sign=float(case.pitch_radiation_sign),
                        pitch_radiation_lever_sign=float(case.pitch_radiation_lever_sign),
                        pitch_forward_speed_sign=float(case.pitch_forward_speed_sign),
                        pitch_moment_sign=float(case.pitch_moment_sign),
                        time_step_scale=float(case.time_step_scale),
                        free_surface_velocity_scale=float(case.free_surface_velocity_scale),
                        history_rhs_scale=float(case.history_rhs_scale),
                        history_convolution_rule=str(case.history_convolution_rule),
                        history_potential_kernel_scale=float(case.history_potential_kernel_scale),
                        history_normal_derivative_kernel_scale=float(case.history_normal_derivative_kernel_scale),
                        control_image_scale=float(case.control_image_scale),
                        control_potential_kernel_scale=float(case.control_potential_kernel_scale),
                        control_normal_derivative_kernel_scale=float(case.control_normal_derivative_kernel_scale),
                        control_diagonal_sign=float(case.control_diagonal_sign),
                        inner_a_scale=float(case.inner_a_scale),
                        inner_b_scale=float(case.inner_b_scale),
                        inner_diagonal_sign=float(case.inner_diagonal_sign),
                        pressure_gradient_scheme=str(case.pressure_gradient_scheme),
                        pressure_gradient_scale=float(case.pressure_gradient_scale),
                        clip_inner_free_surface_to_waterline=bool(case.clip_inner_free_surface_to_waterline),
                        two_zone_inner_free_surface=bool(case.two_zone_inner_free_surface),
                        use_free_surface_marching=bool(case.use_free_surface_marching),
                    )
                sweep = cache[cache_key]
                forces = (
                    sweep.pressure_force_sweep.heave_mode_forces
                    if local_col == 0
                    else sweep.pressure_force_sweep.pitch_mode_forces
                )
                pressures = (
                    sweep.pressure_force_sweep.heave_mode_pressures
                    if local_col == 0
                    else sweep.pressure_force_sweep.pitch_mode_pressures
                )
                solutions = sweep.heave_mode_solutions if local_col == 0 else sweep.pitch_mode_solutions
                free_potential = (
                    sweep.heave_free_surface_potential_by_station
                    if local_col == 0
                    else sweep.pitch_free_surface_potential_by_station
                )
                free_elevation = (
                    sweep.heave_free_surface_elevation_by_station
                    if local_col == 0
                    else sweep.pitch_free_surface_elevation_by_station
                )
                free_potential_after = (
                    sweep.heave_free_surface_potential_after_station
                    if local_col == 0
                    else sweep.pitch_free_surface_potential_after_station
                )
                free_elevation_after = (
                    sweep.heave_free_surface_elevation_after_station
                    if local_col == 0
                    else sweep.pitch_free_surface_elevation_after_station
                )
                history_rhs = (
                    sweep.heave_outer_history_rhs_by_station
                    if local_col == 0
                    else sweep.pitch_outer_history_rhs_by_station
                )
                update_kinds = (
                    sweep.heave_free_surface_update_kind_by_station
                    if local_col == 0
                    else sweep.pitch_free_surface_update_kind_by_station
                )
                force_density = np.asarray(
                    [
                        force.heave_force_per_m if local_row == 0 else force.pitch_moment_per_m
                        for force in forces
                    ],
                    dtype=complex,
                )
                time_density = np.asarray(
                    [
                        force.heave_force_time_derivative_per_m
                        if local_row == 0
                        else force.pitch_moment_time_derivative_per_m
                        for force in forces
                    ],
                    dtype=complex,
                )
                forward_density = np.asarray(
                    [
                        force.heave_force_forward_speed_per_m
                        if local_row == 0
                        else force.pitch_moment_forward_speed_per_m
                        for force in forces
                    ],
                    dtype=complex,
                )
                stokes_body_forward_density = np.asarray(
                    sweep.pressure_force_sweep.stokes_body_forward_speed.force_density_by_station[
                        :,
                        local_row,
                        local_col,
                    ],
                    dtype=complex,
                )
                cumulative_force = _cumulative_trapezoid_complex(sweep.x_m, force_density)
                cumulative_time = _cumulative_trapezoid_complex(sweep.x_m, time_density)
                cumulative_forward = _cumulative_trapezoid_complex(sweep.x_m, forward_density)
                cumulative_stokes_body_forward = _cumulative_trapezoid_complex(
                    sweep.x_m,
                    stokes_body_forward_density,
                )
                weights = _trapezoid_weights(sweep.x_m)
                end_force = sweep.pressure_force_sweep.assembly.end_term_force_matrix[local_row, local_col]
                end_value = _force_component_to_coefficient(prefix, end_force, omega) / scale
                order_rank = {int(local_index): rank for rank, local_index in enumerate(sweep.solve_order)}
                for station_local_index, force in enumerate(forces):
                    block_audit = (
                        sweep.heave_block_audits[station_local_index]
                        if local_col == 0
                        else sweep.pitch_block_audits[station_local_index]
                    )
                    density_value = force_density[station_local_index]
                    time_density_value = time_density[station_local_index]
                    forward_density_value = forward_density[station_local_index]
                    stokes_body_forward_density_value = stokes_body_forward_density[station_local_index]
                    weighted_force = density_value * weights[station_local_index]
                    weighted_time_force = time_density_value * weights[station_local_index]
                    weighted_forward_force = forward_density_value * weights[station_local_index]
                    weighted_stokes_body_forward_force = stokes_body_forward_density_value * weights[station_local_index]
                    cumulative_value = _force_component_to_coefficient(
                        prefix,
                        cumulative_force[station_local_index],
                        omega,
                    ) / scale
                    cumulative_time_value = _force_component_to_coefficient(
                        prefix,
                        cumulative_time[station_local_index],
                        omega,
                    ) / scale
                    cumulative_forward_value = _force_component_to_coefficient(
                        prefix,
                        cumulative_forward[station_local_index],
                        omega,
                    ) / scale
                    cumulative_stokes_body_forward_value = _force_component_to_coefficient(
                        prefix,
                        cumulative_stokes_body_forward[station_local_index],
                        omega,
                    ) / scale
                    fs_potential_before_norm = _complex_norm(free_potential[station_local_index])
                    fs_elevation_before_norm = _complex_norm(free_elevation[station_local_index])
                    fs_potential_after_norm = _complex_norm(free_potential_after[station_local_index])
                    fs_elevation_after_norm = _complex_norm(free_elevation_after[station_local_index])
                    if local_col == 0:
                        body_condition = heave_radiation_normal_velocity(
                            sweep.bodies[station_local_index],
                            omega,
                        )
                        pitch_oscillation = np.zeros_like(body_condition)
                        pitch_forward_speed = np.zeros_like(body_condition)
                    else:
                        pitch_oscillation = sweep.pitch_body_condition_oscillation_by_station[station_local_index]
                        pitch_forward_speed = sweep.pitch_body_condition_forward_speed_by_station[station_local_index]
                        body_condition = pitch_oscillation + pitch_forward_speed
                    pitch_moment_sign_value = float(case.pitch_moment_sign)
                    base_lever_arm = (
                        float(force.lever_arm_m / pitch_moment_sign_value)
                        if abs(pitch_moment_sign_value) > 1e-12
                        else float(force.lever_arm_m)
                    )
                    convention_audit = audit_heave_pitch_a1_convention(
                        sweep.bodies[station_local_index],
                        omega,
                        radiation_lever_arm_m=float(case.pitch_radiation_lever_sign) * base_lever_arm,
                        moment_lever_arm_m=float(case.pitch_moment_sign) * base_lever_arm,
                        forward_speed_mps=speed_mps,
                        pitch_radiation_sign=float(case.pitch_radiation_sign),
                        pitch_forward_speed_sign=float(case.pitch_forward_speed_sign),
                        stokes_pitch_m5_sign=float(case.pitch_moment_sign),
                    )
                    unit_closure = _a1_potential_unit_closure_fields(
                        sweep.bodies[station_local_index],
                        body_condition,
                        solutions[station_local_index],
                        pressures[station_local_index],
                        force,
                    )
                    rows.append(
                        {
                            "row": int(row_index),
                            "case_name": case.name,
                            "coefficient": coefficient,
                            "diagnostic_status": "OK",
                            "gate_role": MATCHED_WIGLEY_SENSITIVITY_STATUS,
                            "hull": str(item.get("hull", "wigley_iii")),
                            "speed_case": str(item.get("speed_case", "")),
                            "fn_l": float(fn_l),
                            "speed_mps": float(speed_mps),
                            "omega_e_sqrt_l_over_g": float(omega_hat),
                            "omega_rad_s": float(omega),
                            "reference_value": reference,
                            "normalization_scale": float(scale),
                            "station_local_index": int(station_local_index),
                            "active_station_index": int(sweep.active_station_indices[station_local_index]),
                            "solve_order_rank": int(order_rank.get(station_local_index, -1)),
                            "x_m": float(sweep.x_m[station_local_index]),
                            "x_from_bow_m": float(length - sweep.x_m[station_local_index]),
                            "trapezoid_weight_m": float(weights[station_local_index]),
                            "inner_free_surface_y_min_m": float(np.min(sweep.inner_free_surface_y_by_station[station_local_index])),
                            "inner_free_surface_y_max_m": float(np.max(sweep.inner_free_surface_y_by_station[station_local_index])),
                            "inner_free_surface_panel_length_min_m": float(
                                np.min(sweep.inner_free_surface_panel_length_by_station[station_local_index])
                            ),
                            "inner_free_surface_panel_length_max_m": float(
                                np.max(sweep.inner_free_surface_panel_length_by_station[station_local_index])
                            ),
                            "selected_mode": "heave" if local_col == 0 else "pitch",
                            "selected_generalized_row": "heave_force" if local_row == 0 else "pitch_moment",
                            "lever_arm_m": float(force.lever_arm_m),
                            "a1_coordinate_convention_name": DEFAULT_A1_HEAVE_PITCH_CONVENTION.name,
                            "a1_coordinate_convention_status": str(
                                DEFAULT_A1_HEAVE_PITCH_CONVENTION.validity.status
                            ),
                            "a1_convention_audit_status": str(convention_audit.validity.status),
                            "a1_radiation_lever_arm_m": float(convention_audit.radiation_lever_arm_m),
                            "a1_moment_lever_arm_m": float(convention_audit.moment_lever_arm_m),
                            "a1_heave_n3_to_force_row_relative_residual": float(
                                convention_audit.heave_n3_to_force_row_relative_residual
                            ),
                            "a1_pitch_n5_to_moment_row_relative_residual": float(
                                convention_audit.pitch_n5_to_moment_row_relative_residual
                            ),
                            "a1_pitch_m5_forward_to_stokes_relative_residual": float(
                                convention_audit.pitch_m5_forward_to_stokes_relative_residual
                            ),
                            "a1_pitch_m5_to_n5_norm_ratio": float(convention_audit.pitch_m5_to_n5_norm_ratio),
                            "a1_heave_force_row_norm": _complex_norm(convention_audit.heave_force_row_per_length),
                            "a1_pitch_moment_row_norm": _complex_norm(convention_audit.pitch_moment_row_per_length),
                            "a1_pitch_m5_norm": _complex_norm(
                                convention_audit.pitch_m5_from_forward_body_condition
                            ),
                            "a1_pitch_n5_norm": _complex_norm(convention_audit.pitch_n5_from_body_condition),
                            "body_condition_norm": _complex_norm(body_condition),
                            "body_condition_max_abs": _complex_max_abs(body_condition),
                            "pitch_body_condition_oscillation_norm": _complex_norm(pitch_oscillation),
                            "pitch_body_condition_oscillation_max_abs": _complex_max_abs(pitch_oscillation),
                            "pitch_body_condition_forward_speed_norm": _complex_norm(pitch_forward_speed),
                            "pitch_body_condition_forward_speed_max_abs": _complex_max_abs(pitch_forward_speed),
                            "pitch_body_condition_forward_to_oscillation_norm_ratio": _safe_ratio(
                                _complex_norm(pitch_forward_speed),
                                _complex_norm(pitch_oscillation),
                            ),
                            "complex_force_density_real": float(np.real(density_value)),
                            "complex_force_density_imag": float(np.imag(density_value)),
                            "station_weighted_force_real": float(np.real(weighted_force)),
                            "station_weighted_force_imag": float(np.imag(weighted_force)),
                            "station_weighted_normalized_contribution": float(
                                _force_component_to_coefficient(prefix, weighted_force, omega) / scale
                            ),
                            "station_weighted_time_derivative_normalized_contribution": float(
                                _force_component_to_coefficient(prefix, weighted_time_force, omega) / scale
                            ),
                            "station_weighted_forward_speed_normalized_contribution": float(
                                _force_component_to_coefficient(prefix, weighted_forward_force, omega) / scale
                            ),
                            "station_weighted_stokes_body_forward_speed_normalized_contribution": float(
                                _force_component_to_coefficient(prefix, weighted_stokes_body_forward_force, omega) / scale
                            ),
                            "station_weighted_forward_minus_stokes_body_normalized_contribution": float(
                                _force_component_to_coefficient(
                                    prefix,
                                    weighted_forward_force - weighted_stokes_body_forward_force,
                                    omega,
                                )
                                / scale
                            ),
                            "cumulative_body_integral_value": float(cumulative_value),
                            "cumulative_time_derivative_value": float(cumulative_time_value),
                            "cumulative_forward_speed_value": float(cumulative_forward_value),
                            "cumulative_stokes_body_forward_speed_value": float(cumulative_stokes_body_forward_value),
                            "cumulative_forward_minus_stokes_body_value": float(
                                cumulative_forward_value - cumulative_stokes_body_forward_value
                            ),
                            "cumulative_time_plus_stokes_body_forward_value": float(
                                cumulative_time_value + cumulative_stokes_body_forward_value
                            ),
                            "end_term_value": float(end_value),
                            "cumulative_with_end_term_value": float(cumulative_value + end_value),
                            "cumulative_stokes_with_end_term_value": float(
                                cumulative_time_value + cumulative_stokes_body_forward_value + end_value
                            ),
                            "body_potential_norm": _complex_norm(solutions[station_local_index].body_potential),
                            "body_potential_max_abs": _complex_max_abs(solutions[station_local_index].body_potential),
                            "control_potential_norm": _complex_norm(solutions[station_local_index].control_potential),
                            "control_potential_max_abs": _complex_max_abs(solutions[station_local_index].control_potential),
                            "control_normal_derivative_norm": _complex_norm(
                                solutions[station_local_index].control_normal_derivative
                            ),
                            "control_normal_derivative_max_abs": _complex_max_abs(
                                solutions[station_local_index].control_normal_derivative
                            ),
                            "body_potential_x_gradient_norm": _complex_norm(
                                pressures[station_local_index].body_potential_x_gradient
                            ),
                            "pressure_norm": _complex_norm(pressures[station_local_index].pressure_pa),
                            "pressure_max_abs": _complex_max_abs(pressures[station_local_index].pressure_pa),
                            "pressure_time_derivative_norm": _complex_norm(
                                pressures[station_local_index].pressure_time_derivative_pa
                            ),
                            "pressure_time_derivative_max_abs": _complex_max_abs(
                                pressures[station_local_index].pressure_time_derivative_pa
                            ),
                            "pressure_forward_speed_norm": _complex_norm(
                                pressures[station_local_index].pressure_forward_speed_pa
                            ),
                            "pressure_forward_speed_max_abs": _complex_max_abs(
                                pressures[station_local_index].pressure_forward_speed_pa
                            ),
                            "inner_free_surface_normal_derivative_norm": _complex_norm(
                                solutions[station_local_index].inner_free_surface_normal_derivative
                            ),
                            "inner_free_surface_normal_derivative_max_abs": _complex_max_abs(
                                solutions[station_local_index].inner_free_surface_normal_derivative
                            ),
                            "outer_history_rhs_norm_before_solve": _complex_norm(history_rhs[station_local_index]),
                            "outer_history_rhs_max_abs_before_solve": _complex_max_abs(history_rhs[station_local_index]),
                            "free_surface_update_kind": str(update_kinds[station_local_index]),
                            "free_surface_potential_norm_before_solve": fs_potential_before_norm,
                            "free_surface_elevation_norm_before_solve": fs_elevation_before_norm,
                            "free_surface_potential_norm_after_update": fs_potential_after_norm,
                            "free_surface_elevation_norm_after_update": fs_elevation_after_norm,
                            "free_surface_potential_growth_ratio": _safe_ratio(
                                fs_potential_after_norm,
                                fs_potential_before_norm,
                            ),
                            "free_surface_elevation_growth_ratio": _safe_ratio(
                                fs_elevation_after_norm,
                                fs_elevation_before_norm,
                            ),
                            "station_condition_number": float(
                                sweep.heave_condition_numbers[station_local_index]
                                if local_col == 0
                                else sweep.pitch_condition_numbers[station_local_index]
                            ),
                            "station_residual": float(
                                sweep.heave_residuals[station_local_index]
                                if local_col == 0
                                else sweep.pitch_residuals[station_local_index]
                            ),
                            **_matched_block_audit_fields(block_audit),
                            **unit_closure,
                            "solver_status": str(sweep.validity.status),
                            "station_count": int(case.station_count),
                            "body_panels_per_section": int(case.body_panels_per_section),
                            "free_surface_inner_panels": int(case.free_surface_inner_panels),
                            "free_surface_outer_panels": int(case.free_surface_outer_panels),
                            "control_surface_radius_beams": float(case.control_surface_radius_beams),
                            "history_steps": int(case.history_steps),
                            "history_quadrature_count": int(case.history_quadrature_count),
                            "history_k_max": float(case.history_k_max),
                            "include_end_term": bool(case.include_end_term),
                            "end_station": str(case.end_station),
                            "end_term_scale": float(case.end_term_scale),
                            "pitch_radiation_sign": float(case.pitch_radiation_sign),
                            "pitch_radiation_lever_sign": float(case.pitch_radiation_lever_sign),
                            "pitch_forward_speed_sign": float(case.pitch_forward_speed_sign),
                            "pitch_moment_sign": float(case.pitch_moment_sign),
                            "time_step_scale": float(case.time_step_scale),
                            "free_surface_velocity_scale": float(case.free_surface_velocity_scale),
                            "history_rhs_scale": float(case.history_rhs_scale),
                            "history_convolution_rule": str(case.history_convolution_rule).strip().lower(),
                            "history_potential_kernel_scale": float(case.history_potential_kernel_scale),
                            "history_normal_derivative_kernel_scale": float(case.history_normal_derivative_kernel_scale),
                            "control_image_scale": float(case.control_image_scale),
                            "control_potential_kernel_scale": float(case.control_potential_kernel_scale),
                            "control_normal_derivative_kernel_scale": float(case.control_normal_derivative_kernel_scale),
                            "control_diagonal_sign": float(case.control_diagonal_sign),
                            "inner_a_scale": float(case.inner_a_scale),
                            "inner_b_scale": float(case.inner_b_scale),
                            "inner_diagonal_sign": float(case.inner_diagonal_sign),
                            "pressure_gradient_scheme": str(case.pressure_gradient_scheme).strip().lower(),
                            "pressure_gradient_scale": float(case.pressure_gradient_scale),
                            "clip_inner_free_surface_to_waterline": bool(case.clip_inner_free_surface_to_waterline),
                            "two_zone_inner_free_surface": bool(case.two_zone_inner_free_surface),
                            "use_free_surface_marching": bool(case.use_free_surface_marching),
                            **grid_audit,
                        }
                    )
            except Exception as exc:
                rows.append(
                    {
                        "row": int(row_index),
                        "case_name": case.name,
                        "coefficient": coefficient,
                        "reference_value": reference,
                        "diagnostic_status": "ERROR",
                        "solver_status": f"error: {exc}",
                        "gate_role": MATCHED_WIGLEY_SENSITIVITY_STATUS,
                    }
                )
    return rows


def matched_wigley_a1_convention_candidate_rows(
    reference_csv: str | Path,
    *,
    candidates: tuple[A1ConventionCandidate, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> list[dict[str, float | str | int | bool]]:
    """Return Wigley III diagnostics annotated by controlled A1 convention candidates."""

    if not candidates:
        raise ValueError("At least one A1 convention candidate is required.")
    by_case_name = {candidate.case.name: candidate for candidate in candidates}
    rows = matched_wigley_sensitivity_rows(
        reference_csv,
        cases=tuple(candidate.case for candidate in candidates),
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    for row in rows:
        candidate = by_case_name.get(str(row.get("case_name", "")))
        if candidate is None:
            row.update(
                {
                    "a1_convention_candidate_name": "",
                    "a1_convention_candidate_status": "NOT_EVALUATED",
                    "a1_convention_changed_mapping_rows": "",
                    "a1_convention_hypothesis": "",
                    "a1_convention_description": "",
                    "default_convention_name": DEFAULT_A1_HEAVE_PITCH_CONVENTION.name,
                    "default_convention_status": DEFAULT_A1_HEAVE_PITCH_CONVENTION.validity.status,
                }
            )
            continue
        row.update(candidate.metadata_row())
    return rows


def matched_wigley_a1_control_surface_candidate_rows(
    reference_csv: str | Path,
    *,
    candidates: tuple[A1ControlSurfaceCandidate, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> list[dict[str, float | str | int | bool]]:
    """Return Wigley III diagnostics annotated by A1 Eq. (24) control-surface candidates."""

    if not candidates:
        raise ValueError("At least one A1 control-surface candidate is required.")
    by_case_name = {candidate.case.name: candidate for candidate in candidates}
    rows = matched_wigley_sensitivity_rows(
        reference_csv,
        cases=tuple(candidate.case for candidate in candidates),
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    for row in rows:
        candidate = by_case_name.get(str(row.get("case_name", "")))
        if candidate is None:
            row.update(
                {
                    "a1_control_candidate_name": "",
                    "a1_control_candidate_status": "NOT_EVALUATED",
                    "a1_control_changed_eq24_terms": "",
                    "a1_control_hypothesis": "",
                    "a1_control_description": "",
                }
            )
            continue
        row.update(candidate.metadata_row())
    return rows


def matched_wigley_a1_inner_kernel_candidate_rows(
    reference_csv: str | Path,
    *,
    candidates: tuple[A1InnerKernelCandidate, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> list[dict[str, float | str | int | bool]]:
    """Return Wigley III diagnostics annotated by A1 Eq. (23) inner-kernel candidates."""

    if not candidates:
        raise ValueError("At least one A1 inner-kernel candidate is required.")
    by_case_name = {candidate.case.name: candidate for candidate in candidates}
    rows = matched_wigley_sensitivity_rows(
        reference_csv,
        cases=tuple(candidate.case for candidate in candidates),
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    for row in rows:
        candidate = by_case_name.get(str(row.get("case_name", "")))
        if candidate is None:
            row.update(
                {
                    "a1_inner_candidate_name": "",
                    "a1_inner_candidate_status": "NOT_EVALUATED",
                    "a1_inner_changed_eq23_terms": "",
                    "a1_inner_hypothesis": "",
                    "a1_inner_description": "",
                }
            )
            continue
        row.update(candidate.metadata_row())
    return rows


def summarize_matched_wigley_sensitivity(detail: pd.DataFrame) -> pd.DataFrame:
    """Summarize diagnostic rows by case and coefficient.

    The summary is intentionally diagnostic-only: it ranks sensitivity cases and
    surfaces numerical failures, but it does not change the hard Ma 2005 gate.
    """

    if detail.empty:
        return pd.DataFrame()
    frame = detail.copy()
    for column in _SUMMARY_NUMERIC_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "case_name" not in frame.columns:
        frame["case_name"] = ""
    if "coefficient" not in frame.columns:
        frame["coefficient"] = ""
    if "diagnostic_status" not in frame.columns:
        frame["diagnostic_status"] = "ERROR"
    grid_defaults = {
        "a1_grid_recommendation_status": "NOT_EVALUATED",
        "a1_control_radius_ok": False,
        "a1_inner_free_surface_panels_ok": False,
        "a1_outer_or_control_panels_ok": False,
        "a1_station_count_ok": False,
        "a1_min_station_count_for_fn": np.nan,
    }
    for column, default in grid_defaults.items():
        if column not in frame.columns:
            frame[column] = default
    group_cols = ["case_name", "coefficient"]
    summary = (
        frame.groupby(group_cols, dropna=False)
        .agg(
            total_rows=("diagnostic_status", "count"),
            pass_rows=("diagnostic_status", lambda values: int(pd.Series(values).eq("PASS").sum())),
            fail_rows=("diagnostic_status", lambda values: int(pd.Series(values).eq("FAIL").sum())),
            error_rows=("diagnostic_status", lambda values: int(pd.Series(values).eq("ERROR").sum())),
            finite_gate_rows=("gate_error_ratio", "count"),
            median_gate_error_ratio=("gate_error_ratio", "median"),
            max_gate_error_ratio=("gate_error_ratio", "max"),
            median_abs_error=("abs_error", "median"),
            median_rel_error=("rel_error", "median"),
            max_heave_residual=("max_heave_residual", "max"),
            max_pitch_residual=("max_pitch_residual", "max"),
            max_heave_condition_number=("max_heave_condition_number", "max"),
            max_pitch_condition_number=("max_pitch_condition_number", "max"),
            a1_grid_recommendation_status=("a1_grid_recommendation_status", "first"),
            a1_control_radius_ok=("a1_control_radius_ok", "first"),
            a1_inner_free_surface_panels_ok=("a1_inner_free_surface_panels_ok", "first"),
            a1_outer_or_control_panels_ok=("a1_outer_or_control_panels_ok", "first"),
            a1_station_count_ok=("a1_station_count_ok", "first"),
            a1_min_station_count_for_fn=("a1_min_station_count_for_fn", "first"),
        )
        .reset_index()
    )
    summary["pass_fraction"] = summary["pass_rows"] / summary["total_rows"].clip(lower=1)
    summary["diagnostic_conclusion"] = np.select(
        [
            summary["error_rows"].eq(summary["total_rows"]),
            summary["fail_rows"].eq(0) & summary["error_rows"].eq(0),
            summary["fail_rows"].gt(0) & summary["pass_rows"].gt(0),
        ],
        [
            "all_rows_error_no_physics_comparison",
            "selected_rows_within_tolerance",
            "mixed_pass_fail_rows",
        ],
        default="selected_rows_outside_tolerance",
    )
    summary["gate_role"] = MATCHED_WIGLEY_SENSITIVITY_STATUS
    summary.sort_values(
        [
            "error_rows",
            "median_gate_error_ratio",
            "max_gate_error_ratio",
            "case_name",
            "coefficient",
        ],
        na_position="last",
        inplace=True,
    )
    return summary


def matched_wigley_best_case_summary(summary: pd.DataFrame) -> pd.DataFrame:
    """Return the best diagnostic case for each coefficient in a summary table."""

    if summary.empty:
        return pd.DataFrame()
    frame = summary.copy()
    for column in (
        "error_rows",
        "fail_rows",
        "pass_rows",
        "total_rows",
        "pass_fraction",
        "median_gate_error_ratio",
        "max_gate_error_ratio",
    ):
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "coefficient" not in frame.columns:
        frame["coefficient"] = ""
    if "case_name" not in frame.columns:
        frame["case_name"] = ""
    sortable = frame.assign(
        _sort_error_rows=frame["error_rows"].fillna(1e12),
        _sort_fail_rows=frame["fail_rows"].fillna(1e12),
        _sort_median=frame["median_gate_error_ratio"].fillna(np.inf),
        _sort_max=frame["max_gate_error_ratio"].fillna(np.inf),
        _sort_pass_fraction=-frame["pass_fraction"].fillna(0.0),
    ).sort_values(
        [
            "coefficient",
            "_sort_error_rows",
            "_sort_fail_rows",
            "_sort_median",
            "_sort_max",
            "_sort_pass_fraction",
            "case_name",
        ],
        na_position="last",
    )
    best = sortable.groupby("coefficient", dropna=False).head(1).copy()
    best.rename(columns={"case_name": "best_case_name"}, inplace=True)
    keep_columns = [
        "coefficient",
        "best_case_name",
        "total_rows",
        "pass_rows",
        "fail_rows",
        "error_rows",
        "finite_gate_rows",
        "pass_fraction",
        "median_gate_error_ratio",
        "max_gate_error_ratio",
        "median_abs_error",
        "median_rel_error",
        "max_heave_residual",
        "max_pitch_residual",
        "max_heave_condition_number",
        "max_pitch_condition_number",
        "a1_grid_recommendation_status",
        "a1_control_radius_ok",
        "a1_inner_free_surface_panels_ok",
        "a1_outer_or_control_panels_ok",
        "a1_station_count_ok",
        "a1_min_station_count_for_fn",
        "diagnostic_conclusion",
        "gate_role",
    ]
    for column in keep_columns:
        if column not in best.columns:
            best[column] = np.nan
    return best[keep_columns].reset_index(drop=True)


def write_matched_wigley_sensitivity(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = matched_wigley_sensitivity_rows(
        reference_csv,
        cases=cases,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    detail = pd.DataFrame(rows)
    for column in _SUMMARY_NUMERIC_COLUMNS:
        if column not in detail.columns:
            detail[column] = np.nan
    detail.to_csv(out_path / "matched_wigley_sensitivity.csv", index=False)
    if detail.empty:
        summary = pd.DataFrame()
        summary.to_csv(out_path / "matched_wigley_sensitivity_summary.csv", index=False)
        summary.to_csv(out_path / "matched_wigley_sensitivity_best_cases.csv", index=False)
        return detail, summary
    summary = summarize_matched_wigley_sensitivity(detail)
    best = matched_wigley_best_case_summary(summary)
    summary.to_csv(out_path / "matched_wigley_sensitivity_summary.csv", index=False)
    best.to_csv(out_path / "matched_wigley_sensitivity_best_cases.csv", index=False)
    return detail, summary


def write_a1_convention_candidate_benchmark(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    base_case: MatchedWigleySensitivityCase | None = None,
    candidates: tuple[A1ConventionCandidate, ...] | None = None,
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Write controlled A1 convention-candidate Wigley III diagnostics.

    The output is a benchmark diagnostic, not a hard-gate pass/fail result.
    Hard acceptance still requires the full Gate 1 dataset and audited
    digitized reference curves.
    """

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    candidate_set = candidates or a1_convention_candidate_cases(base_case)
    rows = matched_wigley_a1_convention_candidate_rows(
        reference_csv,
        candidates=candidate_set,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    detail = pd.DataFrame(rows)
    for column in _SUMMARY_NUMERIC_COLUMNS:
        if column not in detail.columns:
            detail[column] = np.nan
    summary = summarize_matched_wigley_sensitivity(detail)
    best = matched_wigley_best_case_summary(summary)
    mapping = pd.DataFrame(a1_convention_candidate_mapping_rows(candidate_set))
    metadata = pd.DataFrame([candidate.metadata_row() for candidate in candidate_set])
    detail.to_csv(out_path / "a1_convention_candidate_benchmark.csv", index=False)
    summary.to_csv(out_path / "a1_convention_candidate_summary.csv", index=False)
    best.to_csv(out_path / "a1_convention_candidate_best_cases.csv", index=False)
    mapping.to_csv(out_path / "a1_convention_candidate_mapping.csv", index=False)
    metadata.to_csv(out_path / "a1_convention_candidate_metadata.csv", index=False)
    return detail, summary, best


def write_a1_control_surface_candidate_benchmark(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    base_case: MatchedWigleySensitivityCase | None = None,
    candidates: tuple[A1ControlSurfaceCandidate, ...] | None = None,
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Write controlled A1 Eq. (24) control-surface Wigley III diagnostics."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    candidate_set = candidates or a1_control_surface_candidate_cases(base_case)
    rows = matched_wigley_a1_control_surface_candidate_rows(
        reference_csv,
        candidates=candidate_set,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    detail = pd.DataFrame(rows)
    for column in _SUMMARY_NUMERIC_COLUMNS:
        if column not in detail.columns:
            detail[column] = np.nan
    summary = summarize_matched_wigley_sensitivity(detail)
    best = matched_wigley_best_case_summary(summary)
    metadata = pd.DataFrame([candidate.metadata_row() for candidate in candidate_set])
    detail.to_csv(out_path / "a1_control_surface_candidate_benchmark.csv", index=False)
    summary.to_csv(out_path / "a1_control_surface_candidate_summary.csv", index=False)
    best.to_csv(out_path / "a1_control_surface_candidate_best_cases.csv", index=False)
    metadata.to_csv(out_path / "a1_control_surface_candidate_metadata.csv", index=False)
    return detail, summary, best


def write_a1_control_surface_green_identity_audit(
    out_dir: str | Path,
    *,
    candidates: tuple[A1ControlSurfaceCandidate, ...] | None = None,
    panel_counts: tuple[int, ...] | list[int] = (16, 32, 64, 128, 256),
    radius_m: float = 1.0,
    source_points: tuple[tuple[float, float], ...] | list[tuple[float, float]] = ((0.2, 0.3), (-0.25, 0.45)),
    relative_tolerance: float = 0.02,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the A1 Eq. (24) instantaneous control-surface identity audit to CSV."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    candidate_set = candidates or a1_control_surface_candidate_cases(
        MatchedWigleySensitivityCase(name="outer_control_identity_base")
    )
    rows = a1_control_surface_green_identity_rows(
        candidates=candidate_set,
        panel_counts=panel_counts,
        radius_m=radius_m,
        source_points=source_points,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        summary_rows: list[dict[str, float | int | str | bool]] = []
        for candidate in candidate_set:
            group = detail[detail["a1_control_candidate_name"] == candidate.name]
            if group.empty:
                continue
            finest_panel_count = int(group["panel_count"].max())
            finest = group[group["panel_count"] == finest_panel_count]
            fail_rows = int((group["diagnostic_status"] == "FAIL").sum())
            pass_rows = int((group["diagnostic_status"] == "PASS").sum())
            summary_rows.append(
                {
                    "a1_control_candidate_name": candidate.name,
                    "a1_control_candidate_status": candidate.status,
                    "a1_control_green_identity_status": A1_CONTROL_SURFACE_GREEN_IDENTITY_STATUS,
                    "a1_control_changed_eq24_terms": ";".join(candidate.changed_eq24_terms),
                    "pass_rows": pass_rows,
                    "fail_rows": fail_rows,
                    "max_relative_residual": float(group["relative_residual"].max()),
                    "min_relative_residual": float(group["relative_residual"].min()),
                    "finest_panel_count": finest_panel_count,
                    "finest_max_relative_residual": float(finest["relative_residual"].max()),
                    "finest_max_abs_residual": float(finest["max_abs_residual"].max()),
                    "control_image_scale": float(candidate.case.control_image_scale),
                    "control_potential_kernel_scale": float(candidate.case.control_potential_kernel_scale),
                    "control_normal_derivative_kernel_scale": float(
                        candidate.case.control_normal_derivative_kernel_scale
                    ),
                    "control_diagonal_sign": float(candidate.case.control_diagonal_sign),
                    "relative_tolerance": float(relative_tolerance),
                    "diagnostic_conclusion": (
                        "eq24_instantaneous_identity_within_tolerance"
                        if fail_rows == 0
                        else "eq24_instantaneous_identity_outside_tolerance"
                    ),
                    "gate_role": A1_CONTROL_SURFACE_GREEN_IDENTITY_STATUS,
                }
            )
        summary = pd.DataFrame(summary_rows)
    detail.to_csv(out_path / "a1_control_surface_green_identity.csv", index=False)
    summary.to_csv(out_path / "a1_control_surface_green_identity_summary.csv", index=False)
    pd.DataFrame([candidate.metadata_row() for candidate in candidate_set]).to_csv(
        out_path / "a1_control_surface_green_identity_metadata.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "a1_control_green_identity_status": A1_CONTROL_SURFACE_GREEN_IDENTITY_STATUS,
                "reference": "antisymmetric_half_plane_image_source_inside_control_surface",
                "checked_equation": "A1 Eq.24 instantaneous no-history term",
                "homogeneous_identity_note": (
                    "The no-history identity validates image and diagonal signs; reversing both unknown columns "
                    "is row-sign ambiguous until the history RHS is included."
                ),
                "is_hard_gate": False,
            }
        ]
    ).to_csv(out_path / "a1_control_surface_green_identity_audit_metadata.csv", index=False)
    return detail, summary


def write_a1_history_kernel_derivative_audit(
    out_dir: str | Path,
    *,
    panel_counts: tuple[int, ...] | list[int] = (8, 16, 32),
    lag_values_s: tuple[float, ...] | list[float] = (0.02, 0.05, 0.10),
    radius_m: float = 1.0,
    finite_difference_epsilon_m: float = 1.0e-4,
    gravity_m_s2: float = 9.80665,
    quadrature_count: int = 256,
    k_max: float = 50.0,
    relative_tolerance: float = 1.0e-3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the A1 Eq. (28) transient-kernel derivative audit to CSV."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = a1_history_kernel_derivative_rows(
        panel_counts=panel_counts,
        lag_values_s=lag_values_s,
        radius_m=radius_m,
        finite_difference_epsilon_m=finite_difference_epsilon_m,
        gravity_m_s2=gravity_m_s2,
        quadrature_count=quadrature_count,
        k_max=k_max,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        grouped = detail.groupby("lag_s", dropna=False)
        summary = grouped.agg(
            pass_rows=("diagnostic_status", lambda values: int((values == "PASS").sum())),
            fail_rows=("diagnostic_status", lambda values: int((values == "FAIL").sum())),
            max_relative_residual=("relative_residual", "max"),
            min_relative_residual=("relative_residual", "min"),
            finest_panel_count=("panel_count", "max"),
            finest_panel_relative_residual=("relative_residual", "last"),
            max_abs_residual=("max_abs_residual", "max"),
            finite_difference_epsilon_m=("finite_difference_epsilon_m", "first"),
            quadrature_count=("quadrature_count", "first"),
            k_max=("k_max", "first"),
        ).reset_index()
        summary["diagnostic_conclusion"] = np.where(
            summary["fail_rows"].astype(int).eq(0),
            "eq28_normal_derivative_matches_finite_difference",
            "eq28_normal_derivative_outside_tolerance",
        )
        summary["gate_role"] = A1_HISTORY_KERNEL_DERIVATIVE_STATUS
    detail.to_csv(out_path / "a1_history_kernel_derivative.csv", index=False)
    summary.to_csv(out_path / "a1_history_kernel_derivative_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "a1_history_kernel_derivative_status": A1_HISTORY_KERNEL_DERIVATIVE_STATUS,
                "reference": "finite_difference_of_eq28_transient_green_potential_kernel",
                "checked_equation": "A1 Eq.28 C_ij source-normal derivative channel",
                "is_hard_gate": False,
            }
        ]
    ).to_csv(out_path / "a1_history_kernel_derivative_metadata.csv", index=False)
    return detail, summary


def write_a1_history_rhs_convergence_audit(
    out_dir: str | Path,
    *,
    panel_count: int = 10,
    radius_m: float = 1.0,
    dt_s: float = 0.05,
    history_steps: int = 4,
    quadrature_cases: tuple[tuple[int, float], ...] | list[tuple[int, float]] = (
        (48, 40.0),
        (96, 50.0),
        (192, 70.0),
        (256, 80.0),
    ),
    reference_quadrature_count: int = 768,
    reference_k_max: float = 120.0,
    gravity_m_s2: float = 9.80665,
    quadrature_rule: str = "trapezoid",
    relative_tolerance: float = 1.0e-3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the A1 Eq. (24) history-RHS quadrature/cutoff convergence audit."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = a1_history_rhs_convergence_rows(
        panel_count=panel_count,
        radius_m=radius_m,
        dt_s=dt_s,
        history_steps=history_steps,
        quadrature_cases=quadrature_cases,
        reference_quadrature_count=reference_quadrature_count,
        reference_k_max=reference_k_max,
        gravity_m_s2=gravity_m_s2,
        quadrature_rule=quadrature_rule,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        ordered = detail.sort_values(["quadrature_count", "k_max"]).reset_index(drop=True)
        coarse = ordered.iloc[0]
        fine = ordered.iloc[-1]
        max_error_decreases = bool(
            float(fine["max_channel_relative_residual"]) <= float(coarse["max_channel_relative_residual"])
        )
        summary = pd.DataFrame(
            [
                {
                    "a1_history_rhs_convergence_status": A1_HISTORY_RHS_CONVERGENCE_STATUS,
                    "row_count": int(len(detail)),
                    "pass_rows": int((detail["diagnostic_status"] == "PASS").sum()),
                    "fail_rows": int((detail["diagnostic_status"] == "FAIL").sum()),
                    "coarsest_quadrature_count": int(coarse["quadrature_count"]),
                    "coarsest_k_max": float(coarse["k_max"]),
                    "finest_quadrature_count": int(fine["quadrature_count"]),
                    "finest_k_max": float(fine["k_max"]),
                    "coarsest_max_channel_relative_residual": float(coarse["max_channel_relative_residual"]),
                    "finest_max_channel_relative_residual": float(fine["max_channel_relative_residual"]),
                    "coarsest_total_relative_residual": float(coarse["total_relative_residual"]),
                    "finest_total_relative_residual": float(fine["total_relative_residual"]),
                    "coarsest_potential_channel_relative_residual": float(
                        coarse["potential_channel_relative_residual"]
                    ),
                    "finest_potential_channel_relative_residual": float(fine["potential_channel_relative_residual"]),
                    "coarsest_normal_derivative_channel_relative_residual": float(
                        coarse["normal_derivative_channel_relative_residual"]
                    ),
                    "finest_normal_derivative_channel_relative_residual": float(
                        fine["normal_derivative_channel_relative_residual"]
                    ),
                    "max_error_decreases": max_error_decreases,
                    "reference_quadrature_count": int(fine["reference_quadrature_count"]),
                    "reference_k_max": float(fine["reference_k_max"]),
                    "relative_tolerance": float(relative_tolerance),
                    "diagnostic_conclusion": (
                        "eq24_history_rhs_converges_to_refined_kernel_reference"
                        if max_error_decreases and int((detail["diagnostic_status"] == "FAIL").sum()) == 0
                        else "eq24_history_rhs_needs_quadrature_or_cutoff_review"
                    ),
                    "gate_role": A1_HISTORY_RHS_CONVERGENCE_STATUS,
                }
            ]
        )
    detail.to_csv(out_path / "a1_history_rhs_convergence.csv", index=False)
    summary.to_csv(out_path / "a1_history_rhs_convergence_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "a1_history_rhs_convergence_status": A1_HISTORY_RHS_CONVERGENCE_STATUS,
                "reference": "higher_quadrature_count_and_k_max_transient_history_kernel",
                "checked_equation": "A1 Eq.24 history RHS using Eq.28 transient kernels",
                "history_state": "deterministic_smooth_complex_control_surface_state",
                "is_hard_gate": False,
            }
        ]
    ).to_csv(out_path / "a1_history_rhs_convergence_metadata.csv", index=False)
    return detail, summary


def write_a1_outer_control_balance_audit(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    modes: tuple[str, ...] | list[str] = ("heave", "pitch"),
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    relative_tolerance: float = 1.0e-5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write real station-sweep Eq. (24) outer-control scale/phase diagnostics."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = a1_outer_control_balance_rows(
        reference_csv,
        cases=cases,
        coefficients=coefficients,
        modes=modes,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        ok = detail[detail["diagnostic_status"].isin(["PASS", "FAIL"])].copy()
        if ok.empty:
            summary = pd.DataFrame(
                [
                    {
                        "a1_outer_control_balance_status": A1_OUTER_CONTROL_BALANCE_STATUS,
                        "row_count": int(len(detail)),
                        "pass_rows": 0,
                        "fail_rows": 0,
                        "error_rows": int((detail["diagnostic_status"] == "ERROR").sum()),
                        "diagnostic_conclusion": "outer_control_balance_not_evaluated",
                        "gate_role": A1_OUTER_CONTROL_BALANCE_STATUS,
                    }
                ]
            )
        else:
            grouped = ok.groupby(["case_name", "coefficient", "mode_name"], dropna=False)
            summary = grouped.agg(
                station_rows=("diagnostic_status", "size"),
                pass_rows=("diagnostic_status", lambda values: int((values == "PASS").sum())),
                fail_rows=("diagnostic_status", lambda values: int((values == "FAIL").sum())),
                history_rhs_nonzero_rows=("history_rhs_nonzero", lambda values: int(values.astype(bool).sum())),
                max_relative_residual=("relative_residual", "max"),
                max_residual_norm=("residual_norm", "max"),
                max_history_rhs_norm=("history_rhs_norm", "max"),
                median_history_rhs_norm=("history_rhs_norm", "median"),
                max_instantaneous_lhs_norm=("instantaneous_lhs_norm", "max"),
                median_rhs_to_lhs_norm_ratio=("rhs_to_lhs_norm_ratio", "median"),
                max_rhs_to_lhs_norm_ratio=("rhs_to_lhs_norm_ratio", "max"),
                median_potential_to_normal_contribution_norm_ratio=(
                    "potential_to_normal_contribution_norm_ratio",
                    "median",
                ),
                median_history_potential_to_normal_channel_norm_ratio=(
                    "history_potential_to_normal_channel_norm_ratio",
                    "median",
                ),
                median_lhs_rhs_real_alignment=("lhs_rhs_real_alignment", "median"),
                median_lhs_rhs_phase_deg=("lhs_rhs_phase_deg", "median"),
                median_potential_normal_real_alignment=("potential_normal_real_alignment", "median"),
                median_potential_normal_phase_deg=("potential_normal_phase_deg", "median"),
                median_history_channel_real_alignment=("history_channel_real_alignment", "median"),
                median_history_channel_phase_deg=("history_channel_phase_deg", "median"),
                first_history_dt_s=("history_dt_s", "first"),
                first_history_steps=("history_steps", "first"),
                first_control_panel_count=("control_panel_count", "first"),
                first_control_radius_m=("control_radius_m", "first"),
                relative_tolerance=("relative_tolerance", "first"),
                a1_grid_recommendation_status=("a1_grid_recommendation_status", "first"),
            ).reset_index()
            summary["error_rows"] = int((detail["diagnostic_status"] == "ERROR").sum())
            summary["a1_outer_control_balance_status"] = A1_OUTER_CONTROL_BALANCE_STATUS
            summary["diagnostic_conclusion"] = np.where(
                summary["fail_rows"].astype(int).eq(0),
                "outer_control_lhs_reconstructs_history_rhs_scale_phase_recorded",
                "outer_control_lhs_history_rhs_balance_mismatch",
            )
            summary["gate_role"] = A1_OUTER_CONTROL_BALANCE_STATUS
    detail.to_csv(out_path / "a1_outer_control_balance.csv", index=False)
    summary.to_csv(out_path / "a1_outer_control_balance_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "a1_outer_control_balance_status": A1_OUTER_CONTROL_BALANCE_STATUS,
                "reference": "real_wigley_station_sweep_eq24_component_split",
                "checked_equation": "A1 Eq.24 outer-control instantaneous and history terms",
                "checked_channels": (
                    "instantaneous_potential; instantaneous_normal_derivative; "
                    "history_Bij_psi_n; history_Cij_psi"
                ),
                "is_hard_gate": False,
                "note": (
                    "PASS means the stored solved Eq.24 row balances numerically. The scale and phase columns are "
                    "diagnostic evidence for the remaining Ma 2005 coefficient gap."
                ),
            }
        ]
    ).to_csv(out_path / "a1_outer_control_balance_metadata.csv", index=False)
    return detail, summary


def write_a1_rhs_source_decomposition_audit(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    modes: tuple[str, ...] | list[str] = ("heave", "pitch"),
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    relative_tolerance: float = 1.0e-5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write real station-sweep RHS-source decomposition diagnostics."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = a1_rhs_source_decomposition_rows(
        reference_csv,
        cases=cases,
        coefficients=coefficients,
        modes=modes,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        ok = detail[detail["diagnostic_status"].isin(["PASS", "FAIL"])].copy()
        if ok.empty:
            summary = pd.DataFrame(
                [
                    {
                        "a1_rhs_source_decomposition_status": A1_RHS_SOURCE_DECOMPOSITION_STATUS,
                        "row_count": int(len(detail)),
                        "pass_rows": 0,
                        "fail_rows": 0,
                        "error_rows": int((detail["diagnostic_status"] == "ERROR").sum()),
                        "diagnostic_conclusion": "rhs_source_decomposition_not_evaluated",
                        "gate_role": A1_RHS_SOURCE_DECOMPOSITION_STATUS,
                    }
                ]
            )
        else:
            grouped = ok.groupby(["case_name", "coefficient", "mode_name", "source_name"], dropna=False)
            summary = grouped.agg(
                station_rows=("diagnostic_status", "size"),
                pass_rows=("diagnostic_status", lambda values: int((values == "PASS").sum())),
                fail_rows=("diagnostic_status", lambda values: int((values == "FAIL").sum())),
                max_source_sum_relative_residual=("source_sum_relative_residual", "max"),
                median_source_rhs_to_total_rhs_norm_ratio=("source_rhs_to_total_rhs_norm_ratio", "median"),
                median_source_solution_to_full_solution_norm_ratio=(
                    "source_solution_to_full_solution_norm_ratio",
                    "median",
                ),
                max_source_solution_to_full_solution_norm_ratio=(
                    "source_solution_to_full_solution_norm_ratio",
                    "max",
                ),
                median_body_potential_norm=("body_potential_norm", "median"),
                median_inner_free_surface_normal_derivative_norm=(
                    "inner_free_surface_normal_derivative_norm",
                    "median",
                ),
                median_control_potential_norm=("control_potential_norm", "median"),
                median_control_normal_derivative_norm=("control_normal_derivative_norm", "median"),
                max_control_potential_norm=("control_potential_norm", "max"),
                max_control_normal_derivative_norm=("control_normal_derivative_norm", "max"),
                median_source_to_full_real_alignment=("source_to_full_real_alignment", "median"),
                median_source_to_full_phase_deg=("source_to_full_phase_deg", "median"),
                relative_tolerance=("relative_tolerance", "first"),
                a1_grid_recommendation_status=("a1_grid_recommendation_status", "first"),
            ).reset_index()
            summary["error_rows"] = int((detail["diagnostic_status"] == "ERROR").sum())
            summary["a1_rhs_source_decomposition_status"] = A1_RHS_SOURCE_DECOMPOSITION_STATUS
            summary["diagnostic_conclusion"] = np.where(
                summary["fail_rows"].astype(int).eq(0),
                "matched_solution_reconstructs_from_rhs_source_solutions",
                "matched_solution_rhs_source_decomposition_mismatch",
            )
            summary["gate_role"] = A1_RHS_SOURCE_DECOMPOSITION_STATUS
    detail.to_csv(out_path / "a1_rhs_source_decomposition.csv", index=False)
    summary.to_csv(out_path / "a1_rhs_source_decomposition_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "a1_rhs_source_decomposition_status": A1_RHS_SOURCE_DECOMPOSITION_STATUS,
                "reference": "real_wigley_station_sweep_rhs_source_split",
                "checked_equation": "A1 Eq.23-Eq.24 matched system",
                "checked_sources": "body_normal_velocity; inner_free_surface_potential; outer_control_history",
                "is_hard_gate": False,
                "note": (
                    "PASS means the linear source solutions reconstruct the full matched solution. Norm and phase "
                    "columns diagnose which known source drives the control-surface unknowns."
                ),
            }
        ]
    ).to_csv(out_path / "a1_rhs_source_decomposition_metadata.csv", index=False)
    return detail, summary


def write_a1_inner_free_surface_state_audit(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    modes: tuple[str, ...] | list[str] = ("heave", "pitch"),
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    relative_tolerance: float = 1.0e-10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write real station-sweep inner-free-surface state marching diagnostics."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = a1_inner_free_surface_state_rows(
        reference_csv,
        cases=cases,
        coefficients=coefficients,
        modes=modes,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        ok = detail[detail["diagnostic_status"].isin(["PASS", "FAIL"])].copy()
        if ok.empty:
            summary = pd.DataFrame(
                [
                    {
                        "a1_inner_free_surface_state_status": A1_INNER_FREE_SURFACE_STATE_STATUS,
                        "row_count": int(len(detail)),
                        "pass_rows": 0,
                        "fail_rows": 0,
                        "error_rows": int((detail["diagnostic_status"] == "ERROR").sum()),
                        "diagnostic_conclusion": "inner_free_surface_state_not_evaluated",
                        "gate_role": A1_INNER_FREE_SURFACE_STATE_STATUS,
                    }
                ]
            )
        else:
            grouped = ok.groupby(["case_name", "coefficient", "mode_name"], dropna=False)
            summary = grouped.agg(
                station_rows=("diagnostic_status", "size"),
                pass_rows=("diagnostic_status", lambda values: int((values == "PASS").sum())),
                fail_rows=("diagnostic_status", lambda values: int((values == "FAIL").sum())),
                max_update_relative_residual=("update_relative_residual", "max"),
                max_transfer_relative_residual=("transfer_relative_residual", "max"),
                max_state_relative_residual=("max_state_relative_residual", "max"),
                max_time_before_abs_residual_s=("time_before_abs_residual_s", "max"),
                max_time_after_abs_residual_s=("time_after_abs_residual_s", "max"),
                max_state_time_abs_residual_s=("max_state_time_abs_residual_s", "max"),
                max_potential_growth_ratio=("potential_growth_ratio", "max"),
                median_potential_growth_ratio=("potential_growth_ratio", "median"),
                max_elevation_growth_ratio=("elevation_growth_ratio", "max"),
                median_elevation_growth_ratio=("elevation_growth_ratio", "median"),
                median_vertical_velocity_to_elevation_increment_ratio=(
                    "vertical_velocity_to_elevation_increment_ratio",
                    "median",
                ),
                median_potential_increment_to_gravity_elevation_ratio=(
                    "potential_increment_to_gravity_elevation_ratio",
                    "median",
                ),
                median_velocity_elevation_increment_real_alignment=(
                    "velocity_elevation_increment_real_alignment",
                    "median",
                ),
                median_velocity_elevation_increment_phase_deg=(
                    "velocity_elevation_increment_phase_deg",
                    "median",
                ),
                median_elevation_potential_increment_real_alignment=(
                    "elevation_potential_increment_real_alignment",
                    "median",
                ),
                median_elevation_potential_increment_phase_deg=(
                    "elevation_potential_increment_phase_deg",
                    "median",
                ),
                first_update_kind=("free_surface_update_kind", "first"),
                last_update_kind=("free_surface_update_kind", "last"),
                first_history_dt_s=("history_dt_s", "first"),
                first_free_surface_panel_count=("free_surface_panel_count", "first"),
                relative_tolerance=("relative_tolerance", "first"),
                a1_grid_recommendation_status=("a1_grid_recommendation_status", "first"),
            ).reset_index()
            summary["error_rows"] = int((detail["diagnostic_status"] == "ERROR").sum())
            summary["a1_inner_free_surface_state_status"] = A1_INNER_FREE_SURFACE_STATE_STATUS
            summary["diagnostic_conclusion"] = np.where(
                summary["fail_rows"].astype(int).eq(0),
                "inner_free_surface_state_updates_and_transfers_reconstruct_eq19_22",
                "inner_free_surface_state_marching_or_transfer_mismatch",
            )
            summary["gate_role"] = A1_INNER_FREE_SURFACE_STATE_STATUS
    detail.to_csv(out_path / "a1_inner_free_surface_state.csv", index=False)
    summary.to_csv(out_path / "a1_inner_free_surface_state_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "a1_inner_free_surface_state_status": A1_INNER_FREE_SURFACE_STATE_STATUS,
                "reference": "real_wigley_station_sweep_inner_free_surface_state_trace",
                "checked_equation": "A1 Eq.19-Eq.22 station free-surface state marching",
                "checked_channels": (
                    "station_transfer_resample; local_time_alignment; BIE_inner_free_surface_normal_derivative; "
                    "staggered_elevation_update; dynamic_potential_update"
                ),
                "is_hard_gate": False,
                "note": (
                    "PASS means the saved pre-solve and post-update free-surface states reconstruct the implemented "
                    "A1 Eq.19-Eq.22 marching, station transfer, and local-time alignment. Growth and phase columns "
                    "are diagnostic evidence "
                    "for the remaining Ma 2005 coefficient gap."
                ),
            }
        ]
    ).to_csv(out_path / "a1_inner_free_surface_state_metadata.csv", index=False)
    return detail, summary


def write_a1_control_history_inheritance_audit(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    modes: tuple[str, ...] | list[str] = ("heave", "pitch"),
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    relative_tolerance: float = 1.0e-10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the real station-sweep Eq. (24) control-history inheritance audit."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = a1_control_history_inheritance_rows(
        reference_csv,
        cases=cases,
        coefficients=coefficients,
        modes=modes,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        ok = detail[detail["diagnostic_status"].isin(["PASS", "FAIL"])].copy()
        if ok.empty:
            summary = pd.DataFrame(
                [
                    {
                        "a1_control_history_inheritance_status": A1_CONTROL_HISTORY_INHERITANCE_STATUS,
                        "row_count": int(len(detail)),
                        "pass_rows": 0,
                        "fail_rows": 0,
                        "error_rows": int((detail["diagnostic_status"] == "ERROR").sum()),
                        "diagnostic_conclusion": "station_control_history_inheritance_not_evaluated",
                        "gate_role": A1_CONTROL_HISTORY_INHERITANCE_STATUS,
                    }
                ]
            )
        else:
            grouped = ok.groupby(["case_name", "coefficient", "mode_name"], dropna=False)
            summary = grouped.agg(
                station_rows=("diagnostic_status", "size"),
                pass_rows=("diagnostic_status", lambda values: int((values == "PASS").sum())),
                fail_rows=("diagnostic_status", lambda values: int((values == "FAIL").sum())),
                max_rhs_relative_residual=("rhs_relative_residual", "max"),
                max_rhs_residual_norm=("rhs_residual_norm", "max"),
                max_lag0_relative_residual=("max_lag0_relative_residual", "max"),
                max_lag0_potential_relative_residual=("lag0_potential_relative_residual", "max"),
                max_lag0_normal_derivative_relative_residual=("lag0_normal_derivative_relative_residual", "max"),
                max_stored_rhs_norm=("stored_rhs_norm", "max"),
                max_full_history_potential_norm=("full_history_potential_norm", "max"),
                max_full_history_normal_derivative_norm=("full_history_normal_derivative_norm", "max"),
                first_history_dt_s=("history_dt_s", "first"),
                first_history_steps=("history_steps", "first"),
                first_control_panel_count=("control_panel_count", "first"),
                first_control_radius_m=("control_radius_m", "first"),
                relative_tolerance=("relative_tolerance", "first"),
                a1_grid_recommendation_status=("a1_grid_recommendation_status", "first"),
            ).reset_index()
            summary["error_rows"] = int((detail["diagnostic_status"] == "ERROR").sum())
            summary["a1_control_history_inheritance_status"] = A1_CONTROL_HISTORY_INHERITANCE_STATUS
            summary["diagnostic_conclusion"] = np.where(
                summary["fail_rows"].astype(int).eq(0),
                "station_control_history_rhs_reconstructs_from_solve_order",
                "station_control_history_rhs_or_lag0_inheritance_mismatch",
            )
            summary["gate_role"] = A1_CONTROL_HISTORY_INHERITANCE_STATUS
    detail.to_csv(out_path / "a1_control_history_inheritance.csv", index=False)
    summary.to_csv(out_path / "a1_control_history_inheritance_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "a1_control_history_inheritance_status": A1_CONTROL_HISTORY_INHERITANCE_STATUS,
                "reference": "real_wigley_station_sweep_reconstruction",
                "checked_equation": "A1 Eq.24 station-to-station control-surface history RHS",
                "checked_implementation": "solve_order plus _prepend_control_history",
                "is_hard_gate": False,
                "note": (
                    "This audit verifies queue inheritance and RHS reproducibility. It does not validate the "
                    "hydrodynamic coefficient magnitude against Ma 2005."
                ),
            }
        ]
    ).to_csv(out_path / "a1_control_history_inheritance_metadata.csv", index=False)
    return detail, summary


def write_a1_inner_kernel_candidate_benchmark(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    base_case: MatchedWigleySensitivityCase | None = None,
    candidates: tuple[A1InnerKernelCandidate, ...] | None = None,
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Write controlled A1 Eq. (23) inner-kernel Wigley III diagnostics."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    candidate_set = candidates or a1_inner_kernel_candidate_cases(base_case)
    rows = matched_wigley_a1_inner_kernel_candidate_rows(
        reference_csv,
        candidates=candidate_set,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    detail = pd.DataFrame(rows)
    for column in _SUMMARY_NUMERIC_COLUMNS:
        if column not in detail.columns:
            detail[column] = np.nan
    summary = summarize_matched_wigley_sensitivity(detail)
    best = matched_wigley_best_case_summary(summary)
    metadata = pd.DataFrame([candidate.metadata_row() for candidate in candidate_set])
    detail.to_csv(out_path / "a1_inner_kernel_candidate_benchmark.csv", index=False)
    summary.to_csv(out_path / "a1_inner_kernel_candidate_summary.csv", index=False)
    best.to_csv(out_path / "a1_inner_kernel_candidate_best_cases.csv", index=False)
    metadata.to_csv(out_path / "a1_inner_kernel_candidate_metadata.csv", index=False)
    return detail, summary, best


def write_a1_free_surface_oscillator_audit(
    out_dir: str | Path,
    *,
    dt_values: tuple[float, ...] | list[float] = (0.08, 0.04, 0.02, 0.01),
    sample_count: int = 9,
    gravity_m_s2: float = 9.80665,
    wavenumber_rad_m: float = 1.0,
    amplitude_m: float = 1.0,
    phase_rad: float = 0.37,
    phase_gradient_rad_m: float = 0.25,
    period_count: float = 1.0,
    normalized_error_tolerance: float = 0.08,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the A1 Eq. (19)-(22) free-surface oscillator audit to CSV."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = a1_free_surface_oscillator_rows(
        dt_values=dt_values,
        sample_count=sample_count,
        gravity_m_s2=gravity_m_s2,
        wavenumber_rad_m=wavenumber_rad_m,
        amplitude_m=amplitude_m,
        phase_rad=phase_rad,
        phase_gradient_rad_m=phase_gradient_rad_m,
        period_count=period_count,
        normalized_error_tolerance=normalized_error_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        ordered = detail.sort_values("dt_s", ascending=False).reset_index(drop=True)
        coarse = ordered.iloc[0]
        fine = ordered.iloc[-1]

        def observed_order(error_column: str) -> float:
            coarse_error = float(coarse[error_column])
            fine_error = float(fine[error_column])
            coarse_dt = float(coarse["dt_s"])
            fine_dt = float(fine["dt_s"])
            if coarse_error <= 0.0 or fine_error <= 0.0 or coarse_dt <= fine_dt:
                return float("nan")
            return float(math.log(coarse_error / fine_error) / math.log(coarse_dt / fine_dt))

        pass_rows = int((detail["diagnostic_status"] == "PASS").sum())
        fail_rows = int((detail["diagnostic_status"] == "FAIL").sum())
        elevation_decreases = bool(
            float(fine["rms_elevation_normalized_error"]) <= float(coarse["rms_elevation_normalized_error"])
        )
        potential_decreases = bool(
            float(fine["rms_potential_normalized_error"]) <= float(coarse["rms_potential_normalized_error"])
        )
        summary = pd.DataFrame(
            [
                {
                    "a1_free_surface_oscillator_status": A1_FREE_SURFACE_OSCILLATOR_STATUS,
                    "row_count": int(len(detail)),
                    "pass_rows": pass_rows,
                    "fail_rows": fail_rows,
                    "coarsest_dt_s": float(coarse["dt_s"]),
                    "finest_dt_s": float(fine["dt_s"]),
                    "coarsest_max_normalized_error": float(coarse["max_normalized_error"]),
                    "finest_max_normalized_error": float(fine["max_normalized_error"]),
                    "coarsest_rms_elevation_normalized_error": float(coarse["rms_elevation_normalized_error"]),
                    "finest_rms_elevation_normalized_error": float(fine["rms_elevation_normalized_error"]),
                    "coarsest_rms_potential_normalized_error": float(coarse["rms_potential_normalized_error"]),
                    "finest_rms_potential_normalized_error": float(fine["rms_potential_normalized_error"]),
                    "observed_elevation_rms_order": observed_order("rms_elevation_normalized_error"),
                    "observed_potential_rms_order": observed_order("rms_potential_normalized_error"),
                    "elevation_error_decreases": elevation_decreases,
                    "potential_error_decreases": potential_decreases,
                    "normalized_error_tolerance": float(normalized_error_tolerance),
                    "diagnostic_conclusion": (
                        "free_surface_marching_converges_with_step_refinement"
                        if elevation_decreases and potential_decreases and fail_rows == 0
                        else "free_surface_marching_needs_time_level_or_stability_review"
                    ),
                    "gate_role": A1_FREE_SURFACE_OSCILLATOR_STATUS,
                }
            ]
        )
    detail.to_csv(out_path / "a1_free_surface_oscillator.csv", index=False)
    summary.to_csv(out_path / "a1_free_surface_oscillator_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "a1_free_surface_oscillator_status": A1_FREE_SURFACE_OSCILLATOR_STATUS,
                "reference": "linear_deep_water_free_surface_oscillator",
                "checked_equations": "A1 Eq.19-Eq.22",
                "time_level_convention": "elevation_at_half_step_time_s;potential_at_time_s",
                "is_hard_gate": False,
            }
        ]
    ).to_csv(out_path / "a1_free_surface_oscillator_metadata.csv", index=False)
    return detail, summary


def write_a1_inner_kernel_green_identity_audit(
    out_dir: str | Path,
    *,
    candidates: tuple[A1InnerKernelCandidate, ...] | None = None,
    panel_counts: tuple[int, ...] | list[int] = (32, 64, 128),
    potential_names: tuple[str, ...] | list[str] = ("linear_y", "linear_z", "quadratic_y2_minus_z2", "cross_yz"),
    semiaxis_y_m: float = 1.0,
    semiaxis_z_m: float = 0.5,
    relative_tolerance: float = 0.08,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the A1 Eq. (23) closed-boundary Green-identity audit to CSV."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    candidate_set = candidates or a1_inner_kernel_candidate_cases(
        MatchedWigleySensitivityCase(name="inner_green_identity_base")
    )
    rows = a1_inner_kernel_green_identity_rows(
        candidates=candidate_set,
        panel_counts=panel_counts,
        potential_names=potential_names,
        semiaxis_y_m=semiaxis_y_m,
        semiaxis_z_m=semiaxis_z_m,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        grouped = detail.groupby(["a1_inner_candidate_name", "potential_name"], dropna=False)
        summary = grouped.agg(
            pass_rows=("diagnostic_status", lambda values: int((values == "PASS").sum())),
            fail_rows=("diagnostic_status", lambda values: int((values == "FAIL").sum())),
            max_relative_residual=("relative_residual", "max"),
            min_relative_residual=("relative_residual", "min"),
            finest_panel_count=("panel_count", "max"),
            finest_panel_relative_residual=("relative_residual", "last"),
            inner_a_scale=("inner_a_scale", "first"),
            inner_b_scale=("inner_b_scale", "first"),
            inner_diagonal_sign=("inner_diagonal_sign", "first"),
        ).reset_index()
        summary["diagnostic_conclusion"] = np.where(
            summary["fail_rows"].astype(int).eq(0),
            "closed_boundary_identity_within_tolerance",
            "closed_boundary_identity_outside_tolerance",
        )
        summary["gate_role"] = A1_INNER_KERNEL_GREEN_IDENTITY_STATUS
    detail.to_csv(out_path / "a1_inner_kernel_green_identity.csv", index=False)
    summary.to_csv(out_path / "a1_inner_kernel_green_identity_summary.csv", index=False)
    pd.DataFrame([candidate.metadata_row() for candidate in candidate_set]).to_csv(
        out_path / "a1_inner_kernel_green_identity_metadata.csv",
        index=False,
    )
    return detail, summary


def write_a1_closed_cylinder_added_mass_audit(
    out_dir: str | Path,
    *,
    panel_counts: tuple[int, ...] | list[int] = (64, 128, 256),
    radius_m: float = 1.0,
    omega_rad_s: float = 2.0,
    rho_water_kg_m3: float = 1000.0,
    corrected_relative_tolerance: float = 0.02,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the closed-cylinder added-mass pressure-chain audit to CSV."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = a1_closed_cylinder_added_mass_rows(
        panel_counts=panel_counts,
        radius_m=radius_m,
        omega_rad_s=omega_rad_s,
        rho_water_kg_m3=rho_water_kg_m3,
        corrected_relative_tolerance=corrected_relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        summary = pd.DataFrame(
            [
                {
                    "a1_closed_cylinder_added_mass_status": A1_CLOSED_CYLINDER_ADDED_MASS_STATUS,
                    "panel_count_min": int(detail["panel_count"].min()),
                    "panel_count_max": int(detail["panel_count"].max()),
                    "raw_added_mass_ratio_finest": float(detail.iloc[-1]["computed_added_mass_ratio"]),
                    "pressure_sign_corrected_ratio_finest": float(
                        detail.iloc[-1]["pressure_sign_corrected_added_mass_ratio"]
                    ),
                    "pressure_sign_corrected_relative_error_finest": float(
                        detail.iloc[-1]["pressure_sign_corrected_relative_error"]
                    ),
                    "potential_alignment_scale_to_analytic_finest": float(
                        detail.iloc[-1]["potential_alignment_scale_to_analytic"]
                    ),
                    "source_system_relative_residual_max": float(detail["source_system_relative_residual"].max()),
                    "pass_rows": int(detail["diagnostic_status"].eq("PASS").sum()),
                    "fail_rows": int(detail["diagnostic_status"].eq("FAIL").sum()),
                    "diagnostic_conclusion": (
                        "closed_cylinder_exposes_inner_pressure_sign_reversal"
                        if detail["diagnostic_status"].eq("PASS").all()
                        and float(detail.iloc[-1]["computed_added_mass_ratio"]) < 0.0
                        else "closed_cylinder_pressure_chain_needs_review"
                    ),
                    "gate_role": A1_CLOSED_CYLINDER_ADDED_MASS_STATUS,
                }
            ]
        )
    detail.to_csv(out_path / "a1_closed_cylinder_added_mass.csv", index=False)
    summary.to_csv(out_path / "a1_closed_cylinder_added_mass_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "a1_closed_cylinder_added_mass_status": A1_CLOSED_CYLINDER_ADDED_MASS_STATUS,
                "reference": "two-dimensional circular cylinder in infinite fluid",
                "expected_added_mass_per_m": "rho*pi*r^2",
                "checked_path": "inner source Neumann solve -> body potential -> Eq.30 time pressure -> heave force",
                "is_hard_gate": False,
            }
        ]
    ).to_csv(out_path / "a1_closed_cylinder_added_mass_metadata.csv", index=False)
    return detail, summary


def write_a1_inner_mixed_boundary_identity_audit(
    out_dir: str | Path,
    *,
    candidates: tuple[A1InnerKernelCandidate, ...] | None = None,
    panel_counts: tuple[int, ...] | list[int] = (66, 132, 264),
    potential_names: tuple[str, ...] | list[str] = ("linear_y", "linear_z", "quadratic_y2_minus_z2", "cross_yz"),
    semiaxis_y_m: float = 1.0,
    semiaxis_z_m: float = 0.5,
    relative_tolerance: float = 0.08,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the A1 Eq. (23) mixed body/free/control identity audit to CSV."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    candidate_set = candidates or a1_inner_kernel_candidate_cases(
        MatchedWigleySensitivityCase(name="inner_mixed_boundary_base")
    )
    rows = a1_inner_mixed_boundary_identity_rows(
        candidates=candidate_set,
        panel_counts=panel_counts,
        potential_names=potential_names,
        semiaxis_y_m=semiaxis_y_m,
        semiaxis_z_m=semiaxis_z_m,
        relative_tolerance=relative_tolerance,
    )
    detail = pd.DataFrame(rows)
    if detail.empty:
        summary = pd.DataFrame()
    else:
        grouped = detail.groupby(["a1_inner_candidate_name", "potential_name"], dropna=False)
        summary = grouped.agg(
            pass_rows=("diagnostic_status", lambda values: int((values == "PASS").sum())),
            fail_rows=("diagnostic_status", lambda values: int((values == "FAIL").sum())),
            max_total_relative_residual=("total_relative_residual", "max"),
            min_total_relative_residual=("total_relative_residual", "min"),
            finest_panel_count=("panel_count", "max"),
            finest_panel_total_relative_residual=("total_relative_residual", "last"),
            finest_panel_body_relative_residual=("body_relative_residual", "last"),
            finest_panel_free_relative_residual=("free_relative_residual", "last"),
            finest_panel_control_relative_residual=("control_relative_residual", "last"),
            inner_a_scale=("inner_a_scale", "first"),
            inner_b_scale=("inner_b_scale", "first"),
            inner_diagonal_sign=("inner_diagonal_sign", "first"),
        ).reset_index()
        summary["diagnostic_conclusion"] = np.where(
            summary["fail_rows"].astype(int).eq(0),
            "mixed_boundary_identity_within_tolerance",
            "mixed_boundary_identity_outside_tolerance",
        )
        summary["gate_role"] = A1_INNER_MIXED_BOUNDARY_STATUS
    detail.to_csv(out_path / "a1_inner_mixed_boundary_identity.csv", index=False)
    summary.to_csv(out_path / "a1_inner_mixed_boundary_identity_summary.csv", index=False)
    pd.DataFrame([candidate.metadata_row() for candidate in candidate_set]).to_csv(
        out_path / "a1_inner_mixed_boundary_identity_metadata.csv",
        index=False,
    )
    return detail, summary


def write_matched_wigley_station_diagnostics(
    reference_csv: str | Path,
    out_dir: str | Path,
    *,
    cases: tuple[MatchedWigleySensitivityCase, ...],
    coefficients: tuple[str, ...] | list[str] | None = None,
    row_limit: int | None = None,
    row_limit_per_coefficient: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> pd.DataFrame:
    """Write station-level matched Wigley diagnostics to CSV."""

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = matched_wigley_station_diagnostic_rows(
        reference_csv,
        cases=cases,
        coefficients=coefficients,
        row_limit=row_limit,
        row_limit_per_coefficient=row_limit_per_coefficient,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    diagnostics = pd.DataFrame(rows)
    diagnostics.to_csv(out_path / "matched_wigley_station_diagnostics.csv", index=False)
    return diagnostics
