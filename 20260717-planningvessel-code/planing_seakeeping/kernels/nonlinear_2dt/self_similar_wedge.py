from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline, make_smoothing_spline
from scipy.optimize import brentq, least_squares

from .boundary_element import (
    ClosedBoundary2D,
    MixedBoundarySolution,
    boundary_velocity,
    constant_panel_influence_matrices,
    linear_element_influence_components,
    linear_element_influence_rows,
)


SELF_SIMILAR_WEDGE_STATUS = "iafrati_2013_self_similar_outer_flow_diagnostic_unvalidated"


def _linear_residual_square_integral(
    residual_endpoint: np.ndarray,
    panel_length: np.ndarray,
) -> float:
    """Return the exact panelwise integral of a linearly interpolated residual."""

    residual = np.asarray(residual_endpoint, dtype=float)
    length = np.asarray(panel_length, dtype=float)
    if residual.ndim != 2 or residual.shape[1] != 2:
        raise ValueError("Linear residuals require two endpoint values per panel.")
    if length.shape != (residual.shape[0],):
        raise ValueError("Panel lengths must match the linear residual panels.")
    if not np.isfinite(residual).all() or not np.isfinite(length).all():
        raise ValueError("Linear residual integration data must be finite.")
    if np.any(length <= 0.0):
        raise ValueError("Linear residual panel lengths must be positive.")
    left = residual[:, 0]
    right = residual[:, 1]
    return float(
        np.sum(length * (np.square(left) + left * right + np.square(right)) / 3.0)
    )


@dataclass(frozen=True)
class SelfSimilarWedgeConfig:
    """Configuration for an independent self-similar wedge-entry diagnostic.

    Coordinates are the Iafrati similarity coordinates ``(xi, eta)``.  The
    calm free surface is ``eta=0`` and the wedge apex is at ``(0, -1)``.
    This kernel solves the free-boundary equations without reading benchmark
    curves.  It remains diagnostic until the thin-jet matching and all three
    Zhao--Faltinsen acceptance cases pass.
    """

    deadrise_deg: float = 20.0
    far_radius: float = 20.0
    free_surface_panels: int = 36
    body_panels: int = 24
    far_field_panels: int = 24
    symmetry_panels: int = 16
    free_surface_control_points: int = 9
    jet_closure: Literal["body_root", "truncated_control"] = "body_root"
    jet_control_panels: int = 1
    gauss_order: int = 12
    max_nfev: int = 60
    optimizer_ftol: float = 1.0e-8
    optimizer_xtol: float = 1.0e-8
    optimizer_gtol: float = 1.0e-8
    root_y_initial: float | None = None
    root_z_initial: float = 0.36
    maximum_free_surface_eta: float = 1.5
    initial_dipole_coefficient: float = 4.0
    preliminary_iterations: int = 8
    preliminary_relative_tolerance: float = 1.0e-4
    pseudo_cfl: float = 0.20
    pseudo_max_iterations: int = 100
    pseudo_kinematic_tolerance: float = 1.0e-3
    coupled_kinematic_integral_tolerance: float = 1.0e-3
    free_surface_panel_growth: float = 1.05
    coupled_outer_grid_mode: Literal[
        "geometric_root",
        "double_ended",
        "frozen_monitor",
    ] = "geometric_root"
    coupled_outer_root_spacing_ratio: float = 0.08
    coupled_outer_far_spacing_ratio: float = 0.50
    coupled_outer_endpoint_decay: float = 4.0
    coupled_outer_monitor_fractions: tuple[float, ...] | None = None
    body_panel_growth: float = 1.0
    jet_angle_threshold_deg: float = 10.0
    jet_interface_min_thickness_panel_ratio: float = 0.5
    jet_interface_target_thickness_panel_ratio: float = 1.0
    coupled_root_predictor_relaxation: float = 0.1
    coupled_root_inner_relaxation: float = 0.5
    coupled_root_inner_tolerance: float = 1.0e-3
    coupled_matching_surface_bisection_iterations: int = 8
    coupled_jet_bie_panel_count: int | None = None
    shallow_jet_maximum_points: int = 20000
    coupled_jet_terminal_closure: Literal[
        "legacy_parity",
        "continuous_tip",
    ] = "legacy_parity"
    coupled_root_reconstruction_enabled: bool = False
    coupled_root_reconstruction_panels: int = 12
    coupled_root_reconstruction_added_panels: int = 24
    coupled_element_interpolation: Literal["constant_panel", "linear_node"] = (
        "constant_panel"
    )
    coupled_linear_gradient_recovery: Literal[
        "element",
        "connected_nodal",
    ] = "element"
    coupled_linear_corner_treatment: Literal[
        "shared_node",
        "displaced_double_node",
    ] = "shared_node"
    coupled_linear_far_corner_treatment: Literal[
        "shared_node",
        "displaced_double_node",
    ] = "shared_node"
    coupled_linear_cusp_velocity_recovery: Literal[
        "connected_average",
        "split_average",
        "split_outer_side",
    ] = "connected_average"
    coupled_free_surface_update: Literal[
        "full_gradient",
        "continuous_normal",
    ] = "full_gradient"
    coupled_pseudo_time_preconditioner: Literal[
        "uniform",
        "panel_length",
    ] = "uniform"
    coupled_pseudo_time_preconditioner_max_ratio: float = 16.0
    coupled_root_state_recovery: Literal[
        "first_panel_midpoint",
        "quadratic_root_extrapolation",
    ] = "first_panel_midpoint"
    coupled_smoothing_enabled: bool = False
    coupled_smoothing_root_panels: int = 12
    coupled_smoothing_turn_threshold_deg: float = 10.0
    coupled_smoothing_max_local_displacement: float = 1.0

    def __post_init__(self) -> None:
        beta = float(self.deadrise_deg)
        if not 2.0 <= beta <= 60.0:
            raise ValueError("deadrise_deg must lie in [2, 60].")
        if float(self.far_radius) <= 8.0:
            raise ValueError("far_radius must exceed eight similarity lengths.")
        for name, value, minimum in (
            ("free_surface_panels", self.free_surface_panels, 12),
            ("body_panels", self.body_panels, 8),
            ("far_field_panels", self.far_field_panels, 8),
            ("symmetry_panels", self.symmetry_panels, 4),
            ("free_surface_control_points", self.free_surface_control_points, 4),
            ("jet_control_panels", self.jet_control_panels, 1),
            ("gauss_order", self.gauss_order, 4),
            ("max_nfev", self.max_nfev, 1),
            ("preliminary_iterations", self.preliminary_iterations, 1),
            ("pseudo_max_iterations", self.pseudo_max_iterations, 1),
            (
                "coupled_root_reconstruction_panels",
                self.coupled_root_reconstruction_panels,
                4,
            ),
            (
                "coupled_matching_surface_bisection_iterations",
                self.coupled_matching_surface_bisection_iterations,
                1,
            ),
            (
                "coupled_root_reconstruction_added_panels",
                self.coupled_root_reconstruction_added_panels,
                1,
            ),
            ("coupled_smoothing_root_panels", self.coupled_smoothing_root_panels, 4),
            ("shallow_jet_maximum_points", self.shallow_jet_maximum_points, 100),
        ):
            if int(value) < minimum:
                raise ValueError(f"{name} must be at least {minimum}.")
        if self.free_surface_control_points > self.free_surface_panels + 1:
            raise ValueError("free_surface_control_points cannot exceed the free-surface node count.")
        if (
            self.coupled_jet_bie_panel_count is not None
            and int(self.coupled_jet_bie_panel_count) < 2
        ):
            raise ValueError("coupled_jet_bie_panel_count must be at least two when set.")
        if self.coupled_jet_terminal_closure not in (
            "legacy_parity",
            "continuous_tip",
        ):
            raise ValueError(
                "coupled_jet_terminal_closure must be legacy_parity or continuous_tip."
            )
        if self.jet_closure not in ("body_root", "truncated_control"):
            raise ValueError("jet_closure must be 'body_root' or 'truncated_control'.")
        if not 0.0 < float(self.root_z_initial) < float(self.maximum_free_surface_eta):
            raise ValueError("root_z_initial must be positive and below maximum_free_surface_eta.")
        if float(self.maximum_free_surface_eta) <= 0.0:
            raise ValueError("maximum_free_surface_eta must be positive.")
        for name in ("optimizer_ftol", "optimizer_xtol", "optimizer_gtol"):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be positive.")
        if float(self.initial_dipole_coefficient) <= 0.0:
            raise ValueError("initial_dipole_coefficient must be positive.")
        if float(self.preliminary_relative_tolerance) <= 0.0:
            raise ValueError("preliminary_relative_tolerance must be positive.")
        if not 0.0 < float(self.pseudo_cfl) <= 0.25:
            raise ValueError("pseudo_cfl must lie in (0, 0.25].")
        if float(self.pseudo_kinematic_tolerance) <= 0.0:
            raise ValueError("pseudo_kinematic_tolerance must be positive.")
        if float(self.coupled_kinematic_integral_tolerance) <= 0.0:
            raise ValueError(
                "coupled_kinematic_integral_tolerance must be positive."
            )
        if float(self.free_surface_panel_growth) < 1.0:
            raise ValueError("free_surface_panel_growth must be at least one.")
        if self.coupled_outer_grid_mode not in (
            "geometric_root",
            "double_ended",
            "frozen_monitor",
        ):
            raise ValueError(
                "coupled_outer_grid_mode must be geometric_root, double_ended, "
                "or frozen_monitor."
            )
        for name in (
            "coupled_outer_root_spacing_ratio",
            "coupled_outer_far_spacing_ratio",
        ):
            value = float(getattr(self, name))
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must lie in (0, 1].")
        if float(self.coupled_outer_endpoint_decay) <= 0.0:
            raise ValueError("coupled_outer_endpoint_decay must be positive.")
        monitor_fractions = self.coupled_outer_monitor_fractions
        if monitor_fractions is not None:
            monitor = np.asarray(monitor_fractions, dtype=float)
            if monitor.shape != (int(self.free_surface_panels) + 1,):
                raise ValueError(
                    "coupled_outer_monitor_fractions must contain one value per "
                    "free-surface node."
                )
            if (
                not np.isfinite(monitor).all()
                or not np.isclose(monitor[0], 0.0, atol=1.0e-14)
                or not np.isclose(monitor[-1], 1.0, atol=1.0e-14)
                or np.any(np.diff(monitor) <= 0.0)
            ):
                raise ValueError(
                    "coupled_outer_monitor_fractions must increase strictly from 0 to 1."
                )
            object.__setattr__(
                self,
                "coupled_outer_monitor_fractions",
                tuple(float(value) for value in monitor),
            )
        if (
            self.coupled_outer_grid_mode == "frozen_monitor"
            and self.coupled_outer_monitor_fractions is None
        ):
            raise ValueError(
                "frozen_monitor mode requires coupled_outer_monitor_fractions."
            )
        if float(self.body_panel_growth) < 1.0:
            raise ValueError("body_panel_growth must be at least one.")
        if not 0.0 < float(self.jet_angle_threshold_deg) < 45.0:
            raise ValueError("jet_angle_threshold_deg must lie in (0, 45).")
        minimum_ratio = float(self.jet_interface_min_thickness_panel_ratio)
        target_ratio = float(self.jet_interface_target_thickness_panel_ratio)
        if minimum_ratio <= 0.0:
            raise ValueError(
                "jet_interface_min_thickness_panel_ratio must be positive."
            )
        if target_ratio < minimum_ratio:
            raise ValueError(
                "jet_interface_target_thickness_panel_ratio must be at least the "
                "minimum ratio."
            )
        if not 0.0 < float(self.coupled_root_predictor_relaxation) <= 1.0:
            raise ValueError("coupled_root_predictor_relaxation must lie in (0, 1].")
        if not 0.0 < float(self.coupled_root_inner_relaxation) <= 1.0:
            raise ValueError("coupled_root_inner_relaxation must lie in (0, 1].")
        if float(self.coupled_root_inner_tolerance) <= 0.0:
            raise ValueError("coupled_root_inner_tolerance must be positive.")
        if self.coupled_root_reconstruction_enabled and self.coupled_smoothing_enabled:
            raise ValueError(
                "Coupled root reconstruction and smoothing are alternative diagnostics."
            )
        if self.coupled_element_interpolation not in ("constant_panel", "linear_node"):
            raise ValueError(
                "coupled_element_interpolation must be constant_panel or linear_node."
            )
        if self.coupled_linear_gradient_recovery not in (
            "element",
            "connected_nodal",
        ):
            raise ValueError(
                "coupled_linear_gradient_recovery must be element or connected_nodal."
            )
        if self.coupled_linear_corner_treatment not in (
            "shared_node",
            "displaced_double_node",
        ):
            raise ValueError(
                "coupled_linear_corner_treatment must be shared_node or "
                "displaced_double_node."
            )
        if self.coupled_linear_far_corner_treatment not in (
            "shared_node",
            "displaced_double_node",
        ):
            raise ValueError(
                "coupled_linear_far_corner_treatment must be shared_node or "
                "displaced_double_node."
            )
        if self.coupled_linear_cusp_velocity_recovery not in (
            "connected_average",
            "split_average",
            "split_outer_side",
        ):
            raise ValueError(
                "coupled_linear_cusp_velocity_recovery must be "
                "connected_average, split_average, or split_outer_side."
            )
        if (
            self.coupled_linear_cusp_velocity_recovery != "connected_average"
            and self.coupled_linear_corner_treatment != "displaced_double_node"
        ):
            raise ValueError(
                "Split cusp velocity recovery requires displaced_double_node "
                "corner treatment."
            )
        if self.coupled_free_surface_update not in (
            "full_gradient",
            "continuous_normal",
        ):
            raise ValueError(
                "coupled_free_surface_update must be full_gradient or "
                "continuous_normal."
            )
        if (
            self.coupled_free_surface_update == "continuous_normal"
            and self.coupled_element_interpolation != "linear_node"
        ):
            raise ValueError(
                "continuous_normal free-surface updates require linear_node "
                "boundary elements."
            )
        if self.coupled_pseudo_time_preconditioner not in (
            "uniform",
            "panel_length",
        ):
            raise ValueError(
                "coupled_pseudo_time_preconditioner must be uniform or panel_length."
            )
        if float(self.coupled_pseudo_time_preconditioner_max_ratio) < 1.0:
            raise ValueError(
                "coupled_pseudo_time_preconditioner_max_ratio must be at least one."
            )
        if self.coupled_root_state_recovery not in (
            "first_panel_midpoint",
            "quadratic_root_extrapolation",
        ):
            raise ValueError(
                "coupled_root_state_recovery must be first_panel_midpoint or "
                "quadratic_root_extrapolation."
            )
        if not 0.0 < float(self.coupled_smoothing_turn_threshold_deg) < 90.0:
            raise ValueError("coupled_smoothing_turn_threshold_deg must lie in (0, 90).")
        if float(self.coupled_smoothing_max_local_displacement) <= 0.0:
            raise ValueError("coupled_smoothing_max_local_displacement must be positive.")


@dataclass(frozen=True)
class SelfSimilarFreeSurface:
    node_xi: np.ndarray
    node_eta: np.ndarray
    arc_length: np.ndarray
    tau_star: float
    potential: np.ndarray

    def __post_init__(self) -> None:
        xi = np.asarray(self.node_xi, dtype=float)
        eta = np.asarray(self.node_eta, dtype=float)
        arc = np.asarray(self.arc_length, dtype=float)
        phi = np.asarray(self.potential, dtype=float)
        if xi.ndim != 1 or eta.shape != xi.shape or arc.shape != xi.shape:
            raise ValueError("Free-surface node arrays must be matching one-dimensional arrays.")
        if phi.shape != (len(xi) - 1,):
            raise ValueError("Free-surface potential requires one value per panel.")
        if not all(np.isfinite(item).all() for item in (xi, eta, arc, phi)):
            raise ValueError("Free-surface arrays must be finite.")
        if np.any(np.diff(arc) <= 0.0):
            raise ValueError("Free-surface arc length must advance strictly along the boundary.")
        if float(self.tau_star) <= 0.0:
            raise ValueError("tau_star must be positive for the far-field matching used here.")
        object.__setattr__(self, "node_xi", xi)
        object.__setattr__(self, "node_eta", eta)
        object.__setattr__(self, "arc_length", arc)
        object.__setattr__(self, "potential", phi)


@dataclass(frozen=True)
class SelfSimilarWedgeBvpResult:
    boundary: ClosedBoundary2D
    solution: MixedBoundarySolution
    free_surface: SelfSimilarFreeSurface
    dipole_coefficient: float
    flux_residual: float
    kinematic_residual: np.ndarray
    scaled_kinematic_residual: np.ndarray
    jet_control_normal_derivative: float
    body_pressure_coefficient: np.ndarray
    body_vertical_force_coefficient: float
    status: str = SELF_SIMILAR_WEDGE_STATUS

    @property
    def kinematic_rms(self) -> float:
        return float(np.sqrt(np.mean(np.square(self.scaled_kinematic_residual))))


@dataclass(frozen=True)
class SelfSimilarWedgeResult:
    config: SelfSimilarWedgeConfig
    bvp: SelfSimilarWedgeBvpResult
    control_values: np.ndarray
    optimizer_success: bool
    optimizer_message: str
    optimizer_function_evaluations: int
    initial_kinematic_rms: float
    final_kinematic_rms: float
    status: str = SELF_SIMILAR_WEDGE_STATUS


@dataclass(frozen=True)
class SelfSimilarPreliminaryResult:
    """Iafrati Eq. (51) dipole-only free-surface initialization history."""

    config: SelfSimilarWedgeConfig
    bvp: SelfSimilarWedgeBvpResult
    dipole_coefficient_history: np.ndarray
    relative_change_history: np.ndarray
    converged: bool
    status: str = "iafrati_2013_eq51_preliminary_dipole_iteration"

    def __post_init__(self) -> None:
        coefficient = np.asarray(self.dipole_coefficient_history, dtype=float)
        change = np.asarray(self.relative_change_history, dtype=float)
        if coefficient.ndim != 1 or change.shape != coefficient.shape:
            raise ValueError("Preliminary histories must be matching one-dimensional arrays.")
        if len(coefficient) == 0 or not np.isfinite(coefficient).all():
            raise ValueError("Preliminary dipole history must be finite and non-empty.")
        if not np.isfinite(change).all() or np.any(change < 0.0):
            raise ValueError("Preliminary relative changes must be finite and non-negative.")
        object.__setattr__(self, "dipole_coefficient_history", coefficient)
        object.__setattr__(self, "relative_change_history", change)


@dataclass(frozen=True)
class SelfSimilarPseudoTimeResult:
    """Source-defined pseudo-time history for Iafrati Eqs. (31)--(34)."""

    config: SelfSimilarWedgeConfig
    bvp: SelfSimilarWedgeBvpResult
    pseudo_time_history: np.ndarray
    time_step_history: np.ndarray
    kinematic_rms_history: np.ndarray
    dipole_coefficient_history: np.ndarray
    maximum_displacement_ratio_history: np.ndarray
    root_angle_deg_history: np.ndarray
    converged: bool
    termination_reason: Literal[
        "KINEMATIC_CONVERGED",
        "JET_MODEL_REQUIRED",
        "MAXIMUM_ITERATIONS",
        "NUMERICAL_FAILURE",
    ]
    failure_message: str | None = None
    status: str = "iafrati_2013_eq32_second_order_pseudo_time_diagnostic_unvalidated"

    def __post_init__(self) -> None:
        time = np.asarray(self.pseudo_time_history, dtype=float)
        step = np.asarray(self.time_step_history, dtype=float)
        rms = np.asarray(self.kinematic_rms_history, dtype=float)
        dipole = np.asarray(self.dipole_coefficient_history, dtype=float)
        displacement = np.asarray(self.maximum_displacement_ratio_history, dtype=float)
        angle = np.asarray(self.root_angle_deg_history, dtype=float)
        if any(item.ndim != 1 for item in (time, step, rms, dipole, displacement, angle)):
            raise ValueError("Pseudo-time histories must be one-dimensional arrays.")
        if not (len(time) == len(rms) == len(dipole) == len(angle) == len(step) + 1):
            raise ValueError("Pseudo-time state histories must contain one more item than steps.")
        if len(displacement) != len(step):
            raise ValueError("Pseudo-time displacement history must contain one item per step.")
        if not all(np.isfinite(item).all() for item in (time, step, rms, dipole, displacement, angle)):
            raise ValueError("Pseudo-time histories must be finite.")
        if np.any(step <= 0.0) or np.any(displacement < 0.0):
            raise ValueError("Pseudo-time steps must be positive and displacement ratios non-negative.")
        object.__setattr__(self, "pseudo_time_history", time)
        object.__setattr__(self, "time_step_history", step)
        object.__setattr__(self, "kinematic_rms_history", rms)
        object.__setattr__(self, "dipole_coefficient_history", dipole)
        object.__setattr__(self, "maximum_displacement_ratio_history", displacement)
        object.__setattr__(self, "root_angle_deg_history", angle)


@dataclass(frozen=True)
class SelfSimilarReferenceMetrics:
    deadrise_deg: float
    free_surface_point_count: int
    free_surface_nrmse: float
    pressure_point_count: int
    pressure_nrmse: float
    pressure_peak_relative_error: float
    pressure_peak_location_relative_error: float
    computed_vertical_force_coefficient: float
    reference_vertical_force_coefficient: float
    vertical_force_relative_error: float


@dataclass(frozen=True)
class SelfSimilarScalarReferenceMetrics:
    deadrise_deg: float
    computed_pressure_peak: float
    reference_pressure_peak: float
    pressure_peak_relative_error: float
    computed_peak_eta: float
    reference_peak_eta: float
    pressure_peak_location_relative_error: float


@dataclass(frozen=True)
class ShallowWaterJetResult:
    lambda_coordinate: np.ndarray
    thickness: np.ndarray
    s_lambda: np.ndarray
    s_tau: np.ndarray
    subiterations: np.ndarray
    reached_tip: bool
    status: str = "iafrati_2013_eq43_eq46_shallow_water_jet"

    def __post_init__(self) -> None:
        arrays = (
            np.asarray(self.lambda_coordinate, dtype=float),
            np.asarray(self.thickness, dtype=float),
            np.asarray(self.s_lambda, dtype=float),
            np.asarray(self.s_tau, dtype=float),
            np.asarray(self.subiterations, dtype=int),
        )
        if any(item.ndim != 1 for item in arrays) or len({len(item) for item in arrays}) != 1:
            raise ValueError("Shallow-water jet arrays must be matching one-dimensional arrays.")
        if not all(np.isfinite(item).all() for item in arrays[:-1]):
            raise ValueError("Shallow-water jet arrays must be finite.")
        object.__setattr__(self, "lambda_coordinate", arrays[0])
        object.__setattr__(self, "thickness", arrays[1])
        object.__setattr__(self, "s_lambda", arrays[2])
        object.__setattr__(self, "s_tau", arrays[3])
        object.__setattr__(self, "subiterations", arrays[4])


@dataclass(frozen=True)
class ShallowWaterJetRootState:
    thickness: float
    s_lambda: float
    s_tau: float
    delta_lambda: float
    lambda_tangent: np.ndarray

    def __post_init__(self) -> None:
        tangent = np.asarray(self.lambda_tangent, dtype=float)
        if tangent.shape != (2,) or not np.isfinite(tangent).all():
            raise ValueError("lambda_tangent must be a finite two-component vector.")
        if abs(float(np.linalg.norm(tangent)) - 1.0) > 1.0e-10:
            raise ValueError("lambda_tangent must be a unit vector.")
        object.__setattr__(self, "lambda_tangent", tangent)


@dataclass(frozen=True)
class SelfSimilarJetTruncationResult:
    """Outer BEM to shallow-water jet interface defined by Iafrati Fig. 3."""

    config: SelfSimilarWedgeConfig
    bvp: SelfSimilarWedgeBvpResult
    root_state: ShallowWaterJetRootState
    jet: ShallowWaterJetResult
    original_cut_node_index: int
    cut_angle_deg: float
    body_node_xi: np.ndarray
    body_node_eta: np.ndarray
    free_node_xi: np.ndarray
    free_node_eta: np.ndarray
    status: str = "iafrati_2013_fig3_outer_to_shallow_jet_interface_unvalidated"

    def __post_init__(self) -> None:
        arrays = tuple(
            np.asarray(item, dtype=float)
            for item in (
                self.body_node_xi,
                self.body_node_eta,
                self.free_node_xi,
                self.free_node_eta,
            )
        )
        if any(item.ndim != 1 for item in arrays) or len({len(item) for item in arrays}) != 1:
            raise ValueError("Shallow-water jet geometry arrays must be matching vectors.")
        if len(arrays[0]) != len(self.jet.lambda_coordinate):
            raise ValueError("Shallow-water jet geometry must match the marching point count.")
        if not all(np.isfinite(item).all() for item in arrays):
            raise ValueError("Shallow-water jet geometry must be finite.")
        for name, actual, expected in (
            ("thickness", self.jet.thickness[0], self.root_state.thickness),
            ("S_lambda", self.jet.s_lambda[0], self.root_state.s_lambda),
            ("S_tau", self.jet.s_tau[0], self.root_state.s_tau),
        ):
            if not np.isclose(actual, expected, rtol=1.0e-12, atol=1.0e-14):
                raise ValueError(
                    f"Shallow-water jet initial {name} must match its root state."
                )
        object.__setattr__(self, "body_node_xi", arrays[0])
        object.__setattr__(self, "body_node_eta", arrays[1])
        object.__setattr__(self, "free_node_xi", arrays[2])
        object.__setattr__(self, "free_node_eta", arrays[3])


