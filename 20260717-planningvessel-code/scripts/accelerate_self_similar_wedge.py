from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    accelerate_coupled_self_similar_checkpoints,
    coupled_pseudo_time_history_frame,
    infer_matching_surface_phase,
    load_coupled_self_similar_checkpoint,
    write_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    derive_shallow_water_jet_root_state_from_coupled,
    evaluate_self_similar_wedge_reference,
    evaluate_self_similar_wedge_scalar_reference,
    solve_coupled_self_similar_wedge_pseudo_time,
)
from scripts.resume_self_similar_wedge import (
    _plot_resume_diagnostic,
    _write_final_artifacts,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a qualified vector-Aitken state from three sequential coupled "
            "wedge checkpoints and verify it by further pseudo-time steps."
        )
    )
    parser.add_argument("--checkpoints", type=Path, nargs=3, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--additional-iterations", type=int, default=5)
    parser.add_argument("--pseudo-cfl", type=float, default=None)
    parser.add_argument("--maximum-displacement-ratio", type=float, default=4.0)
    parser.add_argument("--maximum-convergence-factor", type=float, default=0.9)
    parser.add_argument(
        "--clip-to-displacement-limit",
        action="store_true",
        help=(
            "Explicitly clip the extrapolation to the displacement trust region; "
            "the rebuilt candidate must still pass residual and conditioning gates."
        ),
    )
    parser.add_argument(
        "--reference-csv",
        type=Path,
        default=(
            ROOT
            / "benchmarks"
            / "sun2007_fig2_6_wedge_similarity"
            / "fig2_6_zhao_faltinsen_similarity_curves.csv"
        ),
    )
    parser.add_argument(
        "--scalar-reference-csv",
        type=Path,
        default=(
            ROOT
            / "benchmarks"
            / "iafrati2013_self_similar_wedge"
            / "table1_pressure_peak.csv"
        ),
    )
    return parser


def _state(coupled: object) -> dict[str, object]:
    root = coupled.jet_interface.root_state
    measured = derive_shallow_water_jet_root_state_from_coupled(coupled)
    return {
        "kinematic_rms": coupled.kinematic_rms,
        "kinematic_integral": coupled.kinematic_integral,
        "kinematic_length_weighted_rms": (
            coupled.kinematic_length_weighted_rms
        ),
        "solved_dipole_coefficient": coupled.dipole_coefficient,
        "bem_condition_number": coupled.solution.condition_number,
        "body_pressure_min": float(np.min(coupled.body_pressure_coefficient)),
        "body_pressure_max": float(np.max(coupled.body_pressure_coefficient)),
        "body_vertical_force_coefficient": (
            coupled.body_vertical_force_coefficient
        ),
        "interface_s_lambda": root.s_lambda,
        "measured_s_lambda": measured.s_lambda,
        "relative_s_lambda_mismatch": abs(measured.s_lambda - root.s_lambda)
        / max(abs(root.s_lambda), np.finfo(float).eps),
        "jet_reached_tip": coupled.jet_interface.jet.reached_tip,
        "jet_point_count": len(coupled.jet_interface.jet.thickness),
        "jet_tip_thickness": float(coupled.jet_interface.jet.thickness[-1]),
        "jet_tip_s_lambda": float(coupled.jet_interface.jet.s_lambda[-1]),
    }


def write_acceleration_rejection(
    output: Path,
    source_paths: tuple[Path, Path, Path],
    checkpoints: tuple[object, object, object],
    *,
    reason: str,
    maximum_displacement_ratio: float,
    maximum_convergence_factor: float = 0.9,
    clip_to_displacement_limit: bool = False,
) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    def phase_diagnostic(checkpoint: object) -> dict[str, object]:
        try:
            return {
                "status": "AVAILABLE",
                **asdict(infer_matching_surface_phase(checkpoint.history)),
            }
        except (AttributeError, TypeError, ValueError) as error:
            return {"status": "UNAVAILABLE", "reason": str(error)}

    report = {
        "status": "self_similar_vector_aitken_rejected",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_transformation": False,
        "qualification": {
            "result": "REJECTED",
            "reason": reason,
            "limits": {
                "maximum_convergence_factor": float(maximum_convergence_factor),
                "maximum_interval_ratio": 1.25,
                "maximum_node_displacement_ratio": float(
                    maximum_displacement_ratio
                ),
                "clip_to_displacement_limit": bool(clip_to_displacement_limit),
                "maximum_candidate_residual_ratio": 0.9,
                "candidate_residual_metric": (
                    "Iafrati 2013 Eq. (52) integral K"
                ),
                "maximum_condition_number_ratio": 5.0,
                "matching_surface_minimum_relative_jump": 0.05,
                "matching_surface_periods_must_match": True,
                "matching_surface_phases_must_match": True,
            },
        },
        "sources": [
            {
                "path": str(path.resolve()),
                "completed_iterations": int(checkpoint.completed_iterations),
                "cumulative_pseudo_time": float(checkpoint.cumulative_pseudo_time),
                "source_hashes": checkpoint.source_hashes,
                "reconstruction_relative_errors": (
                    checkpoint.reconstruction_relative_errors
                ),
                "matching_surface_phase": phase_diagnostic(checkpoint),
            }
            for path, checkpoint in zip(source_paths, checkpoints)
        ],
    }
    path = output / "acceleration_rejection.json"
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return path


def main() -> int:
    args = _parser().parse_args()
    if args.additional_iterations < 1:
        raise ValueError("--additional-iterations must be positive.")
    overrides = (
        {"pseudo_cfl": args.pseudo_cfl}
        if args.pseudo_cfl is not None
        else None
    )
    checkpoints = tuple(
        load_coupled_self_similar_checkpoint(
            path,
            continuation_config_overrides=overrides,
        )
        for path in args.checkpoints
    )
    try:
        accelerated = accelerate_coupled_self_similar_checkpoints(
            checkpoints,
            maximum_convergence_factor=args.maximum_convergence_factor,
            maximum_displacement_ratio=args.maximum_displacement_ratio,
            clip_extrapolation_to_displacement_limit=(
                args.clip_to_displacement_limit
            ),
        )
    except ValueError as error:
        rejection = write_acceleration_rejection(
            args.out,
            tuple(args.checkpoints),
            checkpoints,
            reason=str(error),
            maximum_displacement_ratio=args.maximum_displacement_ratio,
            maximum_convergence_factor=args.maximum_convergence_factor,
            clip_to_displacement_limit=args.clip_to_displacement_limit,
        )
        print(
            json.dumps(
                {"status": "REJECTED", "report": str(rejection)},
                ensure_ascii=True,
            )
        )
        return 2
    candidate_state = _state(accelerated.coupled)
    continuation = solve_coupled_self_similar_wedge_pseudo_time(
        accelerated.coupled,
        maximum_iterations=args.additional_iterations,
        root_inner_iterations=0,
    )
    history = coupled_pseudo_time_history_frame(continuation)
    coupled = continuation.coupled
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    transformation = {
        "type": "qualified_vector_aitken_outer_state",
        "source_paths": [str(path.resolve()) for path in args.checkpoints],
        "source_pseudo_times": list(accelerated.source_pseudo_times),
        "source_pseudo_time_basis": accelerated.source_pseudo_time_basis,
        "source_matching_surface_phases": list(
            accelerated.source_matching_surface_phases
        ),
        "source_modal_cycle_lengths": list(
            accelerated.source_modal_cycle_lengths
        ),
        "source_matching_surface_reset_counts": list(
            accelerated.source_matching_surface_reset_counts
        ),
        "time_interval_ratio": accelerated.time_interval_ratio,
        "vector_convergence_factor": accelerated.vector_convergence_factor,
        "raw_extrapolation_factor": accelerated.raw_extrapolation_factor,
        "extrapolation_factor": accelerated.extrapolation_factor,
        "extrapolation_was_clipped": accelerated.extrapolation_was_clipped,
        "maximum_node_displacement_ratio": (
            accelerated.maximum_node_displacement_ratio
        ),
        "candidate_residual_ratio": accelerated.residual_ratio,
        "candidate_legacy_unweighted_rms_ratio": (
            accelerated.legacy_unweighted_rms_ratio
        ),
        "candidate_condition_number_ratio": accelerated.condition_number_ratio,
        "reference_used_during_transformation": False,
    }
    checkpoint_path = write_coupled_self_similar_checkpoint(
        output,
        coupled,
        history,
        parent=checkpoints[-1],
        transformation=transformation,
    )
    _write_final_artifacts(output, coupled)
    distributed = evaluate_self_similar_wedge_reference(coupled, args.reference_csv)
    scalar = evaluate_self_similar_wedge_scalar_reference(
        coupled, args.scalar_reference_csv
    )
    summary = {
        "status": "self_similar_vector_aitken_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "acceleration": transformation,
        "candidate_state": candidate_state,
        "continuation": {
            "requested_iterations": args.additional_iterations,
            "accepted_iterations": len(continuation.time_step_history),
            "termination_reason": continuation.termination_reason,
            "failure_message": continuation.failure_message,
            "pseudo_time": float(history.iloc[-1]["pseudo_time"]),
        },
        "final_state": _state(coupled),
        "post_solve_reference_metrics": asdict(distributed),
        "post_solve_scalar_reference_metrics": asdict(scalar),
        "checkpoint": str(checkpoint_path),
    }
    (output / "acceleration_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    _plot_resume_diagnostic(output, history, coupled, args.reference_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
