from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    load_coupled_self_similar_checkpoint,
    merge_coupled_checkpoint_history,
    write_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    derive_shallow_water_jet_root_state_from_coupled,
    evaluate_self_similar_wedge_reference,
    evaluate_self_similar_wedge_scalar_reference,
    solve_coupled_self_similar_wedge_pseudo_time,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resume a verified coupled self-similar wedge checkpoint."
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--additional-iterations", type=int, required=True)
    parser.add_argument("--root-inner-iterations", type=int, default=0)
    parser.add_argument(
        "--force-fixed-steps",
        action="store_true",
        help=(
            "Run exactly --additional-iterations accepted steps even when the "
            "source already satisfies the kinematic stopping tolerance. This is "
            "a diagnostic time-step-convergence mode."
        ),
    )
    parser.add_argument(
        "--pseudo-cfl",
        type=float,
        default=None,
        help=(
            "Override only the continuation pseudo-time CFL. The frozen geometry, "
            "potential, jet state, discretization, and physical configuration remain "
            "unchanged."
        ),
    )
    parser.add_argument(
        "--jet-bie-panel-count",
        type=int,
        default=None,
        help=(
            "Diagnostic override that continuously resamples the shallow-water "
            "solution to a fixed number of BIE panels per side."
        ),
    )
    parser.add_argument(
        "--pseudo-time-preconditioner",
        choices=("uniform", "panel_length"),
        default=None,
        help="Experimental positive spatial preconditioner for pseudo-time relaxation.",
    )
    parser.add_argument(
        "--pseudo-time-preconditioner-max-ratio",
        type=float,
        default=None,
        help="Maximum local acceleration ratio for panel_length preconditioning.",
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


def _write_final_artifacts(output: Path, coupled: object) -> None:
    boundary = coupled.boundary
    labels = np.asarray(boundary.panel_labels, dtype=object)
    body = (labels == "body") | (labels == "shallow_jet_body")
    pd.DataFrame(
        {
            "xi": boundary.node_y_m,
            "eta": boundary.node_z_up_m,
            "node_index": np.arange(len(boundary.node_y_m)),
        }
    ).to_csv(output / "coupled_boundary_nodes.csv", index=False)
    pd.DataFrame(
        {
            "eta": boundary.panel_mid_z_up_m[body],
            "xi": boundary.panel_mid_y_m[body],
            "pressure_coefficient": coupled.body_pressure_coefficient,
            "potential": coupled.solution.potential_m2_s[body],
            "normal_derivative": coupled.solution.normal_derivative_m_s[body],
            "segment": labels[body],
        }
    ).to_csv(output / "coupled_body_pressure.csv", index=False)
    outer = labels == "outer_free_surface"
    outer_data: dict[str, np.ndarray] = {
        "panel_index": np.flatnonzero(outer),
        "mid_xi": boundary.panel_mid_y_m[outer],
        "mid_eta": boundary.panel_mid_z_up_m[outer],
        "panel_length": boundary.panel_length_m[outer],
        "kinematic_residual_midpoint": coupled.outer_kinematic_residual,
    }
    endpoint_residual = coupled.outer_kinematic_residual_endpoint
    if endpoint_residual is not None:
        outer_data["kinematic_residual_left"] = endpoint_residual[:, 0]
        outer_data["kinematic_residual_right"] = endpoint_residual[:, 1]
        outer_data["kinematic_integral_panel_linear_exact"] = (
            boundary.panel_length_m[outer]
            * (
                np.square(endpoint_residual[:, 0])
                + endpoint_residual[:, 0] * endpoint_residual[:, 1]
                + np.square(endpoint_residual[:, 1])
            )
            / 3.0
        )
    pd.DataFrame(outer_data).to_csv(
        output / "coupled_outer_kinematic_residual.csv",
        index=False,
    )
    jet = coupled.jet_interface.jet
    pd.DataFrame(
        {
            "lambda": jet.lambda_coordinate,
            "thickness": jet.thickness,
            "s_lambda": jet.s_lambda,
            "s_tau": jet.s_tau,
            "subiterations": jet.subiterations,
            "body_xi": coupled.jet_interface.body_node_xi,
            "body_eta": coupled.jet_interface.body_node_eta,
            "free_xi": coupled.jet_interface.free_node_xi,
            "free_eta": coupled.jet_interface.free_node_eta,
        }
    ).to_csv(output / "coupled_shallow_water_jet.csv", index=False)


def _plot_resume_diagnostic(
    output: Path,
    history: pd.DataFrame,
    coupled: object,
    reference_csv: Path,
) -> None:
    reference = pd.read_csv(reference_csv)
    beta = float(coupled.config.deadrise_deg)
    selected = reference[np.isclose(reference["beta_deg"], beta)]
    pressure_reference = selected[selected["quantity"] == "pressure"]
    free_reference = selected[selected["quantity"] == "free_surface"]
    labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
    body = (labels == "body") | (labels == "shallow_jet_body")

    figure, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    metric_name = "kinematic_rms"
    metric_label = "Legacy kinematic RMS"
    if "kinematic_convergence_integral" in history.columns:
        convergence_integral = pd.to_numeric(
            history["kinematic_convergence_integral"],
            errors="coerce",
        )
        if np.isfinite(convergence_integral).any():
            metric_name = "kinematic_convergence_integral"
            metric_label = "Discretization-consistent Iafrati Eq. (52) K"
    if metric_name == "kinematic_rms" and "kinematic_integral" in history.columns:
        integral = pd.to_numeric(history["kinematic_integral"], errors="coerce")
        if np.isfinite(integral).any():
            metric_name = "kinematic_integral"
            metric_label = "Iafrati Eq. (52) K"
    axes[0, 0].semilogy(history["iteration"], history[metric_name])
    axes[0, 0].set(xlabel="Cumulative iteration", ylabel=metric_label)
    axes[0, 0].grid(True, alpha=0.25)

    axes[0, 1].plot(history["iteration"], history["root_body_eta"], label="root eta")
    axes[0, 1].plot(
        history["iteration"],
        history["root_relative_mismatch"],
        label="root mismatch",
    )
    axes[0, 1].set(xlabel="Cumulative iteration", ylabel="State value")
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.25)

    axes[1, 0].plot(
        coupled.outer_free_surface.node_xi,
        coupled.outer_free_surface.node_eta,
        label="computed outer free surface",
    )
    axes[1, 0].plot(
        coupled.jet_interface.free_node_xi,
        coupled.jet_interface.free_node_eta,
        label="computed shallow jet",
    )
    if len(free_reference):
        axes[1, 0].scatter(
            free_reference["x_nondimensional"],
            free_reference["y_nondimensional"],
            s=8,
            alpha=0.5,
            label="digitized similarity reference",
        )
    axes[1, 0].set(xlabel="xi", ylabel="eta")
    axes[1, 0].axis("equal")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(True, alpha=0.25)

    axes[1, 1].plot(
        coupled.boundary.panel_mid_z_up_m[body],
        coupled.body_pressure_coefficient,
        label="computed",
    )
    if len(pressure_reference):
        axes[1, 1].scatter(
            pressure_reference["x_nondimensional"],
            pressure_reference["y_nondimensional"],
            s=8,
            alpha=0.5,
            label="digitized similarity reference",
        )
    axes[1, 1].set(xlabel="eta on wedge", ylabel="Cp")
    axes[1, 1].legend(fontsize=8)
    axes[1, 1].grid(True, alpha=0.25)
    figure.suptitle(f"Resumed self-similar wedge diagnostic, beta={beta:g} deg")
    figure.savefig(output / "resumed_self_similar_wedge_diagnostic.png", dpi=180)
    plt.close(figure)


