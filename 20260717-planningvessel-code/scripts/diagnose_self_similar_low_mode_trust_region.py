from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Callable

import numpy as np
import pandas as pd
from scipy.fft import dct, idct


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    coupled_pseudo_time_history_frame,
    load_coupled_self_similar_checkpoint,
    write_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    _build_coupled_solution_from_outer_nodes,
    _build_coupled_solution_with_compatible_root,
    _constrain_coupled_outer_nodes,
    _regrid_coupled_outer_nodes,
    derive_shallow_water_jet_root_state_from_coupled,
    solve_coupled_self_similar_wedge_pseudo_time,
)
from scripts.analyze_self_similar_kinematic_residual import (
    continuous_linear_weak_projection,
)
from scripts.diagnose_self_similar_low_mode_line_search import (
    angle_bisector_normals,
    maximum_midpoint_displacement_ratio,
    trial_rejection_reason,
)
from scripts.resume_self_similar_wedge import _write_final_artifacts


@dataclass(frozen=True)
class TrustRegionTrial:
    iteration: int
    step_factor: float
    exact_objective: float
    exact_relative_decrease: float
    low_mode_objective: float
    predicted_low_mode_objective: float
    trust_ratio: float
    maximum_displacement_ratio: float
    condition_number: float
    condition_number_ratio: float
    dipole_coefficient: float
    root_relative_mismatch: float
    curvature_energy: float
    curvature_energy_ratio: float
    maximum_turning_angle_deg: float
    accepted: bool
    rejection_reason: str


def root_feasibility_gate_limit(
    source_root_mismatch: float,
    hard_root_limit: float,
) -> float:
    """Enforce the hard limit or monotonic repair of an infeasible source."""

    source = float(source_root_mismatch)
    hard = float(hard_root_limit)
    if not np.isfinite(source) or source < 0.0 or not np.isfinite(hard) or hard <= 0.0:
        raise ValueError("Root mismatch and hard limit must be finite and admissible.")
    return hard if source <= hard else source


def admissible_one_sided_difference(
    source_residual: np.ndarray,
    epsilon: float,
    residual_at_displacement: Callable[[float], np.ndarray],
) -> tuple[np.ndarray, float]:
    """Return a feasible signed one-sided derivative.

    A low-mode perturbation can cross the shallow-jet physical boundary even
    when the source state is admissible.  Try the positive direction first and
    then the equal negative direction.  The signed denominator is retained so
    the fallback does not silently reverse the Jacobian column.
    """

    base = np.asarray(source_residual, dtype=float)
    step = float(epsilon)
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("Finite-difference epsilon must be finite and positive.")
    errors: list[str] = []
    for sign in (1.0, -1.0):
        signed_step = sign * step
        try:
            perturbed = np.asarray(
                residual_at_displacement(signed_step),
                dtype=float,
            )
            if perturbed.shape != base.shape or not np.isfinite(perturbed).all():
                raise ValueError(
                    "Finite-difference residual must match the source and be finite."
                )
            return (perturbed - base) / signed_step, signed_step
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            errors.append(f"{sign:+g}:{type(error).__name__}:{error}")
    raise ValueError(
        "Both signed finite-difference perturbations are inadmissible: "
        + " | ".join(errors)
    )


def constrained_damped_gauss_newton_step(
    jacobian: np.ndarray,
    residual: np.ndarray,
    damping: float,
    constraint_gradient: np.ndarray,
    constraint_rhs: float = 0.0,
) -> np.ndarray:
    """Solve a damped Gauss-Newton step with one linear equality constraint."""

    matrix = np.asarray(jacobian, dtype=float)
    vector = np.asarray(residual, dtype=float)
    gradient = np.asarray(constraint_gradient, dtype=float)
    if matrix.ndim != 2 or vector.shape != (matrix.shape[0],):
        raise ValueError("Constrained Gauss-Newton inputs have incompatible shapes.")
    if gradient.shape != (matrix.shape[1],):
        raise ValueError("Constraint gradient must contain one value per mode.")
    if not np.isfinite(matrix).all() or not np.isfinite(vector).all():
        raise ValueError("Constrained Gauss-Newton inputs must be finite.")
    if not np.isfinite(gradient).all() or np.linalg.norm(gradient) <= np.finfo(float).eps:
        raise ValueError("Constraint gradient must be finite and non-zero.")
    regularization = float(damping)
    if not np.isfinite(regularization) or regularization < 0.0:
        raise ValueError("Gauss-Newton damping must be finite and non-negative.")
    normal = matrix.T @ matrix + regularization * np.eye(matrix.shape[1])
    right = -(matrix.T @ vector)
    kkt = np.block(
        [
            [normal, gradient[:, None]],
            [gradient[None, :], np.zeros((1, 1), dtype=float)],
        ]
    )
    solution = np.linalg.solve(
        kkt,
        np.concatenate((right, [float(constraint_rhs)])),
    )
    return solution[:-1]


def dct_nodal_basis(node_count: int, mode_count: int) -> np.ndarray:
    """Return orthonormal DCT-II nodal basis vectors as matrix columns."""

    nodes = int(node_count)
    modes = int(mode_count)
    if nodes < 2 or modes < 1 or modes > nodes:
        raise ValueError("DCT basis requires 1 <= mode_count <= node_count and two nodes.")
    coefficients = np.zeros((nodes, modes), dtype=float)
    coefficients[np.arange(modes), np.arange(modes)] = 1.0
    return idct(coefficients, type=2, axis=0, norm="ortho")


def linear_nodal_mass_matrix(panel_length: np.ndarray) -> np.ndarray:
    """Assemble the continuous-linear arc-length mass matrix."""

    length = np.asarray(panel_length, dtype=float)
    if length.ndim != 1 or len(length) < 1:
        raise ValueError("A nodal mass matrix requires at least one panel.")
    if not np.isfinite(length).all() or np.any(length <= 0.0):
        raise ValueError("Nodal mass-matrix panel lengths must be finite and positive.")
    matrix = np.zeros((len(length) + 1, len(length) + 1), dtype=float)
    for panel, value in enumerate(length):
        matrix[panel, panel] += value / 3.0
        matrix[panel + 1, panel + 1] += value / 3.0
        matrix[panel, panel + 1] += value / 6.0
        matrix[panel + 1, panel] += value / 6.0
    return matrix


