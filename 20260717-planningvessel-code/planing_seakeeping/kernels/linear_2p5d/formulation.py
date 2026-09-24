from __future__ import annotations

from collections.abc import Callable
from collections import OrderedDict
from dataclasses import dataclass, field, replace
import hashlib

import numpy as np

from ...providers.linear_hydrodynamics import LinearFrequencyProvider
from ...schema import Linear2p5DProviderConfig
from ...section_bem import SectionOffsets, hard_chine_v_offsets, wigley_section_offsets
from ...station_2p5d import RigidBody6DOF, StationHull
from ...types import FrequencyDomainHydrodynamics, ValidityReport


LINEAR_2P5D_INNER_DOMAIN_STATUS = "a1_inner_domain_simple_green_block_no_free_surface_matching"
LINEAR_2P5D_MARCHING_STATUS = "a1_station_marching_grid_validated_by_formula_only"
LINEAR_2P5D_FREE_SURFACE_STATUS = "a1_free_surface_staggered_marching_eq19_22_not_hydro_validated"
LINEAR_2P5D_FREE_SURFACE_OSCILLATOR_STATUS = "a1_free_surface_eq19_22_oscillator_diagnostic_not_hard_gate"
LINEAR_2P5D_INNER_FREE_SURFACE_STATE_STATUS = (
    "a1_inner_free_surface_state_scale_marching_diagnostic_not_hard_gate"
)
LINEAR_2P5D_OUTER_HISTORY_STATUS = "a1_outer_transient_green_history_kernel_not_hydro_validated"
LINEAR_2P5D_HISTORY_DERIVATIVE_STATUS = "a1_eq28_history_kernel_normal_derivative_diagnostic_not_hard_gate"
LINEAR_2P5D_HISTORY_CONVERGENCE_STATUS = "a1_eq24_history_rhs_quadrature_convergence_diagnostic_not_hard_gate"
LINEAR_2P5D_CONTROL_HISTORY_INHERITANCE_STATUS = (
    "a1_eq24_station_control_history_inheritance_diagnostic_not_hard_gate"
)
LINEAR_2P5D_OUTER_CONTROL_BALANCE_STATUS = "a1_eq24_outer_control_balance_scale_phase_diagnostic_not_hard_gate"
LINEAR_2P5D_RHS_SOURCE_DECOMPOSITION_STATUS = (
    "a1_eq23_eq24_rhs_source_decomposition_diagnostic_not_hard_gate"
)
LINEAR_2P5D_INNER_FREE_SURFACE_RHS_BLOCK_STATUS = (
    "a1_eq23_inner_free_surface_rhs_matrix_block_diagnostic_not_hard_gate"
)
LINEAR_2P5D_CONTROL_MATCH_STATUS = "a1_outer_control_surface_equation_block_not_closed_matched_system"
LINEAR_2P5D_CONTROL_IDENTITY_STATUS = "a1_eq24_outer_control_green_identity_diagnostic_not_hard_gate"
LINEAR_2P5D_MATCHED_SYSTEM_STATUS = "a1_eq23_eq24_matched_square_system_no_pressure_recovery"
LINEAR_2P5D_MATCHED_BLOCK_AUDIT_STATUS = "a1_eq23_eq24_block_audit_not_benchmark_validated"
LINEAR_2P5D_PRESSURE_STATUS = "a1_eq30_body_pressure_recovery_gradient_optional_not_benchmark_validated"
LINEAR_2P5D_SECTION_FORCE_STATUS = "a1_section_pressure_integral_no_end_terms_not_benchmark_validated"
LINEAR_2P5D_STATION_GRADIENT_STATUS = "a1_station_body_potential_x_gradient_not_benchmark_validated"
LINEAR_2P5D_WHOLE_SHIP_STATUS = "a1_whole_ship_heave_pitch_coefficients_no_benchmark_gate"
LINEAR_2P5D_STATION_SWEEP_STATUS = "a1_matched_station_sweep_pipeline_no_benchmark_gate"
LINEAR_2P5D_STOKES_END_TERM_STATUS = "a1_eq32_stokes_end_term_helper_not_benchmark_validated"
LINEAR_2P5D_CONTROL_SURFACE_END_TERM_STATUS = (
    "a1_eq32_control_surface_end_term_diagnostic_not_hard_gate"
)
LINEAR_2P5D_STOKES_BODY_FORWARD_STATUS = "a1_eq32_stokes_body_forward_speed_helper_not_benchmark_validated"
LINEAR_2P5D_CONVENTION_STATUS = "a1_heave_pitch_coordinate_convention_layer_not_benchmark_validated"
LINEAR_2P5D_CONVENTION_AUDIT_STATUS = "a1_heave_pitch_coordinate_convention_audit_not_benchmark_validated"
LINEAR_2P5D_STATION_HULL_SWEEP_STATUS = "a1_station_hull_matched_sweep_free_surface_marching_not_benchmark_validated"
LINEAR_2P5D_HEAD_SEA_EXCITATION_STATUS = (
    "a1_eq3_eq4_eq30_matched_head_sea_excitation_not_benchmark_validated"
)
LINEAR_2P5D_INNER_KERNEL_IDENTITY_STATUS = "a1_eq23_inner_kernel_green_identity_diagnostic_not_hard_gate"
LINEAR_2P5D_BODY_BOUNDARY_NORMAL_STATUS = (
    "a1_eq23_body_boundary_inner_fluid_normal_identity_diagnostic_not_hard_gate"
)
LINEAR_2P5D_CLOSED_CYLINDER_ADDED_MASS_STATUS = (
    "a1_inner_domain_closed_cylinder_added_mass_diagnostic_not_hard_gate"
)


def local_time_from_station(x_from_bow_m: float, speed_mps: float) -> float:
    """Map longitudinal station distance to local 2.5D time."""

    if speed_mps <= 0.0:
        raise ValueError("2.5D local-time mapping requires positive speed_mps.")
    if x_from_bow_m < 0.0:
        raise ValueError("x_from_bow_m must be non-negative when marching from bow to stern.")
    return float(x_from_bow_m / speed_mps)


def deep_water_encounter(omega0_rad_s: np.ndarray | float, speed_mps: float, heading_deg: float, gravity_m_s2: float):
    omega0 = np.asarray(omega0_rad_s, dtype=float)
    k = omega0**2 / gravity_m_s2
    encounter = omega0 - k * float(speed_mps) * np.cos(np.radians(float(heading_deg)))
    if np.isscalar(omega0_rad_s):
        return float(k), float(encounter)
    return k, encounter


def deep_water_head_sea_wave_from_encounter(
    encounter_omega_rad_s: float,
    speed_mps: float,
    gravity_m_s2: float = 9.80665,
) -> tuple[float, float]:
    """Return deep-water head-sea wavenumber and absolute frequency.

    This is the analytic inversion of ``omega_e = omega_0 + U*k`` with
    ``omega_0**2 = g*k``.
    """

    omega_e = float(encounter_omega_rad_s)
    speed = float(speed_mps)
    gravity = float(gravity_m_s2)
    if not np.isfinite(omega_e) or omega_e <= 0.0:
        raise ValueError("encounter_omega_rad_s must be finite and positive.")
    if not np.isfinite(speed) or speed < 0.0:
        raise ValueError("speed_mps must be finite and non-negative.")
    if not np.isfinite(gravity) or gravity <= 0.0:
        raise ValueError("gravity_m_s2 must be finite and positive.")
    if speed <= 1.0e-12:
        wavenumber = omega_e**2 / gravity
    else:
        sqrt_k = (np.sqrt(gravity + 4.0 * speed * omega_e) - np.sqrt(gravity)) / (
            2.0 * speed
        )
        wavenumber = float(sqrt_k**2)
    omega_0 = float(np.sqrt(gravity * wavenumber))
    closure = omega_0 + speed * wavenumber
    if not np.isclose(closure, omega_e, rtol=1.0e-12, atol=1.0e-12):
        raise RuntimeError("Deep-water head-sea encounter inversion failed to close.")
    return float(wavenumber), omega_0


@dataclass(frozen=True)
class SectionMarchingGrid:
    """Station-wise local-time grid used by the Ma-Duan-Song 2.5D formulation."""

    x_from_ap_m: np.ndarray
    x_from_bow_m: np.ndarray
    local_time_s: np.ndarray
    dx_m: np.ndarray
    speed_mps: float
    validity: ValidityReport


@dataclass(frozen=True)
class InnerDomainPanelGeometry:
    """Straight-panel geometry for the inner simple-Green boundary integral block."""

    mid_y_m: np.ndarray
    mid_z_down_m: np.ndarray
    normal_y: np.ndarray
    normal_z: np.ndarray
    length_m: np.ndarray
    node_y_m: np.ndarray
    node_z_down_m: np.ndarray

    @property
    def panel_count(self) -> int:
        return int(len(self.length_m))


@dataclass(frozen=True)
class A1InnerKernelGreenIdentityAudit:
    """Closed-boundary Green-identity audit for the raw A1 Eq. (23) inner kernel."""

    geometry_name: str
    potential_name: str
    panel_count: int
    inner_a_scale: float
    inner_b_scale: float
    inner_diagonal_sign: float
    residual_norm: float
    relative_residual: float
    max_abs_residual: float
    phi_norm: float
    phi_n_norm: float
    a_phi_norm: float
    b_phi_n_norm: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1InnerMixedBoundaryGreenIdentityAudit:
    """Mixed-known-boundary audit for the A1 Eq. (23) body/free/control split."""

    geometry_name: str
    potential_name: str
    panel_count: int
    body_panel_count: int
    free_panel_count: int
    control_panel_count: int
    inner_a_scale: float
    inner_b_scale: float
    inner_diagonal_sign: float
    total_residual_norm: float
    total_relative_residual: float
    body_relative_residual: float
    free_relative_residual: float
    control_relative_residual: float
    max_abs_residual: float
    solution_norm: float
    rhs_norm: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1BodyBoundaryNormalAudit:
    """Composite-boundary identity audit for the A1 Eq. (23) body normal."""

    potential_name: str
    body_panel_count: int
    free_panel_count: int
    control_panel_count: int
    total_panel_count: int
    stored_body_normal_residual_norm: float
    stored_body_normal_relative_residual: float
    inner_fluid_body_normal_residual_norm: float
    inner_fluid_body_normal_relative_residual: float
    corrected_to_stored_residual_ratio: float
    stored_body_normal_max_abs_residual: float
    inner_fluid_body_normal_max_abs_residual: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1ClosedCylinderAddedMassAudit:
    """Closed circular-cylinder audit for the inner-domain pressure/force chain."""

    radius_m: float
    panel_count: int
    omega_rad_s: float
    rho_water_kg_m3: float
    expected_added_mass_per_m: float
    computed_added_mass_per_m: float
    computed_added_mass_ratio: float
    computed_added_mass_relative_error: float
    pressure_sign_corrected_added_mass_per_m: float
    pressure_sign_corrected_added_mass_ratio: float
    pressure_sign_corrected_relative_error: float
    computed_radiation_damping_per_m: float
    pressure_sign_corrected_radiation_damping_per_m: float
    source_system_condition_number: float
    source_system_relative_residual: float
    potential_alignment_scale_to_analytic: float
    potential_alignment_relative_residual: float
    heave_force_row_norm: float
    body_normal_velocity_norm: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1CoordinateMappingRow:
    """One explicit A1-paper to package-convention mapping row."""

    a1_symbol: str
    a1_source: str
    a1_expression: str
    package_expression: str
    package_role: str
    status: str
    notes: str = ""


@dataclass(frozen=True)
class A1HeavePitchCoordinateConvention:
    """Fixed A1 heave/pitch mapping used by the package.

    This layer centralizes the current package convention: section geometry is
    stored with `z` positive downward, reported heave force is positive upward,
    and pitch levers are supplied by the caller. The convention is intentionally
    explicit and benchmark-pending so Gate 1 work can audit one mapping layer
    rather than scattered `-normal_z` expressions.
    """

    name: str = "package_z_down_heave_up_lcg_minus_x"
    validity: ValidityReport = field(
        default_factory=lambda: ValidityReport(
            status=LINEAR_2P5D_CONVENTION_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "A1 Eq. (4)-Eq. (6), Eq. (30), and Eq. (32) heave/pitch convention layer. "
                "It is internally tested but not accepted as benchmark-validated until Gate 1 passes.",
            ),
        )
    )

    def heave_row_per_length(self, normal_z: np.ndarray) -> np.ndarray:
        """Return the package heave-force row per unit panel length."""

        return -np.asarray(normal_z, dtype=float)

    def paper_to_package_mapping_rows(self) -> tuple[A1CoordinateMappingRow, ...]:
        """Return the fixed A1-to-package mapping table for heave/pitch rows."""

        pending = "PENDING_GATE1_BENCHMARK_VALIDATION"
        return (
            A1CoordinateMappingRow(
                a1_symbol="section z coordinate",
                a1_source="A1 station-plane notation",
                a1_expression="A1 uses a vertical station-plane coordinate z; source sign must remain tied to Eq. (5).",
                package_expression="mid_z_down_m stores the section coordinate positive downward.",
                package_role="geometry storage; all vertical normals pass through this convention layer",
                status=pending,
                notes="The layer avoids directly using mid_z_down_m as a force sign.",
            ),
            A1CoordinateMappingRow(
                a1_symbol="N3",
                a1_source="A1 Eq. (5): (N2, N3) = (Ny, Nz)",
                a1_expression="N3 = Nz",
                package_expression="heave_n3 = -normal_z",
                package_role="heave radiation body condition and heave pressure row",
                status=pending,
                notes="normal_z is stored in the z-down panel basis while reported heave force is positive upward.",
            ),
            A1CoordinateMappingRow(
                a1_symbol="N5",
                a1_source="A1 Eq. (5): N5 = -x Nz",
                a1_expression="N5 = -x * Nz",
                package_expression="pitch_n5 = lever_arm_m * (-normal_z)",
                package_role="pitch oscillatory body condition and pitch end-contour row",
                status=pending,
                notes="Current station sweeps pass lever_arm_m = LCG - x_station after any diagnostic sign scale.",
            ),
            A1CoordinateMappingRow(
                a1_symbol="m3",
                a1_source="A1 Eq. (6): m_j = 0 for j=1..4",
                a1_expression="m3 = 0",
                package_expression="stokes_body_m_rows()[0] = 0",
                package_role="Eq. (32) body forward-speed term, heave row",
                status=pending,
                notes="This is why the Eq. (32) body term cannot generate A35 in the current heave/pitch block.",
            ),
            A1CoordinateMappingRow(
                a1_symbol="m5",
                a1_source="A1 Eq. (6): m5 = Nz",
                a1_expression="m5 = Nz",
                package_expression="pitch_m5 = sign * (-normal_z)",
                package_role="pitch forward-speed body condition and Eq. (32) body forward-speed row",
                status=pending,
                notes="The sign argument is diagnostic; default sign=+1 is internally consistent but not yet benchmark-passed.",
            ),
            A1CoordinateMappingRow(
                a1_symbol="heave pressure row",
                a1_source="A1 Eq. (30) pressure integrated over the body contour",
                a1_expression="integral p_j * N3 ds",
                package_expression="pressure_generalized_rows()[0] = (-normal_z) * ds",
                package_role="section heave force density",
                status=pending,
                notes="Shares the same row as heave_n3.",
            ),
            A1CoordinateMappingRow(
                a1_symbol="pitch pressure row",
                a1_source="A1 Eq. (30) pressure integrated over the body contour",
                a1_expression="integral p_j * N5 ds",
                package_expression="pressure_generalized_rows()[1] = lever_arm_m * (-normal_z) * ds",
                package_role="section pitch moment density",
                status=pending,
                notes="Shares the same lever convention as pitch_n5.",
            ),
            A1CoordinateMappingRow(
                a1_symbol="Eq.32 body term",
                a1_source="A1 Eq. (32): rho U integral(phi_j m_i ds)",
                a1_expression="row i uses m3=0 or m5=Nz",
                package_expression="stokes_body_m_rows(): [0, sign * (-normal_z) * ds]",
                package_role="Stokes body forward-speed diagnostic matrix",
                status=pending,
                notes="Stored separately from the default Eq. (30) finite-difference pressure-gradient path.",
            ),
            A1CoordinateMappingRow(
                a1_symbol="Eq.32 end contour term",
                a1_source="A1 Eq. (32): -rho U integral_CA(phi_j N_i dl)",
                a1_expression="row i uses N3 or N5 on the end contour",
                package_expression="end_contour_n_rows(): [(-normal_z) * dl, lever_arm_m * (-normal_z) * dl]",
                package_role="Stokes C_A end-contour diagnostic matrix",
                status=pending,
                notes="End station and contour orientation still require Gate 1 benchmark closure.",
            ),
        )

    def paper_to_package_mapping_table(self) -> tuple[dict[str, str], ...]:
        """Return the mapping table as plain dictionaries for CSV/report output."""

        return tuple(
            {
                "convention_name": self.name,
                "a1_symbol": row.a1_symbol,
                "a1_source": row.a1_source,
                "a1_expression": row.a1_expression,
                "package_expression": row.package_expression,
                "package_role": row.package_role,
                "status": row.status,
                "notes": row.notes,
                "validity_status": self.validity.status,
            }
            for row in self.paper_to_package_mapping_rows()
        )

    def heave_n3(self, geometry: InnerDomainPanelGeometry) -> np.ndarray:
        """Return the package form of A1 `N3` for heave."""

        return self.heave_row_per_length(geometry.normal_z)

    def pitch_n5(self, geometry: InnerDomainPanelGeometry, lever_arm_m: float) -> np.ndarray:
        """Return the package form of A1 `N5` for pitch."""

        return float(lever_arm_m) * self.heave_row_per_length(geometry.normal_z)

    def pitch_m5(self, geometry: InnerDomainPanelGeometry, *, sign: float = 1.0) -> np.ndarray:
        """Return the package form of A1 `m5` for pitch."""

        return float(sign) * self.heave_row_per_length(geometry.normal_z)

    def heave_body_normal_velocity(self, geometry: InnerDomainPanelGeometry, omega_rad_s: float) -> np.ndarray:
        """Return `i omega N3` for unit heave displacement amplitude."""

        omega = float(omega_rad_s)
        if omega <= 0.0:
            raise ValueError("omega_rad_s must be positive.")
        return 1j * omega * self.heave_n3(geometry)

    def pitch_body_normal_velocity_components(
        self,
        geometry: InnerDomainPanelGeometry,
        omega_rad_s: float,
        lever_arm_m: float,
        *,
        forward_speed_mps: float = 0.0,
        radiation_sign: float = 1.0,
        forward_speed_sign: float = 1.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return `i omega N5` and `U m5` for unit pitch displacement amplitude."""

        omega = float(omega_rad_s)
        speed = float(forward_speed_mps)
        if omega <= 0.0:
            raise ValueError("omega_rad_s must be positive.")
        if speed < 0.0:
            raise ValueError("forward_speed_mps must be non-negative.")
        sign = float(radiation_sign)
        speed_sign = float(forward_speed_sign)
        if not np.isfinite(sign):
            raise ValueError("radiation_sign must be finite.")
        if not np.isfinite(speed_sign):
            raise ValueError("forward_speed_sign must be finite.")
        oscillatory = sign * 1j * omega * self.pitch_n5(geometry, lever_arm_m)
        forward_speed = sign * speed * self.pitch_m5(geometry, sign=speed_sign)
        return oscillatory, forward_speed

    def pressure_generalized_rows(
        self,
        normal_z: np.ndarray,
        panel_length_m: np.ndarray,
        *,
        lever_arm_m: float = 0.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return heave and pitch generalized rows for pressure integration."""

        length = np.asarray(panel_length_m, dtype=float)
        heave = self.heave_row_per_length(np.asarray(normal_z, dtype=float)) * length
        return heave, heave * float(lever_arm_m)

    def stokes_body_m_rows(
        self,
        geometry: InnerDomainPanelGeometry,
        *,
        pitch_m5_sign: float = 1.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return A1 Eq. (32) body `m3` and `m5` rows including panel length."""

        heave_m3 = np.zeros(geometry.panel_count, dtype=float)
        pitch_m5 = self.pitch_m5(geometry, sign=float(pitch_m5_sign)) * geometry.length_m
        return heave_m3, pitch_m5

    def end_contour_n_rows(
        self,
        geometry: InnerDomainPanelGeometry,
        *,
        lever_arm_m: float = 0.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return A1 Eq. (32) end-contour `N3` and `N5` rows including panel length."""

        return self.pressure_generalized_rows(
            geometry.normal_z,
            geometry.length_m,
            lever_arm_m=lever_arm_m,
        )


DEFAULT_A1_HEAVE_PITCH_CONVENTION = A1HeavePitchCoordinateConvention()


@dataclass(frozen=True)
class FreeSurfaceMarchingState:
    """Staggered free-surface state for A1 Eqs. (19)-(22)."""

    y_m: np.ndarray
    elevation_m: np.ndarray
    potential_m2_s: np.ndarray
    time_s: float
    half_step_time_s: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1FreeSurfaceOscillatorAudit:
    """Analytic linear free-surface oscillator audit for A1 Eqs. (19)-(22)."""

    sample_count: int
    dt_s: float
    step_count: int
    final_time_s: float
    final_half_step_time_s: float
    gravity_m_s2: float
    wavenumber_rad_m: float
    omega_rad_s: float
    amplitude_m: float
    phase_rad: float
    phase_gradient_rad_m: float
    max_elevation_abs_error_m: float
    rms_elevation_abs_error_m: float
    max_elevation_normalized_error: float
    rms_elevation_normalized_error: float
    final_elevation_abs_error_m: float
    max_potential_abs_error_m2_s: float
    rms_potential_abs_error_m2_s: float
    max_potential_normalized_error: float
    rms_potential_normalized_error: float
    final_potential_abs_error_m2_s: float
    potential_amplitude_m2_s: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1OuterControlGreenIdentityAudit:
    """Half-plane Green-identity audit for the A1 Eq. (24) instantaneous block."""

    geometry_name: str
    potential_name: str
    panel_count: int
    radius_m: float
    source_y_m: float
    source_z_down_m: float
    control_image_scale: float
    control_potential_kernel_scale: float
    control_normal_derivative_kernel_scale: float
    control_diagonal_sign: float
    residual_norm: float
    relative_residual: float
    max_abs_residual: float
    potential_norm: float
    normal_derivative_norm: float
    potential_term_norm: float
    normal_derivative_term_norm: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1TransientHistoryKernelDerivativeAudit:
    """Finite-difference audit for the Eq. (28) transient Green normal-derivative kernel."""

    geometry_name: str
    panel_count: int
    radius_m: float
    lag_s: float
    finite_difference_epsilon_m: float
    gravity_m_s2: float
    quadrature_count: int
    k_max: float
    green_potential_norm: float
    green_normal_derivative_norm: float
    finite_difference_norm: float
    residual_norm: float
    relative_residual: float
    max_abs_residual: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1HistoryRhsConvergenceAudit:
    """Reference-refinement audit for the Eq. (24) transient-history RHS."""

    geometry_name: str
    panel_count: int
    radius_m: float
    dt_s: float
    history_steps: int
    quadrature_rule: str
    quadrature_count: int
    k_max: float
    reference_quadrature_count: int
    reference_k_max: float
    total_rhs_norm: float
    reference_total_rhs_norm: float
    total_residual_norm: float
    total_relative_residual: float
    total_max_abs_residual: float
    potential_channel_relative_residual: float
    normal_derivative_channel_relative_residual: float
    max_channel_relative_residual: float
    past_potential_norm: float
    past_normal_derivative_norm: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1ControlHistoryInheritanceAudit:
    """Station-sweep audit for Eq. (24) control-surface history inheritance."""

    mode_name: str
    station_local_index: int
    active_station_index: int
    solve_order_rank: int
    expected_previous_station_local_index: int
    history_steps: int
    history_dt_s: float
    history_quadrature_count: int
    history_k_max: float
    control_panel_count: int
    control_radius_m: float
    quadrature_rule: str
    stored_rhs_norm: float
    expected_rhs_norm: float
    rhs_residual_norm: float
    rhs_relative_residual: float
    rhs_max_abs_residual: float
    lag0_potential_norm: float
    expected_lag0_potential_norm: float
    lag0_potential_residual_norm: float
    lag0_potential_relative_residual: float
    lag0_normal_derivative_norm: float
    expected_lag0_normal_derivative_norm: float
    lag0_normal_derivative_residual_norm: float
    lag0_normal_derivative_relative_residual: float
    full_history_potential_norm: float
    full_history_normal_derivative_norm: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1OuterControlBalanceAudit:
    """Station-sweep scale/phase audit for the Eq. (24) outer-control row."""

    mode_name: str
    station_local_index: int
    active_station_index: int
    solve_order_rank: int
    history_steps: int
    history_dt_s: float
    control_panel_count: int
    control_radius_m: float
    potential_contribution_norm: float
    normal_derivative_contribution_norm: float
    instantaneous_lhs_norm: float
    history_rhs_norm: float
    history_potential_kernel_channel_norm: float
    history_normal_derivative_kernel_channel_norm: float
    residual_norm: float
    relative_residual: float
    rhs_to_lhs_norm_ratio: float
    potential_to_normal_contribution_norm_ratio: float
    history_potential_to_normal_channel_norm_ratio: float
    lhs_rhs_real_alignment: float
    lhs_rhs_phase_deg: float
    potential_normal_real_alignment: float
    potential_normal_phase_deg: float
    history_channel_real_alignment: float
    history_channel_phase_deg: float
    max_abs_lhs: float
    max_abs_rhs: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1RhsSourceDecompositionAudit:
    """Matched-system solution decomposition by known RHS source."""

    mode_name: str
    station_local_index: int
    active_station_index: int
    solve_order_rank: int
    source_name: str
    source_rhs_norm: float
    total_rhs_norm: float
    source_rhs_to_total_rhs_norm_ratio: float
    full_solution_norm: float
    source_solution_norm: float
    source_solution_to_full_solution_norm_ratio: float
    body_potential_norm: float
    inner_free_surface_normal_derivative_norm: float
    control_potential_norm: float
    control_normal_derivative_norm: float
    source_to_full_real_alignment: float
    source_to_full_phase_deg: float
    source_sum_residual_norm: float
    source_sum_relative_residual: float
    validity: ValidityReport


@dataclass(frozen=True)
class A1InnerFreeSurfaceRhsBlockAudit:
    """Eq. (23) `-A_free * phi_free` row-block and panel contribution audit."""

    mode_name: str
    station_local_index: int
    active_station_index: int
    solve_order_rank: int
    row_block_name: str
    row_block_size: int
    free_surface_panel_index: int
    free_surface_panel_y_m: float
    free_surface_panel_length_m: float
    free_surface_potential_abs: float
    free_surface_potential_phase_deg: float
    matrix_column_norm: float
    row_block_contribution_norm: float
    row_block_free_rhs_norm: float
    total_free_rhs_norm: float
    row_block_to_total_free_rhs_norm_ratio: float
    panel_to_row_block_free_rhs_norm_ratio: float
    panel_to_total_free_rhs_norm_ratio: float
    panel_to_row_block_real_alignment: float
    panel_to_row_block_phase_deg: float
    row_block_to_total_real_alignment: float
    row_block_to_total_phase_deg: float
    gate_role: str
    validity: ValidityReport


@dataclass(frozen=True)
class A1InnerFreeSurfaceStateAudit:
    """Station-sweep audit for inner-free-surface state marching and transfer."""

    mode_name: str
    station_local_index: int
    active_station_index: int
    solve_order_rank: int
    previous_station_local_index: int
    update_kind: str
    free_surface_panel_count: int
    history_dt_s: float
    free_surface_velocity_scale: float
    gravity_m_s2: float
    y_min_m: float
    y_max_m: float
    potential_before_norm: float
    elevation_before_norm: float
    vertical_velocity_norm: float
    potential_after_norm: float
    elevation_after_norm: float
    expected_potential_after_norm: float
    expected_elevation_after_norm: float
    potential_update_increment_norm: float
    elevation_update_increment_norm: float
    update_residual_norm: float
    update_relative_residual: float
    update_max_abs_residual: float
    transfer_residual_norm: float
    transfer_relative_residual: float
    transfer_max_abs_residual: float
    potential_growth_ratio: float
    elevation_growth_ratio: float
    vertical_velocity_to_elevation_increment_ratio: float
    potential_increment_to_gravity_elevation_ratio: float
    velocity_elevation_increment_real_alignment: float
    velocity_elevation_increment_phase_deg: float
    elevation_potential_increment_real_alignment: float
    elevation_potential_increment_phase_deg: float
    before_after_potential_real_alignment: float
    before_after_potential_phase_deg: float
    expected_local_time_s: float
    free_surface_state_time_before_s: float
    free_surface_state_time_after_s: float
    time_before_abs_residual_s: float
    time_after_abs_residual_s: float
    validity: ValidityReport


@dataclass(frozen=True)
class TransientFreeSurfaceHistory:
    """Control-surface transient Green kernels for the A1 outer-domain convolution."""

    lag_s: np.ndarray
    green_potential: np.ndarray
    green_normal_derivative: np.ndarray
    dt_s: float
    quadrature_count: int
    k_max: float
    validity: ValidityReport
    panel_integration_route: str = "midpoint"

    def convolution_rhs(
        self,
        past_potential: np.ndarray,
        past_normal_derivative: np.ndarray,
        *,
        rhs_scale: float = 1.0,
        quadrature_rule: str = "trapezoid",
        potential_kernel_scale: float = 1.0,
        normal_derivative_kernel_scale: float = 1.0,
    ) -> np.ndarray:
        """Return the Eq. (24) history right-hand side for aligned lag arrays."""

        scale = float(rhs_scale)
        if not np.isfinite(scale):
            raise ValueError("rhs_scale must be finite.")
        potential_scale = float(potential_kernel_scale)
        normal_scale = float(normal_derivative_kernel_scale)
        if not np.isfinite(potential_scale) or not np.isfinite(normal_scale):
            raise ValueError("history kernel scales must be finite.")
        rule = str(quadrature_rule).strip().lower()
        if rule not in {"rectangle", "trapezoid"}:
            raise ValueError("quadrature_rule must be 'rectangle' or 'trapezoid'.")
        phi = np.asarray(past_potential, dtype=complex)
        phi_n = np.asarray(past_normal_derivative, dtype=complex)
        if phi.shape != self.green_potential.shape[:1] + self.green_potential.shape[2:]:
            raise ValueError(
                "past_potential must have shape "
                f"{self.green_potential.shape[:1] + self.green_potential.shape[2:]}, got {phi.shape}."
            )
        if phi_n.shape != phi.shape:
            raise ValueError(f"past_normal_derivative must have shape {phi.shape}, got {phi_n.shape}.")
        rhs = np.zeros(self.green_potential.shape[1], dtype=complex)
        weights = np.ones(len(self.lag_s), dtype=float)
        if rule == "trapezoid":
            # The current-time endpoint is represented by the instantaneous
            # log-kernel terms on the left-hand side of Eq. (24); the oldest
            # retained lag receives the trapezoid endpoint half-weight.
            weights[-1] = 0.5
        for lag_index in range(len(self.lag_s)):
            rhs -= self.dt_s * weights[lag_index] * (
                potential_scale * (self.green_potential[lag_index] @ phi_n[lag_index])
                - normal_scale * (self.green_normal_derivative[lag_index] @ phi[lag_index])
            )
        return scale * rhs


@dataclass(frozen=True)
class MatchedSectionBoundaryData:
    """Boundary data for A1 Eqs. (23)-(24).

    body_normal_velocity is the derivative along the fluid-domain outward
    normal (into the hull), opposite to the stored body geometry normal.
    Free-surface and control derivatives use their stored outward normals.
    """

    body: InnerDomainPanelGeometry
    inner_free_surface: InnerDomainPanelGeometry
    control: InnerDomainPanelGeometry
    body_normal_velocity: np.ndarray
    free_surface_potential: np.ndarray
    history: TransientFreeSurfaceHistory
    past_control_potential: np.ndarray
    past_control_normal_derivative: np.ndarray
    free_surface_potential_control_row: np.ndarray | None = None
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
    inner_free_surface_self_diagonal_scale: float = 1.0
    inner_free_surface_known_potential_rhs_scale: float = 1.0
    inner_free_surface_known_potential_body_row_scale: float = 1.0
    inner_free_surface_known_potential_free_row_scale: float = 1.0
    inner_free_surface_known_potential_control_row_scale: float = 1.0
    inner_free_surface_unknown_normal_column_scale: float = 1.0


@dataclass(frozen=True)
class MatchedSectionSolution:
    """Named slices recovered from a matched Eq. (23)-Eq. (24) solution vector."""

    body_potential: np.ndarray
    inner_free_surface_normal_derivative: np.ndarray
    control_potential: np.ndarray
    control_normal_derivative: np.ndarray
    validity: ValidityReport


@dataclass(frozen=True)
class MatchedSectionPressureResult:
    """Body-panel pressure recovered from a matched 2.5D section solution."""

    panel_mid_y_m: np.ndarray
    panel_mid_z_down_m: np.ndarray
    panel_length_m: np.ndarray
    panel_normal_y: np.ndarray
    panel_normal_z: np.ndarray
    body_potential: np.ndarray
    body_potential_x_gradient: np.ndarray
    pressure_pa: np.ndarray
    pressure_time_derivative_pa: np.ndarray
    pressure_forward_speed_pa: np.ndarray
    omega_rad_s: float
    forward_speed_mps: float
    rho_water_kg_m3: float
    validity: ValidityReport


@dataclass(frozen=True)
class MatchedSectionForceResult:
    """Pressure-integrated heave/pitch sectional generalized force."""

    heave_force_per_m: complex
    pitch_moment_per_m: complex
    added_mass_per_m: float
    damping_per_m: float
    pitch_added_mass_per_m2: float
    pitch_damping_per_m2: float
    omega_rad_s: float
    lever_arm_m: float
    validity: ValidityReport
    heave_force_time_derivative_per_m: complex = 0.0j
    heave_force_forward_speed_per_m: complex = 0.0j
    pitch_moment_time_derivative_per_m: complex = 0.0j
    pitch_moment_forward_speed_per_m: complex = 0.0j


@dataclass(frozen=True)
class StationPotentialGradient:
    """Station-wise x-gradient of matched body potential."""

    x_m: np.ndarray
    body_potential_x_gradient: np.ndarray
    scheme: str
    validity: ValidityReport


@dataclass(frozen=True)
class WholeShipHeavePitchAssembly:
    """Whole-ship heave/pitch coefficients assembled from sectional pressure forces."""

    x_m: np.ndarray
    complex_force_matrix: np.ndarray
    added_mass: np.ndarray
    damping: np.ndarray
    end_term_force_matrix: np.ndarray
    time_derivative_force_matrix: np.ndarray
    forward_speed_force_matrix: np.ndarray
    stokes_body_forward_speed_force_matrix: np.ndarray
    force_assembly_route: str
    omega_rad_s: float
    row_labels: tuple[str, str]
    column_labels: tuple[str, str]
    validity: ValidityReport

    def coefficient_dict(self) -> dict[str, float]:
        return {
            "A33": float(self.added_mass[0, 0]),
            "B33": float(self.damping[0, 0]),
            "A35": float(self.added_mass[0, 1]),
            "B35": float(self.damping[0, 1]),
            "A53": float(self.added_mass[1, 0]),
            "B53": float(self.damping[1, 0]),
            "A55": float(self.added_mass[1, 1]),
            "B55": float(self.damping[1, 1]),
        }


@dataclass(frozen=True)
class StokesEndTermForceMatrix:
    """A1 Eq. (32) aft/end-contour contribution for heave/pitch assembly."""

    complex_force_matrix: np.ndarray
    forward_speed_mps: float
    rho_water_kg_m3: float
    lever_arm_m: float
    row_labels: tuple[str, str]
    column_labels: tuple[str, str]
    validity: ValidityReport


@dataclass(frozen=True)
class StokesBodyForwardSpeedForceMatrix:
    """A1 Eq. (32) body `rho U int phi_j m_i ds` contribution."""

    x_m: np.ndarray
    force_density_by_station: np.ndarray
    complex_force_matrix: np.ndarray
    forward_speed_mps: float
    rho_water_kg_m3: float
    pitch_m5_sign: float
    row_labels: tuple[str, str]
    column_labels: tuple[str, str]
    validity: ValidityReport


@dataclass(frozen=True)
class RowMeasureTransportForceMatrix:
    """Diagnostic `rho U int phi_j d(N_i ds)/dx` transport contribution."""

    x_m: np.ndarray
    pressure_row_measure_by_station: np.ndarray
    pressure_row_measure_x_gradient_by_station: np.ndarray
    stokes_m_measure_by_station: np.ndarray
    force_density_by_station: np.ndarray
    complex_force_matrix: np.ndarray
    candidate_names: tuple[str, ...]
    candidate_pressure_row_measure_x_gradient_by_station: np.ndarray
    candidate_force_density_by_station: np.ndarray
    candidate_complex_force_matrices: np.ndarray
    forward_speed_mps: float
    rho_water_kg_m3: float
    pitch_m5_sign: float
    row_labels: tuple[str, str]
    column_labels: tuple[str, str]
    validity: ValidityReport


@dataclass(frozen=True)
class HeavePitchA1ConventionAudit:
    """Station-level audit of the package heave/pitch convention against A1."""

    heave_n3_from_body_condition: np.ndarray
    heave_force_row_per_length: np.ndarray
    pitch_n5_from_body_condition: np.ndarray
    pitch_moment_row_per_length: np.ndarray
    pitch_m5_from_forward_body_condition: np.ndarray
    stokes_pitch_m5_per_length: np.ndarray
    radiation_lever_arm_m: float
    moment_lever_arm_m: float
    heave_n3_to_force_row_relative_residual: float
    pitch_n5_to_moment_row_relative_residual: float
    pitch_m5_forward_to_stokes_relative_residual: float
    pitch_m5_to_n5_norm_ratio: float
    validity: ValidityReport


@dataclass(frozen=True)
class MatchedStationHeavePitchSweep:
    """Station-sweep pressure and force chain for whole-ship heave/pitch coefficients."""

    x_m: np.ndarray
    heave_potential_gradient: StationPotentialGradient
    pitch_potential_gradient: StationPotentialGradient
    heave_mode_pressures: tuple[MatchedSectionPressureResult, ...]
    pitch_mode_pressures: tuple[MatchedSectionPressureResult, ...]
    heave_mode_forces: tuple[MatchedSectionForceResult, ...]
    pitch_mode_forces: tuple[MatchedSectionForceResult, ...]
    assembly: WholeShipHeavePitchAssembly
    stokes_body_forward_speed: StokesBodyForwardSpeedForceMatrix
    row_measure_transport: RowMeasureTransportForceMatrix
    validity: ValidityReport

    def coefficient_dict(self) -> dict[str, float]:
        return self.assembly.coefficient_dict()


@dataclass(frozen=True)
class StationHullMatchedHeavePitchSweep:
    """StationHull-level matched heave/pitch sweep feeding the whole-ship assembly chain."""

    x_m: np.ndarray
    active_station_indices: tuple[int, ...]
    bodies: tuple[InnerDomainPanelGeometry, ...]
    heave_mode_solutions: tuple[MatchedSectionSolution, ...]
    pitch_mode_solutions: tuple[MatchedSectionSolution, ...]
    heave_condition_numbers: np.ndarray
    pitch_condition_numbers: np.ndarray
    heave_residuals: np.ndarray
    pitch_residuals: np.ndarray
    heave_block_audits: tuple[MatchedSystemBlockAudit, ...]
    pitch_block_audits: tuple[MatchedSystemBlockAudit, ...]
    heave_free_surface_potential_by_station: np.ndarray
    pitch_free_surface_potential_by_station: np.ndarray
    heave_free_surface_elevation_by_station: np.ndarray
    pitch_free_surface_elevation_by_station: np.ndarray
    heave_free_surface_potential_after_station: np.ndarray
    pitch_free_surface_potential_after_station: np.ndarray
    heave_free_surface_elevation_after_station: np.ndarray
    pitch_free_surface_elevation_after_station: np.ndarray
    local_time_s_by_station: np.ndarray
    heave_free_surface_time_before_by_station: np.ndarray
    pitch_free_surface_time_before_by_station: np.ndarray
    heave_free_surface_time_after_by_station: np.ndarray
    pitch_free_surface_time_after_by_station: np.ndarray
    inner_free_surface_y_by_station: np.ndarray
    inner_free_surface_panel_length_by_station: np.ndarray
    heave_outer_history_rhs_by_station: np.ndarray
    pitch_outer_history_rhs_by_station: np.ndarray
    pitch_body_condition_oscillation_by_station: np.ndarray
    pitch_body_condition_forward_speed_by_station: np.ndarray
    heave_free_surface_update_kind_by_station: tuple[str, ...]
    pitch_free_surface_update_kind_by_station: tuple[str, ...]
    end_term: StokesEndTermForceMatrix | None
    control_surface_end_term: StokesEndTermForceMatrix | None
    pressure_force_sweep: MatchedStationHeavePitchSweep
    solve_order: tuple[int, ...]
    use_free_surface_marching: bool
    validity: ValidityReport
    end_term_scale: float = 1.0
    end_station: str = "aft"
    end_hull_station_index: int = -1
    end_active_station_local_index: int = -1
    end_station_x_m: float = float("nan")
    end_station_is_degenerate: bool = False
    end_term_geometry_source: str = "not_evaluated"
    pitch_radiation_sign: float = 1.0
    pitch_radiation_lever_sign: float = 1.0
    pitch_forward_speed_sign: float = 1.0
    pitch_oscillation_scale: float = 1.0
    pitch_forward_speed_scale: float = 1.0
    pitch_moment_sign: float = 1.0
    time_step_scale: float = 1.0
    free_surface_substeps_per_station: int = 1
    free_surface_velocity_scale: float = 1.0
    free_surface_normal_derivative_source: str = "raw"
    free_surface_time_direction_sign: float = 1.0
    free_surface_dynamic_gravity_sign: float = -1.0
    free_surface_potential_elevation_level: str = "updated"
    control_row_free_surface_potential_source: str = "shared"
    history_rhs_scale: float = 1.0
    history_convolution_rule: str = "trapezoid"
    history_potential_kernel_scale: float = 1.0
    history_normal_derivative_kernel_scale: float = 1.0
    control_image_scale: float = 1.0
    control_potential_kernel_scale: float = 1.0
    control_normal_derivative_kernel_scale: float = 1.0
    control_diagonal_sign: float = 1.0
    pressure_gradient_scheme: str = "central"
    pressure_gradient_scale: float = 1.0
    force_assembly_route: str = "eq32_stokes_body_plus_end"
    clip_inner_free_surface_to_waterline: bool = True
    two_zone_inner_free_surface: bool = False
    apply_local_time_phase: bool = True
    local_time_phase_x0_m: float = 0.0
    local_time_phase_gradient_correction: bool = True
    inner_a_scale: float = 1.0
    inner_b_scale: float = 1.0
    inner_diagonal_sign: float = -1.0
    inner_free_surface_self_diagonal_scale: float = 1.0
    inner_free_surface_known_potential_rhs_scale: float = 1.0
    inner_free_surface_known_potential_body_row_scale: float = 1.0
    inner_free_surface_known_potential_free_row_scale: float = 1.0
    inner_free_surface_known_potential_control_row_scale: float = 1.0
    inner_free_surface_unknown_normal_column_scale: float = 1.0
    history_steps: int = 0
    history_dt_s: float = 0.0
    history_quadrature_count: int = 0
    history_k_max: float = 0.0
    history_gravity_m_s2: float = 9.80665
    control_panel_count: int = 0
    control_radius_m: float = 0.0
    inner_free_surface_geometries: tuple[InnerDomainPanelGeometry, ...] = ()
    heave_body_condition_by_station: np.ndarray = field(
        default_factory=lambda: np.empty((0, 0), dtype=complex)
    )
    heave_body_condition_source: str = "unit_heave_radiation"

    def coefficient_dict(self) -> dict[str, float]:
        return self.pressure_force_sweep.coefficient_dict()


@dataclass(frozen=True)
class MatchedHeadSeaExcitationSweep:
    """A1 Eq. (3)-(4)-(30) head-sea excitation on the matched 2.5D domain."""

    x_m: np.ndarray
    encounter_omega_rad_s: float
    absolute_wave_omega_rad_s: float
    wavenumber_rad_m: float
    incident_potential_by_station: np.ndarray
    diffraction_body_normal_velocity_by_station: np.ndarray
    incident_pressure_by_station: np.ndarray
    froude_krylov_force_density_by_station: np.ndarray
    diffraction_force_density_by_station: np.ndarray
    total_force_density_by_station: np.ndarray
    froude_krylov_force: np.ndarray
    diffraction_force: np.ndarray
    total_excitation: np.ndarray
    diffraction_sweep: StationHullMatchedHeavePitchSweep
    body_condition_relative_residual: float
    equation30_incident_pressure_relative_residual: float
    force_density_integration_relative_residual: float
    maximum_condition_number: float
    maximum_linear_system_relative_residual: float
    validity: ValidityReport


_CONDITION_CACHE: OrderedDict[tuple, float] = OrderedDict()


@dataclass(frozen=True)
class MatchedBoundarySystem:
    """Inner/outer matched BIE matrix container for the Ma-Duan-Song kernel."""

    matrix: np.ndarray
    rhs: np.ndarray
    unknown_labels: tuple[str, ...]
    validity: ValidityReport

    def solve(self) -> np.ndarray:
        if self.matrix.shape[0] == self.matrix.shape[1]:
            return np.linalg.solve(self.matrix, self.rhs)
        return np.linalg.lstsq(self.matrix, self.rhs, rcond=None)[0]

    @property
    def condition_number(self) -> float:
        # Geometry matrices repeat across modes/frequencies. Hash current
        # contents so mutable NumPy storage cannot leave a stale diagnostic.
        matrix = np.ascontiguousarray(self.matrix)
        key = (matrix.shape, matrix.dtype.str, hashlib.sha256(matrix.tobytes()).digest())
        if key in _CONDITION_CACHE:
            _CONDITION_CACHE.move_to_end(key)
            return _CONDITION_CACHE[key]
        value = float(np.linalg.cond(matrix))
        _CONDITION_CACHE[key] = value
        if len(_CONDITION_CACHE) > 256:
            _CONDITION_CACHE.popitem(last=False)
        return value

    def relative_residual(self, solution: np.ndarray | None = None) -> float:
        values = self.solve() if solution is None else np.asarray(solution)
        residual = self.matrix @ values - self.rhs
        return float(np.linalg.norm(residual) / max(np.linalg.norm(self.rhs), 1e-12))


@dataclass(frozen=True)
class MatchedSystemBlockAudit:
    """Block-level audit for the A1 Eq. (23)-Eq. (24) matched system."""

    row_block_names: tuple[str, ...]
    unknown_block_names: tuple[str, ...]
    row_residual_norms: np.ndarray
    row_relative_residuals: np.ndarray
    row_rhs_norms: np.ndarray
    unknown_solution_norms: np.ndarray
    matrix_block_norms: np.ndarray
    contribution_block_norms: np.ndarray
    total_relative_residual: float
    condition_number: float
    validity: ValidityReport

    def row_index(self, name: str) -> int:
        return self.row_block_names.index(name)

    def unknown_index(self, name: str) -> int:
        return self.unknown_block_names.index(name)

    def row_relative_residual(self, name: str) -> float:
        return float(self.row_relative_residuals[self.row_index(name)])

    def row_rhs_norm(self, name: str) -> float:
        return float(self.row_rhs_norms[self.row_index(name)])

    def unknown_solution_norm(self, name: str) -> float:
        return float(self.unknown_solution_norms[self.unknown_index(name)])

    def max_matrix_block(self) -> tuple[str, float]:
        index = np.unravel_index(int(np.argmax(self.matrix_block_norms)), self.matrix_block_norms.shape)
        label = f"{self.row_block_names[index[0]]}<-{self.unknown_block_names[index[1]]}"
        return label, float(self.matrix_block_norms[index])

    def max_contribution_block(self) -> tuple[str, float]:
        index = np.unravel_index(int(np.argmax(self.contribution_block_norms)), self.contribution_block_norms.shape)
        label = f"{self.row_block_names[index[0]]}<-{self.unknown_block_names[index[1]]}"
        return label, float(self.contribution_block_norms[index])


def _matched_system_block_slices(
    data: MatchedSectionBoundaryData,
) -> tuple[tuple[tuple[str, slice], ...], tuple[tuple[str, slice], ...]]:
    n_body = data.body.panel_count
    n_free = data.inner_free_surface.panel_count
    n_control = data.control.panel_count
    row_blocks = (
        ("eq23_body", slice(0, n_body)),
        ("eq23_free_surface", slice(n_body, n_body + n_free)),
        ("eq23_inner_control", slice(n_body + n_free, n_body + n_free + n_control)),
        ("eq24_outer_control", slice(n_body + n_free + n_control, n_body + n_free + 2 * n_control)),
    )
    unknown_blocks = (
        ("psi_body", slice(0, n_body)),
        ("psi_n_free_surface", slice(n_body, n_body + n_free)),
        ("psi_control", slice(n_body + n_free, n_body + n_free + n_control)),
        ("psi_n_control", slice(n_body + n_free + n_control, n_body + n_free + 2 * n_control)),
    )
    return row_blocks, unknown_blocks


def audit_matched_system_blocks(
    data: MatchedSectionBoundaryData,
    system: MatchedBoundarySystem,
    solution: np.ndarray,
) -> MatchedSystemBlockAudit:
    """Return Eq. (23)-Eq. (24) row/unknown block norms for one solved section."""

    _validate_matched_boundary_data(data)
    values = np.asarray(solution, dtype=complex)
    if values.shape != system.rhs.shape:
        raise ValueError(f"solution must have shape {system.rhs.shape}, got {values.shape}.")
    row_blocks, unknown_blocks = _matched_system_block_slices(data)
    residual = np.asarray(system.matrix @ values - system.rhs, dtype=complex)
    row_residual_norms = np.asarray([np.linalg.norm(residual[row_slice]) for _, row_slice in row_blocks], dtype=float)
    row_rhs_norms = np.asarray([np.linalg.norm(system.rhs[row_slice]) for _, row_slice in row_blocks], dtype=float)
    row_relative_residuals = row_residual_norms / np.maximum(row_rhs_norms, 1e-12)
    unknown_solution_norms = np.asarray(
        [np.linalg.norm(values[col_slice]) for _, col_slice in unknown_blocks],
        dtype=float,
    )
    matrix_block_norms = np.zeros((len(row_blocks), len(unknown_blocks)), dtype=float)
    contribution_block_norms = np.zeros_like(matrix_block_norms)
    for row_index, (_, row_slice) in enumerate(row_blocks):
        for column_index, (_, col_slice) in enumerate(unknown_blocks):
            block = system.matrix[row_slice, col_slice]
            matrix_block_norms[row_index, column_index] = float(np.linalg.norm(block))
            contribution_block_norms[row_index, column_index] = float(np.linalg.norm(block @ values[col_slice]))
    return MatchedSystemBlockAudit(
        row_block_names=tuple(name for name, _ in row_blocks),
        unknown_block_names=tuple(name for name, _ in unknown_blocks),
        row_residual_norms=row_residual_norms,
        row_relative_residuals=row_relative_residuals,
        row_rhs_norms=row_rhs_norms,
        unknown_solution_norms=unknown_solution_norms,
        matrix_block_norms=matrix_block_norms,
        contribution_block_norms=contribution_block_norms,
        total_relative_residual=system.relative_residual(values),
        condition_number=system.condition_number,
        validity=ValidityReport(
            status=LINEAR_2P5D_MATCHED_BLOCK_AUDIT_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_submerged_spheroid"),
            notes=(
                "Diagnostic row/unknown block norms for A1 Eq. (23)-Eq. (24). "
                "This locates scaling issues but does not validate the hydrodynamic coefficients.",
            ),
        ),
    )


def build_section_marching_grid(
    hull: StationHull,
    speed_mps: float,
    station_count: int | None = None,
) -> SectionMarchingGrid:
    """Build the A1 local-time grid, marching from bow to stern.

    `StationHull` stores `x_m` forward from the aft perpendicular. The local
    time used in the 2.5D approximation is the time elapsed after a transverse
    plane encounters the bow, so `x_from_bow_m = L - x_from_ap_m` and `t=x/U`.
    """

    if speed_mps <= 0.0:
        raise ValueError("2.5D marching grid requires positive speed_mps.")
    if station_count is None:
        x_ap = np.asarray([station.x_m for station in hull.stations], dtype=float)
    else:
        count = int(station_count)
        if count < 3:
            raise ValueError("station_count must be at least 3.")
        x_ap = np.linspace(0.0, hull.length_m, count)
    x_ap = np.asarray(np.sort(x_ap), dtype=float)
    if np.any(x_ap < -1e-9) or np.any(x_ap > hull.length_m + 1e-9):
        raise ValueError("Marching stations must lie within hull length.")
    x_bow = hull.length_m - x_ap
    return SectionMarchingGrid(
        x_from_ap_m=x_ap,
        x_from_bow_m=x_bow,
        local_time_s=x_bow / float(speed_mps),
        dx_m=np.asarray(np.gradient(x_ap), dtype=float),
        speed_mps=float(speed_mps),
        validity=ValidityReport(
            status=LINEAR_2P5D_MARCHING_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=("A1 local-time mapping only; transient free-surface history is not solved in this object.",),
        ),
    )


def build_inner_domain_panel_geometry(
    offsets: SectionOffsets,
    body_panel_count: int | None = None,
) -> InnerDomainPanelGeometry:
    """Discretize a wetted section into straight collocation panels."""

    working = offsets.resample_by_arclength(body_panel_count) if body_panel_count is not None else offsets
    y0 = working.y_m[:-1]
    z0 = working.z_down_m[:-1]
    y1 = working.y_m[1:]
    z1 = working.z_down_m[1:]
    dy = y1 - y0
    dz = z1 - z0
    length = np.hypot(dy, dz)
    if np.any(length <= 1e-10):
        raise ValueError("Section contains a zero-length panel.")
    return InnerDomainPanelGeometry(
        mid_y_m=0.5 * (y0 + y1),
        mid_z_down_m=0.5 * (z0 + z1),
        normal_y=dz / length,
        normal_z=-dy / length,
        length_m=length,
        node_y_m=working.y_m,
        node_z_down_m=working.z_down_m,
    )


def inner_domain_source_normal_matrix(geometry: InnerDomainPanelGeometry) -> np.ndarray:
    """Return the simple-Green source influence matrix for the inner Neumann block."""

    y = geometry.mid_y_m
    z = geometry.mid_z_down_m
    dy = y[:, None] - y[None, :]
    dz = z[:, None] - z[None, :]
    r2 = np.maximum(dy**2 + dz**2, 1e-18)
    matrix = (
        (dy * geometry.normal_y[:, None] + dz * geometry.normal_z[:, None])
        / (2.0 * np.pi * r2)
        * geometry.length_m[None, :]
    )
    np.fill_diagonal(matrix, 0.5)
    return matrix


def inner_domain_source_potential_matrix(geometry: InnerDomainPanelGeometry) -> np.ndarray:
    """Return the simple-Green potential matrix at body collocation points."""

    y = geometry.mid_y_m
    z = geometry.mid_z_down_m
    dy = y[:, None] - y[None, :]
    dz = z[:, None] - z[None, :]
    radius = np.sqrt(np.maximum(dy**2 + dz**2, 1e-18))
    matrix = np.log(radius) / (2.0 * np.pi) * geometry.length_m[None, :]
    diagonal = geometry.length_m * (np.log(np.maximum(0.5 * geometry.length_m, 1e-18)) - 1.0) / (2.0 * np.pi)
    np.fill_diagonal(matrix, diagonal)
    return matrix


def build_closed_ellipse_inner_boundary(
    *,
    semiaxis_y_m: float = 1.0,
    semiaxis_z_m: float = 0.5,
    center_z_down_m: float | None = None,
    panel_count: int = 96,
) -> InnerDomainPanelGeometry:
    """Return a closed analytic ellipse boundary for A1 Eq. (23) kernel audits.

    This is not a wetted ship section. It is a closed mathematical contour used
    to check the raw inner Green identity with known harmonic potentials.
    """

    ay = float(semiaxis_y_m)
    az = float(semiaxis_z_m)
    count = int(panel_count)
    if ay <= 0.0 or az <= 0.0:
        raise ValueError("ellipse semiaxes must be positive.")
    if count < 12:
        raise ValueError("panel_count must be at least 12 for the closed ellipse audit.")
    center_z = float(1.25 * az if center_z_down_m is None else center_z_down_m)
    theta = np.linspace(0.0, 2.0 * np.pi, count + 1)
    offsets = SectionOffsets(
        y_m=ay * np.cos(theta),
        z_down_m=center_z + az * np.sin(theta),
    )
    return build_inner_domain_panel_geometry(offsets)


def audit_closed_cylinder_heave_added_mass(
    *,
    radius_m: float = 1.0,
    panel_count: int = 128,
    omega_rad_s: float = 2.0,
    rho_water_kg_m3: float = 1000.0,
) -> A1ClosedCylinderAddedMassAudit:
    """Audit the inner simple-source pressure chain against a closed circular cylinder.

    The reference is the two-dimensional infinite-fluid added mass per unit
    length for a circular cylinder in transverse motion, `rho*pi*r^2`. This is
    not a ship/free-surface validation case; it isolates the sign and amplitude
    of the package path
    `normal velocity -> source strength -> body potential -> Eq. (30) pressure
    -> heave force`.
    """

    radius = float(radius_m)
    omega = float(omega_rad_s)
    rho = float(rho_water_kg_m3)
    count = int(panel_count)
    if radius <= 0.0:
        raise ValueError("radius_m must be positive.")
    if omega <= 0.0:
        raise ValueError("omega_rad_s must be positive.")
    if rho <= 0.0:
        raise ValueError("rho_water_kg_m3 must be positive.")
    if count < 24:
        raise ValueError("panel_count must be at least 24 for the closed-cylinder audit.")

    geometry = build_closed_ellipse_inner_boundary(
        semiaxis_y_m=radius,
        semiaxis_z_m=radius,
        center_z_down_m=0.0,
        panel_count=count,
    )
    normal_matrix = inner_domain_source_normal_matrix(geometry).astype(complex)
    potential_matrix = inner_domain_source_potential_matrix(geometry).astype(complex)
    body_velocity = DEFAULT_A1_HEAVE_PITCH_CONVENTION.heave_body_normal_velocity(geometry, omega)
    source_strength = np.linalg.solve(normal_matrix, body_velocity)
    residual = normal_matrix @ source_strength - body_velocity
    residual_relative = float(np.linalg.norm(residual) / max(float(np.linalg.norm(body_velocity)), 1e-12))
    body_potential = potential_matrix @ source_strength
    pressure = -rho * 1j * omega * body_potential
    heave_row, _ = DEFAULT_A1_HEAVE_PITCH_CONVENTION.pressure_generalized_rows(
        geometry.normal_z,
        geometry.length_m,
    )
    force = complex(np.sum(pressure * heave_row))
    added, damping = pressure_force_to_added_mass_damping(force, omega)
    corrected_added, corrected_damping = pressure_force_to_added_mass_damping(-force, omega)
    expected = float(rho * np.pi * radius**2)

    analytic_potential = -1j * omega * np.asarray(geometry.mid_z_down_m, dtype=float)
    analytic_centered = analytic_potential - np.mean(analytic_potential)
    computed_centered = body_potential - np.mean(body_potential)
    denominator = complex(np.vdot(analytic_centered, analytic_centered))
    if abs(denominator) <= 1e-300:
        alignment_scale = float("nan")
        alignment_residual = float("nan")
    else:
        scale = np.vdot(analytic_centered, computed_centered) / denominator
        alignment_scale = float(np.real(scale))
        alignment_residual = float(
            np.linalg.norm(computed_centered - scale * analytic_centered)
            / max(float(np.linalg.norm(analytic_centered)), 1e-12)
        )

    return A1ClosedCylinderAddedMassAudit(
        radius_m=radius,
        panel_count=count,
        omega_rad_s=omega,
        rho_water_kg_m3=rho,
        expected_added_mass_per_m=expected,
        computed_added_mass_per_m=float(added),
        computed_added_mass_ratio=float(added / expected),
        computed_added_mass_relative_error=float(abs(added - expected) / expected),
        pressure_sign_corrected_added_mass_per_m=float(corrected_added),
        pressure_sign_corrected_added_mass_ratio=float(corrected_added / expected),
        pressure_sign_corrected_relative_error=float(abs(corrected_added - expected) / expected),
        computed_radiation_damping_per_m=float(damping),
        pressure_sign_corrected_radiation_damping_per_m=float(corrected_damping),
        source_system_condition_number=float(np.linalg.cond(normal_matrix)),
        source_system_relative_residual=residual_relative,
        potential_alignment_scale_to_analytic=alignment_scale,
        potential_alignment_relative_residual=alignment_residual,
        heave_force_row_norm=float(np.linalg.norm(heave_row)),
        body_normal_velocity_norm=float(np.linalg.norm(body_velocity)),
        validity=ValidityReport(
            status=LINEAR_2P5D_CLOSED_CYLINDER_ADDED_MASS_STATUS,
            reference_cases=("closed_circular_cylinder_added_mass", "rho*pi*r^2"),
            notes=(
                "Diagnostic-only closed-cylinder heave added-mass audit for the inner simple-source and Eq. (30) "
                "pressure chain. The pressure-sign-corrected field is reported to expose sign convention issues; "
                "it is not a production switch and does not pass Ma 2005 Gate 1."
            ),
        ),
    )


def split_inner_boundary_geometry_by_panel_counts(
    geometry: InnerDomainPanelGeometry,
    panel_counts: tuple[int, int, int],
) -> tuple[InnerDomainPanelGeometry, InnerDomainPanelGeometry, InnerDomainPanelGeometry]:
    """Split one contiguous boundary into three panel-geometry blocks."""

    counts = tuple(int(value) for value in panel_counts)
    if len(counts) != 3 or any(value < 1 for value in counts):
        raise ValueError("panel_counts must contain three positive integers.")
    if sum(counts) != geometry.panel_count:
        raise ValueError("panel_counts must sum to geometry.panel_count.")
    pieces: list[InnerDomainPanelGeometry] = []
    start = 0
    for count in counts:
        stop = start + count
        pieces.append(
            InnerDomainPanelGeometry(
                mid_y_m=np.asarray(geometry.mid_y_m[start:stop], dtype=float),
                mid_z_down_m=np.asarray(geometry.mid_z_down_m[start:stop], dtype=float),
                normal_y=np.asarray(geometry.normal_y[start:stop], dtype=float),
                normal_z=np.asarray(geometry.normal_z[start:stop], dtype=float),
                length_m=np.asarray(geometry.length_m[start:stop], dtype=float),
                node_y_m=np.asarray(geometry.node_y_m[start : stop + 1], dtype=float),
                node_z_down_m=np.asarray(geometry.node_z_down_m[start : stop + 1], dtype=float),
            )
        )
        start = stop
    return tuple(pieces)  # type: ignore[return-value]


def closed_boundary_three_part_panel_counts(panel_count: int) -> tuple[int, int, int]:
    """Return a stable body/free/control split for closed-boundary Eq. (23) audits."""

    count = int(panel_count)
    if count < 12:
        raise ValueError("panel_count must be at least 12.")
    body = count // 3
    free = count // 3
    control = count - body - free
    return body, free, control


def _analytic_harmonic_potential_on_boundary(
    geometry: InnerDomainPanelGeometry,
    potential_name: str,
) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(geometry.mid_y_m, dtype=float)
    z = np.asarray(geometry.mid_z_down_m, dtype=float)
    ny = np.asarray(geometry.normal_y, dtype=float)
    nz = np.asarray(geometry.normal_z, dtype=float)
    name = str(potential_name).strip().lower()
    if name in {"linear_y", "y"}:
        return y.astype(complex), ny.astype(complex)
    if name in {"linear_z", "z", "linear_z_down"}:
        return z.astype(complex), nz.astype(complex)
    if name in {"quadratic_y2_minus_z2", "y2_minus_z2"}:
        return (y**2 - z**2).astype(complex), (2.0 * y * ny - 2.0 * z * nz).astype(complex)
    if name in {"cross_yz", "yz"}:
        return (y * z).astype(complex), (z * ny + y * nz).astype(complex)
    raise ValueError(
        "potential_name must be one of linear_y, linear_z, quadratic_y2_minus_z2, or cross_yz."
    )


def audit_inner_kernel_green_identity(
    geometry: InnerDomainPanelGeometry,
    *,
    potential_name: str = "linear_y",
    geometry_name: str = "closed_boundary",
    inner_a_scale: float = 1.0,
    inner_b_scale: float = 1.0,
    inner_diagonal_sign: float = -1.0,
) -> A1InnerKernelGreenIdentityAudit:
    """Audit the closed-boundary A1 Eq. (23) identity for an analytic harmonic potential.

    For a closed contour and outward normals, the raw A1 Eq. (23) convention used
    by the matched solver should satisfy `A phi - B phi_n = 0` for harmonic
    `phi`, with `A` carrying the `-pi` boundary self term. The audit is a local
    kernel consistency check; it is not a Wigley III hydrodynamic coefficient
    acceptance gate.
    """

    if geometry.panel_count < 3:
        raise ValueError("geometry must contain at least three panels.")
    closure_gap = float(
        np.hypot(
            float(geometry.node_y_m[0] - geometry.node_y_m[-1]),
            float(geometry.node_z_down_m[0] - geometry.node_z_down_m[-1]),
        )
    )
    if closure_gap > 1e-8 * max(1.0, float(np.max(geometry.length_m))):
        raise ValueError("audit_inner_kernel_green_identity requires a closed boundary.")
    a_scale = float(inner_a_scale)
    b_scale = float(inner_b_scale)
    diag_sign = float(inner_diagonal_sign)
    if not all(np.isfinite(value) for value in (a_scale, b_scale, diag_sign)):
        raise ValueError("inner kernel audit scales must be finite.")
    phi, phi_n = _analytic_harmonic_potential_on_boundary(geometry, potential_name)
    a_matrix = a_scale * _inner_a_matrix(
        geometry,
        geometry,
        same_boundary=True,
        diagonal_sign=diag_sign,
    )
    b_matrix = b_scale * _inner_b_matrix(geometry, geometry, same_boundary=True)
    a_phi = a_matrix @ phi
    b_phi_n = b_matrix @ phi_n
    residual = a_phi - b_phi_n
    residual_norm = float(np.linalg.norm(residual))
    denominator = max(float(np.linalg.norm(phi)), float(np.linalg.norm(a_phi)), float(np.linalg.norm(b_phi_n)), 1e-12)
    relative = float(residual_norm / denominator)
    return A1InnerKernelGreenIdentityAudit(
        geometry_name=str(geometry_name),
        potential_name=str(potential_name).strip().lower(),
        panel_count=int(geometry.panel_count),
        inner_a_scale=a_scale,
        inner_b_scale=b_scale,
        inner_diagonal_sign=diag_sign,
        residual_norm=residual_norm,
        relative_residual=relative,
        max_abs_residual=float(np.max(np.abs(residual))) if residual.size else 0.0,
        phi_norm=float(np.linalg.norm(phi)),
        phi_n_norm=float(np.linalg.norm(phi_n)),
        a_phi_norm=float(np.linalg.norm(a_phi)),
        b_phi_n_norm=float(np.linalg.norm(b_phi_n)),
        validity=ValidityReport(
            status=LINEAR_2P5D_INNER_KERNEL_IDENTITY_STATUS,
            reference_cases=("closed_ellipse_green_identity", "ma2005_eq23"),
            notes=(
                "Closed-contour harmonic-potential audit for A1 Eq. (23) raw inner Green kernels. "
                "Passing this diagnostic supports local kernel consistency but does not pass Wigley III Gate 1.",
            ),
        ),
    )


def audit_inner_mixed_boundary_green_identity(
    body: InnerDomainPanelGeometry,
    inner_free_surface: InnerDomainPanelGeometry,
    control: InnerDomainPanelGeometry,
    *,
    potential_name: str = "linear_y",
    geometry_name: str = "closed_ellipse_mixed_boundary",
    inner_a_scale: float = 1.0,
    inner_b_scale: float = 1.0,
    inner_diagonal_sign: float = -1.0,
) -> A1InnerMixedBoundaryGreenIdentityAudit:
    """Audit the A1 Eq. (23) mixed known/unknown placement on a split boundary.

    The known values are assigned exactly as in the matched solver: body normal
    velocity is known, inner free-surface potential is known, and both control
    potential and normal derivative are unknown. For an analytic harmonic
    potential on a closed split contour, substituting the exact boundary values
    into the Eq. (23) rows should leave only discretization residual.
    """

    boundaries = (body, inner_free_surface, control)
    if any(boundary.panel_count < 1 for boundary in boundaries):
        raise ValueError("all mixed-boundary geometries must contain at least one panel.")
    a_scale = float(inner_a_scale)
    b_scale = float(inner_b_scale)
    diag_sign = float(inner_diagonal_sign)
    if not all(np.isfinite(value) for value in (a_scale, b_scale, diag_sign)):
        raise ValueError("inner mixed-boundary audit scales must be finite.")
    body_phi, body_phi_n = _analytic_harmonic_potential_on_boundary(body, potential_name)
    free_phi, free_phi_n = _analytic_harmonic_potential_on_boundary(inner_free_surface, potential_name)
    control_phi, control_phi_n = _analytic_harmonic_potential_on_boundary(control, potential_name)
    known_rhs_parts: list[np.ndarray] = []
    matrix_parts: list[np.ndarray] = []
    for field_index, field in enumerate(boundaries):
        a_body = a_scale * _inner_a_matrix(
            field,
            body,
            same_boundary=field_index == 0,
            diagonal_sign=diag_sign,
        )
        b_body = b_scale * _inner_b_matrix(field, body, same_boundary=field_index == 0)
        a_free = a_scale * _inner_a_matrix(
            field,
            inner_free_surface,
            same_boundary=field_index == 1,
            diagonal_sign=diag_sign,
        )
        b_free = b_scale * _inner_b_matrix(field, inner_free_surface, same_boundary=field_index == 1)
        a_control = a_scale * _inner_a_matrix(
            field,
            control,
            same_boundary=field_index == 2,
            diagonal_sign=diag_sign,
        )
        b_control = b_scale * _inner_b_matrix(field, control, same_boundary=field_index == 2)
        matrix_parts.append(np.hstack([a_body, -b_free, a_control, -b_control]).astype(complex))
        known_rhs_parts.append(b_body @ body_phi_n - a_free @ free_phi)
    matrix = np.vstack(matrix_parts)
    rhs = np.concatenate(known_rhs_parts)
    solution = np.concatenate([body_phi, free_phi_n, control_phi, control_phi_n])
    residual = matrix @ solution - rhs
    body_slice = slice(0, body.panel_count)
    free_slice = slice(body.panel_count, body.panel_count + inner_free_surface.panel_count)
    control_slice = slice(free_slice.stop, free_slice.stop + control.panel_count)

    def block_relative(row_slice: slice) -> float:
        block_residual = residual[row_slice]
        block_rhs = rhs[row_slice]
        return float(np.linalg.norm(block_residual) / max(np.linalg.norm(block_rhs), 1e-12))

    residual_norm = float(np.linalg.norm(residual))
    rhs_norm = float(np.linalg.norm(rhs))
    solution_norm = float(np.linalg.norm(solution))
    total_relative = float(residual_norm / max(rhs_norm, solution_norm, 1e-12))
    return A1InnerMixedBoundaryGreenIdentityAudit(
        geometry_name=str(geometry_name),
        potential_name=str(potential_name).strip().lower(),
        panel_count=int(body.panel_count + inner_free_surface.panel_count + control.panel_count),
        body_panel_count=int(body.panel_count),
        free_panel_count=int(inner_free_surface.panel_count),
        control_panel_count=int(control.panel_count),
        inner_a_scale=a_scale,
        inner_b_scale=b_scale,
        inner_diagonal_sign=diag_sign,
        total_residual_norm=residual_norm,
        total_relative_residual=total_relative,
        body_relative_residual=block_relative(body_slice),
        free_relative_residual=block_relative(free_slice),
        control_relative_residual=block_relative(control_slice),
        max_abs_residual=float(np.max(np.abs(residual))) if residual.size else 0.0,
        solution_norm=solution_norm,
        rhs_norm=rhs_norm,
        validity=ValidityReport(
            status=LINEAR_2P5D_INNER_KERNEL_IDENTITY_STATUS,
            reference_cases=("closed_ellipse_mixed_boundary", "ma2005_eq23"),
            notes=(
                "Closed-contour body/free/control split audit for A1 Eq. (23) known/unknown placement. "
                "It validates inner mixed-boundary signs only; Eq. (24) and Wigley III coefficients remain pending.",
            ),
        ),
    )


def heave_radiation_normal_velocity(geometry: InnerDomainPanelGeometry, omega_rad_s: float) -> np.ndarray:
    """Normal-velocity right-hand side for unit heave displacement amplitude."""

    return DEFAULT_A1_HEAVE_PITCH_CONVENTION.heave_body_normal_velocity(geometry, omega_rad_s)


def pitch_radiation_normal_velocity(
    geometry: InnerDomainPanelGeometry,
    omega_rad_s: float,
    lever_arm_m: float,
    *,
    forward_speed_mps: float = 0.0,
    radiation_sign: float = 1.0,
    forward_speed_sign: float = 1.0,
) -> np.ndarray:
    """Normal-velocity right-hand side for unit pitch displacement amplitude.

    The convention follows the existing station assembly: `lever_arm_m` is
    `LCG - x_station`, and the forward-speed body-condition channel contributes
    `U` to the pitch velocity map.
    """

    oscillatory, forward_speed = pitch_radiation_normal_velocity_components(
        geometry,
        omega_rad_s,
        lever_arm_m,
        forward_speed_mps=forward_speed_mps,
        radiation_sign=radiation_sign,
        forward_speed_sign=forward_speed_sign,
    )
    return oscillatory + forward_speed


def pitch_radiation_normal_velocity_components(
    geometry: InnerDomainPanelGeometry,
    omega_rad_s: float,
    lever_arm_m: float,
    *,
    forward_speed_mps: float = 0.0,
    radiation_sign: float = 1.0,
    forward_speed_sign: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the A1 pitch body-condition components `i omega N5` and `U m5`.

    With the package convention `N5 = -lever * Nz` and, after neglecting steady
    perturbation potential, `m5 = Nz`, the two channels become the oscillatory
    lever-arm term and the forward-speed term that are summed by
    `pitch_radiation_normal_velocity`.
    """

    return DEFAULT_A1_HEAVE_PITCH_CONVENTION.pitch_body_normal_velocity_components(
        geometry,
        omega_rad_s,
        lever_arm_m,
        forward_speed_mps=forward_speed_mps,
        radiation_sign=radiation_sign,
        forward_speed_sign=forward_speed_sign,
    )


def _relative_array_residual(values: np.ndarray, reference: np.ndarray) -> float:
    delta = np.asarray(values, dtype=complex) - np.asarray(reference, dtype=complex)
    scale = max(float(np.linalg.norm(reference)), 1e-12)
    return float(np.linalg.norm(delta) / scale)


def audit_heave_pitch_a1_convention(
    geometry: InnerDomainPanelGeometry,
    omega_rad_s: float,
    *,
    radiation_lever_arm_m: float,
    moment_lever_arm_m: float,
    forward_speed_mps: float = 0.0,
    pitch_radiation_sign: float = 1.0,
    pitch_forward_speed_sign: float = 1.0,
    stokes_pitch_m5_sign: float = 1.0,
) -> HeavePitchA1ConventionAudit:
    """Audit A1 `N_i/m_i` maps against the package heave/pitch rows.

    The helper does not decide which convention is physically correct. It makes
    the current convention measurable: the normal-velocity body condition is
    divided by `i omega` or `U` to recover the implied `N3`, `N5`, and `m5`,
    and those arrays are compared with the package pressure-integration rows.
    """

    omega = float(omega_rad_s)
    speed = float(forward_speed_mps)
    if omega <= 0.0:
        raise ValueError("omega_rad_s must be positive.")
    if speed < 0.0:
        raise ValueError("forward_speed_mps must be non-negative.")
    convention = DEFAULT_A1_HEAVE_PITCH_CONVENTION
    heave_condition = convention.heave_body_normal_velocity(geometry, omega)
    pitch_oscillation, pitch_forward = convention.pitch_body_normal_velocity_components(
        geometry,
        omega,
        float(radiation_lever_arm_m),
        forward_speed_mps=speed,
        radiation_sign=float(pitch_radiation_sign),
        forward_speed_sign=float(pitch_forward_speed_sign),
    )
    heave_row = convention.heave_n3(geometry)
    pitch_row = convention.pitch_n5(geometry, float(moment_lever_arm_m))
    stokes_m5 = convention.pitch_m5(geometry, sign=float(stokes_pitch_m5_sign))
    n3_from_body = heave_condition / (1j * omega)
    n5_from_body = pitch_oscillation / (1j * omega)
    if speed > 1e-12:
        m5_from_body = pitch_forward / speed
    else:
        m5_from_body = np.zeros_like(pitch_forward, dtype=complex)
    n5_norm = float(np.linalg.norm(n5_from_body))
    m5_norm = float(np.linalg.norm(m5_from_body))
    return HeavePitchA1ConventionAudit(
        heave_n3_from_body_condition=np.asarray(n3_from_body, dtype=complex),
        heave_force_row_per_length=np.asarray(heave_row, dtype=float),
        pitch_n5_from_body_condition=np.asarray(n5_from_body, dtype=complex),
        pitch_moment_row_per_length=np.asarray(pitch_row, dtype=float),
        pitch_m5_from_forward_body_condition=np.asarray(m5_from_body, dtype=complex),
        stokes_pitch_m5_per_length=np.asarray(stokes_m5, dtype=float),
        radiation_lever_arm_m=float(radiation_lever_arm_m),
        moment_lever_arm_m=float(moment_lever_arm_m),
        heave_n3_to_force_row_relative_residual=_relative_array_residual(n3_from_body, heave_row),
        pitch_n5_to_moment_row_relative_residual=_relative_array_residual(n5_from_body, pitch_row),
        pitch_m5_forward_to_stokes_relative_residual=_relative_array_residual(m5_from_body, stokes_m5),
        pitch_m5_to_n5_norm_ratio=float(m5_norm / max(n5_norm, 1e-12)),
        validity=ValidityReport(
            status=LINEAR_2P5D_CONVENTION_AUDIT_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "Diagnostic-only A1 Eq. (4)-Eq. (6) convention audit for package z-down, heave-up rows. "
                "Near-zero residuals show internal consistency, not benchmark validation.",
            ),
        ),
    )


def build_control_surface_geometry(radius_m: float, panel_count: int) -> InnerDomainPanelGeometry:
    """Build the fixed half-cylinder control surface used in A1 Section 3.3."""

    radius = float(radius_m)
    count = int(panel_count)
    if radius <= 0.0:
        raise ValueError("radius_m must be positive.")
    if count < 4:
        raise ValueError("panel_count must be at least 4.")
    theta = np.linspace(0.0, np.pi, count + 1)
    node_y = radius * np.cos(theta)
    node_z = radius * np.sin(theta)
    mid_theta = 0.5 * (theta[:-1] + theta[1:])
    return InnerDomainPanelGeometry(
        mid_y_m=radius * np.cos(mid_theta),
        mid_z_down_m=radius * np.sin(mid_theta),
        normal_y=np.cos(mid_theta),
        normal_z=np.sin(mid_theta),
        length_m=np.full(count, radius * np.pi / count),
        node_y_m=node_y,
        node_z_down_m=node_z,
    )


def build_flat_free_surface_geometry(
    y_min_m: float,
    y_max_m: float,
    panel_count: int,
    *,
    z_down_m: float = 0.0,
) -> InnerDomainPanelGeometry:
    """Build a flat inner free-surface boundary segment for A1 Eq. (23)."""

    count = int(panel_count)
    if count < 1:
        raise ValueError("panel_count must be positive.")
    y_min = float(y_min_m)
    y_max = float(y_max_m)
    if not y_max > y_min:
        raise ValueError("y_max_m must be greater than y_min_m.")
    z = float(z_down_m)
    nodes = np.linspace(y_min, y_max, count + 1)
    lengths = np.diff(nodes)
    return InnerDomainPanelGeometry(
        mid_y_m=0.5 * (nodes[:-1] + nodes[1:]),
        mid_z_down_m=np.full(count, z),
        normal_y=np.zeros(count),
        normal_z=-np.ones(count),
        length_m=lengths,
        node_y_m=nodes,
        node_z_down_m=np.full(count + 1, z),
    )


def build_waterline_clipped_free_surface_geometry(
    y_min_m: float,
    y_max_m: float,
    waterline_half_beam_m: float,
    panel_count: int,
    *,
    z_down_m: float = 0.0,
    grading_exponent: float = 1.0,
) -> InnerDomainPanelGeometry:
    """Build inner free-surface panels outside the local waterline interval."""

    count = int(panel_count)
    if count < 2:
        raise ValueError("panel_count must be at least 2 for a waterline-clipped free surface.")
    y_min = float(y_min_m)
    y_max = float(y_max_m)
    half_beam = max(0.0, float(waterline_half_beam_m))
    if not y_max > y_min:
        raise ValueError("y_max_m must be greater than y_min_m.")
    if half_beam >= min(abs(y_min), abs(y_max)):
        raise ValueError("waterline_half_beam_m must leave free-surface panels outside the hull.")
    left_count = count // 2
    right_count = count - left_count
    if left_count < 1 or right_count < 1:
        raise ValueError("panel_count must allocate at least one panel on each side.")
    left_nodes = np.linspace(y_min, -half_beam, left_count + 1)
    right_nodes = np.linspace(half_beam, y_max, right_count + 1)
    exponent = float(grading_exponent)
    if not np.isfinite(exponent) or not 1.0 <= exponent <= 2.0:
        raise ValueError('grading_exponent must be finite and between 1 and 2')
    if exponent != 1.0:
        left_nodes = -half_beam - (-half_beam-y_min)*np.linspace(1.,0.,left_count+1)**exponent
        right_nodes = half_beam + (y_max-half_beam)*np.linspace(0.,1.,right_count+1)**exponent
    mid_y = np.concatenate([0.5 * (left_nodes[:-1] + left_nodes[1:]), 0.5 * (right_nodes[:-1] + right_nodes[1:])])
    lengths = np.concatenate([np.diff(left_nodes), np.diff(right_nodes)])
    return InnerDomainPanelGeometry(
        mid_y_m=mid_y,
        mid_z_down_m=np.full(count, float(z_down_m)),
        normal_y=np.zeros(count),
        normal_z=-np.ones(count),
        length_m=lengths,
        node_y_m=np.concatenate([left_nodes, right_nodes]),
        node_z_down_m=np.full(left_nodes.size + right_nodes.size, float(z_down_m)),
    )


def _waterline_two_zone_side_nodes(
    half_beam_m: float,
    radius_m: float,
    transition_half_beam_m: float,
    inner_panel_count: int,
    outer_panel_count: int,
) -> np.ndarray:
    half_beam = float(half_beam_m)
    radius = float(radius_m)
    transition = float(transition_half_beam_m)
    inner_count = int(inner_panel_count)
    outer_count = int(outer_panel_count)
    if half_beam < 0.0:
        raise ValueError("half_beam_m must be non-negative.")
    if not radius > half_beam:
        raise ValueError("radius_m must be greater than half_beam_m.")
    if inner_count < 1 or outer_count < 1:
        raise ValueError("inner and outer panel counts must be positive.")
    transition = min(max(transition, half_beam), radius)
    total = inner_count + outer_count
    eps = max(1e-12, 1e-9 * radius)
    inner_length = transition - half_beam
    outer_length = radius - transition
    span = radius - half_beam
    small_zone_fraction = 0.10
    if (
        inner_length <= eps
        or outer_length <= eps
        or inner_length / span < small_zone_fraction
        or outer_length / span < small_zone_fraction
    ):
        return np.linspace(half_beam, radius, total + 1)
    inner = np.linspace(half_beam, transition, inner_count + 1)
    outer = np.linspace(transition, radius, outer_count + 1)
    return np.concatenate([inner, outer[1:]])


def build_two_zone_waterline_free_surface_geometry(
    y_min_m: float,
    y_max_m: float,
    waterline_half_beam_m: float,
    transition_half_beam_m: float,
    inner_panel_count_per_side: int,
    outer_panel_count_per_side: int,
    *,
    z_down_m: float = 0.0,
) -> InnerDomainPanelGeometry:
    """Build A1-style waterline-outboard free-surface panels with inner/outer zones.

    The two-zone layout keeps the body waterline gap open, puts the first zone
    between the local waterline and a fixed transition half-beam, and then uses
    the second zone from that transition to the control-surface radius. If a
    station reaches the transition beam, all panels on that side are spread over
    the remaining outboard interval to avoid zero-length panels.
    """

    y_min = float(y_min_m)
    y_max = float(y_max_m)
    if not y_max > y_min:
        raise ValueError("y_max_m must be greater than y_min_m.")
    if y_min >= 0.0 or y_max <= 0.0:
        raise ValueError("two-zone waterline free surface expects a y-range crossing the centerline.")
    radius = min(abs(y_min), abs(y_max))
    half_beam = max(0.0, float(waterline_half_beam_m))
    if half_beam >= radius:
        raise ValueError("waterline_half_beam_m must leave free-surface panels outside the hull.")
    right_nodes = _waterline_two_zone_side_nodes(
        half_beam,
        radius,
        float(transition_half_beam_m),
        int(inner_panel_count_per_side),
        int(outer_panel_count_per_side),
    )
    left_nodes = -right_nodes[::-1]
    nodes = np.concatenate([left_nodes, right_nodes])
    lengths = np.concatenate([np.diff(left_nodes), np.diff(right_nodes)])
    count = int(lengths.size)
    if np.any(lengths <= 0.0):
        raise ValueError("two-zone waterline free-surface grid produced a non-positive panel length.")
    return InnerDomainPanelGeometry(
        mid_y_m=np.concatenate(
            [0.5 * (left_nodes[:-1] + left_nodes[1:]), 0.5 * (right_nodes[:-1] + right_nodes[1:])]
        ),
        mid_z_down_m=np.full(count, float(z_down_m)),
        normal_y=np.zeros(count),
        normal_z=-np.ones(count),
        length_m=lengths,
        node_y_m=nodes,
        node_z_down_m=np.full(nodes.size, float(z_down_m)),
    )


def resample_free_surface_state(
    state: FreeSurfaceMarchingState,
    target_y_m: np.ndarray,
) -> FreeSurfaceMarchingState:
    """Interpolate staggered free-surface state to a station's current y-grid."""

    target_y = np.asarray(target_y_m, dtype=float)
    source_y = np.asarray(state.y_m, dtype=float)
    if target_y.shape == source_y.shape and np.array_equal(target_y, source_y):
        return state
    if np.any(np.diff(source_y) <= 0.0):
        raise ValueError("source free-surface y grid must be strictly increasing for interpolation.")
    if np.any(np.diff(target_y) <= 0.0):
        raise ValueError("target free-surface y grid must be strictly increasing for interpolation.")

    def has_center_gap(y: np.ndarray) -> bool:
        negative = y[y < 0.0]
        positive = y[y > 0.0]
        if negative.size < 1 or positive.size < 1 or y.size < 4:
            return False
        gap = float(positive[0] - negative[-1])
        spacing = np.diff(y)
        positive_spacing = spacing[spacing > 0.0]
        median_spacing = float(np.median(positive_spacing)) if positive_spacing.size else 0.0
        return bool(median_spacing > 0.0 and gap >= 2.0 * median_spacing)

    use_piecewise = has_center_gap(source_y) or has_center_gap(target_y)

    def interp_complex(values: np.ndarray) -> np.ndarray:
        array = np.asarray(values, dtype=complex)
        if use_piecewise:
            result = np.zeros_like(target_y, dtype=complex)
            for mask in (target_y < 0.0, target_y > 0.0):
                if not np.any(mask):
                    continue
                source_mask = source_y < 0.0 if float(np.mean(target_y[mask])) < 0.0 else source_y > 0.0
                if np.count_nonzero(source_mask) >= 2:
                    side_y = source_y[source_mask]
                    side_values = array[source_mask]
                    result[mask] = np.interp(target_y[mask], side_y, np.real(side_values)) + 1j * np.interp(
                        target_y[mask],
                        side_y,
                        np.imag(side_values),
                    )
                elif np.count_nonzero(source_mask) == 1:
                    result[mask] = array[source_mask][0]
            center_mask = target_y == 0.0
            if np.any(center_mask):
                result[center_mask] = 0.0
            return result
        return np.interp(target_y, source_y, np.real(array)) + 1j * np.interp(target_y, source_y, np.imag(array))

    return FreeSurfaceMarchingState(
        y_m=target_y,
        elevation_m=interp_complex(state.elevation_m),
        potential_m2_s=interp_complex(state.potential_m2_s),
        time_s=state.time_s,
        half_step_time_s=state.half_step_time_s,
        validity=state.validity,
    )


def initialize_free_surface_state(
    y_m: np.ndarray,
    vertical_velocity_m_s: np.ndarray,
    dt_s: float,
    *,
    initial_elevation_m: np.ndarray | None = None,
    initial_potential_m2_s: np.ndarray | None = None,
    gravity_m_s2: float = 9.80665,
    time_direction_sign: float = 1.0,
    dynamic_gravity_sign: float = -1.0,
    potential_elevation_level: str = "updated",
) -> FreeSurfaceMarchingState:
    """Initialize A1 Eqs. (21)-(22) from an undisturbed or supplied free surface."""

    y = np.asarray(y_m, dtype=float)
    vertical_velocity = np.asarray(vertical_velocity_m_s, dtype=complex)
    dt = float(dt_s)
    if dt <= 0.0:
        raise ValueError("dt_s must be positive.")
    time_sign = float(time_direction_sign)
    gravity_sign = float(dynamic_gravity_sign)
    if not np.isfinite(time_sign) or abs(time_sign) <= 1e-12:
        raise ValueError("time_direction_sign must be finite and non-zero.")
    if not np.isfinite(gravity_sign):
        raise ValueError("dynamic_gravity_sign must be finite.")
    level = str(potential_elevation_level).strip().lower()
    if level not in {"updated", "previous", "average"}:
        raise ValueError("potential_elevation_level must be 'updated', 'previous', or 'average'.")
    if y.ndim != 1 or vertical_velocity.shape != y.shape:
        raise ValueError("y_m and vertical_velocity_m_s must be one-dimensional arrays with the same shape.")
    elevation0 = np.zeros_like(y, dtype=complex) if initial_elevation_m is None else np.asarray(
        initial_elevation_m, dtype=complex
    )
    potential0 = np.zeros_like(y, dtype=complex) if initial_potential_m2_s is None else np.asarray(
        initial_potential_m2_s, dtype=complex
    )
    if elevation0.shape != y.shape or potential0.shape != y.shape:
        raise ValueError("initial_elevation_m and initial_potential_m2_s must match y_m.")
    signed_dt = time_sign * dt
    elevation_half = elevation0 + 0.5 * vertical_velocity * signed_dt
    if level == "previous":
        dynamic_elevation = elevation0
    elif level == "average":
        dynamic_elevation = 0.5 * (elevation0 + elevation_half)
    else:
        dynamic_elevation = elevation_half
    potential_next = potential0 + gravity_sign * float(gravity_m_s2) * dynamic_elevation * signed_dt
    return FreeSurfaceMarchingState(
        y_m=y,
        elevation_m=elevation_half,
        potential_m2_s=potential_next,
        time_s=signed_dt,
        half_step_time_s=0.5 * signed_dt,
        validity=ValidityReport(
            status=LINEAR_2P5D_FREE_SURFACE_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_submerged_spheroid"),
            notes=("Initialized with A1 Eqs. (21)-(22); coupled BIE feedback is supplied externally.",),
        ),
    )


def advance_free_surface_state(
    state: FreeSurfaceMarchingState,
    vertical_velocity_m_s: np.ndarray,
    dt_s: float,
    *,
    gravity_m_s2: float = 9.80665,
    time_direction_sign: float = 1.0,
    dynamic_gravity_sign: float = -1.0,
    potential_elevation_level: str = "updated",
) -> FreeSurfaceMarchingState:
    """Advance A1 Eqs. (19)-(20) by one staggered time step."""

    dt = float(dt_s)
    if dt <= 0.0:
        raise ValueError("dt_s must be positive.")
    time_sign = float(time_direction_sign)
    gravity_sign = float(dynamic_gravity_sign)
    if not np.isfinite(time_sign) or abs(time_sign) <= 1e-12:
        raise ValueError("time_direction_sign must be finite and non-zero.")
    if not np.isfinite(gravity_sign):
        raise ValueError("dynamic_gravity_sign must be finite.")
    level = str(potential_elevation_level).strip().lower()
    if level not in {"updated", "previous", "average"}:
        raise ValueError("potential_elevation_level must be 'updated', 'previous', or 'average'.")
    vertical_velocity = np.asarray(vertical_velocity_m_s, dtype=complex)
    if vertical_velocity.shape != state.y_m.shape:
        raise ValueError(f"vertical_velocity_m_s must have shape {state.y_m.shape}, got {vertical_velocity.shape}.")
    signed_dt = time_sign * dt
    elevation_next = state.elevation_m + vertical_velocity * signed_dt
    if level == "previous":
        dynamic_elevation = state.elevation_m
    elif level == "average":
        dynamic_elevation = 0.5 * (state.elevation_m + elevation_next)
    else:
        dynamic_elevation = elevation_next
    potential_next = state.potential_m2_s + gravity_sign * float(gravity_m_s2) * dynamic_elevation * signed_dt
    return FreeSurfaceMarchingState(
        y_m=state.y_m,
        elevation_m=elevation_next,
        potential_m2_s=potential_next,
        time_s=state.time_s + signed_dt,
        half_step_time_s=state.half_step_time_s + signed_dt,
        validity=state.validity,
    )


def advance_free_surface_state_with_substeps(
    state: FreeSurfaceMarchingState | None,
    y_m: np.ndarray,
    vertical_velocity_m_s: np.ndarray,
    dt_s: float,
    *,
    substeps_per_station: int = 1,
    gravity_m_s2: float = 9.80665,
    time_direction_sign: float = 1.0,
    dynamic_gravity_sign: float = -1.0,
    potential_elevation_level: str = "updated",
) -> FreeSurfaceMarchingState:
    """Advance A1 free-surface state with local predictor substeps.

    A1 uses a staggered free-surface marching grid, and the free-surface
    stations in the longitudinal direction are twice the body stations in the
    Wigley III setup.  This helper exposes that time-discretization question as
    a traced diagnostic: `substeps_per_station=1` reproduces the existing
    station-to-station update, while larger values split the same station
    interval into equal local predictor substeps using the current BIE-derived
    free-surface vertical velocity.
    """

    substeps = int(substeps_per_station)
    if substeps < 1:
        raise ValueError("substeps_per_station must be a positive integer.")
    dt_sub = float(dt_s) / float(substeps)
    signed_dt = float(time_direction_sign) * float(dt_s)
    velocity = np.asarray(vertical_velocity_m_s, dtype=complex)
    if state is None:
        current = initialize_free_surface_state(
            y_m,
            vertical_velocity_m_s,
            dt_s=dt_sub,
            gravity_m_s2=gravity_m_s2,
            time_direction_sign=time_direction_sign,
            dynamic_gravity_sign=dynamic_gravity_sign,
            potential_elevation_level=potential_elevation_level,
        )
        start = 1
        target_half_time = 0.5 * signed_dt
    else:
        current = state
        start = 0
        target_half_time = state.half_step_time_s + signed_dt
        if substeps > 1:
            # Eta is staggered relative to phi. Recenter it on the substep
            # half level before integrating, retaining the same physical state.
            sub_half_time = state.time_s - 0.5 * signed_dt / substeps
            current = replace(state,
                elevation_m=state.elevation_m + velocity * (sub_half_time-state.half_step_time_s),
                half_step_time_s=sub_half_time)
    for _ in range(start, substeps):
        current = advance_free_surface_state(
            current,
            vertical_velocity_m_s,
            dt_s=dt_sub,
            gravity_m_s2=gravity_m_s2,
            time_direction_sign=time_direction_sign,
            dynamic_gravity_sign=dynamic_gravity_sign,
            potential_elevation_level=potential_elevation_level,
        )
    if substeps > 1:
        current = replace(current,
            elevation_m=current.elevation_m + velocity * (target_half_time-current.half_step_time_s),
            half_step_time_s=target_half_time)
    return current


def audit_free_surface_oscillator_marching(
    *,
    dt_s: float,
    step_count: int,
    sample_count: int = 9,
    gravity_m_s2: float = 9.80665,
    wavenumber_rad_m: float = 1.0,
    amplitude_m: float = 1.0,
    phase_rad: float = 0.37,
    phase_gradient_rad_m: float = 0.25,
) -> A1FreeSurfaceOscillatorAudit:
    """Compare A1 Eqs. (19)-(22) against a linear free-surface oscillator.

    The implemented state is staggered: elevation is stored at
    ``half_step_time_s`` while potential is stored at ``time_s``.  This audit
    drives the kinematic input with the analytic elevation velocity and checks
    both stored time levels separately.
    """

    dt = float(dt_s)
    if dt <= 0.0 or not np.isfinite(dt):
        raise ValueError("dt_s must be positive and finite.")
    steps = int(step_count)
    if steps < 1:
        raise ValueError("step_count must be at least 1.")
    samples = int(sample_count)
    if samples < 1:
        raise ValueError("sample_count must be at least 1.")
    gravity = float(gravity_m_s2)
    wavenumber = float(wavenumber_rad_m)
    amplitude = float(amplitude_m)
    if gravity <= 0.0 or not np.isfinite(gravity):
        raise ValueError("gravity_m_s2 must be positive and finite.")
    if wavenumber <= 0.0 or not np.isfinite(wavenumber):
        raise ValueError("wavenumber_rad_m must be positive and finite.")
    if amplitude <= 0.0 or not np.isfinite(amplitude):
        raise ValueError("amplitude_m must be positive and finite.")
    phase = float(phase_rad)
    phase_gradient = float(phase_gradient_rad_m)
    if not np.isfinite(phase) or not np.isfinite(phase_gradient):
        raise ValueError("phase_rad and phase_gradient_rad_m must be finite.")

    omega = float(np.sqrt(gravity * wavenumber))
    potential_amplitude = float(gravity * amplitude / omega)
    y = np.linspace(-1.0, 1.0, samples)
    local_phase = phase + phase_gradient * y

    def elevation(time_s: float) -> np.ndarray:
        return amplitude * np.cos(omega * float(time_s) + local_phase)

    def potential(time_s: float) -> np.ndarray:
        return -potential_amplitude * np.sin(omega * float(time_s) + local_phase)

    def vertical_velocity(time_s: float) -> np.ndarray:
        return -amplitude * omega * np.sin(omega * float(time_s) + local_phase)

    state = initialize_free_surface_state(
        y,
        vertical_velocity(0.0),
        dt,
        initial_elevation_m=elevation(0.0),
        initial_potential_m2_s=potential(0.0),
        gravity_m_s2=gravity,
    )

    elevation_errors: list[np.ndarray] = []
    potential_errors: list[np.ndarray] = []
    for step_index in range(steps):
        elevation_errors.append(np.asarray(state.elevation_m - elevation(state.half_step_time_s), dtype=complex))
        potential_errors.append(np.asarray(state.potential_m2_s - potential(state.time_s), dtype=complex))
        if step_index + 1 < steps:
            state = advance_free_surface_state(
                state,
                vertical_velocity(state.time_s),
                dt,
                gravity_m_s2=gravity,
            )

    elevation_error = np.concatenate([np.ravel(values) for values in elevation_errors])
    potential_error = np.concatenate([np.ravel(values) for values in potential_errors])
    final_elevation_error = np.asarray(state.elevation_m - elevation(state.half_step_time_s), dtype=complex)
    final_potential_error = np.asarray(state.potential_m2_s - potential(state.time_s), dtype=complex)
    elevation_scale = max(abs(amplitude), np.finfo(float).eps)
    potential_scale = max(abs(potential_amplitude), np.finfo(float).eps)
    max_elevation_abs = float(np.max(np.abs(elevation_error)))
    rms_elevation_abs = float(np.sqrt(np.mean(np.abs(elevation_error) ** 2)))
    max_potential_abs = float(np.max(np.abs(potential_error)))
    rms_potential_abs = float(np.sqrt(np.mean(np.abs(potential_error) ** 2)))
    return A1FreeSurfaceOscillatorAudit(
        sample_count=samples,
        dt_s=dt,
        step_count=steps,
        final_time_s=float(state.time_s),
        final_half_step_time_s=float(state.half_step_time_s),
        gravity_m_s2=gravity,
        wavenumber_rad_m=wavenumber,
        omega_rad_s=omega,
        amplitude_m=amplitude,
        phase_rad=phase,
        phase_gradient_rad_m=phase_gradient,
        max_elevation_abs_error_m=max_elevation_abs,
        rms_elevation_abs_error_m=rms_elevation_abs,
        max_elevation_normalized_error=float(max_elevation_abs / elevation_scale),
        rms_elevation_normalized_error=float(rms_elevation_abs / elevation_scale),
        final_elevation_abs_error_m=float(np.max(np.abs(final_elevation_error))),
        max_potential_abs_error_m2_s=max_potential_abs,
        rms_potential_abs_error_m2_s=rms_potential_abs,
        max_potential_normalized_error=float(max_potential_abs / potential_scale),
        rms_potential_normalized_error=float(rms_potential_abs / potential_scale),
        final_potential_abs_error_m2_s=float(np.max(np.abs(final_potential_error))),
        potential_amplitude_m2_s=potential_amplitude,
        validity=ValidityReport(
            status=LINEAR_2P5D_FREE_SURFACE_OSCILLATOR_STATUS,
            reference_cases=("linear_deep_water_free_surface_oscillator", "a1_eq19_22_time_level_audit"),
            notes=(
                "Elevation is checked at half_step_time_s and potential at time_s.",
                "This is a diagnostic convergence audit, not a Wigley III hydrodynamic-coefficient hard gate.",
            ),
        ),
    )


def _transient_green_matrices_for_lag(
    field: InnerDomainPanelGeometry,
    source: InnerDomainPanelGeometry,
    lag_s: float,
    *,
    gravity_m_s2: float,
    quadrature_count: int,
    k_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    lag = float(lag_s)
    if lag <= 0.0:
        raise ValueError("lag_s must be positive.")
    if quadrature_count < 16:
        raise ValueError("quadrature_count must be at least 16.")
    if k_max <= 0.0:
        raise ValueError("k_max must be positive.")
    s = np.linspace(0.0, np.sqrt(float(k_max)), int(quadrature_count))
    k = s**2
    y_diff = field.mid_y_m[:, None, None] - source.mid_y_m[None, :, None]
    depth = field.mid_z_down_m[:, None, None] + source.mid_z_down_m[None, :, None]
    kk = k[None, None, :]
    phase = np.sqrt(float(gravity_m_s2)) * s[None, None, :] * lag
    exponential = np.exp(-kk * depth)
    cos_term = np.cos(kk * y_diff)
    sin_term = np.sin(phase)
    base = exponential * cos_term * sin_term
    factor = 4.0 * np.sqrt(float(gravity_m_s2))
    green = factor * np.trapezoid(base, s, axis=2)
    d_green_dy_source = factor * np.trapezoid(exponential * kk * np.sin(kk * y_diff) * sin_term, s, axis=2)
    d_green_dz_source = factor * np.trapezoid(-kk * base, s, axis=2)
    normal_derivative = (
        d_green_dy_source * source.normal_y[None, :]
        + d_green_dz_source * source.normal_z[None, :]
    )
    return green * source.length_m[None, :], normal_derivative * source.length_m[None, :]


def _shift_geometry_midpoints_along_normals(
    geometry: InnerDomainPanelGeometry,
    distance_m: float,
) -> InnerDomainPanelGeometry:
    """Shift panel collocation midpoints along stored normals for kernel derivative audits."""

    distance = float(distance_m)
    return InnerDomainPanelGeometry(
        mid_y_m=np.asarray(geometry.mid_y_m, dtype=float) + distance * np.asarray(geometry.normal_y, dtype=float),
        mid_z_down_m=np.asarray(geometry.mid_z_down_m, dtype=float)
        + distance * np.asarray(geometry.normal_z, dtype=float),
        normal_y=np.asarray(geometry.normal_y, dtype=float),
        normal_z=np.asarray(geometry.normal_z, dtype=float),
        length_m=np.asarray(geometry.length_m, dtype=float),
        node_y_m=np.asarray(geometry.node_y_m, dtype=float),
        node_z_down_m=np.asarray(geometry.node_z_down_m, dtype=float),
    )


def audit_transient_history_kernel_normal_derivative(
    control_geometry: InnerDomainPanelGeometry,
    *,
    lag_s: float,
    finite_difference_epsilon_m: float = 1.0e-4,
    gravity_m_s2: float = 9.80665,
    quadrature_count: int = 256,
    k_max: float = 50.0,
    geometry_name: str = "half_cylinder_control_surface",
) -> A1TransientHistoryKernelDerivativeAudit:
    """Check Eq. (28) normal-derivative kernels against source-normal finite differences."""

    lag = float(lag_s)
    epsilon = float(finite_difference_epsilon_m)
    gravity = float(gravity_m_s2)
    cutoff = float(k_max)
    if lag <= 0.0 or not np.isfinite(lag):
        raise ValueError("lag_s must be positive and finite.")
    if epsilon <= 0.0 or not np.isfinite(epsilon):
        raise ValueError("finite_difference_epsilon_m must be positive and finite.")
    if gravity <= 0.0 or not np.isfinite(gravity):
        raise ValueError("gravity_m_s2 must be positive and finite.")
    if cutoff <= 0.0 or not np.isfinite(cutoff):
        raise ValueError("k_max must be positive and finite.")
    if int(quadrature_count) < 16:
        raise ValueError("quadrature_count must be at least 16.")
    green, normal = _transient_green_matrices_for_lag(
        control_geometry,
        control_geometry,
        lag,
        gravity_m_s2=gravity,
        quadrature_count=int(quadrature_count),
        k_max=cutoff,
    )
    plus, _ = _transient_green_matrices_for_lag(
        control_geometry,
        _shift_geometry_midpoints_along_normals(control_geometry, epsilon),
        lag,
        gravity_m_s2=gravity,
        quadrature_count=int(quadrature_count),
        k_max=cutoff,
    )
    minus, _ = _transient_green_matrices_for_lag(
        control_geometry,
        _shift_geometry_midpoints_along_normals(control_geometry, -epsilon),
        lag,
        gravity_m_s2=gravity,
        quadrature_count=int(quadrature_count),
        k_max=cutoff,
    )
    finite_difference = (plus - minus) / (2.0 * epsilon)
    residual = finite_difference - normal
    residual_norm = float(np.linalg.norm(residual))
    denominator = max(float(np.linalg.norm(finite_difference)), float(np.linalg.norm(normal)), 1e-12)
    radius = float(np.max(np.sqrt(np.asarray(control_geometry.node_y_m) ** 2 + np.asarray(control_geometry.node_z_down_m) ** 2)))
    return A1TransientHistoryKernelDerivativeAudit(
        geometry_name=str(geometry_name),
        panel_count=int(control_geometry.panel_count),
        radius_m=radius,
        lag_s=lag,
        finite_difference_epsilon_m=epsilon,
        gravity_m_s2=gravity,
        quadrature_count=int(quadrature_count),
        k_max=cutoff,
        green_potential_norm=float(np.linalg.norm(green)),
        green_normal_derivative_norm=float(np.linalg.norm(normal)),
        finite_difference_norm=float(np.linalg.norm(finite_difference)),
        residual_norm=residual_norm,
        relative_residual=float(residual_norm / denominator),
        max_abs_residual=float(np.max(np.abs(residual))),
        validity=ValidityReport(
            status=LINEAR_2P5D_HISTORY_DERIVATIVE_STATUS,
            reference_cases=("a1_eq28_transient_green_kernel", "source_normal_finite_difference"),
            notes=(
                "Checks the Eq. (28) C-kernel normal derivative against finite differences of the B-kernel "
                "when source collocation points are shifted along their panel normals.",
                "This isolates the transient-kernel derivative channel; it does not validate the full history RHS.",
            ),
        ),
    )


def build_transient_free_surface_history(
    control_geometry: InnerDomainPanelGeometry,
    dt_s: float,
    history_steps: int,
    *,
    gravity_m_s2: float = 9.80665,
    quadrature_count: int = 96,
    k_max: float | None = None,
) -> TransientFreeSurfaceHistory:
    """Build Eq. (28) transient Green history matrices on the control surface."""

    from .panel_integrals import current_panel_integration_route
    integration_route = current_panel_integration_route()
    dt = float(dt_s)
    steps = int(history_steps)
    if dt <= 0.0:
        raise ValueError("dt_s must be positive.")
    if steps < 1:
        raise ValueError("history_steps must be positive.")
    radius = float(np.max(np.hypot(control_geometry.mid_y_m, control_geometry.mid_z_down_m)))
    cutoff = float(k_max if k_max is not None else max(80.0 / max(radius, 1e-6), 40.0))
    lag_values = dt * np.arange(1, steps + 1, dtype=float)
    if int(quadrature_count) < 16:
        raise ValueError("quadrature_count must be at least 16.")
    if cutoff <= 0.0:
        raise ValueError("k_max must be positive.")
    if integration_route == 'reconstructed_symmetric':
        from .reconstructed_history import reconstructed_history_operators
        green_blocks, normal_blocks = reconstructed_history_operators(
            control_geometry, control_geometry, lag_values,
            gravity=gravity_m_s2, spectral_count=int(quadrature_count), k_max=cutoff)
        return TransientFreeSurfaceHistory(
            lag_s=lag_values, green_potential=green_blocks, green_normal_derivative=normal_blocks,
            dt_s=dt, quadrature_count=int(quadrature_count), k_max=cutoff,
            panel_integration_route=integration_route,
            validity=ValidityReport(status=LINEAR_2P5D_OUTER_HISTORY_STATUS,
                reference_cases=(), notes=('Experimental reconstructed circular history; not physically validated.',)))
    s = np.linspace(0.0, np.sqrt(cutoff), int(quadrature_count))
    k = s[None, None, :]**2
    dy = control_geometry.mid_y_m[:, None, None] - control_geometry.mid_y_m[None, :, None]
    depth = control_geometry.mid_z_down_m[:, None, None] + control_geometry.mid_z_down_m[None, :, None]
    exponential = np.exp(-k * depth)
    cosine = np.cos(k * dy)
    spatial_green = exponential * cosine
    spatial_normal = exponential * k * (
        np.sin(k * dy) * control_geometry.normal_y[None, :, None]
        - cosine * control_geometry.normal_z[None, :, None])
    # Only the sine time factor changes with lag. The trapezoidal weights
    # retain the original quadrature while sharing the expensive spatial terms.
    weights = np.zeros_like(s)
    weights[:-1] += 0.5 * np.diff(s)
    weights[1:] += 0.5 * np.diff(s)
    temporal = 4.0 * np.sqrt(float(gravity_m_s2)) * np.sin(
        np.sqrt(float(gravity_m_s2)) * lag_values[:, None] * s[None, :]) * weights
    count = len(control_geometry.mid_y_m)
    green_blocks = (temporal @ spatial_green.reshape(-1, len(s)).T).reshape(steps, count, count)
    normal_blocks = (temporal @ spatial_normal.reshape(-1, len(s)).T).reshape(steps, count, count)
    green_blocks *= control_geometry.length_m[None, None, :]
    normal_blocks *= control_geometry.length_m[None, None, :]
    return TransientFreeSurfaceHistory(
        lag_s=lag_values,
        green_potential=np.asarray(green_blocks, dtype=float),
        green_normal_derivative=np.asarray(normal_blocks, dtype=float),
        dt_s=dt,
        quadrature_count=int(quadrature_count),
        k_max=cutoff,
        panel_integration_route=integration_route,
        validity=ValidityReport(
            status=LINEAR_2P5D_OUTER_HISTORY_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_submerged_spheroid"),
            notes=("A1 Eq. (12)/(28) transient Green kernels with finite quadrature cutoff.",),
        ),
    )


def _synthetic_control_surface_history_state(
    control_geometry: InnerDomainPanelGeometry,
    lag_s: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return smooth deterministic complex control-surface history states for audits."""

    lag = np.asarray(lag_s, dtype=float)
    if lag.ndim != 1 or len(lag) < 1:
        raise ValueError("lag_s must be a non-empty one-dimensional array.")
    theta = np.arctan2(np.asarray(control_geometry.mid_z_down_m, dtype=float), np.asarray(control_geometry.mid_y_m, dtype=float))
    potential_shape = np.sin(theta)[None, :] + 0.35 * np.cos(2.0 * theta)[None, :]
    potential_phase = 0.15 * np.cos(theta)[None, :]
    normal_shape = np.cos(theta)[None, :] - 0.20 * np.sin(2.0 * theta)[None, :]
    normal_phase = 0.10 * np.sin(theta)[None, :]
    potential_decay = np.exp(-0.45 * lag)[:, None]
    normal_decay = np.exp(-0.30 * lag)[:, None]
    potential = potential_decay * (potential_shape + 1j * potential_phase)
    normal_derivative = normal_decay * (normal_shape + 1j * normal_phase)
    return potential.astype(complex), normal_derivative.astype(complex)


def audit_history_rhs_quadrature_convergence(
    control_geometry: InnerDomainPanelGeometry,
    *,
    dt_s: float = 0.05,
    history_steps: int = 4,
    quadrature_count: int = 96,
    k_max: float = 50.0,
    reference_quadrature_count: int = 512,
    reference_k_max: float = 100.0,
    gravity_m_s2: float = 9.80665,
    quadrature_rule: str = "trapezoid",
    geometry_name: str = "half_cylinder_control_surface",
) -> A1HistoryRhsConvergenceAudit:
    """Compare an Eq. (24) history RHS against a higher-resolution kernel reference."""

    dt = float(dt_s)
    steps = int(history_steps)
    quadrature = int(quadrature_count)
    reference_quadrature = int(reference_quadrature_count)
    cutoff = float(k_max)
    reference_cutoff = float(reference_k_max)
    gravity = float(gravity_m_s2)
    rule = str(quadrature_rule).strip().lower()
    if dt <= 0.0 or not np.isfinite(dt):
        raise ValueError("dt_s must be positive and finite.")
    if steps < 1:
        raise ValueError("history_steps must be positive.")
    if quadrature < 16 or reference_quadrature < 16:
        raise ValueError("quadrature counts must be at least 16.")
    if cutoff <= 0.0 or reference_cutoff <= 0.0 or not np.isfinite(cutoff) or not np.isfinite(reference_cutoff):
        raise ValueError("k_max and reference_k_max must be positive and finite.")
    if gravity <= 0.0 or not np.isfinite(gravity):
        raise ValueError("gravity_m_s2 must be positive and finite.")
    if rule not in {"rectangle", "trapezoid"}:
        raise ValueError("quadrature_rule must be 'rectangle' or 'trapezoid'.")
    history = build_transient_free_surface_history(
        control_geometry,
        dt_s=dt,
        history_steps=steps,
        gravity_m_s2=gravity,
        quadrature_count=quadrature,
        k_max=cutoff,
    )
    reference = build_transient_free_surface_history(
        control_geometry,
        dt_s=dt,
        history_steps=steps,
        gravity_m_s2=gravity,
        quadrature_count=reference_quadrature,
        k_max=reference_cutoff,
    )
    past_potential, past_normal_derivative = _synthetic_control_surface_history_state(control_geometry, history.lag_s)

    def rhs_pair(*, potential_scale: float, normal_scale: float) -> tuple[np.ndarray, np.ndarray]:
        candidate_rhs = history.convolution_rhs(
            past_potential,
            past_normal_derivative,
            quadrature_rule=rule,
            potential_kernel_scale=potential_scale,
            normal_derivative_kernel_scale=normal_scale,
        )
        reference_rhs = reference.convolution_rhs(
            past_potential,
            past_normal_derivative,
            quadrature_rule=rule,
            potential_kernel_scale=potential_scale,
            normal_derivative_kernel_scale=normal_scale,
        )
        return candidate_rhs, reference_rhs

    total, reference_total = rhs_pair(potential_scale=1.0, normal_scale=1.0)
    potential_channel, reference_potential_channel = rhs_pair(potential_scale=1.0, normal_scale=0.0)
    normal_channel, reference_normal_channel = rhs_pair(potential_scale=0.0, normal_scale=1.0)

    def relative(candidate: np.ndarray, reference_values: np.ndarray) -> float:
        residual = np.asarray(candidate - reference_values, dtype=complex)
        return float(np.linalg.norm(residual) / max(float(np.linalg.norm(reference_values)), 1e-12))

    residual = np.asarray(total - reference_total, dtype=complex)
    total_relative = relative(total, reference_total)
    potential_relative = relative(potential_channel, reference_potential_channel)
    normal_relative = relative(normal_channel, reference_normal_channel)
    radius = float(np.max(np.sqrt(np.asarray(control_geometry.node_y_m) ** 2 + np.asarray(control_geometry.node_z_down_m) ** 2)))
    return A1HistoryRhsConvergenceAudit(
        geometry_name=str(geometry_name),
        panel_count=int(control_geometry.panel_count),
        radius_m=radius,
        dt_s=dt,
        history_steps=steps,
        quadrature_rule=rule,
        quadrature_count=quadrature,
        k_max=cutoff,
        reference_quadrature_count=reference_quadrature,
        reference_k_max=reference_cutoff,
        total_rhs_norm=float(np.linalg.norm(total)),
        reference_total_rhs_norm=float(np.linalg.norm(reference_total)),
        total_residual_norm=float(np.linalg.norm(residual)),
        total_relative_residual=total_relative,
        total_max_abs_residual=float(np.max(np.abs(residual))),
        potential_channel_relative_residual=potential_relative,
        normal_derivative_channel_relative_residual=normal_relative,
        max_channel_relative_residual=float(max(total_relative, potential_relative, normal_relative)),
        past_potential_norm=float(np.linalg.norm(past_potential)),
        past_normal_derivative_norm=float(np.linalg.norm(past_normal_derivative)),
        validity=ValidityReport(
            status=LINEAR_2P5D_HISTORY_CONVERGENCE_STATUS,
            reference_cases=("a1_eq24_history_rhs_refinement", "synthetic_control_surface_history_state"),
            notes=(
                "Compares Eq. (24) history RHS against a higher quadrature_count/k_max reference using "
                "deterministic smooth complex control-surface history states.",
                "This checks kernel quadrature/cutoff convergence, not Wigley III coefficient acceptance.",
            ),
        ),
    )


def _log_potential_between_raw(
    field: InnerDomainPanelGeometry,
    source: InnerDomainPanelGeometry,
    *,
    mirrored_source: bool = False,
    same_boundary: bool = False,
) -> np.ndarray:
    from .panel_integrals import use_exact_straight_panels, straight_log_integrals, current_panel_integration_route, reconstructed_candidate_operators
    if current_panel_integration_route() == 'reconstructed_symmetric':
        return reconstructed_candidate_operators(field, source, mirrored_source=mirrored_source,
                                                same_boundary=same_boundary)[0]
    if use_exact_straight_panels(source):
        return straight_log_integrals(field, source, mirrored_source=mirrored_source,
                                      same_boundary=same_boundary)[0]
    source_z = -source.mid_z_down_m if mirrored_source else source.mid_z_down_m
    dy = field.mid_y_m[:, None] - source.mid_y_m[None, :]
    dz = field.mid_z_down_m[:, None] - source_z[None, :]
    radius = np.sqrt(np.maximum(dy**2 + dz**2, 1e-18))
    matrix = np.log(radius) * source.length_m[None, :]
    if same_boundary and not mirrored_source:
        diagonal = source.length_m * (np.log(np.maximum(0.5 * source.length_m, 1e-18)) - 1.0)
        np.fill_diagonal(matrix, diagonal)
    return matrix


def _log_normal_derivative_between_raw(
    field: InnerDomainPanelGeometry,
    source: InnerDomainPanelGeometry,
    *,
    mirrored_source: bool = False,
    same_boundary: bool = False,
    diagonal_sign: float = 1.0,
) -> np.ndarray:
    from .panel_integrals import use_exact_straight_panels, straight_log_integrals, current_panel_integration_route, reconstructed_candidate_operators
    if current_panel_integration_route() == 'reconstructed_symmetric':
        return reconstructed_candidate_operators(field, source, mirrored_source=mirrored_source,
                                                same_boundary=same_boundary, diagonal_sign=diagonal_sign)[1]
    if use_exact_straight_panels(source):
        return straight_log_integrals(field, source, mirrored_source=mirrored_source,
                                      same_boundary=same_boundary, diagonal_sign=diagonal_sign)[1]
    source_z = -source.mid_z_down_m if mirrored_source else source.mid_z_down_m
    dy = field.mid_y_m[:, None] - source.mid_y_m[None, :]
    dz = field.mid_z_down_m[:, None] - source_z[None, :]
    r2 = np.maximum(dy**2 + dz**2, 1e-18)
    dlog_dsource_y = -dy / r2
    dlog_dsource_z = dz / r2 if mirrored_source else -dz / r2
    matrix = (
        dlog_dsource_y * source.normal_y[None, :]
        + dlog_dsource_z * source.normal_z[None, :]
    ) * source.length_m[None, :]
    if same_boundary and not mirrored_source:
        np.fill_diagonal(matrix, float(diagonal_sign) * np.pi)
    return matrix


def _log_potential_matrix_raw(geometry: InnerDomainPanelGeometry, *, mirrored_source: bool = False) -> np.ndarray:
    return _log_potential_between_raw(
        geometry,
        geometry,
        mirrored_source=mirrored_source,
        same_boundary=not mirrored_source,
    )


def _log_normal_derivative_matrix_raw(
    geometry: InnerDomainPanelGeometry,
    *,
    mirrored_source: bool = False,
    diagonal_sign: float = 1.0,
) -> np.ndarray:
    return _log_normal_derivative_between_raw(
        geometry,
        geometry,
        mirrored_source=mirrored_source,
        same_boundary=not mirrored_source,
        diagonal_sign=float(diagonal_sign),
    )


def assemble_outer_control_surface_system(
    control_geometry: InnerDomainPanelGeometry,
    history: TransientFreeSurfaceHistory,
    past_potential: np.ndarray,
    past_normal_derivative: np.ndarray,
    *,
    history_rhs_scale: float = 1.0,
    history_convolution_rule: str = "trapezoid",
    history_potential_kernel_scale: float = 1.0,
    history_normal_derivative_kernel_scale: float = 1.0,
    control_image_scale: float = 1.0,
    control_potential_kernel_scale: float = 1.0,
    control_normal_derivative_kernel_scale: float = 1.0,
    control_diagonal_sign: float = 1.0,
) -> MatchedBoundarySystem:
    """Assemble the A1 Eq. (24) outer-domain control-surface equation block."""

    from .panel_integrals import current_panel_integration_route
    route = current_panel_integration_route()
    if ('reconstructed_symmetric' in (route, history.panel_integration_route)
            and route != history.panel_integration_route):
        raise ValueError('Current and history panel integration routes must match')
    rule = str(history_convolution_rule).strip().lower()
    if rule not in {"rectangle", "trapezoid"}:
        raise ValueError("history_convolution_rule must be 'rectangle' or 'trapezoid'.")
    potential_scale = float(history_potential_kernel_scale)
    normal_scale = float(history_normal_derivative_kernel_scale)
    if not np.isfinite(potential_scale) or not np.isfinite(normal_scale):
        raise ValueError("history kernel scales must be finite.")
    image_scale = float(control_image_scale)
    control_potential_scale = float(control_potential_kernel_scale)
    control_normal_scale = float(control_normal_derivative_kernel_scale)
    diagonal_sign = float(control_diagonal_sign)
    if not all(np.isfinite(value) for value in (image_scale, control_potential_scale, control_normal_scale, diagonal_sign)):
        raise ValueError("control-surface instantaneous diagnostic scales must be finite.")
    if history.green_potential.shape[1:] != (control_geometry.panel_count, control_geometry.panel_count):
        raise ValueError("history matrices must match control_geometry panel count.")
    a = _log_normal_derivative_matrix_raw(
        control_geometry,
        mirrored_source=False,
        diagonal_sign=diagonal_sign,
    )
    a_bar = _log_normal_derivative_matrix_raw(control_geometry, mirrored_source=True)
    b = _log_potential_matrix_raw(control_geometry, mirrored_source=False)
    b_bar = _log_potential_matrix_raw(control_geometry, mirrored_source=True)
    matrix = np.hstack(
        [
            control_potential_scale * (a - image_scale * a_bar),
            -control_normal_scale * (b - image_scale * b_bar),
        ]
    ).astype(complex)
    rhs = history.convolution_rhs(
        past_potential,
        past_normal_derivative,
        rhs_scale=history_rhs_scale,
        quadrature_rule=rule,
        potential_kernel_scale=potential_scale,
        normal_derivative_kernel_scale=normal_scale,
    )
    labels = tuple(f"psi_c_{index}" for index in range(control_geometry.panel_count)) + tuple(
        f"psi_n_c_{index}" for index in range(control_geometry.panel_count)
    )
    return MatchedBoundarySystem(
        matrix=matrix,
        rhs=rhs,
        unknown_labels=labels,
        validity=ValidityReport(
            status=LINEAR_2P5D_CONTROL_MATCH_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_submerged_spheroid"),
            notes=(
                "A1 Eq. (24) outer control-surface block. The complete inner/outer square system is assembled "
                "by assemble_matched_section_system().",
            ),
        ),
    )


def _antisymmetric_half_plane_source_on_boundary(
    geometry: InnerDomainPanelGeometry,
    *,
    source_y_m: float,
    source_z_down_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return `ln r - ln r'` and its normal derivative on a lower-half-plane boundary."""

    source_y = float(source_y_m)
    source_z = float(source_z_down_m)
    if source_z <= 0.0:
        raise ValueError("source_z_down_m must be positive for a source below the free surface.")
    y = np.asarray(geometry.mid_y_m, dtype=float)
    z = np.asarray(geometry.mid_z_down_m, dtype=float)
    ny = np.asarray(geometry.normal_y, dtype=float)
    nz = np.asarray(geometry.normal_z, dtype=float)
    radius = float(np.max(np.sqrt(np.asarray(geometry.node_y_m) ** 2 + np.asarray(geometry.node_z_down_m) ** 2)))
    source_radius = float(np.sqrt(source_y**2 + source_z**2))
    if source_radius >= 0.95 * radius:
        raise ValueError("The analytic source must be comfortably inside the control surface.")
    r2 = np.maximum((y - source_y) ** 2 + (z - source_z) ** 2, 1e-18)
    r2_image = np.maximum((y - source_y) ** 2 + (z + source_z) ** 2, 1e-18)
    potential = 0.5 * np.log(r2) - 0.5 * np.log(r2_image)
    grad_y = (y - source_y) / r2 - (y - source_y) / r2_image
    grad_z = (z - source_z) / r2 - (z + source_z) / r2_image
    normal_derivative = grad_y * ny + grad_z * nz
    return potential.astype(complex), normal_derivative.astype(complex)


def audit_outer_control_surface_green_identity(
    control_geometry: InnerDomainPanelGeometry,
    *,
    potential_name: str = "antisymmetric_source",
    geometry_name: str = "half_cylinder_control_surface",
    source_y_m: float = 0.2,
    source_z_down_m: float = 0.3,
    control_image_scale: float = 1.0,
    control_potential_kernel_scale: float = 1.0,
    control_normal_derivative_kernel_scale: float = 1.0,
    control_diagonal_sign: float = 1.0,
) -> A1OuterControlGreenIdentityAudit:
    """Audit the no-history Eq. (24) control-surface identity with an image source."""

    name = str(potential_name).strip().lower()
    if name not in {"antisymmetric_source", "image_source", "dirichlet_source"}:
        raise ValueError("potential_name must be 'antisymmetric_source'.")
    image_scale = float(control_image_scale)
    potential_scale = float(control_potential_kernel_scale)
    normal_scale = float(control_normal_derivative_kernel_scale)
    diagonal_sign = float(control_diagonal_sign)
    if not all(np.isfinite(value) for value in (image_scale, potential_scale, normal_scale, diagonal_sign)):
        raise ValueError("control-surface diagnostic scales must be finite.")
    potential, normal_derivative = _antisymmetric_half_plane_source_on_boundary(
        control_geometry,
        source_y_m=float(source_y_m),
        source_z_down_m=float(source_z_down_m),
    )
    a = _log_normal_derivative_matrix_raw(
        control_geometry,
        mirrored_source=False,
        diagonal_sign=diagonal_sign,
    )
    a_bar = _log_normal_derivative_matrix_raw(control_geometry, mirrored_source=True)
    b = _log_potential_matrix_raw(control_geometry, mirrored_source=False)
    b_bar = _log_potential_matrix_raw(control_geometry, mirrored_source=True)
    potential_term = potential_scale * ((a - image_scale * a_bar) @ potential)
    normal_term = normal_scale * ((b - image_scale * b_bar) @ normal_derivative)
    residual = potential_term - normal_term
    residual_norm = float(np.linalg.norm(residual))
    denominator = max(float(np.linalg.norm(potential_term) + np.linalg.norm(normal_term)), 1e-12)
    radius = float(np.max(np.sqrt(np.asarray(control_geometry.node_y_m) ** 2 + np.asarray(control_geometry.node_z_down_m) ** 2)))
    return A1OuterControlGreenIdentityAudit(
        geometry_name=str(geometry_name),
        potential_name=name,
        panel_count=int(control_geometry.panel_count),
        radius_m=radius,
        source_y_m=float(source_y_m),
        source_z_down_m=float(source_z_down_m),
        control_image_scale=image_scale,
        control_potential_kernel_scale=potential_scale,
        control_normal_derivative_kernel_scale=normal_scale,
        control_diagonal_sign=diagonal_sign,
        residual_norm=residual_norm,
        relative_residual=float(residual_norm / denominator),
        max_abs_residual=float(np.max(np.abs(residual))),
        potential_norm=float(np.linalg.norm(potential)),
        normal_derivative_norm=float(np.linalg.norm(normal_derivative)),
        potential_term_norm=float(np.linalg.norm(potential_term)),
        normal_derivative_term_norm=float(np.linalg.norm(normal_term)),
        validity=ValidityReport(
            status=LINEAR_2P5D_CONTROL_IDENTITY_STATUS,
            reference_cases=("a1_eq24_half_plane_image_source", "ma2005_control_surface_instantaneous_terms"),
            notes=(
                "Uses an antisymmetric image source inside the control surface, so the field is harmonic "
                "in the outer half-plane and zero on the free surface.",
                "This is a homogeneous no-history Eq. (24) identity; reversing both unknown columns is row-sign "
                "ambiguous unless the history RHS is included.",
            ),
        ),
    )


def _validate_matched_boundary_data(data: MatchedSectionBoundaryData) -> None:
    if data.body_normal_velocity.shape != (data.body.panel_count,):
        raise ValueError(
            f"body_normal_velocity must have shape ({data.body.panel_count},), got {data.body_normal_velocity.shape}."
        )
    if data.free_surface_potential.shape != (data.inner_free_surface.panel_count,):
        raise ValueError(
            "free_surface_potential must have shape "
            f"({data.inner_free_surface.panel_count},), got {data.free_surface_potential.shape}."
        )
    if data.free_surface_potential_control_row is not None and data.free_surface_potential_control_row.shape != (
        data.inner_free_surface.panel_count,
    ):
        raise ValueError(
            "free_surface_potential_control_row must have shape "
            f"({data.inner_free_surface.panel_count},), got {data.free_surface_potential_control_row.shape}."
        )
    if data.history.green_potential.shape[1:] != (data.control.panel_count, data.control.panel_count):
        raise ValueError("history matrices must match control panel count.")
    if not np.isfinite(float(data.history_rhs_scale)):
        raise ValueError("history_rhs_scale must be finite.")
    if str(data.history_convolution_rule).strip().lower() not in {"rectangle", "trapezoid"}:
        raise ValueError("history_convolution_rule must be 'rectangle' or 'trapezoid'.")
    if not np.isfinite(float(data.history_potential_kernel_scale)):
        raise ValueError("history_potential_kernel_scale must be finite.")
    if not np.isfinite(float(data.history_normal_derivative_kernel_scale)):
        raise ValueError("history_normal_derivative_kernel_scale must be finite.")
    control_scales = (
        data.control_image_scale,
        data.control_potential_kernel_scale,
        data.control_normal_derivative_kernel_scale,
        data.control_diagonal_sign,
        data.inner_a_scale,
        data.inner_b_scale,
        data.inner_diagonal_sign,
        data.inner_free_surface_self_diagonal_scale,
        data.inner_free_surface_known_potential_rhs_scale,
        data.inner_free_surface_known_potential_body_row_scale,
        data.inner_free_surface_known_potential_free_row_scale,
        data.inner_free_surface_known_potential_control_row_scale,
        data.inner_free_surface_unknown_normal_column_scale,
    )
    if not all(np.isfinite(float(value)) for value in control_scales):
        raise ValueError("control-surface and inner-domain diagnostic scales must be finite.")


def _inner_a_matrix(
    field: InnerDomainPanelGeometry,
    source: InnerDomainPanelGeometry,
    *,
    same_boundary: bool = False,
    diagonal_sign: float = -1.0,
) -> np.ndarray:
    return _log_normal_derivative_between_raw(
        field,
        source,
        same_boundary=same_boundary,
        diagonal_sign=float(diagonal_sign),
    )


def _inner_b_matrix(
    field: InnerDomainPanelGeometry,
    source: InnerDomainPanelGeometry,
    *,
    same_boundary: bool = False,
) -> np.ndarray:
    return _log_potential_between_raw(field, source, same_boundary=same_boundary)


def _body_geometry_with_inner_fluid_outward_normal(
    body: InnerDomainPanelGeometry,
) -> InnerDomainPanelGeometry:
    """Return the body boundary with the A1 inner-fluid-domain source normal.

    Section offsets are traversed from starboard waterline through the keel to
    port waterline, so their stored normal points out of the hull and into the
    fluid.  In A1 Eq. (11)/Eq. (23), however, the body is an internal boundary
    of ``D_i`` and the Green-identity source normal points out of ``D_i`` and
    into the hull.  Only the normal is reversed; collocation points, panel
    lengths, and the body-potential unknown ordering remain unchanged.
    """

    return InnerDomainPanelGeometry(
        mid_y_m=np.asarray(body.mid_y_m, dtype=float),
        mid_z_down_m=np.asarray(body.mid_z_down_m, dtype=float),
        normal_y=-np.asarray(body.normal_y, dtype=float),
        normal_z=-np.asarray(body.normal_z, dtype=float),
        length_m=np.asarray(body.length_m, dtype=float),
        node_y_m=np.asarray(body.node_y_m, dtype=float),
        node_z_down_m=np.asarray(body.node_z_down_m, dtype=float),
    )


def audit_body_boundary_inner_fluid_normal(
    body: InnerDomainPanelGeometry,
    inner_free_surface: InnerDomainPanelGeometry,
    control: InnerDomainPanelGeometry,
    *,
    potential_name: str = "linear_y",
) -> A1BodyBoundaryNormalAudit:
    """Compare the stored and A1-correct body source normals on a composite boundary.

    The analytic harmonic potential is evaluated on the physical inner-domain
    boundary formed by the hull, the outboard free surface, and the fixed
    control surface.  Its body normal derivative always uses the outward normal
    of the fluid domain.  The two residuals differ only in the body-source
    normal used by the ``A_body`` Green-kernel block, isolating the Eq. (23)
    orientation error from pressure recovery and coefficient normalization.
    """

    boundaries = (body, inner_free_surface, control)
    if any(boundary.panel_count < 1 for boundary in boundaries):
        raise ValueError("body, inner_free_surface, and control must contain panels.")
    body_inner = _body_geometry_with_inner_fluid_outward_normal(body)
    body_phi, body_phi_n = _analytic_harmonic_potential_on_boundary(body_inner, potential_name)
    free_phi, free_phi_n = _analytic_harmonic_potential_on_boundary(inner_free_surface, potential_name)
    control_phi, control_phi_n = _analytic_harmonic_potential_on_boundary(control, potential_name)
    phi_values = (body_phi, free_phi, control_phi)
    phi_normal_values = (body_phi_n, free_phi_n, control_phi_n)

    def residual_for(body_source: InnerDomainPanelGeometry) -> np.ndarray:
        sources = (body_source, inner_free_surface, control)
        residual_blocks: list[np.ndarray] = []
        for field_index, field in enumerate(boundaries):
            block = np.zeros(field.panel_count, dtype=complex)
            for source_index, source in enumerate(sources):
                block += _inner_a_matrix(
                    field,
                    source,
                    same_boundary=field_index == source_index,
                    diagonal_sign=-1.0,
                ) @ phi_values[source_index]
                block -= _inner_b_matrix(
                    field,
                    source,
                    same_boundary=field_index == source_index,
                ) @ phi_normal_values[source_index]
            residual_blocks.append(block)
        return np.concatenate(residual_blocks)

    stored_residual = residual_for(body)
    corrected_residual = residual_for(body_inner)
    phi_norm = max(float(np.linalg.norm(np.concatenate(phi_values))), 1e-12)
    stored_norm = float(np.linalg.norm(stored_residual))
    corrected_norm = float(np.linalg.norm(corrected_residual))
    return A1BodyBoundaryNormalAudit(
        potential_name=str(potential_name).strip().lower(),
        body_panel_count=int(body.panel_count),
        free_panel_count=int(inner_free_surface.panel_count),
        control_panel_count=int(control.panel_count),
        total_panel_count=int(sum(boundary.panel_count for boundary in boundaries)),
        stored_body_normal_residual_norm=stored_norm,
        stored_body_normal_relative_residual=float(stored_norm / phi_norm),
        inner_fluid_body_normal_residual_norm=corrected_norm,
        inner_fluid_body_normal_relative_residual=float(corrected_norm / phi_norm),
        corrected_to_stored_residual_ratio=float(corrected_norm / max(stored_norm, 1e-12)),
        stored_body_normal_max_abs_residual=float(np.max(np.abs(stored_residual))),
        inner_fluid_body_normal_max_abs_residual=float(np.max(np.abs(corrected_residual))),
        validity=ValidityReport(
            status=LINEAR_2P5D_BODY_BOUNDARY_NORMAL_STATUS,
            reference_cases=("a1_eq11_eq23_composite_inner_domain", "ma2005_wigley_iii"),
            notes=(
                "A1 Eq.11/Eq.23 uses the outward normal of the inner fluid domain. On the internal hull boundary "
                "this is opposite to the normal stored by section offsets; free-surface and control normals are unchanged.",
            ),
        ),
    )


def assemble_matched_section_system(data: MatchedSectionBoundaryData) -> MatchedBoundarySystem:
    """Assemble the square A1 Eq. (23)-Eq. (24) matched system for one section.

    Unknown ordering follows the algebraic form directly:
    `psi_body`, `psi_n_inner_free_surface`, `psi_control`, `psi_n_control`.
    Body normal velocity and inner free-surface potential are supplied as known
    boundary values from the body condition and A1 Eq. (20), respectively.
    """

    _validate_matched_boundary_data(data)
    body = data.body
    body_inner_source = _body_geometry_with_inner_fluid_outward_normal(body)
    free = data.inner_free_surface
    control = data.control
    inner_a_scale = float(data.inner_a_scale)
    inner_b_scale = float(data.inner_b_scale)
    inner_diagonal_sign = float(data.inner_diagonal_sign)
    free_known_rhs_scale = float(data.inner_free_surface_known_potential_rhs_scale)
    free_potential = np.asarray(data.free_surface_potential, dtype=complex)
    free_potential_control_row = (
        free_potential
        if data.free_surface_potential_control_row is None
        else np.asarray(data.free_surface_potential_control_row, dtype=complex)
    )
    free_known_row_scales = (
        float(data.inner_free_surface_known_potential_body_row_scale),
        float(data.inner_free_surface_known_potential_free_row_scale),
        float(data.inner_free_surface_known_potential_control_row_scale),
    )
    free_unknown_column_scale = float(data.inner_free_surface_unknown_normal_column_scale)
    boundaries = (body, free, control)
    n_body = body.panel_count
    n_free = free.panel_count
    n_control = control.panel_count
    n_inner_rows = n_body + n_free + n_control
    n_unknowns = n_body + n_free + 2 * n_control
    inner_matrix = np.zeros((n_inner_rows, n_unknowns), dtype=complex)
    inner_rhs = np.zeros(n_inner_rows, dtype=complex)

    row_start = 0
    for field_index, field in enumerate(boundaries):
        row_slice = slice(row_start, row_start + field.panel_count)
        a_body = inner_a_scale * _inner_a_matrix(
            field,
            body_inner_source,
            same_boundary=field_index == 0,
            diagonal_sign=inner_diagonal_sign,
        )
        b_body = inner_b_scale * _inner_b_matrix(field, body, same_boundary=field_index == 0)
        a_free = inner_a_scale * _inner_a_matrix(
            field,
            free,
            same_boundary=field_index == 1,
            diagonal_sign=inner_diagonal_sign
            * (float(data.inner_free_surface_self_diagonal_scale) if field_index == 1 else 1.0),
        )
        b_free = inner_b_scale * _inner_b_matrix(field, free, same_boundary=field_index == 1)
        a_control = inner_a_scale * _inner_a_matrix(
            field,
            control,
            same_boundary=field_index == 2,
            diagonal_sign=inner_diagonal_sign,
        )
        b_control = inner_b_scale * _inner_b_matrix(field, control, same_boundary=field_index == 2)

        body_cols = slice(0, n_body)
        free_normal_cols = slice(n_body, n_body + n_free)
        control_potential_cols = slice(n_body + n_free, n_body + n_free + n_control)
        control_normal_cols = slice(n_body + n_free + n_control, n_unknowns)

        inner_matrix[row_slice, body_cols] = a_body
        inner_matrix[row_slice, free_normal_cols] = -free_unknown_column_scale * b_free
        inner_matrix[row_slice, control_potential_cols] = a_control
        inner_matrix[row_slice, control_normal_cols] = -b_control
        row_known_scale = free_known_rhs_scale * free_known_row_scales[field_index]
        row_free_potential = free_potential_control_row if field_index == 2 else free_potential
        inner_rhs[row_slice] = b_body @ np.asarray(
            data.body_normal_velocity,
            dtype=complex,
        ) - row_known_scale * (a_free @ row_free_potential)
        row_start = row_slice.stop

    outer = assemble_outer_control_surface_system(
        control,
        data.history,
        data.past_control_potential,
        data.past_control_normal_derivative,
        history_rhs_scale=float(data.history_rhs_scale),
        history_convolution_rule=str(data.history_convolution_rule),
        history_potential_kernel_scale=float(data.history_potential_kernel_scale),
        history_normal_derivative_kernel_scale=float(data.history_normal_derivative_kernel_scale),
        control_image_scale=float(data.control_image_scale),
        control_potential_kernel_scale=float(data.control_potential_kernel_scale),
        control_normal_derivative_kernel_scale=float(data.control_normal_derivative_kernel_scale),
        control_diagonal_sign=float(data.control_diagonal_sign),
    )
    outer_matrix = np.zeros((n_control, n_unknowns), dtype=complex)
    outer_matrix[:, n_body + n_free :] = outer.matrix
    matrix = np.vstack([inner_matrix, outer_matrix])
    rhs = np.concatenate([inner_rhs, outer.rhs])
    labels = (
        tuple(f"psi_body_{index}" for index in range(n_body))
        + tuple(f"psi_n_free_{index}" for index in range(n_free))
        + tuple(f"psi_control_{index}" for index in range(n_control))
        + tuple(f"psi_n_control_{index}" for index in range(n_control))
    )
    return MatchedBoundarySystem(
        matrix=matrix,
        rhs=rhs,
        unknown_labels=labels,
        validity=ValidityReport(
            status=LINEAR_2P5D_MATCHED_SYSTEM_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_submerged_spheroid"),
            notes=(
                "Square A1 Eq. (23)-Eq. (24) matched system. Pressure recovery, forward-speed gradient terms, "
                "and end-term assembly are implemented in downstream helpers; benchmark-calibrated quadrature "
                "and coefficient gates remain pending.",
            ),
        ),
    )


def split_matched_section_solution(
    data: MatchedSectionBoundaryData,
    solution: np.ndarray,
) -> MatchedSectionSolution:
    """Split the matched system solution into named A1 boundary values."""

    values = np.asarray(solution, dtype=complex)
    n_body = data.body.panel_count
    n_free = data.inner_free_surface.panel_count
    n_control = data.control.panel_count
    expected = n_body + n_free + 2 * n_control
    if values.shape != (expected,):
        raise ValueError(f"solution must have shape ({expected},), got {values.shape}.")
    body_slice = slice(0, n_body)
    free_slice = slice(n_body, n_body + n_free)
    control_slice = slice(n_body + n_free, n_body + n_free + n_control)
    control_normal_slice = slice(n_body + n_free + n_control, expected)
    return MatchedSectionSolution(
        body_potential=values[body_slice],
        inner_free_surface_normal_derivative=values[free_slice],
        control_potential=values[control_slice],
        control_normal_derivative=values[control_normal_slice],
        validity=ValidityReport(
            status=LINEAR_2P5D_MATCHED_SYSTEM_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_submerged_spheroid"),
            notes=("Named solution slices from the A1 Eq. (23)-Eq. (24) matched system.",),
        ),
    )


def _scale_matched_section_solution(
    solution: MatchedSectionSolution,
    scale: complex,
) -> MatchedSectionSolution:
    """Return a copy with every boundary value multiplied by ``scale``."""

    factor = complex(scale)
    return MatchedSectionSolution(
        body_potential=np.asarray(solution.body_potential, dtype=complex) * factor,
        inner_free_surface_normal_derivative=np.asarray(
            solution.inner_free_surface_normal_derivative,
            dtype=complex,
        )
        * factor,
        control_potential=np.asarray(solution.control_potential, dtype=complex) * factor,
        control_normal_derivative=np.asarray(solution.control_normal_derivative, dtype=complex) * factor,
        validity=solution.validity,
    )


def _matched_section_solution_values(solution: MatchedSectionSolution) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(solution.body_potential, dtype=complex),
            np.asarray(solution.inner_free_surface_normal_derivative, dtype=complex),
            np.asarray(solution.control_potential, dtype=complex),
            np.asarray(solution.control_normal_derivative, dtype=complex),
        ]
    )


def _matched_section_rhs_source_vectors(data: MatchedSectionBoundaryData) -> dict[str, np.ndarray]:
    """Return full matched-system RHS vectors split by physical known source."""

    _validate_matched_boundary_data(data)
    body = data.body
    free = data.inner_free_surface
    control = data.control
    inner_a_scale = float(data.inner_a_scale)
    inner_b_scale = float(data.inner_b_scale)
    inner_diagonal_sign = float(data.inner_diagonal_sign)
    free_known_rhs_scale = float(data.inner_free_surface_known_potential_rhs_scale)
    free_potential = np.asarray(data.free_surface_potential, dtype=complex)
    free_potential_control_row = (
        free_potential
        if data.free_surface_potential_control_row is None
        else np.asarray(data.free_surface_potential_control_row, dtype=complex)
    )
    free_known_row_scales = (
        float(data.inner_free_surface_known_potential_body_row_scale),
        float(data.inner_free_surface_known_potential_free_row_scale),
        float(data.inner_free_surface_known_potential_control_row_scale),
    )
    boundaries = (body, free, control)
    n_body = body.panel_count
    n_free = free.panel_count
    n_control = control.panel_count
    n_inner_rows = n_body + n_free + n_control
    total_rows = n_inner_rows + n_control
    sources = {
        "body_normal_velocity": np.zeros(total_rows, dtype=complex),
        "inner_free_surface_potential": np.zeros(total_rows, dtype=complex),
        "outer_control_history": np.zeros(total_rows, dtype=complex),
    }
    row_start = 0
    for field_index, field in enumerate(boundaries):
        row_slice = slice(row_start, row_start + field.panel_count)
        b_body = inner_b_scale * _inner_b_matrix(field, body, same_boundary=field_index == 0)
        a_free = inner_a_scale * _inner_a_matrix(
            field,
            free,
            same_boundary=field_index == 1,
            diagonal_sign=inner_diagonal_sign
            * (float(data.inner_free_surface_self_diagonal_scale) if field_index == 1 else 1.0),
        )
        sources["body_normal_velocity"][row_slice] = b_body @ np.asarray(
            data.body_normal_velocity,
            dtype=complex,
        )
        row_known_scale = free_known_rhs_scale * free_known_row_scales[field_index]
        row_free_potential = free_potential_control_row if field_index == 2 else free_potential
        sources["inner_free_surface_potential"][row_slice] = -row_known_scale * (
            a_free @ row_free_potential
        )
        row_start = row_slice.stop
    outer = assemble_outer_control_surface_system(
        control,
        data.history,
        data.past_control_potential,
        data.past_control_normal_derivative,
        history_rhs_scale=float(data.history_rhs_scale),
        history_convolution_rule=str(data.history_convolution_rule),
        history_potential_kernel_scale=float(data.history_potential_kernel_scale),
        history_normal_derivative_kernel_scale=float(data.history_normal_derivative_kernel_scale),
        control_image_scale=float(data.control_image_scale),
        control_potential_kernel_scale=float(data.control_potential_kernel_scale),
        control_normal_derivative_kernel_scale=float(data.control_normal_derivative_kernel_scale),
        control_diagonal_sign=float(data.control_diagonal_sign),
    )
    sources["outer_control_history"][n_inner_rows:] = np.asarray(outer.rhs, dtype=complex)
    return sources


def audit_inner_free_surface_rhs_block_contributions(
    sweep: StationHullMatchedHeavePitchSweep,
    *,
    mode_name: str = "heave",
    station_count: int = 2,
) -> tuple[A1InnerFreeSurfaceRhsBlockAudit, ...]:
    """Decompose Eq. (23) `-A_free * phi_free` into row-block and panel contributions.

    The audit is intentionally narrow: it reconstructs the actual station marching
    order, then inspects the known inner-free-surface-potential RHS term without
    changing the solved section.  This keeps the first-aft-station diagnosis
    reproducible while preserving the production matched-BIE path.
    """

    mode = str(mode_name).strip().lower()
    if mode not in {"heave", "pitch"}:
        raise ValueError("mode_name must be 'heave' or 'pitch'.")
    active_count = int(len(sweep.x_m))
    count = min(int(station_count), active_count)
    if count < 1:
        raise ValueError("sweep must contain at least one station.")
    if len(sweep.inner_free_surface_geometries) != active_count:
        raise ValueError("sweep.inner_free_surface_geometries must be recorded for every active station.")
    solve_order = tuple(int(index) for index in sweep.solve_order)
    if sorted(solve_order) != list(range(active_count)):
        raise ValueError("sweep.solve_order must be a permutation of station local indices.")
    solutions = sweep.heave_mode_solutions if mode == "heave" else sweep.pitch_mode_solutions
    if len(solutions) != active_count:
        raise ValueError(f"{mode} solution count must match the active station count.")
    free_potential_by_station = (
        sweep.heave_free_surface_potential_by_station
        if mode == "heave"
        else sweep.pitch_free_surface_potential_by_station
    )
    control, history = _history_from_sweep_metadata(sweep)
    past_phi = np.zeros((int(sweep.history_steps), int(sweep.control_panel_count)), dtype=complex)
    past_phi_n = np.zeros_like(past_phi)
    rows: list[A1InnerFreeSurfaceRhsBlockAudit] = []
    row_block_names = ("eq23_body", "eq23_free_surface", "eq23_inner_control")
    validity = ValidityReport(
        status=LINEAR_2P5D_INNER_FREE_SURFACE_RHS_BLOCK_STATUS,
        reference_cases=("ma2005_wigley_iii_station_sweep",),
        notes=(
            "Decomposes the known Eq.23 inner-free-surface-potential RHS term -A_free*phi_free by row block "
            "and free-surface panel. It is a failure-tracing diagnostic, not a hydrodynamic hard gate.",
        ),
    )
    for rank, local_index in enumerate(solve_order):
        body = sweep.bodies[local_index]
        free = sweep.inner_free_surface_geometries[local_index]
        body_condition = _body_normal_velocity_from_sweep(
            sweep,
            mode_name=mode,
            station_local_index=local_index,
        )
        data = MatchedSectionBoundaryData(
            body=body,
            inner_free_surface=free,
            control=control,
            body_normal_velocity=np.asarray(body_condition, dtype=complex),
            free_surface_potential=np.asarray(free_potential_by_station[local_index], dtype=complex),
            history=history,
            past_control_potential=past_phi,
            past_control_normal_derivative=past_phi_n,
            history_rhs_scale=float(sweep.history_rhs_scale),
            history_convolution_rule=str(sweep.history_convolution_rule),
            history_potential_kernel_scale=float(sweep.history_potential_kernel_scale),
            history_normal_derivative_kernel_scale=float(sweep.history_normal_derivative_kernel_scale),
            control_image_scale=float(sweep.control_image_scale),
            control_potential_kernel_scale=float(sweep.control_potential_kernel_scale),
            control_normal_derivative_kernel_scale=float(sweep.control_normal_derivative_kernel_scale),
            control_diagonal_sign=float(sweep.control_diagonal_sign),
            inner_a_scale=float(sweep.inner_a_scale),
            inner_b_scale=float(sweep.inner_b_scale),
            inner_diagonal_sign=float(sweep.inner_diagonal_sign),
            inner_free_surface_self_diagonal_scale=float(sweep.inner_free_surface_self_diagonal_scale),
            inner_free_surface_known_potential_rhs_scale=float(
                sweep.inner_free_surface_known_potential_rhs_scale
            ),
            inner_free_surface_unknown_normal_column_scale=float(
                sweep.inner_free_surface_unknown_normal_column_scale
            ),
        )
        if local_index < count:
            source_rhs = _matched_section_rhs_source_vectors(data)["inner_free_surface_potential"]
            total_free_rhs_norm = float(np.linalg.norm(source_rhs))
            total_rows = source_rhs.shape[0]
            row_start = 0
            for field_index, (row_block_name, field_geometry) in enumerate(
                zip(row_block_names, (body, free, control))
            ):
                row_slice = slice(row_start, row_start + field_geometry.panel_count)
                a_free = (
                    float(data.inner_free_surface_known_potential_rhs_scale)
                    * float(data.inner_a_scale)
                    * _inner_a_matrix(
                        field_geometry,
                        free,
                        same_boundary=field_index == 1,
                        diagonal_sign=float(data.inner_diagonal_sign)
                        * (float(data.inner_free_surface_self_diagonal_scale) if field_index == 1 else 1.0),
                    )
                )
                free_phi = np.asarray(data.free_surface_potential, dtype=complex)
                row_block_rhs = np.zeros(total_rows, dtype=complex)
                row_block_rhs[row_slice] = -a_free @ free_phi
                row_block_norm = float(np.linalg.norm(row_block_rhs))
                row_block_to_total_ratio = _safe_norm_ratio(row_block_rhs, source_rhs)
                row_block_to_total_alignment = _complex_vector_real_alignment(source_rhs, row_block_rhs)
                row_block_to_total_phase = _complex_vector_phase_deg(source_rhs, row_block_rhs)
                for panel_index in range(free.panel_count):
                    panel_vector = np.zeros(total_rows, dtype=complex)
                    panel_vector[row_slice] = -a_free[:, panel_index] * free_phi[panel_index]
                    panel_norm = float(np.linalg.norm(panel_vector))
                    potential_value = complex(free_phi[panel_index])
                    rows.append(
                        A1InnerFreeSurfaceRhsBlockAudit(
                            mode_name=mode,
                            station_local_index=int(local_index),
                            active_station_index=int(sweep.active_station_indices[local_index]),
                            solve_order_rank=int(rank),
                            row_block_name=str(row_block_name),
                            row_block_size=int(field_geometry.panel_count),
                            free_surface_panel_index=int(panel_index),
                            free_surface_panel_y_m=float(free.mid_y_m[panel_index]),
                            free_surface_panel_length_m=float(free.length_m[panel_index]),
                            free_surface_potential_abs=float(abs(potential_value)),
                            free_surface_potential_phase_deg=float(np.rad2deg(np.angle(potential_value))),
                            matrix_column_norm=float(np.linalg.norm(a_free[:, panel_index])),
                            row_block_contribution_norm=panel_norm,
                            row_block_free_rhs_norm=row_block_norm,
                            total_free_rhs_norm=total_free_rhs_norm,
                            row_block_to_total_free_rhs_norm_ratio=row_block_to_total_ratio,
                            panel_to_row_block_free_rhs_norm_ratio=_safe_norm_ratio(panel_vector, row_block_rhs),
                            panel_to_total_free_rhs_norm_ratio=_safe_norm_ratio(panel_vector, source_rhs),
                            panel_to_row_block_real_alignment=_complex_vector_real_alignment(
                                row_block_rhs,
                                panel_vector,
                            ),
                            panel_to_row_block_phase_deg=_complex_vector_phase_deg(row_block_rhs, panel_vector),
                            row_block_to_total_real_alignment=row_block_to_total_alignment,
                            row_block_to_total_phase_deg=row_block_to_total_phase,
                            gate_role="diagnostic_inner_free_surface_rhs_block_not_hard_gate",
                            validity=validity,
                        )
                    )
                row_start = row_slice.stop
        past_phi, past_phi_n = _prepend_control_history(past_phi, past_phi_n, solutions[local_index])
    return tuple(rows)


def recover_body_pressure_from_matched_solution(
    body: InnerDomainPanelGeometry,
    solution: MatchedSectionSolution,
    omega_rad_s: float,
    *,
    rho_water_kg_m3: float = 1025.0,
    forward_speed_mps: float = 0.0,
    body_potential_x_gradient: np.ndarray | None = None,
    pressure_gradient_scale: float = 1.0,
) -> MatchedSectionPressureResult:
    """Recover body-panel pressure from A1 Eq. (30)."""

    omega = float(omega_rad_s)
    if omega <= 0.0:
        raise ValueError("omega_rad_s must be positive.")
    if forward_speed_mps < 0.0:
        raise ValueError("forward_speed_mps must be non-negative.")
    gradient_scale = float(pressure_gradient_scale)
    if not np.isfinite(gradient_scale):
        raise ValueError("pressure_gradient_scale must be finite.")
    phi = np.asarray(solution.body_potential, dtype=complex)
    if phi.shape != (body.panel_count,):
        raise ValueError(f"solution.body_potential must have shape ({body.panel_count},), got {phi.shape}.")
    gradient = np.zeros_like(phi) if body_potential_x_gradient is None else np.asarray(
        body_potential_x_gradient, dtype=complex
    )
    if gradient.shape != phi.shape:
        raise ValueError(f"body_potential_x_gradient must have shape {phi.shape}, got {gradient.shape}.")
    pressure_time = -float(rho_water_kg_m3) * 1j * omega * phi
    pressure_forward = float(rho_water_kg_m3) * float(forward_speed_mps) * gradient_scale * gradient
    pressure = pressure_time + pressure_forward
    notes = ["A1 Eq. (30) pressure recovery from matched body potential."]
    if body_potential_x_gradient is None or abs(float(forward_speed_mps) * gradient_scale) <= 1e-12:
        notes.append("Forward-speed x-gradient contribution was not supplied or speed is zero.")
    return MatchedSectionPressureResult(
        panel_mid_y_m=body.mid_y_m,
        panel_mid_z_down_m=body.mid_z_down_m,
        panel_length_m=body.length_m,
        panel_normal_y=body.normal_y,
        panel_normal_z=body.normal_z,
        body_potential=phi,
        body_potential_x_gradient=gradient,
        pressure_pa=pressure,
        pressure_time_derivative_pa=pressure_time,
        pressure_forward_speed_pa=pressure_forward,
        omega_rad_s=omega,
        forward_speed_mps=float(forward_speed_mps),
        rho_water_kg_m3=float(rho_water_kg_m3),
        validity=ValidityReport(
            status=LINEAR_2P5D_PRESSURE_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=tuple(notes),
        ),
    )


def _integrate_pressure_heave_pitch(
    pressure_pa: np.ndarray,
    panel_normal_z: np.ndarray,
    panel_length_m: np.ndarray,
    lever_arm_m: float,
) -> tuple[complex, complex]:
    pressure = np.asarray(pressure_pa, dtype=complex)
    normal_z = np.asarray(panel_normal_z, dtype=float)
    length = np.asarray(panel_length_m, dtype=float)
    if pressure.shape != normal_z.shape or pressure.shape != length.shape:
        raise ValueError("pressure, panel_normal_z, and panel_length_m must have matching shapes.")
    heave_row, pitch_row = DEFAULT_A1_HEAVE_PITCH_CONVENTION.pressure_generalized_rows(
        normal_z,
        length,
        lever_arm_m=lever_arm_m,
    )
    force_up_panel = pressure * heave_row
    heave_force = complex(np.sum(force_up_panel))
    return heave_force, complex(np.sum(pressure * pitch_row))


def pressure_force_to_added_mass_damping(force: complex, omega_rad_s: float) -> tuple[float, float]:
    """Convert A1 Eq. (33) complex force into added mass and damping."""

    omega = float(omega_rad_s)
    if omega <= 0.0:
        raise ValueError("omega_rad_s must be positive.")
    value = complex(force)
    return float(np.real(value) / omega**2), float(-np.imag(value) / omega)


def integrate_section_heave_pitch_force(
    pressure: MatchedSectionPressureResult,
    *,
    lever_arm_m: float = 0.0,
) -> MatchedSectionForceResult:
    """Integrate body pressure into sectional heave force and pitch moment."""

    heave_force, pitch_moment = _integrate_pressure_heave_pitch(
        pressure.pressure_pa,
        pressure.panel_normal_z,
        pressure.panel_length_m,
        lever_arm_m,
    )
    heave_time, pitch_time = _integrate_pressure_heave_pitch(
        pressure.pressure_time_derivative_pa,
        pressure.panel_normal_z,
        pressure.panel_length_m,
        lever_arm_m,
    )
    heave_forward, pitch_forward = _integrate_pressure_heave_pitch(
        pressure.pressure_forward_speed_pa,
        pressure.panel_normal_z,
        pressure.panel_length_m,
        lever_arm_m,
    )
    added, damping = pressure_force_to_added_mass_damping(heave_force, pressure.omega_rad_s)
    pitch_added, pitch_damping = pressure_force_to_added_mass_damping(pitch_moment, pressure.omega_rad_s)
    return MatchedSectionForceResult(
        heave_force_per_m=heave_force,
        pitch_moment_per_m=pitch_moment,
        added_mass_per_m=added,
        damping_per_m=damping,
        pitch_added_mass_per_m2=pitch_added,
        pitch_damping_per_m2=pitch_damping,
        omega_rad_s=pressure.omega_rad_s,
        lever_arm_m=float(lever_arm_m),
        validity=ValidityReport(
            status=LINEAR_2P5D_SECTION_FORCE_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "Pressure integral over one section. Whole-ship forward-speed gradient and end-term assembly remain pending.",
            ),
        ),
        heave_force_time_derivative_per_m=heave_time,
        heave_force_forward_speed_per_m=heave_forward,
        pitch_moment_time_derivative_per_m=pitch_time,
        pitch_moment_forward_speed_per_m=pitch_forward,
    )


def estimate_body_potential_x_gradient(
    x_m: np.ndarray,
    body_potential_by_station: np.ndarray,
    *,
    scheme: str = "central",
) -> StationPotentialGradient:
    """Estimate `partial phi / partial x` for A1 Eq. (30) from station potentials."""

    x = np.asarray(x_m, dtype=float)
    phi = np.asarray(body_potential_by_station, dtype=complex)
    gradient_scheme = str(scheme).strip().lower()
    if gradient_scheme not in {"central", "forward", "backward"}:
        raise ValueError("scheme must be 'central', 'forward', or 'backward'.")
    if x.ndim != 1:
        raise ValueError("x_m must be one-dimensional.")
    if phi.ndim != 2 or phi.shape[0] != x.size:
        raise ValueError("body_potential_by_station must have shape (n_station, n_panel).")
    if x.size < 2:
        raise ValueError("At least two stations are required to estimate an x-gradient.")
    if np.any(np.diff(x) <= 0.0):
        raise ValueError("x_m must be strictly increasing.")
    if gradient_scheme == "central":
        edge_order = 2 if x.size >= 3 else 1
        gradient = np.gradient(phi, x, axis=0, edge_order=edge_order)
    else:
        gradient = np.zeros_like(phi, dtype=complex)
        if gradient_scheme == "forward":
            gradient[:-1] = (phi[1:] - phi[:-1]) / (x[1:] - x[:-1])[:, None]
            gradient[-1] = gradient[-2]
        else:
            gradient[1:] = (phi[1:] - phi[:-1]) / (x[1:] - x[:-1])[:, None]
            gradient[0] = gradient[1]
    return StationPotentialGradient(
        x_m=x,
        body_potential_x_gradient=np.asarray(gradient, dtype=complex),
        scheme=gradient_scheme,
        validity=ValidityReport(
            status=LINEAR_2P5D_STATION_GRADIENT_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "Station-wise finite-difference gradient for A1 Eq. (30); "
                f"scheme={gradient_scheme}; Stokes end-term form remains preferred.",
            ),
        ),
    )


def estimate_local_time_phase_body_potential_x_gradient(
    x_m: np.ndarray,
    phase_domain_body_potential_by_station: np.ndarray,
    *,
    omega_rad_s: float,
    speed_mps: float,
    phase_factor: np.ndarray,
    scheme: str = "central",
) -> StationPotentialGradient:
    """Recover `partial phi / partial x` from A1 Eq. (8) phase-domain `psi`.

    A1 defines `psi = phi exp(i omega t)` and `t = (x0 - x) / U`.
    Therefore `phi = psi exp(-i omega t)` and, at fixed transverse point,
    `phi_x = exp(-i omega t) * (psi_x + i omega psi / U)`.
    """

    x = np.asarray(x_m, dtype=float)
    psi = np.asarray(phase_domain_body_potential_by_station, dtype=complex)
    phase = np.asarray(phase_factor, dtype=complex)
    omega = float(omega_rad_s)
    speed = float(speed_mps)
    if omega <= 0.0:
        raise ValueError("omega_rad_s must be positive.")
    if speed <= 0.0:
        raise ValueError("speed_mps must be positive.")
    if phase.shape != (x.size,):
        raise ValueError(f"phase_factor must have shape ({x.size},), got {phase.shape}.")
    if psi.ndim != 2 or psi.shape[0] != x.size:
        raise ValueError("phase_domain_body_potential_by_station must have shape (n_station, n_panel).")
    psi_gradient = estimate_body_potential_x_gradient(x, psi, scheme=scheme).body_potential_x_gradient
    dephase = np.conjugate(phase)[:, None]
    phi_gradient = dephase * (psi_gradient + 1j * omega * psi / speed)
    return StationPotentialGradient(
        x_m=x,
        body_potential_x_gradient=np.asarray(phi_gradient, dtype=complex),
        scheme=f"{str(scheme).strip().lower()}_local_time_phase_chain_rule",
        validity=ValidityReport(
            status=LINEAR_2P5D_STATION_GRADIENT_STATUS,
            reference_cases=("ma2005_wigley_iii", "a1_eq8_eq30"),
            notes=(
                "Diagnostic A1 Eq. (8) chain-rule x-gradient for a local-time phase-domain matched sweep. "
                "It is used only when the caller explicitly enables local_time_phase_gradient_correction.",
            ),
        ),
    )


def _interp_complex_1d(source_coordinate: np.ndarray, source_values: np.ndarray, target_coordinate: np.ndarray) -> np.ndarray:
    """Linearly interpolate complex values on a one-dimensional body-coordinate trace."""

    source = np.asarray(source_coordinate, dtype=float)
    values = np.asarray(source_values, dtype=complex)
    target = np.asarray(target_coordinate, dtype=float)
    if source.ndim != 1 or values.ndim != 1 or source.shape != values.shape:
        raise ValueError("source_coordinate and source_values must be one-dimensional arrays with matching shape.")
    if target.ndim != 1:
        raise ValueError("target_coordinate must be one-dimensional.")
    finite = np.isfinite(source) & np.isfinite(values.real) & np.isfinite(values.imag)
    if finite.sum() < 2:
        return np.full(target.shape, np.nan + 1j * np.nan, dtype=complex)
    ordered = np.argsort(source[finite], kind="mergesort")
    sorted_coordinate = source[finite][ordered]
    sorted_values = values[finite][ordered]
    unique_coordinate, inverse = np.unique(sorted_coordinate, return_inverse=True)
    if unique_coordinate.size < 2:
        return np.full(target.shape, np.nan + 1j * np.nan, dtype=complex)
    real_sum = np.zeros(unique_coordinate.size, dtype=float)
    imag_sum = np.zeros(unique_coordinate.size, dtype=float)
    counts = np.zeros(unique_coordinate.size, dtype=float)
    np.add.at(real_sum, inverse, sorted_values.real)
    np.add.at(imag_sum, inverse, sorted_values.imag)
    np.add.at(counts, inverse, 1.0)
    averaged = real_sum / counts + 1j * imag_sum / counts
    real = np.interp(target, unique_coordinate, averaged.real)
    imag = np.interp(target, unique_coordinate, averaged.imag)
    return real + 1j * imag


def estimate_mapped_body_potential_x_gradient(
    x_m: np.ndarray,
    bodies: tuple[InnerDomainPanelGeometry, ...],
    body_potential_by_station: np.ndarray,
    *,
    scheme: str = "central",
    mapping: str = "fixed_y",
) -> StationPotentialGradient:
    """Estimate ``partial phi / partial x`` after mapping adjacent stations onto a common body coordinate.

    The default production path differentiates equal panel indices.  This
    diagnostic alternative first interpolates the adjacent station potential to
    the target station's body coordinate.  It is intended for Ma 2005 Gate 1
    triage of varying sections; it does not replace the production gradient.
    """

    x = np.asarray(x_m, dtype=float)
    phi = np.asarray(body_potential_by_station, dtype=complex)
    gradient_scheme = str(scheme).strip().lower()
    mapping_kind = str(mapping).strip().lower()
    if gradient_scheme not in {"central", "forward", "backward"}:
        raise ValueError("scheme must be 'central', 'forward', or 'backward'.")
    if mapping_kind not in {"fixed_y", "normalized_y"}:
        raise ValueError("mapping must be 'fixed_y' or 'normalized_y'.")
    if x.ndim != 1:
        raise ValueError("x_m must be one-dimensional.")
    if len(bodies) != x.size:
        raise ValueError("bodies must match x_m length.")
    if phi.ndim != 2 or phi.shape[0] != x.size:
        raise ValueError("body_potential_by_station must have shape (n_station, n_panel).")
    if x.size < 2:
        raise ValueError("At least two stations are required to estimate an x-gradient.")
    if np.any(np.diff(x) <= 0.0):
        raise ValueError("x_m must be strictly increasing.")
    panel_count = phi.shape[1]
    for index, body in enumerate(bodies):
        if body.panel_count != panel_count:
            raise ValueError(
                "All station bodies must use the same panel count for mapped x-gradient estimation; "
                f"station {index} has {body.panel_count}, expected {panel_count}."
            )

    def coordinate(index: int) -> np.ndarray:
        body = bodies[index]
        y = np.asarray(body.mid_y_m, dtype=float)
        if mapping_kind == "fixed_y":
            return y
        half_beam = float(np.max(np.abs(np.asarray(body.node_y_m, dtype=float))))
        if half_beam <= 1e-12:
            half_beam = max(float(np.max(np.abs(y))), 1e-12)
        return y / half_beam

    coordinates = tuple(coordinate(index) for index in range(x.size))

    def mapped_phi(source_index: int, target_index: int) -> np.ndarray:
        if source_index == target_index:
            return np.asarray(phi[source_index], dtype=complex)
        return _interp_complex_1d(coordinates[source_index], phi[source_index], coordinates[target_index])

    gradient = np.zeros_like(phi, dtype=complex)
    if gradient_scheme == "forward":
        for index in range(x.size - 1):
            gradient[index] = (mapped_phi(index + 1, index) - phi[index]) / (x[index + 1] - x[index])
        gradient[-1] = gradient[-2]
    elif gradient_scheme == "backward":
        for index in range(1, x.size):
            gradient[index] = (phi[index] - mapped_phi(index - 1, index)) / (x[index] - x[index - 1])
        gradient[0] = gradient[1]
    else:
        gradient[0] = (mapped_phi(1, 0) - phi[0]) / (x[1] - x[0])
        gradient[-1] = (phi[-1] - mapped_phi(x.size - 2, x.size - 1)) / (x[-1] - x[-2])
        for index in range(1, x.size - 1):
            gradient[index] = (mapped_phi(index + 1, index) - mapped_phi(index - 1, index)) / (
                x[index + 1] - x[index - 1]
            )

    return StationPotentialGradient(
        x_m=x,
        body_potential_x_gradient=np.asarray(gradient, dtype=complex),
        scheme=f"mapped_{mapping_kind}_{gradient_scheme}",
        validity=ValidityReport(
            status=LINEAR_2P5D_STATION_GRADIENT_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "Diagnostic station-mapped body-potential x-gradient for A1 Eq. (30). "
                f"mapping={mapping_kind}; scheme={gradient_scheme}; production default remains index-based.",
            ),
        ),
    )


def _force_matrix_from_section_results(
    forces: tuple[MatchedSectionForceResult, ...],
) -> np.ndarray:
    return np.column_stack(
        [
            np.asarray([force.heave_force_per_m for force in forces], dtype=complex),
            np.asarray([force.pitch_moment_per_m for force in forces], dtype=complex),
        ]
    )


def _component_force_matrix_from_section_results(
    forces: tuple[MatchedSectionForceResult, ...],
    *,
    heave_attr: str,
    pitch_attr: str,
) -> np.ndarray:
    return np.column_stack(
        [
            np.asarray([getattr(force, heave_attr) for force in forces], dtype=complex),
            np.asarray([getattr(force, pitch_attr) for force in forces], dtype=complex),
        ]
    )


def _force_density_matrix_from_section_results(
    heave_mode_forces: tuple[MatchedSectionForceResult, ...],
    pitch_mode_forces: tuple[MatchedSectionForceResult, ...],
    *,
    heave_attr: str,
    pitch_attr: str,
) -> np.ndarray:
    heave_density = _component_force_matrix_from_section_results(
        heave_mode_forces,
        heave_attr=heave_attr,
        pitch_attr=pitch_attr,
    )
    pitch_density = _component_force_matrix_from_section_results(
        pitch_mode_forces,
        heave_attr=heave_attr,
        pitch_attr=pitch_attr,
    )
    density = np.zeros((len(heave_mode_forces), 2, 2), dtype=complex)
    density[:, :, 0] = heave_density
    density[:, :, 1] = pitch_density
    return density


def _force_density_peak_diagnostics(
    x_m: np.ndarray,
    density_by_station: np.ndarray,
    *,
    hull_length_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(x_m, dtype=float)
    density = np.asarray(density_by_station, dtype=complex)
    if x.ndim != 1 or density.ndim != 3 or density.shape[0] != x.size:
        raise ValueError("density_by_station must have shape (n_station, 2, 2) matching x_m.")
    if density.shape[1:] != (2, 2):
        raise ValueError(f"density_by_station trailing shape must be (2, 2), got {density.shape[1:]}.")
    length = max(float(hull_length_m), 1e-30)
    abs_density = np.abs(density)
    peak_indices = np.argmax(abs_density, axis=0)
    peak_abs = np.take_along_axis(abs_density, peak_indices[None, :, :], axis=0)[0]
    x_over_l = x / length
    peak_x_over_l = np.take_along_axis(x_over_l[:, None, None], peak_indices[None, :, :], axis=0)[0]
    integral_abs = np.trapezoid(abs_density, x, axis=0)
    peak_to_integral = np.full((2, 2), np.nan, dtype=float)
    centroid_x_over_l = np.full((2, 2), np.nan, dtype=float)
    mask = np.isfinite(integral_abs) & (integral_abs > 1e-30)
    peak_to_integral[mask] = peak_abs[mask] * length / integral_abs[mask]
    weighted_x = np.trapezoid(abs_density * x[:, None, None], x, axis=0)
    centroid_x_over_l[mask] = weighted_x[mask] / integral_abs[mask] / length
    return (
        np.asarray(peak_x_over_l, dtype=float),
        np.asarray(peak_abs, dtype=float),
        np.asarray(peak_to_integral, dtype=float),
        np.asarray(centroid_x_over_l, dtype=float),
    )


def _integrate_force_density_station_subset(
    x_m: np.ndarray,
    density_by_station: np.ndarray,
    *,
    start_index: int = 0,
    stop_index: int | None = None,
) -> np.ndarray:
    x = np.asarray(x_m, dtype=float)
    density = np.asarray(density_by_station, dtype=complex)
    if x.ndim != 1 or density.ndim != 3 or density.shape[0] != x.size or density.shape[1:] != (2, 2):
        raise ValueError("density_by_station must have shape (n_station, 2, 2) matching x_m.")
    start = max(0, int(start_index))
    stop = density.shape[0] if stop_index is None else min(density.shape[0], int(stop_index))
    if stop - start < 2:
        return np.zeros((2, 2), dtype=complex)
    return np.asarray(np.trapezoid(density[start:stop], x[start:stop], axis=0), dtype=complex)


def _forward_speed_force_density_for_body_potential_gradient(
    x_m: np.ndarray,
    bodies: tuple[InnerDomainPanelGeometry, ...],
    heave_mode_solutions: tuple[MatchedSectionSolution, ...],
    pitch_mode_solutions: tuple[MatchedSectionSolution, ...],
    heave_gradient: StationPotentialGradient,
    pitch_gradient: StationPotentialGradient,
    *,
    omega_rad_s: float,
    rho_water_kg_m3: float,
    forward_speed_mps: float,
    lever_arms_m: np.ndarray,
    pressure_gradient_scale: float = 1.0,
) -> np.ndarray:
    """Return forward-speed generalized force density for a diagnostic x-gradient candidate."""

    x = np.asarray(x_m, dtype=float)
    levers = np.asarray(lever_arms_m, dtype=float)
    heave_grad = np.asarray(heave_gradient.body_potential_x_gradient, dtype=complex)
    pitch_grad = np.asarray(pitch_gradient.body_potential_x_gradient, dtype=complex)
    if heave_grad.shape[0] != x.size or pitch_grad.shape[0] != x.size or levers.shape != (x.size,):
        raise ValueError("gradient and lever-arm arrays must match station count.")
    heave_forces = tuple(
        integrate_section_heave_pitch_force(
            recover_body_pressure_from_matched_solution(
                bodies[index],
                heave_mode_solutions[index],
                omega_rad_s,
                rho_water_kg_m3=rho_water_kg_m3,
                forward_speed_mps=forward_speed_mps,
                body_potential_x_gradient=heave_grad[index],
                pressure_gradient_scale=pressure_gradient_scale,
            ),
            lever_arm_m=float(levers[index]),
        )
        for index in range(x.size)
    )
    pitch_forces = tuple(
        integrate_section_heave_pitch_force(
            recover_body_pressure_from_matched_solution(
                bodies[index],
                pitch_mode_solutions[index],
                omega_rad_s,
                rho_water_kg_m3=rho_water_kg_m3,
                forward_speed_mps=forward_speed_mps,
                body_potential_x_gradient=pitch_grad[index],
                pressure_gradient_scale=pressure_gradient_scale,
            ),
            lever_arm_m=float(levers[index]),
        )
        for index in range(x.size)
    )
    return _force_density_matrix_from_section_results(
        heave_forces,
        pitch_forces,
        heave_attr="heave_force_forward_speed_per_m",
        pitch_attr="pitch_moment_forward_speed_per_m",
    )


def _forward_speed_force_matrix_for_body_potential_gradient(
    x_m: np.ndarray,
    bodies: tuple[InnerDomainPanelGeometry, ...],
    heave_mode_solutions: tuple[MatchedSectionSolution, ...],
    pitch_mode_solutions: tuple[MatchedSectionSolution, ...],
    heave_gradient: StationPotentialGradient,
    pitch_gradient: StationPotentialGradient,
    *,
    omega_rad_s: float,
    rho_water_kg_m3: float,
    forward_speed_mps: float,
    lever_arms_m: np.ndarray,
    pressure_gradient_scale: float = 1.0,
) -> np.ndarray:
    density = _forward_speed_force_density_for_body_potential_gradient(
        x_m,
        bodies,
        heave_mode_solutions,
        pitch_mode_solutions,
        heave_gradient,
        pitch_gradient,
        omega_rad_s=omega_rad_s,
        rho_water_kg_m3=rho_water_kg_m3,
        forward_speed_mps=forward_speed_mps,
        lever_arms_m=lever_arms_m,
        pressure_gradient_scale=pressure_gradient_scale,
    )
    return np.asarray(np.trapezoid(density, np.asarray(x_m, dtype=float), axis=0), dtype=complex)


def assemble_whole_ship_heave_pitch_coefficients(
    x_m: np.ndarray,
    heave_mode_forces: tuple[MatchedSectionForceResult, ...],
    pitch_mode_forces: tuple[MatchedSectionForceResult, ...],
    *,
    omega_rad_s: float,
    end_term_force_matrix: np.ndarray | None = None,
    stokes_body_forward_speed_force_matrix: np.ndarray | None = None,
    row_measure_transport_force_matrix: np.ndarray | None = None,
    force_assembly_route: str = "eq32_stokes_body_plus_end",
) -> WholeShipHeavePitchAssembly:
    """Assemble A1 Eq. (33) whole-ship heave/pitch coefficients from section forces."""

    x = np.asarray(x_m, dtype=float)
    omega = float(omega_rad_s)
    if omega <= 0.0:
        raise ValueError("omega_rad_s must be positive.")
    if x.ndim != 1 or x.size < 2:
        raise ValueError("x_m must be one-dimensional with at least two stations.")
    if np.any(np.diff(x) <= 0.0):
        raise ValueError("x_m must be strictly increasing.")
    if len(heave_mode_forces) != x.size or len(pitch_mode_forces) != x.size:
        raise ValueError("heave_mode_forces and pitch_mode_forces must match x_m length.")

    heave_density = _force_matrix_from_section_results(tuple(heave_mode_forces))
    pitch_density = _force_matrix_from_section_results(tuple(pitch_mode_forces))
    heave_time_density = _component_force_matrix_from_section_results(
        tuple(heave_mode_forces),
        heave_attr="heave_force_time_derivative_per_m",
        pitch_attr="pitch_moment_time_derivative_per_m",
    )
    pitch_time_density = _component_force_matrix_from_section_results(
        tuple(pitch_mode_forces),
        heave_attr="heave_force_time_derivative_per_m",
        pitch_attr="pitch_moment_time_derivative_per_m",
    )
    heave_forward_density = _component_force_matrix_from_section_results(
        tuple(heave_mode_forces),
        heave_attr="heave_force_forward_speed_per_m",
        pitch_attr="pitch_moment_forward_speed_per_m",
    )
    pitch_forward_density = _component_force_matrix_from_section_results(
        tuple(pitch_mode_forces),
        heave_attr="heave_force_forward_speed_per_m",
        pitch_attr="pitch_moment_forward_speed_per_m",
    )
    force_matrix = np.zeros((2, 2), dtype=complex)
    force_matrix[:, 0] = np.trapezoid(heave_density, x, axis=0)
    force_matrix[:, 1] = np.trapezoid(pitch_density, x, axis=0)
    time_matrix = np.zeros((2, 2), dtype=complex)
    time_matrix[:, 0] = np.trapezoid(heave_time_density, x, axis=0)
    time_matrix[:, 1] = np.trapezoid(pitch_time_density, x, axis=0)
    forward_matrix = np.zeros((2, 2), dtype=complex)
    forward_matrix[:, 0] = np.trapezoid(heave_forward_density, x, axis=0)
    forward_matrix[:, 1] = np.trapezoid(pitch_forward_density, x, axis=0)
    stokes_body_forward = (
        np.zeros((2, 2), dtype=complex)
        if stokes_body_forward_speed_force_matrix is None
        else np.asarray(stokes_body_forward_speed_force_matrix, dtype=complex)
    )
    if stokes_body_forward.shape != (2, 2):
        raise ValueError(
            "stokes_body_forward_speed_force_matrix must have shape (2, 2), "
            f"got {stokes_body_forward.shape}."
        )
    row_measure_transport = (
        np.zeros((2, 2), dtype=complex)
        if row_measure_transport_force_matrix is None
        else np.asarray(row_measure_transport_force_matrix, dtype=complex)
    )
    if row_measure_transport.shape != (2, 2):
        raise ValueError(
            "row_measure_transport_force_matrix must have shape (2, 2), "
            f"got {row_measure_transport.shape}."
        )
    end_terms = np.zeros((2, 2), dtype=complex) if end_term_force_matrix is None else np.asarray(
        end_term_force_matrix, dtype=complex
    )
    if end_terms.shape != (2, 2):
        raise ValueError(f"end_term_force_matrix must have shape (2, 2), got {end_terms.shape}.")
    route = str(force_assembly_route).strip().lower()
    route_aliases = {
        "current": "current_hybrid_pressure_gradient_plus_end",
        "current_hybrid": "current_hybrid_pressure_gradient_plus_end",
        "hybrid_pressure_gradient_plus_end": "current_hybrid_pressure_gradient_plus_end",
        "current_hybrid_pressure_gradient_plus_end": "current_hybrid_pressure_gradient_plus_end",
        "eq31": "eq31_pressure_gradient_only",
        "eq31_pressure": "eq31_pressure_gradient_only",
        "eq31_pressure_gradient_only": "eq31_pressure_gradient_only",
        "eq32": "eq32_stokes_body_plus_end",
        "eq32_stokes": "eq32_stokes_body_plus_end",
        "eq32_stokes_body_plus_end": "eq32_stokes_body_plus_end",
        "eq32_stokes_body_only": "eq32_stokes_body_only",
        "eq31_pressure_gradient_plus_row_measure_transport": (
            "eq31_pressure_gradient_plus_row_measure_transport"
        ),
        "eq31_plus_row_measure_transport": "eq31_pressure_gradient_plus_row_measure_transport",
        "eq31_pressure_gradient_minus_row_measure_transport": (
            "eq31_pressure_gradient_minus_row_measure_transport"
        ),
        "eq31_minus_row_measure_transport": "eq31_pressure_gradient_minus_row_measure_transport",
        "eq31_pressure_gradient_plus_row_measure_transport_plus_end": (
            "eq31_pressure_gradient_plus_row_measure_transport_plus_end"
        ),
        "eq31_plus_row_measure_transport_plus_end": (
            "eq31_pressure_gradient_plus_row_measure_transport_plus_end"
        ),
        "eq31_pressure_gradient_minus_row_measure_transport_plus_end": (
            "eq31_pressure_gradient_minus_row_measure_transport_plus_end"
        ),
        "eq31_minus_row_measure_transport_plus_end": (
            "eq31_pressure_gradient_minus_row_measure_transport_plus_end"
        ),
        "all_terms": "all_terms_pressure_gradient_stokes_end",
        "all_terms_pressure_gradient_stokes_end": "all_terms_pressure_gradient_stokes_end",
    }
    if route not in route_aliases:
        raise ValueError(
            "force_assembly_route must be one of current_hybrid_pressure_gradient_plus_end, "
            "eq31_pressure_gradient_only, eq32_stokes_body_plus_end, eq32_stokes_body_only, "
            "eq31_pressure_gradient_plus_row_measure_transport, "
            "eq31_pressure_gradient_minus_row_measure_transport, "
            "eq31_pressure_gradient_plus_row_measure_transport_plus_end, "
            "eq31_pressure_gradient_minus_row_measure_transport_plus_end, or all_terms_pressure_gradient_stokes_end."
        )
    route = route_aliases[route]
    if route == "current_hybrid_pressure_gradient_plus_end":
        force_matrix = time_matrix + forward_matrix + end_terms
    elif route == "eq31_pressure_gradient_only":
        force_matrix = time_matrix + forward_matrix
    elif route == "eq32_stokes_body_plus_end":
        force_matrix = time_matrix + stokes_body_forward + end_terms
    elif route == "eq32_stokes_body_only":
        force_matrix = time_matrix + stokes_body_forward
    elif route == "eq31_pressure_gradient_plus_row_measure_transport":
        force_matrix = time_matrix + forward_matrix + row_measure_transport
    elif route == "eq31_pressure_gradient_minus_row_measure_transport":
        force_matrix = time_matrix + forward_matrix - row_measure_transport
    elif route == "eq31_pressure_gradient_plus_row_measure_transport_plus_end":
        force_matrix = time_matrix + forward_matrix + row_measure_transport + end_terms
    elif route == "eq31_pressure_gradient_minus_row_measure_transport_plus_end":
        force_matrix = time_matrix + forward_matrix - row_measure_transport + end_terms
    else:
        force_matrix = time_matrix + forward_matrix + stokes_body_forward + end_terms
    added = np.real(force_matrix) / omega**2
    damping = -np.imag(force_matrix) / omega
    notes = [
        "Whole-ship heave/pitch coefficient assembly from pressure-integrated sectional generalized forces.",
    ]
    if end_term_force_matrix is None:
        notes.append("A1 Eq. (32) end-term force matrix was not supplied.")
    if stokes_body_forward_speed_force_matrix is None:
        notes.append("A1 Eq. (32) body forward-speed force matrix was stored as zero diagnostic.")
    if row_measure_transport_force_matrix is None:
        notes.append("A1 Eq. (31) product-rule row-measure transport matrix was stored as zero diagnostic.")
    notes.append(f"Forward-speed assembly route: {route}.")
    return WholeShipHeavePitchAssembly(
        x_m=x,
        complex_force_matrix=force_matrix,
        added_mass=np.asarray(added, dtype=float),
        damping=np.asarray(damping, dtype=float),
        end_term_force_matrix=end_terms,
        time_derivative_force_matrix=time_matrix,
        forward_speed_force_matrix=forward_matrix,
        stokes_body_forward_speed_force_matrix=stokes_body_forward,
        force_assembly_route=route,
        omega_rad_s=omega,
        row_labels=("heave_force", "pitch_moment"),
        column_labels=("heave_radiation", "pitch_radiation"),
        validity=ValidityReport(
            status=LINEAR_2P5D_WHOLE_SHIP_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=tuple(notes),
        ),
    )


def compute_heave_pitch_stokes_end_term_force_matrix(
    end_body: InnerDomainPanelGeometry,
    heave_mode_solution: MatchedSectionSolution,
    pitch_mode_solution: MatchedSectionSolution,
    *,
    rho_water_kg_m3: float = 1025.0,
    forward_speed_mps: float,
    lever_arm_m: float = 0.0,
) -> StokesEndTermForceMatrix:
    """Compute the heave/pitch C_A contour term in A1 Eq. (32).

    The helper follows the package's current sign convention: heave force is
    positive upward and pitch moment is the heave generalized force multiplied
    by `lever_arm_m`. The physical station selected as C_A must be supplied by
    the caller, normally the aft end of the active wet length.
    """

    speed = float(forward_speed_mps)
    if speed < 0.0:
        raise ValueError("forward_speed_mps must be non-negative.")
    heave_phi = np.asarray(heave_mode_solution.body_potential, dtype=complex)
    pitch_phi = np.asarray(pitch_mode_solution.body_potential, dtype=complex)
    if heave_phi.shape != (end_body.panel_count,):
        raise ValueError(f"heave_mode_solution.body_potential must have shape ({end_body.panel_count},).")
    if pitch_phi.shape != (end_body.panel_count,):
        raise ValueError(f"pitch_mode_solution.body_potential must have shape ({end_body.panel_count},).")
    generalized_heave, generalized_pitch = DEFAULT_A1_HEAVE_PITCH_CONVENTION.end_contour_n_rows(
        end_body,
        lever_arm_m=lever_arm_m,
    )
    end_columns = np.array(
        [
            [
                np.sum(heave_phi * generalized_heave),
                np.sum(pitch_phi * generalized_heave),
            ],
            [
                np.sum(heave_phi * generalized_pitch),
                np.sum(pitch_phi * generalized_pitch),
            ],
        ],
        dtype=complex,
    )
    force_matrix = -float(rho_water_kg_m3) * speed * end_columns
    return StokesEndTermForceMatrix(
        complex_force_matrix=force_matrix,
        forward_speed_mps=speed,
        rho_water_kg_m3=float(rho_water_kg_m3),
        lever_arm_m=float(lever_arm_m),
        row_labels=("heave_force", "pitch_moment"),
        column_labels=("heave_radiation", "pitch_radiation"),
        validity=ValidityReport(
            status=LINEAR_2P5D_STOKES_END_TERM_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "A1 Eq. (32) C_A contour helper using the package heave-positive-up and pitch-lever convention. "
                "The correct physical end station, orientation, and benchmark sign must still be checked against Wigley III.",
            ),
        ),
    )


def compute_heave_pitch_control_surface_end_term_force_matrix(
    control_surface: InnerDomainPanelGeometry,
    heave_mode_solution: MatchedSectionSolution,
    pitch_mode_solution: MatchedSectionSolution,
    *,
    rho_water_kg_m3: float = 1025.0,
    forward_speed_mps: float,
    lever_arm_m: float = 0.0,
) -> StokesEndTermForceMatrix:
    """Diagnostic A1 Eq. (32) C_A term evaluated on the fixed control surface.

    The current production end term uses the wet body end contour. A1's matched
    formulation also introduces a fixed half-cylinder control surface S_C. This
    helper probes whether the end allocation should use the stored control
    potential on that fixed surface. It is diagnostic-only and must not be
    promoted to the default force path without passing the Ma 2005 gate.
    """

    speed = float(forward_speed_mps)
    if speed < 0.0:
        raise ValueError("forward_speed_mps must be non-negative.")
    heave_phi = np.asarray(heave_mode_solution.control_potential, dtype=complex)
    pitch_phi = np.asarray(pitch_mode_solution.control_potential, dtype=complex)
    if heave_phi.shape != (control_surface.panel_count,):
        raise ValueError(
            "heave_mode_solution.control_potential must have shape "
            f"({control_surface.panel_count},)."
        )
    if pitch_phi.shape != (control_surface.panel_count,):
        raise ValueError(
            "pitch_mode_solution.control_potential must have shape "
            f"({control_surface.panel_count},)."
        )
    generalized_heave, generalized_pitch = DEFAULT_A1_HEAVE_PITCH_CONVENTION.end_contour_n_rows(
        control_surface,
        lever_arm_m=lever_arm_m,
    )
    end_columns = np.array(
        [
            [
                np.sum(heave_phi * generalized_heave),
                np.sum(pitch_phi * generalized_heave),
            ],
            [
                np.sum(heave_phi * generalized_pitch),
                np.sum(pitch_phi * generalized_pitch),
            ],
        ],
        dtype=complex,
    )
    force_matrix = -float(rho_water_kg_m3) * speed * end_columns
    return StokesEndTermForceMatrix(
        complex_force_matrix=force_matrix,
        forward_speed_mps=speed,
        rho_water_kg_m3=float(rho_water_kg_m3),
        lever_arm_m=float(lever_arm_m),
        row_labels=("heave_force", "pitch_moment"),
        column_labels=("heave_radiation", "pitch_radiation"),
        validity=ValidityReport(
            status=LINEAR_2P5D_CONTROL_SURFACE_END_TERM_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "Diagnostic-only A1 Eq. (32) C_A probe using fixed control-surface potential on S_C. "
                "It compares the control-surface endpoint allocation with the current body-contour helper and "
                "does not alter the default coefficient path.",
            ),
        ),
    )


def compute_heave_pitch_stokes_body_forward_speed_force_matrix(
    x_m: np.ndarray,
    bodies: tuple[InnerDomainPanelGeometry, ...],
    heave_mode_solutions: tuple[MatchedSectionSolution, ...],
    pitch_mode_solutions: tuple[MatchedSectionSolution, ...],
    *,
    rho_water_kg_m3: float = 1025.0,
    forward_speed_mps: float,
    pitch_m5_sign: float = 1.0,
) -> StokesBodyForwardSpeedForceMatrix:
    """Compute the A1 Eq. (32) body forward-speed term for heave/pitch rows.

    For the reduced heave/pitch block, A1 Eq. (6) gives `m3=0` and `m5=Nz`
    after neglecting the steady perturbation potential. The package stores
    section normals with `z` positive downward and heave force positive upward,
    so the default pitch-row diagnostic uses `-normal_z` as the package form of
    `m5`. The result is diagnostic-only and is not added to the default Eq. (30)
    pressure-gradient force matrix.
    """

    x = np.asarray(x_m, dtype=float)
    speed = float(forward_speed_mps)
    sign = float(pitch_m5_sign)
    if speed < 0.0:
        raise ValueError("forward_speed_mps must be non-negative.")
    if not np.isfinite(sign):
        raise ValueError("pitch_m5_sign must be finite.")
    if x.ndim != 1 or x.size < 2:
        raise ValueError("x_m must be one-dimensional with at least two stations.")
    if np.any(np.diff(x) <= 0.0):
        raise ValueError("x_m must be strictly increasing.")
    station_count = x.size
    if len(bodies) != station_count:
        raise ValueError("bodies must match x_m length.")
    if len(heave_mode_solutions) != station_count or len(pitch_mode_solutions) != station_count:
        raise ValueError("heave_mode_solutions and pitch_mode_solutions must match x_m length.")

    density = np.zeros((station_count, 2, 2), dtype=complex)
    rho_u = float(rho_water_kg_m3) * speed
    for station_index, (body, heave_solution, pitch_solution) in enumerate(
        zip(bodies, heave_mode_solutions, pitch_mode_solutions, strict=True)
    ):
        heave_phi = np.asarray(heave_solution.body_potential, dtype=complex)
        pitch_phi = np.asarray(pitch_solution.body_potential, dtype=complex)
        if heave_phi.shape != (body.panel_count,):
            raise ValueError(
                f"heave_mode_solutions[{station_index}].body_potential must have shape "
                f"({body.panel_count},), got {heave_phi.shape}."
            )
        if pitch_phi.shape != (body.panel_count,):
            raise ValueError(
                f"pitch_mode_solutions[{station_index}].body_potential must have shape "
                f"({body.panel_count},), got {pitch_phi.shape}."
            )
        _, pitch_m5_measure = DEFAULT_A1_HEAVE_PITCH_CONVENTION.stokes_body_m_rows(
            body,
            pitch_m5_sign=sign,
        )
        density[station_index, 1, 0] = rho_u * np.sum(heave_phi * pitch_m5_measure)
        density[station_index, 1, 1] = rho_u * np.sum(pitch_phi * pitch_m5_measure)
    matrix = np.trapezoid(density, x, axis=0)
    return StokesBodyForwardSpeedForceMatrix(
        x_m=x,
        force_density_by_station=density,
        complex_force_matrix=np.asarray(matrix, dtype=complex),
        forward_speed_mps=speed,
        rho_water_kg_m3=float(rho_water_kg_m3),
        pitch_m5_sign=sign,
        row_labels=("heave_force", "pitch_moment"),
        column_labels=("heave_radiation", "pitch_radiation"),
        validity=ValidityReport(
            status=LINEAR_2P5D_STOKES_BODY_FORWARD_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "A1 Eq. (32) body forward-speed helper for rho U integral(phi_j m_i ds). "
                "It is stored as a diagnostic alongside, not a replacement for, the current Eq. (30) "
                "finite-difference pressure-gradient channel.",
            ),
        ),
    )


def compute_heave_pitch_row_measure_transport_force_matrix(
    x_m: np.ndarray,
    bodies: tuple[InnerDomainPanelGeometry, ...],
    heave_mode_solutions: tuple[MatchedSectionSolution, ...],
    pitch_mode_solutions: tuple[MatchedSectionSolution, ...],
    *,
    rho_water_kg_m3: float = 1025.0,
    forward_speed_mps: float,
    lever_arms_m: np.ndarray,
    pitch_m5_sign: float = 1.0,
) -> RowMeasureTransportForceMatrix:
    """Compute diagnostic `rho U int phi_j d(N_i ds)/dx` row-measure transport.

    This is not an alternative production pressure-gradient path. It exposes
    the geometric part of the product rule behind A1 Eq. (31)-Eq. (32), using
    the same equal-panel-index station mapping as the current default gradient.
    """

    x = np.asarray(x_m, dtype=float)
    levers = np.asarray(lever_arms_m, dtype=float)
    speed = float(forward_speed_mps)
    sign = float(pitch_m5_sign)
    if speed < 0.0:
        raise ValueError("forward_speed_mps must be non-negative.")
    if not np.isfinite(sign):
        raise ValueError("pitch_m5_sign must be finite.")
    if x.ndim != 1 or x.size < 2:
        raise ValueError("x_m must be one-dimensional with at least two stations.")
    if np.any(np.diff(x) <= 0.0):
        raise ValueError("x_m must be strictly increasing.")
    station_count = x.size
    if levers.shape != (station_count,):
        raise ValueError(f"lever_arms_m must have shape ({station_count},), got {levers.shape}.")
    if len(bodies) != station_count:
        raise ValueError("bodies must match x_m length.")
    if len(heave_mode_solutions) != station_count or len(pitch_mode_solutions) != station_count:
        raise ValueError("heave_mode_solutions and pitch_mode_solutions must match x_m length.")
    panel_count = bodies[0].panel_count
    for index, body in enumerate(bodies):
        if body.panel_count != panel_count:
            raise ValueError(
                "All station bodies must use the same panel count for row-measure transport diagnostics; "
                f"station 0 has {panel_count}, station {index} has {body.panel_count}."
            )

    convention = DEFAULT_A1_HEAVE_PITCH_CONVENTION
    pressure_row_measure = np.zeros((station_count, 2, panel_count), dtype=float)
    stokes_m_measure = np.zeros_like(pressure_row_measure)
    heave_phi = np.zeros((station_count, panel_count), dtype=complex)
    pitch_phi = np.zeros_like(heave_phi)
    for station_index, (body, heave_solution, pitch_solution) in enumerate(
        zip(bodies, heave_mode_solutions, pitch_mode_solutions, strict=True)
    ):
        heave = np.asarray(heave_solution.body_potential, dtype=complex)
        pitch = np.asarray(pitch_solution.body_potential, dtype=complex)
        if heave.shape != (panel_count,):
            raise ValueError(
                f"heave_mode_solutions[{station_index}].body_potential must have shape "
                f"({panel_count},), got {heave.shape}."
            )
        if pitch.shape != (panel_count,):
            raise ValueError(
                f"pitch_mode_solutions[{station_index}].body_potential must have shape "
                f"({panel_count},), got {pitch.shape}."
            )
        heave_phi[station_index] = heave
        pitch_phi[station_index] = pitch
        pressure_row_measure[station_index, 0], pressure_row_measure[station_index, 1] = (
            convention.pressure_generalized_rows(
                body.normal_z,
                body.length_m,
                lever_arm_m=float(levers[station_index]),
            )
        )
        stokes_m_measure[station_index, 0], stokes_m_measure[station_index, 1] = convention.stokes_body_m_rows(
            body,
            pitch_m5_sign=sign,
        )

    rho_u = float(rho_water_kg_m3) * speed

    def coordinate(index: int, mapping_kind: str) -> np.ndarray:
        body = bodies[index]
        if mapping_kind == "fixed_y":
            return np.asarray(body.mid_y_m, dtype=float)
        if mapping_kind == "normalized_y":
            y = np.asarray(body.mid_y_m, dtype=float)
            half_beam = float(np.max(np.abs(np.asarray(body.node_y_m, dtype=float))))
            if half_beam <= 1e-12:
                half_beam = max(float(np.max(np.abs(y))), 1e-12)
            return y / half_beam
        if mapping_kind == "normalized_arclength":
            length = np.asarray(body.length_m, dtype=float)
            total = float(np.sum(length))
            if total <= 1e-12:
                return np.linspace(0.0, 1.0, body.panel_count)
            centers = np.cumsum(length) - 0.5 * length
            return centers / total
        raise ValueError(f"Unsupported row-measure mapping kind: {mapping_kind}")

    def mapped_row(source_index: int, target_index: int, row_index: int, mapping_kind: str) -> np.ndarray:
        if source_index == target_index:
            return np.asarray(pressure_row_measure[source_index, row_index], dtype=float)
        source_coordinate = coordinate(source_index, mapping_kind)
        target_coordinate = coordinate(target_index, mapping_kind)
        mapped = _interp_complex_1d(
            source_coordinate,
            np.asarray(pressure_row_measure[source_index, row_index], dtype=complex),
            target_coordinate,
        )
        return np.asarray(mapped.real, dtype=float)

    def mapped_row_measure_x_gradient(mapping_kind: str | None) -> np.ndarray:
        if mapping_kind is None:
            edge_order = 2 if station_count >= 3 else 1
            return np.asarray(np.gradient(pressure_row_measure, x, axis=0, edge_order=edge_order), dtype=float)
        gradient = np.zeros_like(pressure_row_measure, dtype=float)
        for row_index in range(2):
            gradient[0, row_index] = (
                mapped_row(1, 0, row_index, mapping_kind) - pressure_row_measure[0, row_index]
            ) / (x[1] - x[0])
            gradient[-1, row_index] = (
                pressure_row_measure[-1, row_index] - mapped_row(station_count - 2, station_count - 1, row_index, mapping_kind)
            ) / (x[-1] - x[-2])
            for station_index in range(1, station_count - 1):
                gradient[station_index, row_index] = (
                    mapped_row(station_index + 1, station_index, row_index, mapping_kind)
                    - mapped_row(station_index - 1, station_index, row_index, mapping_kind)
                ) / (x[station_index + 1] - x[station_index - 1])
        return gradient

    def heave_projection_leibniz_endpoint_gradient() -> np.ndarray:
        """Return a fixed-projection Leibniz endpoint-flux proxy for the heave row.

        For the package convention, the heave pressure row satisfies
        ``N3 ds = -normal_z ds``.  On the body contour this is the signed
        transverse projection of each panel, so the fixed-coordinate transport
        of the heave-row measure is carried by the two moving endpoints of the
        wetted interval.  The pitch row is intentionally left on the current
        equal-panel derivative because this candidate is only a heave-row
        blocker probe, not a complete replacement for Eq. (31)-Eq. (32).
        """

        edge_order = 2 if station_count >= 3 else 1
        gradient = np.asarray(mapped_row_measure_x_gradient(None), dtype=float)
        node_y_by_station = np.asarray(
            [np.asarray(body.node_y_m, dtype=float) for body in bodies],
            dtype=float,
        )
        delta_y_by_station = np.diff(node_y_by_station, axis=1)
        heave_measure = pressure_row_measure[:, 0, :]
        plus_residual = float(np.linalg.norm(heave_measure - delta_y_by_station))
        minus_residual = float(np.linalg.norm(heave_measure + delta_y_by_station))
        projection_sign = 1.0 if plus_residual <= minus_residual else -1.0
        signed_node_y = projection_sign * node_y_by_station
        first_node_gradient = np.gradient(signed_node_y[:, 0], x, edge_order=edge_order)
        last_node_gradient = np.gradient(signed_node_y[:, -1], x, edge_order=edge_order)
        gradient[:, 0, :] = 0.0
        gradient[:, 0, 0] -= first_node_gradient
        gradient[:, 0, -1] += last_node_gradient
        return gradient

    def density_from_row_gradient(row_gradient_by_station: np.ndarray) -> np.ndarray:
        density_result = np.zeros((station_count, 2, 2), dtype=complex)
        for station_index in range(station_count):
            for row_index in range(2):
                row_gradient = row_gradient_by_station[station_index, row_index]
                density_result[station_index, row_index, 0] = rho_u * np.sum(heave_phi[station_index] * row_gradient)
                density_result[station_index, row_index, 1] = rho_u * np.sum(pitch_phi[station_index] * row_gradient)
        return density_result

    row_measure_x_gradient = mapped_row_measure_x_gradient(None)
    density = density_from_row_gradient(row_measure_x_gradient)
    matrix = np.trapezoid(density, x, axis=0)
    candidate_definitions = (
        ("current_equal_panel_x_derivative", None),
        ("mapped_fixed_y_central", "fixed_y"),
        ("mapped_normalized_y_central", "normalized_y"),
        ("mapped_normalized_arclength_central", "normalized_arclength"),
        ("heave_projection_leibniz_endpoint_flux_pitch_current", "heave_projection_leibniz_endpoint_flux"),
    )
    candidate_gradients: list[np.ndarray] = []
    candidate_densities: list[np.ndarray] = []
    candidate_matrices: list[np.ndarray] = []
    for _candidate_name, mapping_kind in candidate_definitions:
        if mapping_kind == "heave_projection_leibniz_endpoint_flux":
            candidate_gradient = heave_projection_leibniz_endpoint_gradient()
        else:
            candidate_gradient = mapped_row_measure_x_gradient(mapping_kind)
        candidate_density = density_from_row_gradient(candidate_gradient)
        candidate_gradients.append(candidate_gradient)
        candidate_densities.append(candidate_density)
        candidate_matrices.append(np.asarray(np.trapezoid(candidate_density, x, axis=0), dtype=complex))
    return RowMeasureTransportForceMatrix(
        x_m=x,
        pressure_row_measure_by_station=pressure_row_measure,
        pressure_row_measure_x_gradient_by_station=np.asarray(row_measure_x_gradient, dtype=float),
        stokes_m_measure_by_station=stokes_m_measure,
        force_density_by_station=density,
        complex_force_matrix=np.asarray(matrix, dtype=complex),
        candidate_names=tuple(name for name, _mapping in candidate_definitions),
        candidate_pressure_row_measure_x_gradient_by_station=np.asarray(candidate_gradients, dtype=float),
        candidate_force_density_by_station=np.asarray(candidate_densities, dtype=complex),
        candidate_complex_force_matrices=np.asarray(candidate_matrices, dtype=complex),
        forward_speed_mps=speed,
        rho_water_kg_m3=float(rho_water_kg_m3),
        pitch_m5_sign=sign,
        row_labels=("heave_force", "pitch_moment"),
        column_labels=("heave_radiation", "pitch_radiation"),
        validity=ValidityReport(
            status="a1_eq31_row_measure_transport_diagnostic_not_hard_gate",
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "Diagnostic-only row-measure transport rho U int phi_j d(N_i ds)/dx. "
                "It uses the current equal-panel-index station mapping to localize Eq.31/Eq.32 "
                "geometry-transport errors; it is not added to the default matched_bie_station_sweep force matrix.",
            ),
        ),
    )


def _station_offsets_for_matched_2p5d(
    station,
    *,
    parametric_section_shape: str,
    point_count_per_side: int,
) -> SectionOffsets:
    offsets = station.section_offsets()
    if offsets is not None:
        return offsets
    beam = float(station.waterplane_beam_m())
    draft = float(station.effective_draft_m())
    shape = parametric_section_shape.strip().lower()
    if shape == "wigley":
        return wigley_section_offsets(beam, draft, point_count_per_side=point_count_per_side)
    if shape in {"hard_chine_v", "v", "v_section"}:
        return hard_chine_v_offsets(beam, draft, point_count_per_side=point_count_per_side)
    raise ValueError("parametric_section_shape must be 'wigley' or 'hard_chine_v'.")


def _solve_one_matched_station_mode(
    solver: "Matched2p5DSectionSolver",
    *,
    body: InnerDomainPanelGeometry,
    free: InnerDomainPanelGeometry,
    control: InnerDomainPanelGeometry,
    history: TransientFreeSurfaceHistory,
    body_normal_velocity: np.ndarray,
    free_surface_potential: np.ndarray,
    free_surface_potential_control_row: np.ndarray | None = None,
    past_control_potential: np.ndarray,
    past_control_normal_derivative: np.ndarray,
    history_rhs_scale: float = 1.0,
    history_convolution_rule: str = "trapezoid",
    history_potential_kernel_scale: float = 1.0,
    history_normal_derivative_kernel_scale: float = 1.0,
    control_image_scale: float = 1.0,
    control_potential_kernel_scale: float = 1.0,
    control_normal_derivative_kernel_scale: float = 1.0,
    control_diagonal_sign: float = 1.0,
    inner_a_scale: float = 1.0,
    inner_b_scale: float = 1.0,
    inner_diagonal_sign: float = -1.0,
    inner_free_surface_self_diagonal_scale: float = 1.0,
    inner_free_surface_known_potential_rhs_scale: float = 1.0,
    inner_free_surface_known_potential_body_row_scale: float = 1.0,
    inner_free_surface_known_potential_free_row_scale: float = 1.0,
    inner_free_surface_known_potential_control_row_scale: float = 1.0,
    inner_free_surface_unknown_normal_column_scale: float = 1.0,
) -> tuple[MatchedSectionSolution, float, float, MatchedSystemBlockAudit]:
    data = MatchedSectionBoundaryData(
        body=body,
        inner_free_surface=free,
        control=control,
        body_normal_velocity=np.asarray(body_normal_velocity, dtype=complex),
        free_surface_potential=np.asarray(free_surface_potential, dtype=complex),
        history=history,
        past_control_potential=past_control_potential,
        past_control_normal_derivative=past_control_normal_derivative,
        free_surface_potential_control_row=(
            None
            if free_surface_potential_control_row is None
            else np.asarray(free_surface_potential_control_row, dtype=complex)
        ),
        history_rhs_scale=float(history_rhs_scale),
        history_convolution_rule=str(history_convolution_rule),
        history_potential_kernel_scale=float(history_potential_kernel_scale),
        history_normal_derivative_kernel_scale=float(history_normal_derivative_kernel_scale),
        control_image_scale=float(control_image_scale),
        control_potential_kernel_scale=float(control_potential_kernel_scale),
        control_normal_derivative_kernel_scale=float(control_normal_derivative_kernel_scale),
        control_diagonal_sign=float(control_diagonal_sign),
        inner_a_scale=float(inner_a_scale),
        inner_b_scale=float(inner_b_scale),
        inner_diagonal_sign=float(inner_diagonal_sign),
        inner_free_surface_self_diagonal_scale=float(inner_free_surface_self_diagonal_scale),
        inner_free_surface_known_potential_rhs_scale=float(inner_free_surface_known_potential_rhs_scale),
        inner_free_surface_known_potential_body_row_scale=float(
            inner_free_surface_known_potential_body_row_scale,
        ),
        inner_free_surface_known_potential_free_row_scale=float(
            inner_free_surface_known_potential_free_row_scale,
        ),
        inner_free_surface_known_potential_control_row_scale=float(
            inner_free_surface_known_potential_control_row_scale,
        ),
        inner_free_surface_unknown_normal_column_scale=float(inner_free_surface_unknown_normal_column_scale),
    )
    system = solver.assemble_matched_section_system(data)
    values = system.solve()
    audit = audit_matched_system_blocks(data, system, values)
    return solver.split_solution(data, values), system.condition_number, system.relative_residual(values), audit


def _prepend_control_history(
    potential_history: np.ndarray,
    normal_history: np.ndarray,
    solution: MatchedSectionSolution,
) -> tuple[np.ndarray, np.ndarray]:
    next_potential = np.array(potential_history, copy=True)
    next_normal = np.array(normal_history, copy=True)
    if next_potential.shape[0] > 1:
        next_potential[1:] = next_potential[:-1]
        next_normal[1:] = next_normal[:-1]
    next_potential[0] = solution.control_potential
    next_normal[0] = solution.control_normal_derivative
    return next_potential, next_normal


def _relative_history_array_residual(
    residual: np.ndarray,
    reference_a: np.ndarray,
    reference_b: np.ndarray | None = None,
) -> float:
    numerator = float(np.linalg.norm(residual))
    denominator = float(np.linalg.norm(reference_a))
    if reference_b is not None:
        denominator = max(denominator, float(np.linalg.norm(reference_b)))
    zero_tolerance = 128.0 * np.finfo(float).eps * np.sqrt(max(np.asarray(residual).size, 1))
    if denominator <= zero_tolerance and numerator <= zero_tolerance:
        return 0.0
    return float(numerator / max(denominator, 1e-12))


def _complex_vector_real_alignment(reference: np.ndarray, target: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=complex)
    tgt = np.asarray(target, dtype=complex)
    denominator = float(np.linalg.norm(ref) * np.linalg.norm(tgt))
    if denominator <= 1e-30:
        return float("nan")
    return float(np.real(np.vdot(ref, tgt)) / denominator)


def _complex_vector_phase_deg(reference: np.ndarray, target: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=complex)
    tgt = np.asarray(target, dtype=complex)
    if float(np.linalg.norm(ref) * np.linalg.norm(tgt)) <= 1e-30:
        return float("nan")
    return float(np.degrees(np.angle(np.vdot(ref, tgt))))


def _safe_norm_ratio(numerator: np.ndarray, denominator: np.ndarray) -> float:
    denom = float(np.linalg.norm(np.asarray(denominator, dtype=complex)))
    if denom <= 1e-30:
        return float("nan")
    return float(np.linalg.norm(np.asarray(numerator, dtype=complex)) / denom)


def _safe_elementwise_ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    num = np.asarray(numerator, dtype=float)
    den = np.asarray(denominator, dtype=float)
    if num.shape != den.shape:
        raise ValueError("numerator and denominator must have matching shapes.")
    result = np.full(num.shape, np.nan, dtype=float)
    mask = np.isfinite(num) & np.isfinite(den) & (np.abs(den) > 1e-30)
    result[mask] = num[mask] / den[mask]
    return result


def _solution_array_norms(solutions: tuple[MatchedSectionSolution, ...], field_name: str) -> np.ndarray:
    return np.asarray(
        [np.linalg.norm(np.asarray(getattr(solution, field_name), dtype=complex)) for solution in solutions],
        dtype=float,
    )


def _pressure_array_norms(pressures: tuple[MatchedSectionPressureResult, ...], field_name: str) -> np.ndarray:
    return np.asarray(
        [np.linalg.norm(np.asarray(getattr(pressure, field_name), dtype=complex)) for pressure in pressures],
        dtype=float,
    )


def _free_surface_potential_increment_diagnostics(
    solutions: tuple[MatchedSectionSolution, ...],
    before_by_station: np.ndarray,
    after_by_station: np.ndarray,
    *,
    free_surface_velocity_scale: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    before = np.asarray(before_by_station, dtype=complex)
    after = np.asarray(after_by_station, dtype=complex)
    if before.shape != after.shape:
        raise ValueError("free-surface before/after arrays must have the same shape.")
    if before.shape[0] != len(solutions):
        raise ValueError("free-surface arrays must have one row per station solution.")
    increment_norms: list[float] = []
    increment_to_velocity_gains: list[float] = []
    increment_velocity_alignments: list[float] = []
    increment_velocity_phases: list[float] = []
    scale = float(free_surface_velocity_scale)
    for index, solution in enumerate(solutions):
        velocity = scale * np.asarray(solution.inner_free_surface_normal_derivative, dtype=complex)
        increment = after[index] - before[index]
        increment_norms.append(float(np.linalg.norm(increment)))
        increment_to_velocity_gains.append(_safe_norm_ratio(increment, velocity))
        increment_velocity_alignments.append(_complex_vector_real_alignment(velocity, increment))
        increment_velocity_phases.append(_complex_vector_phase_deg(velocity, increment))
    return (
        np.asarray(increment_norms, dtype=float),
        np.asarray(increment_to_velocity_gains, dtype=float),
        np.asarray(increment_velocity_alignments, dtype=float),
        np.asarray(increment_velocity_phases, dtype=float),
    )


def _free_surface_marching_velocity_from_normal_derivative(
    normal_derivative: np.ndarray,
    *,
    source: str = "raw",
    body_normal_velocity: np.ndarray | None = None,
) -> np.ndarray:
    """Return diagnostic free-surface vertical velocity used by station marching."""

    raw = np.asarray(normal_derivative, dtype=complex)
    mode = str(source).strip().lower()
    if mode in {"raw", "current_raw"}:
        return raw
    if mode in {"real_part_only", "real_only"}:
        return np.asarray(np.real(raw), dtype=complex)
    if mode in {"imaginary_part_only", "imag_only"}:
        return 1j * np.asarray(np.imag(raw), dtype=float)
    if mode == "phase_lead_90":
        return 1j * raw
    if mode == "phase_lag_90":
        return -1j * raw
    if mode == "body_velocity_norm_normalized":
        reference = np.asarray([] if body_normal_velocity is None else body_normal_velocity, dtype=complex)
        raw_norm = float(np.linalg.norm(raw))
        reference_norm = float(np.linalg.norm(reference))
        if raw_norm <= 1e-30 or reference_norm <= 1e-30:
            return np.zeros_like(raw, dtype=complex)
        return raw * (reference_norm / raw_norm)
    raise ValueError(
        "free_surface_normal_derivative_source must be one of raw, real_part_only, "
        "imaginary_part_only, phase_lead_90, phase_lag_90, or body_velocity_norm_normalized."
    )


def _pressure_to_state_gain(
    pressures: tuple[MatchedSectionPressureResult, ...],
    pressure_field_name: str,
    state_by_station: np.ndarray,
) -> np.ndarray:
    state = np.asarray(state_by_station, dtype=complex)
    if state.shape[0] != len(pressures):
        raise ValueError("state_by_station must have one row per station pressure result.")
    return np.asarray(
        [
            _safe_norm_ratio(np.asarray(getattr(pressure, pressure_field_name), dtype=complex), state[index])
            for index, pressure in enumerate(pressures)
        ],
        dtype=float,
    )


def _pressure_formula_ratios(
    pressures: tuple[MatchedSectionPressureResult, ...],
    *,
    component: str,
) -> np.ndarray:
    component_name = str(component).strip().lower()
    ratios: list[float] = []
    for pressure in pressures:
        rho = float(pressure.rho_water_kg_m3)
        omega = float(pressure.omega_rad_s)
        speed = float(pressure.forward_speed_mps)
        if component_name == "time":
            reference = rho * omega * np.asarray(pressure.body_potential, dtype=complex)
            ratios.append(_safe_norm_ratio(pressure.pressure_time_derivative_pa, reference))
        elif component_name == "forward":
            reference = rho * speed * np.asarray(pressure.body_potential_x_gradient, dtype=complex)
            ratios.append(_safe_norm_ratio(pressure.pressure_forward_speed_pa, reference))
        else:
            raise ValueError("component must be 'time' or 'forward'.")
    return np.asarray(ratios, dtype=float)


def _force_to_pressure_norm_gains(
    pressures: tuple[MatchedSectionPressureResult, ...],
    forces: tuple[MatchedSectionForceResult, ...],
    force_attr: str,
) -> np.ndarray:
    if len(pressures) != len(forces):
        raise ValueError("pressures and forces must have the same length.")
    return np.asarray(
        [
            float(abs(complex(getattr(force, force_attr))) / max(np.linalg.norm(pressure.pressure_pa), 1e-30))
            for pressure, force in zip(pressures, forces, strict=True)
        ],
        dtype=float,
    )


def _potential_gradient_norms(gradient: StationPotentialGradient) -> np.ndarray:
    return np.asarray(
        [np.linalg.norm(row) for row in np.asarray(gradient.body_potential_x_gradient, dtype=complex)],
        dtype=float,
    )


def _potential_gradient_to_potential_gains(
    gradient: StationPotentialGradient,
    potentials_by_station: np.ndarray,
) -> np.ndarray:
    gradients = np.asarray(gradient.body_potential_x_gradient, dtype=complex)
    potentials = np.asarray(potentials_by_station, dtype=complex)
    if gradients.shape != potentials.shape:
        raise ValueError("gradient and potential arrays must have matching shapes.")
    return np.asarray(
        [_safe_norm_ratio(gradients[index], potentials[index]) for index in range(gradients.shape[0])],
        dtype=float,
    )


def _potential_gradient_characteristic_lengths(
    gradient: StationPotentialGradient,
    potentials_by_station: np.ndarray,
) -> np.ndarray:
    gradients = np.asarray(gradient.body_potential_x_gradient, dtype=complex)
    potentials = np.asarray(potentials_by_station, dtype=complex)
    if gradients.shape != potentials.shape:
        raise ValueError("gradient and potential arrays must have matching shapes.")
    return np.asarray(
        [_safe_norm_ratio(potentials[index], gradients[index]) for index in range(gradients.shape[0])],
        dtype=float,
    )


def _scalar_gradient_to_value_gains(x_m: np.ndarray, values: np.ndarray) -> np.ndarray:
    x = np.asarray(x_m, dtype=float)
    data = np.asarray(values, dtype=float)
    if x.ndim != 1 or data.shape != x.shape:
        raise ValueError("x_m and values must be one-dimensional arrays with matching shape.")
    if x.size < 2:
        return np.zeros_like(data, dtype=float)
    edge_order = 2 if x.size >= 3 else 1
    gradient = np.gradient(data, x, edge_order=edge_order)
    denominator = np.maximum(np.abs(data), 1e-30)
    result = np.full(data.shape, np.nan, dtype=float)
    mask = np.isfinite(gradient) & np.isfinite(denominator) & (denominator > 1e-30)
    result[mask] = np.abs(gradient[mask]) / denominator[mask]
    return result


def _adjacent_scalar_relative_jumps(values: np.ndarray) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    if data.ndim != 1:
        raise ValueError("values must be one-dimensional.")
    if data.size < 2:
        return np.zeros(0, dtype=float)
    return np.asarray(
        [
            abs(float(current) - float(previous)) / max(abs(float(previous)), abs(float(current)), 1e-30)
            for previous, current in zip(data[:-1], data[1:], strict=True)
        ],
        dtype=float,
    )


def _station_scalar_peak_x_over_l(x_m: np.ndarray, values: np.ndarray, *, hull_length_m: float) -> float:
    x = np.asarray(x_m, dtype=float)
    data = np.asarray(values, dtype=float)
    if x.ndim != 1 or data.shape != x.shape or data.size == 0:
        return float("nan")
    finite = np.isfinite(data)
    if not np.any(finite):
        return float("nan")
    masked = np.where(finite, np.abs(data), -np.inf)
    index = int(np.argmax(masked))
    return float(x[index] / max(float(hull_length_m), 1e-30))


def _matched_station_geometry_arrays(
    hull: StationHull,
    active_station_indices: tuple[int, ...],
) -> dict[str, np.ndarray]:
    active_stations = tuple(hull.stations[index] for index in active_station_indices)
    return {
        "waterplane_beam_m": np.asarray([station.waterplane_beam_m() for station in active_stations], dtype=float),
        "effective_draft_m": np.asarray([station.effective_draft_m() for station in active_stations], dtype=float),
        "submerged_area_m2": np.asarray([station.submerged_area_m2() for station in active_stations], dtype=float),
    }


def _adjacent_complex_state_diagnostics(values_by_station: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(values_by_station, dtype=complex)
    if values.ndim != 2:
        raise ValueError("values_by_station must be a two-dimensional station-by-panel array.")
    if values.shape[0] < 2:
        empty = np.zeros(0, dtype=float)
        return empty, empty, empty, empty
    relative_jumps: list[float] = []
    symmetric_norm_ratios: list[float] = []
    real_alignments: list[float] = []
    phase_degs: list[float] = []
    for previous, current in zip(values[:-1], values[1:], strict=True):
        previous_norm = float(np.linalg.norm(previous))
        current_norm = float(np.linalg.norm(current))
        denominator = max(previous_norm, current_norm, 1e-30)
        relative_jumps.append(float(np.linalg.norm(current - previous) / denominator))
        if previous_norm <= 1e-30 or current_norm <= 1e-30:
            symmetric_norm_ratios.append(float("nan"))
        else:
            symmetric_norm_ratios.append(float(max(current_norm / previous_norm, previous_norm / current_norm)))
        real_alignments.append(_complex_vector_real_alignment(previous, current))
        phase_degs.append(_complex_vector_phase_deg(previous, current))
    return (
        np.asarray(relative_jumps, dtype=float),
        np.asarray(symmetric_norm_ratios, dtype=float),
        np.asarray(real_alignments, dtype=float),
        np.asarray(phase_degs, dtype=float),
    )


def _phase_align_adjacent_complex_states(values_by_station: np.ndarray) -> np.ndarray:
    values = np.asarray(values_by_station, dtype=complex)
    if values.ndim != 2:
        raise ValueError("values_by_station must be a two-dimensional station-by-panel array.")
    if values.shape[0] < 2:
        return np.array(values, copy=True)
    aligned = np.array(values, copy=True)
    for index in range(1, values.shape[0]):
        reference = aligned[index - 1]
        current = values[index]
        if float(np.linalg.norm(reference) * np.linalg.norm(current)) <= 1e-30:
            aligned[index] = current
            continue
        phase = np.angle(np.vdot(reference, current))
        aligned[index] = current * np.exp(-1j * phase)
    return aligned


def _real_relative_jump(current: np.ndarray, previous: np.ndarray) -> float:
    previous_values = np.asarray(previous, dtype=float)
    current_values = np.asarray(current, dtype=float)
    if previous_values.shape != current_values.shape:
        return float("nan")
    denominator = max(float(np.linalg.norm(previous_values)), float(np.linalg.norm(current_values)), 1e-30)
    return float(np.linalg.norm(current_values - previous_values) / denominator)


def _adjacent_panel_geometry_diagnostics(
    bodies: tuple[InnerDomainPanelGeometry, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if len(bodies) < 2:
        empty = np.zeros(0, dtype=float)
        return empty, empty, empty, empty
    mid_y_jumps: list[float] = []
    mid_z_jumps: list[float] = []
    normal_jumps: list[float] = []
    length_jumps: list[float] = []
    for previous, current in zip(bodies[:-1], bodies[1:], strict=True):
        mid_y_jumps.append(_real_relative_jump(current.mid_y_m, previous.mid_y_m))
        mid_z_jumps.append(_real_relative_jump(current.mid_z_down_m, previous.mid_z_down_m))
        previous_normals = np.column_stack((previous.normal_y, previous.normal_z))
        current_normals = np.column_stack((current.normal_y, current.normal_z))
        normal_jumps.append(_real_relative_jump(current_normals, previous_normals))
        length_jumps.append(_real_relative_jump(current.length_m, previous.length_m))
    return (
        np.asarray(mid_y_jumps, dtype=float),
        np.asarray(mid_z_jumps, dtype=float),
        np.asarray(normal_jumps, dtype=float),
        np.asarray(length_jumps, dtype=float),
    )


def _solve_matched_matrix_rhs(system: MatchedBoundarySystem, rhs: np.ndarray) -> np.ndarray:
    vector = np.asarray(rhs, dtype=complex)
    if vector.shape != system.rhs.shape:
        raise ValueError(f"rhs must have shape {system.rhs.shape}, got {vector.shape}.")
    if system.matrix.shape[0] == system.matrix.shape[1]:
        return np.linalg.solve(system.matrix, vector)
    return np.linalg.lstsq(system.matrix, vector, rcond=None)[0]


def _history_from_sweep_metadata(sweep: StationHullMatchedHeavePitchSweep) -> tuple[InnerDomainPanelGeometry, TransientFreeSurfaceHistory]:
    if sweep.history_steps < 1:
        raise ValueError("sweep.history_steps must be recorded and positive.")
    if sweep.history_dt_s <= 0.0 or not np.isfinite(sweep.history_dt_s):
        raise ValueError("sweep.history_dt_s must be recorded and positive.")
    if sweep.control_panel_count < 4:
        raise ValueError("sweep.control_panel_count must be recorded and at least 4.")
    if sweep.control_radius_m <= 0.0 or not np.isfinite(sweep.control_radius_m):
        raise ValueError("sweep.control_radius_m must be recorded and positive.")
    if sweep.history_quadrature_count < 16:
        raise ValueError("sweep.history_quadrature_count must be recorded and at least 16.")
    if sweep.history_k_max <= 0.0 or not np.isfinite(sweep.history_k_max):
        raise ValueError("sweep.history_k_max must be recorded and positive.")
    control = build_control_surface_geometry(
        radius_m=float(sweep.control_radius_m),
        panel_count=int(sweep.control_panel_count),
    )
    history = build_transient_free_surface_history(
        control,
        dt_s=float(sweep.history_dt_s),
        history_steps=int(sweep.history_steps),
        gravity_m_s2=float(sweep.history_gravity_m_s2),
        quadrature_count=int(sweep.history_quadrature_count),
        k_max=float(sweep.history_k_max),
    )
    return control, history


def _body_normal_velocity_from_sweep(
    sweep: StationHullMatchedHeavePitchSweep,
    *,
    mode_name: str,
    station_local_index: int,
) -> np.ndarray:
    """Reconstruct the exact phase-domain body condition used by the station solve."""

    mode = str(mode_name).strip().lower()
    local_index = int(station_local_index)
    if mode == "heave":
        omega = float(sweep.pressure_force_sweep.assembly.omega_rad_s)
        body_condition = heave_radiation_normal_velocity(sweep.bodies[local_index], omega)
        if bool(sweep.apply_local_time_phase):
            local_times = np.asarray(sweep.local_time_s_by_station, dtype=float)
            if local_times.shape != (len(sweep.x_m),):
                raise ValueError("sweep.local_time_s_by_station must be recorded for every station.")
            body_condition = np.exp(1j * omega * local_times[local_index]) * body_condition
        return np.asarray(body_condition, dtype=complex)
    if mode == "pitch":
        return (
            np.asarray(sweep.pitch_body_condition_oscillation_by_station[local_index], dtype=complex)
            + np.asarray(sweep.pitch_body_condition_forward_speed_by_station[local_index], dtype=complex)
        )
    raise ValueError("mode_name must be 'heave' or 'pitch'.")


def _aft_pair_rhs_source_norms_for_sweep(
    sweep: StationHullMatchedHeavePitchSweep,
    *,
    mode_name: str,
    station_count: int = 2,
) -> dict[str, np.ndarray]:
    """Return RHS source norms for the first active stations without re-solving source systems."""

    mode = str(mode_name).strip().lower()
    if mode not in {"heave", "pitch"}:
        raise ValueError("mode_name must be 'heave' or 'pitch'.")
    count = min(int(station_count), len(sweep.x_m))
    if count < 1:
        raise ValueError("sweep must contain at least one station.")
    control, history = _history_from_sweep_metadata(sweep)
    solutions = sweep.heave_mode_solutions if mode == "heave" else sweep.pitch_mode_solutions
    free_potential_by_station = (
        sweep.heave_free_surface_potential_by_station
        if mode == "heave"
        else sweep.pitch_free_surface_potential_by_station
    )
    past_phi = np.zeros((int(sweep.history_steps), int(sweep.control_panel_count)), dtype=complex)
    past_phi_n = np.zeros_like(past_phi)
    source_names = ("body_normal_velocity", "inner_free_surface_potential", "outer_control_history")
    source_norms = {name: np.full(count, np.nan, dtype=float) for name in source_names}
    source_ratios = {name: np.full(count, np.nan, dtype=float) for name in source_names}
    total_norms = np.full(count, np.nan, dtype=float)
    source_sum_relative_residuals = np.full(count, np.nan, dtype=float)
    for local_index in tuple(int(index) for index in sweep.solve_order):
        body = sweep.bodies[local_index]
        free = sweep.inner_free_surface_geometries[local_index]
        body_condition = _body_normal_velocity_from_sweep(
            sweep,
            mode_name=mode,
            station_local_index=local_index,
        )
        data = MatchedSectionBoundaryData(
            body=body,
            inner_free_surface=free,
            control=control,
            body_normal_velocity=np.asarray(body_condition, dtype=complex),
            free_surface_potential=np.asarray(free_potential_by_station[local_index], dtype=complex),
            history=history,
            past_control_potential=past_phi,
            past_control_normal_derivative=past_phi_n,
            history_rhs_scale=float(sweep.history_rhs_scale),
            history_convolution_rule=str(sweep.history_convolution_rule),
            history_potential_kernel_scale=float(sweep.history_potential_kernel_scale),
            history_normal_derivative_kernel_scale=float(sweep.history_normal_derivative_kernel_scale),
            control_image_scale=float(sweep.control_image_scale),
            control_potential_kernel_scale=float(sweep.control_potential_kernel_scale),
            control_normal_derivative_kernel_scale=float(sweep.control_normal_derivative_kernel_scale),
            control_diagonal_sign=float(sweep.control_diagonal_sign),
            inner_a_scale=float(sweep.inner_a_scale),
            inner_b_scale=float(sweep.inner_b_scale),
            inner_diagonal_sign=float(sweep.inner_diagonal_sign),
            inner_free_surface_self_diagonal_scale=float(sweep.inner_free_surface_self_diagonal_scale),
            inner_free_surface_known_potential_rhs_scale=float(
                sweep.inner_free_surface_known_potential_rhs_scale
            ),
            inner_free_surface_unknown_normal_column_scale=float(
                sweep.inner_free_surface_unknown_normal_column_scale
            ),
        )
        if local_index < count:
            system = assemble_matched_section_system(data)
            source_rhs = _matched_section_rhs_source_vectors(data)
            total_rhs_from_sources = np.sum(np.asarray(tuple(source_rhs.values()), dtype=complex), axis=0)
            total_norms[local_index] = float(np.linalg.norm(system.rhs))
            source_sum_relative_residuals[local_index] = _relative_history_array_residual(
                total_rhs_from_sources - np.asarray(system.rhs, dtype=complex),
                total_rhs_from_sources,
                system.rhs,
            )
            for source_name in source_names:
                source_norms[source_name][local_index] = float(np.linalg.norm(source_rhs[source_name]))
                source_ratios[source_name][local_index] = _safe_norm_ratio(source_rhs[source_name], system.rhs)
        past_phi, past_phi_n = _prepend_control_history(past_phi, past_phi_n, solutions[local_index])
    return {
        "total_rhs_norms": total_norms,
        "source_sum_relative_residuals": source_sum_relative_residuals,
        **{f"{name}_rhs_norms": values for name, values in source_norms.items()},
        **{f"{name}_rhs_to_total_ratios": values for name, values in source_ratios.items()},
    }


def _aft_pair_inner_free_surface_rhs_block_arrays_for_sweep(
    sweep: StationHullMatchedHeavePitchSweep,
    *,
    mode_name: str,
    station_count: int = 2,
) -> dict[str, np.ndarray]:
    """Return compact arrays for the first-station Eq. (23) free-surface RHS block audit."""

    row_block_names = ("eq23_body", "eq23_free_surface", "eq23_inner_control")
    count = min(int(station_count), len(sweep.x_m))
    if count < 1:
        raise ValueError("sweep must contain at least one station.")
    free_panel_count = int(sweep.inner_free_surface_geometries[0].panel_count)
    shape_panel = (count, len(row_block_names), free_panel_count)
    shape_block = (count, len(row_block_names))
    values = {
        "free_surface_panel_y_m": np.full(shape_panel, np.nan, dtype=float),
        "free_surface_panel_length_m": np.full(shape_panel, np.nan, dtype=float),
        "free_surface_potential_abs": np.full(shape_panel, np.nan, dtype=float),
        "free_surface_potential_phase_degs": np.full(shape_panel, np.nan, dtype=float),
        "matrix_column_norms": np.full(shape_panel, np.nan, dtype=float),
        "contribution_norms": np.full(shape_panel, np.nan, dtype=float),
        "panel_to_row_block_ratios": np.full(shape_panel, np.nan, dtype=float),
        "panel_to_total_ratios": np.full(shape_panel, np.nan, dtype=float),
        "panel_to_row_block_alignments": np.full(shape_panel, np.nan, dtype=float),
        "panel_to_row_block_phase_degs": np.full(shape_panel, np.nan, dtype=float),
        "row_block_free_rhs_norms": np.full(shape_block, np.nan, dtype=float),
        "row_block_to_total_ratios": np.full(shape_block, np.nan, dtype=float),
        "row_block_to_total_alignments": np.full(shape_block, np.nan, dtype=float),
        "row_block_to_total_phase_degs": np.full(shape_block, np.nan, dtype=float),
        "total_free_rhs_norms": np.full(count, np.nan, dtype=float),
    }
    row_block_index = {name: index for index, name in enumerate(row_block_names)}
    audits = audit_inner_free_surface_rhs_block_contributions(
        sweep,
        mode_name=mode_name,
        station_count=count,
    )
    for audit in audits:
        station_index = int(audit.station_local_index)
        if station_index >= count:
            continue
        block_index = row_block_index[str(audit.row_block_name)]
        panel_index = int(audit.free_surface_panel_index)
        if panel_index >= free_panel_count:
            continue
        values["free_surface_panel_y_m"][station_index, block_index, panel_index] = float(
            audit.free_surface_panel_y_m
        )
        values["free_surface_panel_length_m"][station_index, block_index, panel_index] = float(
            audit.free_surface_panel_length_m
        )
        values["free_surface_potential_abs"][station_index, block_index, panel_index] = float(
            audit.free_surface_potential_abs
        )
        values["free_surface_potential_phase_degs"][station_index, block_index, panel_index] = float(
            audit.free_surface_potential_phase_deg
        )
        values["matrix_column_norms"][station_index, block_index, panel_index] = float(
            audit.matrix_column_norm
        )
        values["contribution_norms"][station_index, block_index, panel_index] = float(
            audit.row_block_contribution_norm
        )
        values["panel_to_row_block_ratios"][station_index, block_index, panel_index] = float(
            audit.panel_to_row_block_free_rhs_norm_ratio
        )
        values["panel_to_total_ratios"][station_index, block_index, panel_index] = float(
            audit.panel_to_total_free_rhs_norm_ratio
        )
        values["panel_to_row_block_alignments"][station_index, block_index, panel_index] = float(
            audit.panel_to_row_block_real_alignment
        )
        values["panel_to_row_block_phase_degs"][station_index, block_index, panel_index] = float(
            audit.panel_to_row_block_phase_deg
        )
        values["row_block_free_rhs_norms"][station_index, block_index] = float(
            audit.row_block_free_rhs_norm
        )
        values["row_block_to_total_ratios"][station_index, block_index] = float(
            audit.row_block_to_total_free_rhs_norm_ratio
        )
        values["row_block_to_total_alignments"][station_index, block_index] = float(
            audit.row_block_to_total_real_alignment
        )
        values["row_block_to_total_phase_degs"][station_index, block_index] = float(
            audit.row_block_to_total_phase_deg
        )
        values["total_free_rhs_norms"][station_index] = float(audit.total_free_rhs_norm)
    return values


def audit_control_history_inheritance(
    sweep: StationHullMatchedHeavePitchSweep,
    *,
    mode_name: str = "heave",
) -> tuple[A1ControlHistoryInheritanceAudit, ...]:
    """Recompute Eq. (24) station histories from solved control-surface states.

    The matched station sweep stores the history RHS immediately before each
    section is solved.  This audit reconstructs the same history queue from the
    returned solutions and `solve_order`, then verifies the stored RHS and the
    lag-zero inheritance station by station.
    """

    mode = str(mode_name).strip().lower()
    if mode not in {"heave", "pitch"}:
        raise ValueError("mode_name must be 'heave' or 'pitch'.")
    station_count = int(len(sweep.x_m))
    if station_count < 1:
        raise ValueError("sweep must contain at least one station.")
    solve_order = tuple(int(index) for index in sweep.solve_order)
    if sorted(solve_order) != list(range(station_count)):
        raise ValueError("sweep.solve_order must be a permutation of station local indices.")

    solutions = sweep.heave_mode_solutions if mode == "heave" else sweep.pitch_mode_solutions
    stored_rhs_by_station = (
        sweep.heave_outer_history_rhs_by_station if mode == "heave" else sweep.pitch_outer_history_rhs_by_station
    )
    if len(solutions) != station_count:
        raise ValueError(f"{mode} solution count must match the active station count.")
    if stored_rhs_by_station.shape != (station_count, sweep.control_panel_count):
        raise ValueError(
            f"{mode} stored history RHS must have shape {(station_count, sweep.control_panel_count)}, "
            f"got {stored_rhs_by_station.shape}."
        )

    _, history = _history_from_sweep_metadata(sweep)
    past_phi = np.zeros((int(sweep.history_steps), int(sweep.control_panel_count)), dtype=complex)
    past_phi_n = np.zeros_like(past_phi)
    zero_control = np.zeros(int(sweep.control_panel_count), dtype=complex)
    rows: list[A1ControlHistoryInheritanceAudit] = []
    previous_local_index = -1
    for rank, local_index in enumerate(solve_order):
        expected_rhs = history.convolution_rhs(
            past_phi,
            past_phi_n,
            rhs_scale=float(sweep.history_rhs_scale),
            quadrature_rule=str(sweep.history_convolution_rule),
            potential_kernel_scale=float(sweep.history_potential_kernel_scale),
            normal_derivative_kernel_scale=float(sweep.history_normal_derivative_kernel_scale),
        )
        stored_rhs = np.asarray(stored_rhs_by_station[local_index], dtype=complex)
        rhs_residual = stored_rhs - expected_rhs
        if previous_local_index >= 0:
            previous_solution = solutions[previous_local_index]
            expected_lag0_phi = np.asarray(previous_solution.control_potential, dtype=complex)
            expected_lag0_phi_n = np.asarray(previous_solution.control_normal_derivative, dtype=complex)
        else:
            expected_lag0_phi = zero_control
            expected_lag0_phi_n = zero_control
        lag0_phi_residual = past_phi[0] - expected_lag0_phi
        lag0_phi_n_residual = past_phi_n[0] - expected_lag0_phi_n
        rows.append(
            A1ControlHistoryInheritanceAudit(
                mode_name=mode,
                station_local_index=int(local_index),
                active_station_index=int(sweep.active_station_indices[local_index]),
                solve_order_rank=int(rank),
                expected_previous_station_local_index=int(previous_local_index),
                history_steps=int(sweep.history_steps),
                history_dt_s=float(sweep.history_dt_s),
                history_quadrature_count=int(sweep.history_quadrature_count),
                history_k_max=float(sweep.history_k_max),
                control_panel_count=int(sweep.control_panel_count),
                control_radius_m=float(sweep.control_radius_m),
                quadrature_rule=str(sweep.history_convolution_rule),
                stored_rhs_norm=float(np.linalg.norm(stored_rhs)),
                expected_rhs_norm=float(np.linalg.norm(expected_rhs)),
                rhs_residual_norm=float(np.linalg.norm(rhs_residual)),
                rhs_relative_residual=_relative_history_array_residual(rhs_residual, stored_rhs, expected_rhs),
                rhs_max_abs_residual=float(np.max(np.abs(rhs_residual))) if rhs_residual.size else 0.0,
                lag0_potential_norm=float(np.linalg.norm(past_phi[0])),
                expected_lag0_potential_norm=float(np.linalg.norm(expected_lag0_phi)),
                lag0_potential_residual_norm=float(np.linalg.norm(lag0_phi_residual)),
                lag0_potential_relative_residual=_relative_history_array_residual(
                    lag0_phi_residual,
                    expected_lag0_phi,
                ),
                lag0_normal_derivative_norm=float(np.linalg.norm(past_phi_n[0])),
                expected_lag0_normal_derivative_norm=float(np.linalg.norm(expected_lag0_phi_n)),
                lag0_normal_derivative_residual_norm=float(np.linalg.norm(lag0_phi_n_residual)),
                lag0_normal_derivative_relative_residual=_relative_history_array_residual(
                    lag0_phi_n_residual,
                    expected_lag0_phi_n,
                ),
                full_history_potential_norm=float(np.linalg.norm(past_phi)),
                full_history_normal_derivative_norm=float(np.linalg.norm(past_phi_n)),
                validity=ValidityReport(
                    status=LINEAR_2P5D_CONTROL_HISTORY_INHERITANCE_STATUS,
                    reference_cases=("ma2005_wigley_iii_station_sweep",),
                    notes=(
                        "Reconstructs Eq. (24) control-surface history RHS from returned station solutions and "
                        "the recorded solve_order. This is an implementation-inheritance diagnostic, not a "
                        "hydrodynamic-coefficient hard gate.",
                    ),
                ),
            )
        )
        past_phi, past_phi_n = _prepend_control_history(past_phi, past_phi_n, solutions[local_index])
        previous_local_index = int(local_index)
    return tuple(rows)


def audit_outer_control_balance(
    sweep: StationHullMatchedHeavePitchSweep,
    *,
    mode_name: str = "heave",
) -> tuple[A1OuterControlBalanceAudit, ...]:
    """Split real station Eq. (24) control-surface rows into scale/phase components."""

    mode = str(mode_name).strip().lower()
    if mode not in {"heave", "pitch"}:
        raise ValueError("mode_name must be 'heave' or 'pitch'.")
    station_count = int(len(sweep.x_m))
    if station_count < 1:
        raise ValueError("sweep must contain at least one station.")
    solve_order = tuple(int(index) for index in sweep.solve_order)
    if sorted(solve_order) != list(range(station_count)):
        raise ValueError("sweep.solve_order must be a permutation of station local indices.")
    solutions = sweep.heave_mode_solutions if mode == "heave" else sweep.pitch_mode_solutions
    if len(solutions) != station_count:
        raise ValueError(f"{mode} solution count must match the active station count.")

    control, history = _history_from_sweep_metadata(sweep)
    past_phi = np.zeros((int(sweep.history_steps), int(sweep.control_panel_count)), dtype=complex)
    past_phi_n = np.zeros_like(past_phi)
    rows: list[A1OuterControlBalanceAudit] = []
    for rank, local_index in enumerate(solve_order):
        outer = assemble_outer_control_surface_system(
            control,
            history,
            past_phi,
            past_phi_n,
            history_rhs_scale=float(sweep.history_rhs_scale),
            history_convolution_rule=str(sweep.history_convolution_rule),
            history_potential_kernel_scale=float(sweep.history_potential_kernel_scale),
            history_normal_derivative_kernel_scale=float(sweep.history_normal_derivative_kernel_scale),
            control_image_scale=float(sweep.control_image_scale),
            control_potential_kernel_scale=float(sweep.control_potential_kernel_scale),
            control_normal_derivative_kernel_scale=float(sweep.control_normal_derivative_kernel_scale),
            control_diagonal_sign=float(sweep.control_diagonal_sign),
        )
        solution = solutions[local_index]
        n_control = int(sweep.control_panel_count)
        potential_contribution = outer.matrix[:, :n_control] @ np.asarray(solution.control_potential, dtype=complex)
        normal_contribution = outer.matrix[:, n_control:] @ np.asarray(
            solution.control_normal_derivative,
            dtype=complex,
        )
        lhs = potential_contribution + normal_contribution
        rhs = np.asarray(outer.rhs, dtype=complex)
        residual = lhs - rhs
        history_potential_channel = history.convolution_rhs(
            past_phi,
            past_phi_n,
            rhs_scale=float(sweep.history_rhs_scale),
            quadrature_rule=str(sweep.history_convolution_rule),
            potential_kernel_scale=float(sweep.history_potential_kernel_scale),
            normal_derivative_kernel_scale=0.0,
        )
        history_normal_channel = history.convolution_rhs(
            past_phi,
            past_phi_n,
            rhs_scale=float(sweep.history_rhs_scale),
            quadrature_rule=str(sweep.history_convolution_rule),
            potential_kernel_scale=0.0,
            normal_derivative_kernel_scale=float(sweep.history_normal_derivative_kernel_scale),
        )
        rows.append(
            A1OuterControlBalanceAudit(
                mode_name=mode,
                station_local_index=int(local_index),
                active_station_index=int(sweep.active_station_indices[local_index]),
                solve_order_rank=int(rank),
                history_steps=int(sweep.history_steps),
                history_dt_s=float(sweep.history_dt_s),
                control_panel_count=n_control,
                control_radius_m=float(sweep.control_radius_m),
                potential_contribution_norm=float(np.linalg.norm(potential_contribution)),
                normal_derivative_contribution_norm=float(np.linalg.norm(normal_contribution)),
                instantaneous_lhs_norm=float(np.linalg.norm(lhs)),
                history_rhs_norm=float(np.linalg.norm(rhs)),
                history_potential_kernel_channel_norm=float(np.linalg.norm(history_potential_channel)),
                history_normal_derivative_kernel_channel_norm=float(np.linalg.norm(history_normal_channel)),
                residual_norm=float(np.linalg.norm(residual)),
                relative_residual=_relative_history_array_residual(residual, lhs, rhs),
                rhs_to_lhs_norm_ratio=_safe_norm_ratio(rhs, lhs),
                potential_to_normal_contribution_norm_ratio=_safe_norm_ratio(
                    potential_contribution,
                    normal_contribution,
                ),
                history_potential_to_normal_channel_norm_ratio=_safe_norm_ratio(
                    history_potential_channel,
                    history_normal_channel,
                ),
                lhs_rhs_real_alignment=_complex_vector_real_alignment(lhs, rhs),
                lhs_rhs_phase_deg=_complex_vector_phase_deg(lhs, rhs),
                potential_normal_real_alignment=_complex_vector_real_alignment(
                    potential_contribution,
                    normal_contribution,
                ),
                potential_normal_phase_deg=_complex_vector_phase_deg(
                    potential_contribution,
                    normal_contribution,
                ),
                history_channel_real_alignment=_complex_vector_real_alignment(
                    history_potential_channel,
                    history_normal_channel,
                ),
                history_channel_phase_deg=_complex_vector_phase_deg(
                    history_potential_channel,
                    history_normal_channel,
                ),
                max_abs_lhs=float(np.max(np.abs(lhs))) if lhs.size else 0.0,
                max_abs_rhs=float(np.max(np.abs(rhs))) if rhs.size else 0.0,
                validity=ValidityReport(
                    status=LINEAR_2P5D_OUTER_CONTROL_BALANCE_STATUS,
                    reference_cases=("ma2005_wigley_iii_station_sweep",),
                    notes=(
                        "Splits the real Eq. (24) outer-control row into instantaneous potential, instantaneous "
                        "normal-derivative, and two history RHS channels. This is a scale/phase diagnostic, not a "
                        "hydrodynamic-coefficient hard gate.",
                    ),
                ),
            )
        )
        past_phi, past_phi_n = _prepend_control_history(past_phi, past_phi_n, solution)
    return tuple(rows)


def audit_rhs_source_decomposition(
    sweep: StationHullMatchedHeavePitchSweep,
    *,
    mode_name: str = "heave",
) -> tuple[A1RhsSourceDecompositionAudit, ...]:
    """Decompose real matched-system solutions by Eq. (23)-Eq. (24) RHS source."""

    mode = str(mode_name).strip().lower()
    if mode not in {"heave", "pitch"}:
        raise ValueError("mode_name must be 'heave' or 'pitch'.")
    station_count = int(len(sweep.x_m))
    if station_count < 1:
        raise ValueError("sweep must contain at least one station.")
    if len(sweep.inner_free_surface_geometries) != station_count:
        raise ValueError("sweep.inner_free_surface_geometries must be recorded for every active station.")
    solve_order = tuple(int(index) for index in sweep.solve_order)
    if sorted(solve_order) != list(range(station_count)):
        raise ValueError("sweep.solve_order must be a permutation of station local indices.")
    solutions = sweep.heave_mode_solutions if mode == "heave" else sweep.pitch_mode_solutions
    if len(solutions) != station_count:
        raise ValueError(f"{mode} solution count must match the active station count.")
    free_potential_by_station = (
        sweep.heave_free_surface_potential_by_station
        if mode == "heave"
        else sweep.pitch_free_surface_potential_by_station
    )
    control, history = _history_from_sweep_metadata(sweep)
    past_phi = np.zeros((int(sweep.history_steps), int(sweep.control_panel_count)), dtype=complex)
    past_phi_n = np.zeros_like(past_phi)
    rows: list[A1RhsSourceDecompositionAudit] = []
    for rank, local_index in enumerate(solve_order):
        body = sweep.bodies[local_index]
        free = sweep.inner_free_surface_geometries[local_index]
        body_condition = _body_normal_velocity_from_sweep(
            sweep,
            mode_name=mode,
            station_local_index=local_index,
        )
        data = MatchedSectionBoundaryData(
            body=body,
            inner_free_surface=free,
            control=control,
            body_normal_velocity=np.asarray(body_condition, dtype=complex),
            free_surface_potential=np.asarray(free_potential_by_station[local_index], dtype=complex),
            history=history,
            past_control_potential=past_phi,
            past_control_normal_derivative=past_phi_n,
            history_rhs_scale=float(sweep.history_rhs_scale),
            history_convolution_rule=str(sweep.history_convolution_rule),
            history_potential_kernel_scale=float(sweep.history_potential_kernel_scale),
            history_normal_derivative_kernel_scale=float(sweep.history_normal_derivative_kernel_scale),
            control_image_scale=float(sweep.control_image_scale),
            control_potential_kernel_scale=float(sweep.control_potential_kernel_scale),
            control_normal_derivative_kernel_scale=float(sweep.control_normal_derivative_kernel_scale),
            control_diagonal_sign=float(sweep.control_diagonal_sign),
            inner_a_scale=float(sweep.inner_a_scale),
            inner_b_scale=float(sweep.inner_b_scale),
            inner_diagonal_sign=float(sweep.inner_diagonal_sign),
            inner_free_surface_self_diagonal_scale=float(sweep.inner_free_surface_self_diagonal_scale),
            inner_free_surface_known_potential_rhs_scale=float(
                sweep.inner_free_surface_known_potential_rhs_scale
            ),
            inner_free_surface_unknown_normal_column_scale=float(
                sweep.inner_free_surface_unknown_normal_column_scale
            ),
        )
        system = assemble_matched_section_system(data)
        source_rhs = _matched_section_rhs_source_vectors(data)
        total_rhs_from_sources = np.sum(np.asarray(tuple(source_rhs.values()), dtype=complex), axis=0)
        total_values = _matched_section_solution_values(solutions[local_index])
        source_values = {
            name: _solve_matched_matrix_rhs(system, rhs)
            for name, rhs in source_rhs.items()
        }
        source_sum = np.sum(np.asarray(tuple(source_values.values()), dtype=complex), axis=0)
        source_sum_residual = source_sum - total_values
        rhs_sum_residual = total_rhs_from_sources - np.asarray(system.rhs, dtype=complex)
        source_sum_relative = _relative_history_array_residual(
            source_sum_residual,
            source_sum,
            total_values,
        )
        # Include RHS reconstruction in the same scalar so a future RHS split
        # edit cannot silently pass with a correct solution but wrong source labels.
        source_sum_relative = max(
            source_sum_relative,
            _relative_history_array_residual(rhs_sum_residual, total_rhs_from_sources, system.rhs),
        )
        full_norm = float(np.linalg.norm(total_values))
        total_rhs_norm = float(np.linalg.norm(system.rhs))
        for source_name, values in source_values.items():
            split = split_matched_section_solution(data, values)
            rows.append(
                A1RhsSourceDecompositionAudit(
                    mode_name=mode,
                    station_local_index=int(local_index),
                    active_station_index=int(sweep.active_station_indices[local_index]),
                    solve_order_rank=int(rank),
                    source_name=source_name,
                    source_rhs_norm=float(np.linalg.norm(source_rhs[source_name])),
                    total_rhs_norm=total_rhs_norm,
                    source_rhs_to_total_rhs_norm_ratio=_safe_norm_ratio(source_rhs[source_name], system.rhs),
                    full_solution_norm=full_norm,
                    source_solution_norm=float(np.linalg.norm(values)),
                    source_solution_to_full_solution_norm_ratio=_safe_norm_ratio(values, total_values),
                    body_potential_norm=float(np.linalg.norm(split.body_potential)),
                    inner_free_surface_normal_derivative_norm=float(
                        np.linalg.norm(split.inner_free_surface_normal_derivative)
                    ),
                    control_potential_norm=float(np.linalg.norm(split.control_potential)),
                    control_normal_derivative_norm=float(np.linalg.norm(split.control_normal_derivative)),
                    source_to_full_real_alignment=_complex_vector_real_alignment(total_values, values),
                    source_to_full_phase_deg=_complex_vector_phase_deg(total_values, values),
                    source_sum_residual_norm=float(np.linalg.norm(source_sum_residual)),
                    source_sum_relative_residual=source_sum_relative,
                    validity=ValidityReport(
                        status=LINEAR_2P5D_RHS_SOURCE_DECOMPOSITION_STATUS,
                        reference_cases=("ma2005_wigley_iii_station_sweep",),
                        notes=(
                            "Splits one solved Eq.23-Eq.24 matched system into body-normal-velocity, "
                            "inner-free-surface-potential, and outer-control-history RHS source solutions. "
                            "This is a scale diagnostic, not a hydrodynamic-coefficient hard gate.",
                        ),
                    ),
                )
            )
        past_phi, past_phi_n = _prepend_control_history(past_phi, past_phi_n, solutions[local_index])
    return tuple(rows)


def audit_inner_free_surface_state_scale(
    sweep: StationHullMatchedHeavePitchSweep,
    *,
    mode_name: str = "heave",
) -> tuple[A1InnerFreeSurfaceStateAudit, ...]:
    """Reconstruct the real inner-free-surface state transfer and Eq. (19)-(22) update.

    The station sweep stores the free-surface potential/elevation immediately
    before each section solve and after the BIE-derived normal velocity has
    marched the state.  This audit recomputes both operations from stored
    station data: transfer from the previously solved station and the local
    staggered free-surface update.
    """

    mode = str(mode_name).strip().lower()
    if mode not in {"heave", "pitch"}:
        raise ValueError("mode_name must be 'heave' or 'pitch'.")
    station_count = int(len(sweep.x_m))
    if station_count < 1:
        raise ValueError("sweep must contain at least one station.")
    solve_order = tuple(int(index) for index in sweep.solve_order)
    if sorted(solve_order) != list(range(station_count)):
        raise ValueError("sweep.solve_order must be a permutation of station local indices.")

    solutions = sweep.heave_mode_solutions if mode == "heave" else sweep.pitch_mode_solutions
    potential_before_by_station = (
        sweep.heave_free_surface_potential_by_station
        if mode == "heave"
        else sweep.pitch_free_surface_potential_by_station
    )
    elevation_before_by_station = (
        sweep.heave_free_surface_elevation_by_station
        if mode == "heave"
        else sweep.pitch_free_surface_elevation_by_station
    )
    potential_after_by_station = (
        sweep.heave_free_surface_potential_after_station
        if mode == "heave"
        else sweep.pitch_free_surface_potential_after_station
    )
    elevation_after_by_station = (
        sweep.heave_free_surface_elevation_after_station
        if mode == "heave"
        else sweep.pitch_free_surface_elevation_after_station
    )
    update_kinds = (
        sweep.heave_free_surface_update_kind_by_station
        if mode == "heave"
        else sweep.pitch_free_surface_update_kind_by_station
    )
    state_time_before_by_station = (
        sweep.heave_free_surface_time_before_by_station
        if mode == "heave"
        else sweep.pitch_free_surface_time_before_by_station
    )
    state_time_after_by_station = (
        sweep.heave_free_surface_time_after_by_station
        if mode == "heave"
        else sweep.pitch_free_surface_time_after_by_station
    )
    if len(solutions) != station_count:
        raise ValueError(f"{mode} solution count must match the active station count.")
    if len(update_kinds) != station_count:
        raise ValueError(f"{mode} update-kind count must match the active station count.")
    if np.asarray(sweep.local_time_s_by_station).shape != (station_count,):
        raise ValueError("sweep.local_time_s_by_station must be recorded for every station.")
    if np.asarray(state_time_before_by_station).shape != (station_count,):
        raise ValueError(f"{mode} free-surface time before solve must be recorded for every station.")
    if np.asarray(state_time_after_by_station).shape != (station_count,):
        raise ValueError(f"{mode} free-surface time after update must be recorded for every station.")
    if sweep.inner_free_surface_y_by_station.shape[:1] != (station_count,):
        raise ValueError("sweep.inner_free_surface_y_by_station must be recorded for every station.")
    if sweep.history_dt_s <= 0.0 or not np.isfinite(sweep.history_dt_s):
        raise ValueError("sweep.history_dt_s must be recorded and positive.")

    dt = float(sweep.history_dt_s)
    gravity = float(sweep.history_gravity_m_s2)
    rows: list[A1InnerFreeSurfaceStateAudit] = []
    previous_local_index = -1
    for rank, local_index in enumerate(solve_order):
        y = np.asarray(sweep.inner_free_surface_y_by_station[local_index], dtype=float)
        potential_before = np.asarray(potential_before_by_station[local_index], dtype=complex)
        elevation_before = np.asarray(elevation_before_by_station[local_index], dtype=complex)
        potential_after = np.asarray(potential_after_by_station[local_index], dtype=complex)
        elevation_after = np.asarray(elevation_after_by_station[local_index], dtype=complex)
        expected_local_time = float(sweep.local_time_s_by_station[local_index])
        state_time_before = float(state_time_before_by_station[local_index])
        state_time_after = float(state_time_after_by_station[local_index])
        if potential_before.shape != y.shape or elevation_before.shape != y.shape:
            raise ValueError(f"{mode} stored free-surface state before solve must match the station y grid.")
        if potential_after.shape != y.shape or elevation_after.shape != y.shape:
            raise ValueError(f"{mode} stored free-surface state after update must match the station y grid.")

        vertical_velocity = (
            float(sweep.free_surface_velocity_scale)
            * np.asarray(solutions[local_index].inner_free_surface_normal_derivative, dtype=complex)
        )
        if vertical_velocity.shape != y.shape:
            raise ValueError(f"{mode} inner-free-surface normal derivative must match the station y grid.")

        if bool(sweep.use_free_surface_marching):
            if previous_local_index >= 0:
                previous_state = FreeSurfaceMarchingState(
                    y_m=np.asarray(sweep.inner_free_surface_y_by_station[previous_local_index], dtype=float),
                    elevation_m=np.asarray(elevation_after_by_station[previous_local_index], dtype=complex),
                    potential_m2_s=np.asarray(potential_after_by_station[previous_local_index], dtype=complex),
                    time_s=float(state_time_after_by_station[previous_local_index]),
                    half_step_time_s=(
                        float(state_time_after_by_station[previous_local_index])
                        - 0.5 * float(sweep.free_surface_time_direction_sign) * dt
                    ),
                    validity=ValidityReport(
                        status=LINEAR_2P5D_FREE_SURFACE_STATUS,
                        reference_cases=("ma2005_wigley_iii_station_sweep",),
                    ),
                )
                transferred = resample_free_surface_state(previous_state, y)
                expected_potential_before = np.asarray(transferred.potential_m2_s, dtype=complex)
                expected_elevation_before = np.asarray(transferred.elevation_m, dtype=complex)
            else:
                expected_potential_before = np.zeros_like(potential_before)
                expected_elevation_before = np.zeros_like(elevation_before)

            kind = str(update_kinds[local_index])
            if kind.startswith("initialize_eq21_22"):
                expected_state_after = advance_free_surface_state_with_substeps(
                    None,
                    y,
                    vertical_velocity,
                    dt_s=dt,
                    substeps_per_station=int(sweep.free_surface_substeps_per_station),
                    gravity_m_s2=gravity,
                    time_direction_sign=float(sweep.free_surface_time_direction_sign),
                    dynamic_gravity_sign=float(sweep.free_surface_dynamic_gravity_sign),
                    potential_elevation_level=str(sweep.free_surface_potential_elevation_level),
                )
                expected_elevation_after = np.asarray(expected_state_after.elevation_m, dtype=complex)
                expected_potential_after = np.asarray(expected_state_after.potential_m2_s, dtype=complex)
                update_potential_base = np.zeros_like(potential_before)
                update_elevation_base = np.zeros_like(elevation_before)
            elif kind.startswith("advance_eq19_20"):
                state_before = FreeSurfaceMarchingState(
                    y_m=y,
                    elevation_m=elevation_before,
                    potential_m2_s=potential_before,
                    time_s=state_time_before,
                    half_step_time_s=(
                        state_time_before - 0.5 * float(sweep.free_surface_time_direction_sign) * dt
                    ),
                    validity=ValidityReport(
                        status=LINEAR_2P5D_FREE_SURFACE_STATUS,
                        reference_cases=("ma2005_wigley_iii_station_sweep",),
                    ),
                )
                expected_state_after = advance_free_surface_state_with_substeps(
                    state_before,
                    y,
                    vertical_velocity,
                    dt_s=dt,
                    substeps_per_station=int(sweep.free_surface_substeps_per_station),
                    gravity_m_s2=gravity,
                    time_direction_sign=float(sweep.free_surface_time_direction_sign),
                    dynamic_gravity_sign=float(sweep.free_surface_dynamic_gravity_sign),
                    potential_elevation_level=str(sweep.free_surface_potential_elevation_level),
                )
                expected_elevation_after = np.asarray(expected_state_after.elevation_m, dtype=complex)
                expected_potential_after = np.asarray(expected_state_after.potential_m2_s, dtype=complex)
                update_potential_base = potential_before
                update_elevation_base = elevation_before
            else:
                raise ValueError(f"Unsupported free-surface update kind {kind!r}.")
        else:
            expected_potential_before = np.zeros_like(potential_before)
            expected_elevation_before = np.zeros_like(elevation_before)
            expected_potential_after = np.zeros_like(potential_after)
            expected_elevation_after = np.zeros_like(elevation_after)
            update_potential_base = np.zeros_like(potential_before)
            update_elevation_base = np.zeros_like(elevation_before)
            kind = "disabled"

        if bool(sweep.use_free_surface_marching):
            expected_time_after = expected_local_time + float(sweep.free_surface_time_direction_sign) * dt
            time_before_residual = abs(state_time_before - expected_local_time)
            time_after_residual = abs(state_time_after - expected_time_after)
        else:
            expected_time_after = float("nan")
            time_before_residual = float("nan")
            time_after_residual = float("nan")

        transfer_potential_residual = potential_before - expected_potential_before
        transfer_elevation_residual = elevation_before - expected_elevation_before
        potential_update_residual = potential_after - expected_potential_after
        elevation_update_residual = elevation_after - expected_elevation_after
        update_residual = np.concatenate([potential_update_residual, elevation_update_residual])
        update_reference = np.concatenate([potential_after, elevation_after])
        expected_update_reference = np.concatenate([expected_potential_after, expected_elevation_after])
        transfer_residual = np.concatenate([transfer_potential_residual, transfer_elevation_residual])
        transfer_reference = np.concatenate([potential_before, elevation_before])
        expected_transfer_reference = np.concatenate([expected_potential_before, expected_elevation_before])

        potential_increment = potential_after - update_potential_base
        elevation_increment = elevation_after - update_elevation_base
        gravity_elevation_scale = gravity * dt * elevation_after
        rows.append(
            A1InnerFreeSurfaceStateAudit(
                mode_name=mode,
                station_local_index=int(local_index),
                active_station_index=int(sweep.active_station_indices[local_index]),
                solve_order_rank=int(rank),
                previous_station_local_index=int(previous_local_index),
                update_kind=kind,
                free_surface_panel_count=int(y.size),
                history_dt_s=dt,
                free_surface_velocity_scale=float(sweep.free_surface_velocity_scale),
                gravity_m_s2=gravity,
                y_min_m=float(np.min(y)) if y.size else 0.0,
                y_max_m=float(np.max(y)) if y.size else 0.0,
                potential_before_norm=float(np.linalg.norm(potential_before)),
                elevation_before_norm=float(np.linalg.norm(elevation_before)),
                vertical_velocity_norm=float(np.linalg.norm(vertical_velocity)),
                potential_after_norm=float(np.linalg.norm(potential_after)),
                elevation_after_norm=float(np.linalg.norm(elevation_after)),
                expected_potential_after_norm=float(np.linalg.norm(expected_potential_after)),
                expected_elevation_after_norm=float(np.linalg.norm(expected_elevation_after)),
                potential_update_increment_norm=float(np.linalg.norm(potential_increment)),
                elevation_update_increment_norm=float(np.linalg.norm(elevation_increment)),
                update_residual_norm=float(np.linalg.norm(update_residual)),
                update_relative_residual=_relative_history_array_residual(
                    update_residual,
                    update_reference,
                    expected_update_reference,
                ),
                update_max_abs_residual=float(np.max(np.abs(update_residual))) if update_residual.size else 0.0,
                transfer_residual_norm=float(np.linalg.norm(transfer_residual)),
                transfer_relative_residual=_relative_history_array_residual(
                    transfer_residual,
                    transfer_reference,
                    expected_transfer_reference,
                ),
                transfer_max_abs_residual=float(np.max(np.abs(transfer_residual))) if transfer_residual.size else 0.0,
                potential_growth_ratio=_safe_norm_ratio(potential_after, potential_before),
                elevation_growth_ratio=_safe_norm_ratio(elevation_after, elevation_before),
                vertical_velocity_to_elevation_increment_ratio=_safe_norm_ratio(
                    elevation_increment,
                    vertical_velocity * dt,
                ),
                potential_increment_to_gravity_elevation_ratio=_safe_norm_ratio(
                    potential_increment,
                    gravity_elevation_scale,
                ),
                velocity_elevation_increment_real_alignment=_complex_vector_real_alignment(
                    vertical_velocity * dt,
                    elevation_increment,
                ),
                velocity_elevation_increment_phase_deg=_complex_vector_phase_deg(
                    vertical_velocity * dt,
                    elevation_increment,
                ),
                elevation_potential_increment_real_alignment=_complex_vector_real_alignment(
                    gravity_elevation_scale,
                    -potential_increment,
                ),
                elevation_potential_increment_phase_deg=_complex_vector_phase_deg(
                    gravity_elevation_scale,
                    -potential_increment,
                ),
                before_after_potential_real_alignment=_complex_vector_real_alignment(
                    potential_before,
                    potential_after,
                ),
                before_after_potential_phase_deg=_complex_vector_phase_deg(potential_before, potential_after),
                expected_local_time_s=expected_local_time,
                free_surface_state_time_before_s=state_time_before,
                free_surface_state_time_after_s=state_time_after,
                time_before_abs_residual_s=float(time_before_residual),
                time_after_abs_residual_s=float(time_after_residual),
                validity=ValidityReport(
                    status=LINEAR_2P5D_INNER_FREE_SURFACE_STATE_STATUS,
                    reference_cases=("ma2005_wigley_iii_station_sweep",),
                    notes=(
                        "Reconstructs station-to-station inner-free-surface state transfer and the local "
                        "A1 Eq.19-Eq.22 staggered update using the BIE-derived free-surface normal derivative. "
                        "This is a state-scale diagnostic, not a hydrodynamic-coefficient hard gate.",
                    ),
                ),
            )
        )
        previous_local_index = int(local_index)
    return tuple(rows)


def solve_station_hull_heave_pitch_matched_sweep(
    hull: StationHull,
    omega_rad_s: float,
    speed_mps: float,
    *,
    config: Linear2p5DProviderConfig | None = None,
    rho_water_kg_m3: float = 1025.0,
    parametric_section_shape: str = "wigley",
    history_steps: int = 40,
    history_quadrature_count: int = 32,
    history_k_max: float = 25.0,
    include_end_term: bool | None = None,
    end_station: str = "aft",
    end_term_scale: float = 1.0,
    pitch_radiation_sign: float = 1.0,
    pitch_radiation_lever_sign: float = 1.0,
    pitch_forward_speed_sign: float = 1.0,
    pitch_oscillation_scale: float = 1.0,
    pitch_forward_speed_scale: float = 1.0,
    pitch_moment_sign: float = 1.0,
    time_step_scale: float = 1.0,
    free_surface_substeps_per_station: int = 1,
    free_surface_velocity_scale: float = 1.0,
    free_surface_normal_derivative_source: str = "raw",
    free_surface_time_direction_sign: float = 1.0,
    free_surface_dynamic_gravity_sign: float = -1.0,
    free_surface_potential_elevation_level: str = "updated",
    control_row_free_surface_potential_source: str = "shared",
    history_rhs_scale: float = 1.0,
    history_convolution_rule: str = "trapezoid",
    history_potential_kernel_scale: float = 1.0,
    history_normal_derivative_kernel_scale: float = 1.0,
    control_image_scale: float = 1.0,
    control_potential_kernel_scale: float = 1.0,
    control_normal_derivative_kernel_scale: float = 1.0,
    control_diagonal_sign: float = 1.0,
    inner_a_scale: float = 1.0,
    inner_b_scale: float = 1.0,
    inner_diagonal_sign: float = -1.0,
    inner_free_surface_self_diagonal_scale: float = 1.0,
    inner_free_surface_known_potential_rhs_scale: float = 1.0,
    inner_free_surface_known_potential_body_row_scale: float = 1.0,
    inner_free_surface_known_potential_free_row_scale: float = 1.0,
    inner_free_surface_known_potential_control_row_scale: float = 1.0,
    inner_free_surface_unknown_normal_column_scale: float = 1.0,
    pressure_gradient_scheme: str = "central",
    pressure_gradient_scale: float = 1.0,
    force_assembly_route: str = "eq32_stokes_body_plus_end",
    apply_local_time_phase: bool = True,
    local_time_phase_x0_m: float | None = None,
    local_time_phase_gradient_correction: bool = True,
    clip_inner_free_surface_to_waterline: bool = True,
    two_zone_inner_free_surface: bool = False,
    use_free_surface_marching: bool = True,
    active_min_beam_m: float = 1e-8,
    active_min_area_m2: float = 1e-12,
    waterline_grading_exponent: float = 1.0,
    heave_body_normal_velocity_base: Callable[
        [int, float, InnerDomainPanelGeometry], np.ndarray
    ]
    | None = None,
    heave_body_condition_source: str = "unit_heave_radiation",
) -> StationHullMatchedHeavePitchSweep:
    """Run a history-seeded matched heave/pitch station sweep for a StationHull.

    This is the first whole-hull bridge into the Ma-Duan-Song matched BIE
    plumbing. It solves stations from bow to stern so the control-surface
    history has the correct marching direction, then returns arrays ordered by
    increasing StationHull `x_m` for integration.
    """

    cfg = Linear2p5DProviderConfig() if config is None else config
    cfg.validate()
    omega = float(omega_rad_s)
    speed = float(speed_mps)
    if omega <= 0.0:
        raise ValueError("omega_rad_s must be positive.")
    if speed <= 0.0:
        raise ValueError("speed_mps must be positive for a 2.5D station sweep.")
    if history_steps < 1:
        raise ValueError("history_steps must be positive.")
    end_scale = float(end_term_scale)
    if not np.isfinite(end_scale):
        raise ValueError("end_term_scale must be finite.")
    pitch_rad_sign = float(pitch_radiation_sign)
    pitch_lever_sign = float(pitch_radiation_lever_sign)
    pitch_speed_sign = float(pitch_forward_speed_sign)
    pitch_osc_scale = float(pitch_oscillation_scale)
    pitch_fwd_scale = float(pitch_forward_speed_scale)
    pitch_row_sign = float(pitch_moment_sign)
    dt_scale = float(time_step_scale)
    free_substeps = int(free_surface_substeps_per_station)
    free_velocity_scale = float(free_surface_velocity_scale)
    free_normal_source = str(free_surface_normal_derivative_source).strip().lower()
    free_time_sign = float(free_surface_time_direction_sign)
    free_dynamic_sign = float(free_surface_dynamic_gravity_sign)
    free_elevation_level = str(free_surface_potential_elevation_level).strip().lower()
    control_row_free_source = str(control_row_free_surface_potential_source).strip().lower()
    control_row_source_aliases = {
        "default": "shared",
        "same": "shared",
        "current": "shared",
        "before": "before_station",
        "before_station": "before_station",
        "zero": "zero_no_marching",
        "zero_no_marching": "zero_no_marching",
        "after": "after_station",
        "after_station": "after_station",
        "half": "half_step_interpolated",
        "half_step": "half_step_interpolated",
        "half_step_interpolated": "half_step_interpolated",
        "extrapolated": "extrapolated",
    }
    control_row_free_source = control_row_source_aliases.get(control_row_free_source, control_row_free_source)
    history_scale = float(history_rhs_scale)
    history_rule = str(history_convolution_rule).strip().lower()
    history_potential_scale = float(history_potential_kernel_scale)
    history_normal_scale = float(history_normal_derivative_kernel_scale)
    control_image = float(control_image_scale)
    control_potential_scale = float(control_potential_kernel_scale)
    control_normal_scale = float(control_normal_derivative_kernel_scale)
    control_diag_sign = float(control_diagonal_sign)
    inner_a = float(inner_a_scale)
    inner_b = float(inner_b_scale)
    inner_diag_sign = float(inner_diagonal_sign)
    free_self_diag_scale = float(inner_free_surface_self_diagonal_scale)
    free_known_rhs_scale = float(inner_free_surface_known_potential_rhs_scale)
    free_known_body_row_scale = float(inner_free_surface_known_potential_body_row_scale)
    free_known_free_row_scale = float(inner_free_surface_known_potential_free_row_scale)
    free_known_control_row_scale = float(inner_free_surface_known_potential_control_row_scale)
    free_unknown_column_scale = float(inner_free_surface_unknown_normal_column_scale)
    gradient_scheme = str(pressure_gradient_scheme).strip().lower()
    if gradient_scheme not in {"central", "forward", "backward"}:
        raise ValueError("pressure_gradient_scheme must be 'central', 'forward', or 'backward'.")
    pressure_grad_scale = float(pressure_gradient_scale)
    assembly_route = str(force_assembly_route).strip().lower()
    phase_gradient_correction = bool(local_time_phase_gradient_correction)
    phase_x0 = float(hull.length_m if local_time_phase_x0_m is None else local_time_phase_x0_m)
    finite_values = (
        pitch_rad_sign,
        pitch_lever_sign,
        pitch_speed_sign,
        pitch_osc_scale,
        pitch_fwd_scale,
        pitch_row_sign,
        dt_scale,
        free_velocity_scale,
        free_time_sign,
        free_dynamic_sign,
        history_scale,
        history_potential_scale,
        history_normal_scale,
        control_image,
        control_potential_scale,
        control_normal_scale,
        control_diag_sign,
        inner_a,
        inner_b,
        inner_diag_sign,
        free_self_diag_scale,
        free_known_rhs_scale,
        free_known_body_row_scale,
        free_known_free_row_scale,
        free_known_control_row_scale,
        free_unknown_column_scale,
        pressure_grad_scale,
        phase_x0,
    )
    if not all(np.isfinite(value) for value in finite_values):
        raise ValueError("pitch convention, free-surface, and pressure-gradient diagnostic scales must be finite.")
    if abs(free_time_sign) <= 1e-12:
        raise ValueError("free_surface_time_direction_sign must be non-zero.")
    if free_normal_source not in {
        "raw",
        "current_raw",
        "real_part_only",
        "real_only",
        "imaginary_part_only",
        "imag_only",
        "phase_lead_90",
        "phase_lag_90",
        "body_velocity_norm_normalized",
    }:
        raise ValueError(
            "free_surface_normal_derivative_source must be one of raw, real_part_only, imaginary_part_only, "
            "phase_lead_90, phase_lag_90, or body_velocity_norm_normalized."
        )
    if free_elevation_level not in {"updated", "previous", "average"}:
        raise ValueError("free_surface_potential_elevation_level must be 'updated', 'previous', or 'average'.")
    if control_row_free_source not in {
        "shared",
        "before_station",
        "zero_no_marching",
        "after_station",
        "half_step_interpolated",
        "extrapolated",
    }:
        raise ValueError(
            "control_row_free_surface_potential_source must be 'shared', 'before_station', "
            "'zero_no_marching', 'after_station', 'half_step_interpolated', or 'extrapolated'."
        )
    if history_rule not in {"rectangle", "trapezoid"}:
        raise ValueError("history_convolution_rule must be 'rectangle' or 'trapezoid'.")
    if dt_scale <= 0.0:
        raise ValueError("time_step_scale must be positive.")
    if free_substeps < 1:
        raise ValueError("free_surface_substeps_per_station must be a positive integer.")

    active_pairs = tuple(
        (index, station)
        for index, station in enumerate(hull.stations)
        if station.waterplane_beam_m() > float(active_min_beam_m)
        and station.submerged_area_m2() > float(active_min_area_m2)
    )
    if len(active_pairs) < 2:
        raise ValueError("At least two active stations are required for matched station sweep assembly.")
    active_indices = tuple(index for index, _ in active_pairs)
    x = np.asarray([station.x_m for _, station in active_pairs], dtype=float)
    base_lever_arms = hull.lcg_m - x
    pitch_radiation_lever_arms = pitch_lever_sign * base_lever_arms
    pitch_moment_lever_arms = pitch_row_sign * base_lever_arms
    max_beam = max(float(station.waterplane_beam_m()) for _, station in active_pairs)
    max_draft = max(float(station.effective_draft_m()) for _, station in active_pairs)
    radius = max(float(cfg.control_surface_radius_beams) * max_beam, 1.25 * max_draft, 1e-6)
    control = build_control_surface_geometry(radius_m=radius, panel_count=int(cfg.free_surface_outer_panels))
    free_panel_count = int(cfg.free_surface_inner_panels)
    two_zone = bool(two_zone_inner_free_surface)
    grading = float(waterline_grading_exponent)
    if not np.isfinite(grading) or not 1.0 <= grading <= 2.0:
        raise ValueError('waterline_grading_exponent must be finite and between 1 and 2')
    if grading != 1.0 and (two_zone or not clip_inner_free_surface_to_waterline):
        raise ValueError('Waterline grading requires single-zone clipped free surface')
    if two_zone and not bool(clip_inner_free_surface_to_waterline):
        raise ValueError("two_zone_inner_free_surface requires clip_inner_free_surface_to_waterline.")
    if two_zone and (free_panel_count < 4 or free_panel_count % 2 != 0):
        raise ValueError("two_zone_inner_free_surface requires an even free_surface_inner_panels value of at least 4.")
    if bool(clip_inner_free_surface_to_waterline):
        if two_zone:
            panels_per_side = free_panel_count // 2
            inner_panels_per_side = max(1, int(round(0.6 * panels_per_side)))
            outer_panels_per_side = max(1, panels_per_side - inner_panels_per_side)
            if inner_panels_per_side + outer_panels_per_side != panels_per_side:
                inner_panels_per_side = panels_per_side - outer_panels_per_side
            free_geometries = tuple(
                build_two_zone_waterline_free_surface_geometry(
                    -radius,
                    radius,
                    0.5 * float(station.waterplane_beam_m()),
                    0.5 * max_beam,
                    inner_panel_count_per_side=inner_panels_per_side,
                    outer_panel_count_per_side=outer_panels_per_side,
                )
                for _, station in active_pairs
            )
        else:
            free_geometries = tuple(
                build_waterline_clipped_free_surface_geometry(
                    -radius,
                    radius,
                    0.5 * float(station.waterplane_beam_m()),
                    panel_count=free_panel_count,
                    grading_exponent=grading,
                )
                for _, station in active_pairs
            )
    else:
        shared_free = build_flat_free_surface_geometry(-radius, radius, panel_count=free_panel_count)
        free_geometries = tuple(shared_free for _ in active_pairs)
    dx = np.diff(x)
    dt = float(np.median(dx) / speed * dt_scale)
    local_time_s = (phase_x0 - x) / speed
    local_phase = np.exp(1j * omega * local_time_s) if bool(apply_local_time_phase) else np.ones_like(x, dtype=complex)
    pressure_dephase = np.conjugate(local_phase)
    history = build_transient_free_surface_history(
        control,
        dt_s=dt,
        history_steps=int(history_steps),
        quadrature_count=int(history_quadrature_count),
        k_max=float(history_k_max),
    )
    point_count_per_side = max(4, int(cfg.body_panels_per_section) // 2)
    bodies = tuple(
        build_inner_domain_panel_geometry(
            _station_offsets_for_matched_2p5d(
                station,
                parametric_section_shape=parametric_section_shape,
                point_count_per_side=point_count_per_side,
            ),
            body_panel_count=int(cfg.body_panels_per_section),
        )
        for _, station in active_pairs
    )
    heave_condition_source = str(heave_body_condition_source).strip()
    if not heave_condition_source:
        raise ValueError("heave_body_condition_source must be non-empty.")
    if heave_body_normal_velocity_base is not None and heave_condition_source == "unit_heave_radiation":
        heave_condition_source = "caller_supplied_body_normal_velocity"

    solver = Matched2p5DSectionSolver(cfg)
    heave_solutions: list[MatchedSectionSolution | None] = [None] * len(active_pairs)
    pitch_solutions: list[MatchedSectionSolution | None] = [None] * len(active_pairs)
    heave_audits: list[MatchedSystemBlockAudit | None] = [None] * len(active_pairs)
    pitch_audits: list[MatchedSystemBlockAudit | None] = [None] * len(active_pairs)
    heave_conditions = np.zeros(len(active_pairs), dtype=float)
    pitch_conditions = np.zeros(len(active_pairs), dtype=float)
    heave_residuals = np.zeros(len(active_pairs), dtype=float)
    pitch_residuals = np.zeros(len(active_pairs), dtype=float)
    heave_free_potential_by_station = np.zeros((len(active_pairs), free_panel_count), dtype=complex)
    pitch_free_potential_by_station = np.zeros_like(heave_free_potential_by_station)
    heave_free_elevation_by_station = np.zeros_like(heave_free_potential_by_station)
    pitch_free_elevation_by_station = np.zeros_like(heave_free_potential_by_station)
    heave_free_potential_after_station = np.zeros_like(heave_free_potential_by_station)
    pitch_free_potential_after_station = np.zeros_like(heave_free_potential_by_station)
    heave_free_elevation_after_station = np.zeros_like(heave_free_potential_by_station)
    pitch_free_elevation_after_station = np.zeros_like(heave_free_potential_by_station)
    heave_free_time_before_by_station = np.full(len(active_pairs), np.nan, dtype=float)
    pitch_free_time_before_by_station = np.full(len(active_pairs), np.nan, dtype=float)
    heave_free_time_after_by_station = np.full(len(active_pairs), np.nan, dtype=float)
    pitch_free_time_after_by_station = np.full(len(active_pairs), np.nan, dtype=float)
    heave_outer_history_rhs_by_station = np.zeros((len(active_pairs), control.panel_count), dtype=complex)
    pitch_outer_history_rhs_by_station = np.zeros_like(heave_outer_history_rhs_by_station)
    pitch_body_condition_oscillation_by_station = np.zeros(
        (len(active_pairs), int(cfg.body_panels_per_section)),
        dtype=complex,
    )
    pitch_body_condition_forward_speed_by_station = np.zeros_like(pitch_body_condition_oscillation_by_station)
    heave_body_condition_by_station = np.zeros_like(pitch_body_condition_oscillation_by_station)
    free_y_by_station = np.zeros((len(active_pairs), free_panel_count), dtype=float)
    free_length_by_station = np.zeros_like(free_y_by_station)
    heave_update_kind_by_station = ["not_solved"] * len(active_pairs)
    pitch_update_kind_by_station = ["not_solved"] * len(active_pairs)
    heave_past_phi = np.zeros((int(history_steps), control.panel_count), dtype=complex)
    heave_past_phi_n = np.zeros_like(heave_past_phi)
    pitch_past_phi = np.zeros_like(heave_past_phi)
    pitch_past_phi_n = np.zeros_like(heave_past_phi)
    solve_order = tuple(range(len(active_pairs) - 1, -1, -1))
    first_free = free_geometries[solve_order[0]]
    heave_free_state = initialize_free_surface_state(
        first_free.mid_y_m,
        np.zeros(free_panel_count, dtype=complex),
        dt_s=dt,
        time_direction_sign=free_time_sign,
        dynamic_gravity_sign=free_dynamic_sign,
        potential_elevation_level=free_elevation_level,
    )
    pitch_free_state = initialize_free_surface_state(
        first_free.mid_y_m,
        np.zeros(free_panel_count, dtype=complex),
        dt_s=dt,
        time_direction_sign=free_time_sign,
        dynamic_gravity_sign=free_dynamic_sign,
        potential_elevation_level=free_elevation_level,
    )
    # The undisturbed bow state has already been initialized through A1
    # Eqs. (21)-(22) at t=dt.  The first active section must therefore use
    # Eqs. (19)-(20); reinitializing it would leave every later state one
    # longitudinal station behind its physical local time.
    heave_has_free_surface_velocity = True
    pitch_has_free_surface_velocity = True

    def solve_mode_with_control_row_source(
        *,
        body: InnerDomainPanelGeometry,
        free: InnerDomainPanelGeometry,
        body_velocity: np.ndarray,
        free_potential_before: np.ndarray,
        free_state_before: FreeSurfaceMarchingState,
        has_free_surface_velocity: bool,
        past_phi: np.ndarray,
        past_phi_n: np.ndarray,
    ) -> tuple[MatchedSectionSolution, float, float, MatchedSystemBlockAudit]:
        def solve_with(control_row_potential: np.ndarray | None):
            return _solve_one_matched_station_mode(
                solver,
                body=body,
                free=free,
                control=control,
                history=history,
                body_normal_velocity=body_velocity,
                free_surface_potential=free_potential_before,
                free_surface_potential_control_row=control_row_potential,
                past_control_potential=past_phi,
                past_control_normal_derivative=past_phi_n,
                history_rhs_scale=history_scale,
                history_convolution_rule=history_rule,
                history_potential_kernel_scale=history_potential_scale,
                history_normal_derivative_kernel_scale=history_normal_scale,
                control_image_scale=control_image,
                control_potential_kernel_scale=control_potential_scale,
                control_normal_derivative_kernel_scale=control_normal_scale,
                control_diagonal_sign=control_diag_sign,
                inner_a_scale=inner_a,
                inner_b_scale=inner_b,
                inner_diagonal_sign=inner_diag_sign,
                inner_free_surface_self_diagonal_scale=free_self_diag_scale,
                inner_free_surface_known_potential_rhs_scale=free_known_rhs_scale,
                inner_free_surface_known_potential_body_row_scale=free_known_body_row_scale,
                inner_free_surface_known_potential_free_row_scale=free_known_free_row_scale,
                inner_free_surface_known_potential_control_row_scale=free_known_control_row_scale,
                inner_free_surface_unknown_normal_column_scale=free_unknown_column_scale,
            )

        if control_row_free_source == "shared":
            return solve_with(None)
        if control_row_free_source == "before_station":
            return solve_with(free_potential_before)
        if control_row_free_source == "zero_no_marching" or not use_free_surface_marching:
            return solve_with(np.zeros_like(free_potential_before, dtype=complex))

        predictor_solution, _, _, _ = solve_with(None)
        predictor_velocity = free_velocity_scale * _free_surface_marching_velocity_from_normal_derivative(
            predictor_solution.inner_free_surface_normal_derivative,
            source=free_normal_source,
            body_normal_velocity=body_velocity,
        )
        predicted_state = advance_free_surface_state_with_substeps(
            free_state_before if has_free_surface_velocity else None,
            free.mid_y_m,
            predictor_velocity,
            dt_s=dt,
            substeps_per_station=free_substeps,
            time_direction_sign=free_time_sign,
            dynamic_gravity_sign=free_dynamic_sign,
            potential_elevation_level=free_elevation_level,
        )
        predicted_after = np.asarray(predicted_state.potential_m2_s, dtype=complex)
        if control_row_free_source == "after_station":
            control_row_potential = predicted_after
        elif control_row_free_source == "half_step_interpolated":
            control_row_potential = 0.5 * (np.asarray(free_potential_before, dtype=complex) + predicted_after)
        elif control_row_free_source == "extrapolated":
            control_row_potential = 2.0 * predicted_after - np.asarray(free_potential_before, dtype=complex)
        else:  # Defensive guard after validation above.
            control_row_potential = None
        return solve_with(control_row_potential)

    for local_index in solve_order:
        body = bodies[local_index]
        free = free_geometries[local_index]
        free_y_by_station[local_index] = free.mid_y_m
        free_length_by_station[local_index] = free.length_m
        heave_free_state = resample_free_surface_state(heave_free_state, free.mid_y_m)
        pitch_free_state = resample_free_surface_state(pitch_free_state, free.mid_y_m)
        if use_free_surface_marching:
            heave_free_time_before_by_station[local_index] = float(heave_free_state.time_s)
            pitch_free_time_before_by_station[local_index] = float(pitch_free_state.time_s)
        heave_free_potential = (
            heave_free_state.potential_m2_s if use_free_surface_marching else np.zeros(free_panel_count, dtype=complex)
        )
        pitch_free_potential = (
            pitch_free_state.potential_m2_s if use_free_surface_marching else np.zeros(free_panel_count, dtype=complex)
        )
        heave_free_potential_by_station[local_index] = heave_free_potential
        pitch_free_potential_by_station[local_index] = pitch_free_potential
        heave_free_elevation_by_station[local_index] = (
            heave_free_state.elevation_m if use_free_surface_marching else np.zeros(free_panel_count, dtype=complex)
        )
        pitch_free_elevation_by_station[local_index] = (
            pitch_free_state.elevation_m if use_free_surface_marching else np.zeros(free_panel_count, dtype=complex)
        )
        heave_outer_history_rhs_by_station[local_index] = history.convolution_rhs(
            heave_past_phi,
            heave_past_phi_n,
            rhs_scale=history_scale,
            quadrature_rule=history_rule,
            potential_kernel_scale=history_potential_scale,
            normal_derivative_kernel_scale=history_normal_scale,
        )
        if heave_body_normal_velocity_base is None:
            heave_body_velocity_base = heave_radiation_normal_velocity(body, omega)
        else:
            heave_body_velocity_base = np.asarray(
                heave_body_normal_velocity_base(
                    int(local_index),
                    float(x[local_index]),
                    body,
                ),
                dtype=complex,
            )
            if heave_body_velocity_base.shape != (body.panel_count,):
                raise ValueError(
                    "heave_body_normal_velocity_base must return one value per body panel; "
                    f"station {local_index} returned {heave_body_velocity_base.shape}, "
                    f"expected ({body.panel_count},)."
                )
            if not np.isfinite(heave_body_velocity_base.real).all() or not np.isfinite(
                heave_body_velocity_base.imag
            ).all():
                raise ValueError(
                    f"heave_body_normal_velocity_base returned non-finite values at station {local_index}."
                )
        heave_body_velocity = local_phase[local_index] * heave_body_velocity_base
        heave_body_condition_by_station[local_index] = heave_body_velocity
        heave_solution, heave_condition, heave_residual, heave_block_audit = solve_mode_with_control_row_source(
            body=body,
            free=free,
            body_velocity=heave_body_velocity,
            free_potential_before=heave_free_potential,
            free_state_before=heave_free_state,
            has_free_surface_velocity=heave_has_free_surface_velocity,
            past_phi=heave_past_phi,
            past_phi_n=heave_past_phi_n,
        )
        heave_solutions[local_index] = heave_solution
        heave_audits[local_index] = heave_block_audit
        heave_conditions[local_index] = heave_condition
        heave_residuals[local_index] = heave_residual
        heave_past_phi, heave_past_phi_n = _prepend_control_history(
            heave_past_phi, heave_past_phi_n, heave_solution
        )
        if use_free_surface_marching:
            heave_vertical_velocity = free_velocity_scale * _free_surface_marching_velocity_from_normal_derivative(
                heave_solution.inner_free_surface_normal_derivative,
                source=free_normal_source,
                body_normal_velocity=heave_body_velocity,
            )
            heave_free_state = advance_free_surface_state_with_substeps(
                heave_free_state,
                free.mid_y_m,
                heave_vertical_velocity,
                dt_s=dt,
                substeps_per_station=free_substeps,
                time_direction_sign=free_time_sign,
                dynamic_gravity_sign=free_dynamic_sign,
                potential_elevation_level=free_elevation_level,
            )
            heave_update_kind_by_station[local_index] = (
                "advance_eq19_20"
                if free_substeps == 1
                else f"advance_eq19_20_substeps_{free_substeps}"
            )
            heave_free_potential_after_station[local_index] = heave_free_state.potential_m2_s
            heave_free_elevation_after_station[local_index] = heave_free_state.elevation_m
            heave_free_time_after_by_station[local_index] = float(heave_free_state.time_s)
        else:
            heave_update_kind_by_station[local_index] = "disabled"

        pitch_outer_history_rhs_by_station[local_index] = history.convolution_rhs(
            pitch_past_phi,
            pitch_past_phi_n,
            rhs_scale=history_scale,
            quadrature_rule=history_rule,
            potential_kernel_scale=history_potential_scale,
            normal_derivative_kernel_scale=history_normal_scale,
        )
        pitch_oscillation_velocity, pitch_forward_velocity = pitch_radiation_normal_velocity_components(
            body,
            omega,
            float(pitch_radiation_lever_arms[local_index]),
            forward_speed_mps=speed,
            radiation_sign=pitch_rad_sign,
            forward_speed_sign=pitch_speed_sign,
        )
        pitch_oscillation_velocity = pitch_osc_scale * pitch_oscillation_velocity
        pitch_forward_velocity = pitch_fwd_scale * pitch_forward_velocity
        pitch_oscillation_velocity = local_phase[local_index] * pitch_oscillation_velocity
        pitch_forward_velocity = local_phase[local_index] * pitch_forward_velocity
        pitch_body_condition_oscillation_by_station[local_index] = pitch_oscillation_velocity
        pitch_body_condition_forward_speed_by_station[local_index] = pitch_forward_velocity
        pitch_body_velocity = pitch_oscillation_velocity + pitch_forward_velocity
        pitch_solution, pitch_condition, pitch_residual, pitch_block_audit = solve_mode_with_control_row_source(
            body=body,
            free=free,
            body_velocity=pitch_body_velocity,
            free_potential_before=pitch_free_potential,
            free_state_before=pitch_free_state,
            has_free_surface_velocity=pitch_has_free_surface_velocity,
            past_phi=pitch_past_phi,
            past_phi_n=pitch_past_phi_n,
        )
        pitch_solutions[local_index] = pitch_solution
        pitch_audits[local_index] = pitch_block_audit
        pitch_conditions[local_index] = pitch_condition
        pitch_residuals[local_index] = pitch_residual
        pitch_past_phi, pitch_past_phi_n = _prepend_control_history(
            pitch_past_phi, pitch_past_phi_n, pitch_solution
        )
        if use_free_surface_marching:
            pitch_vertical_velocity = free_velocity_scale * _free_surface_marching_velocity_from_normal_derivative(
                pitch_solution.inner_free_surface_normal_derivative,
                source=free_normal_source,
                body_normal_velocity=pitch_body_velocity,
            )
            pitch_free_state = advance_free_surface_state_with_substeps(
                pitch_free_state,
                free.mid_y_m,
                pitch_vertical_velocity,
                dt_s=dt,
                substeps_per_station=free_substeps,
                time_direction_sign=free_time_sign,
                dynamic_gravity_sign=free_dynamic_sign,
                potential_elevation_level=free_elevation_level,
            )
            pitch_update_kind_by_station[local_index] = (
                "advance_eq19_20"
                if free_substeps == 1
                else f"advance_eq19_20_substeps_{free_substeps}"
            )
            pitch_free_potential_after_station[local_index] = pitch_free_state.potential_m2_s
            pitch_free_elevation_after_station[local_index] = pitch_free_state.elevation_m
            pitch_free_time_after_by_station[local_index] = float(pitch_free_state.time_s)
        else:
            pitch_update_kind_by_station[local_index] = "disabled"

    heave_tuple = tuple(solution for solution in heave_solutions if solution is not None)
    pitch_tuple = tuple(solution for solution in pitch_solutions if solution is not None)
    pressure_heave_tuple = tuple(
        _scale_matched_section_solution(solution, pressure_dephase[index])
        for index, solution in enumerate(heave_tuple)
    )
    pressure_pitch_tuple = tuple(
        _scale_matched_section_solution(solution, pressure_dephase[index])
        for index, solution in enumerate(pitch_tuple)
    )
    heave_audit_tuple = tuple(audit for audit in heave_audits if audit is not None)
    pitch_audit_tuple = tuple(audit for audit in pitch_audits if audit is not None)
    selector = end_station.strip().lower()
    if selector == "aft":
        end_hull_index = 0
    elif selector in {"bow", "forward", "fore"}:
        selector = "bow"
        end_hull_index = len(hull.stations) - 1
    else:
        raise ValueError("end_station must be 'aft' or 'bow'.")
    end_hull_station = hull.stations[end_hull_index]
    end_active_index_by_hull_index = {
        hull_index: local_index for local_index, (hull_index, _) in enumerate(active_pairs)
    }
    end_active_local_index = end_active_index_by_hull_index.get(end_hull_index, -1)
    end_station_is_degenerate = bool(
        end_hull_station.waterplane_beam_m() <= 1.0e-12
        and end_hull_station.submerged_area_m2() <= 1.0e-14
    )

    use_end_term = cfg.include_end_terms if include_end_term is None else bool(include_end_term)
    end_term_result: StokesEndTermForceMatrix | None = None
    control_surface_end_term_result: StokesEndTermForceMatrix | None = None
    end_force_matrix: np.ndarray | None = None
    end_term_geometry_source = "disabled"
    if use_end_term:
        if end_active_local_index >= 0:
            end_index = int(end_active_local_index)
            end_term_result = compute_heave_pitch_stokes_end_term_force_matrix(
                bodies[end_index],
                pressure_heave_tuple[end_index],
                pressure_pitch_tuple[end_index],
                rho_water_kg_m3=rho_water_kg_m3,
                forward_speed_mps=speed,
                lever_arm_m=float(pitch_moment_lever_arms[end_index]),
            )
            control_surface_end_term_result = compute_heave_pitch_control_surface_end_term_force_matrix(
                control,
                pressure_heave_tuple[end_index],
                pressure_pitch_tuple[end_index],
                rho_water_kg_m3=rho_water_kg_m3,
                forward_speed_mps=speed,
                lever_arm_m=float(pitch_moment_lever_arms[end_index]),
            )
            end_term_geometry_source = "actual_active_hull_endpoint"
        elif end_station_is_degenerate:
            zero_matrix = np.zeros((2, 2), dtype=complex)
            endpoint_lever = pitch_row_sign * (hull.lcg_m - float(end_hull_station.x_m))
            end_term_result = StokesEndTermForceMatrix(
                complex_force_matrix=zero_matrix,
                forward_speed_mps=speed,
                rho_water_kg_m3=float(rho_water_kg_m3),
                lever_arm_m=float(endpoint_lever),
                row_labels=("heave_force", "pitch_moment"),
                column_labels=("heave_radiation", "pitch_radiation"),
                validity=ValidityReport(
                    status=LINEAR_2P5D_STOKES_END_TERM_STATUS,
                    reference_cases=("ma2005_wigley_iii", "a1_eq32"),
                    notes=(
                        "A1 Eq. (32) C_A is the actual geometric endpoint. The selected endpoint has zero "
                        "waterplane beam and submerged area, so its contour integral is exactly zero; the first "
                        "non-zero active section is not substituted.",
                    ),
                ),
            )
            control_surface_end_term_result = StokesEndTermForceMatrix(
                complex_force_matrix=zero_matrix.copy(),
                forward_speed_mps=speed,
                rho_water_kg_m3=float(rho_water_kg_m3),
                lever_arm_m=float(endpoint_lever),
                row_labels=("heave_force", "pitch_moment"),
                column_labels=("heave_radiation", "pitch_radiation"),
                validity=ValidityReport(
                    status=LINEAR_2P5D_CONTROL_SURFACE_END_TERM_STATUS,
                    reference_cases=("ma2005_wigley_iii", "a1_eq32"),
                    notes=(
                        "No fixed-control-surface endpoint diagnostic is inferred from a neighbouring section "
                        "when the physical hull endpoint contour is degenerate.",
                    ),
                ),
            )
            end_term_geometry_source = "actual_degenerate_hull_endpoint"
        else:
            raise ValueError(
                f"The selected {selector} endpoint at x={end_hull_station.x_m:.6g} m is non-degenerate but was "
                "excluded from the active matched-section sweep. Reduce active_min_beam_m/active_min_area_m2 "
                "or provide an endpoint solution; a neighbouring active section cannot represent A1 Eq. (32) C_A."
            )
        end_force_matrix = end_scale * end_term_result.complex_force_matrix
    heave_gradient_override: StationPotentialGradient | None = None
    pitch_gradient_override: StationPotentialGradient | None = None
    if bool(apply_local_time_phase) and phase_gradient_correction:
        heave_psi = np.asarray([solution.body_potential for solution in heave_tuple], dtype=complex)
        pitch_psi = np.asarray([solution.body_potential for solution in pitch_tuple], dtype=complex)
        heave_gradient_override = estimate_local_time_phase_body_potential_x_gradient(
            x,
            heave_psi,
            omega_rad_s=omega,
            speed_mps=speed,
            phase_factor=local_phase,
            scheme=gradient_scheme,
        )
        pitch_gradient_override = estimate_local_time_phase_body_potential_x_gradient(
            x,
            pitch_psi,
            omega_rad_s=omega,
            speed_mps=speed,
            phase_factor=local_phase,
            scheme=gradient_scheme,
        )
    pressure_force_sweep = assemble_heave_pitch_from_matched_station_solutions(
        x,
        bodies,
        pressure_heave_tuple,
        pressure_pitch_tuple,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        forward_speed_mps=speed,
        lever_arms_m=pitch_moment_lever_arms,
        end_term_force_matrix=end_force_matrix,
        pressure_gradient_scheme=gradient_scheme,
        pressure_gradient_scale=pressure_grad_scale,
        force_assembly_route=assembly_route,
        stokes_pitch_m5_sign=pitch_row_sign,
        heave_potential_gradient_override=heave_gradient_override,
        pitch_potential_gradient_override=pitch_gradient_override,
    )
    return StationHullMatchedHeavePitchSweep(
        x_m=x,
        active_station_indices=active_indices,
        bodies=bodies,
        heave_mode_solutions=heave_tuple,
        pitch_mode_solutions=pitch_tuple,
        heave_condition_numbers=heave_conditions,
        pitch_condition_numbers=pitch_conditions,
        heave_residuals=heave_residuals,
        pitch_residuals=pitch_residuals,
        heave_block_audits=heave_audit_tuple,
        pitch_block_audits=pitch_audit_tuple,
        heave_free_surface_potential_by_station=heave_free_potential_by_station,
        pitch_free_surface_potential_by_station=pitch_free_potential_by_station,
        heave_free_surface_elevation_by_station=heave_free_elevation_by_station,
        pitch_free_surface_elevation_by_station=pitch_free_elevation_by_station,
        heave_free_surface_potential_after_station=heave_free_potential_after_station,
        pitch_free_surface_potential_after_station=pitch_free_potential_after_station,
        heave_free_surface_elevation_after_station=heave_free_elevation_after_station,
        pitch_free_surface_elevation_after_station=pitch_free_elevation_after_station,
        local_time_s_by_station=np.asarray(local_time_s, dtype=float),
        heave_free_surface_time_before_by_station=heave_free_time_before_by_station,
        pitch_free_surface_time_before_by_station=pitch_free_time_before_by_station,
        heave_free_surface_time_after_by_station=heave_free_time_after_by_station,
        pitch_free_surface_time_after_by_station=pitch_free_time_after_by_station,
        inner_free_surface_y_by_station=free_y_by_station,
        inner_free_surface_panel_length_by_station=free_length_by_station,
        heave_outer_history_rhs_by_station=heave_outer_history_rhs_by_station,
        pitch_outer_history_rhs_by_station=pitch_outer_history_rhs_by_station,
        pitch_body_condition_oscillation_by_station=pitch_body_condition_oscillation_by_station,
        pitch_body_condition_forward_speed_by_station=pitch_body_condition_forward_speed_by_station,
        heave_free_surface_update_kind_by_station=tuple(heave_update_kind_by_station),
        pitch_free_surface_update_kind_by_station=tuple(pitch_update_kind_by_station),
        end_term=end_term_result,
        control_surface_end_term=control_surface_end_term_result,
        pressure_force_sweep=pressure_force_sweep,
        solve_order=solve_order,
        use_free_surface_marching=bool(use_free_surface_marching),
        end_term_scale=end_scale,
        end_station=selector,
        end_hull_station_index=int(end_hull_index),
        end_active_station_local_index=int(end_active_local_index),
        end_station_x_m=float(end_hull_station.x_m),
        end_station_is_degenerate=end_station_is_degenerate,
        end_term_geometry_source=end_term_geometry_source,
        pitch_radiation_sign=pitch_rad_sign,
        pitch_radiation_lever_sign=pitch_lever_sign,
        pitch_forward_speed_sign=pitch_speed_sign,
        pitch_oscillation_scale=pitch_osc_scale,
        pitch_forward_speed_scale=pitch_fwd_scale,
        pitch_moment_sign=pitch_row_sign,
        time_step_scale=dt_scale,
        free_surface_substeps_per_station=free_substeps,
        free_surface_velocity_scale=free_velocity_scale,
        free_surface_normal_derivative_source=free_normal_source,
        free_surface_time_direction_sign=free_time_sign,
        free_surface_dynamic_gravity_sign=free_dynamic_sign,
        free_surface_potential_elevation_level=free_elevation_level,
        control_row_free_surface_potential_source=control_row_free_source,
        history_rhs_scale=history_scale,
        history_convolution_rule=history_rule,
        history_potential_kernel_scale=history_potential_scale,
        history_normal_derivative_kernel_scale=history_normal_scale,
        control_image_scale=control_image,
        control_potential_kernel_scale=control_potential_scale,
        control_normal_derivative_kernel_scale=control_normal_scale,
        control_diagonal_sign=control_diag_sign,
        pressure_gradient_scheme=gradient_scheme,
        pressure_gradient_scale=pressure_grad_scale,
        force_assembly_route=pressure_force_sweep.assembly.force_assembly_route,
        clip_inner_free_surface_to_waterline=bool(clip_inner_free_surface_to_waterline),
        two_zone_inner_free_surface=two_zone,
        apply_local_time_phase=bool(apply_local_time_phase),
        local_time_phase_x0_m=phase_x0,
        local_time_phase_gradient_correction=phase_gradient_correction,
        inner_a_scale=inner_a,
        inner_b_scale=inner_b,
        inner_diagonal_sign=inner_diag_sign,
        inner_free_surface_self_diagonal_scale=free_self_diag_scale,
        inner_free_surface_known_potential_rhs_scale=free_known_rhs_scale,
        inner_free_surface_known_potential_body_row_scale=free_known_body_row_scale,
        inner_free_surface_known_potential_free_row_scale=free_known_free_row_scale,
        inner_free_surface_known_potential_control_row_scale=free_known_control_row_scale,
        inner_free_surface_unknown_normal_column_scale=free_unknown_column_scale,
        history_steps=int(history_steps),
        history_dt_s=float(dt),
        history_quadrature_count=int(history_quadrature_count),
        history_k_max=float(history.k_max),
        history_gravity_m_s2=9.80665,
        control_panel_count=int(control.panel_count),
        control_radius_m=float(radius),
        inner_free_surface_geometries=free_geometries,
        heave_body_condition_by_station=heave_body_condition_by_station,
        heave_body_condition_source=heave_condition_source,
        validity=ValidityReport(
            status=LINEAR_2P5D_STATION_HULL_SWEEP_STATUS,
            reference_cases=("ma2005_wigley_iii",),
            notes=(
                "StationHull matched sweep uses bow-to-stern control-surface history seeding and staggered inner "
                "free-surface marching. It is a bridge into the coefficient gate, not a passed Ma 2005 solver.",
            ),
        ),
    )


def solve_station_hull_head_sea_excitation_matched_sweep(
    hull: StationHull,
    encounter_omega_rad_s: float,
    speed_mps: float,
    *,
    config: Linear2p5DProviderConfig | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    parametric_section_shape: str = "wigley",
    matched_sweep_options: dict[str, object] | None = None,
) -> MatchedHeadSeaExcitationSweep:
    """Solve A1 unit-wave-amplitude Froude--Krylov plus diffraction loads.

    The incident potential follows A1 Eq. (3) for head seas.  Its normal
    derivative drives the matched-domain diffraction problem through A1
    Eq. (4).  Incident and diffraction pressures are then integrated with A1
    Eq. (30).  Radiation-only Stokes body and end terms are deliberately not
    added to this excitation load.
    """

    omega_e = float(encounter_omega_rad_s)
    speed = float(speed_mps)
    rho = float(rho_water_kg_m3)
    gravity = float(gravity_m_s2)
    if not np.isfinite(rho) or rho <= 0.0:
        raise ValueError("rho_water_kg_m3 must be finite and positive.")
    wavenumber, omega_0 = deep_water_head_sea_wave_from_encounter(
        omega_e,
        speed,
        gravity,
    )
    options = {} if matched_sweep_options is None else dict(matched_sweep_options)
    reserved = {
        "config",
        "rho_water_kg_m3",
        "parametric_section_shape",
        "heave_body_normal_velocity_base",
        "heave_body_condition_source",
        "include_end_term",
        "force_assembly_route",
    }
    collisions = sorted(reserved.intersection(options))
    if collisions:
        raise ValueError(
            "matched_sweep_options cannot override excitation invariants: "
            + ", ".join(collisions)
        )

    def incident_fields(
        station_x_m: float,
        body_geometry: InnerDomainPanelGeometry,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x_forward = float(station_x_m) - float(hull.lcg_m)
        phase = np.exp(1j * wavenumber * x_forward)
        depth_factor = np.exp(-wavenumber * np.asarray(body_geometry.mid_z_down_m, dtype=float))
        phi_0 = 1j * gravity / omega_0 * depth_factor * phase
        # In z-down coordinates grad_z(phi_0)=-k*phi_0. The fluid-domain
        # outward body normal is -normal_z, so -d(phi_0)/dN=-k*phi_0*normal_z.
        diffraction_normal_velocity = (
            -wavenumber * phi_0 * np.asarray(body_geometry.normal_z, dtype=float)
        )
        incident_pressure = rho * gravity * depth_factor * phase
        return (
            np.asarray(phi_0, dtype=complex),
            np.asarray(diffraction_normal_velocity, dtype=complex),
            np.asarray(incident_pressure, dtype=complex),
        )

    def diffraction_body_condition(
        _local_index: int,
        station_x_m: float,
        body_geometry: InnerDomainPanelGeometry,
    ) -> np.ndarray:
        return incident_fields(station_x_m, body_geometry)[1]

    sweep = solve_station_hull_heave_pitch_matched_sweep(
        hull,
        omega_e,
        speed,
        config=config,
        rho_water_kg_m3=rho,
        parametric_section_shape=parametric_section_shape,
        include_end_term=False,
        force_assembly_route="eq31_pressure_gradient_only",
        heave_body_normal_velocity_base=diffraction_body_condition,
        heave_body_condition_source="a1_eq4_head_sea_diffraction_minus_incident_normal_derivative",
        **options,
    )
    incident_potential = []
    diffraction_boundary = []
    incident_pressure = []
    fk_density = []
    equation30_pressures = []
    for station_x, body_geometry in zip(sweep.x_m, sweep.bodies, strict=True):
        phi_0, boundary_value, pressure_fk = incident_fields(float(station_x), body_geometry)
        incident_potential.append(phi_0)
        diffraction_boundary.append(boundary_value)
        incident_pressure.append(pressure_fk)
        phi_x = 1j * wavenumber * phi_0
        equation30_pressures.append(-rho * (1j * omega_e * phi_0 - speed * phi_x))
        lever = float(sweep.pitch_moment_sign) * (float(hull.lcg_m) - float(station_x))
        fk_density.append(
            _integrate_pressure_heave_pitch(
                pressure_fk,
                body_geometry.normal_z,
                body_geometry.length_m,
                lever,
            )
        )

    incident_potential_array = np.asarray(incident_potential, dtype=complex)
    diffraction_boundary_array = np.asarray(diffraction_boundary, dtype=complex)
    incident_pressure_array = np.asarray(incident_pressure, dtype=complex)
    equation30_pressure_array = np.asarray(equation30_pressures, dtype=complex)
    fk_density_array = np.asarray(fk_density, dtype=complex)
    diffraction_density = np.asarray(
        [
            (force.heave_force_per_m, force.pitch_moment_per_m)
            for force in sweep.pressure_force_sweep.heave_mode_forces
        ],
        dtype=complex,
    )
    if diffraction_density.shape != fk_density_array.shape:
        raise RuntimeError("Matched diffraction and incident force densities do not share a 2-DOF shape.")
    fk_force = np.asarray(np.trapezoid(fk_density_array, sweep.x_m, axis=0), dtype=complex)
    diffraction_force = np.asarray(
        np.trapezoid(diffraction_density, sweep.x_m, axis=0),
        dtype=complex,
    )
    assembly_diffraction = np.asarray(
        sweep.pressure_force_sweep.assembly.complex_force_matrix[:, 0],
        dtype=complex,
    )
    force_density_residual = float(
        np.linalg.norm(diffraction_force - assembly_diffraction)
        / max(float(np.linalg.norm(assembly_diffraction)), 1.0e-30)
    )
    local_phase = (
        np.exp(1j * omega_e * np.asarray(sweep.local_time_s_by_station, dtype=float))
        if sweep.apply_local_time_phase
        else np.ones(len(sweep.x_m), dtype=complex)
    )
    expected_phase_domain_boundary = diffraction_boundary_array * local_phase[:, None]
    body_condition_residual = float(
        np.linalg.norm(sweep.heave_body_condition_by_station - expected_phase_domain_boundary)
        / max(float(np.linalg.norm(expected_phase_domain_boundary)), 1.0e-30)
    )
    incident_pressure_residual = float(
        np.linalg.norm(equation30_pressure_array - incident_pressure_array)
        / max(float(np.linalg.norm(incident_pressure_array)), 1.0e-30)
    )
    total_density = fk_density_array + diffraction_density
    total_excitation = fk_force + diffraction_force
    finite_arrays = (
        incident_potential_array,
        diffraction_boundary_array,
        incident_pressure_array,
        fk_density_array,
        diffraction_density,
        total_density,
        total_excitation,
    )
    if any(
        not np.isfinite(values.real).all() or not np.isfinite(values.imag).all()
        for values in finite_arrays
    ):
        raise RuntimeError("Matched head-sea excitation contains non-finite values.")
    maximum_condition = float(np.max(sweep.heave_condition_numbers))
    maximum_residual = float(np.max(sweep.heave_residuals))
    return MatchedHeadSeaExcitationSweep(
        x_m=np.asarray(sweep.x_m, dtype=float),
        encounter_omega_rad_s=omega_e,
        absolute_wave_omega_rad_s=omega_0,
        wavenumber_rad_m=wavenumber,
        incident_potential_by_station=incident_potential_array,
        diffraction_body_normal_velocity_by_station=diffraction_boundary_array,
        incident_pressure_by_station=incident_pressure_array,
        froude_krylov_force_density_by_station=fk_density_array,
        diffraction_force_density_by_station=diffraction_density,
        total_force_density_by_station=total_density,
        froude_krylov_force=fk_force,
        diffraction_force=diffraction_force,
        total_excitation=np.asarray(total_excitation, dtype=complex),
        diffraction_sweep=sweep,
        body_condition_relative_residual=body_condition_residual,
        equation30_incident_pressure_relative_residual=incident_pressure_residual,
        force_density_integration_relative_residual=force_density_residual,
        maximum_condition_number=maximum_condition,
        maximum_linear_system_relative_residual=maximum_residual,
        validity=ValidityReport(
            status=LINEAR_2P5D_HEAD_SEA_EXCITATION_STATUS,
            reference_cases=("ma2005_eq3_eq4_eq30", "begovic_planing_head_sea"),
            notes=(
                "Unit-wave-amplitude head-sea excitation from matched-domain diffraction plus direct "
                "Froude--Krylov pressure. No response scaling, response inversion, or radiation end term is used.",
            ),
        ),
    )


def assemble_frequency_domain_from_matched_station_hull(
    hull: StationHull,
    body: RigidBody6DOF,
    omega_rad_s: np.ndarray,
    speed_mps: float,
    *,
    config: Linear2p5DProviderConfig | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    heading_deg: float = 180.0,
    parametric_section_shape: str = "wigley",
    history_steps: int = 40,
    history_quadrature_count: int = 32,
    history_k_max: float = 25.0,
    include_end_term: bool | None = None,
    end_station: str = "aft",
    end_term_scale: float = 1.0,
    pitch_radiation_sign: float = 1.0,
    pitch_radiation_lever_sign: float = 1.0,
    pitch_forward_speed_sign: float = 1.0,
    pitch_oscillation_scale: float = 1.0,
    pitch_forward_speed_scale: float = 1.0,
    pitch_moment_sign: float = 1.0,
    time_step_scale: float = 1.0,
    free_surface_substeps_per_station: int = 1,
    waterline_grading_exponent: float = 1.0,
    free_surface_velocity_scale: float = 1.0,
    free_surface_normal_derivative_source: str = "raw",
    free_surface_time_direction_sign: float = 1.0,
    free_surface_dynamic_gravity_sign: float = -1.0,
    free_surface_potential_elevation_level: str = "updated",
    control_row_free_surface_potential_source: str = "shared",
    history_rhs_scale: float = 1.0,
    history_convolution_rule: str = "trapezoid",
    history_potential_kernel_scale: float = 1.0,
    history_normal_derivative_kernel_scale: float = 1.0,
    control_image_scale: float = 1.0,
    control_potential_kernel_scale: float = 1.0,
    control_normal_derivative_kernel_scale: float = 1.0,
    control_diagonal_sign: float = 1.0,
    inner_a_scale: float = 1.0,
    inner_b_scale: float = 1.0,
    inner_diagonal_sign: float = -1.0,
    inner_free_surface_self_diagonal_scale: float = 1.0,
    inner_free_surface_known_potential_rhs_scale: float = 1.0,
    inner_free_surface_known_potential_body_row_scale: float = 1.0,
    inner_free_surface_known_potential_free_row_scale: float = 1.0,
    inner_free_surface_known_potential_control_row_scale: float = 1.0,
    inner_free_surface_unknown_normal_column_scale: float = 1.0,
    pressure_gradient_scheme: str = "central",
    pressure_gradient_scale: float = 1.0,
    force_assembly_route: str = "eq32_stokes_body_plus_end",
    apply_local_time_phase: bool = True,
    local_time_phase_x0_m: float | None = None,
    local_time_phase_gradient_correction: bool = True,
    clip_inner_free_surface_to_waterline: bool = True,
    two_zone_inner_free_surface: bool = False,
    use_free_surface_marching: bool = True,
) -> FrequencyDomainHydrodynamics:
    """Assemble matched StationHull radiation matrices at encounter frequency.

    ``omega_rad_s`` is the oscillation/encounter frequency used in A1 Eq. (4),
    not an absolute wave frequency. It must not be transformed a second time.
    """

    cfg = Linear2p5DProviderConfig() if config is None else config
    cfg.validate()
    omega = np.asarray(omega_rad_s, dtype=float)
    if omega.ndim != 1 or omega.size < 1:
        raise ValueError("omega_rad_s must be a non-empty one-dimensional array.")
    if np.any(omega <= 0.0):
        raise ValueError("omega_rad_s values must be positive.")
    encounter = np.array(omega, copy=True)
    n_freq = omega.size
    added_mass = np.zeros((n_freq, 6, 6), dtype=float)
    damping = np.zeros((n_freq, 6, 6), dtype=float)
    restoring = np.zeros((n_freq, 6, 6), dtype=float)
    excitation = np.zeros((n_freq, 6), dtype=complex)
    hydrostatics = hull.hydrostatics()
    restoring[:, 2, 2] = rho_water_kg_m3 * gravity_m_s2 * hydrostatics.waterplane_area_m2
    restoring[:, 4, 4] = rho_water_kg_m3 * gravity_m_s2 * hydrostatics.waterplane_second_moment_pitch_m4
    sweep_statuses: list[str] = []
    coefficient_rows: list[dict[str, float]] = []
    heave_condition_rows: list[np.ndarray] = []
    pitch_condition_rows: list[np.ndarray] = []
    heave_residual_rows: list[np.ndarray] = []
    pitch_residual_rows: list[np.ndarray] = []
    heave_pitch_force_rows: list[np.ndarray] = []
    heave_pitch_end_term_rows: list[np.ndarray] = []
    heave_pitch_control_surface_end_term_rows: list[np.ndarray] = []
    heave_pitch_time_force_rows: list[np.ndarray] = []
    heave_pitch_forward_force_rows: list[np.ndarray] = []
    gradient_candidate_names = (
        "current_default",
        "scheme_central",
        "scheme_forward",
        "scheme_backward",
        "phase_aligned_central",
        "phase_aligned_forward",
        "phase_aligned_backward",
        "mapped_fixed_y_central",
        "mapped_fixed_y_forward",
        "mapped_fixed_y_backward",
        "mapped_normalized_y_central",
        "mapped_normalized_y_forward",
        "mapped_normalized_y_backward",
        "startup_aft_gradient_zero",
        "startup_aft_gradient_copy_second",
        "startup_first_pair_gradient_average",
    )
    heave_pitch_forward_force_gradient_candidate_rows: dict[str, list[np.ndarray]] = {
        name: [] for name in gradient_candidate_names
    }
    heave_pitch_forward_force_gradient_candidate_density_rows: dict[str, list[np.ndarray]] = {
        name: [] for name in gradient_candidate_names
    }
    heave_body_potential_x_gradient_candidate_rows: dict[str, list[np.ndarray]] = {
        name: [] for name in gradient_candidate_names
    }
    pitch_body_potential_x_gradient_candidate_rows: dict[str, list[np.ndarray]] = {
        name: [] for name in gradient_candidate_names
    }
    heave_pitch_stokes_body_forward_rows: list[np.ndarray] = []
    heave_pitch_stokes_body_forward_force_density_rows: list[np.ndarray] = []
    heave_pitch_row_measure_transport_rows: list[np.ndarray] = []
    heave_pitch_row_measure_transport_force_density_rows: list[np.ndarray] = []
    heave_pitch_pressure_row_measure_rows: list[np.ndarray] = []
    heave_pitch_pressure_row_measure_x_gradient_rows: list[np.ndarray] = []
    heave_pitch_stokes_m_measure_rows: list[np.ndarray] = []
    body_panel_normal_z_rows: list[np.ndarray] = []
    body_panel_length_rows: list[np.ndarray] = []
    body_panel_node_y_rows: list[np.ndarray] = []
    body_panel_node_z_down_rows: list[np.ndarray] = []
    body_panel_delta_y_rows: list[np.ndarray] = []
    heave_body_potential_by_station_rows: list[np.ndarray] = []
    pitch_body_potential_by_station_rows: list[np.ndarray] = []
    heave_pressure_body_potential_by_station_rows: list[np.ndarray] = []
    pitch_pressure_body_potential_by_station_rows: list[np.ndarray] = []
    inner_free_surface_panel_length_rows: list[np.ndarray] = []
    heave_free_surface_potential_by_station_rows: list[np.ndarray] = []
    pitch_free_surface_potential_by_station_rows: list[np.ndarray] = []
    heave_control_potential_by_station_rows: list[np.ndarray] = []
    pitch_control_potential_by_station_rows: list[np.ndarray] = []
    control_panel_length_rows: list[np.ndarray] = []
    row_measure_mapping_candidate_names = (
        "current_equal_panel_x_derivative",
        "mapped_fixed_y_central",
        "mapped_normalized_y_central",
        "mapped_normalized_arclength_central",
        "heave_projection_leibniz_endpoint_flux_pitch_current",
    )
    heave_pitch_row_measure_transport_candidate_rows: dict[str, list[np.ndarray]] = {
        name: [] for name in row_measure_mapping_candidate_names
    }
    heave_pitch_row_measure_transport_candidate_density_rows: dict[str, list[np.ndarray]] = {
        name: [] for name in row_measure_mapping_candidate_names
    }
    heave_pitch_pressure_row_measure_x_gradient_candidate_rows: dict[str, list[np.ndarray]] = {
        name: [] for name in row_measure_mapping_candidate_names
    }
    heave_free_surface_potential_norm_rows: list[np.ndarray] = []
    pitch_free_surface_potential_norm_rows: list[np.ndarray] = []
    heave_free_surface_elevation_norm_rows: list[np.ndarray] = []
    pitch_free_surface_elevation_norm_rows: list[np.ndarray] = []
    heave_outer_history_rhs_norm_rows: list[np.ndarray] = []
    pitch_outer_history_rhs_norm_rows: list[np.ndarray] = []
    heave_inner_free_surface_normal_derivative_norm_rows: list[np.ndarray] = []
    pitch_inner_free_surface_normal_derivative_norm_rows: list[np.ndarray] = []
    heave_free_surface_potential_increment_norm_rows: list[np.ndarray] = []
    pitch_free_surface_potential_increment_norm_rows: list[np.ndarray] = []
    heave_free_surface_potential_increment_to_normal_derivative_gain_rows: list[np.ndarray] = []
    pitch_free_surface_potential_increment_to_normal_derivative_gain_rows: list[np.ndarray] = []
    heave_free_surface_potential_increment_normal_derivative_alignment_rows: list[np.ndarray] = []
    pitch_free_surface_potential_increment_normal_derivative_alignment_rows: list[np.ndarray] = []
    heave_free_surface_potential_increment_normal_derivative_phase_rows: list[np.ndarray] = []
    pitch_free_surface_potential_increment_normal_derivative_phase_rows: list[np.ndarray] = []
    heave_body_potential_norm_rows: list[np.ndarray] = []
    pitch_body_potential_norm_rows: list[np.ndarray] = []
    heave_body_normal_velocity_norm_rows: list[np.ndarray] = []
    pitch_body_normal_velocity_norm_rows: list[np.ndarray] = []
    pitch_body_condition_oscillation_norm_rows: list[np.ndarray] = []
    pitch_body_condition_forward_speed_norm_rows: list[np.ndarray] = []
    pitch_body_condition_forward_to_oscillation_ratio_rows: list[np.ndarray] = []
    pitch_body_condition_forward_oscillation_alignment_rows: list[np.ndarray] = []
    pitch_body_condition_forward_oscillation_phase_rows: list[np.ndarray] = []
    heave_control_potential_norm_rows: list[np.ndarray] = []
    pitch_control_potential_norm_rows: list[np.ndarray] = []
    heave_control_normal_derivative_norm_rows: list[np.ndarray] = []
    pitch_control_normal_derivative_norm_rows: list[np.ndarray] = []
    pitch_base_lever_arm_rows: list[np.ndarray] = []
    pitch_radiation_lever_arm_rows: list[np.ndarray] = []
    pitch_moment_lever_arm_rows: list[np.ndarray] = []
    end_term_station_index_rows: list[float] = []
    end_term_station_x_over_l_rows: list[float] = []
    end_term_lever_arm_rows: list[float] = []
    aft_pair_rhs_norm_rows: dict[str, list[np.ndarray]] = {
        f"{mode}_aft_pair_{name}": []
        for mode in ("heave", "pitch")
        for name in (
            "total_rhs_norms",
            "source_sum_relative_residuals",
            "body_normal_velocity_rhs_norms",
            "inner_free_surface_potential_rhs_norms",
            "outer_control_history_rhs_norms",
            "body_normal_velocity_rhs_to_total_ratios",
            "inner_free_surface_potential_rhs_to_total_ratios",
            "outer_control_history_rhs_to_total_ratios",
        )
    }
    aft_pair_free_rhs_block_rows: dict[str, list[np.ndarray]] = {
        f"{mode}_aft_pair_inner_free_surface_rhs_block_{name}": []
        for mode in ("heave", "pitch")
        for name in (
            "free_surface_panel_y_m",
            "free_surface_panel_length_m",
            "free_surface_potential_abs",
            "free_surface_potential_phase_degs",
            "matrix_column_norms",
            "contribution_norms",
            "panel_to_row_block_ratios",
            "panel_to_total_ratios",
            "panel_to_row_block_alignments",
            "panel_to_row_block_phase_degs",
            "row_block_free_rhs_norms",
            "row_block_to_total_ratios",
            "row_block_to_total_alignments",
            "row_block_to_total_phase_degs",
            "total_free_rhs_norms",
        )
    }
    station_x_m_rows: list[np.ndarray] = []
    station_x_over_l_rows: list[np.ndarray] = []
    station_local_time_rows: list[np.ndarray] = []
    station_solve_order_index_rows: list[np.ndarray] = []
    station_solve_order_x_over_l_rows: list[np.ndarray] = []
    station_solve_order_local_time_rows: list[np.ndarray] = []
    station_waterplane_beam_rows: list[np.ndarray] = []
    station_effective_draft_rows: list[np.ndarray] = []
    station_submerged_area_rows: list[np.ndarray] = []
    station_waterplane_beam_adjacent_jump_rows: list[np.ndarray] = []
    station_effective_draft_adjacent_jump_rows: list[np.ndarray] = []
    station_submerged_area_adjacent_jump_rows: list[np.ndarray] = []
    station_waterplane_beam_gradient_gain_rows: list[np.ndarray] = []
    station_effective_draft_gradient_gain_rows: list[np.ndarray] = []
    station_submerged_area_gradient_gain_rows: list[np.ndarray] = []
    heave_body_potential_norm_to_beam_squared_ratio_rows: list[np.ndarray] = []
    pitch_body_potential_norm_to_beam_squared_ratio_rows: list[np.ndarray] = []
    heave_body_potential_norm_to_submerged_area_ratio_rows: list[np.ndarray] = []
    pitch_body_potential_norm_to_submerged_area_ratio_rows: list[np.ndarray] = []
    heave_body_potential_norm_to_beam_squared_peak_x_over_l_rows: list[float] = []
    pitch_body_potential_norm_to_beam_squared_peak_x_over_l_rows: list[float] = []
    heave_body_potential_norm_to_submerged_area_peak_x_over_l_rows: list[float] = []
    pitch_body_potential_norm_to_submerged_area_peak_x_over_l_rows: list[float] = []
    station_waterplane_beam_gradient_peak_x_over_l_rows: list[float] = []
    station_submerged_area_gradient_peak_x_over_l_rows: list[float] = []
    aft_active_station_x_over_l_rows: list[float] = []
    aft_active_station_waterplane_beam_rows: list[float] = []
    aft_active_station_effective_draft_rows: list[float] = []
    aft_active_station_submerged_area_rows: list[float] = []
    aft_active_station_body_panel_length_sum_rows: list[float] = []
    aft_active_station_body_panel_length_max_rows: list[float] = []
    aft_active_station_body_panel_normal_z_norm_rows: list[float] = []
    aft_active_station_heave_generalized_row_norm_rows: list[float] = []
    aft_active_station_pitch_generalized_row_norm_rows: list[float] = []
    heave_body_pressure_norm_rows: list[np.ndarray] = []
    pitch_body_pressure_norm_rows: list[np.ndarray] = []
    heave_body_pressure_time_derivative_norm_rows: list[np.ndarray] = []
    pitch_body_pressure_time_derivative_norm_rows: list[np.ndarray] = []
    heave_body_pressure_forward_speed_norm_rows: list[np.ndarray] = []
    pitch_body_pressure_forward_speed_norm_rows: list[np.ndarray] = []
    heave_body_pressure_to_body_potential_gain_rows: list[np.ndarray] = []
    pitch_body_pressure_to_body_potential_gain_rows: list[np.ndarray] = []
    heave_body_pressure_to_free_surface_potential_after_gain_rows: list[np.ndarray] = []
    pitch_body_pressure_to_free_surface_potential_after_gain_rows: list[np.ndarray] = []
    heave_body_pressure_forward_to_time_norm_ratio_rows: list[np.ndarray] = []
    pitch_body_pressure_forward_to_time_norm_ratio_rows: list[np.ndarray] = []
    heave_pressure_time_formula_ratio_rows: list[np.ndarray] = []
    pitch_pressure_time_formula_ratio_rows: list[np.ndarray] = []
    heave_pressure_forward_formula_ratio_rows: list[np.ndarray] = []
    pitch_pressure_forward_formula_ratio_rows: list[np.ndarray] = []
    heave_body_potential_x_gradient_norm_rows: list[np.ndarray] = []
    pitch_body_potential_x_gradient_norm_rows: list[np.ndarray] = []
    heave_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    pitch_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    heave_body_potential_x_gradient_characteristic_length_rows: list[np.ndarray] = []
    pitch_body_potential_x_gradient_characteristic_length_rows: list[np.ndarray] = []
    heave_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    pitch_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    heave_central_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    pitch_central_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    heave_forward_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    pitch_forward_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    heave_backward_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    pitch_backward_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    heave_central_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    pitch_central_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    heave_forward_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    pitch_forward_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    heave_backward_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    pitch_backward_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    heave_phase_aligned_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    pitch_phase_aligned_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    heave_phase_aligned_body_potential_x_gradient_characteristic_length_rows: list[np.ndarray] = []
    pitch_phase_aligned_body_potential_x_gradient_characteristic_length_rows: list[np.ndarray] = []
    heave_phase_aligned_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    pitch_phase_aligned_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    heave_phase_aligned_gradient_gain_to_raw_gain_ratio_rows: list[np.ndarray] = []
    pitch_phase_aligned_gradient_gain_to_raw_gain_ratio_rows: list[np.ndarray] = []
    heave_phase_aligned_central_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    pitch_phase_aligned_central_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    heave_phase_aligned_forward_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    pitch_phase_aligned_forward_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    heave_phase_aligned_backward_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    pitch_phase_aligned_backward_body_potential_x_gradient_to_potential_gain_rows: list[np.ndarray] = []
    heave_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    pitch_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    heave_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    pitch_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    heave_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    pitch_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length_rows: list[np.ndarray] = []
    heave_adjacent_body_potential_relative_jump_rows: list[np.ndarray] = []
    pitch_adjacent_body_potential_relative_jump_rows: list[np.ndarray] = []
    heave_adjacent_body_potential_symmetric_norm_ratio_rows: list[np.ndarray] = []
    pitch_adjacent_body_potential_symmetric_norm_ratio_rows: list[np.ndarray] = []
    heave_adjacent_body_potential_real_alignment_rows: list[np.ndarray] = []
    pitch_adjacent_body_potential_real_alignment_rows: list[np.ndarray] = []
    heave_adjacent_body_potential_phase_rows: list[np.ndarray] = []
    pitch_adjacent_body_potential_phase_rows: list[np.ndarray] = []
    heave_phase_aligned_adjacent_body_potential_relative_jump_rows: list[np.ndarray] = []
    pitch_phase_aligned_adjacent_body_potential_relative_jump_rows: list[np.ndarray] = []
    heave_phase_aligned_adjacent_body_potential_real_alignment_rows: list[np.ndarray] = []
    pitch_phase_aligned_adjacent_body_potential_real_alignment_rows: list[np.ndarray] = []
    heave_phase_aligned_adjacent_body_potential_phase_rows: list[np.ndarray] = []
    pitch_phase_aligned_adjacent_body_potential_phase_rows: list[np.ndarray] = []
    body_panel_mid_y_adjacent_relative_jump_rows: list[np.ndarray] = []
    body_panel_mid_z_adjacent_relative_jump_rows: list[np.ndarray] = []
    body_panel_normal_adjacent_relative_jump_rows: list[np.ndarray] = []
    body_panel_length_adjacent_relative_jump_rows: list[np.ndarray] = []
    heave_mode_heave_force_to_pressure_norm_gain_rows: list[np.ndarray] = []
    heave_mode_pitch_moment_to_pressure_norm_gain_rows: list[np.ndarray] = []
    pitch_mode_heave_force_to_pressure_norm_gain_rows: list[np.ndarray] = []
    pitch_mode_pitch_moment_to_pressure_norm_gain_rows: list[np.ndarray] = []
    heave_pitch_total_force_density_rows: list[np.ndarray] = []
    heave_pitch_time_force_density_rows: list[np.ndarray] = []
    heave_pitch_forward_force_density_rows: list[np.ndarray] = []
    heave_pitch_total_force_density_peak_x_over_l_rows: list[np.ndarray] = []
    heave_pitch_time_force_density_peak_x_over_l_rows: list[np.ndarray] = []
    heave_pitch_forward_force_density_peak_x_over_l_rows: list[np.ndarray] = []
    heave_pitch_total_force_density_peak_abs_rows: list[np.ndarray] = []
    heave_pitch_time_force_density_peak_abs_rows: list[np.ndarray] = []
    heave_pitch_forward_force_density_peak_abs_rows: list[np.ndarray] = []
    heave_pitch_total_force_density_peak_to_integral_abs_ratio_rows: list[np.ndarray] = []
    heave_pitch_time_force_density_peak_to_integral_abs_ratio_rows: list[np.ndarray] = []
    heave_pitch_forward_force_density_peak_to_integral_abs_ratio_rows: list[np.ndarray] = []
    heave_pitch_total_force_density_abs_centroid_x_over_l_rows: list[np.ndarray] = []
    heave_pitch_time_force_density_abs_centroid_x_over_l_rows: list[np.ndarray] = []
    heave_pitch_forward_force_density_abs_centroid_x_over_l_rows: list[np.ndarray] = []
    heave_pitch_pressure_force_matrices_excluding_aft_active_station_rows: list[np.ndarray] = []
    heave_pitch_pressure_force_matrices_excluding_bow_active_station_rows: list[np.ndarray] = []
    heave_pitch_pressure_force_matrices_excluding_end_active_stations_rows: list[np.ndarray] = []
    heave_pitch_time_force_matrices_excluding_aft_active_station_rows: list[np.ndarray] = []
    heave_pitch_forward_force_matrices_excluding_aft_active_station_rows: list[np.ndarray] = []
    heave_pitch_total_force_density_aft_abs_rows: list[np.ndarray] = []
    heave_pitch_time_force_density_aft_abs_rows: list[np.ndarray] = []
    heave_pitch_forward_force_density_aft_abs_rows: list[np.ndarray] = []
    heave_eq24_relative_residual_rows: list[np.ndarray] = []
    pitch_eq24_relative_residual_rows: list[np.ndarray] = []
    matched_station_sweeps: list[StationHullMatchedHeavePitchSweep] = []
    idx = np.ix_([2, 4], [2, 4])
    for freq_index, freq in enumerate(omega):
        sweep = solve_station_hull_heave_pitch_matched_sweep(
            hull,
            float(freq),
            speed_mps,
            config=cfg,
            rho_water_kg_m3=rho_water_kg_m3,
            parametric_section_shape=parametric_section_shape,
            history_steps=history_steps,
            history_quadrature_count=history_quadrature_count,
            history_k_max=history_k_max,
            include_end_term=include_end_term,
            end_station=end_station,
            end_term_scale=end_term_scale,
            pitch_radiation_sign=pitch_radiation_sign,
            pitch_radiation_lever_sign=pitch_radiation_lever_sign,
            pitch_forward_speed_sign=pitch_forward_speed_sign,
            pitch_oscillation_scale=pitch_oscillation_scale,
            pitch_forward_speed_scale=pitch_forward_speed_scale,
            pitch_moment_sign=pitch_moment_sign,
            time_step_scale=time_step_scale,
            free_surface_substeps_per_station=free_surface_substeps_per_station,
            waterline_grading_exponent=waterline_grading_exponent,
            free_surface_velocity_scale=free_surface_velocity_scale,
            free_surface_normal_derivative_source=free_surface_normal_derivative_source,
            free_surface_time_direction_sign=free_surface_time_direction_sign,
            free_surface_dynamic_gravity_sign=free_surface_dynamic_gravity_sign,
            free_surface_potential_elevation_level=free_surface_potential_elevation_level,
            control_row_free_surface_potential_source=control_row_free_surface_potential_source,
            history_rhs_scale=history_rhs_scale,
            history_convolution_rule=history_convolution_rule,
            history_potential_kernel_scale=history_potential_kernel_scale,
            history_normal_derivative_kernel_scale=history_normal_derivative_kernel_scale,
            control_image_scale=control_image_scale,
            control_potential_kernel_scale=control_potential_kernel_scale,
            control_normal_derivative_kernel_scale=control_normal_derivative_kernel_scale,
            control_diagonal_sign=control_diagonal_sign,
            inner_a_scale=inner_a_scale,
            inner_b_scale=inner_b_scale,
            inner_diagonal_sign=inner_diagonal_sign,
            inner_free_surface_self_diagonal_scale=inner_free_surface_self_diagonal_scale,
            inner_free_surface_known_potential_rhs_scale=inner_free_surface_known_potential_rhs_scale,
            inner_free_surface_known_potential_body_row_scale=inner_free_surface_known_potential_body_row_scale,
            inner_free_surface_known_potential_free_row_scale=inner_free_surface_known_potential_free_row_scale,
            inner_free_surface_known_potential_control_row_scale=inner_free_surface_known_potential_control_row_scale,
            inner_free_surface_unknown_normal_column_scale=inner_free_surface_unknown_normal_column_scale,
            pressure_gradient_scheme=pressure_gradient_scheme,
            pressure_gradient_scale=pressure_gradient_scale,
            force_assembly_route=force_assembly_route,
            apply_local_time_phase=apply_local_time_phase,
            local_time_phase_x0_m=local_time_phase_x0_m,
            local_time_phase_gradient_correction=local_time_phase_gradient_correction,
            clip_inner_free_surface_to_waterline=clip_inner_free_surface_to_waterline,
            two_zone_inner_free_surface=two_zone_inner_free_surface,
            use_free_surface_marching=use_free_surface_marching,
        )
        matched_station_sweeps.append(sweep)
        added_mass[freq_index][idx] = sweep.pressure_force_sweep.assembly.added_mass
        damping[freq_index][idx] = sweep.pressure_force_sweep.assembly.damping
        sweep_statuses.append(sweep.validity.status)
        coefficient_rows.append(sweep.coefficient_dict())
        heave_condition_rows.append(sweep.heave_condition_numbers)
        pitch_condition_rows.append(sweep.pitch_condition_numbers)
        heave_residual_rows.append(sweep.heave_residuals)
        pitch_residual_rows.append(sweep.pitch_residuals)
        heave_pitch_force_rows.append(sweep.pressure_force_sweep.assembly.complex_force_matrix)
        heave_pitch_end_term_rows.append(sweep.pressure_force_sweep.assembly.end_term_force_matrix)
        if sweep.control_surface_end_term is None:
            heave_pitch_control_surface_end_term_rows.append(np.zeros((2, 2), dtype=complex))
        else:
            heave_pitch_control_surface_end_term_rows.append(
                float(sweep.end_term_scale) * sweep.control_surface_end_term.complex_force_matrix
            )
        heave_pitch_time_force_rows.append(sweep.pressure_force_sweep.assembly.time_derivative_force_matrix)
        heave_pitch_forward_force_rows.append(sweep.pressure_force_sweep.assembly.forward_speed_force_matrix)
        heave_pitch_stokes_body_forward_rows.append(
            sweep.pressure_force_sweep.assembly.stokes_body_forward_speed_force_matrix
        )
        heave_pitch_stokes_body_forward_force_density_rows.append(
            sweep.pressure_force_sweep.stokes_body_forward_speed.force_density_by_station
        )
        heave_pitch_row_measure_transport_rows.append(
            sweep.pressure_force_sweep.row_measure_transport.complex_force_matrix
        )
        heave_pitch_row_measure_transport_force_density_rows.append(
            sweep.pressure_force_sweep.row_measure_transport.force_density_by_station
        )
        heave_pitch_pressure_row_measure_rows.append(
            sweep.pressure_force_sweep.row_measure_transport.pressure_row_measure_by_station
        )
        heave_pitch_pressure_row_measure_x_gradient_rows.append(
            sweep.pressure_force_sweep.row_measure_transport.pressure_row_measure_x_gradient_by_station
        )
        heave_pitch_stokes_m_measure_rows.append(
            sweep.pressure_force_sweep.row_measure_transport.stokes_m_measure_by_station
        )
        body_panel_normal_z_rows.append(
            np.asarray([np.asarray(body.normal_z, dtype=float) for body in sweep.bodies], dtype=float)
        )
        body_panel_length_rows.append(
            np.asarray([np.asarray(body.length_m, dtype=float) for body in sweep.bodies], dtype=float)
        )
        body_panel_node_y_rows.append(
            np.asarray([np.asarray(body.node_y_m, dtype=float) for body in sweep.bodies], dtype=float)
        )
        body_panel_node_z_down_rows.append(
            np.asarray([np.asarray(body.node_z_down_m, dtype=float) for body in sweep.bodies], dtype=float)
        )
        body_panel_delta_y_rows.append(
            np.asarray([np.diff(np.asarray(body.node_y_m, dtype=float)) for body in sweep.bodies], dtype=float)
        )
        heave_body_potential_by_station_rows.append(
            np.asarray(
                [np.asarray(solution.body_potential, dtype=complex) for solution in sweep.heave_mode_solutions],
                dtype=complex,
            )
        )
        pitch_body_potential_by_station_rows.append(
            np.asarray(
                [np.asarray(solution.body_potential, dtype=complex) for solution in sweep.pitch_mode_solutions],
                dtype=complex,
            )
        )
        heave_pressure_body_potential_by_station_rows.append(
            np.asarray(
                [np.asarray(pressure.body_potential, dtype=complex) for pressure in sweep.pressure_force_sweep.heave_mode_pressures],
                dtype=complex,
            )
        )
        pitch_pressure_body_potential_by_station_rows.append(
            np.asarray(
                [np.asarray(pressure.body_potential, dtype=complex) for pressure in sweep.pressure_force_sweep.pitch_mode_pressures],
                dtype=complex,
            )
        )
        inner_free_surface_panel_length_rows.append(
            np.asarray(sweep.inner_free_surface_panel_length_by_station, dtype=float)
        )
        heave_free_surface_potential_by_station_rows.append(
            np.asarray(sweep.heave_free_surface_potential_by_station, dtype=complex)
        )
        pitch_free_surface_potential_by_station_rows.append(
            np.asarray(sweep.pitch_free_surface_potential_by_station, dtype=complex)
        )
        heave_control_potential_by_station_rows.append(
            np.asarray(
                [np.asarray(solution.control_potential, dtype=complex) for solution in sweep.heave_mode_solutions],
                dtype=complex,
            )
        )
        pitch_control_potential_by_station_rows.append(
            np.asarray(
                [np.asarray(solution.control_potential, dtype=complex) for solution in sweep.pitch_mode_solutions],
                dtype=complex,
            )
        )
        control_geometry = build_control_surface_geometry(
            radius_m=float(sweep.control_radius_m),
            panel_count=int(sweep.control_panel_count),
        )
        control_panel_length_rows.append(
            np.broadcast_to(
                np.asarray(control_geometry.length_m, dtype=float),
                (len(sweep.x_m), int(sweep.control_panel_count)),
            ).copy()
        )
        for candidate_index, candidate_name in enumerate(
            sweep.pressure_force_sweep.row_measure_transport.candidate_names
        ):
            if candidate_name not in heave_pitch_row_measure_transport_candidate_rows:
                continue
            heave_pitch_row_measure_transport_candidate_rows[candidate_name].append(
                sweep.pressure_force_sweep.row_measure_transport.candidate_complex_force_matrices[candidate_index]
            )
            heave_pitch_row_measure_transport_candidate_density_rows[candidate_name].append(
                sweep.pressure_force_sweep.row_measure_transport.candidate_force_density_by_station[candidate_index]
            )
            heave_pitch_pressure_row_measure_x_gradient_candidate_rows[candidate_name].append(
                sweep.pressure_force_sweep.row_measure_transport.candidate_pressure_row_measure_x_gradient_by_station[
                    candidate_index
                ]
            )
        heave_free_surface_potential_norm_rows.append(
            np.linalg.norm(sweep.heave_free_surface_potential_by_station, axis=1)
        )
        pitch_free_surface_potential_norm_rows.append(
            np.linalg.norm(sweep.pitch_free_surface_potential_by_station, axis=1)
        )
        heave_free_surface_elevation_norm_rows.append(
            np.linalg.norm(sweep.heave_free_surface_elevation_by_station, axis=1)
        )
        pitch_free_surface_elevation_norm_rows.append(
            np.linalg.norm(sweep.pitch_free_surface_elevation_by_station, axis=1)
        )
        heave_outer_history_rhs_norm_rows.append(np.linalg.norm(sweep.heave_outer_history_rhs_by_station, axis=1))
        pitch_outer_history_rhs_norm_rows.append(np.linalg.norm(sweep.pitch_outer_history_rhs_by_station, axis=1))
        heave_inner_free_surface_normal_derivative_norm_rows.append(
            _solution_array_norms(sweep.heave_mode_solutions, "inner_free_surface_normal_derivative")
        )
        pitch_inner_free_surface_normal_derivative_norm_rows.append(
            _solution_array_norms(sweep.pitch_mode_solutions, "inner_free_surface_normal_derivative")
        )
        heave_increment, heave_gain, heave_alignment, heave_phase = _free_surface_potential_increment_diagnostics(
            sweep.heave_mode_solutions,
            sweep.heave_free_surface_potential_by_station,
            sweep.heave_free_surface_potential_after_station,
            free_surface_velocity_scale=free_surface_velocity_scale,
        )
        pitch_increment, pitch_gain, pitch_alignment, pitch_phase = _free_surface_potential_increment_diagnostics(
            sweep.pitch_mode_solutions,
            sweep.pitch_free_surface_potential_by_station,
            sweep.pitch_free_surface_potential_after_station,
            free_surface_velocity_scale=free_surface_velocity_scale,
        )
        heave_free_surface_potential_increment_norm_rows.append(heave_increment)
        pitch_free_surface_potential_increment_norm_rows.append(pitch_increment)
        heave_free_surface_potential_increment_to_normal_derivative_gain_rows.append(heave_gain)
        pitch_free_surface_potential_increment_to_normal_derivative_gain_rows.append(pitch_gain)
        heave_free_surface_potential_increment_normal_derivative_alignment_rows.append(heave_alignment)
        pitch_free_surface_potential_increment_normal_derivative_alignment_rows.append(pitch_alignment)
        heave_free_surface_potential_increment_normal_derivative_phase_rows.append(heave_phase)
        pitch_free_surface_potential_increment_normal_derivative_phase_rows.append(pitch_phase)
        heave_body_potential_norm = _solution_array_norms(sweep.heave_mode_solutions, "body_potential")
        pitch_body_potential_norm = _solution_array_norms(sweep.pitch_mode_solutions, "body_potential")
        heave_body_potential_norm_rows.append(heave_body_potential_norm)
        pitch_body_potential_norm_rows.append(pitch_body_potential_norm)
        heave_body_normal_velocity_norm_rows.append(
            np.asarray(
                [
                    np.linalg.norm(heave_radiation_normal_velocity(body, float(freq)))
                    for body in sweep.bodies
                ],
                dtype=float,
            )
        )
        pitch_body_normal_velocity_norm_rows.append(
            np.linalg.norm(
                np.asarray(sweep.pitch_body_condition_oscillation_by_station, dtype=complex)
                + np.asarray(sweep.pitch_body_condition_forward_speed_by_station, dtype=complex),
                axis=1,
            )
        )
        pitch_oscillation_condition = np.asarray(sweep.pitch_body_condition_oscillation_by_station, dtype=complex)
        pitch_forward_condition = np.asarray(sweep.pitch_body_condition_forward_speed_by_station, dtype=complex)
        pitch_body_condition_oscillation_norm_rows.append(np.linalg.norm(pitch_oscillation_condition, axis=1))
        pitch_body_condition_forward_speed_norm_rows.append(np.linalg.norm(pitch_forward_condition, axis=1))
        pitch_body_condition_forward_to_oscillation_ratio_rows.append(
            np.asarray(
                [
                    _safe_norm_ratio(pitch_forward_condition[index], pitch_oscillation_condition[index])
                    for index in range(pitch_oscillation_condition.shape[0])
                ],
                dtype=float,
            )
        )
        pitch_body_condition_forward_oscillation_alignment_rows.append(
            np.asarray(
                [
                    _complex_vector_real_alignment(pitch_oscillation_condition[index], pitch_forward_condition[index])
                    for index in range(pitch_oscillation_condition.shape[0])
                ],
                dtype=float,
            )
        )
        pitch_body_condition_forward_oscillation_phase_rows.append(
            np.asarray(
                [
                    _complex_vector_phase_deg(pitch_oscillation_condition[index], pitch_forward_condition[index])
                    for index in range(pitch_oscillation_condition.shape[0])
                ],
                dtype=float,
            )
        )
        heave_control_potential_norm_rows.append(
            _solution_array_norms(sweep.heave_mode_solutions, "control_potential")
        )
        pitch_control_potential_norm_rows.append(
            _solution_array_norms(sweep.pitch_mode_solutions, "control_potential")
        )
        heave_control_normal_derivative_norm_rows.append(
            _solution_array_norms(sweep.heave_mode_solutions, "control_normal_derivative")
        )
        pitch_control_normal_derivative_norm_rows.append(
            _solution_array_norms(sweep.pitch_mode_solutions, "control_normal_derivative")
        )
        for mode_name in ("heave", "pitch"):
            aft_pair_rhs = _aft_pair_rhs_source_norms_for_sweep(sweep, mode_name=mode_name)
            for name, values in aft_pair_rhs.items():
                aft_pair_rhs_norm_rows[f"{mode_name}_aft_pair_{name}"].append(np.asarray(values, dtype=float))
            free_rhs_blocks = _aft_pair_inner_free_surface_rhs_block_arrays_for_sweep(
                sweep,
                mode_name=mode_name,
            )
            for name, values in free_rhs_blocks.items():
                aft_pair_free_rhs_block_rows[
                    f"{mode_name}_aft_pair_inner_free_surface_rhs_block_{name}"
                ].append(np.asarray(values, dtype=float))
        station_geometry = _matched_station_geometry_arrays(hull, sweep.active_station_indices)
        station_x = np.asarray(sweep.x_m, dtype=float)
        station_x_over_l = station_x / max(float(hull.length_m), 1e-30)
        station_local_time = (float(hull.length_m) - station_x) / max(float(speed_mps), 1e-30)
        station_solve_order = np.asarray(sweep.solve_order, dtype=int)
        station_x_m_rows.append(station_x)
        station_x_over_l_rows.append(station_x_over_l)
        station_local_time_rows.append(station_local_time)
        station_solve_order_index_rows.append(station_solve_order.astype(float))
        station_solve_order_x_over_l_rows.append(station_x_over_l[station_solve_order])
        station_solve_order_local_time_rows.append(station_local_time[station_solve_order])
        pitch_base_lever_arm_rows.append(np.asarray(hull.lcg_m - sweep.x_m, dtype=float))
        pitch_radiation_lever_arm_rows.append(
            float(sweep.pitch_radiation_lever_sign) * np.asarray(hull.lcg_m - sweep.x_m, dtype=float)
        )
        pitch_moment_lever_arm_rows.append(
            np.asarray([force.lever_arm_m for force in sweep.pressure_force_sweep.heave_mode_forces], dtype=float)
        )
        if sweep.end_term is None:
            end_term_station_index_rows.append(float("nan"))
            end_term_station_x_over_l_rows.append(float("nan"))
            end_term_lever_arm_rows.append(float("nan"))
        else:
            end_selector = str(sweep.end_station).strip().lower()
            end_index_for_rows = len(sweep.x_m) - 1 if end_selector in {"bow", "forward", "fore"} else 0
            end_term_station_index_rows.append(float(end_index_for_rows))
            end_term_station_x_over_l_rows.append(
                float(sweep.x_m[end_index_for_rows] / max(float(hull.length_m), 1e-30))
            )
            end_term_lever_arm_rows.append(float(sweep.end_term.lever_arm_m))
        station_waterplane_beam = station_geometry["waterplane_beam_m"]
        station_effective_draft = station_geometry["effective_draft_m"]
        station_submerged_area = station_geometry["submerged_area_m2"]
        station_waterplane_beam_rows.append(station_waterplane_beam)
        station_effective_draft_rows.append(station_effective_draft)
        station_submerged_area_rows.append(station_submerged_area)
        station_waterplane_beam_adjacent_jump_rows.append(_adjacent_scalar_relative_jumps(station_waterplane_beam))
        station_effective_draft_adjacent_jump_rows.append(_adjacent_scalar_relative_jumps(station_effective_draft))
        station_submerged_area_adjacent_jump_rows.append(_adjacent_scalar_relative_jumps(station_submerged_area))
        station_waterplane_beam_gradient_gain_rows.append(
            _scalar_gradient_to_value_gains(sweep.x_m, station_waterplane_beam)
        )
        station_effective_draft_gradient_gain_rows.append(
            _scalar_gradient_to_value_gains(sweep.x_m, station_effective_draft)
        )
        station_submerged_area_gradient_gain_rows.append(
            _scalar_gradient_to_value_gains(sweep.x_m, station_submerged_area)
        )
        station_waterplane_beam_gradient_peak_x_over_l_rows.append(
            _station_scalar_peak_x_over_l(
                sweep.x_m,
                _scalar_gradient_to_value_gains(sweep.x_m, station_waterplane_beam),
                hull_length_m=hull.length_m,
            )
        )
        station_submerged_area_gradient_peak_x_over_l_rows.append(
            _station_scalar_peak_x_over_l(
                sweep.x_m,
                _scalar_gradient_to_value_gains(sweep.x_m, station_submerged_area),
                hull_length_m=hull.length_m,
            )
        )
        aft_body = sweep.bodies[0]
        aft_lever_arm = float(sweep.pressure_force_sweep.heave_mode_forces[0].lever_arm_m)
        aft_heave_row, aft_pitch_row = DEFAULT_A1_HEAVE_PITCH_CONVENTION.pressure_generalized_rows(
            aft_body.normal_z,
            aft_body.length_m,
            lever_arm_m=aft_lever_arm,
        )
        aft_active_station_x_over_l_rows.append(float(sweep.x_m[0] / max(float(hull.length_m), 1e-30)))
        aft_active_station_waterplane_beam_rows.append(float(station_waterplane_beam[0]))
        aft_active_station_effective_draft_rows.append(float(station_effective_draft[0]))
        aft_active_station_submerged_area_rows.append(float(station_submerged_area[0]))
        aft_active_station_body_panel_length_sum_rows.append(float(np.sum(aft_body.length_m)))
        aft_active_station_body_panel_length_max_rows.append(float(np.max(aft_body.length_m)))
        aft_active_station_body_panel_normal_z_norm_rows.append(float(np.linalg.norm(aft_body.normal_z)))
        aft_active_station_heave_generalized_row_norm_rows.append(float(np.linalg.norm(aft_heave_row)))
        aft_active_station_pitch_generalized_row_norm_rows.append(float(np.linalg.norm(aft_pitch_row)))
        beam_squared_scale = np.maximum(station_waterplane_beam**2, 1e-30)
        area_scale = np.maximum(station_submerged_area, 1e-30)
        heave_to_beam_squared = _safe_elementwise_ratio(heave_body_potential_norm, beam_squared_scale)
        pitch_to_beam_squared = _safe_elementwise_ratio(pitch_body_potential_norm, beam_squared_scale)
        heave_to_area = _safe_elementwise_ratio(heave_body_potential_norm, area_scale)
        pitch_to_area = _safe_elementwise_ratio(pitch_body_potential_norm, area_scale)
        heave_body_potential_norm_to_beam_squared_ratio_rows.append(heave_to_beam_squared)
        pitch_body_potential_norm_to_beam_squared_ratio_rows.append(pitch_to_beam_squared)
        heave_body_potential_norm_to_submerged_area_ratio_rows.append(heave_to_area)
        pitch_body_potential_norm_to_submerged_area_ratio_rows.append(pitch_to_area)
        heave_body_potential_norm_to_beam_squared_peak_x_over_l_rows.append(
            _station_scalar_peak_x_over_l(sweep.x_m, heave_to_beam_squared, hull_length_m=hull.length_m)
        )
        pitch_body_potential_norm_to_beam_squared_peak_x_over_l_rows.append(
            _station_scalar_peak_x_over_l(sweep.x_m, pitch_to_beam_squared, hull_length_m=hull.length_m)
        )
        heave_body_potential_norm_to_submerged_area_peak_x_over_l_rows.append(
            _station_scalar_peak_x_over_l(sweep.x_m, heave_to_area, hull_length_m=hull.length_m)
        )
        pitch_body_potential_norm_to_submerged_area_peak_x_over_l_rows.append(
            _station_scalar_peak_x_over_l(sweep.x_m, pitch_to_area, hull_length_m=hull.length_m)
        )
        heave_body_pressure_norm_rows.append(_pressure_array_norms(sweep.pressure_force_sweep.heave_mode_pressures, "pressure_pa"))
        pitch_body_pressure_norm_rows.append(_pressure_array_norms(sweep.pressure_force_sweep.pitch_mode_pressures, "pressure_pa"))
        heave_body_pressure_time_derivative_norm_rows.append(
            _pressure_array_norms(sweep.pressure_force_sweep.heave_mode_pressures, "pressure_time_derivative_pa")
        )
        pitch_body_pressure_time_derivative_norm_rows.append(
            _pressure_array_norms(sweep.pressure_force_sweep.pitch_mode_pressures, "pressure_time_derivative_pa")
        )
        heave_body_pressure_forward_speed_norm_rows.append(
            _pressure_array_norms(sweep.pressure_force_sweep.heave_mode_pressures, "pressure_forward_speed_pa")
        )
        pitch_body_pressure_forward_speed_norm_rows.append(
            _pressure_array_norms(sweep.pressure_force_sweep.pitch_mode_pressures, "pressure_forward_speed_pa")
        )
        heave_body_pressure_to_body_potential_gain_rows.append(
            _pressure_to_state_gain(
                sweep.pressure_force_sweep.heave_mode_pressures,
                "pressure_pa",
                np.asarray([solution.body_potential for solution in sweep.heave_mode_solutions], dtype=complex),
            )
        )
        pitch_body_pressure_to_body_potential_gain_rows.append(
            _pressure_to_state_gain(
                sweep.pressure_force_sweep.pitch_mode_pressures,
                "pressure_pa",
                np.asarray([solution.body_potential for solution in sweep.pitch_mode_solutions], dtype=complex),
            )
        )
        heave_body_pressure_to_free_surface_potential_after_gain_rows.append(
            _pressure_to_state_gain(
                sweep.pressure_force_sweep.heave_mode_pressures,
                "pressure_pa",
                sweep.heave_free_surface_potential_after_station,
            )
        )
        pitch_body_pressure_to_free_surface_potential_after_gain_rows.append(
            _pressure_to_state_gain(
                sweep.pressure_force_sweep.pitch_mode_pressures,
                "pressure_pa",
                sweep.pitch_free_surface_potential_after_station,
            )
        )
        heave_body_pressure_forward_to_time_norm_ratio_rows.append(
            np.asarray(
                [
                    _safe_norm_ratio(pressure.pressure_forward_speed_pa, pressure.pressure_time_derivative_pa)
                    for pressure in sweep.pressure_force_sweep.heave_mode_pressures
                ],
                dtype=float,
            )
        )
        pitch_body_pressure_forward_to_time_norm_ratio_rows.append(
            np.asarray(
                [
                    _safe_norm_ratio(pressure.pressure_forward_speed_pa, pressure.pressure_time_derivative_pa)
                    for pressure in sweep.pressure_force_sweep.pitch_mode_pressures
                ],
                dtype=float,
            )
        )
        heave_pressure_time_formula_ratio_rows.append(
            _pressure_formula_ratios(sweep.pressure_force_sweep.heave_mode_pressures, component="time")
        )
        pitch_pressure_time_formula_ratio_rows.append(
            _pressure_formula_ratios(sweep.pressure_force_sweep.pitch_mode_pressures, component="time")
        )
        heave_pressure_forward_formula_ratio_rows.append(
            _pressure_formula_ratios(sweep.pressure_force_sweep.heave_mode_pressures, component="forward")
        )
        pitch_pressure_forward_formula_ratio_rows.append(
            _pressure_formula_ratios(sweep.pressure_force_sweep.pitch_mode_pressures, component="forward")
        )
        heave_phi = np.asarray([solution.body_potential for solution in sweep.heave_mode_solutions], dtype=complex)
        pitch_phi = np.asarray([solution.body_potential for solution in sweep.pitch_mode_solutions], dtype=complex)
        heave_adjacent_jump, heave_adjacent_ratio, heave_adjacent_alignment, heave_adjacent_phase = (
            _adjacent_complex_state_diagnostics(heave_phi)
        )
        pitch_adjacent_jump, pitch_adjacent_ratio, pitch_adjacent_alignment, pitch_adjacent_phase = (
            _adjacent_complex_state_diagnostics(pitch_phi)
        )
        heave_phase_aligned_phi = _phase_align_adjacent_complex_states(heave_phi)
        pitch_phase_aligned_phi = _phase_align_adjacent_complex_states(pitch_phi)
        (
            heave_phase_aligned_adjacent_jump,
            _heave_phase_aligned_adjacent_ratio,
            heave_phase_aligned_adjacent_alignment,
            heave_phase_aligned_adjacent_phase,
        ) = _adjacent_complex_state_diagnostics(heave_phase_aligned_phi)
        (
            pitch_phase_aligned_adjacent_jump,
            _pitch_phase_aligned_adjacent_ratio,
            pitch_phase_aligned_adjacent_alignment,
            pitch_phase_aligned_adjacent_phase,
        ) = _adjacent_complex_state_diagnostics(pitch_phase_aligned_phi)
        (
            body_panel_mid_y_jump,
            body_panel_mid_z_jump,
            body_panel_normal_jump,
            body_panel_length_jump,
        ) = _adjacent_panel_geometry_diagnostics(sweep.bodies)
        heave_adjacent_body_potential_relative_jump_rows.append(heave_adjacent_jump)
        pitch_adjacent_body_potential_relative_jump_rows.append(pitch_adjacent_jump)
        heave_adjacent_body_potential_symmetric_norm_ratio_rows.append(heave_adjacent_ratio)
        pitch_adjacent_body_potential_symmetric_norm_ratio_rows.append(pitch_adjacent_ratio)
        heave_adjacent_body_potential_real_alignment_rows.append(heave_adjacent_alignment)
        pitch_adjacent_body_potential_real_alignment_rows.append(pitch_adjacent_alignment)
        heave_adjacent_body_potential_phase_rows.append(heave_adjacent_phase)
        pitch_adjacent_body_potential_phase_rows.append(pitch_adjacent_phase)
        heave_phase_aligned_adjacent_body_potential_relative_jump_rows.append(heave_phase_aligned_adjacent_jump)
        pitch_phase_aligned_adjacent_body_potential_relative_jump_rows.append(pitch_phase_aligned_adjacent_jump)
        heave_phase_aligned_adjacent_body_potential_real_alignment_rows.append(
            heave_phase_aligned_adjacent_alignment
        )
        pitch_phase_aligned_adjacent_body_potential_real_alignment_rows.append(
            pitch_phase_aligned_adjacent_alignment
        )
        heave_phase_aligned_adjacent_body_potential_phase_rows.append(heave_phase_aligned_adjacent_phase)
        pitch_phase_aligned_adjacent_body_potential_phase_rows.append(pitch_phase_aligned_adjacent_phase)
        body_panel_mid_y_adjacent_relative_jump_rows.append(body_panel_mid_y_jump)
        body_panel_mid_z_adjacent_relative_jump_rows.append(body_panel_mid_z_jump)
        body_panel_normal_adjacent_relative_jump_rows.append(body_panel_normal_jump)
        body_panel_length_adjacent_relative_jump_rows.append(body_panel_length_jump)
        heave_gradient_gain = _potential_gradient_to_potential_gains(
            sweep.pressure_force_sweep.heave_potential_gradient,
            heave_phi,
        )
        pitch_gradient_gain = _potential_gradient_to_potential_gains(
            sweep.pressure_force_sweep.pitch_potential_gradient,
            pitch_phi,
        )
        heave_body_potential_x_gradient_norm_rows.append(
            _potential_gradient_norms(sweep.pressure_force_sweep.heave_potential_gradient)
        )
        pitch_body_potential_x_gradient_norm_rows.append(
            _potential_gradient_norms(sweep.pressure_force_sweep.pitch_potential_gradient)
        )
        heave_body_potential_x_gradient_to_potential_gain_rows.append(heave_gradient_gain)
        pitch_body_potential_x_gradient_to_potential_gain_rows.append(pitch_gradient_gain)
        heave_body_potential_x_gradient_characteristic_length_rows.append(
            _potential_gradient_characteristic_lengths(
                sweep.pressure_force_sweep.heave_potential_gradient,
                heave_phi,
            )
        )
        pitch_body_potential_x_gradient_characteristic_length_rows.append(
            _potential_gradient_characteristic_lengths(
                sweep.pressure_force_sweep.pitch_potential_gradient,
                pitch_phi,
            )
        )
        heave_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * heave_gradient_gain
        )
        pitch_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * pitch_gradient_gain
        )
        heave_phase_aligned_gradient = estimate_body_potential_x_gradient(
            sweep.x_m,
            heave_phase_aligned_phi,
            scheme=pressure_gradient_scheme,
        )
        pitch_phase_aligned_gradient = estimate_body_potential_x_gradient(
            sweep.x_m,
            pitch_phase_aligned_phi,
            scheme=pressure_gradient_scheme,
        )
        heave_phase_aligned_gradient_gain = _potential_gradient_to_potential_gains(
            heave_phase_aligned_gradient,
            heave_phase_aligned_phi,
        )
        pitch_phase_aligned_gradient_gain = _potential_gradient_to_potential_gains(
            pitch_phase_aligned_gradient,
            pitch_phase_aligned_phi,
        )
        heave_phase_aligned_body_potential_x_gradient_to_potential_gain_rows.append(
            heave_phase_aligned_gradient_gain
        )
        pitch_phase_aligned_body_potential_x_gradient_to_potential_gain_rows.append(
            pitch_phase_aligned_gradient_gain
        )
        heave_phase_aligned_body_potential_x_gradient_characteristic_length_rows.append(
            _potential_gradient_characteristic_lengths(
                heave_phase_aligned_gradient,
                heave_phase_aligned_phi,
            )
        )
        pitch_phase_aligned_body_potential_x_gradient_characteristic_length_rows.append(
            _potential_gradient_characteristic_lengths(
                pitch_phase_aligned_gradient,
                pitch_phase_aligned_phi,
            )
        )
        heave_phase_aligned_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * heave_phase_aligned_gradient_gain
        )
        pitch_phase_aligned_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * pitch_phase_aligned_gradient_gain
        )
        heave_phase_aligned_gradient_gain_to_raw_gain_ratio_rows.append(
            _safe_elementwise_ratio(heave_phase_aligned_gradient_gain, heave_gradient_gain)
        )
        pitch_phase_aligned_gradient_gain_to_raw_gain_ratio_rows.append(
            _safe_elementwise_ratio(pitch_phase_aligned_gradient_gain, pitch_gradient_gain)
        )
        heave_scheme_gains: dict[str, np.ndarray] = {}
        pitch_scheme_gains: dict[str, np.ndarray] = {}
        heave_phase_aligned_scheme_gains: dict[str, np.ndarray] = {}
        pitch_phase_aligned_scheme_gains: dict[str, np.ndarray] = {}
        for diagnostic_scheme in ("central", "forward", "backward"):
            heave_scheme_gradient = estimate_body_potential_x_gradient(
                sweep.x_m,
                heave_phi,
                scheme=diagnostic_scheme,
            )
            pitch_scheme_gradient = estimate_body_potential_x_gradient(
                sweep.x_m,
                pitch_phi,
                scheme=diagnostic_scheme,
            )
            heave_phase_aligned_scheme_gradient = estimate_body_potential_x_gradient(
                sweep.x_m,
                heave_phase_aligned_phi,
                scheme=diagnostic_scheme,
            )
            pitch_phase_aligned_scheme_gradient = estimate_body_potential_x_gradient(
                sweep.x_m,
                pitch_phase_aligned_phi,
                scheme=diagnostic_scheme,
            )
            heave_scheme_gains[diagnostic_scheme] = _potential_gradient_to_potential_gains(
                heave_scheme_gradient,
                heave_phi,
            )
            pitch_scheme_gains[diagnostic_scheme] = _potential_gradient_to_potential_gains(
                pitch_scheme_gradient,
                pitch_phi,
            )
            heave_phase_aligned_scheme_gains[diagnostic_scheme] = _potential_gradient_to_potential_gains(
                heave_phase_aligned_scheme_gradient,
                heave_phase_aligned_phi,
            )
            pitch_phase_aligned_scheme_gains[diagnostic_scheme] = _potential_gradient_to_potential_gains(
                pitch_phase_aligned_scheme_gradient,
                pitch_phase_aligned_phi,
            )
        heave_central_body_potential_x_gradient_to_potential_gain_rows.append(heave_scheme_gains["central"])
        pitch_central_body_potential_x_gradient_to_potential_gain_rows.append(pitch_scheme_gains["central"])
        heave_forward_body_potential_x_gradient_to_potential_gain_rows.append(heave_scheme_gains["forward"])
        pitch_forward_body_potential_x_gradient_to_potential_gain_rows.append(pitch_scheme_gains["forward"])
        heave_backward_body_potential_x_gradient_to_potential_gain_rows.append(heave_scheme_gains["backward"])
        pitch_backward_body_potential_x_gradient_to_potential_gain_rows.append(pitch_scheme_gains["backward"])
        heave_central_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * heave_scheme_gains["central"]
        )
        pitch_central_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * pitch_scheme_gains["central"]
        )
        heave_forward_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * heave_scheme_gains["forward"]
        )
        pitch_forward_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * pitch_scheme_gains["forward"]
        )
        heave_backward_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * heave_scheme_gains["backward"]
        )
        pitch_backward_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * pitch_scheme_gains["backward"]
        )
        heave_phase_aligned_central_body_potential_x_gradient_to_potential_gain_rows.append(
            heave_phase_aligned_scheme_gains["central"]
        )
        pitch_phase_aligned_central_body_potential_x_gradient_to_potential_gain_rows.append(
            pitch_phase_aligned_scheme_gains["central"]
        )
        heave_phase_aligned_forward_body_potential_x_gradient_to_potential_gain_rows.append(
            heave_phase_aligned_scheme_gains["forward"]
        )
        pitch_phase_aligned_forward_body_potential_x_gradient_to_potential_gain_rows.append(
            pitch_phase_aligned_scheme_gains["forward"]
        )
        heave_phase_aligned_backward_body_potential_x_gradient_to_potential_gain_rows.append(
            heave_phase_aligned_scheme_gains["backward"]
        )
        pitch_phase_aligned_backward_body_potential_x_gradient_to_potential_gain_rows.append(
            pitch_phase_aligned_scheme_gains["backward"]
        )
        heave_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * heave_phase_aligned_scheme_gains["central"]
        )
        pitch_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * pitch_phase_aligned_scheme_gains["central"]
        )
        heave_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * heave_phase_aligned_scheme_gains["forward"]
        )
        pitch_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * pitch_phase_aligned_scheme_gains["forward"]
        )
        heave_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * heave_phase_aligned_scheme_gains["backward"]
        )
        pitch_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length_rows.append(
            float(hull.length_m) * pitch_phase_aligned_scheme_gains["backward"]
        )

        station_lever_arms = np.asarray(
            [force.lever_arm_m for force in sweep.pressure_force_sweep.heave_mode_forces],
            dtype=float,
        )

        def _with_candidate_gradient_values(
            base_gradient: StationPotentialGradient,
            values: np.ndarray,
            *,
            scheme: str,
        ) -> StationPotentialGradient:
            return StationPotentialGradient(
                x_m=np.asarray(base_gradient.x_m, dtype=float),
                body_potential_x_gradient=np.asarray(values, dtype=complex),
                scheme=scheme,
                validity=base_gradient.validity,
            )

        def _append_forward_speed_gradient_candidate(
            candidate_name: str,
            heave_gradient: StationPotentialGradient,
            pitch_gradient: StationPotentialGradient,
        ) -> None:
            density = _forward_speed_force_density_for_body_potential_gradient(
                sweep.x_m,
                sweep.bodies,
                sweep.heave_mode_solutions,
                sweep.pitch_mode_solutions,
                heave_gradient,
                pitch_gradient,
                omega_rad_s=float(freq),
                rho_water_kg_m3=rho_water_kg_m3,
                forward_speed_mps=speed_mps,
                lever_arms_m=station_lever_arms,
                pressure_gradient_scale=pressure_gradient_scale,
            )
            heave_pitch_forward_force_gradient_candidate_density_rows[candidate_name].append(density)
            heave_pitch_forward_force_gradient_candidate_rows[candidate_name].append(
                np.asarray(np.trapezoid(density, np.asarray(sweep.x_m, dtype=float), axis=0), dtype=complex)
            )
            heave_body_potential_x_gradient_candidate_rows[candidate_name].append(
                np.asarray(heave_gradient.body_potential_x_gradient, dtype=complex)
            )
            pitch_body_potential_x_gradient_candidate_rows[candidate_name].append(
                np.asarray(pitch_gradient.body_potential_x_gradient, dtype=complex)
            )

        heave_current_gradient_values = np.asarray(
            sweep.pressure_force_sweep.heave_potential_gradient.body_potential_x_gradient,
            dtype=complex,
        )
        pitch_current_gradient_values = np.asarray(
            sweep.pressure_force_sweep.pitch_potential_gradient.body_potential_x_gradient,
            dtype=complex,
        )
        current_default_forward_density = _force_density_matrix_from_section_results(
            sweep.pressure_force_sweep.heave_mode_forces,
            sweep.pressure_force_sweep.pitch_mode_forces,
            heave_attr="heave_force_forward_speed_per_m",
            pitch_attr="pitch_moment_forward_speed_per_m",
        )
        heave_pitch_forward_force_gradient_candidate_density_rows["current_default"].append(
            current_default_forward_density
        )
        heave_pitch_forward_force_gradient_candidate_rows["current_default"].append(
            np.asarray(sweep.pressure_force_sweep.assembly.forward_speed_force_matrix, dtype=complex)
        )
        heave_body_potential_x_gradient_candidate_rows["current_default"].append(heave_current_gradient_values)
        pitch_body_potential_x_gradient_candidate_rows["current_default"].append(pitch_current_gradient_values)
        for candidate_scheme in ("central", "forward", "backward"):
            _append_forward_speed_gradient_candidate(
                f"scheme_{candidate_scheme}",
                estimate_body_potential_x_gradient(sweep.x_m, heave_phi, scheme=candidate_scheme),
                estimate_body_potential_x_gradient(sweep.x_m, pitch_phi, scheme=candidate_scheme),
            )
            _append_forward_speed_gradient_candidate(
                f"phase_aligned_{candidate_scheme}",
                estimate_body_potential_x_gradient(sweep.x_m, heave_phase_aligned_phi, scheme=candidate_scheme),
                estimate_body_potential_x_gradient(sweep.x_m, pitch_phase_aligned_phi, scheme=candidate_scheme),
            )
            _append_forward_speed_gradient_candidate(
                f"mapped_fixed_y_{candidate_scheme}",
                estimate_mapped_body_potential_x_gradient(
                    sweep.x_m,
                    sweep.bodies,
                    heave_phi,
                    scheme=candidate_scheme,
                    mapping="fixed_y",
                ),
                estimate_mapped_body_potential_x_gradient(
                    sweep.x_m,
                    sweep.bodies,
                    pitch_phi,
                    scheme=candidate_scheme,
                    mapping="fixed_y",
                ),
            )
            _append_forward_speed_gradient_candidate(
                f"mapped_normalized_y_{candidate_scheme}",
                estimate_mapped_body_potential_x_gradient(
                    sweep.x_m,
                    sweep.bodies,
                    heave_phi,
                    scheme=candidate_scheme,
                    mapping="normalized_y",
                ),
                estimate_mapped_body_potential_x_gradient(
                    sweep.x_m,
                    sweep.bodies,
                    pitch_phi,
                    scheme=candidate_scheme,
                    mapping="normalized_y",
                ),
            )

        heave_aft_zero_gradient = np.array(heave_current_gradient_values, dtype=complex, copy=True)
        pitch_aft_zero_gradient = np.array(pitch_current_gradient_values, dtype=complex, copy=True)
        heave_aft_zero_gradient[0] = 0.0
        pitch_aft_zero_gradient[0] = 0.0
        _append_forward_speed_gradient_candidate(
            "startup_aft_gradient_zero",
            _with_candidate_gradient_values(
                sweep.pressure_force_sweep.heave_potential_gradient,
                heave_aft_zero_gradient,
                scheme="startup_aft_gradient_zero",
            ),
            _with_candidate_gradient_values(
                sweep.pressure_force_sweep.pitch_potential_gradient,
                pitch_aft_zero_gradient,
                scheme="startup_aft_gradient_zero",
            ),
        )

        heave_aft_copy_second_gradient = np.array(heave_current_gradient_values, dtype=complex, copy=True)
        pitch_aft_copy_second_gradient = np.array(pitch_current_gradient_values, dtype=complex, copy=True)
        if heave_aft_copy_second_gradient.shape[0] > 1:
            heave_aft_copy_second_gradient[0] = heave_aft_copy_second_gradient[1]
            pitch_aft_copy_second_gradient[0] = pitch_aft_copy_second_gradient[1]
        _append_forward_speed_gradient_candidate(
            "startup_aft_gradient_copy_second",
            _with_candidate_gradient_values(
                sweep.pressure_force_sweep.heave_potential_gradient,
                heave_aft_copy_second_gradient,
                scheme="startup_aft_gradient_copy_second",
            ),
            _with_candidate_gradient_values(
                sweep.pressure_force_sweep.pitch_potential_gradient,
                pitch_aft_copy_second_gradient,
                scheme="startup_aft_gradient_copy_second",
            ),
        )

        heave_first_pair_average_gradient = np.array(heave_current_gradient_values, dtype=complex, copy=True)
        pitch_first_pair_average_gradient = np.array(pitch_current_gradient_values, dtype=complex, copy=True)
        if heave_first_pair_average_gradient.shape[0] > 1:
            heave_first_pair_average_gradient[0:2] = np.mean(heave_first_pair_average_gradient[0:2], axis=0)
            pitch_first_pair_average_gradient[0:2] = np.mean(pitch_first_pair_average_gradient[0:2], axis=0)
        _append_forward_speed_gradient_candidate(
            "startup_first_pair_gradient_average",
            _with_candidate_gradient_values(
                sweep.pressure_force_sweep.heave_potential_gradient,
                heave_first_pair_average_gradient,
                scheme="startup_first_pair_gradient_average",
            ),
            _with_candidate_gradient_values(
                sweep.pressure_force_sweep.pitch_potential_gradient,
                pitch_first_pair_average_gradient,
                scheme="startup_first_pair_gradient_average",
            ),
        )

        heave_mode_heave_force_to_pressure_norm_gain_rows.append(
            _force_to_pressure_norm_gains(
                sweep.pressure_force_sweep.heave_mode_pressures,
                sweep.pressure_force_sweep.heave_mode_forces,
                "heave_force_per_m",
            )
        )
        heave_mode_pitch_moment_to_pressure_norm_gain_rows.append(
            _force_to_pressure_norm_gains(
                sweep.pressure_force_sweep.heave_mode_pressures,
                sweep.pressure_force_sweep.heave_mode_forces,
                "pitch_moment_per_m",
            )
        )
        pitch_mode_heave_force_to_pressure_norm_gain_rows.append(
            _force_to_pressure_norm_gains(
                sweep.pressure_force_sweep.pitch_mode_pressures,
                sweep.pressure_force_sweep.pitch_mode_forces,
                "heave_force_per_m",
            )
        )
        pitch_mode_pitch_moment_to_pressure_norm_gain_rows.append(
            _force_to_pressure_norm_gains(
                sweep.pressure_force_sweep.pitch_mode_pressures,
                sweep.pressure_force_sweep.pitch_mode_forces,
                "pitch_moment_per_m",
            )
        )
        total_force_density = _force_density_matrix_from_section_results(
            sweep.pressure_force_sweep.heave_mode_forces,
            sweep.pressure_force_sweep.pitch_mode_forces,
            heave_attr="heave_force_per_m",
            pitch_attr="pitch_moment_per_m",
        )
        time_force_density = _force_density_matrix_from_section_results(
            sweep.pressure_force_sweep.heave_mode_forces,
            sweep.pressure_force_sweep.pitch_mode_forces,
            heave_attr="heave_force_time_derivative_per_m",
            pitch_attr="pitch_moment_time_derivative_per_m",
        )
        forward_force_density = _force_density_matrix_from_section_results(
            sweep.pressure_force_sweep.heave_mode_forces,
            sweep.pressure_force_sweep.pitch_mode_forces,
            heave_attr="heave_force_forward_speed_per_m",
            pitch_attr="pitch_moment_forward_speed_per_m",
        )
        heave_pitch_total_force_density_rows.append(total_force_density)
        heave_pitch_time_force_density_rows.append(time_force_density)
        heave_pitch_forward_force_density_rows.append(forward_force_density)
        (
            total_peak_x,
            total_peak_abs,
            total_peak_to_integral,
            total_centroid_x,
        ) = _force_density_peak_diagnostics(
            sweep.x_m,
            total_force_density,
            hull_length_m=hull.length_m,
        )
        (
            time_peak_x,
            time_peak_abs,
            time_peak_to_integral,
            time_centroid_x,
        ) = _force_density_peak_diagnostics(
            sweep.x_m,
            time_force_density,
            hull_length_m=hull.length_m,
        )
        (
            forward_peak_x,
            forward_peak_abs,
            forward_peak_to_integral,
            forward_centroid_x,
        ) = _force_density_peak_diagnostics(
            sweep.x_m,
            forward_force_density,
            hull_length_m=hull.length_m,
        )
        heave_pitch_total_force_density_peak_x_over_l_rows.append(total_peak_x)
        heave_pitch_time_force_density_peak_x_over_l_rows.append(time_peak_x)
        heave_pitch_forward_force_density_peak_x_over_l_rows.append(forward_peak_x)
        heave_pitch_total_force_density_peak_abs_rows.append(total_peak_abs)
        heave_pitch_time_force_density_peak_abs_rows.append(time_peak_abs)
        heave_pitch_forward_force_density_peak_abs_rows.append(forward_peak_abs)
        heave_pitch_total_force_density_peak_to_integral_abs_ratio_rows.append(total_peak_to_integral)
        heave_pitch_time_force_density_peak_to_integral_abs_ratio_rows.append(time_peak_to_integral)
        heave_pitch_forward_force_density_peak_to_integral_abs_ratio_rows.append(forward_peak_to_integral)
        heave_pitch_total_force_density_abs_centroid_x_over_l_rows.append(total_centroid_x)
        heave_pitch_time_force_density_abs_centroid_x_over_l_rows.append(time_centroid_x)
        heave_pitch_forward_force_density_abs_centroid_x_over_l_rows.append(forward_centroid_x)
        heave_pitch_pressure_force_matrices_excluding_aft_active_station_rows.append(
            _integrate_force_density_station_subset(sweep.x_m, total_force_density, start_index=1)
        )
        heave_pitch_pressure_force_matrices_excluding_bow_active_station_rows.append(
            _integrate_force_density_station_subset(
                sweep.x_m,
                total_force_density,
                start_index=0,
                stop_index=total_force_density.shape[0] - 1,
            )
        )
        heave_pitch_pressure_force_matrices_excluding_end_active_stations_rows.append(
            _integrate_force_density_station_subset(
                sweep.x_m,
                total_force_density,
                start_index=1,
                stop_index=total_force_density.shape[0] - 1,
            )
        )
        heave_pitch_time_force_matrices_excluding_aft_active_station_rows.append(
            _integrate_force_density_station_subset(sweep.x_m, time_force_density, start_index=1)
        )
        heave_pitch_forward_force_matrices_excluding_aft_active_station_rows.append(
            _integrate_force_density_station_subset(sweep.x_m, forward_force_density, start_index=1)
        )
        heave_pitch_total_force_density_aft_abs_rows.append(np.abs(total_force_density[0]))
        heave_pitch_time_force_density_aft_abs_rows.append(np.abs(time_force_density[0]))
        heave_pitch_forward_force_density_aft_abs_rows.append(np.abs(forward_force_density[0]))
        heave_eq24_relative_residual_rows.append(
            np.asarray([audit.row_relative_residual("eq24_outer_control") for audit in sweep.heave_block_audits])
        )
        pitch_eq24_relative_residual_rows.append(
            np.asarray([audit.row_relative_residual("eq24_outer_control") for audit in sweep.pitch_block_audits])
        )
    return FrequencyDomainHydrodynamics(
        omega=omega,
        encounter_omega=np.asarray(encounter, dtype=float),
        added_mass=added_mass,
        radiation_damping=damping,
        excitation=excitation,
        restoring=restoring,
        contribution_breakdown={
            "heave_condition_numbers": np.asarray(heave_condition_rows, dtype=float),
            "pitch_condition_numbers": np.asarray(pitch_condition_rows, dtype=float),
            "heave_residuals": np.asarray(heave_residual_rows, dtype=float),
            "pitch_residuals": np.asarray(pitch_residual_rows, dtype=float),
            "heave_pitch_complex_force_matrices": np.asarray(heave_pitch_force_rows, dtype=complex),
            "heave_pitch_end_term_force_matrices": np.asarray(heave_pitch_end_term_rows, dtype=complex),
            "heave_pitch_control_surface_end_term_force_matrices_diagnostic": np.asarray(
                heave_pitch_control_surface_end_term_rows,
                dtype=complex,
            ),
            "heave_pitch_time_derivative_force_matrices": np.asarray(heave_pitch_time_force_rows, dtype=complex),
            "heave_pitch_forward_speed_force_matrices": np.asarray(heave_pitch_forward_force_rows, dtype=complex),
            "heave_pitch_forward_speed_force_gradient_candidate_names": np.asarray(
                gradient_candidate_names,
                dtype=str,
            ),
            **{
                f"heave_pitch_forward_speed_force_matrices_gradient_candidate_{candidate_name}": np.asarray(
                    candidate_rows,
                    dtype=complex,
                )
                for candidate_name, candidate_rows in heave_pitch_forward_force_gradient_candidate_rows.items()
            },
            **{
                f"heave_pitch_forward_speed_force_density_gradient_candidate_{candidate_name}": np.asarray(
                    candidate_rows,
                    dtype=complex,
                )
                for candidate_name, candidate_rows in heave_pitch_forward_force_gradient_candidate_density_rows.items()
            },
            **{
                f"heave_body_potential_x_gradient_candidate_{candidate_name}": np.asarray(
                    candidate_rows,
                    dtype=complex,
                )
                for candidate_name, candidate_rows in heave_body_potential_x_gradient_candidate_rows.items()
            },
            **{
                f"pitch_body_potential_x_gradient_candidate_{candidate_name}": np.asarray(
                    candidate_rows,
                    dtype=complex,
                )
                for candidate_name, candidate_rows in pitch_body_potential_x_gradient_candidate_rows.items()
            },
            "heave_pitch_stokes_body_forward_speed_force_matrices": np.asarray(
                heave_pitch_stokes_body_forward_rows,
                dtype=complex,
            ),
            "heave_pitch_stokes_body_forward_speed_force_density_by_station": np.asarray(
                heave_pitch_stokes_body_forward_force_density_rows,
                dtype=complex,
            ),
            "heave_pitch_row_measure_transport_force_matrices": np.asarray(
                heave_pitch_row_measure_transport_rows,
                dtype=complex,
            ),
            "heave_pitch_row_measure_transport_force_density_by_station": np.asarray(
                heave_pitch_row_measure_transport_force_density_rows,
                dtype=complex,
            ),
            "heave_pitch_pressure_row_measure_by_station": np.asarray(
                heave_pitch_pressure_row_measure_rows,
                dtype=float,
            ),
            "heave_pitch_pressure_row_measure_x_gradient_by_station": np.asarray(
                heave_pitch_pressure_row_measure_x_gradient_rows,
                dtype=float,
            ),
            "heave_pitch_stokes_m_measure_by_station": np.asarray(
                heave_pitch_stokes_m_measure_rows,
                dtype=float,
            ),
            "body_panel_normal_z_by_station": np.asarray(body_panel_normal_z_rows, dtype=float),
            "body_panel_length_by_station": np.asarray(body_panel_length_rows, dtype=float),
            "body_panel_node_y_by_station": np.asarray(body_panel_node_y_rows, dtype=float),
            "body_panel_node_z_down_by_station": np.asarray(body_panel_node_z_down_rows, dtype=float),
            "body_panel_delta_y_by_station": np.asarray(body_panel_delta_y_rows, dtype=float),
            "heave_body_potential_by_station": np.asarray(
                heave_body_potential_by_station_rows,
                dtype=complex,
            ),
            "pitch_body_potential_by_station": np.asarray(
                pitch_body_potential_by_station_rows,
                dtype=complex,
            ),
            "heave_pressure_body_potential_by_station": np.asarray(
                heave_pressure_body_potential_by_station_rows,
                dtype=complex,
            ),
            "pitch_pressure_body_potential_by_station": np.asarray(
                pitch_pressure_body_potential_by_station_rows,
                dtype=complex,
            ),
            "inner_free_surface_panel_length_by_station": np.asarray(
                inner_free_surface_panel_length_rows,
                dtype=float,
            ),
            "heave_free_surface_potential_by_station": np.asarray(
                heave_free_surface_potential_by_station_rows,
                dtype=complex,
            ),
            "pitch_free_surface_potential_by_station": np.asarray(
                pitch_free_surface_potential_by_station_rows,
                dtype=complex,
            ),
            "heave_control_potential_by_station": np.asarray(
                heave_control_potential_by_station_rows,
                dtype=complex,
            ),
            "pitch_control_potential_by_station": np.asarray(
                pitch_control_potential_by_station_rows,
                dtype=complex,
            ),
            "control_panel_length_by_station": np.asarray(control_panel_length_rows, dtype=float),
            "heave_pitch_row_measure_transport_mapping_candidate_names": np.asarray(
                row_measure_mapping_candidate_names,
                dtype=str,
            ),
            **{
                f"heave_pitch_row_measure_transport_force_matrices_mapping_candidate_{candidate_name}": np.asarray(
                    candidate_rows,
                    dtype=complex,
                )
                for candidate_name, candidate_rows in heave_pitch_row_measure_transport_candidate_rows.items()
            },
            **{
                f"heave_pitch_row_measure_transport_force_density_mapping_candidate_{candidate_name}": np.asarray(
                    candidate_rows,
                    dtype=complex,
                )
                for candidate_name, candidate_rows in heave_pitch_row_measure_transport_candidate_density_rows.items()
            },
            **{
                f"heave_pitch_pressure_row_measure_x_gradient_mapping_candidate_{candidate_name}": np.asarray(
                    candidate_rows,
                    dtype=float,
                )
                for candidate_name, candidate_rows in heave_pitch_pressure_row_measure_x_gradient_candidate_rows.items()
            },
            "heave_free_surface_potential_norms": np.asarray(heave_free_surface_potential_norm_rows, dtype=float),
            "pitch_free_surface_potential_norms": np.asarray(pitch_free_surface_potential_norm_rows, dtype=float),
            "heave_free_surface_elevation_norms": np.asarray(heave_free_surface_elevation_norm_rows, dtype=float),
            "pitch_free_surface_elevation_norms": np.asarray(pitch_free_surface_elevation_norm_rows, dtype=float),
            "heave_outer_history_rhs_norms": np.asarray(heave_outer_history_rhs_norm_rows, dtype=float),
            "pitch_outer_history_rhs_norms": np.asarray(pitch_outer_history_rhs_norm_rows, dtype=float),
            "heave_inner_free_surface_normal_derivative_norms": np.asarray(
                heave_inner_free_surface_normal_derivative_norm_rows,
                dtype=float,
            ),
            "pitch_inner_free_surface_normal_derivative_norms": np.asarray(
                pitch_inner_free_surface_normal_derivative_norm_rows,
                dtype=float,
            ),
            "heave_free_surface_potential_increment_norms": np.asarray(
                heave_free_surface_potential_increment_norm_rows,
                dtype=float,
            ),
            "pitch_free_surface_potential_increment_norms": np.asarray(
                pitch_free_surface_potential_increment_norm_rows,
                dtype=float,
            ),
            "heave_free_surface_potential_increment_to_normal_derivative_gains": np.asarray(
                heave_free_surface_potential_increment_to_normal_derivative_gain_rows,
                dtype=float,
            ),
            "pitch_free_surface_potential_increment_to_normal_derivative_gains": np.asarray(
                pitch_free_surface_potential_increment_to_normal_derivative_gain_rows,
                dtype=float,
            ),
            "heave_free_surface_potential_increment_normal_derivative_alignments": np.asarray(
                heave_free_surface_potential_increment_normal_derivative_alignment_rows,
                dtype=float,
            ),
            "pitch_free_surface_potential_increment_normal_derivative_alignments": np.asarray(
                pitch_free_surface_potential_increment_normal_derivative_alignment_rows,
                dtype=float,
            ),
            "heave_free_surface_potential_increment_normal_derivative_phase_degs": np.asarray(
                heave_free_surface_potential_increment_normal_derivative_phase_rows,
                dtype=float,
            ),
            "pitch_free_surface_potential_increment_normal_derivative_phase_degs": np.asarray(
                pitch_free_surface_potential_increment_normal_derivative_phase_rows,
                dtype=float,
            ),
            "heave_body_potential_norms": np.asarray(heave_body_potential_norm_rows, dtype=float),
            "pitch_body_potential_norms": np.asarray(pitch_body_potential_norm_rows, dtype=float),
            "heave_body_normal_velocity_norms": np.asarray(
                heave_body_normal_velocity_norm_rows,
                dtype=float,
            ),
            "pitch_body_normal_velocity_norms": np.asarray(
                pitch_body_normal_velocity_norm_rows,
                dtype=float,
            ),
            "pitch_body_condition_oscillation_norms": np.asarray(
                pitch_body_condition_oscillation_norm_rows,
                dtype=float,
            ),
            "pitch_body_condition_forward_speed_norms": np.asarray(
                pitch_body_condition_forward_speed_norm_rows,
                dtype=float,
            ),
            "pitch_body_condition_forward_to_oscillation_norm_ratios": np.asarray(
                pitch_body_condition_forward_to_oscillation_ratio_rows,
                dtype=float,
            ),
            "pitch_body_condition_forward_oscillation_real_alignments": np.asarray(
                pitch_body_condition_forward_oscillation_alignment_rows,
                dtype=float,
            ),
            "pitch_body_condition_forward_oscillation_phase_degs": np.asarray(
                pitch_body_condition_forward_oscillation_phase_rows,
                dtype=float,
            ),
            "heave_control_potential_norms": np.asarray(heave_control_potential_norm_rows, dtype=float),
            "pitch_control_potential_norms": np.asarray(pitch_control_potential_norm_rows, dtype=float),
            "heave_control_normal_derivative_norms": np.asarray(
                heave_control_normal_derivative_norm_rows,
                dtype=float,
            ),
            "pitch_control_normal_derivative_norms": np.asarray(
                pitch_control_normal_derivative_norm_rows,
                dtype=float,
            ),
            **{
                key: np.asarray(values, dtype=float)
                for key, values in aft_pair_rhs_norm_rows.items()
            },
            "aft_pair_inner_free_surface_rhs_row_block_names": np.asarray(
                ("eq23_body", "eq23_free_surface", "eq23_inner_control"),
                dtype=str,
            ),
            **{
                key: np.asarray(values, dtype=float)
                for key, values in aft_pair_free_rhs_block_rows.items()
            },
            "station_x_m": np.asarray(station_x_m_rows, dtype=float),
            "station_x_over_l": np.asarray(station_x_over_l_rows, dtype=float),
            "station_local_time_s": np.asarray(station_local_time_rows, dtype=float),
            "station_solve_order_indices": np.asarray(station_solve_order_index_rows, dtype=float),
            "station_solve_order_x_over_l": np.asarray(station_solve_order_x_over_l_rows, dtype=float),
            "station_solve_order_local_time_s": np.asarray(station_solve_order_local_time_rows, dtype=float),
            "pitch_base_lever_arms_m": np.asarray(pitch_base_lever_arm_rows, dtype=float),
            "pitch_radiation_lever_arms_m": np.asarray(pitch_radiation_lever_arm_rows, dtype=float),
            "pitch_moment_lever_arms_m": np.asarray(pitch_moment_lever_arm_rows, dtype=float),
            "end_term_station_indices": np.asarray(end_term_station_index_rows, dtype=float),
            "end_term_station_x_over_l": np.asarray(end_term_station_x_over_l_rows, dtype=float),
            "end_term_lever_arms_m": np.asarray(end_term_lever_arm_rows, dtype=float),
            "station_waterplane_beams": np.asarray(station_waterplane_beam_rows, dtype=float),
            "station_effective_drafts": np.asarray(station_effective_draft_rows, dtype=float),
            "station_submerged_areas": np.asarray(station_submerged_area_rows, dtype=float),
            "station_waterplane_beam_adjacent_relative_jumps": np.asarray(
                station_waterplane_beam_adjacent_jump_rows,
                dtype=float,
            ),
            "station_effective_draft_adjacent_relative_jumps": np.asarray(
                station_effective_draft_adjacent_jump_rows,
                dtype=float,
            ),
            "station_submerged_area_adjacent_relative_jumps": np.asarray(
                station_submerged_area_adjacent_jump_rows,
                dtype=float,
            ),
            "station_waterplane_beam_gradient_to_beam_gains": np.asarray(
                station_waterplane_beam_gradient_gain_rows,
                dtype=float,
            ),
            "station_effective_draft_gradient_to_draft_gains": np.asarray(
                station_effective_draft_gradient_gain_rows,
                dtype=float,
            ),
            "station_submerged_area_gradient_to_area_gains": np.asarray(
                station_submerged_area_gradient_gain_rows,
                dtype=float,
            ),
            "station_waterplane_beam_gradient_peak_x_over_l": np.asarray(
                station_waterplane_beam_gradient_peak_x_over_l_rows,
                dtype=float,
            ),
            "station_submerged_area_gradient_peak_x_over_l": np.asarray(
                station_submerged_area_gradient_peak_x_over_l_rows,
                dtype=float,
            ),
            "heave_body_potential_norm_to_beam_squared_ratios": np.asarray(
                heave_body_potential_norm_to_beam_squared_ratio_rows,
                dtype=float,
            ),
            "pitch_body_potential_norm_to_beam_squared_ratios": np.asarray(
                pitch_body_potential_norm_to_beam_squared_ratio_rows,
                dtype=float,
            ),
            "heave_body_potential_norm_to_submerged_area_ratios": np.asarray(
                heave_body_potential_norm_to_submerged_area_ratio_rows,
                dtype=float,
            ),
            "pitch_body_potential_norm_to_submerged_area_ratios": np.asarray(
                pitch_body_potential_norm_to_submerged_area_ratio_rows,
                dtype=float,
            ),
            "heave_body_potential_norm_to_beam_squared_peak_x_over_l": np.asarray(
                heave_body_potential_norm_to_beam_squared_peak_x_over_l_rows,
                dtype=float,
            ),
            "pitch_body_potential_norm_to_beam_squared_peak_x_over_l": np.asarray(
                pitch_body_potential_norm_to_beam_squared_peak_x_over_l_rows,
                dtype=float,
            ),
            "heave_body_potential_norm_to_submerged_area_peak_x_over_l": np.asarray(
                heave_body_potential_norm_to_submerged_area_peak_x_over_l_rows,
                dtype=float,
            ),
            "pitch_body_potential_norm_to_submerged_area_peak_x_over_l": np.asarray(
                pitch_body_potential_norm_to_submerged_area_peak_x_over_l_rows,
                dtype=float,
            ),
            "aft_active_station_x_over_l": np.asarray(aft_active_station_x_over_l_rows, dtype=float),
            "aft_active_station_waterplane_beams": np.asarray(
                aft_active_station_waterplane_beam_rows,
                dtype=float,
            ),
            "aft_active_station_effective_drafts": np.asarray(
                aft_active_station_effective_draft_rows,
                dtype=float,
            ),
            "aft_active_station_submerged_areas": np.asarray(
                aft_active_station_submerged_area_rows,
                dtype=float,
            ),
            "aft_active_station_body_panel_length_sums": np.asarray(
                aft_active_station_body_panel_length_sum_rows,
                dtype=float,
            ),
            "aft_active_station_body_panel_length_maxes": np.asarray(
                aft_active_station_body_panel_length_max_rows,
                dtype=float,
            ),
            "aft_active_station_body_panel_normal_z_norms": np.asarray(
                aft_active_station_body_panel_normal_z_norm_rows,
                dtype=float,
            ),
            "aft_active_station_heave_generalized_row_norms": np.asarray(
                aft_active_station_heave_generalized_row_norm_rows,
                dtype=float,
            ),
            "aft_active_station_pitch_generalized_row_norms": np.asarray(
                aft_active_station_pitch_generalized_row_norm_rows,
                dtype=float,
            ),
            "heave_body_pressure_norms": np.asarray(heave_body_pressure_norm_rows, dtype=float),
            "pitch_body_pressure_norms": np.asarray(pitch_body_pressure_norm_rows, dtype=float),
            "heave_body_pressure_time_derivative_norms": np.asarray(
                heave_body_pressure_time_derivative_norm_rows,
                dtype=float,
            ),
            "pitch_body_pressure_time_derivative_norms": np.asarray(
                pitch_body_pressure_time_derivative_norm_rows,
                dtype=float,
            ),
            "heave_body_pressure_forward_speed_norms": np.asarray(
                heave_body_pressure_forward_speed_norm_rows,
                dtype=float,
            ),
            "pitch_body_pressure_forward_speed_norms": np.asarray(
                pitch_body_pressure_forward_speed_norm_rows,
                dtype=float,
            ),
            "heave_body_pressure_to_body_potential_gains": np.asarray(
                heave_body_pressure_to_body_potential_gain_rows,
                dtype=float,
            ),
            "pitch_body_pressure_to_body_potential_gains": np.asarray(
                pitch_body_pressure_to_body_potential_gain_rows,
                dtype=float,
            ),
            "heave_body_pressure_to_free_surface_potential_after_gains": np.asarray(
                heave_body_pressure_to_free_surface_potential_after_gain_rows,
                dtype=float,
            ),
            "pitch_body_pressure_to_free_surface_potential_after_gains": np.asarray(
                pitch_body_pressure_to_free_surface_potential_after_gain_rows,
                dtype=float,
            ),
            "heave_body_pressure_forward_to_time_norm_ratios": np.asarray(
                heave_body_pressure_forward_to_time_norm_ratio_rows,
                dtype=float,
            ),
            "pitch_body_pressure_forward_to_time_norm_ratios": np.asarray(
                pitch_body_pressure_forward_to_time_norm_ratio_rows,
                dtype=float,
            ),
            "heave_pressure_time_formula_ratios": np.asarray(
                heave_pressure_time_formula_ratio_rows,
                dtype=float,
            ),
            "pitch_pressure_time_formula_ratios": np.asarray(
                pitch_pressure_time_formula_ratio_rows,
                dtype=float,
            ),
            "heave_pressure_forward_formula_ratios": np.asarray(
                heave_pressure_forward_formula_ratio_rows,
                dtype=float,
            ),
            "pitch_pressure_forward_formula_ratios": np.asarray(
                pitch_pressure_forward_formula_ratio_rows,
                dtype=float,
            ),
            "heave_body_potential_x_gradient_norms": np.asarray(
                heave_body_potential_x_gradient_norm_rows,
                dtype=float,
            ),
            "pitch_body_potential_x_gradient_norms": np.asarray(
                pitch_body_potential_x_gradient_norm_rows,
                dtype=float,
            ),
            "heave_body_potential_x_gradient_to_potential_gains": np.asarray(
                heave_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "pitch_body_potential_x_gradient_to_potential_gains": np.asarray(
                pitch_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "heave_body_potential_x_gradient_characteristic_lengths": np.asarray(
                heave_body_potential_x_gradient_characteristic_length_rows,
                dtype=float,
            ),
            "pitch_body_potential_x_gradient_characteristic_lengths": np.asarray(
                pitch_body_potential_x_gradient_characteristic_length_rows,
                dtype=float,
            ),
            "heave_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                heave_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "pitch_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                pitch_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "heave_central_body_potential_x_gradient_to_potential_gains": np.asarray(
                heave_central_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "pitch_central_body_potential_x_gradient_to_potential_gains": np.asarray(
                pitch_central_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "heave_forward_body_potential_x_gradient_to_potential_gains": np.asarray(
                heave_forward_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "pitch_forward_body_potential_x_gradient_to_potential_gains": np.asarray(
                pitch_forward_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "heave_backward_body_potential_x_gradient_to_potential_gains": np.asarray(
                heave_backward_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "pitch_backward_body_potential_x_gradient_to_potential_gains": np.asarray(
                pitch_backward_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "heave_central_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                heave_central_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "pitch_central_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                pitch_central_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "heave_forward_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                heave_forward_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "pitch_forward_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                pitch_forward_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "heave_backward_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                heave_backward_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "pitch_backward_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                pitch_backward_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "heave_phase_aligned_body_potential_x_gradient_to_potential_gains": np.asarray(
                heave_phase_aligned_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_body_potential_x_gradient_to_potential_gains": np.asarray(
                pitch_phase_aligned_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "heave_phase_aligned_body_potential_x_gradient_characteristic_lengths": np.asarray(
                heave_phase_aligned_body_potential_x_gradient_characteristic_length_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_body_potential_x_gradient_characteristic_lengths": np.asarray(
                pitch_phase_aligned_body_potential_x_gradient_characteristic_length_rows,
                dtype=float,
            ),
            "heave_phase_aligned_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                heave_phase_aligned_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                pitch_phase_aligned_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "heave_phase_aligned_gradient_gain_to_raw_gain_ratios": np.asarray(
                heave_phase_aligned_gradient_gain_to_raw_gain_ratio_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_gradient_gain_to_raw_gain_ratios": np.asarray(
                pitch_phase_aligned_gradient_gain_to_raw_gain_ratio_rows,
                dtype=float,
            ),
            "heave_phase_aligned_central_body_potential_x_gradient_to_potential_gains": np.asarray(
                heave_phase_aligned_central_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_central_body_potential_x_gradient_to_potential_gains": np.asarray(
                pitch_phase_aligned_central_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "heave_phase_aligned_forward_body_potential_x_gradient_to_potential_gains": np.asarray(
                heave_phase_aligned_forward_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_forward_body_potential_x_gradient_to_potential_gains": np.asarray(
                pitch_phase_aligned_forward_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "heave_phase_aligned_backward_body_potential_x_gradient_to_potential_gains": np.asarray(
                heave_phase_aligned_backward_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_backward_body_potential_x_gradient_to_potential_gains": np.asarray(
                pitch_phase_aligned_backward_body_potential_x_gradient_to_potential_gain_rows,
                dtype=float,
            ),
            "heave_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                heave_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                pitch_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "heave_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                heave_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                pitch_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "heave_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                heave_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length": np.asarray(
                pitch_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length_rows,
                dtype=float,
            ),
            "heave_adjacent_body_potential_relative_jumps": np.asarray(
                heave_adjacent_body_potential_relative_jump_rows,
                dtype=float,
            ),
            "pitch_adjacent_body_potential_relative_jumps": np.asarray(
                pitch_adjacent_body_potential_relative_jump_rows,
                dtype=float,
            ),
            "heave_adjacent_body_potential_symmetric_norm_ratios": np.asarray(
                heave_adjacent_body_potential_symmetric_norm_ratio_rows,
                dtype=float,
            ),
            "pitch_adjacent_body_potential_symmetric_norm_ratios": np.asarray(
                pitch_adjacent_body_potential_symmetric_norm_ratio_rows,
                dtype=float,
            ),
            "heave_adjacent_body_potential_real_alignments": np.asarray(
                heave_adjacent_body_potential_real_alignment_rows,
                dtype=float,
            ),
            "pitch_adjacent_body_potential_real_alignments": np.asarray(
                pitch_adjacent_body_potential_real_alignment_rows,
                dtype=float,
            ),
            "heave_adjacent_body_potential_phase_degs": np.asarray(
                heave_adjacent_body_potential_phase_rows,
                dtype=float,
            ),
            "pitch_adjacent_body_potential_phase_degs": np.asarray(
                pitch_adjacent_body_potential_phase_rows,
                dtype=float,
            ),
            "heave_phase_aligned_adjacent_body_potential_relative_jumps": np.asarray(
                heave_phase_aligned_adjacent_body_potential_relative_jump_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_adjacent_body_potential_relative_jumps": np.asarray(
                pitch_phase_aligned_adjacent_body_potential_relative_jump_rows,
                dtype=float,
            ),
            "heave_phase_aligned_adjacent_body_potential_real_alignments": np.asarray(
                heave_phase_aligned_adjacent_body_potential_real_alignment_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_adjacent_body_potential_real_alignments": np.asarray(
                pitch_phase_aligned_adjacent_body_potential_real_alignment_rows,
                dtype=float,
            ),
            "heave_phase_aligned_adjacent_body_potential_phase_degs": np.asarray(
                heave_phase_aligned_adjacent_body_potential_phase_rows,
                dtype=float,
            ),
            "pitch_phase_aligned_adjacent_body_potential_phase_degs": np.asarray(
                pitch_phase_aligned_adjacent_body_potential_phase_rows,
                dtype=float,
            ),
            "body_panel_mid_y_adjacent_relative_jumps": np.asarray(
                body_panel_mid_y_adjacent_relative_jump_rows,
                dtype=float,
            ),
            "body_panel_mid_z_adjacent_relative_jumps": np.asarray(
                body_panel_mid_z_adjacent_relative_jump_rows,
                dtype=float,
            ),
            "body_panel_normal_adjacent_relative_jumps": np.asarray(
                body_panel_normal_adjacent_relative_jump_rows,
                dtype=float,
            ),
            "body_panel_length_adjacent_relative_jumps": np.asarray(
                body_panel_length_adjacent_relative_jump_rows,
                dtype=float,
            ),
            "heave_mode_heave_force_to_pressure_norm_gains": np.asarray(
                heave_mode_heave_force_to_pressure_norm_gain_rows,
                dtype=float,
            ),
            "heave_mode_pitch_moment_to_pressure_norm_gains": np.asarray(
                heave_mode_pitch_moment_to_pressure_norm_gain_rows,
                dtype=float,
            ),
            "pitch_mode_heave_force_to_pressure_norm_gains": np.asarray(
                pitch_mode_heave_force_to_pressure_norm_gain_rows,
                dtype=float,
            ),
            "pitch_mode_pitch_moment_to_pressure_norm_gains": np.asarray(
                pitch_mode_pitch_moment_to_pressure_norm_gain_rows,
                dtype=float,
            ),
            "heave_pitch_total_force_density_by_station": np.asarray(
                heave_pitch_total_force_density_rows,
                dtype=complex,
            ),
            "heave_pitch_time_derivative_force_density_by_station": np.asarray(
                heave_pitch_time_force_density_rows,
                dtype=complex,
            ),
            "heave_pitch_forward_speed_force_density_by_station": np.asarray(
                heave_pitch_forward_force_density_rows,
                dtype=complex,
            ),
            "heave_pitch_total_force_density_peak_x_over_l": np.asarray(
                heave_pitch_total_force_density_peak_x_over_l_rows,
                dtype=float,
            ),
            "heave_pitch_time_derivative_force_density_peak_x_over_l": np.asarray(
                heave_pitch_time_force_density_peak_x_over_l_rows,
                dtype=float,
            ),
            "heave_pitch_forward_speed_force_density_peak_x_over_l": np.asarray(
                heave_pitch_forward_force_density_peak_x_over_l_rows,
                dtype=float,
            ),
            "heave_pitch_total_force_density_peak_abs": np.asarray(
                heave_pitch_total_force_density_peak_abs_rows,
                dtype=float,
            ),
            "heave_pitch_time_derivative_force_density_peak_abs": np.asarray(
                heave_pitch_time_force_density_peak_abs_rows,
                dtype=float,
            ),
            "heave_pitch_forward_speed_force_density_peak_abs": np.asarray(
                heave_pitch_forward_force_density_peak_abs_rows,
                dtype=float,
            ),
            "heave_pitch_total_force_density_peak_to_integral_abs_ratios": np.asarray(
                heave_pitch_total_force_density_peak_to_integral_abs_ratio_rows,
                dtype=float,
            ),
            "heave_pitch_time_derivative_force_density_peak_to_integral_abs_ratios": np.asarray(
                heave_pitch_time_force_density_peak_to_integral_abs_ratio_rows,
                dtype=float,
            ),
            "heave_pitch_forward_speed_force_density_peak_to_integral_abs_ratios": np.asarray(
                heave_pitch_forward_force_density_peak_to_integral_abs_ratio_rows,
                dtype=float,
            ),
            "heave_pitch_total_force_density_abs_centroid_x_over_l": np.asarray(
                heave_pitch_total_force_density_abs_centroid_x_over_l_rows,
                dtype=float,
            ),
            "heave_pitch_time_derivative_force_density_abs_centroid_x_over_l": np.asarray(
                heave_pitch_time_force_density_abs_centroid_x_over_l_rows,
                dtype=float,
            ),
            "heave_pitch_forward_speed_force_density_abs_centroid_x_over_l": np.asarray(
                heave_pitch_forward_force_density_abs_centroid_x_over_l_rows,
                dtype=float,
            ),
            "heave_pitch_pressure_force_matrices_excluding_aft_active_station": np.asarray(
                heave_pitch_pressure_force_matrices_excluding_aft_active_station_rows,
                dtype=complex,
            ),
            "heave_pitch_pressure_force_matrices_excluding_bow_active_station": np.asarray(
                heave_pitch_pressure_force_matrices_excluding_bow_active_station_rows,
                dtype=complex,
            ),
            "heave_pitch_pressure_force_matrices_excluding_end_active_stations": np.asarray(
                heave_pitch_pressure_force_matrices_excluding_end_active_stations_rows,
                dtype=complex,
            ),
            "heave_pitch_time_derivative_force_matrices_excluding_aft_active_station": np.asarray(
                heave_pitch_time_force_matrices_excluding_aft_active_station_rows,
                dtype=complex,
            ),
            "heave_pitch_forward_speed_force_matrices_excluding_aft_active_station": np.asarray(
                heave_pitch_forward_force_matrices_excluding_aft_active_station_rows,
                dtype=complex,
            ),
            "heave_pitch_total_force_density_aft_abs": np.asarray(
                heave_pitch_total_force_density_aft_abs_rows,
                dtype=float,
            ),
            "heave_pitch_time_derivative_force_density_aft_abs": np.asarray(
                heave_pitch_time_force_density_aft_abs_rows,
                dtype=float,
            ),
            "heave_pitch_forward_speed_force_density_aft_abs": np.asarray(
                heave_pitch_forward_force_density_aft_abs_rows,
                dtype=float,
            ),
            "heave_eq24_outer_control_relative_residuals": np.asarray(
                heave_eq24_relative_residual_rows,
                dtype=float,
            ),
            "pitch_eq24_outer_control_relative_residuals": np.asarray(
                pitch_eq24_relative_residual_rows,
                dtype=float,
            ),
        },
        validity=ValidityReport(
            status=LINEAR_2P5D_STATION_HULL_SWEEP_STATUS,
            reference_cases=("ma2005_wigley_iii",),
            notes=(
                "FrequencyDomainHydrodynamics wrapper for matched StationHull sweeps. Only heave/pitch radiation "
                "and hydrostatic restoring are populated; wave excitation remains zero pending diffraction.",
            ),
        ),
        metadata={
            "provider_route": "matched_bie_station_sweep",
            "provider_formulation": "matched_bie",
            "matrix_contract": "heave_pitch_2x2_v1",
            "matrix_row_dofs": ("heave", "pitch"),
            "matrix_col_dofs": ("heave", "pitch"),
            "matrix_source_dof_indices": (2, 4),
            "force_harmonic_convention": "F=omega^2*A-i*omega*B",
            "input_omega_role": "radiation_encounter_frequency_a1_eq4",
            "encounter_omega_definition": "same_as_input_omega_for_radiation_problem",
            "wave_encounter_transformation_applied": False,
            "heading_deg_diagnostic_only": float(heading_deg),
            "station_x_origin": "aft_perpendicular",
            "pitch_moment_origin": "longitudinal_center_of_gravity",
            "geometry_vertical_axis": "positive_down",
            "reported_heave_force_axis": "positive_up",
            "pitch_lever_expression": "LCG-x_station",
            "added_mass_units_2x2": (("kg", "kg*m"), ("kg*m", "kg*m^2")),
            "radiation_damping_units_2x2": (("kg/s", "kg*m/s"), ("kg*m/s", "kg*m^2/s")),
            "body_panels_per_section": int(cfg.body_panels_per_section),
            "free_surface_inner_panels_per_side": int(cfg.free_surface_inner_panels),
            "control_surface_panels": int(2 * cfg.free_surface_inner_panels),
            "hull_station_count": int(len(hull.stations)),
            "empirical_output_scaling_used": False,
            "sweep_statuses": tuple(sweep_statuses),
            "heave_pitch_coefficients": tuple(coefficient_rows),
            "rigid_body_mass_kg": float(body.mass_kg),
            "parametric_section_shape": parametric_section_shape,
            "a1_coordinate_convention_name": DEFAULT_A1_HEAVE_PITCH_CONVENTION.name,
            "a1_coordinate_convention_status": DEFAULT_A1_HEAVE_PITCH_CONVENTION.validity.status,
            "use_free_surface_marching": bool(use_free_surface_marching),
            "end_station": str(end_station),
            "end_term_scale": float(end_term_scale),
            "pitch_radiation_sign": float(pitch_radiation_sign),
            "pitch_radiation_lever_sign": float(pitch_radiation_lever_sign),
            "pitch_forward_speed_sign": float(pitch_forward_speed_sign),
            "pitch_oscillation_scale": float(pitch_oscillation_scale),
            "pitch_forward_speed_scale": float(pitch_forward_speed_scale),
            "pitch_moment_sign": float(pitch_moment_sign),
            "time_step_scale": float(time_step_scale),
            "free_surface_substeps_per_station": int(free_surface_substeps_per_station),
            "free_surface_velocity_scale": float(free_surface_velocity_scale),
            "free_surface_normal_derivative_source": str(free_surface_normal_derivative_source).strip().lower(),
            "free_surface_time_direction_sign": float(free_surface_time_direction_sign),
            "free_surface_dynamic_gravity_sign": float(free_surface_dynamic_gravity_sign),
            "free_surface_potential_elevation_level": str(free_surface_potential_elevation_level).strip().lower(),
            "control_row_free_surface_potential_source": str(control_row_free_surface_potential_source)
            .strip()
            .lower(),
            "history_rhs_scale": float(history_rhs_scale),
            "history_convolution_rule": str(history_convolution_rule).strip().lower(),
            "history_potential_kernel_scale": float(history_potential_kernel_scale),
            "history_normal_derivative_kernel_scale": float(history_normal_derivative_kernel_scale),
            "control_image_scale": float(control_image_scale),
            "control_potential_kernel_scale": float(control_potential_kernel_scale),
            "control_normal_derivative_kernel_scale": float(control_normal_derivative_kernel_scale),
            "control_diagonal_sign": float(control_diagonal_sign),
            "inner_a_scale": float(inner_a_scale),
            "inner_b_scale": float(inner_b_scale),
            "inner_diagonal_sign": float(inner_diagonal_sign),
            "inner_free_surface_self_diagonal_scale": float(inner_free_surface_self_diagonal_scale),
            "inner_free_surface_known_potential_rhs_scale": float(inner_free_surface_known_potential_rhs_scale),
            "inner_free_surface_known_potential_body_row_scale": float(
                inner_free_surface_known_potential_body_row_scale,
            ),
            "inner_free_surface_known_potential_free_row_scale": float(
                inner_free_surface_known_potential_free_row_scale,
            ),
            "inner_free_surface_known_potential_control_row_scale": float(
                inner_free_surface_known_potential_control_row_scale,
            ),
            "inner_free_surface_unknown_normal_column_scale": float(inner_free_surface_unknown_normal_column_scale),
            "pressure_gradient_scheme": str(pressure_gradient_scheme).strip().lower(),
            "pressure_gradient_scale": float(pressure_gradient_scale),
            "force_assembly_route": str(force_assembly_route).strip().lower(),
            "apply_local_time_phase": bool(apply_local_time_phase),
            "local_time_phase_x0_m": (
                float(hull.length_m) if local_time_phase_x0_m is None else float(local_time_phase_x0_m)
            ),
            "local_time_phase_gradient_correction": bool(local_time_phase_gradient_correction),
            "clip_inner_free_surface_to_waterline": bool(clip_inner_free_surface_to_waterline),
            "two_zone_inner_free_surface": bool(two_zone_inner_free_surface),
            "matched_station_sweep_count": int(len(matched_station_sweeps)),
            "matched_station_sweeps": tuple(matched_station_sweeps),
        },
    )


def assemble_heave_pitch_from_matched_station_solutions(
    x_m: np.ndarray,
    bodies: tuple[InnerDomainPanelGeometry, ...],
    heave_mode_solutions: tuple[MatchedSectionSolution, ...],
    pitch_mode_solutions: tuple[MatchedSectionSolution, ...],
    *,
    omega_rad_s: float,
    rho_water_kg_m3: float = 1025.0,
    forward_speed_mps: float = 0.0,
    lever_arms_m: np.ndarray | None = None,
    end_term_force_matrix: np.ndarray | None = None,
    pressure_gradient_scheme: str = "central",
    pressure_gradient_scale: float = 1.0,
    force_assembly_route: str = "eq32_stokes_body_plus_end",
    stokes_pitch_m5_sign: float = 1.0,
    heave_potential_gradient_override: StationPotentialGradient | None = None,
    pitch_potential_gradient_override: StationPotentialGradient | None = None,
) -> MatchedStationHeavePitchSweep:
    """Recover pressure/forces for a matched station sweep and assemble heave/pitch A/B coefficients."""

    x = np.asarray(x_m, dtype=float)
    if x.ndim != 1 or x.size < 2:
        raise ValueError("x_m must be one-dimensional with at least two stations.")
    if np.any(np.diff(x) <= 0.0):
        raise ValueError("x_m must be strictly increasing.")
    station_count = x.size
    if len(bodies) != station_count:
        raise ValueError("bodies must match x_m length.")
    if len(heave_mode_solutions) != station_count or len(pitch_mode_solutions) != station_count:
        raise ValueError("heave_mode_solutions and pitch_mode_solutions must match x_m length.")
    levers = np.zeros(station_count, dtype=float) if lever_arms_m is None else np.asarray(lever_arms_m, dtype=float)
    if levers.shape != (station_count,):
        raise ValueError(f"lever_arms_m must have shape ({station_count},), got {levers.shape}.")
    pressure_grad_scale = float(pressure_gradient_scale)
    gradient_scheme = str(pressure_gradient_scheme).strip().lower()
    if gradient_scheme not in {"central", "forward", "backward"}:
        raise ValueError("pressure_gradient_scheme must be 'central', 'forward', or 'backward'.")
    if not np.isfinite(pressure_grad_scale):
        raise ValueError("pressure_gradient_scale must be finite.")
    pitch_m5_sign = float(stokes_pitch_m5_sign)
    if not np.isfinite(pitch_m5_sign):
        raise ValueError("stokes_pitch_m5_sign must be finite.")
    panel_count = bodies[0].panel_count
    if panel_count < 1:
        raise ValueError("Station bodies must contain at least one panel.")
    for index, body in enumerate(bodies):
        if body.panel_count != panel_count:
            raise ValueError(
                "All station bodies must use the same panel count and indexing before x-gradient estimation; "
                f"station 0 has {panel_count}, station {index} has {body.panel_count}."
            )

    heave_phi = np.zeros((station_count, panel_count), dtype=complex)
    pitch_phi = np.zeros((station_count, panel_count), dtype=complex)
    for index, (body, heave_solution, pitch_solution) in enumerate(
        zip(bodies, heave_mode_solutions, pitch_mode_solutions, strict=True)
    ):
        if heave_solution.body_potential.shape != (body.panel_count,):
            raise ValueError(
                f"heave_mode_solutions[{index}].body_potential must have shape ({body.panel_count},), "
                f"got {heave_solution.body_potential.shape}."
            )
        if pitch_solution.body_potential.shape != (body.panel_count,):
            raise ValueError(
                f"pitch_mode_solutions[{index}].body_potential must have shape ({body.panel_count},), "
                f"got {pitch_solution.body_potential.shape}."
            )
        heave_phi[index] = heave_solution.body_potential
        pitch_phi[index] = pitch_solution.body_potential

    heave_gradient = (
        estimate_body_potential_x_gradient(x, heave_phi, scheme=gradient_scheme)
        if heave_potential_gradient_override is None
        else heave_potential_gradient_override
    )
    pitch_gradient = (
        estimate_body_potential_x_gradient(x, pitch_phi, scheme=gradient_scheme)
        if pitch_potential_gradient_override is None
        else pitch_potential_gradient_override
    )
    if heave_gradient.body_potential_x_gradient.shape != heave_phi.shape:
        raise ValueError(
            "heave_potential_gradient_override.body_potential_x_gradient must match the station/panel shape."
        )
    if pitch_gradient.body_potential_x_gradient.shape != pitch_phi.shape:
        raise ValueError(
            "pitch_potential_gradient_override.body_potential_x_gradient must match the station/panel shape."
        )
    heave_pressures = tuple(
        recover_body_pressure_from_matched_solution(
            bodies[index],
            heave_mode_solutions[index],
            omega_rad_s,
            rho_water_kg_m3=rho_water_kg_m3,
            forward_speed_mps=forward_speed_mps,
            body_potential_x_gradient=heave_gradient.body_potential_x_gradient[index],
            pressure_gradient_scale=pressure_grad_scale,
        )
        for index in range(station_count)
    )
    pitch_pressures = tuple(
        recover_body_pressure_from_matched_solution(
            bodies[index],
            pitch_mode_solutions[index],
            omega_rad_s,
            rho_water_kg_m3=rho_water_kg_m3,
            forward_speed_mps=forward_speed_mps,
            body_potential_x_gradient=pitch_gradient.body_potential_x_gradient[index],
            pressure_gradient_scale=pressure_grad_scale,
        )
        for index in range(station_count)
    )
    heave_forces = tuple(
        integrate_section_heave_pitch_force(heave_pressures[index], lever_arm_m=float(levers[index]))
        for index in range(station_count)
    )
    pitch_forces = tuple(
        integrate_section_heave_pitch_force(pitch_pressures[index], lever_arm_m=float(levers[index]))
        for index in range(station_count)
    )
    stokes_body_forward = compute_heave_pitch_stokes_body_forward_speed_force_matrix(
        x,
        bodies,
        heave_mode_solutions,
        pitch_mode_solutions,
        rho_water_kg_m3=rho_water_kg_m3,
        forward_speed_mps=forward_speed_mps,
        pitch_m5_sign=pitch_m5_sign,
    )
    row_measure_transport = compute_heave_pitch_row_measure_transport_force_matrix(
        x,
        bodies,
        heave_mode_solutions,
        pitch_mode_solutions,
        rho_water_kg_m3=rho_water_kg_m3,
        forward_speed_mps=forward_speed_mps,
        lever_arms_m=levers,
        pitch_m5_sign=pitch_m5_sign,
    )
    assembly = assemble_whole_ship_heave_pitch_coefficients(
        x,
        heave_forces,
        pitch_forces,
        omega_rad_s=omega_rad_s,
        end_term_force_matrix=end_term_force_matrix,
        stokes_body_forward_speed_force_matrix=stokes_body_forward.complex_force_matrix,
        row_measure_transport_force_matrix=row_measure_transport.complex_force_matrix,
        force_assembly_route=force_assembly_route,
    )
    return MatchedStationHeavePitchSweep(
        x_m=x,
        heave_potential_gradient=heave_gradient,
        pitch_potential_gradient=pitch_gradient,
        heave_mode_pressures=heave_pressures,
        pitch_mode_pressures=pitch_pressures,
        heave_mode_forces=heave_forces,
        pitch_mode_forces=pitch_forces,
        assembly=assembly,
        stokes_body_forward_speed=stokes_body_forward,
        row_measure_transport=row_measure_transport,
        validity=ValidityReport(
            status=LINEAR_2P5D_STATION_SWEEP_STATUS,
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            notes=(
                "Matched station sweep pressure/force pipeline. It assumes consistent station panel indexing; "
                "real benchmark station solves and the physical A1 Eq. (32) end term remain pending.",
            ),
        ),
    )


@dataclass(frozen=True)
class Matched2p5DSectionSolver:
    """Contract for the Ma-Duan-Song matched inner/outer section solver."""

    config: Linear2p5DProviderConfig = Linear2p5DProviderConfig()

    def assemble_placeholder_system(self, body_panel_count: int) -> MatchedBoundarySystem:
        if body_panel_count < 1:
            raise ValueError("body_panel_count must be positive.")
        matrix = np.eye(body_panel_count)
        rhs = np.zeros(body_panel_count)
        labels = tuple(f"phi_body_{index}" for index in range(body_panel_count))
        return MatchedBoundarySystem(
            matrix=matrix,
            rhs=rhs,
            unknown_labels=labels,
            validity=ValidityReport.unvalidated(
                "Placeholder identity system; replace with Ma-Duan-Song matched inner/outer BIE assembly."
            ),
        )

    def assemble_inner_domain_system(
        self,
        offsets: SectionOffsets,
        boundary_normal_velocity: np.ndarray,
        *,
        body_panel_count: int | None = None,
    ) -> MatchedBoundarySystem:
        """Assemble the A1 inner-domain simple-Green source-panel block."""

        self.config.validate()
        panel_count = self.config.body_panels_per_section if body_panel_count is None else int(body_panel_count)
        geometry = build_inner_domain_panel_geometry(offsets, panel_count)
        rhs = np.asarray(boundary_normal_velocity, dtype=complex)
        if rhs.shape != (geometry.panel_count,):
            raise ValueError(
                f"boundary_normal_velocity must have shape ({geometry.panel_count},), got {rhs.shape}."
            )
        matrix = inner_domain_source_normal_matrix(geometry).astype(complex)
        labels = tuple(f"sigma_body_{index}" for index in range(geometry.panel_count))
        return MatchedBoundarySystem(
            matrix=matrix,
            rhs=rhs,
            unknown_labels=labels,
            validity=ValidityReport(
                status=LINEAR_2P5D_INNER_DOMAIN_STATUS,
                reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
                notes=(
                    "A1 inner-domain simple Green function block only; outer free-surface matching is not included.",
                ),
            ),
        )

    def assemble_outer_control_surface_system(
        self,
        control_geometry: InnerDomainPanelGeometry,
        history: TransientFreeSurfaceHistory,
        past_potential: np.ndarray,
        past_normal_derivative: np.ndarray,
        *,
        history_rhs_scale: float = 1.0,
        history_convolution_rule: str = "trapezoid",
        history_potential_kernel_scale: float = 1.0,
        history_normal_derivative_kernel_scale: float = 1.0,
        control_image_scale: float = 1.0,
        control_potential_kernel_scale: float = 1.0,
        control_normal_derivative_kernel_scale: float = 1.0,
        control_diagonal_sign: float = 1.0,
    ) -> MatchedBoundarySystem:
        """Assemble the A1 Eq. (24) outer control-surface equation block."""

        self.config.validate()
        return assemble_outer_control_surface_system(
            control_geometry,
            history,
            past_potential,
            past_normal_derivative,
            history_rhs_scale=history_rhs_scale,
            history_convolution_rule=history_convolution_rule,
            history_potential_kernel_scale=history_potential_kernel_scale,
            history_normal_derivative_kernel_scale=history_normal_derivative_kernel_scale,
            control_image_scale=control_image_scale,
            control_potential_kernel_scale=control_potential_kernel_scale,
            control_normal_derivative_kernel_scale=control_normal_derivative_kernel_scale,
            control_diagonal_sign=control_diagonal_sign,
        )

    def assemble_matched_section_system(self, data: MatchedSectionBoundaryData) -> MatchedBoundarySystem:
        """Assemble the full A1 Eq. (23)-Eq. (24) square boundary system."""

        self.config.validate()
        return assemble_matched_section_system(data)

    def split_solution(self, data: MatchedSectionBoundaryData, solution: np.ndarray) -> MatchedSectionSolution:
        """Split a matched section solution into named A1 boundary arrays."""

        self.config.validate()
        return split_matched_section_solution(data, solution)

    def recover_body_pressure(
        self,
        body: InnerDomainPanelGeometry,
        solution: MatchedSectionSolution,
        omega_rad_s: float,
        *,
        rho_water_kg_m3: float = 1025.0,
        forward_speed_mps: float = 0.0,
        body_potential_x_gradient: np.ndarray | None = None,
        pressure_gradient_scale: float = 1.0,
    ) -> MatchedSectionPressureResult:
        """Recover body-panel pressure from a matched section solution."""

        self.config.validate()
        return recover_body_pressure_from_matched_solution(
            body,
            solution,
            omega_rad_s,
            rho_water_kg_m3=rho_water_kg_m3,
            forward_speed_mps=forward_speed_mps,
            body_potential_x_gradient=body_potential_x_gradient,
            pressure_gradient_scale=pressure_gradient_scale,
        )

    def estimate_body_potential_x_gradient(
        self,
        x_m: np.ndarray,
        body_potential_by_station: np.ndarray,
        *,
        scheme: str = "central",
    ) -> StationPotentialGradient:
        """Estimate station-wise body-potential x-gradient for pressure recovery."""

        self.config.validate()
        return estimate_body_potential_x_gradient(x_m, body_potential_by_station, scheme=scheme)

    def assemble_whole_ship_heave_pitch_coefficients(
        self,
        x_m: np.ndarray,
        heave_mode_forces: tuple[MatchedSectionForceResult, ...],
        pitch_mode_forces: tuple[MatchedSectionForceResult, ...],
        *,
        omega_rad_s: float,
        end_term_force_matrix: np.ndarray | None = None,
        stokes_body_forward_speed_force_matrix: np.ndarray | None = None,
        row_measure_transport_force_matrix: np.ndarray | None = None,
        force_assembly_route: str = "eq32_stokes_body_plus_end",
    ) -> WholeShipHeavePitchAssembly:
        """Assemble whole-ship heave/pitch A/B coefficients from section forces."""

        self.config.validate()
        return assemble_whole_ship_heave_pitch_coefficients(
            x_m,
            heave_mode_forces,
            pitch_mode_forces,
            omega_rad_s=omega_rad_s,
            end_term_force_matrix=end_term_force_matrix,
            stokes_body_forward_speed_force_matrix=stokes_body_forward_speed_force_matrix,
            row_measure_transport_force_matrix=row_measure_transport_force_matrix,
            force_assembly_route=force_assembly_route,
        )

    def assemble_heave_pitch_from_matched_station_solutions(
        self,
        x_m: np.ndarray,
        bodies: tuple[InnerDomainPanelGeometry, ...],
        heave_mode_solutions: tuple[MatchedSectionSolution, ...],
        pitch_mode_solutions: tuple[MatchedSectionSolution, ...],
        *,
        omega_rad_s: float,
        rho_water_kg_m3: float = 1025.0,
        forward_speed_mps: float = 0.0,
        lever_arms_m: np.ndarray | None = None,
        end_term_force_matrix: np.ndarray | None = None,
        pressure_gradient_scheme: str = "central",
        pressure_gradient_scale: float = 1.0,
        force_assembly_route: str = "eq32_stokes_body_plus_end",
        stokes_pitch_m5_sign: float = 1.0,
        heave_potential_gradient_override: StationPotentialGradient | None = None,
        pitch_potential_gradient_override: StationPotentialGradient | None = None,
    ) -> MatchedStationHeavePitchSweep:
        """Recover station pressure/forces and assemble whole-ship heave/pitch A/B coefficients."""

        self.config.validate()
        return assemble_heave_pitch_from_matched_station_solutions(
            x_m,
            bodies,
            heave_mode_solutions,
            pitch_mode_solutions,
            omega_rad_s=omega_rad_s,
            rho_water_kg_m3=rho_water_kg_m3,
            forward_speed_mps=forward_speed_mps,
            lever_arms_m=lever_arms_m,
            end_term_force_matrix=end_term_force_matrix,
            pressure_gradient_scheme=pressure_gradient_scheme,
            pressure_gradient_scale=pressure_gradient_scale,
            force_assembly_route=force_assembly_route,
            stokes_pitch_m5_sign=stokes_pitch_m5_sign,
            heave_potential_gradient_override=heave_potential_gradient_override,
            pitch_potential_gradient_override=pitch_potential_gradient_override,
        )

    def compute_heave_pitch_stokes_end_term_force_matrix(
        self,
        end_body: InnerDomainPanelGeometry,
        heave_mode_solution: MatchedSectionSolution,
        pitch_mode_solution: MatchedSectionSolution,
        *,
        rho_water_kg_m3: float = 1025.0,
        forward_speed_mps: float,
        lever_arm_m: float = 0.0,
    ) -> StokesEndTermForceMatrix:
        """Compute the A1 Eq. (32) C_A end-contour force matrix."""

        self.config.validate()
        return compute_heave_pitch_stokes_end_term_force_matrix(
            end_body,
            heave_mode_solution,
            pitch_mode_solution,
            rho_water_kg_m3=rho_water_kg_m3,
            forward_speed_mps=forward_speed_mps,
            lever_arm_m=lever_arm_m,
        )

    def compute_heave_pitch_control_surface_end_term_force_matrix(
        self,
        control_surface: InnerDomainPanelGeometry,
        heave_mode_solution: MatchedSectionSolution,
        pitch_mode_solution: MatchedSectionSolution,
        *,
        rho_water_kg_m3: float = 1025.0,
        forward_speed_mps: float,
        lever_arm_m: float = 0.0,
    ) -> StokesEndTermForceMatrix:
        """Compute the diagnostic A1 Eq. (32) fixed-control-surface C_A matrix."""

        self.config.validate()
        return compute_heave_pitch_control_surface_end_term_force_matrix(
            control_surface,
            heave_mode_solution,
            pitch_mode_solution,
            rho_water_kg_m3=rho_water_kg_m3,
            forward_speed_mps=forward_speed_mps,
            lever_arm_m=lever_arm_m,
        )

    def compute_heave_pitch_stokes_body_forward_speed_force_matrix(
        self,
        x_m: np.ndarray,
        bodies: tuple[InnerDomainPanelGeometry, ...],
        heave_mode_solutions: tuple[MatchedSectionSolution, ...],
        pitch_mode_solutions: tuple[MatchedSectionSolution, ...],
        *,
        rho_water_kg_m3: float = 1025.0,
        forward_speed_mps: float,
        pitch_m5_sign: float = 1.0,
    ) -> StokesBodyForwardSpeedForceMatrix:
        """Compute the A1 Eq. (32) body forward-speed diagnostic force matrix."""

        self.config.validate()
        return compute_heave_pitch_stokes_body_forward_speed_force_matrix(
            x_m,
            bodies,
            heave_mode_solutions,
            pitch_mode_solutions,
            rho_water_kg_m3=rho_water_kg_m3,
            forward_speed_mps=forward_speed_mps,
            pitch_m5_sign=pitch_m5_sign,
        )

    def solve_station_hull_heave_pitch_matched_sweep(
        self,
        hull: StationHull,
        omega_rad_s: float,
        speed_mps: float,
        *,
        rho_water_kg_m3: float = 1025.0,
        parametric_section_shape: str = "wigley",
        history_steps: int = 40,
        history_quadrature_count: int = 32,
        history_k_max: float = 25.0,
        include_end_term: bool | None = None,
        end_station: str = "aft",
        end_term_scale: float = 1.0,
        pitch_radiation_sign: float = 1.0,
        pitch_radiation_lever_sign: float = 1.0,
        pitch_forward_speed_sign: float = 1.0,
        pitch_oscillation_scale: float = 1.0,
        pitch_forward_speed_scale: float = 1.0,
        pitch_moment_sign: float = 1.0,
        time_step_scale: float = 1.0,
        free_surface_substeps_per_station: int = 1,
        free_surface_velocity_scale: float = 1.0,
        free_surface_normal_derivative_source: str = "raw",
        free_surface_time_direction_sign: float = 1.0,
        free_surface_dynamic_gravity_sign: float = -1.0,
        free_surface_potential_elevation_level: str = "updated",
        control_row_free_surface_potential_source: str = "shared",
        history_rhs_scale: float = 1.0,
        history_convolution_rule: str = "trapezoid",
        history_potential_kernel_scale: float = 1.0,
        history_normal_derivative_kernel_scale: float = 1.0,
        control_image_scale: float = 1.0,
        control_potential_kernel_scale: float = 1.0,
        control_normal_derivative_kernel_scale: float = 1.0,
        control_diagonal_sign: float = 1.0,
        inner_a_scale: float = 1.0,
        inner_b_scale: float = 1.0,
        inner_diagonal_sign: float = -1.0,
        inner_free_surface_self_diagonal_scale: float = 1.0,
        inner_free_surface_known_potential_rhs_scale: float = 1.0,
        inner_free_surface_known_potential_body_row_scale: float = 1.0,
        inner_free_surface_known_potential_free_row_scale: float = 1.0,
        inner_free_surface_known_potential_control_row_scale: float = 1.0,
        inner_free_surface_unknown_normal_column_scale: float = 1.0,
        pressure_gradient_scheme: str = "central",
        pressure_gradient_scale: float = 1.0,
        force_assembly_route: str = "eq32_stokes_body_plus_end",
        apply_local_time_phase: bool = True,
        local_time_phase_x0_m: float | None = None,
        local_time_phase_gradient_correction: bool = True,
        clip_inner_free_surface_to_waterline: bool = True,
        two_zone_inner_free_surface: bool = False,
        use_free_surface_marching: bool = True,
        active_min_beam_m: float = 1e-8,
        active_min_area_m2: float = 1e-12,
        heave_body_normal_velocity_base: Callable[
            [int, float, InnerDomainPanelGeometry], np.ndarray
        ]
        | None = None,
        heave_body_condition_source: str = "unit_heave_radiation",
    ) -> StationHullMatchedHeavePitchSweep:
        """Run a StationHull-level matched heave/pitch station sweep."""

        self.config.validate()
        return solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s,
            speed_mps,
            config=self.config,
            rho_water_kg_m3=rho_water_kg_m3,
            parametric_section_shape=parametric_section_shape,
            history_steps=history_steps,
            history_quadrature_count=history_quadrature_count,
            history_k_max=history_k_max,
            include_end_term=include_end_term,
            end_station=end_station,
            end_term_scale=end_term_scale,
            pitch_radiation_sign=pitch_radiation_sign,
            pitch_radiation_lever_sign=pitch_radiation_lever_sign,
            pitch_forward_speed_sign=pitch_forward_speed_sign,
            pitch_oscillation_scale=pitch_oscillation_scale,
            pitch_forward_speed_scale=pitch_forward_speed_scale,
            pitch_moment_sign=pitch_moment_sign,
            time_step_scale=time_step_scale,
            free_surface_substeps_per_station=free_surface_substeps_per_station,
            free_surface_velocity_scale=free_surface_velocity_scale,
            free_surface_normal_derivative_source=free_surface_normal_derivative_source,
            free_surface_time_direction_sign=free_surface_time_direction_sign,
            free_surface_dynamic_gravity_sign=free_surface_dynamic_gravity_sign,
            free_surface_potential_elevation_level=free_surface_potential_elevation_level,
            control_row_free_surface_potential_source=control_row_free_surface_potential_source,
            history_rhs_scale=history_rhs_scale,
            history_convolution_rule=history_convolution_rule,
            history_potential_kernel_scale=history_potential_kernel_scale,
            history_normal_derivative_kernel_scale=history_normal_derivative_kernel_scale,
            control_image_scale=control_image_scale,
            control_potential_kernel_scale=control_potential_kernel_scale,
            control_normal_derivative_kernel_scale=control_normal_derivative_kernel_scale,
            control_diagonal_sign=control_diagonal_sign,
            inner_a_scale=inner_a_scale,
            inner_b_scale=inner_b_scale,
            inner_diagonal_sign=inner_diagonal_sign,
            inner_free_surface_self_diagonal_scale=inner_free_surface_self_diagonal_scale,
            inner_free_surface_known_potential_rhs_scale=inner_free_surface_known_potential_rhs_scale,
            inner_free_surface_known_potential_body_row_scale=inner_free_surface_known_potential_body_row_scale,
            inner_free_surface_known_potential_free_row_scale=inner_free_surface_known_potential_free_row_scale,
            inner_free_surface_known_potential_control_row_scale=inner_free_surface_known_potential_control_row_scale,
            inner_free_surface_unknown_normal_column_scale=inner_free_surface_unknown_normal_column_scale,
            pressure_gradient_scheme=pressure_gradient_scheme,
            pressure_gradient_scale=pressure_gradient_scale,
            force_assembly_route=force_assembly_route,
            apply_local_time_phase=apply_local_time_phase,
            local_time_phase_x0_m=local_time_phase_x0_m,
            local_time_phase_gradient_correction=local_time_phase_gradient_correction,
            clip_inner_free_surface_to_waterline=clip_inner_free_surface_to_waterline,
            two_zone_inner_free_surface=two_zone_inner_free_surface,
            use_free_surface_marching=use_free_surface_marching,
            active_min_beam_m=active_min_beam_m,
            active_min_area_m2=active_min_area_m2,
            heave_body_normal_velocity_base=heave_body_normal_velocity_base,
            heave_body_condition_source=heave_body_condition_source,
        )

    def solve_station_hull_head_sea_excitation_matched_sweep(
        self,
        hull: StationHull,
        encounter_omega_rad_s: float,
        speed_mps: float,
        *,
        rho_water_kg_m3: float = 1025.0,
        gravity_m_s2: float = 9.80665,
        parametric_section_shape: str = "wigley",
        matched_sweep_options: dict[str, object] | None = None,
    ) -> MatchedHeadSeaExcitationSweep:
        """Solve matched-domain unit-wave head-sea excitation."""

        self.config.validate()
        return solve_station_hull_head_sea_excitation_matched_sweep(
            hull,
            encounter_omega_rad_s,
            speed_mps,
            config=self.config,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            parametric_section_shape=parametric_section_shape,
            matched_sweep_options=matched_sweep_options,
        )

    def assemble_frequency_domain_from_matched_station_hull(
        self,
        hull: StationHull,
        body: RigidBody6DOF,
        omega_rad_s: np.ndarray,
        speed_mps: float,
        *,
        rho_water_kg_m3: float = 1025.0,
        gravity_m_s2: float = 9.80665,
        heading_deg: float = 180.0,
        parametric_section_shape: str = "wigley",
        history_steps: int = 40,
        history_quadrature_count: int = 32,
        history_k_max: float = 25.0,
        include_end_term: bool | None = None,
        end_station: str = "aft",
        end_term_scale: float = 1.0,
        pitch_radiation_sign: float = 1.0,
        pitch_radiation_lever_sign: float = 1.0,
        pitch_forward_speed_sign: float = 1.0,
        pitch_oscillation_scale: float = 1.0,
        pitch_forward_speed_scale: float = 1.0,
        pitch_moment_sign: float = 1.0,
        time_step_scale: float = 1.0,
        free_surface_substeps_per_station: int = 1,
        free_surface_velocity_scale: float = 1.0,
        free_surface_normal_derivative_source: str = "raw",
        free_surface_time_direction_sign: float = 1.0,
        free_surface_dynamic_gravity_sign: float = -1.0,
        free_surface_potential_elevation_level: str = "updated",
        control_row_free_surface_potential_source: str = "shared",
        history_rhs_scale: float = 1.0,
        history_convolution_rule: str = "trapezoid",
        history_potential_kernel_scale: float = 1.0,
        history_normal_derivative_kernel_scale: float = 1.0,
        control_image_scale: float = 1.0,
        control_potential_kernel_scale: float = 1.0,
        control_normal_derivative_kernel_scale: float = 1.0,
        control_diagonal_sign: float = 1.0,
        inner_a_scale: float = 1.0,
        inner_b_scale: float = 1.0,
        inner_diagonal_sign: float = -1.0,
        inner_free_surface_self_diagonal_scale: float = 1.0,
        inner_free_surface_known_potential_rhs_scale: float = 1.0,
        inner_free_surface_known_potential_body_row_scale: float = 1.0,
        inner_free_surface_known_potential_free_row_scale: float = 1.0,
        inner_free_surface_known_potential_control_row_scale: float = 1.0,
        inner_free_surface_unknown_normal_column_scale: float = 1.0,
        pressure_gradient_scheme: str = "central",
        pressure_gradient_scale: float = 1.0,
        force_assembly_route: str = "eq32_stokes_body_plus_end",
        apply_local_time_phase: bool = True,
        local_time_phase_x0_m: float | None = None,
        local_time_phase_gradient_correction: bool = True,
        clip_inner_free_surface_to_waterline: bool = True,
        two_zone_inner_free_surface: bool = False,
        use_free_surface_marching: bool = True,
    ) -> FrequencyDomainHydrodynamics:
        """Assemble standard frequency-domain matrices from matched StationHull sweeps."""

        self.config.validate()
        return assemble_frequency_domain_from_matched_station_hull(
            hull,
            body,
            omega_rad_s,
            speed_mps,
            config=self.config,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            heading_deg=heading_deg,
            parametric_section_shape=parametric_section_shape,
            history_steps=history_steps,
            history_quadrature_count=history_quadrature_count,
            history_k_max=history_k_max,
            include_end_term=include_end_term,
            end_station=end_station,
            end_term_scale=end_term_scale,
            pitch_radiation_sign=pitch_radiation_sign,
            pitch_radiation_lever_sign=pitch_radiation_lever_sign,
            pitch_forward_speed_sign=pitch_forward_speed_sign,
            pitch_oscillation_scale=pitch_oscillation_scale,
            pitch_forward_speed_scale=pitch_forward_speed_scale,
            pitch_moment_sign=pitch_moment_sign,
            time_step_scale=time_step_scale,
            free_surface_substeps_per_station=free_surface_substeps_per_station,
            free_surface_velocity_scale=free_surface_velocity_scale,
            free_surface_normal_derivative_source=free_surface_normal_derivative_source,
            free_surface_time_direction_sign=free_surface_time_direction_sign,
            free_surface_dynamic_gravity_sign=free_surface_dynamic_gravity_sign,
            free_surface_potential_elevation_level=free_surface_potential_elevation_level,
            control_row_free_surface_potential_source=control_row_free_surface_potential_source,
            history_rhs_scale=history_rhs_scale,
            history_convolution_rule=history_convolution_rule,
            history_potential_kernel_scale=history_potential_kernel_scale,
            history_normal_derivative_kernel_scale=history_normal_derivative_kernel_scale,
            control_image_scale=control_image_scale,
            control_potential_kernel_scale=control_potential_kernel_scale,
            control_normal_derivative_kernel_scale=control_normal_derivative_kernel_scale,
            control_diagonal_sign=control_diagonal_sign,
            inner_a_scale=inner_a_scale,
            inner_b_scale=inner_b_scale,
            inner_diagonal_sign=inner_diagonal_sign,
            inner_free_surface_self_diagonal_scale=inner_free_surface_self_diagonal_scale,
            inner_free_surface_known_potential_rhs_scale=inner_free_surface_known_potential_rhs_scale,
            inner_free_surface_known_potential_body_row_scale=inner_free_surface_known_potential_body_row_scale,
            inner_free_surface_known_potential_free_row_scale=inner_free_surface_known_potential_free_row_scale,
            inner_free_surface_known_potential_control_row_scale=inner_free_surface_known_potential_control_row_scale,
            inner_free_surface_unknown_normal_column_scale=inner_free_surface_unknown_normal_column_scale,
            pressure_gradient_scheme=pressure_gradient_scheme,
            pressure_gradient_scale=pressure_gradient_scale,
            force_assembly_route=force_assembly_route,
            apply_local_time_phase=apply_local_time_phase,
            local_time_phase_x0_m=local_time_phase_x0_m,
            local_time_phase_gradient_correction=local_time_phase_gradient_correction,
            clip_inner_free_surface_to_waterline=clip_inner_free_surface_to_waterline,
            two_zone_inner_free_surface=two_zone_inner_free_surface,
            use_free_surface_marching=use_free_surface_marching,
        )

    def solve_section(self, *args, **kwargs):
        self.config.validate()
        raise NotImplementedError(
            "Matched2p5DSectionSolver.solve_section requires the inner-domain Green function, "
            "outer transient free-surface Green history, control-surface matching, and pressure recovery."
        )


def assemble_frequency_domain_from_station_hull(
    hull: StationHull,
    body: RigidBody6DOF,
    omega_rad_s: np.ndarray,
    speed_mps: float,
    *,
    heading_deg: float = 180.0,
    gravity_m_s2: float = 9.80665,
) -> FrequencyDomainHydrodynamics:
    """Route existing station assembly through the new frequency-domain contract."""

    _, encounter = deep_water_encounter(omega_rad_s, speed_mps, heading_deg, gravity_m_s2)
    provider = LinearFrequencyProvider(
        source="legacy_station_prototype",
        gravity_m_s2=gravity_m_s2,
        config=Linear2p5DProviderConfig(formulation="legacy_station_prototype"),
    )
    hydro = provider.solve_station_hull(hull, body, np.asarray(omega_rad_s, dtype=float), speed_mps=speed_mps)
    return FrequencyDomainHydrodynamics(
        omega=hydro.omega,
        encounter_omega=np.asarray(encounter, dtype=float),
        added_mass=hydro.added_mass,
        radiation_damping=hydro.radiation_damping,
        excitation=hydro.excitation,
        restoring=hydro.restoring,
        contribution_breakdown=hydro.contribution_breakdown,
        validity=ValidityReport.unvalidated(
            "Station-hull wrapper uses the old unvalidated forward-speed assembly under the new Ma-Duan-Song API.",
            reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
        ),
        metadata={**hydro.metadata, "heading_deg": heading_deg},
    )