@dataclass(frozen=True)
class SelfSimilarShallowJetCoupledResult:
    """Outer and shallow-water boundaries solved in one augmented BIE."""

    config: SelfSimilarWedgeConfig
    boundary: ClosedBoundary2D
    solution: MixedBoundarySolution
    panel_velocity: np.ndarray
    outer_free_surface: SelfSimilarFreeSurface
    jet_interface: SelfSimilarJetTruncationResult
    dipole_coefficient: float
    flux_residual: float
    outer_kinematic_residual: np.ndarray
    scaled_outer_kinematic_residual: np.ndarray
    body_pressure_coefficient: np.ndarray
    body_vertical_force_coefficient: float
    outer_kinematic_residual_endpoint: np.ndarray | None = None
    normal_derivative_endpoint: np.ndarray | None = None
    status: str = "iafrati_2013_shallow_jet_augmented_bie_diagnostic_unvalidated"

    def __post_init__(self) -> None:
        velocity = np.asarray(self.panel_velocity, dtype=float)
        if velocity.shape != (self.boundary.panel_count, 2):
            raise ValueError("Coupled panel_velocity must contain one vector per panel.")
        if not np.isfinite(velocity).all():
            raise ValueError("Coupled panel_velocity must be finite.")
        labels = np.asarray(self.boundary.panel_labels, dtype=object)
        outer_count = int(np.count_nonzero(labels == "outer_free_surface"))
        residual = np.asarray(self.outer_kinematic_residual, dtype=float)
        scaled_residual = np.asarray(
            self.scaled_outer_kinematic_residual,
            dtype=float,
        )
        if residual.shape != (outer_count,) or scaled_residual.shape != (outer_count,):
            raise ValueError("Coupled outer residuals must contain one value per panel.")
        if not np.isfinite(residual).all() or not np.isfinite(scaled_residual).all():
            raise ValueError("Coupled outer residuals must be finite.")
        endpoint_residual = self.outer_kinematic_residual_endpoint
        if endpoint_residual is not None:
            endpoint_residual = np.asarray(endpoint_residual, dtype=float)
            if endpoint_residual.shape != (outer_count, 2):
                raise ValueError(
                    "Linear outer residuals must contain two endpoint values per panel."
                )
            if not np.isfinite(endpoint_residual).all():
                raise ValueError("Linear outer endpoint residuals must be finite.")
        endpoint_q = self.normal_derivative_endpoint
        if endpoint_q is not None:
            endpoint_q = np.asarray(endpoint_q, dtype=float)
            if endpoint_q.shape != (self.boundary.panel_count, 2):
                raise ValueError(
                    "Linear normal derivatives must contain two endpoint values per panel."
                )
            if not np.isfinite(endpoint_q).all():
                raise ValueError("Linear endpoint normal derivatives must be finite.")
        object.__setattr__(self, "panel_velocity", velocity)
        object.__setattr__(self, "outer_kinematic_residual", residual)
        object.__setattr__(self, "scaled_outer_kinematic_residual", scaled_residual)
        object.__setattr__(
            self,
            "outer_kinematic_residual_endpoint",
            endpoint_residual,
        )
        object.__setattr__(self, "normal_derivative_endpoint", endpoint_q)

    @property
    def kinematic_rms(self) -> float:
        """Legacy equal-panel scaled RMS retained for diagnostic continuity."""

        return float(np.sqrt(np.mean(np.square(self.scaled_outer_kinematic_residual))))

    @property
    def kinematic_integral(self) -> float:
        """Historical midpoint quadrature for Iafrati (2013) Eq. (52)."""

        labels = np.asarray(self.boundary.panel_labels, dtype=object)
        panel_length = self.boundary.panel_length_m[labels == "outer_free_surface"]
        return float(
            np.sum(np.square(self.outer_kinematic_residual) * panel_length)
        )

    @property
    def kinematic_integral_linear_exact(self) -> float | None:
        """Integrate linear-element ``S_nu**2`` exactly on every outer panel.

        This diagnostic is deliberately separate from ``kinematic_integral`` so
        existing checkpoints and convergence histories retain their original
        midpoint-quadrature meaning.
        """

        if self.outer_kinematic_residual_endpoint is None:
            return None
        labels = np.asarray(self.boundary.panel_labels, dtype=object)
        panel_length = self.boundary.panel_length_m[labels == "outer_free_surface"]
        return _linear_residual_square_integral(
            self.outer_kinematic_residual_endpoint,
            panel_length,
        )

    @property
    def kinematic_integral_endpoint_gradient(self) -> float | None:
        """Non-negative term omitted by midpoint quadrature on linear panels."""

        exact = self.kinematic_integral_linear_exact
        if exact is None:
            return None
        return max(0.0, exact - self.kinematic_integral)

    @property
    def kinematic_convergence_integral(self) -> float:
        """Return the discretization-consistent Eq. (52) stopping metric."""

        exact = self.kinematic_integral_linear_exact
        return self.kinematic_integral if exact is None else exact

    @property
    def kinematic_length_weighted_rms(self) -> float:
        labels = np.asarray(self.boundary.panel_labels, dtype=object)
        panel_length = self.boundary.panel_length_m[labels == "outer_free_surface"]
        return float(np.sqrt(self.kinematic_integral / np.sum(panel_length)))

    @property
    def spray_root_normal_derivative_sides(self) -> np.ndarray | None:
        """Return shallow-jet and outer-surface normal derivatives at the cusp."""

        if self.normal_derivative_endpoint is None:
            return None
        labels = np.asarray(self.boundary.panel_labels, dtype=object)
        shallow = np.flatnonzero(labels == "shallow_jet_free_surface")
        outer = np.flatnonzero(labels == "outer_free_surface")
        if len(shallow) == 0 or len(outer) == 0:
            return None
        return np.asarray(
            [
                self.normal_derivative_endpoint[shallow[-1], 1],
                self.normal_derivative_endpoint[outer[0], 0],
            ],
            dtype=float,
        )

    @property
    def spray_root_corner_angle_deg(self) -> float | None:
        """Return the angle between the two free-surface tangents at the cusp."""

        labels = np.asarray(self.boundary.panel_labels, dtype=object)
        shallow = np.flatnonzero(labels == "shallow_jet_free_surface")
        outer = np.flatnonzero(labels == "outer_free_surface")
        if len(shallow) == 0 or len(outer) == 0:
            return None
        cosine = float(
            np.dot(
                self.boundary.panel_tangent[shallow[-1]],
                self.boundary.panel_tangent[outer[0]],
            )
        )
        return float(np.rad2deg(np.arccos(np.clip(cosine, -1.0, 1.0))))


@dataclass(frozen=True)
class SelfSimilarMatchingSurfaceAdjustment:
    """Accepted relocation needed to obtain a physical shallow-jet root."""

    effective_panel_shift: float
    full_panel_shifts: int
    fractional_panel_shift: float
    root_displacement_ratio: float
    bisection_iterations: int
    trigger_code: Literal[0, 1, 2]

    def __post_init__(self) -> None:
        values = (
            self.effective_panel_shift,
            self.fractional_panel_shift,
            self.root_displacement_ratio,
        )
        if not np.isfinite(values).all() or any(value < 0.0 for value in values):
            raise ValueError("Matching-surface adjustment values must be finite and non-negative.")
        if int(self.full_panel_shifts) < 0 or int(self.bisection_iterations) < 0:
            raise ValueError("Matching-surface adjustment counts must be non-negative.")
        if not 0.0 <= float(self.fractional_panel_shift) <= 1.0:
            raise ValueError("The fractional matching-surface shift must lie in [0, 1].")
        if int(self.trigger_code) not in (0, 1, 2):
            raise ValueError("Unknown matching-surface adjustment trigger code.")


@dataclass(frozen=True)
class SelfSimilarGeometryMaintenanceAdjustment:
    """Normal/tangential velocity injected by regridding and root relocation."""

    raw_normal_velocity_integral: float
    normal_velocity_integral: float
    tangential_velocity_integral: float
    net_normal_velocity_integral: float
    maximum_normal_displacement_ratio: float
    normal_velocity_correlation: float
    normal_cancellation_fraction: float

    def __post_init__(self) -> None:
        non_negative = (
            self.raw_normal_velocity_integral,
            self.normal_velocity_integral,
            self.tangential_velocity_integral,
            self.net_normal_velocity_integral,
            self.maximum_normal_displacement_ratio,
        )
        if not np.isfinite(non_negative).all() or any(
            value < 0.0 for value in non_negative
        ):
            raise ValueError(
                "Geometry-maintenance integral and displacement metrics must be "
                "finite and non-negative."
            )
        if not np.isfinite(
            (self.normal_velocity_correlation, self.normal_cancellation_fraction)
        ).all():
            raise ValueError(
                "Geometry-maintenance correlation metrics must be finite."
            )
        if abs(float(self.normal_velocity_correlation)) > 1.0 + 1.0e-12:
            raise ValueError(
                "The geometry-maintenance normal-velocity correlation must lie in "
                "[-1, 1]."
            )


@dataclass(frozen=True)
class SelfSimilarCoupledRK2Diagnostics:
    """Matching-surface diagnostics for one accepted coupled RK2 step."""

    provisional: SelfSimilarMatchingSurfaceAdjustment
    final: SelfSimilarMatchingSurfaceAdjustment
    provisional_geometry_maintenance: SelfSimilarGeometryMaintenanceAdjustment
    final_geometry_maintenance: SelfSimilarGeometryMaintenanceAdjustment
    rejected_attempt_count: int

    def __post_init__(self) -> None:
        if int(self.rejected_attempt_count) < 0:
            raise ValueError("The rejected RK2 attempt count must be non-negative.")


@dataclass(frozen=True)
class SelfSimilarCoupledPseudoTimeResult:
    """Repeated augmented outer/jet BIE pseudo-time diagnostic."""

    config: SelfSimilarWedgeConfig
    coupled: SelfSimilarShallowJetCoupledResult
    pseudo_time_history: np.ndarray
    time_step_history: np.ndarray
    kinematic_rms_history: np.ndarray
    kinematic_integral_history: np.ndarray
    kinematic_convergence_integral_history: np.ndarray
    dipole_coefficient_history: np.ndarray
    root_thickness_history: np.ndarray
    root_s_lambda_history: np.ndarray
    root_measured_s_lambda_history: np.ndarray
    root_relative_mismatch_history: np.ndarray
    root_body_eta_history: np.ndarray
    root_resolution_ratio_history: np.ndarray
    bem_condition_number_history: np.ndarray
    maximum_displacement_ratio_history: np.ndarray
    converged: bool
    termination_reason: Literal[
        "KINEMATIC_CONVERGED", "MAXIMUM_ITERATIONS", "NUMERICAL_FAILURE"
    ]
    failure_message: str | None = None
    provisional_matching_surface_shift_history: np.ndarray | None = None
    final_matching_surface_shift_history: np.ndarray | None = None
    provisional_matching_surface_root_displacement_history: np.ndarray | None = None
    final_matching_surface_root_displacement_history: np.ndarray | None = None
    provisional_matching_surface_trigger_history: np.ndarray | None = None
    final_matching_surface_trigger_history: np.ndarray | None = None
    rk2_rejected_attempt_count_history: np.ndarray | None = None
    jet_point_count_history: np.ndarray | None = None
    shallow_jet_panel_count_per_side_history: np.ndarray | None = None
    boundary_panel_count_history: np.ndarray | None = None
    jet_tip_thickness_history: np.ndarray | None = None
    jet_tip_s_lambda_history: np.ndarray | None = None
    status: str = "iafrati_2013_repeated_shallow_jet_augmented_bie_unvalidated"

    def __post_init__(self) -> None:
        state_arrays = tuple(
            np.asarray(item, dtype=float)
            for item in (
                self.pseudo_time_history,
                self.kinematic_rms_history,
                self.kinematic_integral_history,
                self.kinematic_convergence_integral_history,
                self.dipole_coefficient_history,
                self.root_thickness_history,
                self.root_s_lambda_history,
                self.root_measured_s_lambda_history,
                self.root_relative_mismatch_history,
                self.root_body_eta_history,
                self.root_resolution_ratio_history,
                self.bem_condition_number_history,
            )
        )
        step = np.asarray(self.time_step_history, dtype=float)
        displacement = np.asarray(self.maximum_displacement_ratio_history, dtype=float)
        if len({len(item) for item in state_arrays}) != 1:
            raise ValueError("Coupled pseudo-time state histories must have matching lengths.")
        if len(step) + 1 != len(state_arrays[0]) or len(displacement) != len(step):
            raise ValueError("Coupled pseudo-time step histories have inconsistent lengths.")
        if not all(np.isfinite(item).all() for item in state_arrays):
            raise ValueError("Coupled pseudo-time state histories must be finite.")
        if (
            np.any(state_arrays[2] < 0.0)
            or np.any(state_arrays[3] < 0.0)
            or np.any(state_arrays[10] <= 0.0)
            or np.any(state_arrays[11] <= 0.0)
        ):
            raise ValueError("Coupled interface ratios and BEM condition numbers must be positive.")
        for name, value in (
            ("pseudo_time_history", state_arrays[0]),
            ("kinematic_rms_history", state_arrays[1]),
            ("kinematic_integral_history", state_arrays[2]),
            ("kinematic_convergence_integral_history", state_arrays[3]),
            ("dipole_coefficient_history", state_arrays[4]),
            ("root_thickness_history", state_arrays[5]),
            ("root_s_lambda_history", state_arrays[6]),
            ("root_measured_s_lambda_history", state_arrays[7]),
            ("root_relative_mismatch_history", state_arrays[8]),
            ("root_body_eta_history", state_arrays[9]),
            ("root_resolution_ratio_history", state_arrays[10]),
            ("bem_condition_number_history", state_arrays[11]),
            ("time_step_history", step),
            ("maximum_displacement_ratio_history", displacement),
        ):
            object.__setattr__(self, name, value)
        optional_step_histories = (
            "provisional_matching_surface_shift_history",
            "final_matching_surface_shift_history",
            "provisional_matching_surface_root_displacement_history",
            "final_matching_surface_root_displacement_history",
            "provisional_matching_surface_trigger_history",
            "final_matching_surface_trigger_history",
            "rk2_rejected_attempt_count_history",
        )
        for name in optional_step_histories:
            supplied = getattr(self, name)
            if supplied is None:
                continue
            values = np.asarray(supplied, dtype=float)
            if len(values) != len(step):
                raise ValueError(
                    f"Optional coupled pseudo-time step history {name} has "
                    "an inconsistent length."
                )
            if not np.isfinite(values).all() or np.any(values < 0.0):
                raise ValueError(
                    f"Optional coupled pseudo-time step history {name} must be "
                    "finite and non-negative."
                )
            object.__setattr__(self, name, values)
        optional_state_histories = (
            "jet_point_count_history",
            "shallow_jet_panel_count_per_side_history",
            "boundary_panel_count_history",
            "jet_tip_thickness_history",
            "jet_tip_s_lambda_history",
        )
        for name in optional_state_histories:
            supplied = getattr(self, name)
            if supplied is None:
                continue
            values = np.asarray(supplied, dtype=float)
            if len(values) != len(state_arrays[0]):
                raise ValueError(
                    f"Optional coupled pseudo-time state history {name} has "
                    "an inconsistent length."
                )
            if not np.isfinite(values).all() or np.any(values < 0.0):
                raise ValueError(
                    f"Optional coupled pseudo-time state history {name} must be "
                    "finite and non-negative."
                )
            object.__setattr__(self, name, values)


@dataclass(frozen=True)
class SelfSimilarJetRootIterationResult:
    """Fixed-outer-surface consistency history for the shallow-jet root."""

    coupled: SelfSimilarShallowJetCoupledResult
    s_lambda_history: np.ndarray
    measured_s_lambda_history: np.ndarray
    relative_mismatch_history: np.ndarray
    relative_change_history: np.ndarray
    converged: bool
    termination_reason: Literal[
        "ROOT_CONSISTENT",
        "MAXIMUM_ITERATIONS",
        "NO_BRACKET_IN_PHYSICAL_DOMAIN",
    ]
    status: str = "iafrati_2013_shallow_jet_root_inner_iteration_unvalidated"

    def __post_init__(self) -> None:
        supplied = np.asarray(self.s_lambda_history, dtype=float)
        measured = np.asarray(self.measured_s_lambda_history, dtype=float)
        mismatch = np.asarray(self.relative_mismatch_history, dtype=float)
        change = np.asarray(self.relative_change_history, dtype=float)
        if not (supplied.shape == measured.shape == mismatch.shape == change.shape):
            raise ValueError("Root-coupling histories must have matching shapes.")
        if supplied.ndim != 1 or len(supplied) < 1:
            raise ValueError("Root-coupling histories must be non-empty vectors.")
        if not all(np.isfinite(item).all() for item in (supplied, measured, mismatch, change)):
            raise ValueError("Root-coupling histories must be finite.")
        if np.any(supplied <= 0.0) or np.any(measured <= 0.0) or np.any(mismatch < 0.0):
            raise ValueError(
                "Root-coupling velocities must be positive and mismatches non-negative."
            )
        object.__setattr__(self, "s_lambda_history", supplied)
        object.__setattr__(self, "measured_s_lambda_history", measured)
        object.__setattr__(self, "relative_mismatch_history", mismatch)
        object.__setattr__(self, "relative_change_history", change)


def derive_shallow_water_jet_root_state(
    bvp: SelfSimilarWedgeBvpResult,
    *,
    deadrise_deg: float,
) -> ShallowWaterJetRootState:
    """Map a truncated-control outer solution to Iafrati's local root data.

    ``lambda`` points from the bulk-flow root toward the spray tip.  On this
    right-hand half-domain that is the outward body tangent; this orientation
    also prevents the reconstructed jet body from overlapping the main body.
    ``S_lambda`` is read directly from the last body panel.  This follows
    Iafrati's statement that all quantities at the first marching point are
    supplied by the boundary-integral solution; Eq. (42) is then applied at
    the next spatial point.  A non-positive value is returned unchanged so
    the caller can reject an outer solution with the wrong flow direction.
    """

    labels = np.asarray(bvp.boundary.panel_labels, dtype=object)
    control_index = np.flatnonzero(labels == "jet_control")
    body_index = np.flatnonzero(labels == "body")
    free_index = np.flatnonzero(labels == "free_surface")
    if len(control_index) == 0:
        raise ValueError("Shallow-water root data require a truncated_control boundary.")
    if len(body_index) < 2 or len(free_index) < 2:
        raise ValueError("Shallow-water root data require resolved body and free-surface panels.")

    beta = np.deg2rad(float(deadrise_deg))
    tangent = np.asarray([np.cos(beta), np.sin(beta)])
    root = np.asarray(
        [bvp.free_surface.node_xi[0], bvp.free_surface.node_eta[0]], dtype=float
    )
    last_body_panel = int(body_index[-1])
    body_end = np.asarray(
        [
            bvp.boundary.node_y_m[last_body_panel + 1],
            bvp.boundary.node_z_up_m[last_body_panel + 1],
        ]
    )
    thickness = float(np.linalg.norm(root - body_end))
    s_tau = -float(bvp.free_surface.tau_star)
    velocity = boundary_velocity(
        bvp.boundary,
        bvp.solution,
        respect_label_boundaries=True,
    )
    body_midpoint = np.asarray(
        [
            bvp.boundary.panel_mid_y_m[last_body_panel],
            bvp.boundary.panel_mid_z_up_m[last_body_panel],
        ]
    )
    bvp_s_lambda = float(
        np.dot(velocity[last_body_panel] - body_midpoint, tangent)
    )
    s_lambda = bvp_s_lambda
    delta_lambda = 0.5 * float(
        bvp.boundary.panel_length_m[int(free_index[0])]
    )
    return ShallowWaterJetRootState(
        thickness=thickness,
        s_lambda=s_lambda,
        s_tau=s_tau,
        delta_lambda=delta_lambda,
        lambda_tangent=tangent,
    )


def march_shallow_water_jet_from_outer_solution(
    bvp: SelfSimilarWedgeBvpResult,
    *,
    deadrise_deg: float,
    relaxation: float = 0.9,
) -> ShallowWaterJetResult:
    """Couple an eligible outer solution to the source-defined jet marcher."""

    root = derive_shallow_water_jet_root_state(
        bvp,
        deadrise_deg=deadrise_deg,
    )
    if root.s_lambda <= 0.0:
        raise ValueError(
            "The outer solution has S_lambda<=0 at the jet root; its local "
            "flow points away from the source-defined root-to-tip marching direction."
        )
    return march_iafrati_shallow_water_jet(
        initial_thickness=root.thickness,
        initial_s_lambda=root.s_lambda,
        initial_s_tau=root.s_tau,
        delta_lambda=root.delta_lambda,
        relaxation=relaxation,
    )


def march_iafrati_shallow_water_jet(
    *,
    initial_thickness: float,
    initial_s_lambda: float,
    initial_s_tau: float,
    delta_lambda: float,
    relaxation: float = 0.9,
    subiteration_tolerance: float = 1.0e-10,
    maximum_subiterations: int = 1000,
    maximum_points: int = 5000,
) -> ShallowWaterJetResult:
    """March Iafrati (2013), Eqs. (43)--(46), from jet root to tip.

    The initial quantities must come from the bulk boundary-integral solution.
    This routine contains no wedge benchmark values and does not invent a
    root thickness; coupling that initial state remains an explicit caller
    responsibility.
    """

    f0 = float(initial_thickness)
    sl0 = float(initial_s_lambda)
    st0 = float(initial_s_tau)
    step = float(delta_lambda)
    omega = float(relaxation)
    tolerance = float(subiteration_tolerance)
    if f0 <= 0.0 or sl0 <= 0.0 or st0 >= 0.0 or step <= 0.0:
        invalid = ", ".join(
            name
            for name, failed in (
                ("thickness<=0", f0 <= 0.0),
                ("S_lambda<=0", sl0 <= 0.0),
                ("S_tau>=0", st0 >= 0.0),
                ("delta_lambda<=0", step <= 0.0),
            )
            if failed
        )
        raise ValueError(
            "The jet root requires thickness>0, S_lambda>0, S_tau<0 and "
            "delta_lambda>0; "
            f"invalid={invalid}; thickness={f0:.17g}, "
            f"S_lambda={sl0:.17g}, S_tau={st0:.17g}, "
            f"delta_lambda={step:.17g}."
        )
    if not 0.0 < omega < 1.0:
        raise ValueError("relaxation must lie strictly between zero and one.")
    if tolerance <= 0.0 or int(maximum_subiterations) < 2 or int(maximum_points) < 2:
        raise ValueError("Jet marching tolerances and iteration limits must be positive.")

    coordinate = [0.0]
    thickness = [f0]
    s_lambda = [sl0]
    s_tau = [st0]
    subiterations = [0]
    reached_tip = abs(sl0) < step

    while not reached_tip and len(coordinate) < int(maximum_points):
        previous_f = thickness[-1]
        previous_sl = s_lambda[-1]
        previous_st = s_tau[-1]
        candidate_f = previous_f
        candidate_sl = previous_sl
        candidate_st = previous_st
        converged = False

        def state_from_thickness(value: float) -> tuple[float, float]:
            slope = (value - previous_f) / step
            value_st = previous_st + np.hypot(step, value - previous_f)
            value_sl = -value_st / np.sqrt(1.0 + slope**2)
            return float(value_sl), float(value_st)

        def thickness_equation(value: float) -> float:
            value_sl, _ = state_from_thickness(value)
            denominator = step + value_sl
            if abs(denominator) <= 64.0 * np.finfo(float).eps:
                return np.nan
            return float(value + previous_f * (step - previous_sl) / denominator)

        for iteration in range(1, int(maximum_subiterations) + 1):
            denominator = step + candidate_sl
            if abs(denominator) <= np.finfo(float).eps:
                break
            new_f = (
                omega * candidate_f
                - (1.0 - omega)
                * previous_f
                * (step - previous_sl)
                / denominator
            )
            thickness_slope = (new_f - previous_f) / step
            new_st = previous_st + np.hypot(step, new_f - previous_f)
            new_sl = -new_st / np.sqrt(1.0 + thickness_slope**2)
            if not np.isfinite([new_f, new_sl, new_st]).all():
                break
            if max(abs(new_f - candidate_f), abs(new_sl - candidate_sl)) <= tolerance:
                candidate_f, candidate_sl, candidate_st = new_f, new_sl, new_st
                converged = True
                break
            candidate_f, candidate_sl, candidate_st = new_f, new_sl, new_st

        # The attached shallow jet must thin from the matching surface toward
        # its tip. A converged fixed point on an increasing-thickness branch is
        # a root of the algebraic step, but not the physical continuation.
        if not converged or candidate_f > previous_f + tolerance:
            upper = previous_f
            samples = np.linspace(0.0, upper, 129)
            values = np.asarray([thickness_equation(value) for value in samples])
            roots: list[tuple[float, int]] = []
            for bracket_index in range(len(samples) - 1):
                left_value = values[bracket_index]
                right_value = values[bracket_index + 1]
                if not np.isfinite([left_value, right_value]).all():
                    continue
                if left_value == 0.0:
                    roots.append((float(samples[bracket_index]), 1))
                elif left_value * right_value < 0.0:
                    root, root_result = brentq(
                        thickness_equation,
                        float(samples[bracket_index]),
                        float(samples[bracket_index + 1]),
                        xtol=tolerance,
                        rtol=max(4.0 * np.finfo(float).eps, tolerance),
                        maxiter=int(maximum_subiterations),
                        full_output=True,
                    )
                    roots.append((float(root), int(root_result.iterations)))
            roots = [
                item
                for item in roots
                if -tolerance <= item[0] <= previous_f + tolerance
            ]
            if not roots:
                if len(coordinate) == 1:
                    raise ValueError(
                        "The shallow-water root state has no physical first-step "
                        f"solution: f={previous_f:.12g}, "
                        f"S_lambda={previous_sl:.12g}, S_tau={previous_st:.12g}, "
                        f"delta_lambda={step:.12g}."
                    )
                raise ValueError(
                    "Iafrati Eq. (43)--(46) fixed point and bracketed root solve "
                    f"failed at point {len(coordinate)}: f={previous_f:.12g}, "
                    f"S_lambda={previous_sl:.12g}, S_tau={previous_st:.12g}, "
                    f"delta_lambda={step:.12g}."
                )
            candidate_f, iteration = min(
                roots,
                key=lambda item: abs(
                    item[0] - min(max(candidate_f, 0.0), previous_f)
                ),
            )
            candidate_sl, candidate_st = state_from_thickness(candidate_f)
        if candidate_f < -tolerance:
            raise ValueError("Iafrati shallow-water marching produced negative jet thickness.")
        coordinate.append(coordinate[-1] + step)
        thickness.append(max(candidate_f, 0.0))
        s_lambda.append(candidate_sl)
        s_tau.append(candidate_st)
        subiterations.append(iteration)
        reached_tip = abs(candidate_sl) < step or candidate_f <= tolerance

    if not reached_tip:
        raise ValueError(
            "Iafrati shallow-water marching reached maximum_points before the "
            f"jet tip: points={len(coordinate)}, thickness={thickness[-1]:.12g}, "
            f"S_lambda={s_lambda[-1]:.12g}, delta_lambda={step:.12g}."
        )

    return ShallowWaterJetResult(
        lambda_coordinate=np.asarray(coordinate),
        thickness=np.asarray(thickness),
        s_lambda=np.asarray(s_lambda),
        s_tau=np.asarray(s_tau),
        subiterations=np.asarray(subiterations),
        reached_tip=bool(reached_tip),
    )