def endpoint_local_nodal_basis(
    panel_length: np.ndarray,
    mode_count: int,
    *,
    global_mode_count: int = 2,
    support_fraction: float = 0.15,
    endpoint: str = "root",
) -> np.ndarray:
    """Return an arc-weighted basis with global and endpoint-local modes."""

    length = np.asarray(panel_length, dtype=float)
    modes = int(mode_count)
    global_modes = int(global_mode_count)
    support = float(support_fraction)
    endpoint_name = str(endpoint)
    if modes < 2 or not 1 <= global_modes < modes:
        raise ValueError(
            "Endpoint-local basis requires 1 <= global_mode_count < mode_count."
        )
    if not 0.0 < support <= 0.5:
        raise ValueError("Endpoint-local support_fraction must lie in (0, 0.5].")
    if endpoint_name not in {"root", "far"}:
        raise ValueError("Endpoint-local basis endpoint must be 'root' or 'far'.")
    mass = linear_nodal_mass_matrix(length)
    arc = np.concatenate(([0.0], np.cumsum(length)))
    arc /= arc[-1]
    local_arc = arc if endpoint_name == "root" else 1.0 - arc
    local_modes = modes - global_modes
    spacing = support / (local_modes + 1)
    centers = spacing * np.arange(local_modes, dtype=float)
    width = 1.5 * spacing
    local = np.column_stack(
        [
            np.maximum(1.0 - np.abs(local_arc - center) / width, 0.0)
            for center in centers
        ]
    )
    seed = np.column_stack(
        (dct_nodal_basis(len(arc), global_modes), local)
    )
    gram = seed.T @ mass @ seed
    try:
        factor = np.linalg.cholesky(gram)
    except np.linalg.LinAlgError as error:
        raise ValueError(
            "Endpoint-local shape basis is linearly dependent or ill-conditioned."
        ) from error
    basis = seed @ np.linalg.inv(factor.T)
    if not np.isfinite(basis).all():
        raise ValueError("Endpoint-local shape basis contains non-finite values.")
    orthogonality = basis.T @ mass @ basis
    if not np.allclose(
        orthogonality,
        np.eye(modes),
        rtol=1.0e-8,
        atol=1.0e-8,
    ):
        raise ValueError("Endpoint-local shape basis is numerically ill-conditioned.")
    return basis


def root_local_nodal_basis(
    panel_length: np.ndarray,
    mode_count: int,
    *,
    global_mode_count: int = 2,
    support_fraction: float = 0.15,
) -> np.ndarray:
    """Return global and compact modes around the shallow-jet root."""

    return endpoint_local_nodal_basis(
        panel_length,
        mode_count,
        global_mode_count=global_mode_count,
        support_fraction=support_fraction,
        endpoint="root",
    )


def endpoint_cosine_local_nodal_basis(
    panel_length: np.ndarray,
    mode_count: int,
    *,
    global_mode_count: int = 2,
    support_fraction: float = 0.15,
    endpoint: str = "root",
) -> np.ndarray:
    """Return smooth compact cosine modes resolved on the actual arc grid."""

    length = np.asarray(panel_length, dtype=float)
    modes = int(mode_count)
    global_modes = int(global_mode_count)
    support = float(support_fraction)
    endpoint_name = str(endpoint)
    if (
        length.ndim != 1
        or len(length) < 2
        or not np.isfinite(length).all()
        or np.any(length <= 0.0)
    ):
        raise ValueError("Cosine-local basis requires positive finite panel lengths.")
    if modes < 2 or not 1 <= global_modes < modes:
        raise ValueError(
            "Cosine-local basis requires 1 <= global_mode_count < mode_count."
        )
    if not 0.0 < support <= 0.5:
        raise ValueError("Cosine-local support_fraction must lie in (0, 0.5].")
    if endpoint_name not in {"root", "far"}:
        raise ValueError("Cosine-local endpoint must be 'root' or 'far'.")

    mass = linear_nodal_mass_matrix(length)
    arc = np.concatenate(([0.0], np.cumsum(length)))
    arc /= arc[-1]
    local_arc = arc if endpoint_name == "root" else 1.0 - arc
    local_modes = modes - global_modes
    resolved_nodes = int(np.count_nonzero(local_arc <= support))
    if local_modes > resolved_nodes:
        raise ValueError(
            "Cosine-local mode count exceeds the nodes resolved inside its support."
        )

    normalized = local_arc / support
    active = normalized <= 1.0
    window = np.zeros_like(normalized)
    window[active] = np.square(0.5 * (1.0 + np.cos(np.pi * normalized[active])))
    orders = np.arange(local_modes, dtype=float)
    local = window[:, None] * np.cos(
        np.pi * normalized[:, None] * orders[None, :]
    )
    seed = np.column_stack((dct_nodal_basis(len(arc), global_modes), local))

    factor = np.linalg.cholesky(mass)
    whitened = factor.T @ seed
    orthogonal, upper = np.linalg.qr(whitened, mode="reduced")
    diagonal = np.abs(np.diag(upper))
    tolerance = max(seed.shape) * np.finfo(float).eps * max(
        float(np.max(diagonal, initial=0.0)), 1.0
    )
    if len(diagonal) != modes or np.any(diagonal <= tolerance):
        raise ValueError("Cosine-local shape basis is linearly dependent.")
    signs = np.where(np.diag(upper) < 0.0, -1.0, 1.0)
    orthogonal *= signs[None, :]
    basis = np.linalg.solve(factor.T, orthogonal)
    if not np.isfinite(basis).all() or not np.allclose(
        basis.T @ mass @ basis,
        np.eye(modes),
        rtol=1.0e-8,
        atol=1.0e-8,
    ):
        raise ValueError("Cosine-local shape basis is numerically ill-conditioned.")
    return basis


def root_cosine_local_nodal_basis(
    panel_length: np.ndarray,
    mode_count: int,
    *,
    global_mode_count: int = 2,
    support_fraction: float = 0.15,
) -> np.ndarray:
    """Return smooth global and compact cosine modes near the spray root."""

    return endpoint_cosine_local_nodal_basis(
        panel_length,
        mode_count,
        global_mode_count=global_mode_count,
        support_fraction=support_fraction,
        endpoint="root",
    )


