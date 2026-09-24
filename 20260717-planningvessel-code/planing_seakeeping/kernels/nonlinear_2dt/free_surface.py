from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .boundary_element import ClosedBoundary2D, MixedBoundarySolution, boundary_velocity, solve_section_potential_bvp


NONLINEAR_2DT_FREE_SURFACE_STATUS = (
    "sun_ch2_lagrangian_free_surface_rk4_no_jet_spray_or_remesh_benchmark_pending"
)


BodyNormalVelocity = Callable[[ClosedBoundary2D, float], np.ndarray]


@dataclass(frozen=True)
class LagrangianFreeSurfaceState:
    boundary: ClosedBoundary2D
    free_surface_potential_m2_s: np.ndarray
    time_s: float = 0.0
    status: str = NONLINEAR_2DT_FREE_SURFACE_STATUS

    def __post_init__(self) -> None:
        labels = np.asarray(self.boundary.panel_labels, dtype=object)
        count = int(np.count_nonzero(labels == "free_surface"))
        potential = np.asarray(self.free_surface_potential_m2_s, dtype=float)
        if potential.shape != (count,) or not np.isfinite(potential).all():
            raise ValueError("free_surface_potential_m2_s must be finite with one value per free panel.")
        if not np.isfinite(float(self.time_s)):
            raise ValueError("time_s must be finite.")
        object.__setattr__(self, "free_surface_potential_m2_s", potential)


@dataclass(frozen=True)
class FreeSurfaceRhs:
    node_velocity_mps: np.ndarray
    potential_rate_m2_s2: np.ndarray
    potential_solution: MixedBoundarySolution


@dataclass(frozen=True)
class FreeSurfaceAdvanceResult:
    state: LagrangianFreeSurfaceState
    max_bvp_relative_residual: float
    max_bvp_condition_number: float
    stage_count: int = 4


def _free_node_velocity(
    boundary: ClosedBoundary2D,
    free_panel_velocity: np.ndarray,
) -> np.ndarray:
    labels = np.asarray(boundary.panel_labels, dtype=object)
    free_indices = np.flatnonzero(labels == "free_surface")
    if free_panel_velocity.shape != (len(free_indices), 2):
        raise ValueError("free_panel_velocity must have shape (n_free_panel, 2).")
    panel_velocity = np.zeros((boundary.panel_count, 2), dtype=float)
    panel_velocity[free_indices] = free_panel_velocity
    node_velocity = np.zeros((boundary.panel_count + 1, 2), dtype=float)
    for node_index in range(boundary.panel_count):
        previous_panel = (node_index - 1) % boundary.panel_count
        next_panel = node_index
        adjacent_free = [index for index in (previous_panel, next_panel) if labels[index] == "free_surface"]
        if not adjacent_free:
            continue
        candidate = np.mean(panel_velocity[adjacent_free], axis=0)
        adjacent_nonfree = [index for index in (previous_panel, next_panel) if labels[index] != "free_surface"]
        if adjacent_nonfree:
            tangent = boundary.panel_tangent[adjacent_nonfree[0]]
            candidate = tangent * float(np.dot(candidate, tangent))
        node_velocity[node_index] = candidate
    node_velocity[-1] = node_velocity[0]
    return node_velocity


def evaluate_free_surface_rhs(
    state: LagrangianFreeSurfaceState,
    body_normal_velocity: BodyNormalVelocity,
    *,
    gravity_m_s2: float = 9.80665,
    gauss_order: int = 12,
) -> FreeSurfaceRhs:
    """Evaluate the nonlinear Lagrangian free-surface equations (2.3)-(2.4)."""

    gravity = float(gravity_m_s2)
    if gravity <= 0.0:
        raise ValueError("gravity_m_s2 must be positive.")
    boundary = state.boundary
    labels = np.asarray(boundary.panel_labels, dtype=object)
    free_mask = labels == "free_surface"
    body_mask = labels == "body"
    body_velocity = np.asarray(body_normal_velocity(boundary, float(state.time_s)), dtype=float)
    if body_velocity.shape != (int(np.count_nonzero(body_mask)),) or not np.isfinite(body_velocity).all():
        raise ValueError("body_normal_velocity callback returned an invalid body-panel vector.")
    solution = solve_section_potential_bvp(
        boundary,
        free_surface_potential_m2_s=state.free_surface_potential_m2_s,
        body_normal_velocity_mps=body_velocity,
        gauss_order=gauss_order,
    )
    velocity = boundary_velocity(boundary, solution)
    free_velocity = velocity[free_mask]
    node_velocity = _free_node_velocity(boundary, free_velocity)
    potential_rate = 0.5 * np.sum(free_velocity**2, axis=1) - gravity * boundary.panel_mid_z_up_m[free_mask]
    return FreeSurfaceRhs(
        node_velocity_mps=node_velocity,
        potential_rate_m2_s2=potential_rate,
        potential_solution=solution,
    )


