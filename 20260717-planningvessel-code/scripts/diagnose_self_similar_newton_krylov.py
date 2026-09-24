from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Callable

import numpy as np
import pandas as pd
from scipy.fft import dct
from scipy.sparse.linalg import LinearOperator, gmres


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    coupled_pseudo_time_history_frame,
    load_coupled_self_similar_checkpoint,
    write_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    derive_shallow_water_jet_root_state_from_coupled,
    solve_coupled_self_similar_wedge_pseudo_time,
)
from scripts.diagnose_self_similar_low_mode_line_search import (
    angle_bisector_normals,
    maximum_midpoint_displacement_ratio,
    trial_rejection_reason,
)
from scripts.diagnose_self_similar_low_mode_trust_region import (
    _build_candidate,
    admissible_one_sided_difference,
    basis_residual_coefficients,
    dct_nodal_basis,
    exact_endpoint_residual_vector,
    fix_endpoint_basis_nodes,
    polyline_curvature_metrics,
    root_cosine_local_nodal_basis,
    root_local_nodal_basis,
    trust_region_scale,
)
from scripts.resume_self_similar_wedge import _write_final_artifacts


MAPPING_VERSION = "newton_krylov_joint_root_v2"
CANDIDATE_MAP_POLICIES = (
    "freeze_rebased_source",
    "synchronize_candidate",
)


@dataclass(frozen=True)
class DirectionalProductRecord:
    direction_norm: float
    maximum_unit_displacement_ratio: float
    signed_finite_difference_step: float
    source_residual_norm: float
    perturbed_residual_norm: float
    product_norm: float


@dataclass(frozen=True)
class NewtonKrylovTrial:
    outer_iteration: int
    step_factor: float
    formal_exact_objective: float
    formal_exact_relative_decrease: float
    reduced_objective: float
    projected_integral: float
    unresolved_integral: float
    unrepresented_projected_integral: float
    predicted_reduced_objective: float
    predicted_formal_exact_objective: float
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


@dataclass(frozen=True)
class FormalOuterState:
    panel_length: np.ndarray
    endpoint_residual: np.ndarray
    exact_objective: float
    root_relative_mismatch: float
    condition_number: float
    dipole_coefficient: float


@dataclass(frozen=True)
class CandidateMapRebase:
    phase: str
    outer_iteration: int
    source_shape_dipole_coefficient: float
    target_shape_dipole_coefficient: float
    source_formal_exact_objective: float
    rebased_formal_exact_objective: float
    formal_exact_relative_change: float
    maximum_displacement_ratio: float
    rebased_root_relative_mismatch: float
    rebased_condition_number: float


def formal_outer_state(coupled: object) -> FormalOuterState:
    """Return the unweighted, piecewise-linear Gate-2 outer-surface state."""

    endpoint = coupled.outer_kinematic_residual_endpoint
    if endpoint is None:
        raise ValueError("Newton--Krylov requires continuous linear elements.")
    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    length = np.asarray(
        coupled.boundary.panel_length_m[labels == "outer_free_surface"],
        dtype=float,
    )
    endpoint_array = np.asarray(endpoint, dtype=float)
    exact = exact_endpoint_residual_vector(length, endpoint_array)
    measured = derive_shallow_water_jet_root_state_from_coupled(coupled)
    interface = float(coupled.jet_interface.root_state.s_lambda)
    root_mismatch = abs(float(measured.s_lambda) - interface) / max(
        abs(interface), np.finfo(float).eps
    )
    return FormalOuterState(
        panel_length=length,
        endpoint_residual=endpoint_array,
        exact_objective=float(np.dot(exact, exact)),
        root_relative_mismatch=float(root_mismatch),
        condition_number=float(coupled.solution.condition_number),
        dipole_coefficient=float(coupled.dipole_coefficient),
    )


def rebase_candidate_map_source(
    coupled: object,
    *,
    source_shape_dipole_coefficient: float,
    root_inner_iterations: int,
    matching_surface_policy: str,
    outer_iteration: int,
    phase: str,
) -> tuple[object, float, CandidateMapRebase]:
    """Synchronize and canonicalize the source before taking derivatives.

    This explicit rebase is deliberately outside the Newton finite-difference
    map.  Candidate perturbations can therefore freeze the same far-shape
    coefficient and node parameterization as their source, making ``F(0)`` a
    genuine source residual instead of a hidden dipole/regrid update.
    """

    source_state = formal_outer_state(coupled)
    source_nodes = np.column_stack(
        (coupled.outer_free_surface.node_xi, coupled.outer_free_surface.node_eta)
    )
    target_shape_dipole = float(coupled.dipole_coefficient)
    rebased, _, displacement = _build_candidate(
        coupled,
        source_nodes,
        np.zeros(len(source_nodes), dtype=float),
        root_inner_iterations=root_inner_iterations,
        matching_surface_policy=matching_surface_policy,
        far_shape_dipole_coefficient=target_shape_dipole,
        regrid_candidate=True,
    )
    rebased_state = formal_outer_state(rebased)
    relative_change = (
        rebased_state.exact_objective - source_state.exact_objective
    ) / max(source_state.exact_objective, np.finfo(float).eps)
    record = CandidateMapRebase(
        phase=str(phase),
        outer_iteration=int(outer_iteration),
        source_shape_dipole_coefficient=float(source_shape_dipole_coefficient),
        target_shape_dipole_coefficient=target_shape_dipole,
        source_formal_exact_objective=source_state.exact_objective,
        rebased_formal_exact_objective=rebased_state.exact_objective,
        formal_exact_relative_change=float(relative_change),
        maximum_displacement_ratio=float(displacement),
        rebased_root_relative_mismatch=rebased_state.root_relative_mismatch,
        rebased_condition_number=rebased_state.condition_number,
    )
    return rebased, target_shape_dipole, record


def _candidate_map_contract(candidate_map_policy: str) -> dict[str, str]:
    """Return the recorded contract for one candidate-map policy."""

    if candidate_map_policy == "freeze_rebased_source":
        return {
            "candidate_map_far_shape_dipole_policy": "freeze_rebased_source",
            "candidate_map_regrid_policy": "frozen_nodes_during_linearization",
            "candidate_map_source_residual_policy": "rebased_source_is_F0",
        }
    if candidate_map_policy == "synchronize_candidate":
        return {
            "candidate_map_far_shape_dipole_policy": (
                "synchronize_candidate_solved_dipole"
            ),
            "candidate_map_regrid_policy": (
                "canonical_regrid_after_candidate_dipole_sync"
            ),
            "candidate_map_source_residual_policy": (
                "evaluate_synchronized_candidate_map_at_zero_displacement"
            ),
        }
    raise ValueError("Unknown Newton--Krylov candidate-map policy.")


