from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    coupled_pseudo_time_history_frame,
    load_coupled_self_similar_checkpoint,
    write_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    solve_coupled_self_similar_wedge_pseudo_time,
)
from scripts.diagnose_self_similar_low_mode_line_search import (
    trial_rejection_reason,
)
from scripts.diagnose_self_similar_low_mode_trust_region import (
    _build_candidate,
    damped_gauss_newton_step,
    fix_endpoint_basis_nodes,
    polyline_curvature_metrics,
    trust_region_scale,
)
from scripts.diagnose_self_similar_multigrid_trust_region import (
    CANDIDATE_ROOT_SEED_POLICY,
    _evaluate_grids,
    apply_leading_panel_objective_weight,
    bounded_root_damped_gauss_newton_step,
    grid_objective_limit_rejection_reason,
    leading_panel_objective_by_grid,
    maximum_objective_ratio,
    multigrid_shape_basis,
    multi_constraint_damped_gauss_newton_step,
    normalized_multigrid_residual,
    root_constraint_rhs,
)
from scripts.resume_self_similar_wedge import _write_final_artifacts


def reconstruct_multigrid_normal_direction(
    jacobian: np.ndarray,
    residual: np.ndarray,
    basis: np.ndarray,
    source_nodes: np.ndarray,
    *,
    damping: float,
    trust_radius: float,
    trust_radius_safety_factor: float,
    root_constraint: str,
    constraint_jacobian: np.ndarray,
    source_root_defect: np.ndarray,
    root_bound: float | None = None,
    target_root_defect: np.ndarray | None = None,
) -> np.ndarray:
    """Reconstruct the frozen multigrid run's scaled nodal normal direction."""

    if root_constraint == "none":
        step = damped_gauss_newton_step(jacobian, residual, damping)
    elif root_constraint == "bounded":
        if root_bound is None:
            raise ValueError("A bounded root direction requires a root bound.")
        step, _, _ = bounded_root_damped_gauss_newton_step(
            jacobian,
            residual,
            damping,
            constraint_jacobian,
            source_root_defect,
            root_bound,
        )
    else:
        right = root_constraint_rhs(
            source_root_defect,
            root_constraint,
            target_root_defect,
        )
        step = multi_constraint_damped_gauss_newton_step(
            jacobian,
            residual,
            damping,
            constraint_jacobian,
            right,
        )
    displacement = basis @ step
    step *= trust_region_scale(
        source_nodes,
        displacement,
        float(trust_radius) * float(trust_radius_safety_factor),
    )
    return basis @ step


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reuse one frozen multigrid trust direction while re-evaluating "
            "every objective grid and nonlinear root gate at each step."
        )
    )
    parser.add_argument("--trust-run", type=Path, required=True)
    parser.add_argument("--initial-checkpoint", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--maximum-steps", type=int, default=8)
    parser.add_argument(
        "--step-factors", type=float, nargs="+", default=(1.0, 0.5, 0.25)
    )
    parser.add_argument("--damping", type=float, default=1.0e-3)
    parser.add_argument("--trust-radius", type=float, default=0.25)
    parser.add_argument("--trust-radius-safety-factor", type=float, default=1.0)
    parser.add_argument("--minimum-relative-decrease", type=float, default=1.0e-4)
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.05)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument("--grid-objective-limit", type=float, default=1.0e-3)
    parser.add_argument("--curvature-energy-ratio-limit", type=float, default=1.10)
    parser.add_argument("--root-inner-iterations", type=int, default=0)
    parser.add_argument("--reconstruction-tolerance", type=float, default=1.0e-6)
    return parser


def _pivot_jacobian(path: Path, mode_count: int) -> np.ndarray:
    frame = pd.read_csv(path)
    matrix = (
        frame.pivot(index="residual_row", columns="shape_mode", values="value")
        .sort_index()
        .sort_index(axis=1)
        .to_numpy(dtype=float)
    )
    if matrix.shape[1] != mode_count or not np.isfinite(matrix).all():
        raise ValueError("Saved multigrid Jacobian has an incompatible shape.")
    return matrix


def _pivot_root_jacobian(
    path: Path,
    panel_counts: tuple[int, ...],
    mode_count: int,
) -> np.ndarray:
    frame = pd.read_csv(path)
    matrix = (
        frame.pivot(index="panel_count", columns="shape_mode", values="value")
        .reindex(index=list(panel_counts), columns=list(range(mode_count)))
        .to_numpy(dtype=float)
    )
    if matrix.shape != (len(panel_counts), mode_count) or not np.isfinite(matrix).all():
        raise ValueError("Saved multigrid root Jacobian is incomplete.")
    return matrix