def far_local_nodal_basis(
    panel_length: np.ndarray,
    mode_count: int,
    *,
    global_mode_count: int = 2,
    support_fraction: float = 0.15,
) -> np.ndarray:
    """Return global and compact modes around the far-field endpoint."""

    return endpoint_local_nodal_basis(
        panel_length,
        mode_count,
        global_mode_count=global_mode_count,
        support_fraction=support_fraction,
        endpoint="far",
    )


def dual_endpoint_local_nodal_basis(
    panel_length: np.ndarray,
    mode_count: int,
    *,
    global_mode_count: int = 2,
    support_fraction: float = 0.15,
) -> np.ndarray:
    """Return global modes plus compact modes at both arc endpoints."""

    length = np.asarray(panel_length, dtype=float)
    modes = int(mode_count)
    global_modes = int(global_mode_count)
    support = float(support_fraction)
    local_modes = modes - global_modes
    if modes < 3 or not 1 <= global_modes < modes - 1:
        raise ValueError(
            "Dual-endpoint basis requires at least one local mode per endpoint."
        )
    if not 0.0 < support <= 0.5:
        raise ValueError("Dual-endpoint support_fraction must lie in (0, 0.5].")
    if length.ndim != 1 or len(length) < 1:
        raise ValueError("Dual-endpoint basis requires at least one panel.")
    if not np.isfinite(length).all() or np.any(length <= 0.0):
        raise ValueError(
            "Dual-endpoint panel lengths must be finite and positive."
        )

    arc = np.concatenate(([0.0], np.cumsum(length)))
    arc /= arc[-1]
    root_count = (local_modes + 1) // 2
    far_count = local_modes - root_count

    def compact_modes(local_arc: np.ndarray, count: int) -> np.ndarray:
        spacing = support / (count + 1)
        centers = spacing * np.arange(count, dtype=float)
        width = 1.5 * spacing
        return np.column_stack(
            [
                np.maximum(1.0 - np.abs(local_arc - center) / width, 0.0)
                for center in centers
            ]
        )

    seed = np.column_stack(
        (
            dct_nodal_basis(len(arc), global_modes),
            compact_modes(arc, root_count),
            compact_modes(1.0 - arc, far_count),
        )
    )
    mass = linear_nodal_mass_matrix(length)
    gram = seed.T @ mass @ seed
    try:
        factor = np.linalg.cholesky(gram)
    except np.linalg.LinAlgError as error:
        raise ValueError("Dual-endpoint shape basis is linearly dependent.") from error
    basis = seed @ np.linalg.inv(factor.T)
    if not np.isfinite(basis).all():
        raise ValueError("Dual-endpoint shape basis contains non-finite values.")
    if not np.allclose(
        basis.T @ mass @ basis,
        np.eye(modes),
        rtol=1.0e-8,
        atol=1.0e-8,
    ):
        raise ValueError("Dual-endpoint shape basis is numerically ill-conditioned.")
    return basis


def fix_endpoint_basis_nodes(
    basis: np.ndarray,
    panel_length: np.ndarray,
    *,
    fixed_root_node_count: int = 0,
    fixed_far_node_count: int = 0,
) -> np.ndarray:
    """Fix declared endpoint nodes and re-orthonormalize shape modes."""

    shape = np.asarray(basis, dtype=float).copy()
    root_count = int(fixed_root_node_count)
    far_count = int(fixed_far_node_count)
    if shape.ndim != 2 or shape.shape[0] != len(panel_length) + 1:
        raise ValueError("Fixed-endpoint basis has an incompatible node count.")
    if (
        root_count < 0
        or far_count < 0
        or root_count + far_count >= shape.shape[0]
    ):
        raise ValueError(
            "Fixed endpoint counts must leave at least one movable node."
        )
    if root_count == 0 and far_count == 0:
        return shape
    if root_count:
        shape[:root_count] = 0.0
    if far_count:
        shape[-far_count:] = 0.0
    mass = linear_nodal_mass_matrix(panel_length)
    gram = shape.T @ mass @ shape
    try:
        factor = np.linalg.cholesky(gram)
    except np.linalg.LinAlgError as error:
        raise ValueError("Fixed-endpoint basis lost rank.") from error
    return shape @ np.linalg.inv(factor.T)


def fix_root_basis_nodes(
    basis: np.ndarray,
    panel_length: np.ndarray,
    fixed_node_count: int,
) -> np.ndarray:
    """Fix leading matching-surface nodes and re-orthonormalize shape modes."""

    return fix_endpoint_basis_nodes(
        basis,
        panel_length,
        fixed_root_node_count=fixed_node_count,
    )


def fix_far_basis_nodes(
    basis: np.ndarray,
    panel_length: np.ndarray,
    fixed_node_count: int,
) -> np.ndarray:
    """Fix trailing far-field nodes and re-orthonormalize shape modes."""

    return fix_endpoint_basis_nodes(
        basis,
        panel_length,
        fixed_far_node_count=fixed_node_count,
    )


def low_mode_residual_coefficients(
    panel_length: np.ndarray,
    residual_endpoint: np.ndarray,
    mode_count: int,
) -> tuple[np.ndarray, float, float]:
    """Return lowest DCT coefficients of the continuous weak residual."""

    projected, _, projected_integral, unresolved = (
        continuous_linear_weak_projection(panel_length, residual_endpoint)
    )
    modes = int(mode_count)
    if modes < 1 or modes > len(projected):
        raise ValueError("mode_count must lie within the projected node count.")
    coefficients = dct(projected, type=2, norm="ortho")[:modes]
    return coefficients, projected_integral, unresolved


def basis_residual_coefficients(
    panel_length: np.ndarray,
    residual_endpoint: np.ndarray,
    basis: np.ndarray,
    *,
    metric_panel_length: np.ndarray | None = None,
) -> tuple[np.ndarray, float, float]:
    """Project the continuous weak residual onto an arc-orthonormal basis."""

    projected, _, projected_integral, unresolved = (
        continuous_linear_weak_projection(panel_length, residual_endpoint)
    )
    shape = np.asarray(basis, dtype=float)
    if shape.ndim != 2 or shape.shape[0] != len(projected):
        raise ValueError("Residual basis has an incompatible node count.")
    metric_length = (
        np.asarray(panel_length, dtype=float)
        if metric_panel_length is None
        else np.asarray(metric_panel_length, dtype=float)
    )
    mass = linear_nodal_mass_matrix(metric_length)
    coefficients = shape.T @ mass @ projected
    return coefficients, projected_integral, unresolved