def build_candidate_map(
    coupled: object,
    source_nodes: np.ndarray,
    normal_displacement: np.ndarray,
    *,
    root_inner_iterations: int,
    matching_surface_policy: str,
    far_shape_dipole_coefficient: float,
    candidate_map_policy: str = "freeze_rebased_source",
    geometry_reference_nodes: np.ndarray | None = None,
) -> tuple[object, np.ndarray, float]:
    """Build one residual-evaluated candidate under the declared map policy.

    The legacy policy deliberately makes one frozen-shape, unregridded
    candidate build.  The synchronized policy first solves that displaced
    candidate, then rebuilds its solved geometry with the candidate's solved
    dipole as the far-shape coefficient and a canonical regrid.  Because the
    latter changes the zero-displacement map, callers must evaluate its
    ``F(0)`` through this same function before forming finite differences.
    """

    _candidate_map_contract(candidate_map_policy)
    candidate, candidate_nodes, displacement = _build_candidate(
        coupled,
        source_nodes,
        normal_displacement,
        root_inner_iterations=root_inner_iterations,
        matching_surface_policy=matching_surface_policy,
        far_shape_dipole_coefficient=far_shape_dipole_coefficient,
        regrid_candidate=False,
    )
    if candidate_map_policy == "freeze_rebased_source":
        return candidate, candidate_nodes, displacement

    candidate_shape_dipole = float(candidate.dipole_coefficient)
    candidate, candidate_nodes, _ = _build_candidate(
        candidate,
        candidate_nodes,
        np.zeros(len(candidate_nodes), dtype=float),
        root_inner_iterations=root_inner_iterations,
        matching_surface_policy=matching_surface_policy,
        far_shape_dipole_coefficient=candidate_shape_dipole,
        regrid_candidate=True,
    )
    reference_nodes = (
        source_nodes
        if geometry_reference_nodes is None
        else np.asarray(geometry_reference_nodes, dtype=float)
    )
    if np.asarray(reference_nodes).shape != np.asarray(candidate_nodes).shape:
        raise ValueError("Candidate-map geometry reference nodes are incompatible.")
    displacement = maximum_midpoint_displacement_ratio(
        reference_nodes,
        candidate_nodes,
    )
    return candidate, candidate_nodes, displacement


def reduced_residual(
    coupled: object,
    basis: np.ndarray,
    metric_panel_length: np.ndarray,
) -> tuple[np.ndarray, float, float]:
    """Project the current weak residual into one frozen arc-metric basis."""

    state = formal_outer_state(coupled)
    return basis_residual_coefficients(
        state.panel_length,
        state.endpoint_residual,
        basis,
        metric_panel_length=metric_panel_length,
    )


def endpoint_block_residual(
    panel_length: np.ndarray,
    endpoint_residual: np.ndarray,
    *,
    average_mode_count: int,
    jump_mode_count: int,
    metric_panel_length: np.ndarray | None = None,
) -> np.ndarray:
    """Return selected exact-average and exact-jump panel DCT coefficients."""

    length = np.asarray(panel_length, dtype=float)
    endpoint = np.asarray(endpoint_residual, dtype=float)
    metric = (
        length
        if metric_panel_length is None
        else np.asarray(metric_panel_length, dtype=float)
    )
    average_modes = int(average_mode_count)
    jump_modes = int(jump_mode_count)
    if endpoint.shape != (len(length), 2) or metric.shape != length.shape:
        raise ValueError("Endpoint block residual arrays have incompatible shapes.")
    if (
        len(length) < 2
        or not all(np.isfinite(item).all() for item in (length, endpoint, metric))
        or np.any(length <= 0.0)
        or np.any(metric <= 0.0)
    ):
        raise ValueError("Endpoint block residual data must be finite and positive.")
    if not 1 <= average_modes <= len(length) or not 1 <= jump_modes <= len(length):
        raise ValueError("Endpoint block mode counts must lie within panel count.")
    average = np.sqrt(metric / 4.0) * (endpoint[:, 0] + endpoint[:, 1])
    jump = np.sqrt(metric / 12.0) * (endpoint[:, 0] - endpoint[:, 1])
    return np.concatenate(
        (
            dct(average, type=2, norm="ortho")[:average_modes],
            dct(jump, type=2, norm="ortho")[:jump_modes],
        )
    )


def source_aligned_householder_vector(
    source_exact_residual: np.ndarray,
    *,
    reduced_size: int,
) -> np.ndarray:
    """Return a Householder vector that aligns the source with coordinate zero."""

    source = np.asarray(source_exact_residual, dtype=float)
    size = int(reduced_size)
    if source.ndim != 1 or len(source) < 2 or not np.isfinite(source).all():
        raise ValueError("Source-aligned sketch requires one finite residual vector.")
    if not 1 <= size < len(source):
        raise ValueError("Source-aligned sketch size must be below full residual size.")
    norm = float(np.linalg.norm(source))
    if norm <= np.finfo(float).eps:
        raise ValueError("Source-aligned sketch requires a non-zero source residual.")
    target = -np.copysign(norm, source[0] if source[0] != 0.0 else 1.0)
    vector = source.copy()
    vector[0] -= target
    vector_norm = float(np.linalg.norm(vector))
    if vector_norm <= np.finfo(float).eps:
        raise ValueError("Source-aligned Householder construction is singular.")
    return vector / vector_norm


def apply_source_aligned_exact_sketch(
    full_exact_residual: np.ndarray,
    householder_vector: np.ndarray,
    *,
    reduced_size: int,
) -> np.ndarray:
    """Apply one frozen orthogonal transform and retain its leading rows."""

    residual = np.asarray(full_exact_residual, dtype=float)
    vector = np.asarray(householder_vector, dtype=float)
    size = int(reduced_size)
    if (
        residual.ndim != 1
        or vector.shape != residual.shape
        or not np.isfinite(residual).all()
        or not np.isfinite(vector).all()
    ):
        raise ValueError("Source-aligned sketch arrays must be finite and compatible.")
    if not 1 <= size < len(residual):
        raise ValueError("Source-aligned sketch size must be below full residual size.")
    if not np.isclose(np.dot(vector, vector), 1.0, rtol=1.0e-12, atol=1.0e-12):
        raise ValueError("Source-aligned Householder vector must have unit norm.")
    transformed = residual - 2.0 * vector * np.dot(vector, residual)
    return transformed[:size]


def direction_residual(
    coupled: object,
    basis: np.ndarray,
    metric_panel_length: np.ndarray,
    *,
    residual_generator: str,
    jump_mode_count: int,
    source_aligned_vector: np.ndarray | None = None,
) -> np.ndarray:
    """Return the declared square residual used to generate Krylov directions."""

    if residual_generator == "continuous_weak":
        return reduced_residual(coupled, basis, metric_panel_length)[0]
    if residual_generator not in {"endpoint_block", "source_aligned_exact"}:
        raise ValueError("Unknown Newton--Krylov residual generator.")
    state = formal_outer_state(coupled)
    if residual_generator == "source_aligned_exact":
        if source_aligned_vector is None:
            raise ValueError("Source-aligned exact residual requires a frozen transform.")
        full = endpoint_block_residual(
            state.panel_length,
            state.endpoint_residual,
            average_mode_count=len(state.panel_length),
            jump_mode_count=len(state.panel_length),
            metric_panel_length=metric_panel_length,
        )
        return apply_source_aligned_exact_sketch(
            full,
            source_aligned_vector,
            reduced_size=basis.shape[1],
        )
    average_modes = basis.shape[1] - int(jump_mode_count)
    return endpoint_block_residual(
        state.panel_length,
        state.endpoint_residual,
        average_mode_count=average_modes,
        jump_mode_count=jump_mode_count,
        metric_panel_length=metric_panel_length,
    )