def _identity_resume_transformation(
    checkpoint: object,
    continuation: object,
) -> dict[str, object] | None:
    if len(continuation.time_step_history) > 0:
        return None
    return {
        "type": "identity_resume_at_converged_source",
        "outer_shape_dipole_coefficient": (
            checkpoint.outer_shape_dipole_coefficient
        ),
        "termination_reason": continuation.termination_reason,
        "continuation_config_overrides": (
            checkpoint.continuation_config_overrides
        ),
        "reference_used_during_transformation": False,
    }


def main() -> int:
    args = _parser().parse_args()
    if args.additional_iterations < 1:
        raise ValueError("--additional-iterations must be positive.")
    if args.root_inner_iterations < 0:
        raise ValueError("--root-inner-iterations must be non-negative.")
    source = args.checkpoint.resolve()
    output = args.out.resolve()
    if source == output:
        raise ValueError("Resume output must differ from the source checkpoint.")
    output.mkdir(parents=True, exist_ok=True)

    overrides = {}
    if args.pseudo_cfl is not None:
        overrides["pseudo_cfl"] = args.pseudo_cfl
    if args.jet_bie_panel_count is not None:
        overrides["coupled_jet_bie_panel_count"] = args.jet_bie_panel_count
    if args.pseudo_time_preconditioner is not None:
        overrides["coupled_pseudo_time_preconditioner"] = (
            args.pseudo_time_preconditioner
        )
    if args.pseudo_time_preconditioner_max_ratio is not None:
        overrides["coupled_pseudo_time_preconditioner_max_ratio"] = (
            args.pseudo_time_preconditioner_max_ratio
        )
    checkpoint = load_coupled_self_similar_checkpoint(
        source,
        continuation_config_overrides=overrides or None,
    )
    continuation = solve_coupled_self_similar_wedge_pseudo_time(
        checkpoint.coupled,
        maximum_iterations=args.additional_iterations,
        root_inner_iterations=args.root_inner_iterations,
        stop_when_converged=not args.force_fixed_steps,
    )
    merged = merge_coupled_checkpoint_history(checkpoint, continuation)
    coupled = continuation.coupled
    transformation = _identity_resume_transformation(checkpoint, continuation)
    checkpoint_path = write_coupled_self_similar_checkpoint(
        output,
        coupled,
        merged,
        parent=checkpoint,
        transformation=transformation,
    )
    _write_final_artifacts(output, coupled)

    try:
        distributed = asdict(
            evaluate_self_similar_wedge_reference(coupled, args.reference_csv)
        )
    except ValueError as error:
        distributed = {
            "status": "REFERENCE_NOT_AVAILABLE",
            "reason": str(error),
            "used_during_solve": False,
        }
    try:
        scalar = asdict(
            evaluate_self_similar_wedge_scalar_reference(
                coupled,
                args.scalar_reference_csv,
            )
        )
    except ValueError as error:
        scalar = {
            "status": "REFERENCE_NOT_AVAILABLE",
            "reason": str(error),
            "used_during_solve": False,
        }
    root = coupled.jet_interface.root_state
    measured = derive_shallow_water_jet_root_state_from_coupled(coupled)
    summary = {
        "status": (
            "self_similar_coupled_forced_step_diagnostic_unvalidated"
            if args.force_fixed_steps
            else "self_similar_coupled_resume_diagnostic_unvalidated"
        ),
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "source_checkpoint": {
            "path": str(source),
            "kind": checkpoint.source_kind,
            "completed_iterations": checkpoint.completed_iterations,
            "cumulative_pseudo_time": checkpoint.cumulative_pseudo_time,
            "source_hashes": checkpoint.source_hashes,
            "reconstruction_relative_errors": (
                checkpoint.reconstruction_relative_errors
            ),
            "continuation_config_overrides": (
                checkpoint.continuation_config_overrides
            ),
        },
        "continuation": {
            "requested_iterations": args.additional_iterations,
            "accepted_iterations": len(continuation.time_step_history),
            "forced_fixed_steps": bool(args.force_fixed_steps),
            "termination_reason": continuation.termination_reason,
            "failure_message": continuation.failure_message,
            "completed_iterations": int(merged.iloc[-1]["iteration"]),
            "cumulative_pseudo_time": float(merged.iloc[-1]["pseudo_time"]),
        },
        "final_state": {
            "kinematic_rms": coupled.kinematic_rms,
            "kinematic_integral": coupled.kinematic_integral,
            "kinematic_integral_linear_exact": (
                coupled.kinematic_integral_linear_exact
            ),
            "kinematic_integral_endpoint_gradient": (
                coupled.kinematic_integral_endpoint_gradient
            ),
            "kinematic_convergence_integral": (
                coupled.kinematic_convergence_integral
            ),
            "kinematic_length_weighted_rms": (
                coupled.kinematic_length_weighted_rms
            ),
            "spray_root_corner_angle_deg": coupled.spray_root_corner_angle_deg,
            "spray_root_normal_derivative_sides": (
                None
                if coupled.spray_root_normal_derivative_sides is None
                else coupled.spray_root_normal_derivative_sides.tolist()
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
        },
        "post_solve_reference_metrics": distributed,
        "post_solve_scalar_reference_metrics": scalar,
        "checkpoint": str(checkpoint_path),
    }
    (output / "resume_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    _plot_resume_diagnostic(output, merged, coupled, args.reference_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