def _wagner_half_width(deadrise_rad: float) -> float:
    return float(np.pi / (2.0 * np.tan(deadrise_rad)))


def _initial_control_vector(config: SelfSimilarWedgeConfig) -> np.ndarray:
    beta = np.deg2rad(config.deadrise_deg)
    root_y = (
        float(config.root_y_initial)
        if config.root_y_initial is not None
        else 0.95 * _wagner_half_width(beta)
    )
    u = np.linspace(0.0, 1.0, config.free_surface_control_points)
    if config.jet_closure == "body_root":
        root_eta = -1.0 + root_y * np.tan(beta)
        eta = root_eta * np.square(1.0 - u)
        return np.concatenate(([root_y], eta[1:-1]))
    eta = float(config.root_z_initial) * np.square(1.0 - u)
    return np.concatenate(([root_y], eta[:-1]))


def _control_bounds(config: SelfSimilarWedgeConfig) -> tuple[np.ndarray, np.ndarray]:
    beta = np.deg2rad(config.deadrise_deg)
    wagner = _wagner_half_width(beta)
    # A truncated spray jet must meet the wedge at or above the undisturbed
    # free surface.  ``cot(beta)`` is the horizontal body coordinate where
    # the translated wedge first crosses eta=0; this is a geometry condition,
    # not a benchmark-derived bound.
    minimum_root_y = max(0.55 * wagner, 1.001 / np.tan(beta))
    free_parameter_count = (
        config.free_surface_control_points - 2
        if config.jet_closure == "body_root"
        else config.free_surface_control_points - 1
    )
    lower = np.concatenate(([minimum_root_y], np.zeros(free_parameter_count)))
    upper = np.concatenate(
        (
            [min(1.5 * wagner, 0.75 * config.far_radius)],
            np.full(free_parameter_count, config.maximum_free_surface_eta),
        )
    )
    return lower, upper


def build_self_similar_free_surface(
    config: SelfSimilarWedgeConfig,
    control_values: np.ndarray,
) -> SelfSimilarFreeSurface:
    """Build the lower free-surface branch and Iafrati Eq. (34) potential."""

    controls = np.asarray(control_values, dtype=float)
    expected = (
        config.free_surface_control_points - 1
        if config.jet_closure == "body_root"
        else config.free_surface_control_points
    )
    if controls.shape != (expected,) or not np.isfinite(controls).all():
        raise ValueError(f"control_values must be finite with shape ({expected},).")
    root_y = float(controls[0])
    if config.jet_closure == "body_root":
        beta = np.deg2rad(config.deadrise_deg)
        root_eta = -1.0 + root_y * np.tan(beta)
        control_eta = np.concatenate(([root_eta], controls[1:], [0.0]))
    else:
        control_eta = np.concatenate((controls[1:], [0.0]))
    control_u = np.linspace(0.0, 1.0, config.free_surface_control_points)
    node_u = _outer_panel_fractions(config)
    spline = CubicSpline(control_u, control_eta, bc_type=((1, 0.0), (1, 0.0)))
    node_xi = root_y + (float(config.far_radius) - root_y) * node_u
    node_eta = spline(node_u)
    node_eta[-1] = 0.0
    return build_self_similar_free_surface_from_nodes(
        config,
        node_xi,
        node_eta,
        far_dipole_coefficient=0.0,
    )


def build_self_similar_free_surface_from_nodes(
    config: SelfSimilarWedgeConfig,
    node_xi: np.ndarray,
    node_eta: np.ndarray,
    *,
    far_dipole_coefficient: float,
) -> SelfSimilarFreeSurface:
    """Apply Iafrati Eqs. (22), (33) and far-field matching to nodes."""

    xi = np.asarray(node_xi, dtype=float)
    eta = np.asarray(node_eta, dtype=float)
    if xi.ndim != 1 or eta.shape != xi.shape or len(xi) < 5:
        raise ValueError("Free-surface nodes must be matching vectors with at least five nodes.")
    if not np.isfinite(xi).all() or not np.isfinite(eta).all():
        raise ValueError("Free-surface nodes must be finite.")
    segment = np.hypot(np.diff(xi), np.diff(eta))
    if np.any(segment <= 1.0e-12):
        raise ValueError("Free-surface nodes contain a zero-length panel.")
    arc_length = np.concatenate(([0.0], np.cumsum(segment)))
    far_rho_squared = float(xi[-1] ** 2 + eta[-1] ** 2)
    radius_error = abs(np.sqrt(far_rho_squared) - float(config.far_radius))
    if radius_error > 1.0e-8 * float(config.far_radius):
        raise ValueError("The outer free-surface node must lie on the far-field circle.")
    far_phi = float(far_dipole_coefficient) * float(eta[-1]) / far_rho_squared
    far_s = far_phi - 0.5 * far_rho_squared
    if far_s >= 0.0:
        raise ValueError("Far-field matching requires a negative modified potential S.")
    tau_far = np.sqrt(-2.0 * far_s)
    tau_star = float(tau_far - arc_length[-1])

    midpoint_xi = 0.5 * (xi[:-1] + xi[1:])
    midpoint_eta = 0.5 * (eta[:-1] + eta[1:])
    midpoint_s = 0.5 * (arc_length[:-1] + arc_length[1:])
    tau = tau_star + midpoint_s
    potential = 0.5 * (midpoint_xi**2 + midpoint_eta**2 - tau**2)
    return SelfSimilarFreeSurface(
        node_xi=xi,
        node_eta=eta,
        arc_length=arc_length,
        tau_star=tau_star,
        potential=potential,
    )


def _geometric_panel_fractions(panel_count: int, growth: float) -> np.ndarray:
    """Return normalized panel-end arclengths refined at the body end."""

    count = int(panel_count)
    ratio = float(growth)
    if count < 1 or ratio < 1.0:
        raise ValueError("panel_count must be positive and growth must be at least one.")
    panel_length = np.power(ratio, np.arange(count, dtype=float))
    return np.concatenate(([0.0], np.cumsum(panel_length) / np.sum(panel_length)))


def _double_ended_panel_fractions(
    panel_count: int,
    root_spacing_ratio: float,
    far_spacing_ratio: float,
    endpoint_decay: float,
) -> np.ndarray:
    """Return smooth panel fractions independently refined at both endpoints.

    The two spacing ratios prescribe the unnormalised endpoint panel lengths
    relative to the interior scale.  Their logarithms are blended with smooth
    endpoint weights, avoiding a piecewise spacing jump in the middle of the
    free surface.  The construction depends only on declared numerical
    resolution parameters and never reads a benchmark curve.
    """

    count = int(panel_count)
    root_ratio = float(root_spacing_ratio)
    far_ratio = float(far_spacing_ratio)
    decay = float(endpoint_decay)
    if count < 1:
        raise ValueError("panel_count must be positive.")
    if not 0.0 < root_ratio <= 1.0 or not 0.0 < far_ratio <= 1.0:
        raise ValueError("Endpoint spacing ratios must lie in (0, 1].")
    if decay <= 0.0:
        raise ValueError("endpoint_decay must be positive.")
    coordinate = np.linspace(0.0, 1.0, count)
    log_length = (
        np.log(root_ratio) * np.power(1.0 - coordinate, decay)
        + np.log(far_ratio) * np.power(coordinate, decay)
    )
    panel_length = np.exp(log_length)
    return np.concatenate(([0.0], np.cumsum(panel_length) / np.sum(panel_length)))


def _outer_panel_fractions(config: SelfSimilarWedgeConfig) -> np.ndarray:
    if config.coupled_outer_grid_mode == "frozen_monitor":
        if config.coupled_outer_monitor_fractions is None:
            raise ValueError("Frozen monitor fractions are missing from the configuration.")
        return np.asarray(config.coupled_outer_monitor_fractions, dtype=float).copy()
    if config.coupled_outer_grid_mode == "double_ended":
        return _double_ended_panel_fractions(
            config.free_surface_panels,
            config.coupled_outer_root_spacing_ratio,
            config.coupled_outer_far_spacing_ratio,
            config.coupled_outer_endpoint_decay,
        )
    return _geometric_panel_fractions(
        config.free_surface_panels,
        config.free_surface_panel_growth,
    )


def build_residual_curvature_monitor_fractions(
    coupled: SelfSimilarShallowJetCoupledResult,
    target_panel_count: int,
    *,
    root_spacing_ratio: float | None = None,
    far_spacing_ratio: float | None = None,
    endpoint_decay: float | None = None,
    residual_weight: float = 1.0,
    curvature_weight: float = 0.25,
    growth_weight: float = 0.15,
    smoothing_passes: int = 2,
    maximum_node_shift_panels: float = 2.0,
) -> np.ndarray:
    """Equidistribute a reference-isolated outer-free-surface monitor.

    The monitor combines the current kinematic residual, geometric turning,
    adjacent-panel growth, and a declared double-ended base density.  It uses
    no benchmark coordinates or target metric.  Returned normalized arclength
    fractions can be frozen in ``SelfSimilarWedgeConfig`` so every Runge--Kutta
    resampling stage preserves the same declared mesh contract.
    """

    count = int(target_panel_count)
    if count < 12:
        raise ValueError("A monitored outer free surface requires at least 12 panels.")
    weights = np.asarray(
        [residual_weight, curvature_weight, growth_weight],
        dtype=float,
    )
    if not np.isfinite(weights).all() or np.any(weights < 0.0):
        raise ValueError("Monitor weights must be finite and non-negative.")
    passes = int(smoothing_passes)
    if passes < 0:
        raise ValueError("smoothing_passes must be non-negative.")
    maximum_shift = float(maximum_node_shift_panels)
    if not np.isfinite(maximum_shift) or maximum_shift <= 0.0:
        raise ValueError("maximum_node_shift_panels must be positive.")

    config = coupled.config
    root_ratio = float(
        config.coupled_outer_root_spacing_ratio
        if root_spacing_ratio is None
        else root_spacing_ratio
    )
    far_ratio = float(
        config.coupled_outer_far_spacing_ratio
        if far_spacing_ratio is None
        else far_spacing_ratio
    )
    decay = float(
        config.coupled_outer_endpoint_decay
        if endpoint_decay is None
        else endpoint_decay
    )
    base = _double_ended_panel_fractions(count, root_ratio, far_ratio, decay)

    nodes = np.column_stack(
        (
            coupled.outer_free_surface.node_xi,
            coupled.outer_free_surface.node_eta,
        )
    )
    segment_vector = np.diff(nodes, axis=0)
    length = np.linalg.norm(segment_vector, axis=1)
    if np.any(length <= np.finfo(float).eps):
        raise ValueError("The source outer free surface contains a zero-length panel.")
    arc = np.concatenate(([0.0], np.cumsum(length)))
    panel_mid_fraction = 0.5 * (arc[:-1] + arc[1:]) / arc[-1]

    endpoint_residual = coupled.outer_kinematic_residual_endpoint
    if endpoint_residual is None:
        residual_indicator = np.abs(coupled.outer_kinematic_residual)
    else:
        left = endpoint_residual[:, 0]
        right = endpoint_residual[:, 1]
        residual_indicator = np.sqrt(
            (np.square(left) + left * right + np.square(right)) / 3.0
        )

    tangent = segment_vector / length[:, None]
    node_turn = np.zeros(len(nodes), dtype=float)
    if len(tangent) > 1:
        node_turn[1:-1] = np.arccos(
            np.clip(np.sum(tangent[:-1] * tangent[1:], axis=1), -1.0, 1.0)
        )
    curvature_indicator = 0.5 * (node_turn[:-1] + node_turn[1:])

    log_length = np.log(length)
    growth_indicator = np.zeros_like(length)
    if len(length) > 1:
        adjacent_growth = np.abs(np.diff(log_length))
        growth_indicator[:-1] += 0.5 * adjacent_growth
        growth_indicator[1:] += 0.5 * adjacent_growth

    def normalized(indicator: np.ndarray) -> np.ndarray:
        scale = float(
            np.sqrt(
                np.sum(np.square(indicator) * length)
                / max(np.sum(length), np.finfo(float).eps)
            )
        )
        if scale <= np.finfo(float).eps:
            return np.zeros_like(indicator)
        return np.clip(indicator / scale, 0.0, 8.0)

    base_length = np.diff(base)
    base_mid = 0.5 * (base[:-1] + base[1:])
    base_density = np.interp(
        panel_mid_fraction,
        base_mid,
        1.0 / (count * base_length),
        left=1.0 / (count * base_length[0]),
        right=1.0 / (count * base_length[-1]),
    )
    monitor = base_density * (
        1.0
        + weights[0] * normalized(residual_indicator)
        + weights[1] * normalized(curvature_indicator)
        + weights[2] * normalized(growth_indicator)
    )
    for _ in range(passes):
        padded = np.pad(np.log(monitor), (1, 1), mode="edge")
        monitor = np.exp(
            0.25 * padded[:-2] + 0.5 * padded[1:-1] + 0.25 * padded[2:]
        )

    cumulative = np.concatenate(([0.0], np.cumsum(monitor * length)))
    cumulative /= cumulative[-1]
    adaptive_arc = np.interp(np.linspace(0.0, 1.0, count + 1), cumulative, arc)
    adaptive = adaptive_arc / arc[-1]
    maximum_fraction_shift = maximum_shift / count
    fractions = np.clip(
        adaptive,
        base - maximum_fraction_shift,
        base + maximum_fraction_shift,
    )
    fractions[[0, -1]] = (0.0, 1.0)
    if np.any(np.diff(fractions) <= 0.0):
        raise ValueError("The monitored grid lost strict node ordering.")
    return fractions


def _body_panel_fractions(panel_count: int, growth: float) -> np.ndarray:
    """Return body arclength fractions clustered at the spray-root end."""

    outward = _geometric_panel_fractions(panel_count, growth)
    return 1.0 - outward[::-1]


def build_iafrati_dipole_initial_free_surface(
    config: SelfSimilarWedgeConfig,
    dipole_coefficient: float,
) -> SelfSimilarFreeSurface:
    """Construct the wedge-entry first guess from Iafrati (2013), Eq. (51).

    The free surface ``eta=CD/(3*xi**2)`` is clipped only by its physical
    intersections with the wedge and the circular far boundary.  No
    Zhao--Faltinsen or Sun--Troesch reference value enters this construction.
    """

    if config.jet_closure != "body_root":
        raise ValueError("Iafrati Eq. (51) initialization requires jet_closure='body_root'.")
    coefficient = float(dipole_coefficient)
    if not np.isfinite(coefficient) or coefficient <= 0.0:
        raise ValueError("dipole_coefficient must be finite and positive.")
    beta = np.deg2rad(config.deadrise_deg)
    radius = float(config.far_radius)

    def elevation(xi: float | np.ndarray) -> float | np.ndarray:
        return coefficient / (3.0 * np.square(xi))

    def body_intersection(xi: float) -> float:
        return -1.0 + xi * np.tan(beta) - float(elevation(xi))

    lower = max(1.0 / np.tan(beta), np.sqrt(np.finfo(float).eps))
    upper = radius * (1.0 - 1.0e-10)
    if body_intersection(upper) <= 0.0:
        raise ValueError("The Eq. (51) free surface does not intersect the wedge inside the far field.")
    root_xi = float(brentq(body_intersection, lower, upper, xtol=1.0e-13))

    def far_intersection(xi: float) -> float:
        return xi**2 + float(elevation(xi)) ** 2 - radius**2

    if far_intersection(root_xi) >= 0.0:
        raise ValueError("The Eq. (51) wedge intersection lies outside the far-field circle.")
    far_xi = float(brentq(far_intersection, root_xi, radius, xtol=1.0e-13))
    fractions = _outer_panel_fractions(config)
    node_xi = root_xi + fractions * (far_xi - root_xi)
    node_eta = np.asarray(elevation(node_xi), dtype=float)
    return build_self_similar_free_surface_from_nodes(
        config,
        node_xi,
        node_eta,
        far_dipole_coefficient=coefficient,
    )


def _project_root_to_wedge(
    root: np.ndarray,
    deadrise_rad: float,
) -> np.ndarray:
    apex = np.asarray([0.0, -1.0])
    tangent = np.asarray([np.cos(deadrise_rad), np.sin(deadrise_rad)])
    distance = float(np.dot(root - apex, tangent))
    if distance <= 0.0:
        raise ValueError("Free-surface root projects behind the wedge apex.")
    return apex + distance * tangent


def build_self_similar_wedge_boundary(
    config: SelfSimilarWedgeConfig,
    free_surface: SelfSimilarFreeSurface,
) -> ClosedBoundary2D:
    """Build the closed half-domain used by the truncated-jet outer solver."""

    beta = np.deg2rad(config.deadrise_deg)
    root = np.asarray([free_surface.node_xi[0], free_surface.node_eta[0]])
    body_end = (
        root.copy()
        if config.jet_closure == "body_root"
        else _project_root_to_wedge(root, beta)
    )
    if body_end[1] < -1.0e-10:
        raise ValueError(
            "The truncated spray-jet control surface projects below eta=0."
        )
    radius = float(config.far_radius)

    coordinates = [np.column_stack((free_surface.node_xi, free_surface.node_eta))]
    labels: list[str] = ["free_surface"] * (len(free_surface.node_xi) - 1)

    far_start_angle = float(np.arctan2(free_surface.node_eta[-1], free_surface.node_xi[-1]))
    if not -0.5 * np.pi < far_start_angle < 0.5 * np.pi:
        raise ValueError("The outer free-surface node must lie on the right far-field semicircle.")
    theta = np.linspace(far_start_angle, -0.5 * np.pi, config.far_field_panels + 1)
    far = np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))
    far[0] = np.asarray([free_surface.node_xi[-1], free_surface.node_eta[-1]])
    coordinates.append(far[1:])
    labels.extend(["far_field"] * config.far_field_panels)

    symmetry = np.column_stack(
        (
            np.zeros(config.symmetry_panels + 1),
            np.linspace(-radius, -1.0, config.symmetry_panels + 1),
        )
    )
    coordinates.append(symmetry[1:])
    labels.extend(["symmetry"] * config.symmetry_panels)

    apex = np.asarray([0.0, -1.0])
    body_fraction = _body_panel_fractions(
        config.body_panels,
        config.body_panel_growth,
    )
    body = apex[None, :] + body_fraction[:, None] * (body_end - apex)[None, :]
    coordinates.append(body[1:])
    labels.extend(["body"] * config.body_panels)

    if config.jet_closure == "truncated_control":
        control_fraction = np.linspace(0.0, 1.0, config.jet_control_panels + 1)
        control = body_end[None, :] + control_fraction[:, None] * (root - body_end)[None, :]
        coordinates.append(control[1:])
        labels.extend(["jet_control"] * config.jet_control_panels)

    nodes = np.vstack(coordinates)
    nodes[-1] = nodes[0]
    return ClosedBoundary2D(nodes[:, 0], nodes[:, 1], tuple(labels))


def _jet_control_normal_derivative(
    boundary: ClosedBoundary2D,
    free_surface: SelfSimilarFreeSurface,
) -> float:
    """Project the root free-surface tangential velocity onto the control normal.

    This is the coordinate-invariant form of the truncated-jet control
    approximation associated with Iafrati Eq. (37).  It is intentionally
    isolated because a shallow-water jet match is still required for final
    validation.
    """

    labels = np.asarray(boundary.panel_labels, dtype=object)
    free_index = np.flatnonzero(labels == "free_surface")
    control_index = np.flatnonzero(labels == "jet_control")
    if len(control_index) == 0:
        return 0.0
    midpoint_s = 0.5 * (free_surface.arc_length[:-1] + free_surface.arc_length[1:])
    edge_order = 2 if len(midpoint_s) >= 3 else 1
    dphi_ds = np.gradient(free_surface.potential, midpoint_s, edge_order=edge_order)
    root_velocity = dphi_ds[0] * boundary.panel_tangent[free_index[0]]
    return float(np.dot(root_velocity, boundary.panel_normal[control_index[0]]))


def solve_self_similar_wedge_bvp_for_free_surface(
    config: SelfSimilarWedgeConfig,
    free_surface: SelfSimilarFreeSurface,
) -> SelfSimilarWedgeBvpResult:
    """Solve one fixed-shape self-similar mixed BVP with far dipole closure."""

    boundary = build_self_similar_wedge_boundary(config, free_surface)
    labels = np.asarray(boundary.panel_labels, dtype=object)
    free_mask = labels == "free_surface"
    far_mask = labels == "far_field"
    body_mask = labels == "body"
    symmetry_mask = labels == "symmetry"
    control_mask = labels == "jet_control"
    dirichlet_mask = free_mask | far_mask
    neumann_mask = ~dirichlet_mask

    h_matrix, g_matrix = constant_panel_influence_matrices(
        boundary,
        gauss_order=config.gauss_order,
    )
    count = boundary.panel_count
    system = np.zeros((count + 1, count + 1), dtype=float)
    rhs = np.zeros(count + 1, dtype=float)
    dirichlet_index = np.flatnonzero(dirichlet_mask)
    neumann_index = np.flatnonzero(neumann_mask)

    system[:count, dirichlet_index] = -g_matrix[:, dirichlet_mask]
    system[:count, neumann_index] = h_matrix[:, neumann_mask]

    free_phi = free_surface.potential
    rhs[:count] -= h_matrix[:, free_mask] @ free_phi

    q_known = np.zeros(count, dtype=float)
    beta = np.deg2rad(config.deadrise_deg)
    q_known[body_mask] = -np.cos(beta)
    q_known[symmetry_mask] = 0.0
    control_q = _jet_control_normal_derivative(boundary, free_surface)
    if np.any(control_mask):
        q_known[control_mask] = control_q
    rhs[:count] += g_matrix[:, neumann_mask] @ q_known[neumann_mask]

    far_radius_squared = (
        boundary.panel_mid_y_m[far_mask] ** 2
        + boundary.panel_mid_z_up_m[far_mask] ** 2
    )
    dipole_basis = boundary.panel_mid_z_up_m[far_mask] / far_radius_squared
    system[:count, count] = h_matrix[:, far_mask] @ dipole_basis

    far_index = np.flatnonzero(far_mask)
    far_xi = boundary.panel_mid_y_m[far_mask]
    far_eta = boundary.panel_mid_z_up_m[far_mask]
    radius_squared = far_xi**2 + far_eta**2
    dipole_gradient = np.column_stack(
        (
            -2.0 * far_xi * far_eta / np.square(radius_squared),
            (far_xi**2 - far_eta**2) / np.square(radius_squared),
        )
    )
    dipole_normal_derivative = np.sum(
        dipole_gradient * boundary.panel_normal[far_mask], axis=1
    )
    system[count, far_index] = -boundary.panel_length_m[far_mask]
    system[count, count] = float(
        np.sum(dipole_normal_derivative * boundary.panel_length_m[far_mask])
    )

    try:
        unknown = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError:
        unknown, _, rank, _ = np.linalg.lstsq(system, rhs, rcond=1.0e-12)
        if rank < count + 1:
            raise ValueError("Self-similar augmented BEM system is rank deficient.")

    dipole_coefficient = float(unknown[count])
    potential = np.empty(count, dtype=float)
    normal_derivative = np.empty(count, dtype=float)
    potential[free_mask] = free_phi
    potential[far_mask] = dipole_coefficient * dipole_basis
    potential[neumann_mask] = unknown[:count][neumann_mask]
    normal_derivative[dirichlet_mask] = unknown[:count][dirichlet_mask]
    normal_derivative[neumann_mask] = q_known[neumann_mask]

    identity_residual = h_matrix @ potential - g_matrix @ normal_derivative
    identity_scale = max(
        float(np.linalg.norm(h_matrix @ potential)),
        float(np.linalg.norm(g_matrix @ normal_derivative)),
        1.0e-12,
    )
    flux_residual = float(
        -np.sum(normal_derivative[far_mask] * boundary.panel_length_m[far_mask])
        + dipole_coefficient
        * np.sum(dipole_normal_derivative * boundary.panel_length_m[far_mask])
    )
    solution = MixedBoundarySolution(
        potential_m2_s=potential,
        normal_derivative_m_s=normal_derivative,
        condition_number=float(np.linalg.cond(system)),
        relative_residual=float(np.linalg.norm(identity_residual) / identity_scale),
        max_abs_residual=float(np.max(np.abs(identity_residual))),
        dirichlet_panel_count=int(np.count_nonzero(dirichlet_mask)),
        neumann_panel_count=int(np.count_nonzero(neumann_mask)),
        gauss_order=config.gauss_order,
        status=SELF_SIMILAR_WEDGE_STATUS,
    )

    position = np.column_stack((boundary.panel_mid_y_m, boundary.panel_mid_z_up_m))
    s_normal = normal_derivative[free_mask] - np.sum(
        position[free_mask] * boundary.panel_normal[free_mask], axis=1
    )
    residual_scale = np.maximum(
        1.0,
        np.abs(np.sum(position[free_mask] * boundary.panel_normal[free_mask], axis=1)),
    )
    scaled_s_normal = s_normal / residual_scale

    velocity = boundary_velocity(boundary, solution, respect_label_boundaries=True)
    pressure_function = (
        -potential
        + np.sum(position * velocity, axis=1)
        - 0.5 * np.sum(np.square(velocity), axis=1)
    )
    pressure_coefficient = 2.0 * pressure_function[body_mask]
    vertical_force = float(
        np.sum(
            pressure_coefficient
            * boundary.panel_normal[body_mask, 1]
            * boundary.panel_length_m[body_mask]
        )
    )
    return SelfSimilarWedgeBvpResult(
        boundary=boundary,
        solution=solution,
        free_surface=free_surface,
        dipole_coefficient=dipole_coefficient,
        flux_residual=flux_residual,
        kinematic_residual=s_normal,
        scaled_kinematic_residual=scaled_s_normal,
        jet_control_normal_derivative=control_q,
        body_pressure_coefficient=pressure_coefficient,
        body_vertical_force_coefficient=vertical_force,
    )