def matrix_free_directional_product(
    source_residual: np.ndarray,
    coefficient_direction: np.ndarray,
    basis: np.ndarray,
    source_nodes: np.ndarray,
    finite_difference_ratio: float,
    residual_at_normal_displacement: Callable[[np.ndarray], np.ndarray],
) -> tuple[np.ndarray, DirectionalProductRecord]:
    """Evaluate a scale-invariant finite-difference Jacobian product.

    The coefficient direction is normalized before choosing the perturbation.
    The finite-difference step is then set by a declared maximum midpoint
    displacement ratio.  Multiplying the unit-direction derivative by the
    original coefficient norm preserves the required ``J @ v`` scaling.
    """

    base = np.asarray(source_residual, dtype=float)
    direction = np.asarray(coefficient_direction, dtype=float)
    shape = np.asarray(basis, dtype=float)
    nodes = np.asarray(source_nodes, dtype=float)
    ratio = float(finite_difference_ratio)
    if base.ndim != 1 or direction.shape != base.shape:
        raise ValueError("Matrix-free residual and coefficient dimensions must match.")
    if shape.shape != (len(nodes), len(direction)):
        raise ValueError("Matrix-free basis dimensions are incompatible.")
    if not all(np.isfinite(item).all() for item in (base, direction, shape, nodes)):
        raise ValueError("Matrix-free inputs must be finite.")
    if not np.isfinite(ratio) or ratio <= 0.0:
        raise ValueError("Finite-difference ratio must be finite and positive.")

    direction_norm = float(np.linalg.norm(direction))
    if direction_norm <= np.finfo(float).eps:
        record = DirectionalProductRecord(
            direction_norm=direction_norm,
            maximum_unit_displacement_ratio=0.0,
            signed_finite_difference_step=0.0,
            source_residual_norm=float(np.linalg.norm(base)),
            perturbed_residual_norm=float(np.linalg.norm(base)),
            product_norm=0.0,
        )
        return np.zeros_like(base), record

    unit_direction = direction / direction_norm
    unit_displacement = shape @ unit_direction
    normals = angle_bisector_normals(nodes)
    unit_displacement_ratio = maximum_midpoint_displacement_ratio(
        nodes,
        nodes + unit_displacement[:, None] * normals,
    )
    if not np.isfinite(unit_displacement_ratio) or unit_displacement_ratio <= 0.0:
        raise ValueError("Coefficient direction produces no admissible nodal motion.")
    epsilon = ratio / unit_displacement_ratio
    perturbed_by_step: dict[float, np.ndarray] = {}

    def evaluate(signed_step: float) -> np.ndarray:
        value = np.asarray(
            residual_at_normal_displacement(signed_step * unit_displacement),
            dtype=float,
        )
        perturbed_by_step[float(signed_step)] = value
        return value

    derivative, signed_epsilon = admissible_one_sided_difference(
        base,
        epsilon,
        evaluate,
    )
    product = derivative * direction_norm
    perturbed = perturbed_by_step[float(signed_epsilon)]
    return product, DirectionalProductRecord(
        direction_norm=direction_norm,
        maximum_unit_displacement_ratio=unit_displacement_ratio,
        signed_finite_difference_step=float(signed_epsilon),
        source_residual_norm=float(np.linalg.norm(base)),
        perturbed_residual_norm=float(np.linalg.norm(perturbed)),
        product_norm=float(np.linalg.norm(product)),
    )


def solve_matrix_free_newton_step(
    residual: np.ndarray,
    jacobian_product: Callable[[np.ndarray], np.ndarray],
    *,
    damping: float,
    relative_tolerance: float,
    maximum_iterations: int,
    right_preconditioner_scale: np.ndarray | None = None,
) -> tuple[np.ndarray, int, list[float]]:
    """Solve a right-preconditioned damped Newton system with one GMRES cycle."""

    value = np.asarray(residual, dtype=float)
    regularization = float(damping)
    tolerance = float(relative_tolerance)
    iterations = int(maximum_iterations)
    if value.ndim != 1 or len(value) < 1 or not np.isfinite(value).all():
        raise ValueError("Krylov residual must be one finite non-empty vector.")
    if not np.isfinite(regularization) or regularization < 0.0:
        raise ValueError("Krylov damping must be finite and non-negative.")
    if not 0.0 < tolerance < 1.0:
        raise ValueError("Krylov relative tolerance must lie in (0, 1).")
    if iterations < 1 or iterations > len(value):
        raise ValueError("Krylov iterations must lie between one and system size.")
    scale = (
        np.ones_like(value)
        if right_preconditioner_scale is None
        else np.asarray(right_preconditioner_scale, dtype=float)
    )
    if (
        scale.shape != value.shape
        or not np.isfinite(scale).all()
        or np.any(scale <= 0.0)
    ):
        raise ValueError("Right-preconditioner scale must be finite and positive.")

    def system_product(preconditioned_vector: np.ndarray) -> np.ndarray:
        physical_vector = scale * np.asarray(preconditioned_vector, dtype=float)
        product = np.asarray(jacobian_product(physical_vector), dtype=float)
        if product.shape != value.shape or not np.isfinite(product).all():
            raise ValueError("Jacobian product must match the residual and be finite.")
        return product + regularization * physical_vector

    operator = LinearOperator(
        (len(value), len(value)),
        matvec=system_product,
        dtype=float,
    )
    history: list[float] = []
    step, info = gmres(
        operator,
        -value,
        rtol=tolerance,
        atol=0.0,
        restart=iterations,
        maxiter=1,
        callback=lambda norm: history.append(float(norm)),
        callback_type="pr_norm",
    )
    step = scale * np.asarray(step, dtype=float)
    if step.shape != value.shape or not np.isfinite(step).all():
        raise ValueError("Krylov solver returned a non-finite or incompatible step.")
    return step, int(info), history