def exact_endpoint_residual_vector(
    panel_length: np.ndarray,
    residual_endpoint: np.ndarray,
    *,
    metric_panel_length: np.ndarray | None = None,
) -> np.ndarray:
    """Factor the exact piecewise-linear residual integral into a vector norm."""

    length = np.asarray(panel_length, dtype=float)
    endpoint = np.asarray(residual_endpoint, dtype=float)
    metric = (
        length
        if metric_panel_length is None
        else np.asarray(metric_panel_length, dtype=float)
    )
    if endpoint.shape != (len(length), 2) or metric.shape != length.shape:
        raise ValueError("Exact endpoint residual arrays have incompatible shapes.")
    if (
        not all(np.isfinite(item).all() for item in (length, endpoint, metric))
        or np.any(metric <= 0.0)
    ):
        raise ValueError("Exact endpoint residual data must be finite and positive.")
    vector = np.empty(2 * len(length), dtype=float)
    vector[0::2] = np.sqrt(metric / 4.0) * (
        endpoint[:, 0] + endpoint[:, 1]
    )
    vector[1::2] = np.sqrt(metric / 12.0) * (
        endpoint[:, 0] - endpoint[:, 1]
    )
    return vector


def damped_gauss_newton_step(
    jacobian: np.ndarray,
    residual: np.ndarray,
    damping: float,
) -> np.ndarray:
    """Solve a diagonally scaled Levenberg--Marquardt normal equation."""

    matrix = np.asarray(jacobian, dtype=float)
    value = np.asarray(residual, dtype=float)
    regularization = float(damping)
    if matrix.ndim != 2 or value.shape != (matrix.shape[0],):
        raise ValueError("Gauss--Newton Jacobian and residual dimensions do not match.")
    if matrix.shape[1] == 0 or not np.isfinite(matrix).all() or not np.isfinite(value).all():
        raise ValueError("Gauss--Newton data must be finite and non-empty.")
    if not np.isfinite(regularization) or regularization < 0.0:
        raise ValueError("Gauss--Newton damping must be finite and non-negative.")
    normal = matrix.T @ matrix
    scale = np.maximum(np.diag(normal), np.finfo(float).eps)
    system = normal + regularization * np.diag(scale)
    return np.linalg.solve(system, -(matrix.T @ value))


def trust_region_scale(
    nodes: np.ndarray,
    normal_displacement: np.ndarray,
    maximum_ratio: float,
) -> float:
    """Scale a nodal normal displacement to a midpoint panel trust radius."""

    coordinates = np.asarray(nodes, dtype=float)
    displacement = np.asarray(normal_displacement, dtype=float)
    limit = float(maximum_ratio)
    if displacement.shape != (len(coordinates),) or not np.isfinite(displacement).all():
        raise ValueError("Trust-region displacement must contain one finite value per node.")
    if not np.isfinite(limit) or limit <= 0.0:
        raise ValueError("Trust-region maximum ratio must be positive.")
    normals = angle_bisector_normals(coordinates)
    trial = coordinates + displacement[:, None] * normals
    ratio = maximum_midpoint_displacement_ratio(coordinates, trial)
    return 1.0 if ratio <= limit else limit / ratio


def polyline_curvature_metrics(nodes: np.ndarray) -> tuple[float, float]:
    """Return arc-integrated squared curvature and maximum node turning angle.

    The metric is reference-isolated and resolution-aware: each interior-node
    turning angle is divided by its dual arc length before integration.  It is
    used only as a trust-region smoothness guard, not as a physical residual or
    an additional field equation.
    """

    coordinates = np.asarray(nodes, dtype=float)
    if (
        coordinates.ndim != 2
        or coordinates.shape[1] != 2
        or len(coordinates) < 3
        or not np.isfinite(coordinates).all()
    ):
        raise ValueError("Curvature metrics require at least three finite 2D nodes.")
    segment = np.diff(coordinates, axis=0)
    length = np.linalg.norm(segment, axis=1)
    if np.any(length <= np.finfo(float).eps):
        raise ValueError("Curvature metrics require positive segment lengths.")
    tangent = segment / length[:, None]
    cross = tangent[:-1, 0] * tangent[1:, 1] - tangent[:-1, 1] * tangent[1:, 0]
    dot = np.sum(tangent[:-1] * tangent[1:], axis=1)
    turning = np.arctan2(cross, np.clip(dot, -1.0, 1.0))
    dual_length = 0.5 * (length[:-1] + length[1:])
    curvature_energy = float(np.sum(np.square(turning) / dual_length))
    maximum_turning_angle_deg = float(np.rad2deg(np.max(np.abs(turning))))
    return curvature_energy, maximum_turning_angle_deg


def _outer_state(
    coupled: object,
    mode_count: int,
    *,
    basis: np.ndarray | None = None,
    metric_panel_length: np.ndarray | None = None,
    residual_space: str = "matching",
) -> tuple[np.ndarray, float, float]:
    endpoint = coupled.outer_kinematic_residual_endpoint
    if endpoint is None:
        raise ValueError("Low-mode trust region requires continuous linear elements.")
    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    length = coupled.boundary.panel_length_m[labels == "outer_free_surface"]
    if residual_space == "exact_endpoint":
        _, _, projected_integral, unresolved = (
            continuous_linear_weak_projection(length, endpoint)
        )
        return (
            exact_endpoint_residual_vector(
                length,
                endpoint,
                metric_panel_length=metric_panel_length,
            ),
            projected_integral,
            unresolved,
        )
    if residual_space != "matching":
        raise ValueError("Unknown trust-region residual space.")
    if basis is None:
        return low_mode_residual_coefficients(length, endpoint, mode_count)
    return basis_residual_coefficients(
        length,
        endpoint,
        basis,
        metric_panel_length=metric_panel_length,
    )


