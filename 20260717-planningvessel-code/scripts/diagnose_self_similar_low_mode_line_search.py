from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.fft import dct, idct


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    load_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    _build_coupled_solution_from_outer_nodes,
    _constrain_coupled_outer_nodes,
    _regrid_coupled_outer_nodes,
    derive_shallow_water_jet_root_state_from_coupled,
)
from scripts.analyze_self_similar_kinematic_residual import (
    continuous_linear_weak_projection,
)
from scripts.resume_self_similar_wedge import _write_final_artifacts


@dataclass(frozen=True)
class TrialMetrics:
    iteration: int
    step_scale: float
    objective: float
    relative_decrease: float
    maximum_displacement_ratio: float
    condition_number: float
    condition_number_ratio: float
    dipole_coefficient: float
    root_relative_mismatch: float
    accepted: bool
    rejection_reason: str


def cosine_low_pass(values: np.ndarray, retained_modes: int) -> np.ndarray:
    """Retain the lowest DCT-II modes of a finite nodal sequence."""

    data = np.asarray(values, dtype=float)
    count = int(retained_modes)
    if data.ndim != 1 or len(data) < 2 or not np.isfinite(data).all():
        raise ValueError("Low-mode filtering requires a finite nodal sequence.")
    if count < 1 or count > len(data):
        raise ValueError("retained_modes must lie between one and the node count.")
    coefficients = dct(data, type=2, norm="ortho")
    coefficients[count:] = 0.0
    return idct(coefficients, type=2, norm="ortho")


def angle_bisector_normals(nodes: np.ndarray) -> np.ndarray:
    """Return continuous left normals of the root-to-far free-surface chain."""

    coordinates = np.asarray(nodes, dtype=float)
    if (
        coordinates.ndim != 2
        or coordinates.shape[1] != 2
        or len(coordinates) < 3
        or not np.isfinite(coordinates).all()
    ):
        raise ValueError("Angle-bisector normals require at least three finite nodes.")
    segment = np.diff(coordinates, axis=0)
    length = np.linalg.norm(segment, axis=1)
    if np.any(length <= np.finfo(float).eps):
        raise ValueError("Angle-bisector normals require positive panel lengths.")
    tangent = segment / length[:, None]
    node_tangent = np.empty_like(coordinates)
    node_tangent[[0, -1]] = tangent[[0, -1]]
    node_tangent[1:-1] = tangent[:-1] + tangent[1:]
    norm = np.linalg.norm(node_tangent, axis=1)
    if np.any(norm <= np.finfo(float).eps):
        raise ValueError("Angle-bisector normal is undefined at a folded node.")
    node_tangent /= norm[:, None]
    return np.column_stack((-node_tangent[:, 1], node_tangent[:, 0]))


def maximum_midpoint_displacement_ratio(
    source_nodes: np.ndarray,
    candidate_nodes: np.ndarray,
) -> float:
    """Measure midpoint displacement relative to each source panel length."""

    source = np.asarray(source_nodes, dtype=float)
    candidate = np.asarray(candidate_nodes, dtype=float)
    if source.shape != candidate.shape or source.ndim != 2 or source.shape[1] != 2:
        raise ValueError("Displacement ratio requires matching planar node arrays.")
    length = np.linalg.norm(np.diff(source, axis=0), axis=1)
    if np.any(length <= np.finfo(float).eps):
        raise ValueError("Displacement ratio requires positive source panel lengths.")
    source_midpoint = 0.5 * (source[:-1] + source[1:])
    candidate_midpoint = 0.5 * (candidate[:-1] + candidate[1:])
    return float(
        np.max(np.linalg.norm(candidate_midpoint - source_midpoint, axis=1) / length)
    )


