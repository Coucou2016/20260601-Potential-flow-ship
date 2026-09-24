from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    load_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    _coupled_outer_pseudo_velocity,
)


def continuous_linear_weak_projection(
    panel_length: np.ndarray,
    residual_endpoint: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Project discontinuous panel endpoint residuals onto a continuous P1 chain.

    The assembled load is ``b_i = integral(N_i r ds)`` and the consistent
    one-dimensional mass matrix satisfies ``M c = b``.  ``c`` is the weakly
    projected nodal residual and ``c.T M c = b.T M^-1 b`` is its squared L2
    norm.  The gap to the panelwise exact norm isolates residual content that
    cannot be represented by the continuous test space.
    """

    length = np.asarray(panel_length, dtype=float)
    endpoint = np.asarray(residual_endpoint, dtype=float)
    if length.ndim != 1 or endpoint.shape != (len(length), 2):
        raise ValueError("Weak projection requires two residual endpoints per panel.")
    if len(length) == 0 or not np.isfinite(length).all() or np.any(length <= 0.0):
        raise ValueError("Weak projection panel lengths must be finite and positive.")
    if not np.isfinite(endpoint).all():
        raise ValueError("Weak projection residual endpoints must be finite.")

    node_count = len(length) + 1
    mass = np.zeros((node_count, node_count), dtype=float)
    load = np.zeros(node_count, dtype=float)
    for panel, panel_length_value in enumerate(length):
        local_mass = panel_length_value * np.asarray(
            [[2.0, 1.0], [1.0, 2.0]],
            dtype=float,
        ) / 6.0
        mass[panel : panel + 2, panel : panel + 2] += local_mass
        load[panel : panel + 2] += local_mass @ endpoint[panel]
    projected = np.linalg.solve(mass, load)
    projected_integral = float(np.dot(projected, load))
    exact_integral = float(
        np.sum(
            length
            * (
                np.square(endpoint[:, 0])
                + endpoint[:, 0] * endpoint[:, 1]
                + np.square(endpoint[:, 1])
            )
            / 3.0
        )
    )
    unresolved_integral = max(0.0, exact_integral - projected_integral)
    return projected, load, projected_integral, unresolved_integral


def continuous_linear_projection_error_contribution(
    panel_length: np.ndarray,
    residual_endpoint: np.ndarray,
    projected_node_residual: np.ndarray,
) -> np.ndarray:
    """Return the non-negative panelwise norm of the weak-projection error."""

    length = np.asarray(panel_length, dtype=float)
    endpoint = np.asarray(residual_endpoint, dtype=float)
    projected = np.asarray(projected_node_residual, dtype=float)
    if endpoint.shape != (len(length), 2) or projected.shape != (len(length) + 1,):
        raise ValueError("Projection-error data have incompatible dimensions.")
    if (
        len(length) == 0
        or not np.isfinite(length).all()
        or np.any(length <= 0.0)
        or not np.isfinite(endpoint).all()
        or not np.isfinite(projected).all()
    ):
        raise ValueError("Projection-error data must be finite with positive lengths.")
    difference = endpoint - np.column_stack((projected[:-1], projected[1:]))
    return length * (
        np.square(difference[:, 0])
        + difference[:, 0] * difference[:, 1]
        + np.square(difference[:, 1])
    ) / 3.0


def linear_endpoint_residual_diagnostics(
    panel_length: np.ndarray,
    residual_endpoint: np.ndarray,
    residual_midpoint: np.ndarray,
) -> dict[str, float | bool]:
    """Separate panel-average residual from within-element trace variation.

    For endpoint values ``r_L`` and ``r_R``, the exact linear-element norm is
    ``L * (m**2 + h**2 / 3)``, where ``m=(r_L+r_R)/2`` and
    ``h=(r_R-r_L)/2``.  The second non-negative term exposes variation that a
    midpoint diagnostic cannot see.  Adjacent endpoint jumps additionally
    diagnose the discontinuous Neumann trace used by the linear BEM.
    """

    length = np.asarray(panel_length, dtype=float)
    endpoint = np.asarray(residual_endpoint, dtype=float)
    midpoint = np.asarray(residual_midpoint, dtype=float)
    if endpoint.shape != (len(length), 2) or midpoint.shape != length.shape:
        raise ValueError("Endpoint residual diagnostics have incompatible shapes.")
    if (
        len(length) < 2
        or not all(np.isfinite(item).all() for item in (length, endpoint, midpoint))
        or np.any(length <= 0.0)
    ):
        raise ValueError(
            "Endpoint residual diagnostics require finite data and two positive panels."
        )
    average = 0.5 * (endpoint[:, 0] + endpoint[:, 1])
    half_difference = 0.5 * (endpoint[:, 1] - endpoint[:, 0])
    average_integral = float(np.sum(length * np.square(average)))
    slope_integral = float(np.sum(length * np.square(half_difference) / 3.0))
    exact_integral = average_integral + slope_integral
    midpoint_integral = float(np.sum(length * np.square(midpoint)))
    average_scale = max(float(np.linalg.norm(average)), np.finfo(float).eps)
    jump = endpoint[1:, 0] - endpoint[:-1, 1]
    dual_length = 0.5 * (length[:-1] + length[1:])
    jump_energy = float(np.sum(dual_length * np.square(jump)))

    def correlation(left: np.ndarray, right: np.ndarray) -> float:
        if np.std(left) <= np.finfo(float).eps or np.std(right) <= np.finfo(float).eps:
            return 0.0
        return float(np.corrcoef(left, right)[0, 1])

    return {
        "endpoint_average_integral": average_integral,
        "within_panel_slope_integral": slope_integral,
        "exact_integral": exact_integral,
        "midpoint_integral": midpoint_integral,
        "slope_fraction_of_exact": slope_integral / max(
            exact_integral, np.finfo(float).eps
        ),
        "midpoint_to_endpoint_average_relative_l2": float(
            np.linalg.norm(midpoint - average) / average_scale
        ),
        "opposite_sign_arclength_fraction": float(
            np.sum(length[endpoint[:, 0] * endpoint[:, 1] < 0.0])
            / np.sum(length)
        ),
        "within_panel_left_right_correlation": correlation(
            endpoint[:, 0], endpoint[:, 1]
        ),
        "adjacent_endpoint_correlation": correlation(
            endpoint[:-1, 1], endpoint[1:, 0]
        ),
        "adjacent_endpoint_jump_energy": jump_energy,
        "adjacent_endpoint_jump_energy_to_exact": jump_energy
        / max(exact_integral, np.finfo(float).eps),
        "discontinuous_trace_dominates": slope_integral
        > 0.5 * exact_integral,
    }


def continuous_geometry_normal_residual_endpoint(coupled: object) -> np.ndarray:
    """Reproject endpoint ``grad(S)`` onto angle-bisector geometry normals.

    Linear panels have a two-sided normal at every interior geometry node.
    This diagnostic reconstructs the endpoint velocity from the panel
    tangential potential derivative and solved endpoint flux, then projects
    ``grad(phi)-x`` onto one continuous angle-bisector normal per outer node.
    It changes neither the BIE solution nor the formal acceptance metric.
    """

    boundary = coupled.boundary
    labels = np.asarray(boundary.panel_labels, dtype=object)
    outer_index = np.flatnonzero(labels == "outer_free_surface")
    if len(outer_index) < 2 or not np.array_equal(
        outer_index[1:], outer_index[:-1] + 1
    ):
        raise ValueError("Continuous-normal diagnosis requires a contiguous outer chain.")
    solved_q = getattr(coupled, "normal_derivative_endpoint", None)
    if solved_q is None:
        raise ValueError("Continuous-normal diagnosis requires endpoint fluxes.")
    solved_q = np.asarray(solved_q, dtype=float)
    if solved_q.shape != (boundary.panel_count, 2) or not np.isfinite(solved_q).all():
        raise ValueError("Continuous-normal endpoint fluxes must be finite.")

    outer = coupled.outer_free_surface
    node_position = np.column_stack((outer.node_xi, outer.node_eta))
    if node_position.shape != (len(outer_index) + 1, 2):
        raise ValueError("Outer geometry and boundary panel counts disagree.")
    tau = float(outer.tau_star) + np.asarray(outer.arc_length, dtype=float)
    node_phi = 0.5 * (np.sum(np.square(node_position), axis=1) - np.square(tau))
    panel_length = np.asarray(boundary.panel_length_m[outer_index], dtype=float)
    panel_tangent = np.asarray(boundary.panel_tangent[outer_index], dtype=float)
    panel_normal = np.asarray(boundary.panel_normal[outer_index], dtype=float)
    tangential_derivative = np.diff(node_phi) / panel_length

    node_normal = np.empty((len(outer_index) + 1, 2), dtype=float)
    node_normal[0] = panel_normal[0]
    node_normal[-1] = panel_normal[-1]
    node_normal[1:-1] = panel_normal[:-1] + panel_normal[1:]
    normal_norm = np.linalg.norm(node_normal, axis=1)
    if np.any(normal_norm <= np.finfo(float).eps):
        raise ValueError("Continuous geometry normal is undefined at a folded node.")
    node_normal /= normal_norm[:, None]

    residual = np.empty((len(outer_index), 2), dtype=float)
    for endpoint in (0, 1):
        velocity = (
            tangential_derivative[:, None] * panel_tangent
            + solved_q[outer_index, endpoint, None] * panel_normal
        )
        gradient_s = velocity - node_position[
            np.arange(len(outer_index)) + endpoint
        ]
        residual[:, endpoint] = np.sum(
            gradient_s
            * node_normal[np.arange(len(outer_index)) + endpoint],
            axis=1,
        )
    return residual


def similarity_tangential_identity(coupled: object) -> dict[str, np.ndarray | float]:
    """Audit the source-defined outer-free-surface identity ``S_tau=-tau``."""

    boundary = coupled.boundary
    labels = np.asarray(boundary.panel_labels, dtype=object)
    outer_index = np.flatnonzero(labels == "outer_free_surface")
    outer = coupled.outer_free_surface
    length = np.asarray(boundary.panel_length_m[outer_index], dtype=float)
    arc = np.asarray(outer.arc_length, dtype=float)
    if len(outer_index) < 2 or arc.shape != (len(outer_index) + 1,):
        raise ValueError("Tangential identity requires a resolved outer chain.")
    tau_node = float(outer.tau_star) + arc
    tau_mid = 0.5 * (tau_node[:-1] + tau_node[1:])
    node_position = np.column_stack((outer.node_xi, outer.node_eta))
    node_phi = 0.5 * (np.sum(np.square(node_position), axis=1) - np.square(tau_node))
    midpoint = np.column_stack(
        (
            boundary.panel_mid_y_m[outer_index],
            boundary.panel_mid_z_up_m[outer_index],
        )
    )
    tangent = np.asarray(boundary.panel_tangent[outer_index], dtype=float)
    element_s_tau = np.diff(node_phi) / length - np.sum(midpoint * tangent, axis=1)
    element_residual = element_s_tau + tau_mid

    panel_velocity = np.asarray(coupled.panel_velocity, dtype=float)
    if panel_velocity.shape != (boundary.panel_count, 2):
        raise ValueError("Tangential identity requires one velocity per panel.")
    recovered_s_tau = np.sum(
        (panel_velocity[outer_index] - midpoint) * tangent,
        axis=1,
    )
    recovered_residual = recovered_s_tau + tau_mid
    jet_root_s_tau = float(coupled.jet_interface.root_state.s_tau)
    expected_root_s_tau = -float(outer.tau_star)
    return {
        "tau_mid": tau_mid,
        "element_s_tau": element_s_tau,
        "element_residual": element_residual,
        "recovered_s_tau": recovered_s_tau,
        "recovered_residual": recovered_residual,
        "element_integral": float(np.sum(np.square(element_residual) * length)),
        "recovered_integral": float(np.sum(np.square(recovered_residual) * length)),
        "recovered_max_abs": float(np.max(np.abs(recovered_residual))),
        "root_expected_s_tau": expected_root_s_tau,
        "root_jet_s_tau": jet_root_s_tau,
        "root_absolute_mismatch": abs(jet_root_s_tau - expected_root_s_tau),
    }


def node_pseudo_velocity_similarity_identity(
    panel_length: np.ndarray,
    panel_tangent: np.ndarray,
    panel_normal: np.ndarray,
    tau_node: np.ndarray,
    node_gradient_s: np.ndarray,
) -> dict[str, np.ndarray | float]:
    """Audit the actual nodal pseudo velocity against both similarity conditions."""

    length = np.asarray(panel_length, dtype=float)
    tangent = np.asarray(panel_tangent, dtype=float)
    normal = np.asarray(panel_normal, dtype=float)
    tau = np.asarray(tau_node, dtype=float)
    gradient = np.asarray(node_gradient_s, dtype=float)
    panel_count = len(length)
    if (
        tangent.shape != (panel_count, 2)
        or normal.shape != (panel_count, 2)
        or tau.shape != (panel_count + 1,)
        or gradient.shape != (panel_count + 1, 2)
    ):
        raise ValueError("Nodal pseudo-velocity identity arrays have inconsistent shapes.")
    if not all(
        np.isfinite(item).all()
        for item in (length, tangent, normal, tau, gradient)
    ) or np.any(length <= 0.0):
        raise ValueError("Nodal pseudo-velocity identity arrays must be finite and resolved.")

    node_tangent = np.empty((panel_count + 1, 2), dtype=float)
    node_normal = np.empty((panel_count + 1, 2), dtype=float)
    node_tangent[[0, -1]] = tangent[[0, -1]]
    node_normal[[0, -1]] = normal[[0, -1]]
    node_tangent[1:-1] = tangent[:-1] + tangent[1:]
    node_normal[1:-1] = normal[:-1] + normal[1:]
    tangent_norm = np.linalg.norm(node_tangent, axis=1)
    normal_norm = np.linalg.norm(node_normal, axis=1)
    if np.any(tangent_norm <= np.finfo(float).eps) or np.any(
        normal_norm <= np.finfo(float).eps
    ):
        raise ValueError("Nodal pseudo-velocity directions are undefined at a fold.")
    node_tangent /= tangent_norm[:, None]
    node_normal /= normal_norm[:, None]

    tangential_residual = np.sum(gradient * node_tangent, axis=1) + tau
    normal_residual = np.sum(gradient * node_normal, axis=1)

    def linear_integral(node_value: np.ndarray) -> float:
        return float(
            np.sum(
                length
                * (
                    np.square(node_value[:-1])
                    + node_value[:-1] * node_value[1:]
                    + np.square(node_value[1:])
                )
                / 3.0
            )
        )

    return {
        "tangential_residual": tangential_residual,
        "normal_residual": normal_residual,
        "tangential_integral": linear_integral(tangential_residual),
        "normal_integral": linear_integral(normal_residual),
        "tangential_max_abs": float(np.max(np.abs(tangential_residual))),
        "normal_max_abs": float(np.max(np.abs(normal_residual))),
    }


def kinematic_residual_frame(coupled: object) -> pd.DataFrame:
    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    outer = labels == "outer_free_surface"
    length = np.asarray(coupled.boundary.panel_length_m[outer], dtype=float)
    residual = np.asarray(coupled.outer_kinematic_residual, dtype=float)
    if residual.shape != length.shape or len(length) < 4:
        raise ValueError("Outer kinematic residual requires at least four panels.")
    contribution = np.square(residual) * length
    total = float(np.sum(contribution))
    if not np.isfinite(total) or total <= 0.0:
        raise ValueError("Iafrati Eq. (52) panel contributions must have a positive sum.")
    arc_end = np.cumsum(length)
    arc_start = np.concatenate(([0.0], arc_end[:-1]))
    arc_mid = 0.5 * (arc_start + arc_end)
    data: dict[str, np.ndarray] = {
            "outer_panel_index": np.arange(len(length), dtype=int),
            "xi_mid": coupled.boundary.panel_mid_y_m[outer],
            "eta_mid": coupled.boundary.panel_mid_z_up_m[outer],
            "panel_length": length,
            "arc_mid": arc_mid,
            "normalized_arc_mid": arc_mid / arc_end[-1],
            "s_nu": residual,
            "k_contribution": contribution,
            "k_fraction": contribution / total,
            "cumulative_k_fraction": np.cumsum(contribution) / total,
    }
    if (
        getattr(coupled, "panel_velocity", None) is not None
        and getattr(coupled, "outer_free_surface", None) is not None
        and getattr(coupled, "jet_interface", None) is not None
    ):
        tangential = similarity_tangential_identity(coupled)
        data["tau_mid"] = np.asarray(tangential["tau_mid"], dtype=float)
        data["s_tau_element"] = np.asarray(
            tangential["element_s_tau"], dtype=float
        )
        data["s_tau_element_identity_residual"] = np.asarray(
            tangential["element_residual"], dtype=float
        )
        data["s_tau_recovered"] = np.asarray(
            tangential["recovered_s_tau"], dtype=float
        )
        data["s_tau_recovered_identity_residual"] = np.asarray(
            tangential["recovered_residual"], dtype=float
        )
        outer_index = np.flatnonzero(labels == "outer_free_surface")
        outer = coupled.outer_free_surface
        node_identity = node_pseudo_velocity_similarity_identity(
            length,
            coupled.boundary.panel_tangent[outer_index],
            coupled.boundary.panel_normal[outer_index],
            float(outer.tau_star) + np.asarray(outer.arc_length, dtype=float),
            _coupled_outer_pseudo_velocity(coupled),
        )
        node_tangential = np.asarray(
            node_identity["tangential_residual"], dtype=float
        )
        node_normal = np.asarray(node_identity["normal_residual"], dtype=float)
        data["node_pseudo_tangential_residual_left"] = node_tangential[:-1]
        data["node_pseudo_tangential_residual_right"] = node_tangential[1:]
        data["node_pseudo_normal_residual_left"] = node_normal[:-1]
        data["node_pseudo_normal_residual_right"] = node_normal[1:]
    endpoint = getattr(coupled, "outer_kinematic_residual_endpoint", None)
    if endpoint is not None:
        endpoint = np.asarray(endpoint, dtype=float)
        if endpoint.shape != (len(length), 2) or not np.isfinite(endpoint).all():
            raise ValueError("Outer endpoint residuals must contain two finite values per panel.")
        exact_contribution = length * (
            np.square(endpoint[:, 0])
            + endpoint[:, 0] * endpoint[:, 1]
            + np.square(endpoint[:, 1])
        ) / 3.0
        data["s_nu_left"] = endpoint[:, 0]
        data["s_nu_right"] = endpoint[:, 1]
        data["k_contribution_linear_exact"] = exact_contribution
        endpoint_average = 0.5 * (endpoint[:, 0] + endpoint[:, 1])
        endpoint_half_difference = 0.5 * (endpoint[:, 1] - endpoint[:, 0])
        data["k_contribution_endpoint_average"] = (
            length * np.square(endpoint_average)
        )
        data["k_contribution_within_panel_slope"] = (
            length * np.square(endpoint_half_difference) / 3.0
        )
        projected, _, _, _ = continuous_linear_weak_projection(length, endpoint)
        projected_endpoint = np.column_stack((projected[:-1], projected[1:]))
        projected_contribution = length * (
            np.square(projected_endpoint[:, 0])
            + projected_endpoint[:, 0] * projected_endpoint[:, 1]
            + np.square(projected_endpoint[:, 1])
        ) / 3.0
        data["s_nu_weak_projected_left"] = projected_endpoint[:, 0]
        data["s_nu_weak_projected_right"] = projected_endpoint[:, 1]
        data["k_contribution_weak_projected"] = projected_contribution
        data["k_contribution_weak_projection_error"] = (
            continuous_linear_projection_error_contribution(
                length,
                endpoint,
                projected,
            )
        )
        endpoint_jump = np.full(len(length), np.nan, dtype=float)
        endpoint_jump[:-1] = endpoint[1:, 0] - endpoint[:-1, 1]
        data["s_nu_endpoint_jump_to_next"] = endpoint_jump
        if getattr(coupled, "normal_derivative_endpoint", None) is not None:
            continuous_normal = continuous_geometry_normal_residual_endpoint(
                coupled
            )
            continuous_normal_contribution = length * (
                np.square(continuous_normal[:, 0])
                + continuous_normal[:, 0] * continuous_normal[:, 1]
                + np.square(continuous_normal[:, 1])
            ) / 3.0
            data["s_nu_continuous_normal_left"] = continuous_normal[:, 0]
            data["s_nu_continuous_normal_right"] = continuous_normal[:, 1]
            data["k_contribution_continuous_normal_exact"] = (
                continuous_normal_contribution
            )
    return pd.DataFrame(data)


def kinematic_residual_summary(
    frame: pd.DataFrame,
    *,
    source_hashes: dict[str, str],
    expected_integral: float,
    free_surface_update: str = "full_gradient",
) -> dict[str, object]:
    contribution = frame["k_contribution"].to_numpy(dtype=float)
    reconstructed = float(np.sum(contribution))
    scale = max(abs(float(expected_integral)), np.finfo(float).eps)
    relative_error = abs(reconstructed - float(expected_integral)) / scale
    if relative_error > 1.0e-10:
        raise ValueError("Panel contributions do not reconstruct Iafrati Eq. (52) K.")
    root_count = min(2, len(frame))
    far_count = min(8, max(len(frame) - root_count, 1))
    interior_start = root_count
    interior_stop = len(frame) - far_count
    deciles: list[dict[str, float]] = []
    normalized = frame["normalized_arc_mid"].to_numpy(dtype=float)
    for index in range(10):
        lower = 0.1 * index
        upper = 0.1 * (index + 1)
        mask = (normalized >= lower) & (
            (normalized < upper) if index < 9 else (normalized <= upper)
        )
        value = float(np.sum(contribution[mask]))
        deciles.append(
            {
                "normalized_arc_lower": lower,
                "normalized_arc_upper": upper,
                "k_contribution": value,
                "k_fraction": value / reconstructed,
            }
        )
    result: dict[str, object] = {
        "status": "self_similar_kinematic_residual_localization_diagnostic",
        "validated": False,
        "reference_used": False,
        "metric": "Iafrati 2013 Eq. (52), K = integral(S_nu^2 ds)",
        "source_hashes": source_hashes,
        "panel_count": len(frame),
        "kinematic_integral": reconstructed,
        "reconstruction_relative_error": relative_error,
        "root_first_two_panels": {
            "k_contribution": float(np.sum(contribution[:root_count])),
            "k_fraction": float(np.sum(contribution[:root_count]) / reconstructed),
        },
        "interior_excluding_root2_far8": {
            "k_contribution": float(
                np.sum(contribution[interior_start:interior_stop])
            ),
            "k_fraction": float(
                np.sum(contribution[interior_start:interior_stop]) / reconstructed
            ),
        },
        "far_last_eight_panels": {
            "k_contribution": float(np.sum(contribution[-far_count:])),
            "k_fraction": float(np.sum(contribution[-far_count:]) / reconstructed),
        },
        "arc_deciles": deciles,
    }
    if "k_contribution_linear_exact" in frame:
        exact_contribution = frame["k_contribution_linear_exact"].to_numpy(
            dtype=float
        )
        exact = float(np.sum(exact_contribution))
        result["kinematic_integral_linear_exact"] = exact
        result["linear_exact_to_midpoint_ratio"] = exact / reconstructed
        endpoint_diagnostics = linear_endpoint_residual_diagnostics(
            frame["panel_length"].to_numpy(dtype=float),
            frame[["s_nu_left", "s_nu_right"]].to_numpy(dtype=float),
            frame["s_nu"].to_numpy(dtype=float),
        )
        result["linear_element_residual_decomposition"] = endpoint_diagnostics
        result["linear_exact_regions"] = {
            "root_first_two_panels": float(
                np.sum(exact_contribution[:root_count])
            ),
            "interior_excluding_root2_far8": float(
                np.sum(exact_contribution[interior_start:interior_stop])
            ),
            "far_last_eight_panels": float(
                np.sum(exact_contribution[-far_count:])
            ),
        }
        weak_contribution = frame[
            "k_contribution_weak_projected"
        ].to_numpy(dtype=float)
        weak_integral = float(np.sum(weak_contribution))
        unresolved = max(0.0, exact - weak_integral)
        window = min(16, max(len(frame) // 3, 1))
        interior_window = slice(window, len(frame) - window)
        result["continuous_p1_weak_projection"] = {
            "kinematic_integral": weak_integral,
            "fraction_of_linear_exact": weak_integral / exact,
            "unresolved_integral": unresolved,
            "unresolved_fraction_of_linear_exact": unresolved / exact,
        }
        result["linear_exact_regions_panel_windows"] = {
            "root_first_two_panels": float(np.sum(exact_contribution[:root_count])),
            "root_first_window_panels": {
                "panel_count": window,
                "kinematic_integral": float(np.sum(exact_contribution[:window])),
            },
            "interior_excluding_endpoint_windows": {
                "endpoint_window_panel_count": window,
                "kinematic_integral": float(
                    np.sum(exact_contribution[interior_window])
                ),
            },
            "far_last_window_panels": {
                "panel_count": window,
                "kinematic_integral": float(np.sum(exact_contribution[-window:])),
            },
        }
        result["weak_projected_regions_panel_windows"] = {
            "root_first_window_panels": float(np.sum(weak_contribution[:window])),
            "interior_excluding_endpoint_windows": float(
                np.sum(weak_contribution[interior_window])
            ),
            "far_last_window_panels": float(np.sum(weak_contribution[-window:])),
        }
        projection_error = frame[
            "k_contribution_weak_projection_error"
        ].to_numpy(dtype=float)
        if not np.isclose(
            np.sum(projection_error),
            unresolved,
            rtol=1.0e-10,
            atol=1.0e-14,
        ):
            raise ValueError(
                "Panelwise weak-projection error does not reconstruct the "
                "orthogonal unresolved integral."
            )
        error_deciles: list[dict[str, float]] = []
        for index in range(10):
            lower = 0.1 * index
            upper = 0.1 * (index + 1)
            mask = (normalized >= lower) & (
                (normalized < upper) if index < 9 else (normalized <= upper)
            )
            value = float(np.sum(projection_error[mask]))
            error_deciles.append(
                {
                    "normalized_arc_lower": lower,
                    "normalized_arc_upper": upper,
                    "projection_error_integral": value,
                    "projection_error_fraction": (
                        0.0 if unresolved == 0.0 else value / unresolved
                    ),
                }
            )
        result["weak_projection_error_regions"] = {
            "root_first_window_panels": float(np.sum(projection_error[:window])),
            "interior_excluding_endpoint_windows": float(
                np.sum(projection_error[interior_window])
            ),
            "far_last_window_panels": float(np.sum(projection_error[-window:])),
            "arc_deciles": error_deciles,
        }
        slope_contribution = frame[
            "k_contribution_within_panel_slope"
        ].to_numpy(dtype=float)
        slope_total = float(np.sum(slope_contribution))
        result["within_panel_slope_regions"] = {
            "root_first_window_panels": float(np.sum(slope_contribution[:window])),
            "interior_excluding_endpoint_windows": float(
                np.sum(slope_contribution[interior_window])
            ),
            "far_last_window_panels": float(np.sum(slope_contribution[-window:])),
            "root_first_arc_decile_fraction": float(
                np.sum(slope_contribution[normalized < 0.1])
                / max(slope_total, np.finfo(float).eps)
            ),
        }
        if "k_contribution_continuous_normal_exact" in frame:
            continuous_normal_contribution = frame[
                "k_contribution_continuous_normal_exact"
            ].to_numpy(dtype=float)
            continuous_normal_integral = float(
                np.sum(continuous_normal_contribution)
            )
            result["continuous_geometry_normal"] = {
                "kinematic_integral": continuous_normal_integral,
                "ratio_to_panel_normal_linear_exact": (
                    continuous_normal_integral / exact
                ),
                "relative_change_from_panel_normal": (
                    abs(continuous_normal_integral - exact) / exact
                ),
                "root_first_window_panels": float(
                    np.sum(continuous_normal_contribution[:window])
                ),
                "interior_excluding_endpoint_windows": float(
                    np.sum(continuous_normal_contribution[interior_window])
                ),
                "far_last_window_panels": float(
                    np.sum(continuous_normal_contribution[-window:])
                ),
            }
    if "s_tau_recovered_identity_residual" in frame:
        length = frame["panel_length"].to_numpy(dtype=float)
        element_residual = frame[
            "s_tau_element_identity_residual"
        ].to_numpy(dtype=float)
        recovered_residual = frame[
            "s_tau_recovered_identity_residual"
        ].to_numpy(dtype=float)
        result["tangential_similarity_identity"] = {
            "definition": "S_tau + tau = 0 on the outer free surface",
            "element_integral": float(
                np.sum(np.square(element_residual) * length)
            ),
            "element_max_abs": float(np.max(np.abs(element_residual))),
            "recovered_integral": float(
                np.sum(np.square(recovered_residual) * length)
            ),
            "recovered_max_abs": float(np.max(np.abs(recovered_residual))),
        }
    if "node_pseudo_tangential_residual_left" in frame:
        length = frame["panel_length"].to_numpy(dtype=float)

        def endpoint_integral(left_name: str, right_name: str) -> float:
            left = frame[left_name].to_numpy(dtype=float)
            right = frame[right_name].to_numpy(dtype=float)
            return float(
                np.sum(
                    length
                    * (np.square(left) + left * right + np.square(right))
                    / 3.0
                )
            )

        tangential_left = frame[
            "node_pseudo_tangential_residual_left"
        ].to_numpy(dtype=float)
        tangential_right = frame[
            "node_pseudo_tangential_residual_right"
        ].to_numpy(dtype=float)
        normal_left = frame[
            "node_pseudo_normal_residual_left"
        ].to_numpy(dtype=float)
        normal_right = frame[
            "node_pseudo_normal_residual_right"
        ].to_numpy(dtype=float)
        result["actual_node_pseudo_velocity_identity"] = {
            "free_surface_update": free_surface_update,
            "tangential_identity_applicable": (
                free_surface_update == "full_gradient"
            ),
            "tangential_gauge_note": (
                "S_tau + tau applies to the full-gradient material update. "
                "The continuous-normal shape update deliberately sets the "
                "tangential gauge to zero and delegates node spacing to regridding."
            ),
            "tangential_integral": endpoint_integral(
                "node_pseudo_tangential_residual_left",
                "node_pseudo_tangential_residual_right",
            ),
            "normal_integral": endpoint_integral(
                "node_pseudo_normal_residual_left",
                "node_pseudo_normal_residual_right",
            ),
            "tangential_max_abs": float(
                max(np.max(np.abs(tangential_left)), np.max(np.abs(tangential_right)))
            ),
            "normal_max_abs": float(
                max(np.max(np.abs(normal_left)), np.max(np.abs(normal_right)))
            ),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Localize panel contributions to Iafrati Eq. (52) K."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", type=Path)
    source.add_argument(
        "--artifact-dir",
        type=Path,
        help="Analyze coupled_outer_kinematic_residual.csv without a checkpoint.",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.run is not None:
        checkpoint = load_coupled_self_similar_checkpoint(args.run)
        frame = kinematic_residual_frame(checkpoint.coupled)
        source_hashes = checkpoint.source_hashes
        expected_integral = checkpoint.coupled.kinematic_integral
        free_surface_update = checkpoint.coupled.config.coupled_free_surface_update
    else:
        artifact = args.artifact_dir.resolve()
        residual_path = artifact / "coupled_outer_kinematic_residual.csv"
        source_frame = pd.read_csv(residual_path)
        required = {
            "panel_index",
            "mid_xi",
            "mid_eta",
            "panel_length",
            "kinematic_residual_midpoint",
            "kinematic_residual_left",
            "kinematic_residual_right",
        }
        missing = required.difference(source_frame.columns)
        if missing:
            raise ValueError(
                "Artifact residual table is missing columns: "
                + ", ".join(sorted(missing))
            )
        length = source_frame["panel_length"].to_numpy(dtype=float)
        residual = source_frame["kinematic_residual_midpoint"].to_numpy(dtype=float)
        endpoint = source_frame[
            ["kinematic_residual_left", "kinematic_residual_right"]
        ].to_numpy(dtype=float)
        arc_end = np.cumsum(length)
        arc_start = np.concatenate(([0.0], arc_end[:-1]))
        arc_mid = 0.5 * (arc_start + arc_end)
        midpoint_contribution = np.square(residual) * length
        midpoint_total = float(np.sum(midpoint_contribution))
        projected, _, _, _ = continuous_linear_weak_projection(length, endpoint)
        projected_endpoint = np.column_stack((projected[:-1], projected[1:]))
        exact_contribution = length * (
            np.square(endpoint[:, 0])
            + endpoint[:, 0] * endpoint[:, 1]
            + np.square(endpoint[:, 1])
        ) / 3.0
        projected_contribution = length * (
            np.square(projected_endpoint[:, 0])
            + projected_endpoint[:, 0] * projected_endpoint[:, 1]
            + np.square(projected_endpoint[:, 1])
        ) / 3.0
        endpoint_jump = np.full(len(length), np.nan, dtype=float)
        endpoint_jump[:-1] = endpoint[1:, 0] - endpoint[:-1, 1]
        endpoint_average = 0.5 * (endpoint[:, 0] + endpoint[:, 1])
        endpoint_half_difference = 0.5 * (endpoint[:, 1] - endpoint[:, 0])
        frame = pd.DataFrame(
            {
                "outer_panel_index": source_frame["panel_index"].to_numpy(dtype=int),
                "xi_mid": source_frame["mid_xi"].to_numpy(dtype=float),
                "eta_mid": source_frame["mid_eta"].to_numpy(dtype=float),
                "panel_length": length,
                "arc_mid": arc_mid,
                "normalized_arc_mid": arc_mid / arc_end[-1],
                "s_nu": residual,
                "k_contribution": midpoint_contribution,
                "k_fraction": midpoint_contribution / midpoint_total,
                "cumulative_k_fraction": np.cumsum(midpoint_contribution)
                / midpoint_total,
                "s_nu_left": endpoint[:, 0],
                "s_nu_right": endpoint[:, 1],
                "k_contribution_linear_exact": exact_contribution,
                "k_contribution_endpoint_average": (
                    length * np.square(endpoint_average)
                ),
                "k_contribution_within_panel_slope": (
                    length * np.square(endpoint_half_difference) / 3.0
                ),
                "s_nu_weak_projected_left": projected_endpoint[:, 0],
                "s_nu_weak_projected_right": projected_endpoint[:, 1],
                "k_contribution_weak_projected": projected_contribution,
                "k_contribution_weak_projection_error": (
                    continuous_linear_projection_error_contribution(
                        length, endpoint, projected
                    )
                ),
                "s_nu_endpoint_jump_to_next": endpoint_jump,
            }
        )
        digest = hashlib.sha256(residual_path.read_bytes()).hexdigest()
        source_hashes = {residual_path.name: digest}
        expected_integral = midpoint_total
        free_surface_update = "artifact_unknown"
    summary = kinematic_residual_summary(
        frame,
        source_hashes=source_hashes,
        expected_integral=expected_integral,
        free_surface_update=free_surface_update,
    )
    frame.to_csv(output / "kinematic_residual_by_panel.csv", index=False)
    (output / "kinematic_residual_localization.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), constrained_layout=True)
    axes[0].plot(frame["normalized_arc_mid"], frame["s_nu"], "o-", ms=2.5, label="midpoint")
    if "s_nu_weak_projected_left" in frame:
        projected_midpoint = 0.5 * (
            frame["s_nu_weak_projected_left"]
            + frame["s_nu_weak_projected_right"]
        )
        axes[0].plot(
            frame["normalized_arc_mid"],
            projected_midpoint,
            "-",
            lw=1.2,
            label="continuous P1 weak projection",
        )
    axes[0].axhline(0.0, color="black", lw=0.8)
    axes[0].set(xlabel="Normalized outer arc", ylabel=r"$S_\nu$")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend()
    axes[1].semilogy(
        frame["normalized_arc_mid"],
        frame["k_contribution"],
        "o-",
        ms=2.5,
    )
    if "k_contribution_weak_projected" in frame:
        axes[1].semilogy(
            frame["normalized_arc_mid"],
            frame["k_contribution_weak_projected"],
            "-",
            lw=1.2,
            label="weak projected",
        )
    axes[1].set(xlabel="Normalized outer arc", ylabel="Panel contribution to K")
    axes[1].grid(True, which="both", alpha=0.25)
    axes[1].legend()
    figure.savefig(output / "kinematic_residual_localization.png", dpi=180)
    plt.close(figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