def accepted_trial_mask(values: pd.Series) -> pd.Series:
    """Return a strict boolean mask for persisted trial acceptance values."""

    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False)
    normalized = values.astype("string").str.strip().str.lower()
    invalid = normalized[~normalized.isin(("true", "false")) & normalized.notna()]
    if not invalid.empty:
        raise ValueError("Saved trial acceptance column contains invalid values.")
    return normalized.eq("true").fillna(False)


def main() -> int:
    args = _parser().parse_args()
    if args.maximum_steps < 1 or args.root_inner_iterations < 0:
        raise ValueError("Step count must be positive and root iterations non-negative.")
    if any(value <= 0.0 or not np.isfinite(value) for value in args.step_factors):
        raise ValueError("Step factors must be finite and positive.")
    if (
        args.damping < 0.0
        or args.trust_radius <= 0.0
        or args.trust_radius_safety_factor <= 0.0
        or args.root_mismatch_limit <= 0.0
        or args.grid_objective_limit <= 0.0
        or args.curvature_energy_ratio_limit < 1.0
        or args.reconstruction_tolerance <= 0.0
    ):
        raise ValueError("Reuse limits must be finite and physically admissible.")

    trust_run = args.trust_run.resolve()
    summary = json.loads(
        (trust_run / "multigrid_trust_region_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if int(summary.get("accepted_iterations", 0)) < 1:
        raise ValueError("Direction reuse requires an accepted multigrid run.")
    if bool(summary.get("reference_used_during_solve", True)):
        raise ValueError("Reference-contaminated directions cannot be reused.")
    if summary.get("candidate_root_seed_policy") != CANDIDATE_ROOT_SEED_POLICY:
        raise ValueError(
            "Saved direction uses an incompatible candidate root-seed policy."
        )
    if int(summary.get("root_inner_iterations", -1)) != int(
        args.root_inner_iterations
    ):
        raise ValueError(
            "Saved direction uses a different root-inner iteration mapping."
        )
    matching_surface_policy = str(
        summary.get("matching_surface_policy", "")
    )
    if matching_surface_policy not in ("fixed_branch", "relocate"):
        raise ValueError(
            "Saved direction has no compatible matching-surface policy."
        )

    objective_counts = tuple(int(value) for value in summary["objective_panel_counts"])
    objective_weights = tuple(float(value) for value in summary["objective_panel_weights"])
    objective_validation_counts = tuple(
        int(value)
        for value in summary.get(
            "objective_validation_panel_counts", summary["objective_panel_counts"]
        )
    )
    constraint_counts = tuple(
        int(value) for value in summary["root_constraint_panel_counts"]
    )
    validation_counts = tuple(
        int(value)
        for value in summary.get(
            "root_validation_panel_counts", summary["root_constraint_panel_counts"]
        )
    )
    all_counts = tuple(
        sorted(
            set(objective_counts)
            | set(objective_validation_counts)
            | set(constraint_counts)
            | set(validation_counts)
        )
    )
    if len(objective_counts) != len(objective_weights):
        raise ValueError("Objective panel counts and weights have different lengths.")
    weight_by_grid = dict(zip(objective_counts, objective_weights))

    source = load_coupled_self_similar_checkpoint(summary["source_checkpoint"])
    initial_path = trust_run if args.initial_checkpoint is None else args.initial_checkpoint.resolve()
    initial = load_coupled_self_similar_checkpoint(initial_path)
    if source.config.free_surface_panels != initial.config.free_surface_panels:
        raise ValueError("Saved direction and initial checkpoint use different source grids.")

    mode_count = int(summary["mode_count"])
    source_nodes = np.column_stack(
        (source.coupled.outer_free_surface.node_xi, source.coupled.outer_free_surface.node_eta)
    )
    source_residuals, source_states = _evaluate_grids(
        source,
        source.coupled,
        all_counts,
        outer_shape_dipole_coefficient=source.outer_shape_dipole_coefficient,
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
    jacobian = _pivot_jacobian(
        trust_run / "multigrid_trust_region_jacobians.csv", mode_count
    )
    leading_panel_objective_count = int(
        summary.get("leading_panel_objective_count", 0)
    )
    leading_panel_objective_weight = float(
        summary.get("leading_panel_objective_weight", 1.0)
    )
    leading_panel_objective_ratio_limit = summary.get(
        "leading_panel_objective_ratio_limit"
    )
    if leading_panel_objective_ratio_limit is not None:
        leading_panel_objective_ratio_limit = float(
            leading_panel_objective_ratio_limit
        )
    step_residual, step_jacobian = apply_leading_panel_objective_weight(
        residual,
        jacobian,
        objective_counts,
        leading_panel_objective_count,
        leading_panel_objective_weight,
    )
    constraint_jacobian = _pivot_root_jacobian(
        trust_run / "multigrid_trust_region_root_jacobians.csv",
        constraint_counts,
        mode_count,
    )
    source_root_defect = np.asarray(
        [source_states[count].signed_root_defect for count in constraint_counts],
        dtype=float,
    )
    target = summary.get("root_target_defects")
    target_root_defect = None if target is None else np.asarray(target, dtype=float)
    root_bound = (
        float(summary["root_bound_safety_factor"]) * args.root_mismatch_limit
        if summary["root_constraint"] == "bounded"
        else None
    )
    labels = np.asarray(source.coupled.boundary.panel_labels, dtype=object)
    source_panel_length = source.coupled.boundary.panel_length_m[
        labels == "outer_free_surface"
    ]
    basis = multigrid_shape_basis(
        source_panel_length,
        mode_count,
        basis=str(summary.get("basis", "dct")),
        global_mode_count=int(summary.get("global_mode_count", 2)),
        local_support_fraction=float(summary.get("local_support_fraction", 0.15)),
    )
    basis = fix_endpoint_basis_nodes(
        basis,
        source_panel_length,
        fixed_root_node_count=int(summary.get("fixed_root_node_count", 0)),
        fixed_far_node_count=int(summary.get("fixed_far_node_count", 0)),
    )
    normal_displacement = reconstruct_multigrid_normal_direction(
        step_jacobian,
        step_residual,
        basis,
        source_nodes,
        damping=args.damping,
        trust_radius=args.trust_radius,
        trust_radius_safety_factor=args.trust_radius_safety_factor,
        root_constraint=str(summary["root_constraint"]),
        constraint_jacobian=constraint_jacobian,
        source_root_defect=source_root_defect,
        root_bound=root_bound,
        target_root_defect=target_root_defect,
    )

    trial_frame = pd.read_csv(trust_run / "multigrid_trust_region_trials.csv")
    accepted_trial = trial_frame[accepted_trial_mask(trial_frame["accepted"])].sort_values(
        "normalized_objective"
    ).iloc[0]
    saved_factor = float(accepted_trial["step_factor"])
    reconstructed, reconstructed_nodes, _ = _build_candidate(
        source.coupled,
        source_nodes,
        saved_factor * normal_displacement,
        root_inner_iterations=args.root_inner_iterations,
        matching_surface_policy=str(summary.get("matching_surface_policy", "fixed_branch")),
    )
    saved = load_coupled_self_similar_checkpoint(trust_run)
    saved_nodes = np.column_stack(
        (saved.coupled.outer_free_surface.node_xi, saved.coupled.outer_free_surface.node_eta)
    )
    source_scale = max(
        float(np.max(np.linalg.norm(np.diff(source_nodes, axis=0), axis=1))),
        np.finfo(float).eps,
    )
    reconstruction_error = float(
        np.max(np.linalg.norm(reconstructed_nodes - saved_nodes, axis=1)) / source_scale
    )
    dipole_error = abs(reconstructed.dipole_coefficient - saved.coupled.dipole_coefficient) / max(
        abs(saved.coupled.dipole_coefficient), np.finfo(float).eps
    )
    if max(reconstruction_error, dipole_error) > args.reconstruction_tolerance:
        raise ValueError(
            "Saved multigrid direction did not reconstruct its accepted checkpoint: "
            f"node_error={reconstruction_error:.6e}, dipole_error={dipole_error:.6e}."
        )

    coupled = initial.coupled
    outer_shape_dipole_coefficient = float(initial.outer_shape_dipole_coefficient)
    rows: list[dict[str, object]] = []
    grid_rows: list[dict[str, object]] = []
    accepted_rows: list[dict[str, object]] = []
    current_states: dict[int, object] = {}
    for step_index in range(1, args.maximum_steps + 1):
        nodes = np.column_stack(
            (coupled.outer_free_surface.node_xi, coupled.outer_free_surface.node_eta)
        )
        current_residuals, current_states = _evaluate_grids(
            source,
            coupled,
            all_counts,
            outer_shape_dipole_coefficient=outer_shape_dipole_coefficient,
            root_inner_iterations=args.root_inner_iterations,
        )
        current_objective_by_grid = {
            count: current_states[count].exact_objective for count in objective_counts
        }
        current_validation_objective_by_grid = {
            count: current_states[count].exact_objective
            for count in objective_validation_counts
        }
        current_leading_objective_by_grid = (
            None
            if leading_panel_objective_count < 1
            else leading_panel_objective_by_grid(
                {
                    count: current_residuals[count]
                    for count in objective_validation_counts
                },
                leading_panel_objective_count,
            )
        )
        source_condition = max(state.condition_number for state in current_states.values())
        source_curvature, source_turn = polyline_curvature_metrics(nodes)
        candidates: list[tuple[float, object, dict[int, object], dict[str, object]]] = []
        for factor in sorted(set(args.step_factors), reverse=True):
            row: dict[str, object] = {
                "reuse_step": step_index,
                "step_factor": float(factor),
                "source_curvature_energy": source_curvature,
                "source_maximum_turning_angle_deg": source_turn,
            }
            try:
                candidate, candidate_nodes, displacement = _build_candidate(
                    coupled,
                    nodes,
                    float(factor) * normal_displacement,
                    root_inner_iterations=args.root_inner_iterations,
                    matching_surface_policy=str(
                        summary.get("matching_surface_policy", "fixed_branch")
                    ),
                )
                candidate_residuals, candidate_states = _evaluate_grids(
                    source,
                    candidate,
                    all_counts,
                    outer_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                    root_inner_iterations=args.root_inner_iterations,
                )
                candidate_residual = normalized_multigrid_residual(
                    {count: candidate_residuals[count] for count in objective_counts},
                    current_objective_by_grid,
                    weight_by_grid,
                )
                objective = float(np.dot(candidate_residual, candidate_residual))
                maximum_root = max(
                    candidate_states[count].root_relative_mismatch
                    for count in validation_counts
                )
                maximum_leading_ratio = (
                    1.0
                    if current_leading_objective_by_grid is None
                    else maximum_objective_ratio(
                        current_leading_objective_by_grid,
                        leading_panel_objective_by_grid(
                            {
                                count: candidate_residuals[count]
                                for count in objective_validation_counts
                            },
                            leading_panel_objective_count,
                        ),
                    )
                )
                maximum_condition = max(
                    state.condition_number for state in candidate_states.values()
                )
                curvature, maximum_turn = polyline_curvature_metrics(candidate_nodes)
                curvature_ratio = curvature / max(source_curvature, np.finfo(float).eps)
                reason = trial_rejection_reason(
                    source_objective=1.0,
                    candidate_objective=objective,
                    minimum_relative_decrease=args.minimum_relative_decrease,
                    maximum_displacement_ratio_value=displacement,
                    displacement_limit=args.trust_radius,
                    source_condition_number=source_condition,
                    candidate_condition_number=maximum_condition,
                    condition_number_ratio_limit=args.condition_number_ratio_limit,
                    dipole_coefficient=candidate.dipole_coefficient,
                    root_relative_mismatch=maximum_root,
                    root_mismatch_limit=args.root_mismatch_limit,
                )
                if not reason:
                    reason = grid_objective_limit_rejection_reason(
                        current_validation_objective_by_grid,
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
                    and leading_panel_objective_ratio_limit is not None
                    and maximum_leading_ratio > leading_panel_objective_ratio_limit
                ):
                    reason = "leading_panel_objective_ratio"
                row.update(
                    {
                        "normalized_objective": objective,
                        "normalized_relative_decrease": 1.0 - objective,
                        "maximum_root_relative_mismatch": maximum_root,
                        "maximum_leading_panel_objective_ratio": maximum_leading_ratio,
                        "maximum_condition_number": maximum_condition,
                        "maximum_condition_number_ratio": maximum_condition / source_condition,
                        "maximum_displacement_ratio": displacement,
                        "curvature_energy": curvature,
                        "curvature_energy_ratio": curvature_ratio,
                        "maximum_turning_angle_deg": maximum_turn,
                        "dipole_coefficient": float(candidate.dipole_coefficient),
                        "accepted": not reason,
                        "rejection_reason": reason,
                    }
                )
                if not reason:
                    candidates.append((objective, candidate, candidate_states, row))
                for count in all_counts:
                    grid_rows.append(
                        {
                            "reuse_step": step_index,
                            "step_factor": float(factor),
                            "panel_count": count,
                            "exact_objective": candidate_states[count].exact_objective,
                            "signed_root_defect": candidate_states[count].signed_root_defect,
                            "root_relative_mismatch": candidate_states[count].root_relative_mismatch,
                            "condition_number": candidate_states[count].condition_number,
                        }
                    )
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
                row.update(
                    {
                        "accepted": False,
                        "rejection_reason": f"solver_failure:{type(error).__name__}:{error}",
                    }
                )
            rows.append(row)
        if not candidates:
            break
        _, selected, selected_states, accepted = min(candidates, key=lambda item: item[0])
        outer_shape_dipole_coefficient = float(coupled.dipole_coefficient)
        coupled = selected
        current_states = selected_states
        accepted["outer_shape_dipole_coefficient"] = outer_shape_dipole_coefficient
        accepted_rows.append(accepted)
        print(json.dumps({"progress": "multigrid_reuse_step_accepted", **accepted}), flush=True)

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "multigrid_direction_reuse_trials.csv", index=False)
    pd.DataFrame(accepted_rows).to_csv(
        output / "multigrid_direction_reuse_accepted.csv", index=False
    )
    pd.DataFrame(grid_rows).to_csv(output / "multigrid_direction_reuse_grids.csv", index=False)
    pd.DataFrame(
        {
            "node_index": np.arange(len(normal_displacement)),
            "normal_displacement": normal_displacement,
        }
    ).to_csv(output / "multigrid_direction_reuse_normal_displacement.csv", index=False)
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
        parent=initial,
        transformation={
            "type": "reference_isolated_frozen_multigrid_direction_reuse",
            "trust_run": str(trust_run),
            "maximum_steps": args.maximum_steps,
            "accepted_steps": len(accepted_rows),
            "objective_panel_counts": list(objective_counts),
            "objective_validation_panel_counts": list(objective_validation_counts),
            "leading_panel_objective_count": leading_panel_objective_count,
            "leading_panel_objective_weight": leading_panel_objective_weight,
            "leading_panel_objective_ratio_limit": leading_panel_objective_ratio_limit,
            "direction_objective_preconditioner": "leading_panel_rows_only",
            "acceptance_objective_preconditioned": False,
            "candidate_root_seed_policy": CANDIDATE_ROOT_SEED_POLICY,
            "root_inner_iterations": args.root_inner_iterations,
            "matching_surface_policy": matching_surface_policy,
            "root_validation_panel_counts": list(validation_counts),
            "saved_step_factor": saved_factor,
            "reconstruction_relative_error": reconstruction_error,
            "reconstruction_dipole_relative_error": dipole_error,
            "outer_shape_dipole_coefficient": outer_shape_dipole_coefficient,
            "reference_used_during_solve": False,
        },
    )
    _, final_states = _evaluate_grids(
        source,
        coupled,
        all_counts,
        outer_shape_dipole_coefficient=outer_shape_dipole_coefficient,
        root_inner_iterations=args.root_inner_iterations,
    )
    result = {
        "status": "self_similar_frozen_multigrid_direction_reuse_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "trust_run": str(trust_run),
        "initial_checkpoint": str(initial_path),
        "requested_steps": args.maximum_steps,
        "accepted_steps": len(accepted_rows),
        "saved_step_factor": saved_factor,
        "direction_reconstruction_relative_error": reconstruction_error,
        "direction_reconstruction_dipole_relative_error": dipole_error,
        "objective_panel_counts": list(objective_counts),
        "objective_validation_panel_counts": list(objective_validation_counts),
        "leading_panel_objective_count": leading_panel_objective_count,
        "leading_panel_objective_weight": leading_panel_objective_weight,
        "leading_panel_objective_ratio_limit": leading_panel_objective_ratio_limit,
        "direction_objective_preconditioner": "leading_panel_rows_only",
        "acceptance_objective_preconditioned": False,
        "candidate_root_seed_policy": CANDIDATE_ROOT_SEED_POLICY,
        "root_inner_iterations": args.root_inner_iterations,
        "matching_surface_policy": matching_surface_policy,
        "root_validation_panel_counts": list(validation_counts),
        "final_grid_states": {
            str(count): {
                "exact_objective": final_states[count].exact_objective,
                "signed_root_defect": final_states[count].signed_root_defect,
                "root_relative_mismatch": final_states[count].root_relative_mismatch,
                "condition_number": final_states[count].condition_number,
            }
            for count in all_counts
        },
        "checkpoint": str(checkpoint_path),
        "conclusion": (
            "accepted_frozen_multigrid_direction_steps"
            if accepted_rows
            else "no_admissible_frozen_multigrid_direction_step"
        ),
    }
    (output / "multigrid_direction_reuse_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