def trial_rejection_reason(
    *,
    source_objective: float,
    candidate_objective: float,
    minimum_relative_decrease: float,
    maximum_displacement_ratio_value: float,
    displacement_limit: float,
    source_condition_number: float,
    candidate_condition_number: float,
    condition_number_ratio_limit: float,
    dipole_coefficient: float,
    root_relative_mismatch: float,
    root_mismatch_limit: float,
) -> str:
    """Return the first failed reference-isolated line-search safeguard."""

    values = (
        source_objective,
        candidate_objective,
        minimum_relative_decrease,
        maximum_displacement_ratio_value,
        displacement_limit,
        source_condition_number,
        candidate_condition_number,
        condition_number_ratio_limit,
        dipole_coefficient,
        root_relative_mismatch,
        root_mismatch_limit,
    )
    if not np.isfinite(values).all():
        return "nonfinite_metric"
    if source_objective <= 0.0 or source_condition_number <= 0.0:
        return "invalid_source_metric"
    relative_decrease = (source_objective - candidate_objective) / source_objective
    if relative_decrease < minimum_relative_decrease:
        return "insufficient_objective_decrease"
    if maximum_displacement_ratio_value > displacement_limit:
        return "displacement_limit"
    if candidate_condition_number <= 0.0:
        return "invalid_condition_number"
    if candidate_condition_number / source_condition_number > condition_number_ratio_limit:
        return "condition_number_growth"
    if dipole_coefficient <= 0.0:
        return "nonpositive_dipole"
    if root_relative_mismatch > root_mismatch_limit:
        return "root_mismatch"
    return ""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reference-isolated low-mode steady line search for the coupled "
            "self-similar wedge diagnostic."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--retained-modes", type=int, default=2)
    parser.add_argument(
        "--step-scales",
        type=float,
        nargs="+",
        default=(0.10, 0.05, 0.02),
    )
    parser.add_argument("--minimum-relative-decrease", type=float, default=1.0e-4)
    parser.add_argument("--maximum-displacement-ratio", type=float, default=0.25)
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.05)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument("--root-inner-iterations", type=int, default=0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.iterations < 1:
        raise ValueError("--iterations must be positive.")
    if args.root_inner_iterations < 0:
        raise ValueError("--root-inner-iterations must be non-negative.")
    if any(step <= 0.0 or not np.isfinite(step) for step in args.step_scales):
        raise ValueError("--step-scales must be finite and positive.")

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = load_coupled_self_similar_checkpoint(args.checkpoint.resolve())
    coupled = checkpoint.coupled
    trials: list[TrialMetrics] = []
    accepted_history: list[dict[str, float | int]] = []

    for iteration in range(1, args.iterations + 1):
        endpoint = coupled.outer_kinematic_residual_endpoint
        if endpoint is None:
            raise ValueError("Low-mode line search requires continuous linear elements.")
        labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
        outer = labels == "outer_free_surface"
        panel_length = coupled.boundary.panel_length_m[outer]
        projected, _, projected_integral, unresolved_integral = (
            continuous_linear_weak_projection(panel_length, endpoint)
        )
        low_mode = cosine_low_pass(projected, args.retained_modes)
        source_nodes = np.column_stack(
            (
                coupled.outer_free_surface.node_xi,
                coupled.outer_free_surface.node_eta,
            )
        )
        normal = angle_bisector_normals(source_nodes)
        source_objective = coupled.kinematic_convergence_integral
        source_condition = coupled.solution.condition_number
        source_root = derive_shallow_water_jet_root_state_from_coupled(coupled)
        source_root_mismatch = abs(
            source_root.s_lambda - coupled.jet_interface.root_state.s_lambda
        ) / max(abs(coupled.jet_interface.root_state.s_lambda), np.finfo(float).eps)
        root_limit = max(float(args.root_mismatch_limit), 1.05 * source_root_mismatch)

        iteration_candidates: list[tuple[TrialMetrics, object]] = []
        for step_scale in sorted(set(args.step_scales), reverse=True):
            try:
                raw_nodes = _constrain_coupled_outer_nodes(
                    coupled.config,
                    source_nodes + float(step_scale) * low_mode[:, None] * normal,
                    allow_reversed_root=True,
                )
                candidate_nodes = _regrid_coupled_outer_nodes(
                    coupled.config,
                    raw_nodes,
                )
                displacement = maximum_midpoint_displacement_ratio(
                    source_nodes,
                    candidate_nodes,
                )
                candidate = _build_coupled_solution_from_outer_nodes(
                    coupled.config,
                    candidate_nodes,
                    coupled.dipole_coefficient,
                    root_inner_iterations=args.root_inner_iterations,
                    s_lambda_seed=coupled.jet_interface.root_state.s_lambda,
                )
                measured_root = derive_shallow_water_jet_root_state_from_coupled(candidate)
                root_mismatch = abs(
                    measured_root.s_lambda - candidate.jet_interface.root_state.s_lambda
                ) / max(
                    abs(candidate.jet_interface.root_state.s_lambda),
                    np.finfo(float).eps,
                )
                reason = trial_rejection_reason(
                    source_objective=source_objective,
                    candidate_objective=candidate.kinematic_convergence_integral,
                    minimum_relative_decrease=args.minimum_relative_decrease,
                    maximum_displacement_ratio_value=displacement,
                    displacement_limit=args.maximum_displacement_ratio,
                    source_condition_number=source_condition,
                    candidate_condition_number=candidate.solution.condition_number,
                    condition_number_ratio_limit=args.condition_number_ratio_limit,
                    dipole_coefficient=candidate.dipole_coefficient,
                    root_relative_mismatch=root_mismatch,
                    root_mismatch_limit=root_limit,
                )
                metrics = TrialMetrics(
                    iteration=iteration,
                    step_scale=float(step_scale),
                    objective=candidate.kinematic_convergence_integral,
                    relative_decrease=(
                        source_objective - candidate.kinematic_convergence_integral
                    )
                    / source_objective,
                    maximum_displacement_ratio=displacement,
                    condition_number=candidate.solution.condition_number,
                    condition_number_ratio=(
                        candidate.solution.condition_number / source_condition
                    ),
                    dipole_coefficient=candidate.dipole_coefficient,
                    root_relative_mismatch=root_mismatch,
                    accepted=not reason,
                    rejection_reason=reason,
                )
                iteration_candidates.append((metrics, candidate))
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
                metrics = TrialMetrics(
                    iteration=iteration,
                    step_scale=float(step_scale),
                    objective=float("nan"),
                    relative_decrease=float("nan"),
                    maximum_displacement_ratio=float("nan"),
                    condition_number=float("nan"),
                    condition_number_ratio=float("nan"),
                    dipole_coefficient=float("nan"),
                    root_relative_mismatch=float("nan"),
                    accepted=False,
                    rejection_reason=f"solver_failure:{type(error).__name__}:{error}",
                )
                iteration_candidates.append((metrics, None))

        trials.extend(item[0] for item in iteration_candidates)
        admissible = [item for item in iteration_candidates if item[0].accepted]
        if not admissible:
            break
        selected_metrics, selected = min(admissible, key=lambda item: item[0].objective)
        coupled = selected
        accepted_history.append(
            {
                "iteration": iteration,
                "step_scale": selected_metrics.step_scale,
                "objective": selected_metrics.objective,
                "relative_decrease": selected_metrics.relative_decrease,
                "weak_projected_integral_at_source": projected_integral,
                "unresolved_integral_at_source": unresolved_integral,
            }
        )

    pd.DataFrame([asdict(item) for item in trials]).to_csv(
        output / "low_mode_line_search_trials.csv",
        index=False,
    )
    pd.DataFrame(accepted_history).to_csv(
        output / "low_mode_line_search_accepted.csv",
        index=False,
    )
    pd.DataFrame(
        {
            "xi": coupled.outer_free_surface.node_xi,
            "eta": coupled.outer_free_surface.node_eta,
            "node_index": np.arange(len(coupled.outer_free_surface.node_xi)),
        }
    ).to_csv(output / "low_mode_final_outer_nodes.csv", index=False)
    _write_final_artifacts(output, coupled)
    final_root = coupled.jet_interface.root_state
    summary = {
        "status": "self_similar_low_mode_line_search_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "source_checkpoint": str(args.checkpoint.resolve()),
        "requested_iterations": args.iterations,
        "accepted_iterations": len(accepted_history),
        "retained_modes": args.retained_modes,
        "step_scales": [float(value) for value in args.step_scales],
        "safeguards": {
            "minimum_relative_decrease": args.minimum_relative_decrease,
            "maximum_displacement_ratio": args.maximum_displacement_ratio,
            "condition_number_ratio_limit": args.condition_number_ratio_limit,
            "root_mismatch_limit": args.root_mismatch_limit,
            "positive_dipole_required": True,
        },
        "initial_objective": checkpoint.coupled.kinematic_convergence_integral,
        "final_objective": coupled.kinematic_convergence_integral,
        "final_condition_number": coupled.solution.condition_number,
        "final_dipole_coefficient": coupled.dipole_coefficient,
        "final_root_s_lambda": final_root.s_lambda,
        "final_root_thickness": final_root.thickness,
        "conclusion": (
            "accepted_reference_isolated_descent_steps"
            if accepted_history
            else "no_admissible_descent_step"
        ),
    }
    (output / "low_mode_line_search_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