def exact_krylov_subspace_gauss_newton_step(
    exact_residual: np.ndarray,
    coefficient_directions: list[np.ndarray],
    exact_products: list[np.ndarray],
    *,
    damping: float,
    independence_tolerance: float = 1.0e-10,
) -> tuple[np.ndarray, np.ndarray, int, float]:
    """Minimize the exact endpoint residual in the sampled Krylov subspace."""

    residual = np.asarray(exact_residual, dtype=float)
    if residual.ndim != 1 or not np.isfinite(residual).all():
        raise ValueError("Exact subspace residual must be one finite vector.")
    if len(coefficient_directions) != len(exact_products) or not exact_products:
        raise ValueError("Exact subspace directions and products must be paired.")
    regularization = float(damping)
    tolerance = float(independence_tolerance)
    if not np.isfinite(regularization) or regularization < 0.0:
        raise ValueError("Exact subspace damping must be finite and non-negative.")
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("Independence tolerance must be finite and positive.")

    selected_directions: list[np.ndarray] = []
    selected_products: list[np.ndarray] = []
    orthonormal: list[np.ndarray] = []
    coefficient_size: int | None = None
    for direction_value, product_value in zip(
        coefficient_directions,
        exact_products,
        strict=True,
    ):
        direction = np.asarray(direction_value, dtype=float)
        product = np.asarray(product_value, dtype=float)
        if coefficient_size is None:
            coefficient_size = len(direction)
        if (
            direction.shape != (coefficient_size,)
            or product.shape != residual.shape
            or not np.isfinite(direction).all()
            or not np.isfinite(product).all()
        ):
            raise ValueError("Exact subspace samples have incompatible dimensions.")
        norm = float(np.linalg.norm(direction))
        if norm <= np.finfo(float).eps:
            continue
        candidate = direction / norm
        for vector in orthonormal:
            candidate -= np.dot(vector, candidate) * vector
        independent_norm = float(np.linalg.norm(candidate))
        if independent_norm <= tolerance:
            continue
        orthonormal.append(candidate / independent_norm)
        selected_directions.append(direction)
        selected_products.append(product)

    if not selected_directions or coefficient_size is None:
        raise ValueError("Exact subspace contains no independent direction.")
    directions = np.column_stack(selected_directions)
    jacobian = np.column_stack(selected_products)
    system = np.vstack(
        (jacobian, np.sqrt(regularization) * directions)
    )
    right = np.concatenate((-residual, np.zeros(coefficient_size, dtype=float)))
    coefficients, _, _, singular = np.linalg.lstsq(system, right, rcond=None)
    step = directions @ coefficients
    exact_product = jacobian @ coefficients
    condition = (
        float("inf")
        if len(singular) == 0 or singular[-1] <= np.finfo(float).eps
        else float(singular[0] / singular[-1])
    )
    if not np.isfinite(step).all() or not np.isfinite(exact_product).all():
        raise ValueError("Exact subspace solve returned non-finite data.")
    return step, exact_product, len(selected_directions), condition


