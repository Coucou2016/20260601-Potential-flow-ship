from __future__ import annotations

import argparse
from dataclasses import asdict
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
    polyline_curvature_metrics,
)
from scripts.diagnose_self_similar_newton_krylov import (
    formal_outer_state,
    rebase_candidate_map_source,
)
from scripts.resume_self_similar_wedge import _write_final_artifacts


def load_saved_normal_direction(run: str | Path) -> tuple[np.ndarray, int]:
    """Load the last trust-scaled nodal displacement from one Newton run."""

    directory = Path(run).resolve()
    frame = pd.read_csv(directory / "newton_krylov_direction_nodes.csv")
    required = {"outer_iteration", "node_index", "normal_displacement"}
    if not required.issubset(frame.columns) or len(frame) == 0:
        raise ValueError("Newton direction data are empty or missing required columns.")
    iteration = int(frame["outer_iteration"].max())
    selected = frame[frame["outer_iteration"] == iteration].sort_values("node_index")
    expected = np.arange(len(selected), dtype=int)
    if not np.array_equal(selected["node_index"].to_numpy(dtype=int), expected):
        raise ValueError("Newton direction node indices must be contiguous from zero.")
    direction = selected["normal_displacement"].to_numpy(dtype=float)
    if not np.isfinite(direction).all() or np.linalg.norm(direction) <= np.finfo(float).eps:
        raise ValueError("Newton direction must be finite and non-zero.")
    return direction, iteration


def normalized_arc_coordinate(node_xi: np.ndarray, node_eta: np.ndarray) -> np.ndarray:
    """Return a monotone zero-to-one arc coordinate for one nodal polyline."""

    xi = np.asarray(node_xi, dtype=float)
    eta = np.asarray(node_eta, dtype=float)
    if xi.ndim != 1 or eta.shape != xi.shape or len(xi) < 2:
        raise ValueError("Arc-coordinate nodes must be matching one-dimensional arrays.")
    if not np.isfinite(xi).all() or not np.isfinite(eta).all():
        raise ValueError("Arc-coordinate nodes must be finite.")
    segment = np.hypot(np.diff(xi), np.diff(eta))
    if np.any(segment <= 0.0):
        raise ValueError("Arc-coordinate nodes must define positive-length segments.")
    arc = np.concatenate(([0.0], np.cumsum(segment)))
    return arc / arc[-1]


