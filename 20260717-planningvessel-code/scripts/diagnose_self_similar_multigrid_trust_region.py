from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    SelfSimilarCoupledCheckpoint,
    coupled_pseudo_time_history_frame,
    load_coupled_self_similar_checkpoint,
    regrid_coupled_self_similar_checkpoint,
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
    damped_gauss_newton_step,
    dct_nodal_basis,
    dual_endpoint_local_nodal_basis,
    exact_endpoint_residual_vector,
    far_local_nodal_basis,
    fix_endpoint_basis_nodes,
    polyline_curvature_metrics,
    root_local_nodal_basis,
    root_cosine_local_nodal_basis,
    trust_region_scale,
)
from scripts.resume_self_similar_wedge import _write_final_artifacts


CANDIDATE_ROOT_SEED_POLICY = "inherit_source"


@dataclass(frozen=True)
class GridState:
    panel_count: int
    exact_objective: float
    signed_root_defect: float
    root_relative_mismatch: float
    condition_number: float
    dipole_coefficient: float


@dataclass(frozen=True)
class MultigridTrial:
    step_factor: float
    normalized_objective: float
    normalized_relative_decrease: float
    predicted_normalized_objective: float
    trust_ratio: float
    maximum_grid_objective_ratio: float
    maximum_leading_panel_objective_ratio: float
    maximum_root_relative_mismatch: float
    maximum_condition_number: float
    maximum_condition_number_ratio: float
    maximum_displacement_ratio: float
    curvature_energy: float
    curvature_energy_ratio: float
    maximum_turning_angle_deg: float
    dipole_coefficient: float
    feasibility_repair: bool
    accepted: bool
    rejection_reason: str


def linearization_panel_counts(
    objective_panel_counts: tuple[int, ...],
    root_constraint_panel_counts: tuple[int, ...],
    root_constraint: str,
) -> tuple[int, ...]:
    """Return only grids needed to construct the local linear model.

    Root-validation grids are intentionally absent here. They are still solved
    for every nonlinear trial, but need not be repeated for every finite-
    difference mode when they do not enter the objective or linear constraint.
    """

    objective = tuple(int(value) for value in objective_panel_counts)
    constraint = tuple(int(value) for value in root_constraint_panel_counts)
    if not objective:
        raise ValueError("At least one objective grid is required.")
    active_constraint = () if root_constraint == "none" else constraint
    return tuple(sorted(set(objective) | set(active_constraint)))


def normalized_multigrid_residual(
    residual_by_grid: dict[int, np.ndarray],
    source_objective_by_grid: dict[int, float],
    weight_by_grid: dict[int, float],
) -> np.ndarray:
    """Stack grid residuals so each grid contributes a weighted relative error."""

    if set(residual_by_grid) != set(source_objective_by_grid) or set(
        residual_by_grid
    ) != set(weight_by_grid):
        raise ValueError("Multigrid residual, source objective, and weights must align.")
    total_weight = float(sum(weight_by_grid.values()))
    if not np.isfinite(total_weight) or total_weight <= 0.0:
        raise ValueError("Multigrid weights must have a positive finite sum.")
    blocks: list[np.ndarray] = []
    for count in sorted(residual_by_grid):
        residual = np.asarray(residual_by_grid[count], dtype=float)
        source_objective = float(source_objective_by_grid[count])
        weight = float(weight_by_grid[count]) / total_weight
        if (
            residual.ndim != 1
            or not np.isfinite(residual).all()
            or not np.isfinite(source_objective)
            or source_objective <= 0.0
            or not np.isfinite(weight)
            or weight <= 0.0
        ):
            raise ValueError("Multigrid residual normalization requires positive data.")
        blocks.append(np.sqrt(weight / source_objective) * residual)
    return np.concatenate(blocks)