def _load_outer_nodes(state_dir: Path, panel_count: int) -> np.ndarray:
    for name in (
        "low_mode_final_outer_nodes.csv",
        "low_mode_trust_region_final_outer_nodes.csv",
    ):
        explicit = state_dir / name
        if explicit.exists():
            frame = pd.read_csv(explicit, float_precision="round_trip")
            return frame.loc[:, ["xi", "eta"]].to_numpy(dtype=float)
    boundary = pd.read_csv(
        state_dir / "coupled_boundary_nodes.csv",
        float_precision="round_trip",
    )
    residual = pd.read_csv(state_dir / "coupled_outer_kinematic_residual.csv")
    first = int(residual["panel_index"].iloc[0])
    last = int(residual["panel_index"].iloc[-1]) + 1
    nodes = boundary.iloc[first : last + 1].loc[:, ["xi", "eta"]].to_numpy(dtype=float)
    if len(nodes) != panel_count + 1:
        raise ValueError("Recovered state directory has an incompatible outer grid.")
    return nodes


def _build_candidate(
    coupled: object,
    source_nodes: np.ndarray,
    normal_displacement: np.ndarray,
    *,
    root_inner_iterations: int,
    matching_surface_policy: str = "relocate",
    far_shape_dipole_coefficient: float | None = None,
    regrid_candidate: bool = True,
) -> tuple[object, np.ndarray, float]:
    """Build one physical candidate with an explicit, differentiable map.

    The BEM-solved dipole coefficient and the coefficient used to construct the
    current outer-surface potential are distinct nonlinear state values.  A
    Newton finite difference must freeze the latter; silently replacing it by
    the former introduces a zeroth-order defect in every Jacobian column.
    Regridding is likewise optional so a linearization can keep ``F(0)`` equal
    to its declared source state.
    """

    normal = angle_bisector_normals(source_nodes)
    raw = _constrain_coupled_outer_nodes(
        coupled.config,
        source_nodes + normal_displacement[:, None] * normal,
        allow_reversed_root=True,
    )
    nodes = (
        _regrid_coupled_outer_nodes(coupled.config, raw)
        if regrid_candidate
        else raw
    )
    shape_dipole = (
        float(coupled.dipole_coefficient)
        if far_shape_dipole_coefficient is None
        else float(far_shape_dipole_coefficient)
    )
    if not np.isfinite(shape_dipole) or shape_dipole <= 0.0:
        raise ValueError("The far-shape dipole coefficient must be finite and positive.")
    # The supplied shallow-jet root velocity is part of the nonlinear state.
    # Dropping it at zero inner iterations makes the candidate map discontinuous
    # even when the nodal displacement tends to zero.
    seed = coupled.jet_interface.root_state.s_lambda
    if matching_surface_policy == "fixed_branch":
        candidate = _build_coupled_solution_from_outer_nodes(
            coupled.config,
            nodes,
            shape_dipole,
            root_inner_iterations=root_inner_iterations,
            s_lambda_seed=seed,
        )
    elif matching_surface_policy == "relocate":
        candidate = _build_coupled_solution_with_compatible_root(
            coupled.config,
            nodes,
            shape_dipole,
            root_inner_iterations=root_inner_iterations,
            s_lambda_seed=seed,
        )
    else:
        raise ValueError("Unknown matching-surface policy.")
    accepted_nodes = np.column_stack(
        (
            candidate.outer_free_surface.node_xi,
            candidate.outer_free_surface.node_eta,
        )
    )
    displacement = maximum_midpoint_displacement_ratio(
        source_nodes,
        accepted_nodes,
    )
    return candidate, accepted_nodes, displacement


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reference-isolated finite-difference low-mode Jacobian and trust-region "
            "diagnostic for the coupled self-similar wedge."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--initial-state-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--mode-count", type=int, default=2)
    parser.add_argument(
        "--basis",
        choices=(
            "dct",
            "root_local",
            "root_cosine_local",
            "far_local",
            "dual_endpoint_local",
        ),
        default="dct",
    )
    parser.add_argument("--global-mode-count", type=int, default=2)
    parser.add_argument("--root-support-fraction", type=float, default=0.15)
    parser.add_argument("--fixed-root-node-count", type=int, default=0)
    parser.add_argument("--fixed-far-node-count", type=int, default=0)
    parser.add_argument(
        "--residual-space",
        choices=("matching", "exact_endpoint"),
        default="matching",
    )
    parser.add_argument("--finite-difference-ratio", type=float, default=0.01)
    parser.add_argument("--trust-radius", type=float, default=0.20)
    parser.add_argument("--trust-radius-safety-factor", type=float, default=0.95)
    parser.add_argument("--damping", type=float, default=1.0e-3)
    parser.add_argument(
        "--step-factors",
        type=float,
        nargs="+",
        default=(1.0, 0.5, 0.25),
    )
    parser.add_argument("--minimum-trust-ratio", type=float, default=0.05)
    parser.add_argument("--minimum-relative-decrease", type=float, default=1.0e-4)
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.05)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument(
        "--curvature-energy-ratio-limit",
        type=float,
        default=1.10,
        help=(
            "Reject a candidate when its arc-integrated squared curvature "
            "exceeds this multiple of the source geometry."
        ),
    )
    parser.add_argument("--root-inner-iterations", type=int, default=0)
    parser.add_argument(
        "--matching-surface-policy",
        choices=("fixed_branch", "relocate"),
        default="relocate",
        help=(
            "Keep every finite-difference candidate on the source matching-"
            "surface topology, or allow the production compatibility search "
            "to relocate it."
        ),
    )
    parser.add_argument(
        "--root-constraint",
        choices=("none", "preserve", "close"),
        default="none",
        help=(
            "Optionally constrain the linearized signed augmented-BIE root "
            "defect to remain unchanged or move to zero while computing the "
            "trust-region step."
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.iterations < 1 or args.mode_count < 1:
        raise ValueError("--iterations and --mode-count must be positive.")
    if not 0.0 < args.finite_difference_ratio <= args.trust_radius <= 0.25:
        raise ValueError(
            "Require 0 < finite-difference-ratio <= trust-radius <= 0.25."
        )
    if not 0.0 < args.trust_radius_safety_factor <= 1.0:
        raise ValueError("--trust-radius-safety-factor must lie in (0, 1].")
    if args.fixed_root_node_count < 0 or args.fixed_far_node_count < 0:
        raise ValueError("Fixed endpoint node counts must be non-negative.")
    if any(value <= 0.0 or not np.isfinite(value) for value in args.step_factors):
        raise ValueError("--step-factors must be finite and positive.")
    if (
        not np.isfinite(args.curvature_energy_ratio_limit)
        or args.curvature_energy_ratio_limit < 1.0
    ):
        raise ValueError("--curvature-energy-ratio-limit must be finite and >= 1.")

    source = load_coupled_self_similar_checkpoint(args.checkpoint.resolve())
    coupled = source.coupled
    outer_shape_dipole_coefficient = source.outer_shape_dipole_coefficient
    if args.initial_state_dir is not None:
        state_dir = args.initial_state_dir.resolve()
        summary_paths = (
            state_dir / "low_mode_line_search_summary.json",
            state_dir / "low_mode_trust_region_summary.json",
        )
        summary_path = next((item for item in summary_paths if item.exists()), None)
        if summary_path is None:
            raise ValueError("Initial state directory has no supported summary file.")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        nodes = _load_outer_nodes(state_dir, coupled.config.free_surface_panels)
        jet = pd.read_csv(state_dir / "coupled_shallow_water_jet.csv")
        outer_shape_dipole_coefficient = float(summary["final_dipole_coefficient"])
        coupled = _build_coupled_solution_from_outer_nodes(
            coupled.config,
            nodes,
            outer_shape_dipole_coefficient,
            root_inner_iterations=args.root_inner_iterations,
            s_lambda_seed=float(jet["s_lambda"].iloc[0]),
        )

    initial_objective = coupled.kinematic_convergence_integral
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    trials: list[TrustRegionTrial] = []
    jacobian_rows: list[dict[str, float | int]] = []
    accepted_rows: list[dict[str, float | int]] = []
    trust_radius_safety_factor = float(args.trust_radius_safety_factor)

    for iteration in range(1, args.iterations + 1):
        trial_outer_shape_dipole_coefficient = coupled.dipole_coefficient
        source_nodes = np.column_stack(
            (coupled.outer_free_surface.node_xi, coupled.outer_free_surface.node_eta)
        )
        source_curvature_energy, source_maximum_turning_angle_deg = (
            polyline_curvature_metrics(source_nodes)
        )
        labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
        source_panel_length = coupled.boundary.panel_length_m[
            labels == "outer_free_surface"
        ]
        if args.basis == "dct":
            basis = dct_nodal_basis(len(source_nodes), args.mode_count)
        else:
            local_basis_builder = {
                "root_local": root_local_nodal_basis,
                "root_cosine_local": root_cosine_local_nodal_basis,
                "far_local": far_local_nodal_basis,
                "dual_endpoint_local": dual_endpoint_local_nodal_basis,
            }[args.basis]
            basis = local_basis_builder(
                source_panel_length,
                args.mode_count,
                global_mode_count=args.global_mode_count,
                support_fraction=args.root_support_fraction,
            )
        if args.fixed_root_node_count:
            if args.basis == "dct":
                raise ValueError("Fixed root nodes require an endpoint-local basis.")
        basis = fix_endpoint_basis_nodes(
            basis,
            source_panel_length,
            fixed_root_node_count=args.fixed_root_node_count,
            fixed_far_node_count=args.fixed_far_node_count,
        )
        residual, projected_integral, unresolved = _outer_state(
            coupled,
            args.mode_count,
            basis=None if args.basis == "dct" else basis,
            metric_panel_length=source_panel_length,
            residual_space=args.residual_space,
        )
        low_objective = float(np.dot(residual, residual))
        jacobian = np.empty((len(residual), args.mode_count), dtype=float)
        finite_difference_steps = np.empty(args.mode_count, dtype=float)
        root_defect_gradient = np.empty(args.mode_count, dtype=float)
        jacobian_failure: str | None = None
        measured_source_root = derive_shallow_water_jet_root_state_from_coupled(coupled)
        source_interface_s_lambda = coupled.jet_interface.root_state.s_lambda
        source_signed_root_defect = (
            measured_source_root.s_lambda - source_interface_s_lambda
        ) / max(abs(source_interface_s_lambda), np.finfo(float).eps)

        for mode in range(args.mode_count):
            unit_displacement = basis[:, mode]
            unit_ratio = maximum_midpoint_displacement_ratio(
                source_nodes,
                source_nodes
                + unit_displacement[:, None] * angle_bisector_normals(source_nodes),
            )
            epsilon = args.finite_difference_ratio / unit_ratio
            root_defects: dict[float, float] = {}
            def residual_at_displacement(signed_epsilon: float) -> np.ndarray:
                perturbed, _, _ = _build_candidate(
                    coupled,
                    source_nodes,
                    signed_epsilon * unit_displacement,
                    root_inner_iterations=args.root_inner_iterations,
                    matching_surface_policy=args.matching_surface_policy,
                )
                perturbed_residual, _, _ = _outer_state(
                    perturbed,
                    args.mode_count,
                    basis=None if args.basis == "dct" else basis,
                    metric_panel_length=source_panel_length,
                    residual_space=args.residual_space,
                )
                perturbed_measured_root = (
                    derive_shallow_water_jet_root_state_from_coupled(perturbed)
                )
                perturbed_interface = perturbed.jet_interface.root_state.s_lambda
                root_defects[float(signed_epsilon)] = (
                    perturbed_measured_root.s_lambda - perturbed_interface
                ) / max(abs(perturbed_interface), np.finfo(float).eps)
                return perturbed_residual

            try:
                derivative, signed_epsilon = admissible_one_sided_difference(
                    residual,
                    epsilon,
                    residual_at_displacement,
                )
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
                jacobian_failure = (
                    f"jacobian_construction_failure:mode={mode}:"
                    f"{type(error).__name__}:{error}"
                )
                trials.append(
                    TrustRegionTrial(
                        iteration=iteration,
                        step_factor=float("nan"),
                        exact_objective=float("nan"),
                        exact_relative_decrease=float("nan"),
                        low_mode_objective=float("nan"),
                        predicted_low_mode_objective=float("nan"),
                        trust_ratio=float("nan"),
                        maximum_displacement_ratio=float("nan"),
                        condition_number=float("nan"),
                        condition_number_ratio=float("nan"),
                        dipole_coefficient=float("nan"),
                        root_relative_mismatch=float("nan"),
                        curvature_energy=float("nan"),
                        curvature_energy_ratio=float("nan"),
                        maximum_turning_angle_deg=float("nan"),
                        accepted=False,
                        rejection_reason=jacobian_failure,
                    )
                )
                break
            finite_difference_steps[mode] = signed_epsilon
            jacobian[:, mode] = derivative
            root_defect_gradient[mode] = (
                root_defects[float(signed_epsilon)] - source_signed_root_defect
            ) / signed_epsilon
            print(
                json.dumps(
                    {
                        "progress": "jacobian_mode_complete",
                        "iteration": iteration,
                        "mode": mode + 1,
                        "mode_count": args.mode_count,
                        "signed_finite_difference_step": signed_epsilon,
                        "matching_surface_policy": args.matching_surface_policy,
                    }
                ),
                flush=True,
            )

        if jacobian_failure is not None:
            break

        if args.root_constraint in {"preserve", "close"}:
            step = constrained_damped_gauss_newton_step(
                jacobian,
                residual,
                args.damping,
                root_defect_gradient,
                (
                    0.0
                    if args.root_constraint == "preserve"
                    else -source_signed_root_defect
                ),
            )
        else:
            step = damped_gauss_newton_step(jacobian, residual, args.damping)
        normal_displacement = basis @ step
        step *= trust_region_scale(
            source_nodes,
            normal_displacement,
            trust_radius_safety_factor * args.trust_radius,
        )
        normal_displacement = basis @ step
        source_exact = coupled.kinematic_convergence_integral
        source_condition = coupled.solution.condition_number
        measured_source_root = derive_shallow_water_jet_root_state_from_coupled(coupled)
        source_root_mismatch = abs(
            measured_source_root.s_lambda - coupled.jet_interface.root_state.s_lambda
        ) / max(abs(coupled.jet_interface.root_state.s_lambda), np.finfo(float).eps)
        root_limit = root_feasibility_gate_limit(
            source_root_mismatch,
            args.root_mismatch_limit,
        )

        for row in range(len(residual)):
            for column in range(args.mode_count):
                jacobian_rows.append(
                    {
                        "iteration": iteration,
                        "residual_mode": row,
                        "shape_mode": column,
                        "value": jacobian[row, column],
                        "finite_difference_step": finite_difference_steps[column],
                        "root_defect_derivative": root_defect_gradient[column],
                        "source_signed_root_defect": source_signed_root_defect,
                        "jacobian_condition_number": float(np.linalg.cond(jacobian)),
                    }
                )

        candidates: list[tuple[TrustRegionTrial, object]] = []
        for factor in sorted(set(args.step_factors), reverse=True):
            try:
                candidate, candidate_nodes, displacement = _build_candidate(
                    coupled,
                    source_nodes,
                    float(factor) * normal_displacement,
                    root_inner_iterations=args.root_inner_iterations,
                    matching_surface_policy=args.matching_surface_policy,
                )
                candidate_residual, _, _ = _outer_state(
                    candidate,
                    args.mode_count,
                    basis=None if args.basis == "dct" else basis,
                    metric_panel_length=source_panel_length,
                    residual_space=args.residual_space,
                )
                candidate_low = float(np.dot(candidate_residual, candidate_residual))
                predicted = residual + float(factor) * jacobian @ step
                predicted_low = float(np.dot(predicted, predicted))
                predicted_reduction = low_objective - predicted_low
                trust_ratio = (
                    float("-inf")
                    if predicted_reduction <= 0.0
                    else (low_objective - candidate_low) / predicted_reduction
                )
                measured_root = derive_shallow_water_jet_root_state_from_coupled(candidate)
                root_mismatch = abs(
                    measured_root.s_lambda - candidate.jet_interface.root_state.s_lambda
                ) / max(
                    abs(candidate.jet_interface.root_state.s_lambda),
                    np.finfo(float).eps,
                )
                candidate_curvature_energy, candidate_maximum_turning_angle_deg = (
                    polyline_curvature_metrics(candidate_nodes)
                )
                curvature_energy_ratio = candidate_curvature_energy / max(
                    source_curvature_energy,
                    np.finfo(float).eps,
                )
                reason = trial_rejection_reason(
                    source_objective=source_exact,
                    candidate_objective=candidate.kinematic_convergence_integral,
                    minimum_relative_decrease=args.minimum_relative_decrease,
                    maximum_displacement_ratio_value=displacement,
                    displacement_limit=args.trust_radius,
                    source_condition_number=source_condition,
                    candidate_condition_number=candidate.solution.condition_number,
                    condition_number_ratio_limit=args.condition_number_ratio_limit,
                    dipole_coefficient=candidate.dipole_coefficient,
                    root_relative_mismatch=root_mismatch,
                    root_mismatch_limit=root_limit,
                )
                if (
                    not reason
                    and curvature_energy_ratio
                    > args.curvature_energy_ratio_limit
                ):
                    reason = "curvature_energy"
                if not reason and trust_ratio < args.minimum_trust_ratio:
                    reason = "insufficient_trust_ratio"
                metric = TrustRegionTrial(
                    iteration=iteration,
                    step_factor=float(factor),
                    exact_objective=candidate.kinematic_convergence_integral,
                    exact_relative_decrease=(
                        source_exact - candidate.kinematic_convergence_integral
                    )
                    / source_exact,
                    low_mode_objective=candidate_low,
                    predicted_low_mode_objective=predicted_low,
                    trust_ratio=trust_ratio,
                    maximum_displacement_ratio=displacement,
                    condition_number=candidate.solution.condition_number,
                    condition_number_ratio=candidate.solution.condition_number
                    / source_condition,
                    dipole_coefficient=candidate.dipole_coefficient,
                    root_relative_mismatch=root_mismatch,
                    curvature_energy=candidate_curvature_energy,
                    curvature_energy_ratio=curvature_energy_ratio,
                    maximum_turning_angle_deg=(
                        candidate_maximum_turning_angle_deg
                    ),
                    accepted=not reason,
                    rejection_reason=reason,
                )
                candidates.append((metric, candidate))
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
                candidates.append(
                    (
                        TrustRegionTrial(
                            iteration=iteration,
                            step_factor=float(factor),
                            exact_objective=float("nan"),
                            exact_relative_decrease=float("nan"),
                            low_mode_objective=float("nan"),
                            predicted_low_mode_objective=float("nan"),
                            trust_ratio=float("nan"),
                            maximum_displacement_ratio=float("nan"),
                            condition_number=float("nan"),
                            condition_number_ratio=float("nan"),
                            dipole_coefficient=float("nan"),
                            root_relative_mismatch=float("nan"),
                            curvature_energy=float("nan"),
                            curvature_energy_ratio=float("nan"),
                            maximum_turning_angle_deg=float("nan"),
                            accepted=False,
                            rejection_reason=(
                                f"solver_failure:{type(error).__name__}:{error}"
                            ),
                        ),
                        None,
                    )
                )

        trials.extend(item[0] for item in candidates)
        admissible = [item for item in candidates if item[0].accepted]
        if not admissible:
            break
        selected_metric, selected = min(
            admissible, key=lambda item: item[0].exact_objective
        )
        coupled = selected
        outer_shape_dipole_coefficient = trial_outer_shape_dipole_coefficient
        accepted_rows.append(
            {
                "iteration": iteration,
                "step_factor": selected_metric.step_factor,
                "exact_objective": selected_metric.exact_objective,
                "exact_relative_decrease": selected_metric.exact_relative_decrease,
                "low_mode_objective_at_source": low_objective,
                "projected_integral_at_source": projected_integral,
                "unresolved_integral_at_source": unresolved,
                "jacobian_condition_number": float(np.linalg.cond(jacobian)),
                "source_curvature_energy": source_curvature_energy,
                "source_maximum_turning_angle_deg": (
                    source_maximum_turning_angle_deg
                ),
                "candidate_curvature_energy": selected_metric.curvature_energy,
                "candidate_curvature_energy_ratio": (
                    selected_metric.curvature_energy_ratio
                ),
                "candidate_maximum_turning_angle_deg": (
                    selected_metric.maximum_turning_angle_deg
                ),
                "source_root_relative_mismatch": source_root_mismatch,
                "root_gate_limit": root_limit,
                "root_feasibility_repair": (
                    source_root_mismatch > args.root_mismatch_limit
                ),
                "candidate_root_relative_mismatch": (
                    selected_metric.root_relative_mismatch
                ),
                "candidate_hard_root_pass": (
                    selected_metric.root_relative_mismatch
                    <= args.root_mismatch_limit
                ),
            }
        )

    pd.DataFrame([asdict(item) for item in trials]).to_csv(
        output / "low_mode_trust_region_trials.csv", index=False
    )
    pd.DataFrame(jacobian_rows).to_csv(
        output / "low_mode_trust_region_jacobians.csv", index=False
    )
    pd.DataFrame(accepted_rows).to_csv(
        output / "low_mode_trust_region_accepted.csv", index=False
    )
    pd.DataFrame(
        {
            "xi": coupled.outer_free_surface.node_xi,
            "eta": coupled.outer_free_surface.node_eta,
            "node_index": np.arange(len(coupled.outer_free_surface.node_xi)),
        }
    ).to_csv(output / "low_mode_trust_region_final_outer_nodes.csv", index=False)
    _write_final_artifacts(output, coupled)
    frozen = solve_coupled_self_similar_wedge_pseudo_time(
        coupled,
        maximum_iterations=0,
        root_inner_iterations=args.root_inner_iterations,
    )
    checkpoint_path = write_coupled_self_similar_checkpoint(
        output,
        coupled,
        coupled_pseudo_time_history_frame(frozen),
        parent=source,
        transformation={
            "type": "reference_isolated_low_mode_trust_region",
            "initial_state_dir": (
                None
                if args.initial_state_dir is None
                else str(args.initial_state_dir.resolve())
            ),
            "basis": args.basis,
            "mode_count": args.mode_count,
            "global_mode_count": args.global_mode_count,
            "root_support_fraction": args.root_support_fraction,
            "fixed_root_node_count": args.fixed_root_node_count,
            "fixed_far_node_count": args.fixed_far_node_count,
            "residual_space": args.residual_space,
            "root_inner_iterations": args.root_inner_iterations,
            "root_constraint": args.root_constraint,
            "source_signed_root_defect": source_signed_root_defect,
            "root_gate_policy": "hard_limit_or_monotonic_feasibility_repair",
            "matching_surface_policy": args.matching_surface_policy,
            "curvature_energy_ratio_limit": (
                args.curvature_energy_ratio_limit
            ),
            "outer_shape_dipole_coefficient": outer_shape_dipole_coefficient,
            "reference_used_during_solve": False,
        },
    )
    summary = {
        "status": "self_similar_low_mode_trust_region_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "source_checkpoint": str(args.checkpoint.resolve()),
        "initial_state_dir": (
            None if args.initial_state_dir is None else str(args.initial_state_dir.resolve())
        ),
        "mode_count": args.mode_count,
        "basis": args.basis,
        "global_mode_count": args.global_mode_count,
        "root_support_fraction": args.root_support_fraction,
        "fixed_root_node_count": args.fixed_root_node_count,
        "fixed_far_node_count": args.fixed_far_node_count,
        "residual_space": args.residual_space,
        "root_constraint": args.root_constraint,
        "root_gate_policy": "hard_limit_or_monotonic_feasibility_repair",
        "matching_surface_policy": args.matching_surface_policy,
        "curvature_energy_ratio_limit": args.curvature_energy_ratio_limit,
        "requested_iterations": args.iterations,
        "accepted_iterations": len(accepted_rows),
        "finite_difference_ratio": args.finite_difference_ratio,
        "trust_radius": args.trust_radius,
        "trust_radius_safety_factor": trust_radius_safety_factor,
        "damping": args.damping,
        "initial_objective": initial_objective,
        "final_objective": coupled.kinematic_convergence_integral,
        "final_condition_number": coupled.solution.condition_number,
        "final_dipole_coefficient": coupled.dipole_coefficient,
        "final_outer_shape_dipole_coefficient": (
            outer_shape_dipole_coefficient
        ),
        "checkpoint": str(checkpoint_path),
        "conclusion": (
            "accepted_reference_isolated_trust_region_steps"
            if accepted_rows
            else "no_admissible_trust_region_step"
        ),
    }
    (output / "low_mode_trust_region_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