def map_saved_normal_direction(
    direction: np.ndarray,
    source_xi: np.ndarray,
    source_eta: np.ndarray,
    target_xi: np.ndarray,
    target_eta: np.ndarray,
    *,
    mapping: str,
) -> np.ndarray:
    """Map a physical normal-displacement field between declared nodal grids."""

    values = np.asarray(direction, dtype=float)
    source_arc = normalized_arc_coordinate(source_xi, source_eta)
    target_arc = normalized_arc_coordinate(target_xi, target_eta)
    if values.shape != source_arc.shape:
        raise ValueError("Saved direction and source checkpoint use different node counts.")
    if mapping == "strict":
        if values.shape != target_arc.shape:
            raise ValueError("Saved direction and initial checkpoint use different node counts.")
        return values.copy()
    if mapping != "normalized_arc":
        raise ValueError(f"Unknown direction mapping: {mapping}")
    mapped = np.interp(target_arc, source_arc, values)
    if not np.isfinite(mapped).all() or np.linalg.norm(mapped) <= np.finfo(float).eps:
        raise ValueError("Mapped Newton direction must be finite and non-zero.")
    return mapped


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reuse one frozen Newton--Krylov nodal direction with complete "
            "nonlinear root closure and exact endpoint acceptance at every step."
        )
    )
    parser.add_argument("--newton-run", type=Path, required=True)
    parser.add_argument("--initial-checkpoint", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--direction-mapping",
        choices=("strict", "normalized_arc"),
        default="strict",
        help=(
            "Use strict for the original nodal grid, or normalized_arc to "
            "interpolate the frozen physical displacement onto a regridded state."
        ),
    )
    parser.add_argument("--maximum-steps", type=int, default=8)
    parser.add_argument(
        "--step-factors",
        type=float,
        nargs="+",
        default=(1.0, 0.75, 0.5, 0.25, 0.125),
    )
    parser.add_argument("--minimum-relative-decrease", type=float, default=1.0e-4)
    parser.add_argument("--trust-radius", type=float, default=0.20)
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.10)
    parser.add_argument("--curvature-energy-ratio-limit", type=float, default=1.25)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument("--formal-objective-limit", type=float, default=1.0e-3)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.maximum_steps < 1:
        raise ValueError("--maximum-steps must be positive.")
    if any(not np.isfinite(value) or value <= 0.0 for value in args.step_factors):
        raise ValueError("Step factors must be finite and positive.")
    if not 0.0 < args.trust_radius <= 0.25:
        raise ValueError("--trust-radius must lie in (0, 0.25].")
    if args.curvature_energy_ratio_limit < 1.0:
        raise ValueError("Curvature-energy ratio limit must be at least one.")

    newton_run = args.newton_run.resolve()
    summary = json.loads(
        (newton_run / "newton_krylov_summary.json").read_text(encoding="utf-8")
    )
    if int(summary.get("accepted_iterations", 0)) < 1:
        raise ValueError("Direction reuse requires an accepted Newton--Krylov run.")
    saved_normal_displacement, direction_iteration = load_saved_normal_direction(
        newton_run
    )
    direction_checkpoint = load_coupled_self_similar_checkpoint(newton_run)
    initial_path = (
        newton_run
        if args.initial_checkpoint is None
        else args.initial_checkpoint.resolve()
    )
    initial = load_coupled_self_similar_checkpoint(initial_path)
    coupled = initial.coupled
    normal_displacement = map_saved_normal_direction(
        saved_normal_displacement,
        direction_checkpoint.coupled.outer_free_surface.node_xi,
        direction_checkpoint.coupled.outer_free_surface.node_eta,
        coupled.outer_free_surface.node_xi,
        coupled.outer_free_surface.node_eta,
        mapping=args.direction_mapping,
    )

    root_inner_iterations = int(summary["root_inner_iterations"])
    matching_surface_policy = str(summary["matching_surface_policy"])
    initial_state = formal_outer_state(coupled)
    outer_shape_dipole_coefficient = float(initial.outer_shape_dipole_coefficient)
    trial_rows: list[dict[str, object]] = []
    accepted_rows: list[dict[str, object]] = []
    rebase_rows: list[dict[str, object]] = []

    for reuse_step in range(1, args.maximum_steps + 1):
        coupled, outer_shape_dipole_coefficient, rebase = (
            rebase_candidate_map_source(
                coupled,
                source_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                root_inner_iterations=root_inner_iterations,
                matching_surface_policy=matching_surface_policy,
                outer_iteration=reuse_step,
                phase="pre_direction_reuse",
            )
        )
        rebase_rows.append(asdict(rebase))
        source_nodes = np.column_stack(
            (coupled.outer_free_surface.node_xi, coupled.outer_free_surface.node_eta)
        )
        source_state = formal_outer_state(coupled)
        source_curvature, source_turn = polyline_curvature_metrics(source_nodes)
        candidates: list[tuple[float, object, dict[str, object]]] = []
        for factor in sorted(set(args.step_factors), reverse=True):
            row: dict[str, object] = {
                "reuse_step": reuse_step,
                "step_factor": float(factor),
                "source_formal_exact_objective": source_state.exact_objective,
                "source_root_relative_mismatch": source_state.root_relative_mismatch,
                "source_condition_number": source_state.condition_number,
                "source_curvature_energy": source_curvature,
                "source_maximum_turning_angle_deg": source_turn,
            }
            try:
                candidate, candidate_nodes, displacement = _build_candidate(
                    coupled,
                    source_nodes,
                    float(factor) * normal_displacement,
                    root_inner_iterations=root_inner_iterations,
                    matching_surface_policy=matching_surface_policy,
                    far_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                    regrid_candidate=False,
                )
                candidate_state = formal_outer_state(candidate)
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
                row.update(
                    {
                        "candidate_formal_exact_objective": candidate_state.exact_objective,
                        "formal_exact_relative_decrease": (
                            source_state.exact_objective - candidate_state.exact_objective
                        )
                        / source_state.exact_objective,
                        "maximum_displacement_ratio": displacement,
                        "condition_number": candidate_state.condition_number,
                        "condition_number_ratio": (
                            candidate_state.condition_number / source_state.condition_number
                        ),
                        "root_relative_mismatch": candidate_state.root_relative_mismatch,
                        "curvature_energy": candidate_curvature,
                        "curvature_energy_ratio": curvature_ratio,
                        "maximum_turning_angle_deg": candidate_turn,
                        "accepted": not reason,
                        "rejection_reason": reason,
                    }
                )
                if not reason:
                    candidates.append((candidate_state.exact_objective, candidate, row))
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
                row.update(
                    {
                        "accepted": False,
                        "rejection_reason": (
                            f"solver_failure:{type(error).__name__}:{error}"
                        ),
                    }
                )
            trial_rows.append(row)
        if not candidates:
            break
        _, coupled, accepted = min(candidates, key=lambda item: item[0])
        accepted_rows.append(accepted)
        print(json.dumps({"progress": "reuse_step_accepted", **accepted}), flush=True)
        if formal_outer_state(coupled).exact_objective <= args.formal_objective_limit:
            break

    if accepted_rows:
        coupled, outer_shape_dipole_coefficient, rebase = (
            rebase_candidate_map_source(
                coupled,
                source_shape_dipole_coefficient=outer_shape_dipole_coefficient,
                root_inner_iterations=root_inner_iterations,
                matching_surface_policy=matching_surface_policy,
                outer_iteration=len(accepted_rows),
                phase="final_synchronization",
            )
        )
        rebase_rows.append(asdict(rebase))

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(trial_rows).to_csv(
        output / "newton_direction_reuse_trials.csv", index=False
    )
    pd.DataFrame(accepted_rows).to_csv(
        output / "newton_direction_reuse_accepted.csv", index=False
    )
    pd.DataFrame(rebase_rows).to_csv(
        output / "newton_direction_reuse_rebase.csv", index=False
    )
    _write_final_artifacts(output, coupled)
    frozen = solve_coupled_self_similar_wedge_pseudo_time(
        coupled,
        maximum_iterations=0,
        root_inner_iterations=root_inner_iterations,
    )
    checkpoint_path = write_coupled_self_similar_checkpoint(
        output,
        coupled,
        coupled_pseudo_time_history_frame(frozen),
        parent=initial,
        transformation={
            "type": "reference_isolated_newton_krylov_direction_reuse",
            "newton_run": str(newton_run),
            "direction_outer_iteration": direction_iteration,
            "direction_mapping": args.direction_mapping,
            "direction_source_node_count": len(saved_normal_displacement),
            "direction_target_node_count": len(normal_displacement),
            "requested_steps": args.maximum_steps,
            "accepted_steps": len(accepted_rows),
            "root_inner_iterations": root_inner_iterations,
            "matching_surface_policy": matching_surface_policy,
            "acceptance_objective": "unweighted_piecewise_linear_exact_integral",
            "candidate_map_far_shape_dipole_policy": "freeze_rebased_source",
            "candidate_map_regrid_policy": "frozen_nodes_during_direction_reuse",
            "reuse_step_rebase_policy": "sync_to_solved_dipole_then_regrid",
            "outer_shape_dipole_coefficient": outer_shape_dipole_coefficient,
            "reference_used_during_solve": False,
        },
    )
    final_state = formal_outer_state(coupled)
    result = {
        "status": "self_similar_newton_direction_reuse_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "newton_run": str(newton_run),
        "initial_checkpoint": str(initial_path),
        "direction_outer_iteration": direction_iteration,
        "direction_mapping": args.direction_mapping,
        "direction_source_node_count": len(saved_normal_displacement),
        "direction_target_node_count": len(normal_displacement),
        "requested_steps": args.maximum_steps,
        "accepted_steps": len(accepted_rows),
        "initial_formal_exact_objective": initial_state.exact_objective,
        "final_formal_exact_objective": final_state.exact_objective,
        "formal_objective_limit": args.formal_objective_limit,
        "formal_numerical_gate_pass": bool(
            final_state.exact_objective <= args.formal_objective_limit
            and final_state.root_relative_mismatch <= args.root_mismatch_limit
        ),
        "final_root_relative_mismatch": final_state.root_relative_mismatch,
        "root_mismatch_limit": args.root_mismatch_limit,
        "final_condition_number": final_state.condition_number,
        "checkpoint": str(checkpoint_path),
        "conclusion": (
            "accepted_frozen_newton_direction_steps"
            if accepted_rows
            else "no_admissible_frozen_newton_direction_step"
        ),
    }
    (output / "newton_direction_reuse_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
