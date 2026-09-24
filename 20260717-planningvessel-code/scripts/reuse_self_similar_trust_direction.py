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
    derive_shallow_water_jet_root_state_from_coupled,
    solve_coupled_self_similar_wedge_pseudo_time,
)
from scripts.diagnose_self_similar_low_mode_line_search import (
    trial_rejection_reason,
)
from scripts.diagnose_self_similar_low_mode_trust_region import (
    _build_candidate,
    _outer_state,
    constrained_damped_gauss_newton_step,
    damped_gauss_newton_step,
    dct_nodal_basis,
    polyline_curvature_metrics,
    root_feasibility_gate_limit,
    trust_region_scale,
)
from scripts.resume_self_similar_wedge import _write_final_artifacts


def reconstruct_saved_trust_direction(
    jacobian: np.ndarray,
    residual: np.ndarray,
    basis: np.ndarray,
    source_nodes: np.ndarray,
    *,
    damping: float,
    trust_radius: float,
    trust_radius_safety_factor: float,
    root_constraint: str,
    root_defect_gradient: np.ndarray | None,
    source_signed_root_defect: float | None = None,
) -> np.ndarray:
    """Reconstruct the accepted run's scaled nodal normal direction."""

    if root_constraint in {"preserve", "close"}:
        if root_defect_gradient is None:
            raise ValueError("A root-constrained direction requires its gradient.")
        if root_constraint == "close" and source_signed_root_defect is None:
            raise ValueError("A root-closing direction requires the source defect.")
        step = constrained_damped_gauss_newton_step(
            jacobian,
            residual,
            damping,
            root_defect_gradient,
            (
                0.0
                if root_constraint == "preserve"
                else -float(source_signed_root_defect)
            ),
        )
    elif root_constraint == "none":
        step = damped_gauss_newton_step(jacobian, residual, damping)
    else:
        raise ValueError("Unknown saved root constraint.")
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
            "Reuse one frozen, reference-isolated trust direction with full "
            "nonlinear BIE reconstruction and acceptance gates at every step."
        )
    )
    parser.add_argument("--trust-run", type=Path, required=True)
    parser.add_argument("--initial-checkpoint", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--maximum-steps", type=int, default=8)
    parser.add_argument(
        "--step-factors", type=float, nargs="+", default=(1.0, 0.5, 0.25)
    )
    parser.add_argument("--minimum-relative-decrease", type=float, default=1.0e-4)
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.05)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument("--curvature-energy-ratio-limit", type=float, default=1.10)
    parser.add_argument("--root-inner-iterations", type=int, default=0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.maximum_steps < 1 or args.root_inner_iterations < 0:
        raise ValueError("Step count must be positive and root iterations non-negative.")
    if any(value <= 0.0 or not np.isfinite(value) for value in args.step_factors):
        raise ValueError("Step factors must be finite and positive.")
    if args.curvature_energy_ratio_limit < 1.0:
        raise ValueError("Curvature-energy ratio limit must be at least one.")

    trust_run = args.trust_run.resolve()
    summary = json.loads(
        (trust_run / "low_mode_trust_region_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if summary["basis"] != "dct" or int(summary["accepted_iterations"]) < 1:
        raise ValueError("Direction reuse currently requires an accepted DCT trust run.")
    source = load_coupled_self_similar_checkpoint(summary["source_checkpoint"])
    initial_path = (
        trust_run
        if args.initial_checkpoint is None
        else args.initial_checkpoint.resolve()
    )
    initial = load_coupled_self_similar_checkpoint(initial_path)
    if source.config.free_surface_panels != initial.config.free_surface_panels:
        raise ValueError("Saved direction and initial checkpoint use different grids.")

    mode_count = int(summary["mode_count"])
    source_nodes = np.column_stack(
        (source.coupled.outer_free_surface.node_xi, source.coupled.outer_free_surface.node_eta)
    )
    labels = np.asarray(source.coupled.boundary.panel_labels, dtype=object)
    source_length = source.coupled.boundary.panel_length_m[
        labels == "outer_free_surface"
    ]
    basis = dct_nodal_basis(len(source_nodes), mode_count)
    residual, _, _ = _outer_state(
        source.coupled,
        mode_count,
        metric_panel_length=source_length,
        residual_space=str(summary["residual_space"]),
    )
    jacobian_frame = pd.read_csv(trust_run / "low_mode_trust_region_jacobians.csv")
    iteration = int(jacobian_frame["iteration"].max())
    selected = jacobian_frame[jacobian_frame["iteration"] == iteration]
    jacobian = selected.pivot(
        index="residual_mode", columns="shape_mode", values="value"
    ).sort_index().sort_index(axis=1).to_numpy(dtype=float)
    gradient = (
        selected.groupby("shape_mode")["root_defect_derivative"]
        .first()
        .sort_index()
        .to_numpy(dtype=float)
    )
    measured_source = derive_shallow_water_jet_root_state_from_coupled(
        source.coupled
    )
    source_interface = float(source.coupled.jet_interface.root_state.s_lambda)
    source_signed_root_defect = (
        measured_source.s_lambda - source_interface
    ) / max(abs(source_interface), np.finfo(float).eps)
    normal_displacement = reconstruct_saved_trust_direction(
        jacobian,
        residual,
        basis,
        source_nodes,
        damping=float(summary["damping"]),
        trust_radius=float(summary["trust_radius"]),
        trust_radius_safety_factor=float(summary["trust_radius_safety_factor"]),
        root_constraint=str(summary["root_constraint"]),
        root_defect_gradient=gradient,
        source_signed_root_defect=source_signed_root_defect,
    )

    coupled = initial.coupled
    outer_shape_dipole_coefficient = float(initial.outer_shape_dipole_coefficient)
    initial_objective = float(coupled.kinematic_convergence_integral)
    rows: list[dict[str, object]] = []
    accepted_rows: list[dict[str, object]] = []
    for step_index in range(1, args.maximum_steps + 1):
        nodes = np.column_stack(
            (coupled.outer_free_surface.node_xi, coupled.outer_free_surface.node_eta)
        )
        source_objective = float(coupled.kinematic_convergence_integral)
        source_condition = float(coupled.solution.condition_number)
        source_curvature, source_turn = polyline_curvature_metrics(nodes)
        measured_source = derive_shallow_water_jet_root_state_from_coupled(coupled)
        source_root_mismatch = abs(
            measured_source.s_lambda - coupled.jet_interface.root_state.s_lambda
        ) / max(abs(coupled.jet_interface.root_state.s_lambda), np.finfo(float).eps)
        root_limit = root_feasibility_gate_limit(
            source_root_mismatch,
            args.root_mismatch_limit,
        )
        feasibility_repair = source_root_mismatch > args.root_mismatch_limit
        candidates: list[tuple[float, object, dict[str, object]]] = []
        for factor in sorted(set(args.step_factors), reverse=True):
            row: dict[str, object] = {
                "reuse_step": step_index,
                "step_factor": float(factor),
                "source_objective": source_objective,
                "source_curvature_energy": source_curvature,
                "source_maximum_turning_angle_deg": source_turn,
                "source_root_relative_mismatch": source_root_mismatch,
                "root_gate_limit": root_limit,
                "root_feasibility_repair": feasibility_repair,
            }
            try:
                candidate, candidate_nodes, displacement = _build_candidate(
                    coupled,
                    nodes,
                    float(factor) * normal_displacement,
                    root_inner_iterations=args.root_inner_iterations,
                    matching_surface_policy=str(
                        summary.get("matching_surface_policy", "relocate")
                    ),
                )
                measured = derive_shallow_water_jet_root_state_from_coupled(candidate)
                root_mismatch = abs(
                    measured.s_lambda - candidate.jet_interface.root_state.s_lambda
                ) / max(
                    abs(candidate.jet_interface.root_state.s_lambda),
                    np.finfo(float).eps,
                )
                curvature, maximum_turn = polyline_curvature_metrics(candidate_nodes)
                curvature_ratio = curvature / max(
                    source_curvature, np.finfo(float).eps
                )
                reason = trial_rejection_reason(
                    source_objective=source_objective,
                    candidate_objective=candidate.kinematic_convergence_integral,
                    minimum_relative_decrease=args.minimum_relative_decrease,
                    maximum_displacement_ratio_value=displacement,
                    displacement_limit=float(summary["trust_radius"]),
                    source_condition_number=source_condition,
                    candidate_condition_number=candidate.solution.condition_number,
                    condition_number_ratio_limit=args.condition_number_ratio_limit,
                    dipole_coefficient=candidate.dipole_coefficient,
                    root_relative_mismatch=root_mismatch,
                    root_mismatch_limit=root_limit,
                )
                if not reason and curvature_ratio > args.curvature_energy_ratio_limit:
                    reason = "curvature_energy"
                row.update(
                    {
                        "candidate_objective": candidate.kinematic_convergence_integral,
                        "relative_decrease": (
                            source_objective - candidate.kinematic_convergence_integral
                        )
                        / source_objective,
                        "maximum_displacement_ratio": displacement,
                        "condition_number": candidate.solution.condition_number,
                        "root_relative_mismatch": root_mismatch,
                        "hard_root_pass": root_mismatch <= args.root_mismatch_limit,
                        "curvature_energy": curvature,
                        "curvature_energy_ratio": curvature_ratio,
                        "maximum_turning_angle_deg": maximum_turn,
                        "accepted": not reason,
                        "rejection_reason": reason,
                    }
                )
                if not reason:
                    candidates.append(
                        (candidate.kinematic_convergence_integral, candidate, row)
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
        source_dipole_coefficient = float(coupled.dipole_coefficient)
        _, coupled, accepted = min(candidates, key=lambda item: item[0])
        outer_shape_dipole_coefficient = source_dipole_coefficient
        accepted["outer_shape_dipole_coefficient"] = outer_shape_dipole_coefficient
        accepted_rows.append(accepted)
        print(json.dumps({"progress": "reuse_step_accepted", **accepted}), flush=True)

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "trust_direction_reuse_trials.csv", index=False)
    pd.DataFrame(accepted_rows).to_csv(
        output / "trust_direction_reuse_accepted.csv", index=False
    )
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
            "type": "reference_isolated_frozen_trust_direction_reuse",
            "trust_run": str(trust_run),
            "maximum_steps": args.maximum_steps,
            "accepted_steps": len(accepted_rows),
            "root_gate_policy": "hard_limit_or_monotonic_feasibility_repair",
            "outer_shape_dipole_coefficient": outer_shape_dipole_coefficient,
            "reference_used_during_solve": False,
        },
    )
    measured_final = derive_shallow_water_jet_root_state_from_coupled(coupled)
    final_root_mismatch = abs(
        measured_final.s_lambda - coupled.jet_interface.root_state.s_lambda
    ) / max(abs(coupled.jet_interface.root_state.s_lambda), np.finfo(float).eps)
    result = {
        "status": "self_similar_frozen_trust_direction_reuse_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "trust_run": str(trust_run),
        "initial_checkpoint": str(initial_path),
        "requested_steps": args.maximum_steps,
        "accepted_steps": len(accepted_rows),
        "root_gate_policy": "hard_limit_or_monotonic_feasibility_repair",
        "root_mismatch_limit": args.root_mismatch_limit,
        "final_root_relative_mismatch": float(final_root_mismatch),
        "final_hard_root_pass": bool(
            final_root_mismatch <= args.root_mismatch_limit
        ),
        "initial_objective": initial_objective,
        "final_objective": float(coupled.kinematic_convergence_integral),
        "checkpoint": str(checkpoint_path),
        "conclusion": (
            "accepted_frozen_direction_steps"
            if accepted_rows
            else "no_admissible_frozen_direction_step"
        ),
    }
    (output / "trust_direction_reuse_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