def geometric_right_preconditioner_scale(
    basis: np.ndarray,
    source_nodes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Balance shape columns by their unit midpoint displacement ratio."""

    shape = np.asarray(basis, dtype=float)
    nodes = np.asarray(source_nodes, dtype=float)
    if shape.ndim != 2 or shape.shape[0] != len(nodes):
        raise ValueError("Geometric preconditioner basis dimensions are incompatible.")
    if not np.isfinite(shape).all() or not np.isfinite(nodes).all():
        raise ValueError("Geometric preconditioner inputs must be finite.")
    normals = angle_bisector_normals(nodes)
    ratios = np.asarray(
        [
            maximum_midpoint_displacement_ratio(
                nodes,
                nodes + shape[:, mode, None] * normals,
            )
            for mode in range(shape.shape[1])
        ],
        dtype=float,
    )
    if not np.isfinite(ratios).all() or np.any(ratios <= 0.0):
        raise ValueError("Every shape mode must produce positive finite displacement.")
    median = float(np.median(ratios))
    return median / ratios, ratios


def free_nodal_arc_basis(
    panel_length: np.ndarray,
    *,
    fixed_root_node_count: int = 0,
    fixed_far_node_count: int = 0,
) -> np.ndarray:
    """Return an arc-mass-orthonormal basis for every unfixed nodal value."""

    length = np.asarray(panel_length, dtype=float)
    root_count = int(fixed_root_node_count)
    far_count = int(fixed_far_node_count)
    node_count = len(length) + 1
    if (
        length.ndim != 1
        or len(length) < 1
        or not np.isfinite(length).all()
        or np.any(length <= 0.0)
    ):
        raise ValueError("Full nodal basis requires positive finite panel lengths.")
    if root_count < 0 or far_count < 0 or root_count + far_count >= node_count:
        raise ValueError("Fixed endpoint counts must leave at least one free node.")
    free = np.arange(root_count, node_count - far_count, dtype=int)
    seed = np.eye(node_count, dtype=float)[:, free]
    from scripts.diagnose_self_similar_low_mode_trust_region import (
        linear_nodal_mass_matrix,
    )

    mass = linear_nodal_mass_matrix(length)
    gram = seed.T @ mass @ seed
    factor = np.linalg.cholesky(gram)
    basis = seed @ np.linalg.inv(factor.T)
    if not np.allclose(
        basis.T @ mass @ basis,
        np.eye(len(free)),
        rtol=1.0e-8,
        atol=1.0e-8,
    ):
        raise ValueError("Full nodal basis is numerically ill-conditioned.")
    return basis


def newton_krylov_transformation(
    *,
    basis_name: str,
    mode_count: int,
    global_mode_count: int,
    support_fraction: float,
    fixed_root_node_count: int,
    fixed_far_node_count: int,
    root_inner_iterations: int,
    matching_surface_policy: str,
    finite_difference_ratio: float,
    damping: float,
    krylov_relative_tolerance: float,
    krylov_maximum_iterations: int,
    right_preconditioner: str,
    outer_shape_dipole_coefficient: float,
    direction_solver: str,
    residual_generator: str,
    jump_mode_count: int,
    candidate_map_policy: str = "freeze_rebased_source",
) -> dict[str, object]:
    """Return the checkpoint contract for this nonlinear candidate mapping."""

    candidate_map_contract = _candidate_map_contract(candidate_map_policy)
    return {
        "type": "reference_isolated_self_similar_newton_krylov",
        "mapping_version": MAPPING_VERSION,
        "basis": basis_name,
        "mode_count": int(mode_count),
        "global_mode_count": int(global_mode_count),
        "local_support_fraction": float(support_fraction),
        "fixed_root_node_count": int(fixed_root_node_count),
        "fixed_far_node_count": int(fixed_far_node_count),
        "residual_space": {
            "continuous_weak": "continuous_P1_weak_projection_in_frozen_arc_metric",
            "endpoint_block": "exact_panel_average_and_jump_DCT_block_in_frozen_metric",
            "source_aligned_exact": (
                "source_aligned_orthogonal_sketch_of_full_exact_endpoint_block"
            ),
        }[residual_generator],
        "residual_generator": residual_generator,
        "average_mode_count": (
            int(mode_count) - int(jump_mode_count)
            if residual_generator == "endpoint_block"
            else None
        ),
        "jump_mode_count": (
            int(jump_mode_count) if residual_generator == "endpoint_block" else None
        ),
        "source_alignment_preserves_source_exact_objective": (
            residual_generator == "source_aligned_exact"
        ),
        "acceptance_objective": "unweighted_piecewise_linear_exact_integral",
        "candidate_root_seed_policy": "inherit_source",
        "candidate_map_policy": candidate_map_policy,
        **candidate_map_contract,
        "outer_iteration_rebase_policy": "sync_to_solved_dipole_then_regrid",
        "root_inner_iterations": int(root_inner_iterations),
        "matching_surface_policy": matching_surface_policy,
        "finite_difference_policy": "normalized_direction_midpoint_ratio",
        "finite_difference_ratio": float(finite_difference_ratio),
        "linear_system": (
            "min ||exact_residual + J_exact delta||^2 + damping ||delta||^2"
            if direction_solver == "exact_coordinate_subspace"
            else "(matrix_free_J + damping_I) P y = -residual; delta = P y"
        ),
        "damping": float(damping),
        "krylov_solver": (
            "explicit_coordinate_sampling"
            if direction_solver == "exact_coordinate_subspace"
            else "scipy.sparse.linalg.gmres"
        ),
        "right_preconditioner": right_preconditioner,
        "direction_solver": direction_solver,
        "krylov_relative_tolerance": float(krylov_relative_tolerance),
        "krylov_maximum_iterations": int(krylov_maximum_iterations),
        "outer_shape_dipole_coefficient": float(
            outer_shape_dipole_coefficient
        ),
        "reference_used_during_solve": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reference-isolated high-dimensional matrix-free Newton--Krylov "
            "diagnostic for the coupled self-similar wedge free surface."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--outer-iterations", type=int, default=1)
    parser.add_argument("--mode-count", type=int, default=64)
    parser.add_argument(
        "--basis",
        choices=("root_local", "root_cosine_local", "global_dct", "full_nodal"),
        default="root_local",
    )
    parser.add_argument("--global-mode-count", type=int, default=4)
    parser.add_argument("--support-fraction", type=float, default=0.30)
    parser.add_argument("--fixed-root-node-count", type=int, default=0)
    parser.add_argument("--fixed-far-node-count", type=int, default=2)
    parser.add_argument("--root-inner-iterations", type=int, default=8)
    parser.add_argument(
        "--matching-surface-policy",
        choices=("fixed_branch", "relocate"),
        default="relocate",
    )
    parser.add_argument(
        "--candidate-map-policy",
        choices=CANDIDATE_MAP_POLICIES,
        default="freeze_rebased_source",
        help=(
            "Freeze the rebased source map (default), or synchronize each "
            "candidate to its solved dipole and canonical regrid."
        ),
    )
    parser.add_argument("--finite-difference-ratio", type=float, default=1.0e-3)
    parser.add_argument("--damping", type=float, default=1.0e-3)
    parser.add_argument("--krylov-relative-tolerance", type=float, default=1.0e-2)
    parser.add_argument("--krylov-maximum-iterations", type=int, default=16)
    parser.add_argument(
        "--right-preconditioner",
        choices=("none", "geometric_midpoint"),
        default="geometric_midpoint",
    )
    parser.add_argument(
        "--direction-solver",
        choices=(
            "reduced_gmres",
            "exact_krylov_subspace",
            "exact_coordinate_subspace",
        ),
        default="exact_krylov_subspace",
    )
    parser.add_argument(
        "--residual-generator",
        choices=("continuous_weak", "endpoint_block", "source_aligned_exact"),
        default="endpoint_block",
    )
    parser.add_argument("--jump-mode-count", type=int, default=32)
    parser.add_argument(
        "--step-factors",
        type=float,
        nargs="+",
        default=(1.0, 0.5, 0.25, 0.125, 0.0625),
    )
    parser.add_argument("--trust-radius", type=float, default=0.20)
    parser.add_argument("--trust-radius-safety-factor", type=float, default=0.95)
    parser.add_argument("--minimum-relative-decrease", type=float, default=1.0e-4)
    parser.add_argument("--minimum-trust-ratio", type=float, default=0.01)
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.10)
    parser.add_argument("--curvature-energy-ratio-limit", type=float, default=1.25)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument("--formal-objective-limit", type=float, default=1.0e-3)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.outer_iterations < 1:
        raise ValueError("--outer-iterations must be positive.")
    if args.mode_count < 2:
        raise ValueError("--mode-count must be at least two.")
    if not 1 <= args.global_mode_count < args.mode_count:
        raise ValueError("--global-mode-count must lie below --mode-count.")
    if not 0.0 < args.support_fraction <= 0.5:
        raise ValueError("--support-fraction must lie in (0, 0.5].")
    if args.fixed_root_node_count < 0 or args.fixed_far_node_count < 0:
        raise ValueError("Fixed endpoint node counts must be non-negative.")
    if args.root_inner_iterations < 1:
        raise ValueError("Joint root closure requires positive inner iterations.")
    if args.candidate_map_policy not in CANDIDATE_MAP_POLICIES:
        raise ValueError("Unknown Newton--Krylov candidate-map policy.")
    if not 0.0 < args.finite_difference_ratio <= args.trust_radius <= 0.25:
        raise ValueError(
            "Require 0 < finite-difference-ratio <= trust-radius <= 0.25."
        )
    if not 0.0 < args.trust_radius_safety_factor <= 1.0:
        raise ValueError("--trust-radius-safety-factor must lie in (0, 1].")
    if not 1 <= args.krylov_maximum_iterations <= args.mode_count:
        raise ValueError("Krylov iterations must lie within the reduced system size.")
    if (
        args.residual_generator == "endpoint_block"
        and not 1 <= args.jump_mode_count < args.mode_count
    ):
        raise ValueError("Jump mode count must leave at least one average mode.")
    if any(not np.isfinite(item) or item <= 0.0 for item in args.step_factors):
        raise ValueError("Step factors must be finite and positive.")
    positive = (
        args.condition_number_ratio_limit,
        args.curvature_energy_ratio_limit,
        args.root_mismatch_limit,
        args.formal_objective_limit,
    )
    if any(not np.isfinite(item) or item <= 0.0 for item in positive):
        raise ValueError("Acceptance limits must be finite and positive.")


def _basis(
    name: str,
    panel_length: np.ndarray,
    mode_count: int,
    global_mode_count: int,
    support_fraction: float,
    fixed_root_node_count: int,
    fixed_far_node_count: int,
) -> np.ndarray:
    if name == "full_nodal":
        full = free_nodal_arc_basis(
            panel_length,
            fixed_root_node_count=fixed_root_node_count,
            fixed_far_node_count=fixed_far_node_count,
        )
        if full.shape[1] != mode_count:
            raise ValueError(
                "Full nodal basis requires mode_count equal to the number of "
                f"unfixed nodes ({full.shape[1]})."
            )
        return full
    if name == "global_dct":
        raw = dct_nodal_basis(len(panel_length) + 1, mode_count)
        return fix_endpoint_basis_nodes(
            raw,
            panel_length,
            fixed_root_node_count=fixed_root_node_count,
            fixed_far_node_count=fixed_far_node_count,
        )
    builder = {
        "root_local": root_local_nodal_basis,
        "root_cosine_local": root_cosine_local_nodal_basis,
    }[name]
    raw = builder(
        panel_length,
        mode_count,
        global_mode_count=global_mode_count,
        support_fraction=support_fraction,
    )
    return fix_endpoint_basis_nodes(
        raw,
        panel_length,
        fixed_root_node_count=fixed_root_node_count,
        fixed_far_node_count=fixed_far_node_count,
    )


def main() -> int:
    args = _parser().parse_args()
    _validate_args(args)
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_checkpoint = load_coupled_self_similar_checkpoint(
        args.checkpoint.resolve()
    )
    coupled = source_checkpoint.coupled
    outer_shape_dipole_coefficient = (
        source_checkpoint.outer_shape_dipole_coefficient
    )
    initial_state = formal_outer_state(coupled)
    initial_objective = initial_state.exact_objective
    jvp_rows: list[dict[str, object]] = []
    krylov_rows: list[dict[str, object]] = []
    trial_rows: list[NewtonKrylovTrial] = []
    accepted_rows: list[dict[str, object]] = []
    rebase_rows: list[CandidateMapRebase] = []
    step_rows: list[dict[str, object]] = []
    direction_node_rows: list[dict[str, object]] = []
    accepted_iterations = 0

    for outer_iteration in range(1, args.outer_iterations + 1):
        coupled, outer_shape_dipole_coefficient, rebase = (
            rebase_candidate_map_source(
                coupled,
                source_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                root_inner_iterations=args.root_inner_iterations,
                matching_surface_policy=args.matching_surface_policy,
                outer_iteration=outer_iteration,
                phase="pre_linearization",
            )
        )
        rebase_rows.append(rebase)
        source_nodes = np.column_stack(
            (
                coupled.outer_free_surface.node_xi,
                coupled.outer_free_surface.node_eta,
            )
        )
        source_state = formal_outer_state(coupled)
        source_metric_panel_length = source_state.panel_length
        source_residual_coupled = coupled
        source_residual_nodes = source_nodes
        candidate_geometry_reference_nodes = source_nodes
        if args.candidate_map_policy == "synchronize_candidate":
            # The synchronized map is not necessarily the identity at zero
            # displacement.  Evaluate that same map for F(0) so no dipole or
            # regrid change leaks into a finite-difference numerator.
            source_residual_coupled, source_residual_nodes, _ = (
                build_candidate_map(
                    coupled,
                    source_nodes,
                    np.zeros(len(source_nodes), dtype=float),
                    root_inner_iterations=args.root_inner_iterations,
                    matching_surface_policy=args.matching_surface_policy,
                    far_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                    candidate_map_policy=args.candidate_map_policy,
                )
            )
            candidate_geometry_reference_nodes = source_residual_nodes
        if args.candidate_map_policy == "synchronize_candidate":
            source_state = formal_outer_state(source_residual_coupled)
        basis = _basis(
            args.basis,
            source_metric_panel_length,
            args.mode_count,
            args.global_mode_count,
            args.support_fraction,
            args.fixed_root_node_count,
            args.fixed_far_node_count,
        )
        source_weak, projected_integral, unresolved_integral = reduced_residual(
            source_residual_coupled,
            basis,
            source_metric_panel_length,
        )
        source_aligned_vector: np.ndarray | None = None
        if args.residual_generator == "source_aligned_exact":
            source_full_block = endpoint_block_residual(
                source_state.panel_length,
                source_state.endpoint_residual,
                average_mode_count=len(source_state.panel_length),
                jump_mode_count=len(source_state.panel_length),
                metric_panel_length=source_metric_panel_length,
            )
            source_aligned_vector = source_aligned_householder_vector(
                source_full_block,
                reduced_size=args.mode_count,
            )
        source_reduced = direction_residual(
            source_residual_coupled,
            basis,
            source_metric_panel_length,
            residual_generator=args.residual_generator,
            jump_mode_count=args.jump_mode_count,
            source_aligned_vector=source_aligned_vector,
        )
        source_reduced_objective = float(np.dot(source_reduced, source_reduced))
        source_weak_objective = float(np.dot(source_weak, source_weak))
        source_exact_vector = exact_endpoint_residual_vector(
            source_state.panel_length,
            source_state.endpoint_residual,
            metric_panel_length=source_metric_panel_length,
        )
        source_curvature, source_turn = polyline_curvature_metrics(
            source_residual_nodes
        )
        if args.right_preconditioner == "geometric_midpoint":
            right_scale, geometric_ratios = geometric_right_preconditioner_scale(
                basis,
                source_nodes,
            )
        else:
            right_scale = np.ones(args.mode_count, dtype=float)
            geometric_ratios = np.ones(args.mode_count, dtype=float)
        jvp_call_count = 0
        sampled_directions: list[np.ndarray] = []
        sampled_exact_products: list[np.ndarray] = []
        latest_exact_product = np.zeros_like(source_exact_vector)

        def jacobian_product(direction: np.ndarray) -> np.ndarray:
            nonlocal jvp_call_count, latest_exact_product
            candidate_exact: dict[str, np.ndarray] = {}

            def evaluate_with_exact(displacement: np.ndarray) -> np.ndarray:
                candidate, _, _ = build_candidate_map(
                    coupled,
                    source_nodes,
                    displacement,
                    root_inner_iterations=args.root_inner_iterations,
                    matching_surface_policy=args.matching_surface_policy,
                    far_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                    candidate_map_policy=args.candidate_map_policy,
                    geometry_reference_nodes=candidate_geometry_reference_nodes,
                )
                candidate_state = formal_outer_state(candidate)
                candidate_exact["value"] = exact_endpoint_residual_vector(
                    candidate_state.panel_length,
                    candidate_state.endpoint_residual,
                    metric_panel_length=source_metric_panel_length,
                )
                residual = direction_residual(
                    candidate,
                    basis,
                    source_metric_panel_length,
                    residual_generator=args.residual_generator,
                    jump_mode_count=args.jump_mode_count,
                    source_aligned_vector=source_aligned_vector,
                )
                return residual

            product, record = matrix_free_directional_product(
                source_reduced,
                direction,
                basis,
                source_nodes,
                args.finite_difference_ratio,
                evaluate_with_exact,
            )
            direction_array = np.asarray(direction, dtype=float).copy()
            if record.direction_norm <= np.finfo(float).eps:
                exact_product = np.zeros_like(source_exact_vector)
            else:
                exact_product = (
                    candidate_exact["value"] - source_exact_vector
                ) / record.signed_finite_difference_step * record.direction_norm
            latest_exact_product = exact_product
            sampled_directions.append(direction_array)
            sampled_exact_products.append(exact_product.copy())
            jvp_call_count += 1
            row = {
                "outer_iteration": outer_iteration,
                "jvp_call": jvp_call_count,
                **asdict(record),
            }
            jvp_rows.append(row)
            print(json.dumps({"progress": "jvp_complete", **row}), flush=True)
            return product

        try:
            if args.direction_solver == "exact_coordinate_subspace":
                for coefficient_index in range(args.mode_count):
                    direction = np.zeros(args.mode_count, dtype=float)
                    direction[coefficient_index] = 1.0
                    jacobian_product(direction)
                step = np.zeros(args.mode_count, dtype=float)
                krylov_info = 0
                krylov_history: list[float] = []
            else:
                step, krylov_info, krylov_history = solve_matrix_free_newton_step(
                    source_reduced,
                    jacobian_product,
                    damping=args.damping,
                    relative_tolerance=args.krylov_relative_tolerance,
                    maximum_iterations=args.krylov_maximum_iterations,
                    right_preconditioner_scale=right_scale,
                )
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            trial_rows.append(
                NewtonKrylovTrial(
                    outer_iteration=outer_iteration,
                    step_factor=float("nan"),
                    formal_exact_objective=float("nan"),
                    formal_exact_relative_decrease=float("nan"),
                    reduced_objective=float("nan"),
                    projected_integral=float("nan"),
                    unresolved_integral=float("nan"),
                    unrepresented_projected_integral=float("nan"),
                    predicted_reduced_objective=float("nan"),
                    predicted_formal_exact_objective=float("nan"),
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
                        f"krylov_failure:{type(error).__name__}:{error}"
                    ),
                )
            )
            break

        for index, norm in enumerate(krylov_history, start=1):
            krylov_rows.append(
                {
                    "outer_iteration": outer_iteration,
                    "krylov_iteration": index,
                    "preconditioned_relative_residual": norm,
                    "gmres_info": krylov_info,
                }
            )
        subspace_rank = 0
        subspace_condition = float("nan")
        if args.direction_solver in {
            "exact_krylov_subspace",
            "exact_coordinate_subspace",
        }:
            step, exact_jacobian_step, subspace_rank, subspace_condition = (
                exact_krylov_subspace_gauss_newton_step(
                    source_exact_vector,
                    sampled_directions,
                    sampled_exact_products,
                    damping=args.damping,
                )
            )
        else:
            exact_jacobian_step = latest_exact_product.copy()
        unscaled_step = step.copy()
        normal_displacement = basis @ unscaled_step
        step_scale = trust_region_scale(
            source_nodes,
            normal_displacement,
            args.trust_radius_safety_factor * args.trust_radius,
        )
        step *= step_scale
        normal_displacement = basis @ step
        for coefficient_index, (unscaled, scaled) in enumerate(
            zip(unscaled_step, step, strict=True)
        ):
            step_rows.append(
                {
                    "outer_iteration": outer_iteration,
                    "coefficient_index": coefficient_index,
                    "unscaled_step": unscaled,
                    "trust_scaled_step": scaled,
                    "trust_region_step_scale": step_scale,
                }
            )
        for node_index, displacement_value in enumerate(normal_displacement):
            direction_node_rows.append(
                {
                    "outer_iteration": outer_iteration,
                    "node_index": node_index,
                    "normal_displacement": displacement_value,
                }
            )
        actual_jacobian_step = jacobian_product(step)
        if args.direction_solver == "reduced_gmres":
            exact_jacobian_step = latest_exact_product.copy()
        else:
            exact_jacobian_step *= step_scale

        candidates: list[tuple[NewtonKrylovTrial, object]] = []
        for factor in sorted(set(args.step_factors), reverse=True):
            try:
                candidate, candidate_nodes, displacement = build_candidate_map(
                    coupled,
                    source_nodes,
                    float(factor) * normal_displacement,
                    root_inner_iterations=args.root_inner_iterations,
                    matching_surface_policy=args.matching_surface_policy,
                    far_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                    candidate_map_policy=args.candidate_map_policy,
                    geometry_reference_nodes=candidate_geometry_reference_nodes,
                )
                candidate_state = formal_outer_state(candidate)
                candidate_weak, candidate_projected, candidate_unresolved = (
                    reduced_residual(
                    candidate,
                    basis,
                    source_metric_panel_length,
                    )
                )
                candidate_reduced = direction_residual(
                    candidate,
                    basis,
                    source_metric_panel_length,
                    residual_generator=args.residual_generator,
                    jump_mode_count=args.jump_mode_count,
                    source_aligned_vector=source_aligned_vector,
                )
                candidate_reduced_objective = float(
                    np.dot(candidate_reduced, candidate_reduced)
                )
                candidate_weak_objective = float(
                    np.dot(candidate_weak, candidate_weak)
                )
                predicted = source_reduced + float(factor) * actual_jacobian_step
                predicted_objective = float(np.dot(predicted, predicted))
                predicted_exact = (
                    source_exact_vector
                    + float(factor) * exact_jacobian_step
                )
                predicted_exact_objective = float(
                    np.dot(predicted_exact, predicted_exact)
                )
                predicted_reduction = (
                    source_state.exact_objective - predicted_exact_objective
                )
                trust_ratio = (
                    float("-inf")
                    if predicted_reduction <= 0.0
                    else (
                        source_state.exact_objective
                        - candidate_state.exact_objective
                    )
                    / predicted_reduction
                )
                candidate_curvature, candidate_turn = polyline_curvature_metrics(
                    candidate_nodes
                )
                curvature_ratio = candidate_curvature / max(
                    source_curvature, np.finfo(float).eps
                )
                reason = trial_rejection_reason(
                    source_objective=source_state.exact_objective,
                    candidate_objective=candidate_state.exact_objective,
                    minimum_relative_decrease=args.minimum_relative_decrease,
                    maximum_displacement_ratio_value=displacement,
                    displacement_limit=args.trust_radius,
                    source_condition_number=source_state.condition_number,
                    candidate_condition_number=candidate_state.condition_number,
                    condition_number_ratio_limit=args.condition_number_ratio_limit,
                    dipole_coefficient=candidate_state.dipole_coefficient,
                    root_relative_mismatch=candidate_state.root_relative_mismatch,
                    root_mismatch_limit=args.root_mismatch_limit,
                )
                if not reason and curvature_ratio > args.curvature_energy_ratio_limit:
                    reason = "curvature_energy"
                if not reason and trust_ratio < args.minimum_trust_ratio:
                    reason = "insufficient_trust_ratio"
                metric = NewtonKrylovTrial(
                    outer_iteration=outer_iteration,
                    step_factor=float(factor),
                    formal_exact_objective=candidate_state.exact_objective,
                    formal_exact_relative_decrease=(
                        source_state.exact_objective - candidate_state.exact_objective
                    )
                    / source_state.exact_objective,
                    reduced_objective=candidate_reduced_objective,
                    projected_integral=candidate_projected,
                    unresolved_integral=candidate_unresolved,
                    unrepresented_projected_integral=max(
                        0.0,
                        candidate_projected - candidate_weak_objective,
                    ),
                    predicted_reduced_objective=predicted_objective,
                    predicted_formal_exact_objective=(
                        predicted_exact_objective
                    ),
                    trust_ratio=trust_ratio,
                    maximum_displacement_ratio=displacement,
                    condition_number=candidate_state.condition_number,
                    condition_number_ratio=(
                        candidate_state.condition_number
                        / source_state.condition_number
                    ),
                    dipole_coefficient=candidate_state.dipole_coefficient,
                    root_relative_mismatch=candidate_state.root_relative_mismatch,
                    curvature_energy=candidate_curvature,
                    curvature_energy_ratio=curvature_ratio,
                    maximum_turning_angle_deg=candidate_turn,
                    accepted=not reason,
                    rejection_reason=reason,
                )
                candidates.append((metric, candidate))
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
                candidates.append(
                    (
                        NewtonKrylovTrial(
                            outer_iteration=outer_iteration,
                            step_factor=float(factor),
                            formal_exact_objective=float("nan"),
                            formal_exact_relative_decrease=float("nan"),
                            reduced_objective=float("nan"),
                            projected_integral=float("nan"),
                            unresolved_integral=float("nan"),
                            unrepresented_projected_integral=float("nan"),
                            predicted_reduced_objective=float("nan"),
                            predicted_formal_exact_objective=float("nan"),
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

        trial_rows.extend(item[0] for item in candidates)
        admissible = [item for item in candidates if item[0].accepted]
        if not admissible:
            break
        selected_metric, selected = min(
            admissible,
            key=lambda item: item[0].formal_exact_objective,
        )
        coupled = selected
        accepted_iterations += 1
        accepted_rows.append(
            {
                "outer_iteration": outer_iteration,
                "step_factor": selected_metric.step_factor,
                "source_formal_exact_objective": source_state.exact_objective,
                "candidate_formal_exact_objective": (
                    selected_metric.formal_exact_objective
                ),
                "formal_exact_relative_decrease": (
                    selected_metric.formal_exact_relative_decrease
                ),
                "source_reduced_objective": source_reduced_objective,
                "source_weak_objective": source_weak_objective,
                "residual_generator": args.residual_generator,
                "average_mode_count": (
                    args.mode_count - args.jump_mode_count
                    if args.residual_generator == "endpoint_block"
                    else None
                ),
                "jump_mode_count": (
                    args.jump_mode_count
                    if args.residual_generator == "endpoint_block"
                    else None
                ),
                "source_projected_integral": projected_integral,
                "source_unresolved_integral": unresolved_integral,
                "candidate_reduced_objective": selected_metric.reduced_objective,
                "candidate_projected_integral": selected_metric.projected_integral,
                "candidate_unresolved_integral": selected_metric.unresolved_integral,
                "candidate_unrepresented_projected_integral": (
                    selected_metric.unrepresented_projected_integral
                ),
                "gmres_info": krylov_info,
                "krylov_iterations": len(krylov_history),
                "jvp_calls": jvp_call_count,
                "direction_solver": args.direction_solver,
                "exact_subspace_rank": subspace_rank,
                "exact_subspace_condition_number": subspace_condition,
                "trust_region_step_scale": step_scale,
                "right_preconditioner": args.right_preconditioner,
                "right_scale_minimum": float(np.min(right_scale)),
                "right_scale_median": float(np.median(right_scale)),
                "right_scale_maximum": float(np.max(right_scale)),
                "geometric_ratio_minimum": float(np.min(geometric_ratios)),
                "geometric_ratio_median": float(np.median(geometric_ratios)),
                "geometric_ratio_maximum": float(np.max(geometric_ratios)),
                "source_curvature_energy": source_curvature,
                "source_maximum_turning_angle_deg": source_turn,
                "candidate_curvature_energy": selected_metric.curvature_energy,
                "candidate_root_relative_mismatch": (
                    selected_metric.root_relative_mismatch
                ),
            }
        )

    if accepted_iterations:
        coupled, outer_shape_dipole_coefficient, final_rebase = (
            rebase_candidate_map_source(
                coupled,
                source_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                root_inner_iterations=args.root_inner_iterations,
                matching_surface_policy=args.matching_surface_policy,
                outer_iteration=accepted_iterations,
                phase="final_synchronization",
            )
        )
        rebase_rows.append(final_rebase)
    final_state = formal_outer_state(coupled)
    pd.DataFrame(jvp_rows).to_csv(output / "newton_krylov_jvp.csv", index=False)
    pd.DataFrame(krylov_rows).to_csv(
        output / "newton_krylov_krylov_history.csv", index=False
    )
    pd.DataFrame([asdict(item) for item in trial_rows]).to_csv(
        output / "newton_krylov_trials.csv", index=False
    )
    pd.DataFrame(accepted_rows).to_csv(
        output / "newton_krylov_accepted.csv", index=False
    )
    pd.DataFrame([asdict(item) for item in rebase_rows]).to_csv(
        output / "newton_krylov_rebase.csv", index=False
    )
    pd.DataFrame(step_rows).to_csv(output / "newton_krylov_steps.csv", index=False)
    pd.DataFrame(direction_node_rows).to_csv(
        output / "newton_krylov_direction_nodes.csv", index=False
    )
    pd.DataFrame(
        {
            "node_index": np.arange(len(coupled.outer_free_surface.node_xi)),
            "xi": coupled.outer_free_surface.node_xi,
            "eta": coupled.outer_free_surface.node_eta,
        }
    ).to_csv(output / "newton_krylov_final_outer_nodes.csv", index=False)
    _write_final_artifacts(output, coupled)
    frozen = solve_coupled_self_similar_wedge_pseudo_time(
        coupled,
        maximum_iterations=0,
        root_inner_iterations=args.root_inner_iterations,
    )
    transformation = newton_krylov_transformation(
        basis_name=args.basis,
        mode_count=args.mode_count,
        global_mode_count=args.global_mode_count,
        support_fraction=args.support_fraction,
        fixed_root_node_count=args.fixed_root_node_count,
        fixed_far_node_count=args.fixed_far_node_count,
        root_inner_iterations=args.root_inner_iterations,
        matching_surface_policy=args.matching_surface_policy,
        finite_difference_ratio=args.finite_difference_ratio,
        damping=args.damping,
        krylov_relative_tolerance=args.krylov_relative_tolerance,
        krylov_maximum_iterations=args.krylov_maximum_iterations,
        right_preconditioner=args.right_preconditioner,
        outer_shape_dipole_coefficient=outer_shape_dipole_coefficient,
        direction_solver=args.direction_solver,
        residual_generator=args.residual_generator,
        jump_mode_count=args.jump_mode_count,
        candidate_map_policy=args.candidate_map_policy,
    )
    checkpoint_path = write_coupled_self_similar_checkpoint(
        output,
        coupled,
        coupled_pseudo_time_history_frame(frozen),
        parent=source_checkpoint,
        transformation=transformation,
    )
    summary = {
        "status": "self_similar_newton_krylov_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "source_checkpoint": str(args.checkpoint.resolve()),
        **transformation,
        "outer_iterations_requested": args.outer_iterations,
        "accepted_iterations": accepted_iterations,
        "initial_formal_exact_objective": initial_objective,
        "final_formal_exact_objective": final_state.exact_objective,
        "formal_objective_limit": args.formal_objective_limit,
        "final_root_relative_mismatch": final_state.root_relative_mismatch,
        "root_mismatch_limit": args.root_mismatch_limit,
        "formal_numerical_gate_pass": bool(
            final_state.exact_objective <= args.formal_objective_limit
            and final_state.root_relative_mismatch <= args.root_mismatch_limit
        ),
        "final_condition_number": final_state.condition_number,
        "checkpoint": str(checkpoint_path),
        "conclusion": (
            "accepted_reference_isolated_newton_krylov_step"
            if accepted_iterations
            else "no_admissible_newton_krylov_step"
        ),
    }
    (output / "newton_krylov_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
