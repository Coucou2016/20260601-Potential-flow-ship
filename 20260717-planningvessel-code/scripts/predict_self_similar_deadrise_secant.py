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
    angle_bisector_normals,
    polyline_curvature_metrics,
)
from scripts.diagnose_self_similar_newton_krylov import formal_outer_state
from scripts.resume_self_similar_wedge import _write_final_artifacts
from scripts.reuse_self_similar_newton_krylov_direction import (
    normalized_arc_coordinate,
)


def secant_prediction_normal_displacement(
    previous_nodes: np.ndarray,
    current_nodes: np.ndarray,
    target_nodes: np.ndarray,
    *,
    previous_parameter: float,
    current_parameter: float,
    target_parameter: float,
) -> tuple[np.ndarray, float, float]:
    """Return the target-grid normal projection of a two-state secant predictor."""

    previous = np.asarray(previous_nodes, dtype=float)
    current = np.asarray(current_nodes, dtype=float)
    target = np.asarray(target_nodes, dtype=float)
    if any(nodes.ndim != 2 or nodes.shape[1] != 2 for nodes in (previous, current, target)):
        raise ValueError("Secant predictor nodes must be two-column coordinate arrays.")
    denominator = current_parameter - previous_parameter
    if abs(denominator) <= np.finfo(float).eps:
        raise ValueError("Secant predictor parameters must be distinct.")
    ratio = (target_parameter - current_parameter) / denominator
    previous_arc = normalized_arc_coordinate(previous[:, 0], previous[:, 1])
    current_arc = normalized_arc_coordinate(current[:, 0], current[:, 1])
    target_arc = normalized_arc_coordinate(target[:, 0], target[:, 1])
    previous_on_target = np.column_stack(
        [np.interp(target_arc, previous_arc, previous[:, column]) for column in range(2)]
    )
    current_on_target = np.column_stack(
        [np.interp(target_arc, current_arc, current[:, column]) for column in range(2)]
    )
    predicted = current_on_target + ratio * (current_on_target - previous_on_target)
    delta = predicted - target
    normals = angle_bisector_normals(target)
    normal_displacement = np.einsum("ij,ij->i", delta, normals)
    tangential = delta - normal_displacement[:, None] * normals
    tangential_fraction = float(
        np.linalg.norm(tangential) / max(np.linalg.norm(delta), np.finfo(float).eps)
    )
    return normal_displacement, float(ratio), tangential_fraction


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a reference-isolated two-checkpoint secant predictor for a "
            "nearby self-similar wedge deadrise and verify it nonlinearly."
        )
    )
    parser.add_argument("--previous-checkpoint", type=Path, required=True)
    parser.add_argument("--current-checkpoint", type=Path, required=True)
    parser.add_argument("--target-checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--step-factors",
        type=float,
        nargs="+",
        default=(1.0, 0.75, 0.5, 0.25, 0.125),
    )
    parser.add_argument("--root-inner-iterations", type=int, default=8)
    parser.add_argument(
        "--matching-surface-policy",
        choices=("fixed_branch", "relocate"),
        default="relocate",
    )
    parser.add_argument("--minimum-relative-decrease", type=float, default=1.0e-4)
    parser.add_argument("--trust-radius", type=float, default=0.20)
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.10)
    parser.add_argument("--curvature-energy-ratio-limit", type=float, default=1.25)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    return parser