def solve_self_similar_wedge_bvp(
    config: SelfSimilarWedgeConfig,
    control_values: np.ndarray,
) -> SelfSimilarWedgeBvpResult:
    """Build the parametric free surface and solve its mixed BVP."""

    return solve_self_similar_wedge_bvp_for_free_surface(
        config,
        build_self_similar_free_surface(config, control_values),
    )


def solve_iafrati_dipole_preliminary_iterations(
    config: SelfSimilarWedgeConfig,
) -> SelfSimilarPreliminaryResult:
    """Run the Eq. (51) dipole-only preliminary iterations from Section 4.1."""

    coefficient = float(config.initial_dipole_coefficient)
    coefficient_history: list[float] = []
    change_history: list[float] = []
    converged = False
    bvp: SelfSimilarWedgeBvpResult | None = None
    for _ in range(int(config.preliminary_iterations)):
        free_surface = build_iafrati_dipole_initial_free_surface(config, coefficient)
        bvp = solve_self_similar_wedge_bvp_for_free_surface(config, free_surface)
        updated = float(bvp.dipole_coefficient)
        if not np.isfinite(updated) or updated <= 0.0:
            raise ValueError("The preliminary BVP produced a non-positive dipole coefficient.")
        relative_change = abs(updated - coefficient) / max(
            abs(coefficient), np.finfo(float).eps
        )
        coefficient_history.append(coefficient)
        change_history.append(relative_change)
        if relative_change <= float(config.preliminary_relative_tolerance):
            converged = True
            break
        coefficient = updated
    if bvp is None:
        raise RuntimeError("No preliminary dipole iteration was executed.")
    return SelfSimilarPreliminaryResult(
        config=config,
        bvp=bvp,
        dipole_coefficient_history=np.asarray(coefficient_history),
        relative_change_history=np.asarray(change_history),
        converged=converged,
    )


def _free_surface_pseudo_velocity(
    config: SelfSimilarWedgeConfig,
    bvp: SelfSimilarWedgeBvpResult,
) -> np.ndarray:
    """Reconstruct nodal ``grad(S)=grad(phi)-x`` for Iafrati Eq. (32)."""

    labels = np.asarray(bvp.boundary.panel_labels, dtype=object)
    free_index = np.flatnonzero(labels == "free_surface")
    all_velocity = boundary_velocity(
        bvp.boundary,
        bvp.solution,
        respect_label_boundaries=True,
    )
    velocity = all_velocity[free_index]
    midpoint = np.column_stack(
        (
            bvp.boundary.panel_mid_y_m[free_index],
            bvp.boundary.panel_mid_z_up_m[free_index],
        )
    )
    panel_gradient = velocity - midpoint
    panel_length = bvp.boundary.panel_length_m[free_index]
    node_gradient = np.empty((len(panel_gradient) + 1, 2), dtype=float)
    if config.jet_closure == "body_root":
        # The body/free-surface intersection is a mixed-boundary corner. Its
        # pseudo velocity must be taken from the body side and projected along
        # the body because the normal derivative jumps across the corner.
        body_index = np.flatnonzero(labels == "body")
        if len(body_index) == 0:
            raise ValueError("Pseudo-time root motion requires a resolved body boundary.")
        last_body = int(body_index[-1])
        body_position = np.asarray(
            [
                bvp.boundary.panel_mid_y_m[last_body],
                bvp.boundary.panel_mid_z_up_m[last_body],
            ]
        )
        body_gradient = all_velocity[last_body] - body_position
        body_tangent = bvp.boundary.panel_tangent[last_body]
        node_gradient[0] = float(np.dot(body_gradient, body_tangent)) * body_tangent
    else:
        # A truncated-control root lies on the physical free surface rather
        # than on the body, so Eq. (32) uses the free-side pseudo velocity.
        node_gradient[0] = panel_gradient[0]
    node_gradient[-1] = panel_gradient[-1]
    if len(panel_gradient) > 1:
        denominator = panel_length[:-1] + panel_length[1:]
        node_gradient[1:-1] = (
            panel_length[1:, None] * panel_gradient[:-1]
            + panel_length[:-1, None] * panel_gradient[1:]
        ) / denominator[:, None]
    return node_gradient