def _state_increment(
    state: LagrangianFreeSurfaceState,
    rhs: FreeSurfaceRhs,
    scale_s: float,
) -> LagrangianFreeSurfaceState:
    scale = float(scale_s)
    y = state.boundary.node_y_m + scale * rhs.node_velocity_mps[:, 0]
    z = state.boundary.node_z_up_m + scale * rhs.node_velocity_mps[:, 1]
    y[-1], z[-1] = y[0], z[0]
    return LagrangianFreeSurfaceState(
        boundary=ClosedBoundary2D(
            node_y_m=y,
            node_z_up_m=z,
            panel_labels=state.boundary.panel_labels,
        ),
        free_surface_potential_m2_s=(
            state.free_surface_potential_m2_s + scale * rhs.potential_rate_m2_s2
        ),
        time_s=state.time_s + scale,
    )


def advance_free_surface_rk4(
    state: LagrangianFreeSurfaceState,
    body_normal_velocity: BodyNormalVelocity,
    *,
    time_step_s: float,
    gravity_m_s2: float = 9.80665,
    gauss_order: int = 12,
) -> FreeSurfaceAdvanceResult:
    """Advance one fully nonlinear Lagrangian free-surface RK4 step."""

    dt = float(time_step_s)
    if dt <= 0.0:
        raise ValueError("time_step_s must be positive.")
    k1 = evaluate_free_surface_rhs(
        state,
        body_normal_velocity,
        gravity_m_s2=gravity_m_s2,
        gauss_order=gauss_order,
    )
    k2 = evaluate_free_surface_rhs(
        _state_increment(state, k1, 0.5 * dt),
        body_normal_velocity,
        gravity_m_s2=gravity_m_s2,
        gauss_order=gauss_order,
    )
    k3 = evaluate_free_surface_rhs(
        _state_increment(state, k2, 0.5 * dt),
        body_normal_velocity,
        gravity_m_s2=gravity_m_s2,
        gauss_order=gauss_order,
    )
    k4 = evaluate_free_surface_rhs(
        _state_increment(state, k3, dt),
        body_normal_velocity,
        gravity_m_s2=gravity_m_s2,
        gauss_order=gauss_order,
    )
    combined_node_velocity = (
        k1.node_velocity_mps
        + 2.0 * k2.node_velocity_mps
        + 2.0 * k3.node_velocity_mps
        + k4.node_velocity_mps
    ) / 6.0
    combined_potential_rate = (
        k1.potential_rate_m2_s2
        + 2.0 * k2.potential_rate_m2_s2
        + 2.0 * k3.potential_rate_m2_s2
        + k4.potential_rate_m2_s2
    ) / 6.0
    final_rhs = FreeSurfaceRhs(
        node_velocity_mps=combined_node_velocity,
        potential_rate_m2_s2=combined_potential_rate,
        potential_solution=k4.potential_solution,
    )
    final_state = _state_increment(state, final_rhs, dt)
    stage_solutions = (k1.potential_solution, k2.potential_solution, k3.potential_solution, k4.potential_solution)
    return FreeSurfaceAdvanceResult(
        state=final_state,
        max_bvp_relative_residual=max(item.relative_residual for item in stage_solutions),
        max_bvp_condition_number=max(item.condition_number for item in stage_solutions),
    )