def main() -> int:
    args = _parser().parse_args()
    previous_checkpoint = load_coupled_self_similar_checkpoint(
        args.previous_checkpoint, verification_tolerance=1.0e-12
    )
    current_checkpoint = load_coupled_self_similar_checkpoint(
        args.current_checkpoint, verification_tolerance=1.0e-12
    )
    target_checkpoint = load_coupled_self_similar_checkpoint(
        args.target_checkpoint, verification_tolerance=1.0e-12
    )
    previous = previous_checkpoint.coupled
    current = current_checkpoint.coupled
    target = target_checkpoint.coupled
    previous_nodes = np.column_stack(
        (previous.outer_free_surface.node_xi, previous.outer_free_surface.node_eta)
    )
    current_nodes = np.column_stack(
        (current.outer_free_surface.node_xi, current.outer_free_surface.node_eta)
    )
    target_nodes = np.column_stack(
        (target.outer_free_surface.node_xi, target.outer_free_surface.node_eta)
    )
    normal_displacement, parameter_ratio, tangential_fraction = (
        secant_prediction_normal_displacement(
            previous_nodes,
            current_nodes,
            target_nodes,
            previous_parameter=float(previous.config.deadrise_deg),
            current_parameter=float(current.config.deadrise_deg),
            target_parameter=float(target.config.deadrise_deg),
        )
    )
    source_state = formal_outer_state(target)
    source_curvature, source_turn = polyline_curvature_metrics(target_nodes)
    trial_rows: list[dict[str, object]] = []
    candidates: list[tuple[float, object, dict[str, object]]] = []
    for factor in sorted(set(args.step_factors), reverse=True):
        row: dict[str, object] = {
            "step_factor": float(factor),
            "source_formal_exact_objective": source_state.exact_objective,
            "source_root_relative_mismatch": source_state.root_relative_mismatch,
            "secant_parameter_ratio": parameter_ratio,
            "secant_tangential_fraction": tangential_fraction,
        }
        try:
            candidate, candidate_nodes, displacement = _build_candidate(
                target,
                target_nodes,
                float(factor) * normal_displacement,
                root_inner_iterations=args.root_inner_iterations,
                matching_surface_policy=args.matching_surface_policy,
            )
            state = formal_outer_state(candidate)
            curvature, turn = polyline_curvature_metrics(candidate_nodes)
            curvature_ratio = curvature / max(source_curvature, np.finfo(float).eps)
            reason = trial_rejection_reason(
                source_objective=source_state.exact_objective,
                candidate_objective=state.exact_objective,
                minimum_relative_decrease=args.minimum_relative_decrease,
                maximum_displacement_ratio_value=displacement,
                displacement_limit=args.trust_radius,
                source_condition_number=source_state.condition_number,
                candidate_condition_number=state.condition_number,
                condition_number_ratio_limit=args.condition_number_ratio_limit,
                dipole_coefficient=state.dipole_coefficient,
                root_relative_mismatch=state.root_relative_mismatch,
                root_mismatch_limit=args.root_mismatch_limit,
            )
            if not reason and curvature_ratio > args.curvature_energy_ratio_limit:
                reason = "curvature_energy"
            row.update(
                {
                    "candidate_formal_exact_objective": state.exact_objective,
                    "formal_exact_relative_decrease": (
                        source_state.exact_objective - state.exact_objective
                    )
                    / source_state.exact_objective,
                    "maximum_displacement_ratio": displacement,
                    "condition_number": state.condition_number,
                    "condition_number_ratio": (
                        state.condition_number / source_state.condition_number
                    ),
                    "root_relative_mismatch": state.root_relative_mismatch,
                    "curvature_energy": curvature,
                    "curvature_energy_ratio": curvature_ratio,
                    "maximum_turning_angle_deg": turn,
                    "accepted": not reason,
                    "rejection_reason": reason,
                }
            )
            if not reason:
                candidates.append((state.exact_objective, candidate, row))
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            row.update(
                {
                    "accepted": False,
                    "rejection_reason": f"solver_failure:{type(error).__name__}:{error}",
                }
            )
        trial_rows.append(row)

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(trial_rows).to_csv(output / "deadrise_secant_trials.csv", index=False)
    selected = min(candidates, key=lambda item: item[0]) if candidates else None
    final = target if selected is None else selected[1]
    _write_final_artifacts(output, final)
    frozen = solve_coupled_self_similar_wedge_pseudo_time(
        final,
        maximum_iterations=0,
        root_inner_iterations=args.root_inner_iterations,
    )
    checkpoint_path = write_coupled_self_similar_checkpoint(
        output,
        final,
        coupled_pseudo_time_history_frame(frozen),
        parent=target_checkpoint,
        transformation={
            "type": "reference_isolated_deadrise_secant_predictor",
            "previous_checkpoint": str(args.previous_checkpoint.resolve()),
            "current_checkpoint": str(args.current_checkpoint.resolve()),
            "target_checkpoint": str(args.target_checkpoint.resolve()),
            "parameter_ratio": parameter_ratio,
            "tangential_fraction": tangential_fraction,
            "selected_step_factor": (
                float(selected[2]["step_factor"]) if selected is not None else None
            ),
            "outer_shape_dipole_coefficient": float(target.dipole_coefficient),
            "root_inner_iterations": args.root_inner_iterations,
            "matching_surface_policy": args.matching_surface_policy,
            "reference_used_during_solve": False,
        },
    )
    final_state = formal_outer_state(final)
    result = {
        "status": "self_similar_deadrise_secant_predictor_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "previous_deadrise_deg": float(previous.config.deadrise_deg),
        "current_deadrise_deg": float(current.config.deadrise_deg),
        "target_deadrise_deg": float(target.config.deadrise_deg),
        "parameter_ratio": parameter_ratio,
        "tangential_fraction": tangential_fraction,
        "initial_formal_exact_objective": source_state.exact_objective,
        "final_formal_exact_objective": final_state.exact_objective,
        "final_root_relative_mismatch": final_state.root_relative_mismatch,
        "accepted": selected is not None,
        "selected_step_factor": (
            float(selected[2]["step_factor"]) if selected is not None else None
        ),
        "checkpoint": str(checkpoint_path),
    }
    (output / "deadrise_secant_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0 if selected is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