def apply_leading_panel_objective_weight(
    residual: np.ndarray,
    jacobian: np.ndarray,
    objective_panel_counts: tuple[int, ...],
    leading_panel_count: int,
    leading_panel_weight: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Precondition leading panel rows without changing the physical objective."""

    vector = np.asarray(residual, dtype=float)
    matrix = np.asarray(jacobian, dtype=float)
    counts = tuple(sorted(int(value) for value in objective_panel_counts))
    if vector.ndim != 1 or matrix.ndim != 2 or matrix.shape[0] != len(vector):
        raise ValueError("Residual and Jacobian must have aligned row dimensions.")
    if not counts or any(value < 1 for value in counts):
        raise ValueError("Objective panel counts must be positive.")
    if leading_panel_count < 0 or leading_panel_count > min(counts):
        raise ValueError("Leading panel count must fit every objective grid.")
    if not np.isfinite(leading_panel_weight) or leading_panel_weight <= 0.0:
        raise ValueError("Leading panel weight must be positive and finite.")
    expected_rows = 2 * sum(counts)
    if len(vector) != expected_rows:
        raise ValueError(
            "Leading-panel preconditioning requires two residual rows per panel."
        )

    weighted_residual = vector.copy()
    weighted_jacobian = matrix.copy()
    scale = float(np.sqrt(leading_panel_weight))
    offset = 0
    for count in counts:
        leading_rows = 2 * leading_panel_count
        weighted_residual[offset : offset + leading_rows] *= scale
        weighted_jacobian[offset : offset + leading_rows, :] *= scale
        offset += 2 * count
    return weighted_residual, weighted_jacobian


def leading_panel_objective_by_grid(
    residual_by_grid: dict[int, np.ndarray],
    leading_panel_count: int,
) -> dict[int, float]:
    """Return exact residual energy in the leading panel window of each grid."""

    count = int(leading_panel_count)
    if count < 1:
        raise ValueError("Leading panel objective count must be positive.")
    result: dict[int, float] = {}
    for panel_count, values in residual_by_grid.items():
        residual = np.asarray(values, dtype=float)
        if panel_count < count or residual.shape != (2 * int(panel_count),):
            raise ValueError("Leading panel objective data have incompatible shapes.")
        if not np.isfinite(residual).all():
            raise ValueError("Leading panel objective data must be finite.")
        result[int(panel_count)] = float(np.dot(residual[: 2 * count], residual[: 2 * count]))
    return result


def maximum_objective_ratio(
    source_by_grid: dict[int, float], candidate_by_grid: dict[int, float]
) -> float:
    """Return the largest aligned positive candidate/source objective ratio."""

    if set(source_by_grid) != set(candidate_by_grid) or not source_by_grid:
        raise ValueError("Source and candidate objective windows must align.")
    ratios: list[float] = []
    for count in sorted(source_by_grid):
        source = float(source_by_grid[count])
        candidate = float(candidate_by_grid[count])
        if (
            not np.isfinite(source)
            or not np.isfinite(candidate)
            or source <= 0.0
            or candidate < 0.0
        ):
            raise ValueError("Objective window values must be finite and admissible.")
        ratios.append(candidate / source)
    return max(ratios)


def validate_reusable_jacobian_summary(
    summary: dict[str, object],
    *,
    source_checkpoint: Path,
    objective_panel_counts: tuple[int, ...],
    objective_panel_weights: tuple[float, ...],
    root_constraint_panel_counts: tuple[int, ...],
    mode_count: int,
    basis: str = "dct",
    global_mode_count: int = 2,
    local_support_fraction: float = 0.15,
    fixed_root_node_count: int = 0,
    fixed_far_node_count: int = 0,
    root_inner_iterations: int = 0,
    matching_surface_policy: str = "fixed_branch",
) -> int:
    """Require identical metadata and return an available shape-mode prefix."""

    expected = {
        "source_checkpoint": str(source_checkpoint.resolve()),
        "objective_panel_counts": list(objective_panel_counts),
        "objective_panel_weights": list(objective_panel_weights),
        "candidate_root_seed_policy": CANDIDATE_ROOT_SEED_POLICY,
        "root_inner_iterations": int(root_inner_iterations),
        "matching_surface_policy": str(matching_surface_policy),
        "reference_used_during_solve": False,
    }
    for name, value in expected.items():
        if summary.get(name) != value:
            raise ValueError(f"Reusable multigrid Jacobian disagrees in {name}.")
    saved_basis = str(summary.get("basis", "dct"))
    if saved_basis != basis:
        raise ValueError("Reusable multigrid Jacobian disagrees in basis.")
    if basis != "dct" and (
        int(summary.get("global_mode_count", -1)) != int(global_mode_count)
        or not np.isclose(
            float(summary.get("local_support_fraction", float("nan"))),
            float(local_support_fraction),
        )
    ):
        raise ValueError("Reusable endpoint-local basis metadata disagrees.")
    if int(summary.get("fixed_root_node_count", 0)) != int(
        fixed_root_node_count
    ) or int(summary.get("fixed_far_node_count", 0)) != int(fixed_far_node_count):
        raise ValueError("Reusable multigrid Jacobian disagrees in fixed endpoints.")

    available = set(summary.get("root_constraint_panel_counts", []))
    requested = set(root_constraint_panel_counts)
    if not requested.issubset(available):
        missing = sorted(requested - available)
        raise ValueError(
            "Reusable multigrid root Jacobian lacks requested panel counts: "
            f"{missing}."
        )
    available_mode_count = int(summary.get("mode_count", 0))
    if available_mode_count < 1 or available_mode_count > mode_count:
        raise ValueError(
            "Reusable multigrid Jacobian has an incompatible mode prefix."
        )
    if basis != "dct" and available_mode_count != mode_count:
        raise ValueError(
            "Endpoint-local Jacobians cannot be reused as mode prefixes."
        )
    return available_mode_count


def multigrid_shape_basis(
    panel_length: np.ndarray,
    mode_count: int,
    *,
    basis: str,
    global_mode_count: int,
    local_support_fraction: float,
) -> np.ndarray:
    """Build the declared global or endpoint-local multigrid shape basis."""

    length = np.asarray(panel_length, dtype=float)
    if basis == "dct":
        return dct_nodal_basis(len(length) + 1, mode_count)
    builders = {
        "root_local": root_local_nodal_basis,
        "root_cosine_local": root_cosine_local_nodal_basis,
        "far_local": far_local_nodal_basis,
        "dual_endpoint_local": dual_endpoint_local_nodal_basis,
    }
    if basis not in builders:
        raise ValueError(f"Unknown multigrid shape basis: {basis}.")
    return builders[basis](
        length,
        mode_count,
        global_mode_count=global_mode_count,
        support_fraction=local_support_fraction,
    )


def root_constraint_rhs(
    source_defect: np.ndarray,
    mode: str,
    target_defect: np.ndarray | None = None,
) -> np.ndarray:
    """Return the linearized equality right-hand side for root control."""

    source = np.asarray(source_defect, dtype=float)
    if source.ndim != 1 or not np.isfinite(source).all():
        raise ValueError("Source root defects must be a finite vector.")
    if mode == "preserve":
        return np.zeros_like(source)
    if mode == "close":
        return -source
    if mode == "target":
        if target_defect is None:
            raise ValueError("Target root defects are required for target mode.")
        target = np.asarray(target_defect, dtype=float)
        if target.shape != source.shape or not np.isfinite(target).all():
            raise ValueError("Target root defects must match the source vector.")
        return target - source
    raise ValueError(f"Unsupported root-constraint mode: {mode}.")


def multi_constraint_damped_gauss_newton_step(
    jacobian: np.ndarray,
    residual: np.ndarray,
    damping: float,
    constraint_jacobian: np.ndarray,
    constraint_rhs: np.ndarray,
) -> np.ndarray:
    """Solve a scaled damped Gauss--Newton step with multiple equalities."""

    matrix = np.asarray(jacobian, dtype=float)
    vector = np.asarray(residual, dtype=float)
    constraints = np.asarray(constraint_jacobian, dtype=float)
    right_constraint = np.asarray(constraint_rhs, dtype=float)
    if matrix.ndim != 2 or vector.shape != (matrix.shape[0],):
        raise ValueError("Multigrid Gauss--Newton residual dimensions do not match.")
    if constraints.ndim != 2 or constraints.shape[1] != matrix.shape[1]:
        raise ValueError("Constraint Jacobian must have one column per shape mode.")
    if right_constraint.shape != (constraints.shape[0],):
        raise ValueError("Constraint right-hand side has an incompatible length.")
    if constraints.shape[0] < 1 or np.linalg.matrix_rank(constraints) < constraints.shape[0]:
        raise ValueError("Multigrid root constraints must be non-empty and independent.")
    if not all(
        np.isfinite(item).all()
        for item in (matrix, vector, constraints, right_constraint)
    ):
        raise ValueError("Multigrid Gauss--Newton inputs must be finite.")
    regularization = float(damping)
    if not np.isfinite(regularization) or regularization < 0.0:
        raise ValueError("Gauss--Newton damping must be finite and non-negative.")
    normal = matrix.T @ matrix
    scale = np.maximum(np.diag(normal), np.finfo(float).eps)
    system = normal + regularization * np.diag(scale)
    kkt = np.block(
        [
            [system, constraints.T],
            [constraints, np.zeros((constraints.shape[0], constraints.shape[0]))],
        ]
    )
    right = np.concatenate((-(matrix.T @ vector), right_constraint))
    return np.linalg.solve(kkt, right)[: matrix.shape[1]]


def bounded_root_damped_gauss_newton_step(
    jacobian: np.ndarray,
    residual: np.ndarray,
    damping: float,
    constraint_jacobian: np.ndarray,
    source_defect: np.ndarray,
    root_bound: float,
) -> tuple[np.ndarray, tuple[str, ...], np.ndarray]:
    """Solve the linearized residual problem subject to symmetric root bounds."""

    matrix = np.asarray(jacobian, dtype=float)
    vector = np.asarray(residual, dtype=float)
    constraints = np.asarray(constraint_jacobian, dtype=float)
    source = np.asarray(source_defect, dtype=float)
    bound = float(root_bound)
    if matrix.ndim != 2 or vector.shape != (matrix.shape[0],):
        raise ValueError("Bounded Gauss--Newton residual dimensions do not match.")
    if constraints.ndim != 2 or constraints.shape[1] != matrix.shape[1]:
        raise ValueError("Bounded root Jacobian must have one column per mode.")
    if source.shape != (constraints.shape[0],):
        raise ValueError("Source root defects must match the bounded constraints.")
    if constraints.shape[0] < 1 or constraints.shape[0] > 6:
        raise ValueError("Bounded root active-set enumeration supports 1 to 6 roots.")
    if not all(np.isfinite(item).all() for item in (matrix, vector, constraints, source)):
        raise ValueError("Bounded Gauss--Newton inputs must be finite.")
    if not np.isfinite(bound) or bound <= 0.0:
        raise ValueError("The root bound must be positive and finite.")
    tolerance = 64.0 * np.finfo(float).eps * max(1.0, bound)

    normal = matrix.T @ matrix
    scale = np.maximum(np.diag(normal), np.finfo(float).eps)
    regularization = float(damping)
    candidates: list[tuple[float, int, np.ndarray, tuple[int, ...], np.ndarray]] = []
    for active_state in product((-1, 0, 1), repeat=constraints.shape[0]):
        active = tuple(index for index, state in enumerate(active_state) if state)
        try:
            if active:
                active_rows = constraints[np.asarray(active, dtype=int)]
                targets = np.asarray(
                    [active_state[index] * bound for index in active], dtype=float
                )
                step = multi_constraint_damped_gauss_newton_step(
                    matrix,
                    vector,
                    regularization,
                    active_rows,
                    targets - source[np.asarray(active, dtype=int)],
                )
            else:
                step = damped_gauss_newton_step(matrix, vector, regularization)
        except (ValueError, np.linalg.LinAlgError):
            continue
        predicted_root = source + constraints @ step
        if np.max(np.abs(predicted_root)) > bound + tolerance:
            continue
        predicted_residual = vector + matrix @ step
        score = float(
            np.dot(predicted_residual, predicted_residual)
            + regularization * np.dot(scale * step, step)
        )
        if np.isfinite(score):
            candidates.append((score, len(active), step, active_state, predicted_root))

    if not candidates:
        raise ValueError("No feasible bounded-root Gauss--Newton active set exists.")
    _, _, step, active_state, predicted_root = min(
        candidates, key=lambda item: (item[0], item[1])
    )
    labels = tuple(
        "lower" if state < 0 else "upper" if state > 0 else "free"
        for state in active_state
    )
    return step, labels, predicted_root


def grid_objective_limit_rejection_reason(
    source_by_grid: dict[int, float],
    candidate_by_grid: dict[int, float],
    objective_limit: float,
) -> str:
    """Keep feasible grids feasible and require violating grids to improve."""

    if set(source_by_grid) != set(candidate_by_grid):
        raise ValueError("Source and candidate grid objectives must align.")
    limit = float(objective_limit)
    if not np.isfinite(limit) or limit <= 0.0:
        raise ValueError("The grid objective limit must be positive and finite.")
    for count in sorted(source_by_grid):
        source = float(source_by_grid[count])
        candidate = float(candidate_by_grid[count])
        if not np.isfinite(source) or not np.isfinite(candidate) or source <= 0.0:
            return "invalid_individual_grid_objective"
        if source <= limit and candidate > limit:
            return "feasible_grid_left_objective_limit"
        if source > limit and candidate >= source:
            return "violating_grid_not_improved"
    return ""


def _ephemeral_checkpoint(
    source: SelfSimilarCoupledCheckpoint,
    coupled: object,
    outer_shape_dipole_coefficient: float,
) -> SelfSimilarCoupledCheckpoint:
    return SelfSimilarCoupledCheckpoint(
        source_directory=source.source_directory,
        source_kind="in_memory_multigrid_candidate",
        config=coupled.config,
        coupled=coupled,
        history=pd.DataFrame(),
        outer_shape_dipole_coefficient=float(outer_shape_dipole_coefficient),
        completed_iterations=0,
        cumulative_pseudo_time=0.0,
        source_hashes={},
        reconstruction_relative_errors={},
        continuation_config_overrides={},
    )


def resolved_source_jet_bie_panel_count(coupled: object) -> int:
    """Preserve the realized jet topology of legacy adaptive checkpoints."""

    configured = coupled.config.coupled_jet_bie_panel_count
    if configured is not None:
        return int(configured)
    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    realized = int(np.count_nonzero(labels == "shallow_jet_body"))
    if realized < 2:
        raise ValueError(
            "A legacy checkpoint has no resolved shallow-jet topology to preserve."
        )
    return realized


def _rebuild_grids(
    source: SelfSimilarCoupledCheckpoint,
    coupled: object,
    panel_counts: tuple[int, ...],
    *,
    outer_shape_dipole_coefficient: float,
    root_inner_iterations: int,
) -> dict[int, object]:
    source_count = int(coupled.config.free_surface_panels)
    checkpoint = _ephemeral_checkpoint(
        source,
        coupled,
        outer_shape_dipole_coefficient,
    )
    jet_bie_panel_count = resolved_source_jet_bie_panel_count(coupled)
    rebuilt: dict[int, object] = {}
    for count in panel_counts:
        if count == source_count:
            rebuilt[count] = coupled
        else:
            rebuilt[count] = regrid_coupled_self_similar_checkpoint(
                checkpoint,
                count,
                root_inner_iterations=root_inner_iterations,
                jet_bie_panel_count=jet_bie_panel_count,
            ).coupled
    return rebuilt


def _grid_residual_and_state(coupled: object) -> tuple[np.ndarray, GridState]:
    endpoint = coupled.outer_kinematic_residual_endpoint
    if endpoint is None:
        raise ValueError("Multigrid trust region requires continuous linear elements.")
    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    length = coupled.boundary.panel_length_m[labels == "outer_free_surface"]
    residual = exact_endpoint_residual_vector(length, endpoint)
    measured = derive_shallow_water_jet_root_state_from_coupled(coupled)
    interface = coupled.jet_interface.root_state.s_lambda
    signed_defect = (measured.s_lambda - interface) / max(
        abs(interface), np.finfo(float).eps
    )
    state = GridState(
        panel_count=int(coupled.config.free_surface_panels),
        exact_objective=float(np.dot(residual, residual)),
        signed_root_defect=float(signed_defect),
        root_relative_mismatch=abs(float(signed_defect)),
        condition_number=float(coupled.solution.condition_number),
        dipole_coefficient=float(coupled.dipole_coefficient),
    )
    return residual, state


def _evaluate_grids(
    source: SelfSimilarCoupledCheckpoint,
    coupled: object,
    panel_counts: tuple[int, ...],
    *,
    outer_shape_dipole_coefficient: float,
    root_inner_iterations: int,
) -> tuple[dict[int, np.ndarray], dict[int, GridState]]:
    rebuilt = _rebuild_grids(
        source,
        coupled,
        panel_counts,
        outer_shape_dipole_coefficient=outer_shape_dipole_coefficient,
        root_inner_iterations=root_inner_iterations,
    )
    residuals: dict[int, np.ndarray] = {}
    states: dict[int, GridState] = {}
    for count, item in rebuilt.items():
        residuals[count], states[count] = _grid_residual_and_state(item)
    return residuals, states


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reference-isolated multigrid residual and root-constraint trust "
            "region for one coupled self-similar wedge step."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode-count", type=int, default=16)
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
    parser.add_argument("--local-support-fraction", type=float, default=0.15)
    parser.add_argument(
        "--fixed-root-node-count",
        type=int,
        default=0,
        help="Leading matching-surface nodes held fixed in every shape mode.",
    )
    parser.add_argument(
        "--fixed-far-node-count",
        type=int,
        default=0,
        help="Trailing far-field nodes held fixed in every shape mode.",
    )
    parser.add_argument(
        "--objective-panel-counts", type=int, nargs="+", required=True
    )
    parser.add_argument("--objective-panel-weights", type=float, nargs="+", default=None)
    parser.add_argument(
        "--leading-panel-objective-count",
        type=int,
        default=0,
        help=(
            "Leading panels per objective grid preconditioned during direction "
            "construction only; nonlinear acceptance remains unweighted."
        ),
    )
    parser.add_argument(
        "--leading-panel-objective-weight",
        type=float,
        default=1.0,
        help=(
            "Positive least-squares weight applied to each selected leading-panel "
            "residual row during direction construction only."
        ),
    )
    parser.add_argument(
        "--leading-panel-objective-ratio-limit",
        type=float,
        default=None,
        help=(
            "Optional nonlinear hard limit on each validation grid's leading-panel "
            "exact residual energy relative to its source value."
        ),
    )
    parser.add_argument(
        "--objective-validation-panel-counts",
        type=int,
        nargs="+",
        default=None,
        help=(
            "Panel counts subject to nonlinear per-grid objective acceptance. "
            "Defaults to the objective counts but may include finer grids that "
            "do not enter the finite-difference Jacobian."
        ),
    )
    parser.add_argument(
        "--root-constraint-panel-counts", type=int, nargs="+", default=None
    )
    parser.add_argument(
        "--root-validation-panel-counts",
        type=int,
        nargs="+",
        default=None,
        help=(
            "Panel counts checked against the nonlinear hard root limit. "
            "Defaults to the root-constraint counts."
        ),
    )
    parser.add_argument(
        "--root-constraint",
        choices=("none", "preserve", "close", "target", "bounded"),
        default="close",
    )
    parser.add_argument(
        "--root-target-defects",
        type=float,
        nargs="+",
        default=None,
        help="Signed target defects, one per root-constraint grid, for target mode.",
    )
    parser.add_argument(
        "--root-bound-safety-factor",
        type=float,
        default=0.95,
        help="Fraction of the nonlinear hard root limit used by bounded mode.",
    )
    parser.add_argument(
        "--reuse-jacobian-run",
        type=Path,
        default=None,
        help=(
            "Reuse a frozen multigrid Jacobian generated from the same source, "
            "objective grids, weights, constraint grids, and mode count."
        ),
    )
    parser.add_argument("--finite-difference-ratio", type=float, default=0.002)
    parser.add_argument("--trust-radius", type=float, default=0.25)
    parser.add_argument("--trust-radius-safety-factor", type=float, default=1.0)
    parser.add_argument("--damping", type=float, default=1.0e-3)
    parser.add_argument(
        "--step-factors", type=float, nargs="+", default=(1.0, 0.5, 0.25)
    )
    parser.add_argument("--minimum-trust-ratio", type=float, default=0.05)
    parser.add_argument("--minimum-relative-decrease", type=float, default=1.0e-4)
    parser.add_argument(
        "--allow-feasibility-repair",
        action="store_true",
        help=(
            "Allow a candidate that repairs an initially violated root hard limit "
            "while all absolute grid objectives remain feasible."
        ),
    )
    parser.add_argument("--maximum-grid-objective-ratio", type=float, default=1.001)
    parser.add_argument(
        "--grid-objective-limit",
        type=float,
        default=None,
        help=(
            "Optional absolute per-grid objective limit. Feasible grids must remain "
            "feasible and violating grids must improve."
        ),
    )
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.05)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument("--curvature-energy-ratio-limit", type=float, default=1.10)
    parser.add_argument("--root-inner-iterations", type=int, default=0)
    parser.add_argument(
        "--matching-surface-policy",
        choices=("fixed_branch", "relocate"),
        default="fixed_branch",
    )
    return parser


def _validated_counts(values: list[int], source_count: int, name: str) -> tuple[int, ...]:
    counts = tuple(int(value) for value in values)
    if len(counts) < 1 or len(set(counts)) != len(counts):
        raise ValueError(f"{name} must contain unique panel counts.")
    if any(value < source_count for value in counts):
        raise ValueError(f"{name} cannot be coarser than the source grid.")
    return counts


def main() -> int:
    args = _parser().parse_args()
    source = load_coupled_self_similar_checkpoint(args.checkpoint.resolve())
    coupled = source.coupled
    source_count = int(coupled.config.free_surface_panels)
    objective_counts = _validated_counts(
        args.objective_panel_counts,
        source_count,
        "objective-panel-counts",
    )
    constraint_counts = _validated_counts(
        (
            args.root_constraint_panel_counts
            if args.root_constraint_panel_counts is not None
            else list(objective_counts)
        ),
        source_count,
        "root-constraint-panel-counts",
    )
    objective_validation_counts = _validated_counts(
        (
            args.objective_validation_panel_counts
            if args.objective_validation_panel_counts is not None
            else list(objective_counts)
        ),
        source_count,
        "objective-validation-panel-counts",
    )
    validation_counts = _validated_counts(
        (
            args.root_validation_panel_counts
            if args.root_validation_panel_counts is not None
            else list(constraint_counts)
        ),
        source_count,
        "root-validation-panel-counts",
    )
    all_counts = tuple(
        sorted(
            set(objective_counts)
            | set(objective_validation_counts)
            | set(constraint_counts)
            | set(validation_counts)
        )
    )
    linearization_counts = linearization_panel_counts(
        objective_counts,
        constraint_counts,
        args.root_constraint,
    )
    if (
        args.root_constraint != "none"
        and args.mode_count < len(constraint_counts)
    ) or args.mode_count > source_count + 1:
        raise ValueError("mode-count must cover all constraints and fit the source nodes.")
    if (
        args.fixed_root_node_count < 0
        or args.fixed_far_node_count < 0
        or args.fixed_root_node_count + args.fixed_far_node_count
        >= source_count + 1
    ):
        raise ValueError("Fixed endpoint counts must leave at least one movable node.")
    if not 0.0 < args.finite_difference_ratio <= args.trust_radius <= 0.25:
        raise ValueError("Require 0 < finite-difference-ratio <= trust-radius <= 0.25.")
    if not 0.0 < args.trust_radius_safety_factor <= 1.0:
        raise ValueError("trust-radius-safety-factor must lie in (0, 1].")
    if not 0.0 < args.root_bound_safety_factor <= 1.0:
        raise ValueError("root-bound-safety-factor must lie in (0, 1].")
    if args.grid_objective_limit is not None and (
        not np.isfinite(args.grid_objective_limit)
        or args.grid_objective_limit <= 0.0
    ):
        raise ValueError("grid-objective-limit must be positive and finite.")
    if any(value <= 0.0 or not np.isfinite(value) for value in args.step_factors):
        raise ValueError("step-factors must be finite and positive.")
    if args.objective_panel_weights is None:
        weights = np.ones(len(objective_counts), dtype=float)
    else:
        weights = np.asarray(args.objective_panel_weights, dtype=float)
        if weights.shape != (len(objective_counts),):
            raise ValueError("objective-panel-weights must match objective counts.")
    if not np.isfinite(weights).all() or np.any(weights <= 0.0):
        raise ValueError("objective-panel-weights must be finite and positive.")
    weight_by_grid = dict(zip(objective_counts, weights))
    if (
        args.leading_panel_objective_count < 0
        or args.leading_panel_objective_count > min(objective_counts)
    ):
        raise ValueError(
            "leading-panel-objective-count must fit every objective grid."
        )
    if (
        not np.isfinite(args.leading_panel_objective_weight)
        or args.leading_panel_objective_weight <= 0.0
    ):
        raise ValueError(
            "leading-panel-objective-weight must be positive and finite."
        )
    if args.leading_panel_objective_ratio_limit is not None and (
        args.leading_panel_objective_count < 1
        or not np.isfinite(args.leading_panel_objective_ratio_limit)
        or args.leading_panel_objective_ratio_limit <= 0.0
    ):
        raise ValueError(
            "leading-panel-objective-ratio-limit requires a positive panel count "
            "and a positive finite ratio."
        )

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    outer_shape_dipole_coefficient = float(coupled.dipole_coefficient)
    source_nodes = np.column_stack(
        (coupled.outer_free_surface.node_xi, coupled.outer_free_surface.node_eta)
    )
    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    source_panel_length = coupled.boundary.panel_length_m[
        labels == "outer_free_surface"
    ]
    source_curvature, source_turn = polyline_curvature_metrics(source_nodes)
    basis = multigrid_shape_basis(
        source_panel_length,
        args.mode_count,
        basis=args.basis,
        global_mode_count=args.global_mode_count,
        local_support_fraction=args.local_support_fraction,
    )
    basis = fix_endpoint_basis_nodes(
        basis,
        source_panel_length,
        fixed_root_node_count=args.fixed_root_node_count,
        fixed_far_node_count=args.fixed_far_node_count,
    )
    source_residuals, source_states = _evaluate_grids(
        source,
        coupled,
        all_counts,
        outer_shape_dipole_coefficient=outer_shape_dipole_coefficient,
        root_inner_iterations=args.root_inner_iterations,
    )
    source_objective_by_grid = {
        count: source_states[count].exact_objective for count in objective_counts
    }
    residual = normalized_multigrid_residual(
        {count: source_residuals[count] for count in objective_counts},
        source_objective_by_grid,
        weight_by_grid,
    )
    normalized_source_objective = float(np.dot(residual, residual))
    source_leading_objective_by_grid = (
        None
        if args.leading_panel_objective_count < 1
        else leading_panel_objective_by_grid(
            {
                count: source_residuals[count]
                for count in objective_validation_counts
            },
            args.leading_panel_objective_count,
        )
    )
    jacobian = np.empty((len(residual), args.mode_count), dtype=float)
    constraint_jacobian = np.empty(
        (len(constraint_counts), args.mode_count), dtype=float
    )
    finite_difference_steps = np.empty(args.mode_count, dtype=float)
    grid_rows: list[dict[str, object]] = []
    root_jacobian_rows: list[dict[str, float | int]] = []
    jacobian_rows: list[dict[str, float | int]] = []
    reused_mode_count = 0

    for count in all_counts:
        grid_rows.append({"stage": "source", **asdict(source_states[count])})

    source_root_defect = np.asarray(
        [source_states[count].signed_root_defect for count in constraint_counts],
        dtype=float,
    )
    source_has_validation_root_violation = any(
        source_states[count].root_relative_mismatch > args.root_mismatch_limit
        for count in validation_counts
    )
    target_root_defect: np.ndarray | None = None
    if args.root_constraint == "target":
        if args.root_target_defects is None or len(args.root_target_defects) != len(
            constraint_counts
        ):
            raise ValueError(
                "--root-target-defects must provide one value per root-constraint grid."
            )
        target_root_defect = np.asarray(args.root_target_defects, dtype=float)
        if (
            not np.isfinite(target_root_defect).all()
            or np.max(np.abs(target_root_defect)) > args.root_mismatch_limit
        ):
            raise ValueError(
                "Target root defects must be finite and within the root mismatch limit."
            )
    elif args.root_target_defects is not None:
        raise ValueError("--root-target-defects is only valid with target mode.")
    normals = angle_bisector_normals(source_nodes)
    if args.reuse_jacobian_run is not None:
        reuse = args.reuse_jacobian_run.resolve()
        reuse_summary = json.loads(
            (reuse / "multigrid_trust_region_summary.json").read_text(
                encoding="utf-8"
            )
        )
        reused_mode_count = validate_reusable_jacobian_summary(
            reuse_summary,
            source_checkpoint=args.checkpoint,
            objective_panel_counts=objective_counts,
            objective_panel_weights=tuple(
                weight_by_grid[count] for count in objective_counts
            ),
            root_constraint_panel_counts=constraint_counts,
            mode_count=args.mode_count,
            basis=args.basis,
            global_mode_count=args.global_mode_count,
            local_support_fraction=args.local_support_fraction,
            fixed_root_node_count=args.fixed_root_node_count,
            fixed_far_node_count=args.fixed_far_node_count,
            root_inner_iterations=args.root_inner_iterations,
            matching_surface_policy=args.matching_surface_policy,
        )
        reused_jacobian_frame = pd.read_csv(
            reuse / "multigrid_trust_region_jacobians.csv"
        )
        reused_root_jacobian_frame = pd.read_csv(
            reuse / "multigrid_trust_region_root_jacobians.csv"
        )
        reused_jacobian = reused_jacobian_frame.pivot(
            index="residual_row",
            columns="shape_mode",
            values="value",
        ).sort_index(axis=1)
        reused_constraint_jacobian = reused_root_jacobian_frame.pivot(
            index="panel_count",
            columns="shape_mode",
            values="value",
        ).loc[list(constraint_counts)].sort_index(axis=1)
        reused_finite_difference_steps = (
            reused_jacobian_frame.groupby("shape_mode")["finite_difference_step"]
            .first()
            .sort_index()
            .to_numpy(dtype=float)
        )
        expected_columns = list(range(reused_mode_count))
        if list(reused_jacobian.columns) != expected_columns or list(
            reused_constraint_jacobian.columns
        ) != expected_columns:
            raise ValueError("Reusable multigrid Jacobian modes are not a prefix.")
        if reused_jacobian.shape != (len(residual), reused_mode_count):
            raise ValueError("Reusable multigrid residual Jacobian has wrong shape.")
        if reused_constraint_jacobian.shape != (
            len(constraint_counts),
            reused_mode_count,
        ):
            raise ValueError("Reusable multigrid root Jacobian has wrong shape.")
        if reused_finite_difference_steps.shape != (reused_mode_count,):
            raise ValueError("Reusable finite-difference steps have wrong shape.")
        jacobian[:, :reused_mode_count] = reused_jacobian.to_numpy(dtype=float)
        constraint_jacobian[:, :reused_mode_count] = (
            reused_constraint_jacobian.to_numpy(dtype=float)
        )
        finite_difference_steps[:reused_mode_count] = reused_finite_difference_steps
        print(
            json.dumps(
                {
                    "progress": "multigrid_jacobian_prefix_reused",
                    "reuse_run": str(reuse),
                    "reused_mode_count": reused_mode_count,
                    "requested_mode_count": args.mode_count,
                    "objective_panel_counts": objective_counts,
                    "constraint_panel_counts": constraint_counts,
                }
            ),
            flush=True,
        )
    for mode in range(reused_mode_count, args.mode_count):
        unit_displacement = basis[:, mode]
        unit_ratio = maximum_midpoint_displacement_ratio(
            source_nodes,
            source_nodes + unit_displacement[:, None] * normals,
        )
        epsilon = args.finite_difference_ratio / unit_ratio
        perturbed_root: dict[float, np.ndarray] = {}

        def residual_at_displacement(signed_epsilon: float) -> np.ndarray:
            candidate, _, _ = _build_candidate(
                coupled,
                source_nodes,
                signed_epsilon * unit_displacement,
                root_inner_iterations=args.root_inner_iterations,
                matching_surface_policy=args.matching_surface_policy,
            )
            candidate_residuals, candidate_states = _evaluate_grids(
                source,
                candidate,
                linearization_counts,
                outer_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                root_inner_iterations=args.root_inner_iterations,
            )
            if args.root_constraint == "none":
                perturbed_root[float(signed_epsilon)] = source_root_defect.copy()
            else:
                perturbed_root[float(signed_epsilon)] = np.asarray(
                    [
                        candidate_states[count].signed_root_defect
                        for count in constraint_counts
                    ],
                    dtype=float,
                )
            return normalized_multigrid_residual(
                {
                    count: candidate_residuals[count]
                    for count in objective_counts
                },
                source_objective_by_grid,
                weight_by_grid,
            )

        derivative, signed_epsilon = admissible_one_sided_difference(
            residual,
            epsilon,
            residual_at_displacement,
        )
        finite_difference_steps[mode] = signed_epsilon
        jacobian[:, mode] = derivative
        constraint_jacobian[:, mode] = (
            perturbed_root[float(signed_epsilon)] - source_root_defect
        ) / signed_epsilon
        print(
            json.dumps(
                {
                    "progress": "multigrid_jacobian_mode_complete",
                    "mode": mode + 1,
                    "mode_count": args.mode_count,
                    "signed_finite_difference_step": signed_epsilon,
                    "objective_panel_counts": objective_counts,
                    "constraint_panel_counts": constraint_counts,
                    "linearization_panel_counts": linearization_counts,
                }
            ),
            flush=True,
        )

    step_residual, step_jacobian = apply_leading_panel_objective_weight(
        residual,
        jacobian,
        objective_counts,
        args.leading_panel_objective_count,
        args.leading_panel_objective_weight,
    )
    active_root_bounds: tuple[str, ...] | None = None
    linearized_predicted_root = source_root_defect.copy()
    linearized_root_bound: float | None = None
    if args.root_constraint == "none":
        step = damped_gauss_newton_step(step_jacobian, step_residual, args.damping)
        linearized_predicted_root = source_root_defect + constraint_jacobian @ step
    elif args.root_constraint == "bounded":
        linearized_root_bound = (
            args.root_bound_safety_factor * args.root_mismatch_limit
        )
        step, active_root_bounds, linearized_predicted_root = (
            bounded_root_damped_gauss_newton_step(
                step_jacobian,
                step_residual,
                args.damping,
                constraint_jacobian,
                source_root_defect,
                linearized_root_bound,
            )
        )
    else:
        constraint_rhs = root_constraint_rhs(
            source_root_defect,
            args.root_constraint,
            target_root_defect,
        )
        step = multi_constraint_damped_gauss_newton_step(
            step_jacobian,
            step_residual,
            args.damping,
            constraint_jacobian,
            constraint_rhs,
        )
        linearized_predicted_root = source_root_defect + constraint_jacobian @ step
    normal_displacement = basis @ step
    step *= trust_region_scale(
        source_nodes,
        normal_displacement,
        args.trust_radius_safety_factor * args.trust_radius,
    )
    normal_displacement = basis @ step
    source_maximum_condition = max(
        state.condition_number for state in source_states.values()
    )
    trials: list[MultigridTrial] = []
    candidate_payloads: list[tuple[MultigridTrial, object, dict[int, GridState]]] = []
    for factor in sorted(set(args.step_factors), reverse=True):
        try:
            candidate, candidate_nodes, displacement = _build_candidate(
                coupled,
                source_nodes,
                float(factor) * normal_displacement,
                root_inner_iterations=args.root_inner_iterations,
                matching_surface_policy=args.matching_surface_policy,
            )
            candidate_residuals, candidate_states = _evaluate_grids(
                source,
                candidate,
                all_counts,
                outer_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                root_inner_iterations=args.root_inner_iterations,
            )
            candidate_residual = normalized_multigrid_residual(
                {
                    count: candidate_residuals[count]
                    for count in objective_counts
                },
                source_objective_by_grid,
                weight_by_grid,
            )
            objective = float(np.dot(candidate_residual, candidate_residual))
            predicted = residual + float(factor) * jacobian @ step
            predicted_objective = float(np.dot(predicted, predicted))
            predicted_reduction = normalized_source_objective - predicted_objective
            trust_ratio = (
                float("-inf")
                if predicted_reduction <= 0.0
                else (normalized_source_objective - objective) / predicted_reduction
            )
            maximum_grid_ratio = max(
                candidate_states[count].exact_objective
                / source_states[count].exact_objective
                for count in objective_validation_counts
            )
            maximum_leading_ratio = (
                1.0
                if source_leading_objective_by_grid is None
                else maximum_objective_ratio(
                    source_leading_objective_by_grid,
                    leading_panel_objective_by_grid(
                        {
                            count: candidate_residuals[count]
                            for count in objective_validation_counts
                        },
                        args.leading_panel_objective_count,
                    ),
                )
            )
            maximum_root = max(
                candidate_states[count].root_relative_mismatch
                for count in validation_counts
            )
            feasibility_repair = bool(
                args.allow_feasibility_repair
                and source_has_validation_root_violation
                and maximum_root <= args.root_mismatch_limit
            )
            maximum_condition = max(
                state.condition_number for state in candidate_states.values()
            )
            candidate_curvature, candidate_turn = polyline_curvature_metrics(
                candidate_nodes
            )
            curvature_ratio = candidate_curvature / max(
                source_curvature, np.finfo(float).eps
            )
            reason = trial_rejection_reason(
                source_objective=normalized_source_objective,
                candidate_objective=objective,
                minimum_relative_decrease=(
                    (normalized_source_objective - objective)
                    / normalized_source_objective
                    - 1.0e-12
                    if feasibility_repair
                    else args.minimum_relative_decrease
                ),
                maximum_displacement_ratio_value=displacement,
                displacement_limit=args.trust_radius,
                source_condition_number=source_maximum_condition,
                candidate_condition_number=maximum_condition,
                condition_number_ratio_limit=args.condition_number_ratio_limit,
                dipole_coefficient=candidate.dipole_coefficient,
                root_relative_mismatch=maximum_root,
                root_mismatch_limit=args.root_mismatch_limit,
            )
            if not reason and args.grid_objective_limit is None:
                if maximum_grid_ratio > args.maximum_grid_objective_ratio:
                    reason = "individual_grid_objective_increase"
            elif not reason:
                reason = grid_objective_limit_rejection_reason(
                    {
                        count: source_states[count].exact_objective
                        for count in objective_validation_counts
                    },
                    {
                        count: candidate_states[count].exact_objective
                        for count in objective_validation_counts
                    },
                    args.grid_objective_limit,
                )
            if not reason and curvature_ratio > args.curvature_energy_ratio_limit:
                reason = "curvature_energy"
            if (
                not reason
                and args.leading_panel_objective_ratio_limit is not None
                and maximum_leading_ratio
                > args.leading_panel_objective_ratio_limit
            ):
                reason = "leading_panel_objective_ratio"
            if (
                not reason
                and not feasibility_repair
                and trust_ratio < args.minimum_trust_ratio
            ):
                reason = "insufficient_trust_ratio"
            metric = MultigridTrial(
                step_factor=float(factor),
                normalized_objective=objective,
                normalized_relative_decrease=(normalized_source_objective - objective)
                / normalized_source_objective,
                predicted_normalized_objective=predicted_objective,
                trust_ratio=trust_ratio,
                maximum_grid_objective_ratio=maximum_grid_ratio,
                maximum_leading_panel_objective_ratio=maximum_leading_ratio,
                maximum_root_relative_mismatch=maximum_root,
                maximum_condition_number=maximum_condition,
                maximum_condition_number_ratio=maximum_condition
                / source_maximum_condition,
                maximum_displacement_ratio=displacement,
                curvature_energy=candidate_curvature,
                curvature_energy_ratio=curvature_ratio,
                maximum_turning_angle_deg=candidate_turn,
                dipole_coefficient=float(candidate.dipole_coefficient),
                feasibility_repair=feasibility_repair,
                accepted=not reason,
                rejection_reason=reason,
            )
            trials.append(metric)
            candidate_payloads.append((metric, candidate, candidate_states))
            for count in all_counts:
                grid_rows.append(
                    {
                        "stage": f"candidate_factor_{factor:g}",
                        **asdict(candidate_states[count]),
                    }
                )
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            trials.append(
                MultigridTrial(
                    step_factor=float(factor),
                    normalized_objective=float("nan"),
                    normalized_relative_decrease=float("nan"),
                    predicted_normalized_objective=float("nan"),
                    trust_ratio=float("nan"),
                    maximum_grid_objective_ratio=float("nan"),
                    maximum_leading_panel_objective_ratio=float("nan"),
                    maximum_root_relative_mismatch=float("nan"),
                    maximum_condition_number=float("nan"),
                    maximum_condition_number_ratio=float("nan"),
                    maximum_displacement_ratio=float("nan"),
                    curvature_energy=float("nan"),
                    curvature_energy_ratio=float("nan"),
                    maximum_turning_angle_deg=float("nan"),
                    dipole_coefficient=float("nan"),
                    feasibility_repair=False,
                    accepted=False,
                    rejection_reason=f"solver_failure:{type(error).__name__}:{error}",
                )
            )

    admissible = [item for item in candidate_payloads if item[0].accepted]
    if admissible:
        selected_metric, selected, selected_states = min(
            admissible, key=lambda item: item[0].normalized_objective
        )
        accepted_iterations = 1
    else:
        selected_metric = None
        selected = coupled
        selected_states = source_states
        accepted_iterations = 0

    jacobian_condition_number = float(np.linalg.cond(jacobian))
    for row in range(len(residual)):
        for mode in range(args.mode_count):
            jacobian_rows.append(
                {
                    "residual_row": row,
                    "shape_mode": mode,
                    "value": jacobian[row, mode],
                    "finite_difference_step": finite_difference_steps[mode],
                    "jacobian_condition_number": jacobian_condition_number,
                }
            )
    for count_index, count in enumerate(constraint_counts):
        for mode in range(args.mode_count):
            root_jacobian_rows.append(
                {
                    "panel_count": count,
                    "shape_mode": mode,
                    "value": constraint_jacobian[count_index, mode],
                    "source_signed_root_defect": source_root_defect[count_index],
                    "finite_difference_step": finite_difference_steps[mode],
                }
            )
    pd.DataFrame([asdict(item) for item in trials]).to_csv(
        output / "multigrid_trust_region_trials.csv", index=False
    )
    pd.DataFrame(grid_rows).to_csv(
        output / "multigrid_trust_region_grids.csv", index=False
    )
    pd.DataFrame(jacobian_rows).to_csv(
        output / "multigrid_trust_region_jacobians.csv", index=False
    )
    pd.DataFrame(root_jacobian_rows).to_csv(
        output / "multigrid_trust_region_root_jacobians.csv", index=False
    )
    pd.DataFrame(
        {
            "xi": selected.outer_free_surface.node_xi,
            "eta": selected.outer_free_surface.node_eta,
            "node_index": np.arange(len(selected.outer_free_surface.node_xi)),
        }
    ).to_csv(output / "multigrid_trust_region_final_outer_nodes.csv", index=False)
    _write_final_artifacts(output, selected)
    frozen = solve_coupled_self_similar_wedge_pseudo_time(
        selected,
        maximum_iterations=0,
        root_inner_iterations=args.root_inner_iterations,
    )
    checkpoint_path = write_coupled_self_similar_checkpoint(
        output,
        selected,
        coupled_pseudo_time_history_frame(frozen),
        parent=source,
        transformation={
            "type": "reference_isolated_multigrid_trust_region",
            "basis": args.basis,
            "global_mode_count": args.global_mode_count,
            "local_support_fraction": args.local_support_fraction,
            "fixed_root_node_count": args.fixed_root_node_count,
            "fixed_far_node_count": args.fixed_far_node_count,
            "mode_count": args.mode_count,
            "objective_panel_counts": list(objective_counts),
            "objective_panel_weights": [weight_by_grid[count] for count in objective_counts],
            "objective_validation_panel_counts": list(objective_validation_counts),
            "objective_normalization": "relative_to_frozen_source_grid_objective",
            "leading_panel_objective_count": args.leading_panel_objective_count,
            "leading_panel_objective_weight": args.leading_panel_objective_weight,
            "leading_panel_objective_ratio_limit": args.leading_panel_objective_ratio_limit,
            "direction_objective_preconditioner": "leading_panel_rows_only",
            "acceptance_objective_preconditioned": False,
            "candidate_root_seed_policy": CANDIDATE_ROOT_SEED_POLICY,
            "root_constraint": args.root_constraint,
            "root_constraint_panel_counts": list(constraint_counts),
            "root_validation_panel_counts": list(validation_counts),
            "linearization_panel_counts": list(linearization_counts),
            "root_target_defects": (
                None if target_root_defect is None else target_root_defect.tolist()
            ),
            "root_bound_safety_factor": args.root_bound_safety_factor,
            "linearized_root_bound": linearized_root_bound,
            "root_constraint_active_bounds": active_root_bounds,
            "linearized_predicted_root_defects": linearized_predicted_root.tolist(),
            "reused_jacobian_run": (
                None
                if args.reuse_jacobian_run is None
                else str(args.reuse_jacobian_run.resolve())
            ),
            "matching_surface_policy": args.matching_surface_policy,
            "root_inner_iterations": args.root_inner_iterations,
            "maximum_grid_objective_ratio": args.maximum_grid_objective_ratio,
            "grid_objective_limit": args.grid_objective_limit,
            "allow_feasibility_repair": args.allow_feasibility_repair,
            "curvature_energy_ratio_limit": args.curvature_energy_ratio_limit,
            "outer_shape_dipole_coefficient": outer_shape_dipole_coefficient,
            "reference_used_during_solve": False,
        },
    )
    summary = {
        "status": "self_similar_multigrid_trust_region_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "source_checkpoint": str(args.checkpoint.resolve()),
        "basis": args.basis,
        "global_mode_count": args.global_mode_count,
        "local_support_fraction": args.local_support_fraction,
        "fixed_root_node_count": args.fixed_root_node_count,
        "fixed_far_node_count": args.fixed_far_node_count,
        "objective_panel_counts": list(objective_counts),
        "objective_panel_weights": [weight_by_grid[count] for count in objective_counts],
        "objective_validation_panel_counts": list(objective_validation_counts),
        "objective_normalization": "relative_to_frozen_source_grid_objective",
        "leading_panel_objective_count": args.leading_panel_objective_count,
        "leading_panel_objective_weight": args.leading_panel_objective_weight,
        "leading_panel_objective_ratio_limit": args.leading_panel_objective_ratio_limit,
        "direction_objective_preconditioner": "leading_panel_rows_only",
        "acceptance_objective_preconditioned": False,
        "candidate_root_seed_policy": CANDIDATE_ROOT_SEED_POLICY,
        "matching_surface_policy": args.matching_surface_policy,
        "root_inner_iterations": args.root_inner_iterations,
        "root_constraint": args.root_constraint,
        "root_constraint_panel_counts": list(constraint_counts),
        "root_validation_panel_counts": list(validation_counts),
        "linearization_panel_counts": list(linearization_counts),
        "root_target_defects": (
            None if target_root_defect is None else target_root_defect.tolist()
        ),
        "root_bound_safety_factor": args.root_bound_safety_factor,
        "linearized_root_bound": linearized_root_bound,
        "root_constraint_active_bounds": active_root_bounds,
        "linearized_predicted_root_defects": linearized_predicted_root.tolist(),
        "grid_objective_limit": args.grid_objective_limit,
        "allow_feasibility_repair": args.allow_feasibility_repair,
        "reused_jacobian_run": (
            None
            if args.reuse_jacobian_run is None
            else str(args.reuse_jacobian_run.resolve())
        ),
        "mode_count": args.mode_count,
        "accepted_iterations": accepted_iterations,
        "initial_normalized_objective": normalized_source_objective,
        "final_normalized_objective": (
            normalized_source_objective
            if selected_metric is None
            else selected_metric.normalized_objective
        ),
        "source_grid_states": {
            str(count): asdict(source_states[count]) for count in all_counts
        },
        "final_grid_states": {
            str(count): asdict(selected_states[count]) for count in all_counts
        },
        "checkpoint": str(checkpoint_path),
        "conclusion": (
            "accepted_reference_isolated_multigrid_step"
            if accepted_iterations
            else "no_admissible_multigrid_step"
        ),
    }
    (output / "multigrid_trust_region_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