def _constrain_pseudo_time_nodes(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> np.ndarray:
    constrained = np.asarray(nodes, dtype=float).copy()
    if constrained.shape != (config.free_surface_panels + 1, 2):
        raise ValueError("Pseudo-time nodes have an inconsistent shape.")
    beta = np.deg2rad(config.deadrise_deg)
    if config.jet_closure == "body_root":
        constrained[0] = _project_root_to_wedge(constrained[0], beta)
    else:
        body_root = _project_root_to_wedge(constrained[0], beta)
        if body_root[1] < -1.0e-10:
            raise ValueError("Truncated-control root projected below eta=0.")
        if float(np.linalg.norm(constrained[0] - body_root)) <= 1.0e-10:
            raise ValueError("Truncated-control pseudo time collapsed the jet root thickness.")
    far_norm = float(np.linalg.norm(constrained[-1]))
    if far_norm <= np.finfo(float).eps or constrained[-1, 0] <= 0.0:
        raise ValueError("Pseudo-time far node left the right far-field semicircle.")
    constrained[-1] *= float(config.far_radius) / far_norm
    return constrained


def _regrid_pseudo_time_nodes(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> np.ndarray:
    segment = np.linalg.norm(np.diff(nodes, axis=0), axis=1)
    if np.any(segment <= 1.0e-12):
        raise ValueError("Pseudo-time update produced a zero-length free-surface panel.")
    arc = np.concatenate(([0.0], np.cumsum(segment)))
    target = arc[-1] * _outer_panel_fractions(config)
    xi_spline = CubicSpline(arc, nodes[:, 0], bc_type="natural")
    eta_spline = CubicSpline(arc, nodes[:, 1], bc_type="natural")
    regridded = np.column_stack((xi_spline(target), eta_spline(target)))
    regridded[0] = nodes[0]
    regridded[-1] = nodes[-1]
    return _constrain_pseudo_time_nodes(config, regridded)


def self_similar_wedge_root_angle_deg(
    config: SelfSimilarWedgeConfig,
    free_surface: SelfSimilarFreeSurface,
) -> float:
    """Return the acute body/free-surface angle at the truncated jet root."""

    beta = np.deg2rad(config.deadrise_deg)
    body_tangent = np.asarray([np.cos(beta), np.sin(beta)])
    free_tangent = np.asarray(
        [
            free_surface.node_xi[1] - free_surface.node_xi[0],
            free_surface.node_eta[1] - free_surface.node_eta[0],
        ]
    )
    free_tangent /= np.linalg.norm(free_tangent)
    return float(np.rad2deg(np.arccos(np.clip(np.dot(body_tangent, free_tangent), -1.0, 1.0))))


def advance_self_similar_wedge_pseudo_time_rk2(
    config: SelfSimilarWedgeConfig,
    bvp: SelfSimilarWedgeBvpResult,
) -> tuple[SelfSimilarWedgeBvpResult, float, float]:
    """Advance one adaptive second-order Eq. (32) step without reference data."""

    old_nodes = np.column_stack(
        (bvp.free_surface.node_xi, bvp.free_surface.node_eta)
    )
    free_length = np.diff(bvp.free_surface.arc_length)
    k1 = _free_surface_pseudo_velocity(config, bvp)
    panel_speed = 0.5 * (
        np.linalg.norm(k1[:-1], axis=1) + np.linalg.norm(k1[1:], axis=1)
    )
    time_step = float(config.pseudo_cfl) * float(
        np.min(free_length / np.maximum(panel_speed, np.finfo(float).eps))
    )
    if not np.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("Pseudo-time CFL produced an invalid time step.")

    maximum_ratio = np.inf
    for _ in range(12):
        provisional_nodes = _constrain_pseudo_time_nodes(
            config,
            old_nodes + time_step * k1,
        )
        provisional_surface = build_self_similar_free_surface_from_nodes(
            config,
            provisional_nodes[:, 0],
            provisional_nodes[:, 1],
            far_dipole_coefficient=bvp.dipole_coefficient,
        )
        provisional_bvp = solve_self_similar_wedge_bvp_for_free_surface(
            config,
            provisional_surface,
        )
        k2 = _free_surface_pseudo_velocity(config, provisional_bvp)
        raw_nodes = _constrain_pseudo_time_nodes(
            config,
            old_nodes + 0.5 * time_step * (k1 + k2),
        )
        old_midpoint = 0.5 * (old_nodes[:-1] + old_nodes[1:])
        new_midpoint = 0.5 * (raw_nodes[:-1] + raw_nodes[1:])
        displacement = np.linalg.norm(new_midpoint - old_midpoint, axis=1)
        maximum_ratio = float(np.max(displacement / free_length))
        if maximum_ratio <= 0.25 + 1.0e-12:
            break
        time_step *= 0.5
    else:
        raise ValueError("Pseudo-time step could not satisfy the one-quarter-panel CFL limit.")

    new_nodes = _regrid_pseudo_time_nodes(config, raw_nodes)
    new_surface = build_self_similar_free_surface_from_nodes(
        config,
        new_nodes[:, 0],
        new_nodes[:, 1],
        far_dipole_coefficient=bvp.dipole_coefficient,
    )
    return (
        solve_self_similar_wedge_bvp_for_free_surface(config, new_surface),
        time_step,
        maximum_ratio,
    )


def solve_self_similar_wedge_pseudo_time(
    config: SelfSimilarWedgeConfig,
    *,
    initial_bvp: SelfSimilarWedgeBvpResult | None = None,
) -> SelfSimilarPseudoTimeResult:
    """Run Eq. (51) initialization and Eqs. (31)--(34) pseudo time.

    The run stops before an unresolved thin jet can be passed off as a valid
    boundary-integral solution.  ``JET_MODEL_REQUIRED`` is therefore a
    physical interface state, not a successful wedge benchmark result.
    """

    if initial_bvp is None and config.jet_closure != "body_root":
        raise ValueError("truncated_control pseudo time requires an initial outer BVP.")
    bvp = (
        initial_bvp
        if initial_bvp is not None
        else solve_iafrati_dipole_preliminary_iterations(config).bvp
    )
    pseudo_time = [0.0]
    steps: list[float] = []
    kinematic = [bvp.kinematic_rms]
    dipole = [bvp.dipole_coefficient]
    displacement: list[float] = []
    angle = [self_similar_wedge_root_angle_deg(config, bvp.free_surface)]
    converged = bvp.kinematic_rms <= float(config.pseudo_kinematic_tolerance)
    termination: Literal[
        "KINEMATIC_CONVERGED",
        "JET_MODEL_REQUIRED",
        "MAXIMUM_ITERATIONS",
        "NUMERICAL_FAILURE",
    ] = "KINEMATIC_CONVERGED" if converged else "MAXIMUM_ITERATIONS"
    failure_message: str | None = None

    for _ in range(int(config.pseudo_max_iterations)):
        if converged:
            break
        if (
            config.jet_closure == "body_root"
            and angle[-1] <= float(config.jet_angle_threshold_deg)
        ):
            termination = "JET_MODEL_REQUIRED"
            break
        try:
            previous_bvp = bvp
            previous_angle = angle[-1]
            bvp, time_step, maximum_ratio = advance_self_similar_wedge_pseudo_time_rk2(
                config,
                previous_bvp,
            )
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            termination = "NUMERICAL_FAILURE"
            failure_message = str(error)
            break
        new_angle = self_similar_wedge_root_angle_deg(config, bvp.free_surface)
        threshold = float(config.jet_angle_threshold_deg)
        if (
            config.jet_closure == "body_root"
            and previous_angle > threshold
            and new_angle < threshold
        ):
            lower_fraction = 0.0
            upper_fraction = 1.0
            event_bvp = bvp
            event_step = time_step
            event_ratio = maximum_ratio
            for _ in range(18):
                middle_fraction = 0.5 * (lower_fraction + upper_fraction)
                event_config = replace(
                    config,
                    pseudo_cfl=float(config.pseudo_cfl) * middle_fraction,
                )
                candidate_bvp, candidate_step, candidate_ratio = (
                    advance_self_similar_wedge_pseudo_time_rk2(
                        event_config,
                        previous_bvp,
                    )
                )
                candidate_angle = self_similar_wedge_root_angle_deg(
                    config,
                    candidate_bvp.free_surface,
                )
                if candidate_angle > threshold:
                    lower_fraction = middle_fraction
                else:
                    upper_fraction = middle_fraction
                    event_bvp = candidate_bvp
                    event_step = candidate_step
                    event_ratio = candidate_ratio
                if abs(candidate_angle - threshold) <= 1.0e-3:
                    event_bvp = candidate_bvp
                    event_step = candidate_step
                    event_ratio = candidate_ratio
                    break
            bvp = event_bvp
            time_step = event_step
            maximum_ratio = event_ratio
            new_angle = self_similar_wedge_root_angle_deg(config, bvp.free_surface)

        steps.append(time_step)
        displacement.append(maximum_ratio)
        pseudo_time.append(pseudo_time[-1] + time_step)
        kinematic.append(bvp.kinematic_rms)
        dipole.append(bvp.dipole_coefficient)
        angle.append(new_angle)
        if bvp.kinematic_rms <= float(config.pseudo_kinematic_tolerance):
            converged = True
            termination = "KINEMATIC_CONVERGED"
            break
    return SelfSimilarPseudoTimeResult(
        config=config,
        bvp=bvp,
        pseudo_time_history=np.asarray(pseudo_time),
        time_step_history=np.asarray(steps),
        kinematic_rms_history=np.asarray(kinematic),
        dipole_coefficient_history=np.asarray(dipole),
        maximum_displacement_ratio_history=np.asarray(displacement),
        root_angle_deg_history=np.asarray(angle),
        converged=converged,
        termination_reason=termination,
        failure_message=failure_message,
    )


def truncate_self_similar_wedge_to_shallow_jet(
    config: SelfSimilarWedgeConfig,
    pseudo_result: SelfSimilarPseudoTimeResult,
) -> SelfSimilarJetTruncationResult:
    """Replace the unresolved thin tip by Iafrati's Fig. 3 jet interface.

    Starting at the body/free-surface contact, the first node at which the
    next outer free-surface panel again forms more than the source threshold
    with the body is retained as the bulk-flow root.  The free point is
    projected normally to the wedge to form the finite jet thickness.  The
    omitted tip is then marched from that root with Eqs. (43)--(46).
    """

    if config.jet_closure != "body_root":
        raise ValueError("Jet truncation requires a body_root pseudo-time solution.")
    if pseudo_result.termination_reason != "JET_MODEL_REQUIRED":
        raise ValueError("Jet truncation requires a JET_MODEL_REQUIRED pseudo-time state.")
    free_surface = pseudo_result.bvp.free_surface
    nodes = np.column_stack((free_surface.node_xi, free_surface.node_eta))
    segment = np.diff(nodes, axis=0)
    segment /= np.linalg.norm(segment, axis=1)[:, None]
    beta = np.deg2rad(config.deadrise_deg)
    outward_body_tangent = np.asarray([np.cos(beta), np.sin(beta)])
    panel_angle = np.rad2deg(
        np.arccos(np.clip(segment @ outward_body_tangent, -1.0, 1.0))
    )
    threshold = float(config.jet_angle_threshold_deg)
    if panel_angle[0] > threshold + 1.0e-10:
        raise ValueError("The contact panel has not reached the jet-angle threshold.")
    outer_panel = np.flatnonzero(panel_angle[1:] > threshold)
    if len(outer_panel) == 0:
        raise ValueError("No resolved outer free-surface panel exists beyond the thin jet.")
    truncated_config = replace(config, jet_closure="truncated_control")
    last_physical_error: ValueError | None = None
    for candidate_panel in outer_panel:
        cut_node_index = int(candidate_panel + 1)
        retained = nodes[cut_node_index:]
        if len(retained) < 4:
            break

        retained_segment = np.linalg.norm(np.diff(retained, axis=0), axis=1)
        retained_arc = np.concatenate(([0.0], np.cumsum(retained_segment)))
        target_arc = retained_arc[-1] * _geometric_panel_fractions(
            config.free_surface_panels,
            config.free_surface_panel_growth,
        )
        xi_spline = CubicSpline(retained_arc, retained[:, 0], bc_type="natural")
        eta_spline = CubicSpline(retained_arc, retained[:, 1], bc_type="natural")
        outer_nodes = np.column_stack((xi_spline(target_arc), eta_spline(target_arc)))
        outer_nodes[0] = retained[0]
        outer_nodes[-1] = retained[-1]

        truncated_surface = build_self_similar_free_surface_from_nodes(
            truncated_config,
            outer_nodes[:, 0],
            outer_nodes[:, 1],
            far_dipole_coefficient=pseudo_result.bvp.dipole_coefficient,
        )
        truncated_bvp = solve_self_similar_wedge_bvp_for_free_surface(
            truncated_config,
            truncated_surface,
        )
        try:
            return _build_shallow_jet_interface_from_truncated_bvp(
                truncated_config,
                truncated_bvp,
                original_cut_node_index=cut_node_index,
                cut_angle_deg=float(panel_angle[cut_node_index]),
            )
        except ValueError as error:
            message = str(error).lower()
            if (
                "no physical first-step solution" not in message
                and "jet root requires" not in message
            ):
                raise
            last_physical_error = error

    detail = "" if last_physical_error is None else f" Last root error: {last_physical_error}"
    raise ValueError(
        "No shallow-water-compatible initial matching surface remains." + detail
    )


def _build_shallow_jet_interface_from_truncated_bvp(
    config: SelfSimilarWedgeConfig,
    truncated_bvp: SelfSimilarWedgeBvpResult,
    *,
    original_cut_node_index: int,
    cut_angle_deg: float,
    s_lambda_seed: float | None = None,
) -> SelfSimilarJetTruncationResult:
    if config.jet_closure != "truncated_control":
        raise ValueError("A shallow-water interface requires truncated_control closure.")
    root_state = derive_shallow_water_jet_root_state(
        truncated_bvp,
        deadrise_deg=config.deadrise_deg,
    )
    if s_lambda_seed is not None:
        if not np.isfinite(s_lambda_seed) or float(s_lambda_seed) <= 0.0:
            raise ValueError("The augmented-BIE shallow-jet S_lambda seed must be positive.")
        root_state = replace(root_state, s_lambda=float(s_lambda_seed))
    jet = march_iafrati_shallow_water_jet(
        initial_thickness=root_state.thickness,
        initial_s_lambda=root_state.s_lambda,
        initial_s_tau=root_state.s_tau,
        delta_lambda=root_state.delta_lambda,
        maximum_points=config.shallow_jet_maximum_points,
    )

    free_root = np.asarray(
        [
            truncated_bvp.free_surface.node_xi[0],
            truncated_bvp.free_surface.node_eta[0],
        ]
    )
    beta = np.deg2rad(config.deadrise_deg)
    body_root = _project_root_to_wedge(free_root, beta)
    fluid_normal = (free_root - body_root) / root_state.thickness
    body_nodes = (
        body_root[None, :]
        + jet.lambda_coordinate[:, None] * root_state.lambda_tangent[None, :]
    )
    free_nodes = body_nodes + jet.thickness[:, None] * fluid_normal[None, :]
    free_nodes[0] = free_root
    return SelfSimilarJetTruncationResult(
        config=config,
        bvp=truncated_bvp,
        root_state=root_state,
        jet=jet,
        original_cut_node_index=int(original_cut_node_index),
        cut_angle_deg=float(cut_angle_deg),
        body_node_xi=body_nodes[:, 0],
        body_node_eta=body_nodes[:, 1],
        free_node_xi=free_nodes[:, 0],
        free_node_eta=free_nodes[:, 1],
    )


def _recover_connected_linear_panel_velocity(
    boundary: ClosedBoundary2D,
    potential_node: np.ndarray,
    panel_normal_derivative: np.ndarray,
    *,
    split_free_surface_cusp: bool = False,
) -> np.ndarray:
    """Recover a continuous tangential gradient on physically smooth chains.

    Linear elements give a piecewise-constant tangential derivative.  The main
    and shallow body are one straight wedge face, while the shallow and outer
    free surfaces meet at the numerical matching surface.  A nonuniform nodal
    derivative is therefore recovered across each connected chain before the
    pressure and pseudo-velocity are evaluated at panel midpoints.  Geometric
    corners such as body/symmetry and free/far remain separate.
    """

    node_phi = np.asarray(potential_node, dtype=float)
    panel_q = np.asarray(panel_normal_derivative, dtype=float)
    count = boundary.panel_count
    if node_phi.shape != (count,) or panel_q.shape != (count,):
        raise ValueError("Connected gradient recovery requires nodal phi and panel q.")
    labels = np.asarray(boundary.panel_labels, dtype=object)
    panel_tangential = (
        np.roll(node_phi, -1) - node_phi
    ) / boundary.panel_length_m

    body_chain = np.concatenate(
        (
            np.flatnonzero(labels == "body"),
            np.flatnonzero(labels == "shallow_jet_body"),
        )
    )
    shallow_free = np.flatnonzero(labels == "shallow_jet_free_surface")
    outer_free = np.flatnonzero(labels == "outer_free_surface")
    chains = (
        (body_chain, shallow_free, outer_free)
        if split_free_surface_cusp
        else (body_chain, np.concatenate((shallow_free, outer_free)))
    )
    for panels in chains:
        if len(panels) < 2:
            continue
        expected_next = (panels[:-1] + 1) % count
        if not np.array_equal(expected_next, panels[1:]):
            raise ValueError("A connected gradient-recovery chain is not contiguous.")
        node_index = np.concatenate((panels[:1], [(panels[-1] + 1) % count]))
        if len(panels) > 1:
            node_index = np.concatenate(
                (
                    panels,
                    [(panels[-1] + 1) % count],
                )
            )
        arc = np.concatenate(
            ([0.0], np.cumsum(boundary.panel_length_m[panels]))
        )
        edge_order = 2 if len(node_index) >= 3 else 1
        node_tangential = np.gradient(
            node_phi[node_index],
            arc,
            edge_order=edge_order,
        )
        panel_tangential[panels] = 0.5 * (
            node_tangential[:-1] + node_tangential[1:]
        )
    return (
        panel_tangential[:, None] * boundary.panel_tangent
        + panel_q[:, None] * boundary.panel_normal
    )


def _solve_linear_augmented_self_similar_boundary(
    config: SelfSimilarWedgeConfig,
    boundary: ClosedBoundary2D,
    prescribed_potential_endpoint: np.ndarray,
    prescribed_normal_derivative_endpoint: np.ndarray,
) -> tuple[
    MixedBoundarySolution,
    float,
    float,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """Solve the dipole-augmented BVP with continuous linear elements."""

    count = boundary.panel_count
    phi_endpoint = np.asarray(prescribed_potential_endpoint, dtype=float)
    q_endpoint = np.asarray(prescribed_normal_derivative_endpoint, dtype=float)
    if phi_endpoint.shape != (count, 2) or q_endpoint.shape != (count, 2):
        raise ValueError("Linear augmented boundary data require two endpoint values per panel.")
    labels = np.asarray(boundary.panel_labels, dtype=object)
    far_mask = labels == "far_field"
    fixed_phi_panel = np.isfinite(phi_endpoint).all(axis=1)
    if np.any(np.isfinite(phi_endpoint).any(axis=1) != fixed_phi_panel):
        raise ValueError("Dirichlet panels require both endpoint potentials.")
    dirichlet_panel = fixed_phi_panel | far_mask
    neumann_panel = ~dirichlet_panel
    if not np.isfinite(q_endpoint[neumann_panel]).all():
        raise ValueError("Neumann panels require both endpoint normal derivatives.")

    h_matrix, g_left, g_right, panel_length = linear_element_influence_components(
        boundary,
        gauss_order=config.gauss_order,
    )
    node_dirichlet = np.zeros(count, dtype=bool)
    fixed_phi_sum = np.zeros(count, dtype=float)
    fixed_phi_count = np.zeros(count, dtype=int)
    for panel in np.flatnonzero(dirichlet_panel):
        left = int(panel)
        right = int((panel + 1) % count)
        node_dirichlet[[left, right]] = True
        if fixed_phi_panel[panel]:
            for endpoint, node in ((0, left), (1, right)):
                fixed_phi_sum[node] += phi_endpoint[panel, endpoint]
                fixed_phi_count[node] += 1
    fixed_phi = np.zeros(count, dtype=float)
    has_fixed_phi = fixed_phi_count > 0
    fixed_phi[has_fixed_phi] = (
        fixed_phi_sum[has_fixed_phi] / fixed_phi_count[has_fixed_phi]
    )
    for node in np.flatnonzero(fixed_phi_count > 1):
        values: list[float] = []
        previous = (int(node) - 1) % count
        if fixed_phi_panel[previous]:
            values.append(float(phi_endpoint[previous, 1]))
        if fixed_phi_panel[node]:
            values.append(float(phi_endpoint[node, 0]))
        scale = max(1.0, max(abs(value) for value in values))
        if max(values) - min(values) > 1.0e-6 * scale:
            raise ValueError(
                "Continuous linear free-surface potentials disagree at a shared node."
            )

    node_xi = boundary.node_y_m[:-1]
    node_eta = boundary.node_z_up_m[:-1]
    radius_squared = np.square(node_xi) + np.square(node_eta)
    dipole_basis_node = node_eta / radius_squared
    dipole_node_coefficient = np.zeros(count, dtype=float)
    for panel in np.flatnonzero(far_mask):
        for node in (int(panel), int((panel + 1) % count)):
            if not has_fixed_phi[node]:
                dipole_node_coefficient[node] = dipole_basis_node[node]
    if np.any(node_dirichlet & ~has_fixed_phi & (dipole_node_coefficient == 0.0)):
        raise ValueError("A continuous-linear Dirichlet node has no potential definition.")

    double_corner = config.coupled_linear_corner_treatment == "displaced_double_node"
    double_far_corner = (
        config.coupled_linear_far_corner_treatment == "displaced_double_node"
    )
    cusp_velocity_recovery = config.coupled_linear_cusp_velocity_recovery
    cusp_node: int | None = None
    cusp_previous: int | None = None
    cusp_next: int | None = None
    split_corners: list[tuple[str, int, int, int]] = []
    if double_corner:
        outer_panel = np.flatnonzero(labels == "outer_free_surface")
        shallow_free_panel = np.flatnonzero(labels == "shallow_jet_free_surface")
        if len(outer_panel) == 0 or len(shallow_free_panel) == 0:
            raise ValueError(
                "Displaced double-node treatment requires outer and shallow free surfaces."
            )
        cusp_next = int(outer_panel[0])
        cusp_node = cusp_next
        cusp_previous = int((cusp_node - 1) % count)
        if cusp_previous != int(shallow_free_panel[-1]):
            raise ValueError("The spray-root corner is not a connected free-surface cusp.")
        if not dirichlet_panel[cusp_previous] or not dirichlet_panel[cusp_next]:
            raise ValueError("Both spray-root sides must carry Dirichlet potential data.")
        split_corners.append(("spray_root", cusp_node, cusp_previous, cusp_next))
    if double_far_corner:
        outer_panel = np.flatnonzero(labels == "outer_free_surface")
        far_panel = np.flatnonzero(labels == "far_field")
        if len(outer_panel) == 0 or len(far_panel) == 0:
            raise ValueError(
                "Far-corner double-node treatment requires outer and far-field panels."
            )
        far_next = int(far_panel[0])
        far_node = far_next
        far_previous = int((far_node - 1) % count)
        if far_previous != int(outer_panel[-1]):
            raise ValueError("The free-surface/far-field corner is not connected.")
        if not dirichlet_panel[far_previous] or not dirichlet_panel[far_next]:
            raise ValueError("Both far-corner sides must carry Dirichlet potential data.")
        split_corners.append(("far_field", far_node, far_previous, far_next))
    split_nodes = [item[1] for item in split_corners]
    if len(set(split_nodes)) != len(split_nodes):
        raise ValueError("Two displaced double-node treatments selected the same node.")
    if split_corners:
        retained_row = ~np.isin(np.arange(count), split_nodes)
        displaced_panel = np.asarray(
            [panel for _, _, previous, next_panel in split_corners for panel in (previous, next_panel)],
            dtype=int,
        )
        displaced_fraction = np.tile(np.asarray([2.0 / 3.0, 1.0 / 3.0]), len(split_corners))
        displaced_y = (
            (1.0 - displaced_fraction) * boundary.node_y_m[displaced_panel]
            + displaced_fraction * boundary.node_y_m[displaced_panel + 1]
        )
        displaced_z = (
            (1.0 - displaced_fraction) * boundary.node_z_up_m[displaced_panel]
            + displaced_fraction * boundary.node_z_up_m[displaced_panel + 1]
        )
        displaced_h, displaced_g_left, displaced_g_right = (
            linear_element_influence_rows(
                boundary,
                field_y_m=displaced_y,
                field_z_up_m=displaced_z,
                field_panel_index=displaced_panel,
                field_panel_fraction=displaced_fraction,
                gauss_order=config.gauss_order,
            )
        )
        h_rows = np.vstack((h_matrix[retained_row], displaced_h))
        g_left_rows = np.vstack((g_left[retained_row], displaced_g_left))
        g_right_rows = np.vstack((g_right[retained_row], displaced_g_right))
    else:
        h_rows = h_matrix
        g_left_rows = g_left
        g_right_rows = g_right

    bie_row_count = h_rows.shape[0]
    extra_q_column = {
        (node, next_panel): count + index
        for index, (_, node, _, next_panel) in enumerate(split_corners)
    }
    dipole_column = count + len(split_corners)
    flux_row = bie_row_count
    system = np.zeros((bie_row_count + 1, dipole_column + 1), dtype=float)
    rhs = np.zeros(bie_row_count + 1, dtype=float)
    rhs[:bie_row_count] = -h_rows @ fixed_phi

    def q_unknown_column(panel: int, endpoint: int) -> int:
        node = int((panel + endpoint) % count)
        split_column = extra_q_column.get((node, panel)) if endpoint == 0 else None
        if split_column is not None:
            return split_column
        return node

    for node in range(count):
        if not node_dirichlet[node]:
            system[:bie_row_count, node] = h_rows[:, node]
    for panel in np.flatnonzero(dirichlet_panel):
        system[
            :bie_row_count,
            q_unknown_column(int(panel), 0),
        ] -= g_left_rows[:, panel]
        system[
            :bie_row_count,
            q_unknown_column(int(panel), 1),
        ] -= g_right_rows[:, panel]
    for panel in np.flatnonzero(neumann_panel):
        rhs[:bie_row_count] += g_left_rows[:, panel] * q_endpoint[panel, 0]
        rhs[:bie_row_count] += g_right_rows[:, panel] * q_endpoint[panel, 1]
    system[:bie_row_count, dipole_column] = h_rows @ dipole_node_coefficient

    dipole_gradient_node = np.column_stack(
        (
            -2.0 * node_xi * node_eta / np.square(radius_squared),
            (np.square(node_xi) - np.square(node_eta)) / np.square(radius_squared),
        )
    )
    dipole_flux = 0.0
    for panel in np.flatnonzero(far_mask):
        left = int(panel)
        right = int((panel + 1) % count)
        length = float(panel_length[panel])
        system[flux_row, q_unknown_column(int(panel), 0)] -= 0.5 * length
        system[flux_row, q_unknown_column(int(panel), 1)] -= 0.5 * length
        dipole_flux += 0.5 * length * float(
            np.dot(dipole_gradient_node[left], boundary.panel_normal[panel])
            + np.dot(dipole_gradient_node[right], boundary.panel_normal[panel])
        )
    system[flux_row, dipole_column] = dipole_flux

    try:
        unknown = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError:
        unknown, _, rank, _ = np.linalg.lstsq(
            system,
            rhs,
            rcond=1.0e-12,
        )
        if rank < len(system):
            raise ValueError("Linear shallow-jet augmented BEM system is rank deficient.")
    dipole_coefficient = float(unknown[dipole_column])
    potential_node = fixed_phi + dipole_coefficient * dipole_node_coefficient
    potential_node[~node_dirichlet] = unknown[:count][~node_dirichlet]
    solved_q_endpoint = np.empty((count, 2), dtype=float)
    for panel in range(count):
        if dirichlet_panel[panel]:
            solved_q_endpoint[panel] = (
                unknown[q_unknown_column(panel, 0)],
                unknown[q_unknown_column(panel, 1)],
            )
        else:
            solved_q_endpoint[panel] = q_endpoint[panel]
    integral_q_rows = np.zeros(bie_row_count, dtype=float)
    for panel in range(count):
        integral_q_rows += g_left_rows[:, panel] * solved_q_endpoint[panel, 0]
        integral_q_rows += g_right_rows[:, panel] * solved_q_endpoint[panel, 1]
    identity_residual = h_rows @ potential_node - integral_q_rows
    identity_scale = max(
        float(np.linalg.norm(h_rows @ potential_node)),
        float(np.linalg.norm(integral_q_rows)),
        1.0e-12,
    )
    panel_potential = 0.5 * (potential_node + np.roll(potential_node, -1))
    panel_q = np.mean(solved_q_endpoint, axis=1)
    tangential = (np.roll(potential_node, -1) - potential_node) / panel_length
    velocity = (
        tangential[:, None] * boundary.panel_tangent
        + panel_q[:, None] * boundary.panel_normal
    )
    if config.coupled_linear_gradient_recovery == "connected_nodal":
        velocity = _recover_connected_linear_panel_velocity(
            boundary,
            potential_node,
            panel_q,
            split_free_surface_cusp=(
                cusp_velocity_recovery != "connected_average"
            ),
        )
    position = np.column_stack((boundary.panel_mid_y_m, boundary.panel_mid_z_up_m))
    pressure_function = (
        -panel_potential
        + np.sum(position * velocity, axis=1)
        - 0.5 * np.sum(np.square(velocity), axis=1)
    )
    flux_residual = float(
        -sum(
            0.5
            * panel_length[panel]
            * np.sum(solved_q_endpoint[panel])
            for panel in np.flatnonzero(far_mask)
        )
        + dipole_coefficient * dipole_flux
    )
    solution = MixedBoundarySolution(
        potential_m2_s=panel_potential,
        normal_derivative_m_s=panel_q,
        condition_number=float(np.linalg.cond(system)),
        relative_residual=float(np.linalg.norm(identity_residual) / identity_scale),
        max_abs_residual=float(np.max(np.abs(identity_residual))),
        dirichlet_panel_count=int(np.count_nonzero(dirichlet_panel)),
        neumann_panel_count=int(np.count_nonzero(neumann_panel)),
        gauss_order=config.gauss_order,
        status=(
            "iafrati_2013_continuous_linear_shallow_jet_augmented_bie_"
            f"{config.coupled_linear_gradient_recovery}_gradient_"
            f"{config.coupled_linear_corner_treatment}_corner_"
            f"{config.coupled_linear_far_corner_treatment}_far_corner_"
            f"{cusp_velocity_recovery}_cusp_velocity_unvalidated"
        ),
    )
    return (
        solution,
        dipole_coefficient,
        flux_residual,
        velocity,
        pressure_function,
        solved_q_endpoint,
    )


def _solve_augmented_self_similar_boundary(
    config: SelfSimilarWedgeConfig,
    boundary: ClosedBoundary2D,
    prescribed_potential: np.ndarray,
    prescribed_normal_derivative: np.ndarray,
    *,
    prescribed_potential_endpoint: np.ndarray | None = None,
    prescribed_normal_derivative_endpoint: np.ndarray | None = None,
) -> tuple[
    MixedBoundarySolution,
    float,
    float,
    np.ndarray,
    np.ndarray,
    np.ndarray | None,
]:
    """Solve Eq. (29)--(30) for arbitrary body/free boundary topology."""

    if config.coupled_element_interpolation == "linear_node":
        if (
            prescribed_potential_endpoint is None
            or prescribed_normal_derivative_endpoint is None
        ):
            raise ValueError("Continuous linear coupling requires endpoint boundary data.")
        return _solve_linear_augmented_self_similar_boundary(
            config,
            boundary,
            prescribed_potential_endpoint,
            prescribed_normal_derivative_endpoint,
        )

    phi_known = np.asarray(prescribed_potential, dtype=float)
    q_known = np.asarray(prescribed_normal_derivative, dtype=float)
    count = boundary.panel_count
    if phi_known.shape != (count,) or q_known.shape != (count,):
        raise ValueError("Augmented self-similar boundary data must contain one value per panel.")
    labels = np.asarray(boundary.panel_labels, dtype=object)
    far_mask = labels == "far_field"
    free_mask = np.isfinite(phi_known)
    if np.any(free_mask & far_mask):
        raise ValueError("Far-field dipole panels cannot have a fixed potential coefficient.")
    dirichlet_mask = free_mask | far_mask
    neumann_mask = ~dirichlet_mask
    if not np.isfinite(q_known[neumann_mask]).all():
        raise ValueError("All Neumann panels require a finite prescribed normal derivative.")

    h_matrix, g_matrix = constant_panel_influence_matrices(
        boundary,
        gauss_order=config.gauss_order,
    )
    system = np.zeros((count + 1, count + 1), dtype=float)
    rhs = np.zeros(count + 1, dtype=float)
    dirichlet_index = np.flatnonzero(dirichlet_mask)
    neumann_index = np.flatnonzero(neumann_mask)
    system[:count, dirichlet_index] = -g_matrix[:, dirichlet_mask]
    system[:count, neumann_index] = h_matrix[:, neumann_mask]
    rhs[:count] -= h_matrix[:, free_mask] @ phi_known[free_mask]
    rhs[:count] += g_matrix[:, neumann_mask] @ q_known[neumann_mask]

    far_radius_squared = (
        boundary.panel_mid_y_m[far_mask] ** 2
        + boundary.panel_mid_z_up_m[far_mask] ** 2
    )
    dipole_basis = boundary.panel_mid_z_up_m[far_mask] / far_radius_squared
    system[:count, count] = h_matrix[:, far_mask] @ dipole_basis
    far_index = np.flatnonzero(far_mask)
    far_xi = boundary.panel_mid_y_m[far_mask]
    far_eta = boundary.panel_mid_z_up_m[far_mask]
    radius_squared = far_xi**2 + far_eta**2
    dipole_gradient = np.column_stack(
        (
            -2.0 * far_xi * far_eta / np.square(radius_squared),
            (far_xi**2 - far_eta**2) / np.square(radius_squared),
        )
    )
    dipole_normal_derivative = np.sum(
        dipole_gradient * boundary.panel_normal[far_mask],
        axis=1,
    )
    system[count, far_index] = -boundary.panel_length_m[far_mask]
    system[count, count] = float(
        np.sum(dipole_normal_derivative * boundary.panel_length_m[far_mask])
    )

    try:
        unknown = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError:
        unknown, _, rank, _ = np.linalg.lstsq(system, rhs, rcond=1.0e-12)
        if rank < count + 1:
            raise ValueError("Shallow-jet augmented BEM system is rank deficient.")
    dipole_coefficient = float(unknown[count])
    potential = np.empty(count, dtype=float)
    normal_derivative = np.empty(count, dtype=float)
    potential[free_mask] = phi_known[free_mask]
    potential[far_mask] = dipole_coefficient * dipole_basis
    potential[neumann_mask] = unknown[:count][neumann_mask]
    normal_derivative[dirichlet_mask] = unknown[:count][dirichlet_mask]
    normal_derivative[neumann_mask] = q_known[neumann_mask]

    identity_residual = h_matrix @ potential - g_matrix @ normal_derivative
    identity_scale = max(
        float(np.linalg.norm(h_matrix @ potential)),
        float(np.linalg.norm(g_matrix @ normal_derivative)),
        1.0e-12,
    )
    flux_residual = float(
        -np.sum(normal_derivative[far_mask] * boundary.panel_length_m[far_mask])
        + dipole_coefficient
        * np.sum(dipole_normal_derivative * boundary.panel_length_m[far_mask])
    )
    solution = MixedBoundarySolution(
        potential_m2_s=potential,
        normal_derivative_m_s=normal_derivative,
        condition_number=float(np.linalg.cond(system)),
        relative_residual=float(np.linalg.norm(identity_residual) / identity_scale),
        max_abs_residual=float(np.max(np.abs(identity_residual))),
        dirichlet_panel_count=int(np.count_nonzero(dirichlet_mask)),
        neumann_panel_count=int(np.count_nonzero(neumann_mask)),
        gauss_order=config.gauss_order,
        status="iafrati_2013_shallow_jet_augmented_bie_diagnostic_unvalidated",
    )
    velocity = _connected_self_similar_boundary_velocity(boundary, solution)
    position = np.column_stack((boundary.panel_mid_y_m, boundary.panel_mid_z_up_m))
    pressure_function = (
        -potential
        + np.sum(position * velocity, axis=1)
        - 0.5 * np.sum(np.square(velocity), axis=1)
    )
    return (
        solution,
        dipole_coefficient,
        flux_residual,
        velocity,
        pressure_function,
        None,
    )


def _connected_self_similar_boundary_velocity(
    boundary: ClosedBoundary2D,
    solution: MixedBoundarySolution,
) -> np.ndarray:
    """Reconstruct velocity across the physically connected jet interfaces.

    The main and shallow body are one differentiable body contour.  Likewise,
    the shallow and outer free surfaces meet at the bulk-flow root, although
    they straddle the last/first panel index of the closed polygon.  Treating
    those labels as separate segments creates artificial one-sided gradients.
    """

    velocity = boundary_velocity(
        boundary,
        solution,
        respect_label_boundaries=True,
    )
    labels = np.asarray(boundary.panel_labels, dtype=object)
    length = boundary.panel_length_m
    potential = solution.potential_m2_s

    def overwrite_tangential(indices: np.ndarray) -> None:
        if len(indices) < 2:
            return
        distance = 0.5 * (length[indices[:-1]] + length[indices[1:]])
        arc = np.concatenate(([0.0], np.cumsum(distance)))
        edge_order = 2 if len(indices) >= 3 else 1
        derivative = np.gradient(
            potential[indices],
            arc,
            edge_order=edge_order,
        )
        velocity[indices] = (
            derivative[:, None] * boundary.panel_tangent[indices]
            + solution.normal_derivative_m_s[indices, None]
            * boundary.panel_normal[indices]
        )

    main_body = np.flatnonzero(labels == "body")
    jet_body = np.flatnonzero(labels == "shallow_jet_body")
    if len(main_body) and len(jet_body):
        overwrite_tangential(np.concatenate((main_body, jet_body)))

    jet_free = np.flatnonzero(labels == "shallow_jet_free_surface")
    outer_free = np.flatnonzero(labels == "outer_free_surface")
    if len(jet_free) and len(outer_free):
        overwrite_tangential(np.concatenate((jet_free, outer_free)))
    return velocity


def _paired_shallow_jet_bie_discretization(
    truncation: SelfSimilarJetTruncationResult,
    *,
    body_tangent: np.ndarray,
    target_panel_count: int | None = None,
    terminal_closure: Literal[
        "legacy_parity",
        "continuous_tip",
    ] = "legacy_parity",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return an even-step jet discretization for Iafrati Section 3.4.

    The source BIE uses two adjacent shallow-water steps per boundary panel.
    ``legacy_parity`` reproduces historical checkpoints. ``continuous_tip``
    always closes the source-bounded unresolved distance and splits it when
    needed so every BIE panel still contains exactly two shallow-water steps.
    """

    body_jet = np.column_stack((truncation.body_node_xi, truncation.body_node_eta))
    free_jet = np.column_stack((truncation.free_node_xi, truncation.free_node_eta))
    s_tau = np.asarray(truncation.jet.s_tau, dtype=float).copy()
    if len(body_jet) < 3 or free_jet.shape != body_jet.shape:
        raise ValueError("The shallow-water march did not resolve a finite jet region.")
    step_count = len(body_jet) - 1
    if terminal_closure not in ("legacy_parity", "continuous_tip"):
        raise ValueError("Unknown shallow-jet terminal closure mode.")
    remaining = float(
        np.clip(
            abs(float(truncation.jet.s_lambda[-1])),
            np.finfo(float).eps,
            float(truncation.root_state.delta_lambda),
        )
    )
    if terminal_closure == "legacy_parity" and not step_count % 2:
        free_jet[-1] = body_jet[-1]
    else:
        terminal_body = body_jet[-1] + remaining * np.asarray(
            body_tangent,
            dtype=float,
        )
        terminal_free = terminal_body.copy()
        terminal_substeps = 1 if step_count % 2 else 2
        fractions = np.linspace(0.0, 1.0, terminal_substeps + 1)[1:]
        body_tail = body_jet[-1] + fractions[:, None] * (
            terminal_body - body_jet[-1]
        )
        free_tail = free_jet[-1] + fractions[:, None] * (
            terminal_free - free_jet[-1]
        )
        tail_arc = np.linalg.norm(
            np.diff(np.vstack((free_jet[-1], free_tail)), axis=0),
            axis=1,
        )
        tail_s_tau = s_tau[-1] + np.cumsum(tail_arc)
        body_jet = np.vstack((body_jet, body_tail))
        free_jet = np.vstack((free_jet, free_tail))
        s_tau = np.concatenate((s_tau, tail_s_tau))
        step_count += terminal_substeps
    if target_panel_count is not None:
        count = int(target_panel_count)
        if count < 2:
            raise ValueError("A fixed shallow-jet BIE topology requires at least two panels.")
        source_lambda = (body_jet - body_jet[0]) @ np.asarray(
            body_tangent,
            dtype=float,
        )
        if np.any(np.diff(source_lambda) <= 0.0):
            raise ValueError("The shallow-jet body coordinate must increase to the tip.")
        target_lambda = np.linspace(source_lambda[0], source_lambda[-1], 2 * count + 1)
        body_jet = np.column_stack(
            tuple(np.interp(target_lambda, source_lambda, body_jet[:, axis]) for axis in range(2))
        )
        free_jet = np.column_stack(
            tuple(np.interp(target_lambda, source_lambda, free_jet[:, axis]) for axis in range(2))
        )
        s_tau = np.interp(target_lambda, source_lambda, s_tau)
        free_jet[-1] = body_jet[-1]
    panel_node_index = np.arange(0, len(body_jet), 2, dtype=int)
    if panel_node_index[-1] != len(body_jet) - 1:
        raise ValueError("The paired shallow-water BIE discretization must end at the jet tip.")
    return body_jet, free_jet, s_tau, panel_node_index


def solve_self_similar_wedge_with_shallow_jet(
    truncation: SelfSimilarJetTruncationResult,
) -> SelfSimilarShallowJetCoupledResult:
    """Include the Eq. (43)--(46) jet panels in the Eq. (29) BIE.

    Two adjacent shallow-water steps define one BIE panel, and the potential
    is assigned at their shared middle node, exactly as specified in Section
    3.4.  The final sub-step thickness is collapsed to zero because the source
    stopping rule bounds the unresolved distance to less than one step.
    """

    config = truncation.config
    outer = truncation.bvp.free_surface
    beta = np.deg2rad(config.deadrise_deg)
    radius = float(config.far_radius)
    root = np.asarray([outer.node_xi[0], outer.node_eta[0]])
    body_root = _project_root_to_wedge(root, beta)

    apex = np.asarray([0.0, -1.0])
    outward_body_tangent = np.asarray([np.cos(beta), np.sin(beta)])
    body_jet, free_jet, jet_s_tau, panel_node_index = (
        _paired_shallow_jet_bie_discretization(
            truncation,
            body_tangent=outward_body_tangent,
            target_panel_count=config.coupled_jet_bie_panel_count,
            terminal_closure=config.coupled_jet_terminal_closure,
        )
    )
    if float(np.dot(body_jet[-1] - body_root, outward_body_tangent)) <= 0.0:
        raise ValueError("The reconstructed jet tip does not lie outward of its bulk-flow root.")
    if float(np.dot(body_jet[-1] - apex, outward_body_tangent)) <= 0.0:
        raise ValueError("The reconstructed shallow-water jet tip crossed the wedge apex.")
    body_jet_panels = body_jet[panel_node_index]
    free_jet_panels = free_jet[panel_node_index]

    coordinates = [np.column_stack((outer.node_xi, outer.node_eta))]
    labels: list[str] = ["outer_free_surface"] * (len(outer.node_xi) - 1)
    far_start_angle = float(np.arctan2(outer.node_eta[-1], outer.node_xi[-1]))
    theta = np.linspace(far_start_angle, -0.5 * np.pi, config.far_field_panels + 1)
    far = np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))
    far[0] = np.asarray([outer.node_xi[-1], outer.node_eta[-1]])
    coordinates.append(far[1:])
    labels.extend(["far_field"] * config.far_field_panels)
    symmetry = np.column_stack(
        (
            np.zeros(config.symmetry_panels + 1),
            np.linspace(-radius, -1.0, config.symmetry_panels + 1),
        )
    )
    coordinates.append(symmetry[1:])
    labels.extend(["symmetry"] * config.symmetry_panels)
    body_fraction = _body_panel_fractions(
        config.body_panels,
        config.body_panel_growth,
    )
    main_body = apex[None, :] + body_fraction[:, None] * (body_root - apex)[None, :]
    coordinates.append(main_body[1:])
    labels.extend(["body"] * config.body_panels)
    body_jet_panels[0] = body_root
    coordinates.append(body_jet_panels[1:])
    labels.extend(["shallow_jet_body"] * (len(body_jet_panels) - 1))
    reversed_free_jet = free_jet_panels[::-1].copy()
    reversed_free_jet[-1] = root
    coordinates.append(reversed_free_jet[1:])
    labels.extend(["shallow_jet_free_surface"] * (len(reversed_free_jet) - 1))
    nodes = np.vstack(coordinates)
    nodes[-1] = nodes[0]
    boundary = ClosedBoundary2D(nodes[:, 0], nodes[:, 1], tuple(labels))

    prescribed_phi = np.full(boundary.panel_count, np.nan, dtype=float)
    prescribed_q = np.full(boundary.panel_count, np.nan, dtype=float)
    prescribed_phi_endpoint = np.full((boundary.panel_count, 2), np.nan, dtype=float)
    prescribed_q_endpoint = np.full((boundary.panel_count, 2), np.nan, dtype=float)
    label_array = np.asarray(boundary.panel_labels, dtype=object)
    outer_mask = label_array == "outer_free_surface"
    shallow_free_mask = label_array == "shallow_jet_free_surface"
    body_mask = (label_array == "body") | (label_array == "shallow_jet_body")
    symmetry_mask = label_array == "symmetry"
    prescribed_phi[outer_mask] = outer.potential
    outer_panel = np.flatnonzero(outer_mask)
    outer_tau = outer.tau_star + outer.arc_length
    outer_node_phi = 0.5 * (
        np.square(outer.node_xi)
        + np.square(outer.node_eta)
        - np.square(outer_tau)
    )
    prescribed_phi_endpoint[outer_panel, 0] = outer_node_phi[:-1]
    prescribed_phi_endpoint[outer_panel, 1] = outer_node_phi[1:]

    shallow_phi_root_to_tip = np.empty(len(panel_node_index) - 1, dtype=float)
    for panel, (start, stop) in enumerate(
        zip(panel_node_index[:-1], panel_node_index[1:])
    ):
        midpoint_position = free_jet[start + 1]
        midpoint_s_tau = jet_s_tau[start + 1]
        shallow_phi_root_to_tip[panel] = 0.5 * (
            float(np.dot(midpoint_position, midpoint_position))
            - float(midpoint_s_tau) ** 2
        )
    prescribed_phi[shallow_free_mask] = shallow_phi_root_to_tip[::-1]
    shallow_node_position = free_jet[panel_node_index]
    shallow_node_s_tau = jet_s_tau[panel_node_index]
    shallow_node_phi_root_to_tip = 0.5 * (
        np.sum(np.square(shallow_node_position), axis=1)
        - np.square(shallow_node_s_tau)
    )
    shallow_node_phi_boundary = shallow_node_phi_root_to_tip[::-1]
    shallow_panel = np.flatnonzero(shallow_free_mask)
    prescribed_phi_endpoint[shallow_panel, 0] = shallow_node_phi_boundary[:-1]
    prescribed_phi_endpoint[shallow_panel, 1] = shallow_node_phi_boundary[1:]
    prescribed_q[body_mask] = -np.cos(beta)
    prescribed_q[symmetry_mask] = 0.0
    prescribed_q_endpoint[body_mask] = -np.cos(beta)
    prescribed_q_endpoint[symmetry_mask] = 0.0
    (
        solution,
        dipole,
        flux,
        panel_velocity,
        pressure_function,
        solved_q_endpoint,
    ) = _solve_augmented_self_similar_boundary(
        config,
        boundary,
        prescribed_phi,
        prescribed_q,
        prescribed_potential_endpoint=prescribed_phi_endpoint,
        prescribed_normal_derivative_endpoint=prescribed_q_endpoint,
    )
    if dipole <= 0.0:
        raise ValueError(
            "The coupled wedge-entry solution produced a non-positive far-field "
            "dipole coefficient: "
            f"C_D={dipole:.12g}, condition_number={solution.condition_number:.12g}, "
            f"relative_residual={solution.relative_residual:.12g}."
        )

    position = np.column_stack((boundary.panel_mid_y_m, boundary.panel_mid_z_up_m))
    outer_residual = solution.normal_derivative_m_s[outer_mask] - np.sum(
        position[outer_mask] * boundary.panel_normal[outer_mask],
        axis=1,
    )
    outer_scale = np.maximum(
        1.0,
        np.abs(np.sum(position[outer_mask] * boundary.panel_normal[outer_mask], axis=1)),
    )
    outer_residual_endpoint: np.ndarray | None = None
    if solved_q_endpoint is not None:
        endpoint_position = np.stack(
            (
                np.column_stack((boundary.node_y_m[:-1], boundary.node_z_up_m[:-1])),
                np.column_stack((boundary.node_y_m[1:], boundary.node_z_up_m[1:])),
            ),
            axis=1,
        )
        endpoint_normal_velocity = np.sum(
            endpoint_position * boundary.panel_normal[:, None, :],
            axis=2,
        )
        outer_residual_endpoint = (
            solved_q_endpoint[outer_mask] - endpoint_normal_velocity[outer_mask]
        )
    body_pressure = 2.0 * pressure_function[body_mask]
    vertical_force = float(
        np.sum(
            body_pressure
            * boundary.panel_normal[body_mask, 1]
            * boundary.panel_length_m[body_mask]
        )
    )
    return SelfSimilarShallowJetCoupledResult(
        config=config,
        boundary=boundary,
        solution=solution,
        panel_velocity=panel_velocity,
        outer_free_surface=outer,
        jet_interface=truncation,
        dipole_coefficient=dipole,
        flux_residual=flux,
        outer_kinematic_residual=outer_residual,
        scaled_outer_kinematic_residual=outer_residual / outer_scale,
        body_pressure_coefficient=body_pressure,
        body_vertical_force_coefficient=vertical_force,
        outer_kinematic_residual_endpoint=outer_residual_endpoint,
        normal_derivative_endpoint=solved_q_endpoint,
    )


def derive_shallow_water_jet_root_state_from_coupled(
    coupled: SelfSimilarShallowJetCoupledResult,
) -> ShallowWaterJetRootState:
    """Recover the bulk-flow root limit from adjacent shallow-body panels.

    Panel velocities live at panel midpoints, while the matching state belongs
    at the root node. A one-sided quadratic extrapolation through the first
    three midpoint values recovers that root limit on the smooth body segment
    without inserting benchmark information.
    """

    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    jet_body_index = np.flatnonzero(labels == "shallow_jet_body")
    outer_index = np.flatnonzero(labels == "outer_free_surface")
    if len(jet_body_index) < 2 or len(outer_index) < 2:
        raise ValueError("The coupled BIE does not resolve the shallow root and outer surface.")
    velocity = coupled.panel_velocity
    recovery = coupled.config.coupled_root_state_recovery
    root_panels = (
        jet_body_index[:1]
        if recovery == "first_panel_midpoint"
        else jet_body_index[:3]
    )
    if recovery == "quadratic_root_extrapolation" and len(root_panels) < 3:
        raise ValueError("Quadratic root recovery requires three shallow-body panels.")
    position = np.column_stack(
        (
            coupled.boundary.panel_mid_y_m[root_panels],
            coupled.boundary.panel_mid_z_up_m[root_panels],
        )
    )
    beta = np.deg2rad(coupled.config.deadrise_deg)
    tangent = np.asarray([np.cos(beta), np.sin(beta)])
    free_root = np.asarray(
        [
            coupled.outer_free_surface.node_xi[0],
            coupled.outer_free_surface.node_eta[0],
        ]
    )
    body_root = _project_root_to_wedge(free_root, beta)
    root_distance = (position - body_root) @ tangent
    midpoint_s_lambda = np.sum(
        (velocity[root_panels] - position) * tangent[None, :],
        axis=1,
    )
    if np.any(root_distance <= 0.0) or np.any(np.diff(root_distance) <= 0.0):
        raise ValueError("The shallow-body root panels are not outward ordered.")
    if recovery == "first_panel_midpoint":
        s_lambda = float(midpoint_s_lambda[0])
    else:
        weights = np.empty(3, dtype=float)
        for index in range(3):
            others = np.delete(root_distance, index)
            weights[index] = float(
                np.prod(-others) / np.prod(root_distance[index] - others)
            )
        s_lambda = float(np.dot(weights, midpoint_s_lambda))
    return ShallowWaterJetRootState(
        thickness=coupled.jet_interface.root_state.thickness,
        s_lambda=s_lambda,
        s_tau=-float(coupled.outer_free_surface.tau_star),
        delta_lambda=0.5
        * float(coupled.boundary.panel_length_m[int(outer_index[0])]),
        lambda_tangent=tangent,
    )


def rebuild_shallow_jet_from_coupled_root(
    coupled: SelfSimilarShallowJetCoupledResult,
    *,
    s_lambda_override: float | None = None,
) -> SelfSimilarJetTruncationResult:
    """Remarch Eqs. (43)--(46) from root data supplied by the full BIE."""

    root_state = derive_shallow_water_jet_root_state_from_coupled(coupled)
    if s_lambda_override is not None:
        root_state = replace(root_state, s_lambda=float(s_lambda_override))
    jet = march_iafrati_shallow_water_jet(
        initial_thickness=root_state.thickness,
        initial_s_lambda=root_state.s_lambda,
        initial_s_tau=root_state.s_tau,
        delta_lambda=root_state.delta_lambda,
        maximum_points=coupled.config.shallow_jet_maximum_points,
    )
    free_root = np.asarray(
        [
            coupled.outer_free_surface.node_xi[0],
            coupled.outer_free_surface.node_eta[0],
        ]
    )
    beta = np.deg2rad(coupled.config.deadrise_deg)
    body_root = _project_root_to_wedge(free_root, beta)
    fluid_normal = (free_root - body_root) / root_state.thickness
    body_nodes = (
        body_root[None, :]
        + jet.lambda_coordinate[:, None] * root_state.lambda_tangent[None, :]
    )
    free_nodes = body_nodes + jet.thickness[:, None] * fluid_normal[None, :]
    free_nodes[0] = free_root
    return SelfSimilarJetTruncationResult(
        config=coupled.config,
        bvp=coupled.jet_interface.bvp,
        root_state=root_state,
        jet=jet,
        original_cut_node_index=coupled.jet_interface.original_cut_node_index,
        cut_angle_deg=coupled.jet_interface.cut_angle_deg,
        body_node_xi=body_nodes[:, 0],
        body_node_eta=body_nodes[:, 1],
        free_node_xi=free_nodes[:, 0],
        free_node_eta=free_nodes[:, 1],
    )


def iterate_shallow_jet_root_coupling(
    initial: SelfSimilarShallowJetCoupledResult,
    *,
    maximum_iterations: int = 8,
    relative_tolerance: float = 1.0e-3,
    relaxation: float = 0.5,
) -> SelfSimilarJetRootIterationResult:
    """Solve the scalar outer-BIE/shallow-jet root compatibility equation.

    For a supplied shallow-jet root velocity ``s``, the augmented BIE returns
    a measured velocity ``F(s)``.  The matching condition is ``F(s)-s=0``.
    A damped fixed-point step starts the search; subsequent steps use a
    safeguarded secant update, while a sign-changing pair brackets the root.
    Trials outside the physical shallow-water domain are backed toward the
    last valid state rather than clipped.
    """

    if int(maximum_iterations) < 1 or float(relative_tolerance) <= 0.0:
        raise ValueError("Root iteration limits and tolerance must be positive.")
    if not 0.0 < float(relaxation) <= 1.0:
        raise ValueError("Root iteration relaxation must lie in (0, 1].")
    base = initial
    coupled = initial
    supplied = float(coupled.jet_interface.root_state.s_lambda)
    measured = float(derive_shallow_water_jet_root_state_from_coupled(coupled).s_lambda)
    if measured <= 0.0:
        raise ValueError("The full BIE produced S_lambda<=0 at the shallow root.")

    history = [supplied]
    measured_history = [measured]
    residual_history = [measured - supplied]
    mismatch_history = [
        abs(residual_history[-1]) / max(abs(supplied), np.finfo(float).eps)
    ]
    changes = [0.0]
    converged = mismatch_history[-1] <= float(relative_tolerance)

    no_physical_bracket = False
    for _ in range(int(maximum_iterations)):
        if converged:
            break
        current = history[-1]
        current_residual = residual_history[-1]
        negative = [
            (value, residual)
            for value, residual in zip(history, residual_history)
            if residual < 0.0
        ]
        positive = [
            (value, residual)
            for value, residual in zip(history, residual_history)
            if residual > 0.0
        ]
        if negative and positive:
            lower = max(positive, key=lambda item: item[0])
            upper = min(negative, key=lambda item: item[0])
            if lower[0] > upper[0]:
                lower, upper = upper, lower
            denominator = upper[1] - lower[1]
            trial = (
                0.5 * (lower[0] + upper[0])
                if abs(denominator) <= np.finfo(float).eps
                else lower[0]
                - lower[1] * (upper[0] - lower[0]) / denominator
            )
            span = upper[0] - lower[0]
            trial = float(
                np.clip(
                    trial,
                    lower[0] + 0.05 * span,
                    upper[0] - 0.05 * span,
                )
            )
        elif len(history) >= 2:
            previous = history[-2]
            previous_residual = residual_history[-2]
            denominator = current_residual - previous_residual
            if abs(denominator) > np.finfo(float).eps:
                trial = current - current_residual * (current - previous) / denominator
            else:
                trial = current + float(relaxation) * current_residual
            if trial <= 0.0 or abs(trial - current) > max(abs(current), 1.0):
                trial = current + float(relaxation) * current_residual
        else:
            trial = current + float(relaxation) * current_residual
        trial = max(float(trial), np.finfo(float).eps)

        physical_boundary_hit = False
        try:
            interface = rebuild_shallow_jet_from_coupled_root(
                base,
                s_lambda_override=trial,
            )
        except ValueError as error:
            if "shallow-water root state has no physical first-step solution" not in str(error):
                raise
            physical_boundary_hit = True
            valid_value = current
            invalid_value = trial
            valid_interface = rebuild_shallow_jet_from_coupled_root(
                base,
                s_lambda_override=valid_value,
            )
            for _ in range(20):
                middle = 0.5 * (valid_value + invalid_value)
                try:
                    middle_interface = rebuild_shallow_jet_from_coupled_root(
                        base,
                        s_lambda_override=middle,
                    )
                except ValueError as middle_error:
                    if (
                        "shallow-water root state has no physical first-step solution"
                        not in str(middle_error)
                    ):
                        raise
                    invalid_value = middle
                else:
                    valid_value = middle
                    valid_interface = middle_interface
            trial = valid_value
            interface = valid_interface
        trial_coupled = solve_self_similar_wedge_with_shallow_jet(interface)

        trial_measured = float(
            derive_shallow_water_jet_root_state_from_coupled(trial_coupled).s_lambda
        )
        if trial_measured <= 0.0:
            raise ValueError("The full BIE produced S_lambda<=0 at the shallow root.")
        trial_residual = trial_measured - trial
        relative_change = abs(trial - current) / max(
            abs(current), np.finfo(float).eps
        )
        relative_mismatch = abs(trial_residual) / max(
            abs(trial), np.finfo(float).eps
        )
        coupled = trial_coupled
        history.append(trial)
        measured_history.append(trial_measured)
        residual_history.append(trial_residual)
        mismatch_history.append(relative_mismatch)
        changes.append(relative_change)
        converged = relative_mismatch <= float(relative_tolerance)
        if (
            physical_boundary_hit
            and not converged
            and np.sign(trial_residual) == np.sign(current_residual)
        ):
            no_physical_bracket = True
            break
    termination_reason: Literal[
        "ROOT_CONSISTENT",
        "MAXIMUM_ITERATIONS",
        "NO_BRACKET_IN_PHYSICAL_DOMAIN",
    ]
    if converged:
        termination_reason = "ROOT_CONSISTENT"
    elif no_physical_bracket:
        termination_reason = "NO_BRACKET_IN_PHYSICAL_DOMAIN"
    else:
        termination_reason = "MAXIMUM_ITERATIONS"
    return SelfSimilarJetRootIterationResult(
        coupled=coupled,
        s_lambda_history=np.asarray(history),
        measured_s_lambda_history=np.asarray(measured_history),
        relative_mismatch_history=np.asarray(mismatch_history),
        relative_change_history=np.asarray(changes),
        converged=converged,
        termination_reason=termination_reason,
    )


def _continuous_normal_shape_velocity(
    panel_length: np.ndarray,
    panel_tangent: np.ndarray,
    panel_normal: np.ndarray,
    residual_endpoint: np.ndarray,
) -> np.ndarray:
    """Project discontinuous panel ``S_nu`` onto a continuous normal field.

    Tangential pseudo velocity is a free curve-parameterization choice. This
    constrained vector L2 projection therefore retains only shape-changing
    normal motion, while the existing arc-length regrid controls node spacing.
    """

    length = np.asarray(panel_length, dtype=float)
    tangent = np.asarray(panel_tangent, dtype=float)
    normal = np.asarray(panel_normal, dtype=float)
    residual = np.asarray(residual_endpoint, dtype=float)
    panel_count = len(length)
    if (
        tangent.shape != (panel_count, 2)
        or normal.shape != (panel_count, 2)
        or residual.shape != (panel_count, 2)
    ):
        raise ValueError(
            "Continuous-normal projection arrays have inconsistent shapes."
        )
    if not all(
        np.isfinite(item).all() for item in (length, tangent, normal, residual)
    ) or np.any(length <= 0.0):
        raise ValueError(
            "Continuous-normal projection requires finite, positive panels."
        )

    node_normal = np.empty((panel_count + 1, 2), dtype=float)
    node_normal[[0, -1]] = normal[[0, -1]]
    node_normal[1:-1] = normal[:-1] + normal[1:]
    node_normal_norm = np.linalg.norm(node_normal, axis=1)
    if np.any(node_normal_norm <= np.finfo(float).eps):
        raise ValueError(
            "Continuous-normal projection found an undefined normal at a fold."
        )
    node_normal /= node_normal_norm[:, None]

    mass = np.zeros((panel_count + 1, panel_count + 1), dtype=float)
    load = np.zeros(panel_count + 1, dtype=float)
    for panel in range(panel_count):
        left = panel
        right = panel + 1
        local_length = float(length[panel])
        normal_dot = float(np.dot(node_normal[left], node_normal[right]))
        mass[left, left] += local_length / 3.0
        mass[right, right] += local_length / 3.0
        mass[left, right] += local_length * normal_dot / 6.0
        mass[right, left] += local_length * normal_dot / 6.0
        left_projection = float(np.dot(node_normal[left], normal[panel]))
        right_projection = float(np.dot(node_normal[right], normal[panel]))
        load[left] += (
            local_length
            * (2.0 * residual[panel, 0] + residual[panel, 1])
            * left_projection
            / 6.0
        )
        load[right] += (
            local_length
            * (residual[panel, 0] + 2.0 * residual[panel, 1])
            * right_projection
            / 6.0
        )
    try:
        normal_speed = np.linalg.solve(mass, load)
    except np.linalg.LinAlgError as error:
        raise ValueError(
            "Continuous-normal projection mass matrix is singular."
        ) from error
    velocity = normal_speed[:, None] * node_normal
    if not np.isfinite(velocity).all():
        raise ValueError("Continuous-normal projection produced non-finite velocity.")
    return velocity


def _panel_length_pseudo_time_scale(
    panel_length: np.ndarray,
    maximum_ratio: float,
) -> np.ndarray:
    """Return a positive local pseudo-time preconditioner for free-surface nodes.

    Multiplying ``grad(S)`` by this strictly positive scale preserves the
    stationary normal condition ``S_nu=0``.  The scale only reduces the severe
    relaxation-rate disparity between the tiny jet-root panels and the much
    larger far-field panels; the existing panel-relative CFL remains the hard
    displacement bound.
    """

    length = np.asarray(panel_length, dtype=float)
    limit = float(maximum_ratio)
    if (
        length.ndim != 1
        or len(length) == 0
        or not np.isfinite(length).all()
        or np.any(length <= 0.0)
    ):
        raise ValueError("Pseudo-time preconditioning requires positive panel lengths.")
    if not np.isfinite(limit) or limit < 1.0:
        raise ValueError("Pseudo-time preconditioner maximum ratio must be at least one.")
    local = np.empty(len(length) + 1, dtype=float)
    local[[0, -1]] = length[[0, -1]]
    local[1:-1] = np.minimum(length[:-1], length[1:])
    reference = float(np.min(local))
    return np.clip(local / reference, 1.0, limit)


def _coupled_outer_pseudo_velocity(
    coupled: SelfSimilarShallowJetCoupledResult,
) -> np.ndarray:
    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    outer_index = np.flatnonzero(labels == "outer_free_surface")
    if coupled.config.coupled_free_surface_update == "continuous_normal":
        if coupled.outer_kinematic_residual_endpoint is None:
            raise ValueError(
                "continuous_normal free-surface updates require endpoint S_nu data."
            )
        node_velocity = _continuous_normal_shape_velocity(
            coupled.boundary.panel_length_m[outer_index],
            coupled.boundary.panel_tangent[outer_index],
            coupled.boundary.panel_normal[outer_index],
            coupled.outer_kinematic_residual_endpoint,
        )
    else:
        jet_free_index = np.flatnonzero(labels == "shallow_jet_free_surface")
        velocity = coupled.panel_velocity
        midpoint = np.column_stack(
            (
                coupled.boundary.panel_mid_y_m,
                coupled.boundary.panel_mid_z_up_m,
            )
        )
        all_panel_gradient = velocity - midpoint
        panel_gradient = all_panel_gradient[outer_index]
        panel_length = coupled.boundary.panel_length_m[outer_index]
        node_gradient = np.empty((len(panel_gradient) + 1, 2), dtype=float)
        if (
            coupled.config.coupled_linear_cusp_velocity_recovery
            == "split_outer_side"
            and coupled.normal_derivative_endpoint is not None
        ):
            root_outer_panel = int(outer_index[0])
            outer = coupled.outer_free_surface
            outer_tau = outer.tau_star + outer.arc_length
            outer_node_phi = 0.5 * (
                np.square(outer.node_xi)
                + np.square(outer.node_eta)
                - np.square(outer_tau)
            )
            tangential_derivative = float(
                (outer_node_phi[1] - outer_node_phi[0])
                / coupled.boundary.panel_length_m[root_outer_panel]
            )
            root_velocity = (
                tangential_derivative
                * coupled.boundary.panel_tangent[root_outer_panel]
                + coupled.normal_derivative_endpoint[root_outer_panel, 0]
                * coupled.boundary.panel_normal[root_outer_panel]
            )
            root_position = np.asarray([outer.node_xi[0], outer.node_eta[0]])
            node_gradient[0] = root_velocity - root_position
        elif len(jet_free_index):
            root_jet_panel = int(jet_free_index[-1])
            root_outer_panel = int(outer_index[0])
            jet_length = float(coupled.boundary.panel_length_m[root_jet_panel])
            outer_length = float(coupled.boundary.panel_length_m[root_outer_panel])
            node_gradient[0] = (
                outer_length * all_panel_gradient[root_jet_panel]
                + jet_length * all_panel_gradient[root_outer_panel]
            ) / (jet_length + outer_length)
        else:
            node_gradient[0] = panel_gradient[0]
        node_gradient[-1] = panel_gradient[-1]
        denominator = panel_length[:-1] + panel_length[1:]
        node_gradient[1:-1] = (
            panel_length[1:, None] * panel_gradient[:-1]
            + panel_length[:-1, None] * panel_gradient[1:]
        ) / denominator[:, None]
        node_velocity = node_gradient
    if coupled.config.coupled_pseudo_time_preconditioner == "panel_length":
        scale = _panel_length_pseudo_time_scale(
            coupled.boundary.panel_length_m[outer_index],
            coupled.config.coupled_pseudo_time_preconditioner_max_ratio,
        )
        node_velocity = node_velocity * scale[:, None]
    return node_velocity


def _constrain_coupled_outer_nodes(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
    *,
    allow_reversed_root: bool = False,
) -> np.ndarray:
    constrained = np.asarray(nodes, dtype=float).copy()
    far_norm = float(np.linalg.norm(constrained[-1]))
    if far_norm <= np.finfo(float).eps or constrained[-1, 0] <= 0.0:
        raise ValueError("Coupled pseudo-time far node left the right far-field semicircle.")
    constrained[-1] *= float(config.far_radius) / far_norm
    beta = np.deg2rad(config.deadrise_deg)
    body_root = _project_root_to_wedge(constrained[0], beta)
    thickness = float(np.linalg.norm(constrained[0] - body_root))
    if thickness <= 1.0e-10:
        raise ValueError("Coupled pseudo-time collapsed the finite shallow-jet root thickness.")
    if body_root[1] < -1.0e-10:
        raise ValueError("Coupled pseudo-time moved the shallow-jet root below eta=0.")
    return constrained


def _trim_shallow_angle_coupled_root_panels(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> np.ndarray:
    """Move the bulk/jet interface continuously to the angle threshold.

    The matching surface is defined by a physical angle criterion, not by a
    particular mesh node.  Snapping it to the first resolved node injects a
    panel-sized jump whenever the leading angle crosses the threshold.  The
    crossing is therefore interpolated between adjacent panel centroids and
    mapped back to the polygonal free-surface arc.
    """

    coordinates = np.asarray(nodes, dtype=float)
    beta = np.deg2rad(config.deadrise_deg)
    body_tangent = np.asarray([np.cos(beta), np.sin(beta)])
    segment = np.diff(coordinates, axis=0)
    segment_length = np.linalg.norm(segment, axis=1)
    if np.any(segment_length <= 1.0e-12):
        raise ValueError("Shallow-angle interface transfer found a zero-length panel.")
    unit = segment / segment_length[:, None]
    angle = np.rad2deg(
        np.arccos(np.clip(unit @ body_tangent, -1.0, 1.0))
    )
    threshold = float(config.jet_angle_threshold_deg)
    if angle[0] >= threshold:
        return coordinates
    resolved = np.flatnonzero(angle >= threshold)
    resolved = resolved[(resolved >= 1) & (resolved <= len(coordinates) - 5)]
    if len(resolved) == 0:
        raise ValueError(
            "No resolved bulk free-surface panel remains beyond the shallow-angle jet."
        )
    upper = int(resolved[0])
    lower = upper - 1
    denominator = float(angle[upper] - angle[lower])
    fraction = (
        1.0
        if abs(denominator) <= np.finfo(float).eps
        else float(np.clip((threshold - angle[lower]) / denominator, 0.0, 1.0))
    )
    node_arc = np.concatenate(([0.0], np.cumsum(segment_length)))
    panel_mid_arc = 0.5 * (node_arc[:-1] + node_arc[1:])
    crossing_arc = float(
        panel_mid_arc[lower]
        + fraction * (panel_mid_arc[upper] - panel_mid_arc[lower])
    )
    crossing_panel = int(np.searchsorted(node_arc, crossing_arc, side="right") - 1)
    crossing_panel = int(np.clip(crossing_panel, 0, len(segment_length) - 1))
    local_fraction = float(
        (crossing_arc - node_arc[crossing_panel])
        / segment_length[crossing_panel]
    )
    new_root = coordinates[crossing_panel] + local_fraction * segment[crossing_panel]
    tail_start = crossing_panel + 1
    retained = np.vstack((new_root, coordinates[tail_start:]))
    if len(retained) < 5:
        raise ValueError(
            "Angle-interpolated matching surface left too few outer free-surface nodes."
        )
    return retained


def _maximum_coupled_outer_turn_deg(nodes: np.ndarray) -> float:
    coordinates = np.asarray(nodes, dtype=float)
    segment = np.diff(coordinates, axis=0)
    if len(segment) < 2 or np.any(np.linalg.norm(segment, axis=1) <= 1.0e-12):
        raise ValueError("Free-surface turning requires at least two finite panels.")
    angle = np.unwrap(np.arctan2(segment[:, 1], segment[:, 0]))
    return float(np.max(np.abs(np.rad2deg(np.diff(angle)))))


def _smooth_oscillatory_coupled_outer_nodes(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> np.ndarray:
    """Remove unresolved panel-scale turning while fixing both curve endpoints."""

    coordinates = np.asarray(nodes, dtype=float)
    if not config.coupled_smoothing_enabled:
        return coordinates
    local_node_count = min(
        len(coordinates),
        int(config.coupled_smoothing_root_panels) + 1,
    )
    local = coordinates[:local_node_count]
    threshold = float(config.coupled_smoothing_turn_threshold_deg)
    if len(local) < 6 or _maximum_coupled_outer_turn_deg(local) <= threshold:
        return coordinates
    panel_length = np.linalg.norm(np.diff(local, axis=0), axis=1)
    arc = np.concatenate(([0.0], np.cumsum(panel_length)))
    weight = np.ones(len(local), dtype=float)
    weight[[0, -1]] = 1.0e6
    smoothed_local = np.column_stack(
        (
            make_smoothing_spline(arc, local[:, 0], w=weight)(arc),
            make_smoothing_spline(arc, local[:, 1], w=weight)(arc),
        )
    )
    smoothed_local[[0, -1]] = local[[0, -1]]
    local_length = np.concatenate(
        (
            [panel_length[0]],
            np.minimum(panel_length[:-1], panel_length[1:]),
            [panel_length[-1]],
        )
    )
    displacement_ratio = np.linalg.norm(smoothed_local - local, axis=1) / local_length
    maximum_ratio = float(np.max(displacement_ratio))
    limit = float(config.coupled_smoothing_max_local_displacement)
    if maximum_ratio > limit:
        smoothed_local = local + (limit / maximum_ratio) * (smoothed_local - local)
        smoothed_local[[0, -1]] = local[[0, -1]]
    smoothed = coordinates.copy()
    smoothed[:local_node_count] = smoothed_local
    return smoothed


def _reconstruct_coupled_root_nodes(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> np.ndarray:
    """Refine the root arc while preserving its endpoints and outer tail.

    Sun's regridding procedure uses polygonal arc length as the cubic-spline
    parameter and redistributes nodes on equal or geometrically increasing
    arcs.  Here the first target arc is set by the local shallow-jet thickness
    so the adjacent BIE panel remains of comparable size.  Only the declared
    root interval is redistributed; its root, local anchor, and all nodes
    beyond the anchor are unchanged.  The caller subsequently rebuilds the
    Iafrati Eq. (34) potential from the reconstructed arc.
    """

    coordinates = np.asarray(nodes, dtype=float)
    if not config.coupled_root_reconstruction_enabled:
        return coordinates
    original_panel_count = min(
        int(config.coupled_root_reconstruction_panels),
        len(coordinates) - 2,
    )
    if original_panel_count < 4:
        return coordinates
    target_ratio = float(config.jet_interface_target_thickness_panel_ratio)

    beta = np.deg2rad(config.deadrise_deg)
    body_root = _project_root_to_wedge(coordinates[0], beta)
    thickness = float(np.linalg.norm(coordinates[0] - body_root))
    local = coordinates[: original_panel_count + 1]
    panel_length = np.linalg.norm(np.diff(local, axis=0), axis=1)
    if np.any(panel_length <= 1.0e-12):
        raise ValueError("Root reconstruction encountered a zero-length panel.")
    arc = np.concatenate(([0.0], np.cumsum(panel_length)))
    local_length = float(arc[-1])
    refined_panel_count = (
        original_panel_count
        + int(config.coupled_root_reconstruction_added_panels)
    )
    first_target = min(
        thickness / target_ratio,
        local_length / refined_panel_count,
    )
    if first_target <= 1.0e-12:
        raise ValueError("Root reconstruction requires a finite first target arc.")

    powers = np.arange(refined_panel_count, dtype=float)

    def arc_balance(growth: float) -> float:
        return float(first_target * np.sum(np.power(growth, powers)) - local_length)

    upper = max(1.01, float(config.free_surface_panel_growth))
    while arc_balance(upper) < 0.0 and upper < 8.0:
        upper *= 1.5
    if arc_balance(upper) < 0.0:
        return coordinates
    growth = float(brentq(arc_balance, 1.0, upper, xtol=1.0e-13, rtol=1.0e-13))
    target_panel_length = first_target * np.power(growth, powers)
    target_panel_length *= local_length / float(np.sum(target_panel_length))
    target_arc = np.concatenate(([0.0], np.cumsum(target_panel_length)))
    reconstructed_local = np.column_stack(
        (
            CubicSpline(arc, local[:, 0], bc_type="natural")(target_arc),
            CubicSpline(arc, local[:, 1], bc_type="natural")(target_arc),
        )
    )
    reconstructed_local[[0, -1]] = local[[0, -1]]
    reconstructed = np.vstack(
        (
            reconstructed_local,
            coordinates[original_panel_count + 1 :],
        )
    )
    return _constrain_coupled_outer_nodes(config, reconstructed)


def _coupled_jet_interface_resolution_ratio(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> float:
    """Return local jet thickness divided by the adjacent outer-panel size.

    Iafrati Section 3.3 requires boundary-integral panels in the thin layer to
    have dimensions comparable with the local jet thickness.  Values much
    below one identify a segment that belongs in the shallow-water region,
    rather than in the bulk-flow boundary-integral discretization.
    """

    coordinates = np.asarray(nodes, dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 2 or len(coordinates) < 2:
        raise ValueError("Jet-interface resolution requires at least two planar nodes.")
    first_panel_length = float(np.linalg.norm(coordinates[1] - coordinates[0]))
    if first_panel_length <= 1.0e-12:
        raise ValueError("Jet-interface resolution encountered a zero-length first panel.")
    beta = np.deg2rad(config.deadrise_deg)
    body_root = _project_root_to_wedge(coordinates[0], beta)
    thickness = float(np.linalg.norm(coordinates[0] - body_root))
    return thickness / first_panel_length


def _resample_coupled_outer_nodes(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> np.ndarray:
    segment = np.linalg.norm(np.diff(nodes, axis=0), axis=1)
    if np.any(segment <= 1.0e-12):
        raise ValueError("Coupled pseudo-time produced a zero-length outer panel.")
    arc = np.concatenate(([0.0], np.cumsum(segment)))
    target = arc[-1] * _outer_panel_fractions(config)
    regridded = np.column_stack(
        (
            CubicSpline(arc, nodes[:, 0], bc_type="natural")(target),
            CubicSpline(arc, nodes[:, 1], bc_type="natural")(target),
        )
    )
    regridded[0] = nodes[0]
    regridded[-1] = nodes[-1]
    return _constrain_coupled_outer_nodes(config, regridded)


def _relocate_underresolved_coupled_jet_interface(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> np.ndarray:
    """Transfer unresolved root panels from the outer BIE to the jet model.

    The interface is a numerical matching surface, not a material marker.  If
    its thickness is less than half the adjacent panel size, the root is moved
    along the current outer free surface to the first interpolated location at
    which thickness and local panel size are comparable.  The fixed 0.5/1.0
    hysteresis is declared in the configuration and never inferred from a
    pressure or response benchmark.
    """

    relocated = np.asarray(nodes, dtype=float).copy()
    minimum_ratio = float(config.jet_interface_min_thickness_panel_ratio)
    target_ratio = float(config.jet_interface_target_thickness_panel_ratio)
    beta = np.deg2rad(config.deadrise_deg)

    for _ in range(4):
        if _coupled_jet_interface_resolution_ratio(config, relocated) >= minimum_ratio:
            return relocated
        panel_length = np.linalg.norm(np.diff(relocated, axis=0), axis=1)
        body_projection = np.asarray(
            [_project_root_to_wedge(point, beta) for point in relocated[:-1]]
        )
        thickness = np.linalg.norm(relocated[:-1] - body_projection, axis=1)
        node_ratio = thickness / panel_length
        trial_target = target_ratio
        candidate: np.ndarray | None = None
        for _ in range(12):
            eligible = np.flatnonzero(node_ratio >= trial_target)
            eligible = eligible[eligible <= len(relocated) - 5]
            if len(eligible) == 0:
                trial_target = 0.5 * (trial_target + minimum_ratio)
                continue
            upper = int(eligible[0])
            if upper == 0:
                return relocated
            lower = upper - 1
            denominator = float(node_ratio[upper] - node_ratio[lower])
            fraction = (
                1.0
                if abs(denominator) <= np.finfo(float).eps
                else float(
                    np.clip(
                        (trial_target - node_ratio[lower]) / denominator,
                        0.0,
                        1.0,
                    )
                )
            )
            new_root = relocated[lower] + fraction * (
                relocated[upper] - relocated[lower]
            )
            tail_start = upper + 1 if fraction >= 1.0 - 1.0e-12 else upper
            retained = np.vstack((new_root, relocated[tail_start:]))
            try:
                candidate = _resample_coupled_outer_nodes(config, retained)
            except ValueError as error:
                if "reversed the first bulk" not in str(error):
                    raise
                trial_target = 0.5 * (trial_target + minimum_ratio)
                continue
            break
        if candidate is None:
            discrete = np.flatnonzero(node_ratio >= minimum_ratio)
            discrete = discrete[
                (discrete >= 1) & (discrete <= len(relocated) - 5)
            ]
            for root_index in discrete:
                try:
                    candidate = _resample_coupled_outer_nodes(
                        config,
                        relocated[int(root_index) :],
                    )
                except ValueError as error:
                    if "reversed the first bulk" not in str(error):
                        raise
                    continue
                if (
                    _coupled_jet_interface_resolution_ratio(config, candidate)
                    >= minimum_ratio
                ):
                    break
                candidate = None
        if candidate is None:
            raise ValueError(
                "No topology-preserving interpolated or discrete outer free-surface "
                "location remains for adaptive shallow-jet interface relocation."
            )
        relocated = candidate
    if _coupled_jet_interface_resolution_ratio(config, relocated) < minimum_ratio:
        raise ValueError(
            "Adaptive shallow-jet interface relocation did not resolve the BIE root."
        )
    return relocated


def _regrid_coupled_outer_nodes(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
) -> np.ndarray:
    constrained = _constrain_coupled_outer_nodes(
        config,
        nodes,
        allow_reversed_root=True,
    )
    # Iafrati's truncation criterion constrains the finite angle between the
    # body and the bulk free surface, not the sign of its body-tangent
    # projection.  Deleting panels at a 90-degree crossing creates a discrete
    # matching-surface jump and is therefore not part of the source method.
    resolved = _trim_shallow_angle_coupled_root_panels(config, constrained)
    smoothed = _smooth_oscillatory_coupled_outer_nodes(config, resolved)
    regridded = _resample_coupled_outer_nodes(config, smoothed)
    reconstructed = _reconstruct_coupled_root_nodes(config, regridded)
    relocated = _relocate_underresolved_coupled_jet_interface(config, reconstructed)
    if config.coupled_root_reconstruction_enabled and len(relocated) == len(regridded):
        relocated = _reconstruct_coupled_root_nodes(config, relocated)
    return relocated


def _build_coupled_solution_from_outer_nodes(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
    far_dipole_coefficient: float,
    *,
    root_inner_iterations: int,
    s_lambda_seed: float | None = None,
) -> SelfSimilarShallowJetCoupledResult:
    if config.jet_closure != "truncated_control":
        raise ValueError("Repeated shallow-jet coupling requires truncated_control config.")
    outer = build_self_similar_free_surface_from_nodes(
        config,
        nodes[:, 0],
        nodes[:, 1],
        far_dipole_coefficient=far_dipole_coefficient,
    )
    outer_bvp = solve_self_similar_wedge_bvp_for_free_surface(config, outer)
    beta = np.deg2rad(config.deadrise_deg)
    body_tangent = np.asarray([np.cos(beta), np.sin(beta)])
    first_tangent = nodes[1] - nodes[0]
    first_tangent /= np.linalg.norm(first_tangent)
    angle = float(
        np.rad2deg(
            np.arccos(np.clip(np.dot(body_tangent, first_tangent), -1.0, 1.0))
        )
    )
    interface = _build_shallow_jet_interface_from_truncated_bvp(
        config,
        outer_bvp,
        original_cut_node_index=0,
        cut_angle_deg=angle,
        s_lambda_seed=s_lambda_seed,
    )
    coupled = solve_self_similar_wedge_with_shallow_jet(interface)
    if int(root_inner_iterations) > 0:
        root_iteration = iterate_shallow_jet_root_coupling(
            coupled,
            maximum_iterations=int(root_inner_iterations),
            relative_tolerance=float(config.coupled_root_inner_tolerance),
            relaxation=float(config.coupled_root_inner_relaxation),
        )
        if not root_iteration.converged:
            raise ValueError(
                "Shallow-jet root compatibility did not converge: reason="
                f"{root_iteration.termination_reason}, relative mismatch="
                f"{root_iteration.relative_mismatch_history[-1]:.6g}."
            )
        coupled = root_iteration.coupled
    return coupled


def _matching_surface_trigger_code(error: Exception | None) -> Literal[0, 1, 2]:
    if error is None:
        return 0
    message = str(error).lower()
    if (
        "shallow-water root state has no physical first-step solution" in message
        or "jet root requires" in message
    ):
        return 1
    if "Shallow-jet root compatibility did not converge" in message:
        return 2
    return 0


def _build_coupled_solution_with_compatible_root(
    config: SelfSimilarWedgeConfig,
    nodes: np.ndarray,
    far_dipole_coefficient: float,
    *,
    root_inner_iterations: int,
    s_lambda_seed: float | None,
    diagnostic_sink: list[SelfSimilarMatchingSurfaceAdjustment] | None = None,
) -> SelfSimilarShallowJetCoupledResult:
    """Move the matching surface outward until the local/global root is admissible.

    The matching surface is numerical rather than material.  It is therefore
    also ineligible when the shallow march exists for a supplied root value
    but no root-consistent augmented-BIE state is found in that physical
    domain.  In both cases one leading outer panel is transferred to the
    shallow model and all root data are recomputed from the new outer BIE.
    """

    original = np.asarray(nodes, dtype=float)
    candidate = original.copy()
    initial_panel_length = float(np.linalg.norm(original[1] - original[0]))
    seed = s_lambda_seed
    last_error: Exception | None = None
    full_panel_shifts = 0

    def try_build(
        trial_nodes: np.ndarray,
        trial_seed: float | None,
    ) -> tuple[SelfSimilarShallowJetCoupledResult | None, Exception | None]:
        try:
            result = _build_coupled_solution_from_outer_nodes(
                config,
                trial_nodes,
                far_dipole_coefficient,
                root_inner_iterations=root_inner_iterations,
                s_lambda_seed=trial_seed,
            )
            return result, None
        except ValueError as error:
            message = str(error).lower()
            relocatable = (
                "shallow-water root state has no physical first-step solution" in message
                or "jet root requires" in message
                or "shallow-jet root compatibility did not converge" in message
            )
            if not relocatable:
                raise
            return None, error

    for _ in range(8):
        result, error = try_build(candidate, seed)
        if result is not None:
            if diagnostic_sink is not None:
                diagnostic_sink.append(
                    SelfSimilarMatchingSurfaceAdjustment(
                        effective_panel_shift=float(full_panel_shifts),
                        full_panel_shifts=full_panel_shifts,
                        fractional_panel_shift=0.0,
                        root_displacement_ratio=float(
                            np.linalg.norm(candidate[0] - original[0])
                            / initial_panel_length
                        ),
                        bisection_iterations=0,
                        trigger_code=0,
                    )
                )
            return result
        last_error = error
        if len(candidate) <= 5:
            break

        shifted = _regrid_coupled_outer_nodes(config, candidate[1:])
        shifted_result, shifted_error = try_build(shifted, None)
        if shifted_result is None:
            candidate = shifted
            seed = None
            last_error = shifted_error
            full_panel_shifts += 1
            continue

        invalid = candidate
        valid = shifted
        best = shifted_result
        invalid_fraction = 0.0
        valid_fraction = 1.0
        for _ in range(int(config.coupled_matching_surface_bisection_iterations)):
            midpoint_fraction = 0.5 * (invalid_fraction + valid_fraction)
            midpoint = _regrid_coupled_outer_nodes(
                config,
                0.5 * (invalid + valid),
            )
            midpoint_result, midpoint_error = try_build(midpoint, None)
            if midpoint_result is None:
                invalid = midpoint
                invalid_fraction = midpoint_fraction
                last_error = midpoint_error
            else:
                valid = midpoint
                valid_fraction = midpoint_fraction
                best = midpoint_result
        if diagnostic_sink is not None:
            best_root = np.asarray(
                [
                    best.outer_free_surface.node_xi[0],
                    best.outer_free_surface.node_eta[0],
                ]
            )
            diagnostic_sink.append(
                SelfSimilarMatchingSurfaceAdjustment(
                    effective_panel_shift=full_panel_shifts + valid_fraction,
                    full_panel_shifts=full_panel_shifts,
                    fractional_panel_shift=valid_fraction,
                    root_displacement_ratio=float(
                        np.linalg.norm(best_root - original[0]) / initial_panel_length
                    ),
                    bisection_iterations=int(
                        config.coupled_matching_surface_bisection_iterations
                    ),
                    trigger_code=_matching_surface_trigger_code(error),
                )
            )
        return best
    detail = "" if last_error is None else f" Last root error: {last_error}"
    raise ValueError(
        "No shallow-water-compatible outer/jet matching surface remains." + detail
    )


def _geometry_maintenance_adjustment(
    old_nodes: np.ndarray,
    raw_nodes: np.ndarray,
    accepted_nodes: np.ndarray,
    time_step: float,
) -> SelfSimilarGeometryMaintenanceAdjustment:
    """Measure geometric velocity added after the explicit RK stage.

    The accepted curve is sampled at the normalized arc coordinates of the raw
    RK curve. This removes pure node redistribution along an unchanged curve;
    the remaining normal component measures shape motion introduced by spline
    regridding, smoothing, root transfer, or matching-surface relocation.
    """

    old = np.asarray(old_nodes, dtype=float)
    raw = np.asarray(raw_nodes, dtype=float)
    accepted = np.asarray(accepted_nodes, dtype=float)
    if old.shape != raw.shape or old.ndim != 2 or old.shape[1] != 2:
        raise ValueError(
            "Geometry-maintenance diagnostics require matching planar old/raw nodes."
        )
    if accepted.ndim != 2 or accepted.shape[1] != 2 or len(accepted) < 2:
        raise ValueError(
            "Geometry-maintenance diagnostics require a finite accepted curve."
        )
    if not np.isfinite((old, raw, accepted)).all():
        raise ValueError("Geometry-maintenance nodes must be finite.")
    if not np.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("Geometry-maintenance diagnostics require a positive time step.")

    raw_segment = np.diff(raw, axis=0)
    raw_length = np.linalg.norm(raw_segment, axis=1)
    accepted_length = np.linalg.norm(np.diff(accepted, axis=0), axis=1)
    if np.any(raw_length <= 1.0e-12) or np.any(accepted_length <= 1.0e-12):
        raise ValueError(
            "Geometry-maintenance diagnostics encountered a zero-length panel."
        )
    raw_arc = np.concatenate(([0.0], np.cumsum(raw_length)))
    accepted_arc = np.concatenate(([0.0], np.cumsum(accepted_length)))
    raw_fraction = raw_arc / raw_arc[-1]
    accepted_fraction = accepted_arc / accepted_arc[-1]
    accepted_on_raw = np.column_stack(
        (
            np.interp(raw_fraction, accepted_fraction, accepted[:, 0]),
            np.interp(raw_fraction, accepted_fraction, accepted[:, 1]),
        )
    )

    panel_tangent = raw_segment / raw_length[:, None]
    node_tangent = np.empty_like(raw)
    node_tangent[[0, -1]] = panel_tangent[[0, -1]]
    node_tangent[1:-1] = panel_tangent[:-1] + panel_tangent[1:]
    tangent_norm = np.linalg.norm(node_tangent, axis=1)
    if np.any(tangent_norm <= 1.0e-12):
        raise ValueError(
            "Geometry-maintenance diagnostics found an undefined node tangent."
        )
    node_tangent /= tangent_norm[:, None]
    node_normal = np.column_stack((-node_tangent[:, 1], node_tangent[:, 0]))

    node_weight = np.empty(len(raw), dtype=float)
    node_weight[[0, -1]] = 0.5 * raw_length[[0, -1]]
    node_weight[1:-1] = 0.5 * (raw_length[:-1] + raw_length[1:])
    local_length = np.empty(len(raw), dtype=float)
    local_length[[0, -1]] = raw_length[[0, -1]]
    local_length[1:-1] = np.minimum(raw_length[:-1], raw_length[1:])

    raw_velocity = (raw - old) / float(time_step)
    maintenance_displacement = accepted_on_raw - raw
    maintenance_velocity = maintenance_displacement / float(time_step)
    raw_normal = np.sum(raw_velocity * node_normal, axis=1)
    maintenance_normal = np.sum(maintenance_velocity * node_normal, axis=1)
    maintenance_tangential = np.sum(maintenance_velocity * node_tangent, axis=1)
    raw_energy = float(np.sum(node_weight * np.square(raw_normal)))
    maintenance_energy = float(
        np.sum(node_weight * np.square(maintenance_normal))
    )
    maintenance_tangential_energy = float(
        np.sum(node_weight * np.square(maintenance_tangential))
    )
    net_energy = float(
        np.sum(node_weight * np.square(raw_normal + maintenance_normal))
    )
    cross = float(np.sum(node_weight * raw_normal * maintenance_normal))
    denominator = np.sqrt(max(raw_energy * maintenance_energy, 0.0))
    correlation = 0.0 if denominator <= np.finfo(float).eps else cross / denominator
    cancellation = (
        0.0 if raw_energy <= np.finfo(float).eps else -cross / raw_energy
    )
    maximum_ratio = float(
        np.max(
            np.abs(np.sum(maintenance_displacement * node_normal, axis=1))
            / local_length
        )
    )
    return SelfSimilarGeometryMaintenanceAdjustment(
        raw_normal_velocity_integral=raw_energy,
        normal_velocity_integral=maintenance_energy,
        tangential_velocity_integral=maintenance_tangential_energy,
        net_normal_velocity_integral=net_energy,
        maximum_normal_displacement_ratio=maximum_ratio,
        normal_velocity_correlation=float(np.clip(correlation, -1.0, 1.0)),
        normal_cancellation_fraction=cancellation,
    )


def _coupled_root_predictor_seed(
    coupled: SelfSimilarShallowJetCoupledResult,
    measured: ShallowWaterJetRootState,
    *,
    root_inner_iterations: int,
) -> float | None:
    """Return a relaxed augmented-BIE seed only for the optional root solve.

    Iafrati's source algorithm initializes the shallow march from the bulk-flow
    BIE at every pseudo-time stage.  The augmented-BIE fixed-point iteration is
    an additional diagnostic used by this implementation.  Disabling that
    iteration must therefore also disable its predictor; otherwise the source
    root is silently overwritten even though ``root_inner_iterations`` is zero.
    """

    if int(root_inner_iterations) <= 0:
        return None
    relaxation = float(coupled.config.coupled_root_predictor_relaxation)
    return float(
        (1.0 - relaxation) * coupled.jet_interface.root_state.s_lambda
        + relaxation * measured.s_lambda
    )


def _advance_coupled_self_similar_wedge_pseudo_time_rk2_with_diagnostics(
    coupled: SelfSimilarShallowJetCoupledResult,
    *,
    root_inner_iterations: int = 8,
) -> tuple[
    SelfSimilarShallowJetCoupledResult,
    float,
    float,
    SelfSimilarCoupledRK2Diagnostics,
]:
    """Advance one RK2 step with the shallow jet rebuilt at both stages."""

    config = coupled.config
    old_nodes = np.column_stack(
        (
            coupled.outer_free_surface.node_xi,
            coupled.outer_free_surface.node_eta,
        )
    )
    free_length = np.diff(coupled.outer_free_surface.arc_length)
    k1 = _coupled_outer_pseudo_velocity(coupled)
    stage_one_root = derive_shallow_water_jet_root_state_from_coupled(coupled)
    if stage_one_root.s_lambda <= 0.0:
        raise ValueError("The current augmented BIE produced S_lambda<=0 at the jet root.")
    stage_one_seed = _coupled_root_predictor_seed(
        coupled,
        stage_one_root,
        root_inner_iterations=root_inner_iterations,
    )
    panel_speed = 0.5 * (
        np.linalg.norm(k1[:-1], axis=1) + np.linalg.norm(k1[1:], axis=1)
    )
    time_step = float(config.pseudo_cfl) * float(
        np.min(free_length / np.maximum(panel_speed, np.finfo(float).eps))
    )
    if not np.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("Coupled pseudo-time CFL produced an invalid time step.")

    last_stage_error: Exception | None = None
    last_stage_name = "initialization"
    last_attempt = -1
    last_attempt_time_step = time_step
    for rejected_attempt_count in range(12):
        last_attempt = rejected_attempt_count
        last_attempt_time_step = time_step
        provisional_adjustments: list[SelfSimilarMatchingSurfaceAdjustment] = []
        final_adjustments: list[SelfSimilarMatchingSurfaceAdjustment] = []
        try:
            last_stage_name = "provisional_raw_geometry"
            provisional_raw_nodes = _constrain_coupled_outer_nodes(
                config,
                old_nodes + time_step * k1,
                allow_reversed_root=True,
            )
            last_stage_name = "provisional_regrid"
            provisional_nodes = _regrid_coupled_outer_nodes(
                config,
                provisional_raw_nodes,
            )
            last_stage_name = "provisional_coupled_bie"
            provisional = _build_coupled_solution_with_compatible_root(
                config,
                provisional_nodes,
                coupled.dipole_coefficient,
                root_inner_iterations=root_inner_iterations,
                s_lambda_seed=stage_one_seed,
                diagnostic_sink=provisional_adjustments,
            )
            provisional_accepted_nodes = np.column_stack(
                (
                    provisional.outer_free_surface.node_xi,
                    provisional.outer_free_surface.node_eta,
                )
            )
            provisional_geometry_maintenance = _geometry_maintenance_adjustment(
                old_nodes,
                provisional_raw_nodes,
                provisional_accepted_nodes,
                time_step,
            )
            last_stage_name = "provisional_root_recovery"
            k2 = _coupled_outer_pseudo_velocity(provisional)
            stage_two_root = derive_shallow_water_jet_root_state_from_coupled(
                provisional
            )
            if stage_two_root.s_lambda <= 0.0:
                raise ValueError(
                    "The provisional augmented BIE produced S_lambda<=0 at the jet root."
                )
            stage_two_seed = _coupled_root_predictor_seed(
                provisional,
                stage_two_root,
                root_inner_iterations=root_inner_iterations,
            )
            last_stage_name = "final_raw_geometry"
            raw_nodes = _constrain_coupled_outer_nodes(
                config,
                old_nodes + 0.5 * time_step * (k1 + k2),
                allow_reversed_root=True,
            )
            old_midpoint = 0.5 * (old_nodes[:-1] + old_nodes[1:])
            new_midpoint = 0.5 * (raw_nodes[:-1] + raw_nodes[1:])
            maximum_ratio = float(
                np.max(np.linalg.norm(new_midpoint - old_midpoint, axis=1) / free_length)
            )
            if maximum_ratio > 0.25 + 1.0e-12:
                time_step *= 0.5
                continue
            last_stage_name = "final_regrid"
            final_nodes = _regrid_coupled_outer_nodes(config, raw_nodes)
            last_stage_name = "final_coupled_bie"
            final = _build_coupled_solution_with_compatible_root(
                config,
                final_nodes,
                coupled.dipole_coefficient,
                root_inner_iterations=root_inner_iterations,
                s_lambda_seed=stage_two_seed,
                diagnostic_sink=final_adjustments,
            )
            final_accepted_nodes = np.column_stack(
                (
                    final.outer_free_surface.node_xi,
                    final.outer_free_surface.node_eta,
                )
            )
            final_geometry_maintenance = _geometry_maintenance_adjustment(
                old_nodes,
                raw_nodes,
                final_accepted_nodes,
                time_step,
            )
            if len(provisional_adjustments) != 1 or len(final_adjustments) != 1:
                raise ValueError(
                    "Accepted coupled RK2 stages require one matching-surface "
                    "diagnostic each."
                )
            diagnostics = SelfSimilarCoupledRK2Diagnostics(
                provisional=provisional_adjustments[0],
                final=final_adjustments[0],
                provisional_geometry_maintenance=provisional_geometry_maintenance,
                final_geometry_maintenance=final_geometry_maintenance,
                rejected_attempt_count=rejected_attempt_count,
            )
            return final, time_step, maximum_ratio, diagnostics
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            last_stage_error = error
            if "NO_BRACKET_IN_PHYSICAL_DOMAIN" in str(error):
                break
            time_step *= 0.5
    detail = (
        ""
        if last_stage_error is None
        else (
            f" Last stage={last_stage_name}, attempt={last_attempt}, "
            f"time_step={last_attempt_time_step:.17g} error: {last_stage_error}"
        )
    )
    raise ValueError(
        "Coupled pseudo-time RK2 could not construct a valid jet stage." + detail
    )


def advance_coupled_self_similar_wedge_pseudo_time_rk2(
    coupled: SelfSimilarShallowJetCoupledResult,
    *,
    root_inner_iterations: int = 8,
) -> tuple[SelfSimilarShallowJetCoupledResult, float, float]:
    """Advance one RK2 step while retaining the established public result tuple."""

    advanced, time_step, maximum_ratio, _ = (
        _advance_coupled_self_similar_wedge_pseudo_time_rk2_with_diagnostics(
            coupled,
            root_inner_iterations=root_inner_iterations,
        )
    )
    return advanced, time_step, maximum_ratio


def solve_coupled_self_similar_wedge_pseudo_time(
    initial: SelfSimilarShallowJetCoupledResult,
    *,
    maximum_iterations: int = 5,
    root_inner_iterations: int = 8,
    stop_when_converged: bool = True,
) -> SelfSimilarCoupledPseudoTimeResult:
    """Repeat the augmented outer/jet BIE update without benchmark feedback.

    ``stop_when_converged=False`` is an explicit fixed-step diagnostic used for
    time-step convergence from an already qualified checkpoint. The default
    production stopping behavior is unchanged.
    """

    def jet_topology_metrics(
        current: SelfSimilarShallowJetCoupledResult,
    ) -> tuple[int, int, int, float, float]:
        labels = np.asarray(current.boundary.panel_labels, dtype=object)
        jet = current.jet_interface.jet
        return (
            len(jet.thickness),
            int(np.count_nonzero(labels == "shallow_jet_body")),
            current.boundary.panel_count,
            float(jet.thickness[-1]),
            float(jet.s_lambda[-1]),
        )

    if int(maximum_iterations) < 0:
        raise ValueError("maximum_iterations must be non-negative.")
    coupled = initial
    if coupled.config.coupled_root_reconstruction_enabled:
        initial_nodes = np.column_stack(
            (
                coupled.outer_free_surface.node_xi,
                coupled.outer_free_surface.node_eta,
            )
        )
        expected_refined_nodes = (
            coupled.config.free_surface_panels
            + coupled.config.coupled_root_reconstruction_added_panels
            + 1
        )
        if len(initial_nodes) != expected_refined_nodes:
            rebuilt_nodes = _regrid_coupled_outer_nodes(coupled.config, initial_nodes)
            coupled = _build_coupled_solution_with_compatible_root(
                coupled.config,
                rebuilt_nodes,
                coupled.dipole_coefficient,
                root_inner_iterations=root_inner_iterations,
                s_lambda_seed=coupled.jet_interface.root_state.s_lambda,
            )
    pseudo_time = [0.0]
    steps: list[float] = []
    kinematic = [coupled.kinematic_rms]
    kinematic_integral = [coupled.kinematic_integral]
    kinematic_convergence_integral = [coupled.kinematic_convergence_integral]
    dipole = [coupled.dipole_coefficient]
    thickness = [coupled.jet_interface.root_state.thickness]
    s_lambda = [coupled.jet_interface.root_state.s_lambda]
    measured_root = derive_shallow_water_jet_root_state_from_coupled(coupled)
    measured_s_lambda = [measured_root.s_lambda]
    root_mismatch = [
        abs(measured_root.s_lambda - s_lambda[-1])
        / max(abs(s_lambda[-1]), np.finfo(float).eps)
    ]
    initial_nodes = np.column_stack(
        (
            coupled.outer_free_surface.node_xi,
            coupled.outer_free_surface.node_eta,
        )
    )
    beta = np.deg2rad(coupled.config.deadrise_deg)
    root_body_eta = [float(_project_root_to_wedge(initial_nodes[0], beta)[1])]
    root_resolution_ratio = [
        _coupled_jet_interface_resolution_ratio(coupled.config, initial_nodes)
    ]
    bem_condition_number = [coupled.solution.condition_number]
    initial_topology = jet_topology_metrics(coupled)
    jet_point_count = [initial_topology[0]]
    shallow_jet_panel_count = [initial_topology[1]]
    boundary_panel_count = [initial_topology[2]]
    jet_tip_thickness = [initial_topology[3]]
    jet_tip_s_lambda = [initial_topology[4]]
    displacement: list[float] = []
    provisional_matching_shift: list[float] = []
    final_matching_shift: list[float] = []
    provisional_matching_root_displacement: list[float] = []
    final_matching_root_displacement: list[float] = []
    provisional_matching_trigger: list[int] = []
    final_matching_trigger: list[int] = []
    rk2_rejected_attempt_count: list[int] = []
    converged = coupled.kinematic_convergence_integral <= float(
        coupled.config.coupled_kinematic_integral_tolerance
    )
    termination: Literal[
        "KINEMATIC_CONVERGED", "MAXIMUM_ITERATIONS", "NUMERICAL_FAILURE"
    ] = (
        "KINEMATIC_CONVERGED"
        if converged and bool(stop_when_converged)
        else "MAXIMUM_ITERATIONS"
    )
    failure_message: str | None = None
    for _ in range(int(maximum_iterations)):
        if converged and bool(stop_when_converged):
            break
        try:
            coupled, step, ratio, step_diagnostics = (
                _advance_coupled_self_similar_wedge_pseudo_time_rk2_with_diagnostics(
                    coupled,
                    root_inner_iterations=root_inner_iterations,
                )
            )
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            termination = "NUMERICAL_FAILURE"
            failure_message = str(error)
            break
        steps.append(step)
        displacement.append(ratio)
        provisional_matching_shift.append(
            step_diagnostics.provisional.effective_panel_shift
        )
        final_matching_shift.append(step_diagnostics.final.effective_panel_shift)
        provisional_matching_root_displacement.append(
            step_diagnostics.provisional.root_displacement_ratio
        )
        final_matching_root_displacement.append(
            step_diagnostics.final.root_displacement_ratio
        )
        provisional_matching_trigger.append(step_diagnostics.provisional.trigger_code)
        final_matching_trigger.append(step_diagnostics.final.trigger_code)
        rk2_rejected_attempt_count.append(step_diagnostics.rejected_attempt_count)
        pseudo_time.append(pseudo_time[-1] + step)
        kinematic.append(coupled.kinematic_rms)
        kinematic_integral.append(coupled.kinematic_integral)
        kinematic_convergence_integral.append(
            coupled.kinematic_convergence_integral
        )
        dipole.append(coupled.dipole_coefficient)
        thickness.append(coupled.jet_interface.root_state.thickness)
        s_lambda.append(coupled.jet_interface.root_state.s_lambda)
        measured_root = derive_shallow_water_jet_root_state_from_coupled(coupled)
        measured_s_lambda.append(measured_root.s_lambda)
        root_mismatch.append(
            abs(measured_root.s_lambda - s_lambda[-1])
            / max(abs(s_lambda[-1]), np.finfo(float).eps)
        )
        current_nodes = np.column_stack(
            (
                coupled.outer_free_surface.node_xi,
                coupled.outer_free_surface.node_eta,
            )
        )
        root_body_eta.append(
            float(_project_root_to_wedge(current_nodes[0], beta)[1])
        )
        root_resolution_ratio.append(
            _coupled_jet_interface_resolution_ratio(coupled.config, current_nodes)
        )
        bem_condition_number.append(coupled.solution.condition_number)
        current_topology = jet_topology_metrics(coupled)
        jet_point_count.append(current_topology[0])
        shallow_jet_panel_count.append(current_topology[1])
        boundary_panel_count.append(current_topology[2])
        jet_tip_thickness.append(current_topology[3])
        jet_tip_s_lambda.append(current_topology[4])
        if coupled.kinematic_convergence_integral <= float(
            coupled.config.coupled_kinematic_integral_tolerance
        ):
            converged = True
            if bool(stop_when_converged):
                termination = "KINEMATIC_CONVERGED"
                break
    return SelfSimilarCoupledPseudoTimeResult(
        config=coupled.config,
        coupled=coupled,
        pseudo_time_history=np.asarray(pseudo_time),
        time_step_history=np.asarray(steps),
        kinematic_rms_history=np.asarray(kinematic),
        kinematic_integral_history=np.asarray(kinematic_integral),
        kinematic_convergence_integral_history=np.asarray(
            kinematic_convergence_integral
        ),
        dipole_coefficient_history=np.asarray(dipole),
        root_thickness_history=np.asarray(thickness),
        root_s_lambda_history=np.asarray(s_lambda),
        root_measured_s_lambda_history=np.asarray(measured_s_lambda),
        root_relative_mismatch_history=np.asarray(root_mismatch),
        root_body_eta_history=np.asarray(root_body_eta),
        root_resolution_ratio_history=np.asarray(root_resolution_ratio),
        bem_condition_number_history=np.asarray(bem_condition_number),
        maximum_displacement_ratio_history=np.asarray(displacement),
        converged=converged,
        termination_reason=termination,
        failure_message=failure_message,
        provisional_matching_surface_shift_history=np.asarray(
            provisional_matching_shift
        ),
        final_matching_surface_shift_history=np.asarray(final_matching_shift),
        provisional_matching_surface_root_displacement_history=np.asarray(
            provisional_matching_root_displacement
        ),
        final_matching_surface_root_displacement_history=np.asarray(
            final_matching_root_displacement
        ),
        provisional_matching_surface_trigger_history=np.asarray(
            provisional_matching_trigger
        ),
        final_matching_surface_trigger_history=np.asarray(final_matching_trigger),
        rk2_rejected_attempt_count_history=np.asarray(rk2_rejected_attempt_count),
        jet_point_count_history=np.asarray(jet_point_count),
        shallow_jet_panel_count_per_side_history=np.asarray(
            shallow_jet_panel_count
        ),
        boundary_panel_count_history=np.asarray(boundary_panel_count),
        jet_tip_thickness_history=np.asarray(jet_tip_thickness),
        jet_tip_s_lambda_history=np.asarray(jet_tip_s_lambda),
        status=(
            "iafrati_2013_repeated_shallow_jet_augmented_bie_"
            f"{coupled.config.coupled_free_surface_update}_update_"
            f"{coupled.config.coupled_pseudo_time_preconditioner}_preconditioner_"
            f"{coupled.config.coupled_jet_terminal_closure}_terminal_unvalidated"
        ),
    )


def solve_self_similar_wedge(
    config: SelfSimilarWedgeConfig,
) -> SelfSimilarWedgeResult:
    """Minimize Iafrati Eq. (17) without using a benchmark response curve."""

    initial = _initial_control_vector(config)
    lower, upper = _control_bounds(config)
    initial = np.clip(initial, lower + 1.0e-9, upper - 1.0e-9)
    initial_bvp = solve_self_similar_wedge_bvp(config, initial)

    def residual(controls: np.ndarray) -> np.ndarray:
        try:
            return solve_self_similar_wedge_bvp(config, controls).scaled_kinematic_residual
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            return np.full(config.free_surface_panels, 1.0e3, dtype=float)

    optimization = least_squares(
        residual,
        initial,
        bounds=(lower, upper),
        max_nfev=config.max_nfev,
        ftol=config.optimizer_ftol,
        xtol=config.optimizer_xtol,
        gtol=config.optimizer_gtol,
        x_scale="jac",
    )
    final_bvp = solve_self_similar_wedge_bvp(config, optimization.x)
    return SelfSimilarWedgeResult(
        config=config,
        bvp=final_bvp,
        control_values=np.asarray(optimization.x, dtype=float),
        optimizer_success=bool(optimization.success),
        optimizer_message=str(optimization.message),
        optimizer_function_evaluations=int(optimization.nfev),
        initial_kinematic_rms=initial_bvp.kinematic_rms,
        final_kinematic_rms=final_bvp.kinematic_rms,
    )


def _quadratic_peak_location_and_value(
    coordinate: np.ndarray,
    values: np.ndarray,
) -> tuple[float, float]:
    """Estimate a sampled smooth peak with a local nonuniform quadratic fit."""

    x = np.asarray(coordinate, dtype=float)
    y = np.asarray(values, dtype=float)
    if (
        x.ndim != 1
        or y.shape != x.shape
        or len(x) < 1
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
        or np.any(np.diff(x) <= 0.0)
    ):
        raise ValueError("Peak interpolation requires finite increasing samples.")
    peak_index = int(np.argmax(y))
    if peak_index == 0 or peak_index == len(x) - 1 or len(x) < 3:
        return float(x[peak_index]), float(y[peak_index])

    local_x = x[peak_index - 1 : peak_index + 2]
    local_y = y[peak_index - 1 : peak_index + 2]
    origin = float(local_x[1])
    scale = max(float(local_x[-1] - local_x[0]), np.finfo(float).eps)
    normalized_x = (local_x - origin) / scale
    quadratic, linear, constant = np.polyfit(normalized_x, local_y, 2)
    if not np.isfinite((quadratic, linear, constant)).all() or quadratic >= 0.0:
        return float(x[peak_index]), float(y[peak_index])
    normalized_peak = float(-linear / (2.0 * quadratic))
    peak_x = origin + scale * normalized_peak
    if peak_x < local_x[0] or peak_x > local_x[-1]:
        return float(x[peak_index]), float(y[peak_index])
    peak_y = float(
        quadratic * normalized_peak**2 + linear * normalized_peak + constant
    )
    if not np.isfinite(peak_y) or peak_y < y[peak_index]:
        return float(x[peak_index]), float(y[peak_index])
    return float(peak_x), peak_y


def _wedge_pressure_vertical_force_coefficient(
    vertical_coordinate: np.ndarray,
    pressure_coefficient: np.ndarray,
    deadrise_deg: float,
) -> float:
    """Integrate one wedge-side pressure using n_z ds = cot(beta) d eta."""

    eta = np.asarray(vertical_coordinate, dtype=float)
    pressure = np.asarray(pressure_coefficient, dtype=float)
    beta = float(deadrise_deg)
    if (
        eta.ndim != 1
        or pressure.shape != eta.shape
        or len(eta) < 2
        or not np.isfinite(eta).all()
        or not np.isfinite(pressure).all()
        or np.any(np.diff(eta) <= 0.0)
        or not np.isfinite(beta)
        or not 0.0 < beta < 90.0
    ):
        raise ValueError("Wedge pressure integration inputs are invalid.")
    return float(np.trapezoid(pressure, eta) / np.tan(np.deg2rad(beta)))


def evaluate_self_similar_wedge_reference(
    result: (
        SelfSimilarWedgeResult
        | SelfSimilarPseudoTimeResult
        | SelfSimilarShallowJetCoupledResult
    ),
    reference_csv: str | Path,
) -> SelfSimilarReferenceMetrics:
    """Score a completed solve; benchmark data never enter the optimizer."""

    frame = pd.read_csv(Path(reference_csv))
    required = {"beta_deg", "quantity", "x_nondimensional", "y_nondimensional"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Reference CSV is missing columns: {sorted(missing)}")
    subset = frame[np.isclose(frame["beta_deg"], result.config.deadrise_deg)]
    free = subset[subset["quantity"] == "free_surface"].sort_values("x_nondimensional")
    pressure = subset[subset["quantity"] == "pressure"].sort_values("x_nondimensional")
    if free.empty or pressure.empty:
        raise ValueError("Reference CSV does not contain both requested curves.")

    if isinstance(result, SelfSimilarShallowJetCoupledResult):
        model_free_x = result.outer_free_surface.node_xi
        model_free_eta = result.outer_free_surface.node_eta
        boundary = result.boundary
        labels = np.asarray(boundary.panel_labels, dtype=object)
        body_mask = (labels == "body") | (labels == "shallow_jet_body")
        body_pressure = result.body_pressure_coefficient
        computed_vertical_force = float(result.body_vertical_force_coefficient)
    else:
        model_free_x = result.bvp.free_surface.node_xi
        model_free_eta = result.bvp.free_surface.node_eta
        boundary = result.bvp.boundary
        labels = np.asarray(boundary.panel_labels, dtype=object)
        body_mask = labels == "body"
        body_pressure = result.bvp.body_pressure_coefficient
        computed_vertical_force = float(result.bvp.body_vertical_force_coefficient)
    free_domain = free[
        (free["x_nondimensional"] >= model_free_x[0])
        & (free["x_nondimensional"] <= model_free_x[-1])
    ]
    if len(free_domain) < 3:
        raise ValueError("Insufficient overlapping free-surface reference points.")
    free_model = np.interp(
        free_domain["x_nondimensional"], model_free_x, model_free_eta
    )
    free_reference = free_domain["y_nondimensional"].to_numpy(float)
    free_scale = max(float(np.ptp(free_reference)), 1.0e-12)
    free_nrmse = float(np.sqrt(np.mean(np.square(free_model - free_reference))) / free_scale)

    body_eta = boundary.panel_mid_z_up_m[body_mask]
    order = np.argsort(body_eta)
    body_eta = body_eta[order]
    body_cp = body_pressure[order]
    pressure_domain = pressure[
        (pressure["x_nondimensional"] >= body_eta[0])
        & (pressure["x_nondimensional"] <= body_eta[-1])
    ]
    if len(pressure_domain) < 3:
        raise ValueError("Insufficient overlapping pressure reference points.")
    pressure_model = np.interp(
        pressure_domain["x_nondimensional"], body_eta, body_cp
    )
    pressure_reference = pressure_domain["y_nondimensional"].to_numpy(float)
    pressure_scale = max(float(np.ptp(pressure_reference)), 1.0e-12)
    pressure_nrmse = float(
        np.sqrt(np.mean(np.square(pressure_model - pressure_reference))) / pressure_scale
    )
    pressure_coordinate = pressure_domain["x_nondimensional"].to_numpy(float)
    reference_peak_location, reference_peak = _quadratic_peak_location_and_value(
        pressure_coordinate, pressure_reference
    )
    model_peak_location, model_peak = _quadratic_peak_location_and_value(
        pressure_coordinate, pressure_model
    )
    pressure_peak_relative_error = float(
        abs(model_peak - reference_peak) / max(abs(reference_peak), 1.0e-12)
    )
    pressure_peak_location_relative_error = float(
        abs(model_peak_location - reference_peak_location)
        / max(abs(reference_peak_location), 1.0e-12)
    )
    reference_vertical_force = _wedge_pressure_vertical_force_coefficient(
        pressure["x_nondimensional"].to_numpy(float),
        pressure["y_nondimensional"].to_numpy(float),
        result.config.deadrise_deg,
    )
    vertical_force_relative_error = float(
        abs(computed_vertical_force - reference_vertical_force)
        / max(abs(reference_vertical_force), 1.0e-12)
    )
    return SelfSimilarReferenceMetrics(
        deadrise_deg=result.config.deadrise_deg,
        free_surface_point_count=len(free_domain),
        free_surface_nrmse=free_nrmse,
        pressure_point_count=len(pressure_domain),
        pressure_nrmse=pressure_nrmse,
        pressure_peak_relative_error=pressure_peak_relative_error,
        pressure_peak_location_relative_error=pressure_peak_location_relative_error,
        computed_vertical_force_coefficient=computed_vertical_force,
        reference_vertical_force_coefficient=reference_vertical_force,
        vertical_force_relative_error=vertical_force_relative_error,
    )


def evaluate_self_similar_wedge_scalar_reference(
    result: (
        SelfSimilarWedgeResult
        | SelfSimilarPseudoTimeResult
        | SelfSimilarShallowJetCoupledResult
    ),
    reference_csv: str | Path,
) -> SelfSimilarScalarReferenceMetrics:
    """Compare the completed solve with exact Iafrati Table 1 scalars."""

    frame = pd.read_csv(Path(reference_csv))
    required = {"deadrise_deg", "pressure_coefficient_peak", "peak_eta"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Scalar reference CSV is missing columns: {sorted(missing)}")
    subset = frame[np.isclose(frame["deadrise_deg"], result.config.deadrise_deg)]
    if len(subset) != 1:
        raise ValueError("Scalar reference CSV must contain exactly one requested angle row.")
    reference_peak = float(subset.iloc[0]["pressure_coefficient_peak"])
    reference_eta = float(subset.iloc[0]["peak_eta"])

    if isinstance(result, SelfSimilarShallowJetCoupledResult):
        labels = np.asarray(result.boundary.panel_labels, dtype=object)
        body_mask = (labels == "body") | (labels == "shallow_jet_body")
        body_eta = result.boundary.panel_mid_z_up_m[body_mask]
        body_cp = result.body_pressure_coefficient
    else:
        labels = np.asarray(result.bvp.boundary.panel_labels, dtype=object)
        body_mask = labels == "body"
        body_eta = result.bvp.boundary.panel_mid_z_up_m[body_mask]
        body_cp = result.bvp.body_pressure_coefficient
    order = np.argsort(body_eta)
    computed_eta, computed_peak = _quadratic_peak_location_and_value(
        body_eta[order], body_cp[order]
    )
    return SelfSimilarScalarReferenceMetrics(
        deadrise_deg=result.config.deadrise_deg,
        computed_pressure_peak=computed_peak,
        reference_pressure_peak=reference_peak,
        pressure_peak_relative_error=abs(computed_peak - reference_peak)
        / max(abs(reference_peak), 1.0e-12),
        computed_peak_eta=computed_eta,
        reference_peak_eta=reference_eta,
        pressure_peak_location_relative_error=abs(computed_eta - reference_eta)
        / max(abs(reference_eta), 1.0e-12),
    )
