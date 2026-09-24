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
    coupled_pseudo_time_history_frame,
    load_coupled_self_similar_checkpoint,
    regrid_coupled_self_similar_checkpoint,
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
            "Explicitly regrid one frozen coupled self-similar wedge checkpoint "
            "and continue it for a spatial-convergence diagnostic."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--outer-panels", type=int, required=True)
    parser.add_argument("--far-radius", type=float, default=None)
    parser.add_argument(
        "--outer-grid-mode",
        choices=("geometric_root", "double_ended", "frozen_monitor"),
        default=None,
    )
    parser.add_argument("--root-spacing-ratio", type=float, default=None)
    parser.add_argument("--far-spacing-ratio", type=float, default=None)
    parser.add_argument("--endpoint-decay", type=float, default=None)
    parser.add_argument("--far-field-panels", type=int, default=None)
    parser.add_argument("--symmetry-panels", type=int, default=None)
    parser.add_argument("--monitor-residual-weight", type=float, default=None)
    parser.add_argument("--monitor-curvature-weight", type=float, default=0.25)
    parser.add_argument("--monitor-growth-weight", type=float, default=0.15)
    parser.add_argument("--monitor-smoothing-passes", type=int, default=2)
    parser.add_argument(
        "--monitor-maximum-node-shift-panels",
        type=float,
        default=2.0,
    )
    parser.add_argument("--jet-bie-panels", type=int, default=None)
    parser.add_argument(
        "--jet-terminal-closure",
        choices=("legacy_parity", "continuous_tip"),
        default=None,
    )
    parser.add_argument(
        "--linear-gradient-recovery",
        choices=("element", "connected_nodal"),
        default=None,
    )
    parser.add_argument(
        "--linear-corner-treatment",
        choices=("shared_node", "displaced_double_node"),
        default=None,
    )
    parser.add_argument(
        "--linear-far-corner-treatment",
        choices=("shared_node", "displaced_double_node"),
        default=None,
    )
    parser.add_argument(
        "--linear-cusp-velocity-recovery",
        choices=("connected_average", "split_average", "split_outer_side"),
        default=None,
    )
    parser.add_argument(
        "--free-surface-update",
        choices=("full_gradient", "continuous_normal"),
        default=None,
    )
    parser.add_argument("--additional-iterations", type=int, required=True)
    parser.add_argument("--pseudo-cfl", type=float, default=None)
    parser.add_argument("--root-inner-iterations", type=int, default=0)
    parser.add_argument(
        "--root-inner-tolerance",
        type=float,
        default=None,
        help=(
            "Optional shallow-jet matching tolerance persisted in the "
            "continuation checkpoint."
        ),
    )
    parser.add_argument(
        "--root-state-recovery",
        choices=("first_panel_midpoint", "quadratic_root_extrapolation"),
        default=None,
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


def main() -> int:
    args = _parser().parse_args()
    if args.additional_iterations < 0:
        raise ValueError("--additional-iterations must be non-negative.")
    if args.root_inner_iterations < 0:
        raise ValueError("--root-inner-iterations must be non-negative.")
    if args.root_inner_tolerance is not None and (
        not np.isfinite(args.root_inner_tolerance)
        or args.root_inner_tolerance <= 0.0
    ):
        raise ValueError("--root-inner-tolerance must be positive and finite.")
    source = args.checkpoint.resolve()
    output = args.out.resolve()
    if source == output:
        raise ValueError("Regridded output must differ from the source checkpoint.")
    output.mkdir(parents=True, exist_ok=True)
    overrides = {}
    if args.pseudo_cfl is not None:
        overrides["pseudo_cfl"] = args.pseudo_cfl
    if args.root_inner_tolerance is not None:
        overrides["coupled_root_inner_tolerance"] = args.root_inner_tolerance
    checkpoint = load_coupled_self_similar_checkpoint(
        source,
        continuation_config_overrides=overrides or None,
    )
    regridded = regrid_coupled_self_similar_checkpoint(
        checkpoint,
        args.outer_panels,
        root_inner_iterations=args.root_inner_iterations,
        root_state_recovery=args.root_state_recovery,
        target_far_radius=args.far_radius,
        grid_mode=args.outer_grid_mode,
        root_spacing_ratio=args.root_spacing_ratio,
        far_spacing_ratio=args.far_spacing_ratio,
        endpoint_decay=args.endpoint_decay,
        far_field_panels=args.far_field_panels,
        symmetry_panels=args.symmetry_panels,
        linear_gradient_recovery=args.linear_gradient_recovery,
        linear_corner_treatment=args.linear_corner_treatment,
        linear_far_corner_treatment=args.linear_far_corner_treatment,
        linear_cusp_velocity_recovery=args.linear_cusp_velocity_recovery,
        free_surface_update=args.free_surface_update,
        monitor_residual_weight=args.monitor_residual_weight,
        monitor_curvature_weight=args.monitor_curvature_weight,
        monitor_growth_weight=args.monitor_growth_weight,
        monitor_smoothing_passes=args.monitor_smoothing_passes,
        monitor_maximum_node_shift_panels=(
            args.monitor_maximum_node_shift_panels
        ),
        jet_bie_panel_count=args.jet_bie_panels,
        jet_terminal_closure=args.jet_terminal_closure,
    )
    continuation = solve_coupled_self_similar_wedge_pseudo_time(
        regridded.coupled,
        maximum_iterations=args.additional_iterations,
        root_inner_iterations=args.root_inner_iterations,
    )
    history = coupled_pseudo_time_history_frame(continuation)
    coupled = continuation.coupled
    transformation = {
        "type": "outer_free_surface_arc_length_regrid",
        "source_panel_count": regridded.source_panel_count,
        "target_panel_count": regridded.target_panel_count,
        "source_panel_growth": regridded.source_panel_growth,
        "target_panel_growth": regridded.target_panel_growth,
        "source_far_radius": regridded.source_far_radius,
        "target_far_radius": regridded.target_far_radius,
        "source_grid_mode": regridded.source_grid_mode,
        "target_grid_mode": regridded.target_grid_mode,
        "target_root_spacing_ratio": regridded.target_root_spacing_ratio,
        "target_far_spacing_ratio": regridded.target_far_spacing_ratio,
        "target_endpoint_decay": regridded.target_endpoint_decay,
        "monitor_used": regridded.monitor_used,
        "monitor_residual_weight": regridded.monitor_residual_weight,
        "monitor_curvature_weight": regridded.monitor_curvature_weight,
        "monitor_growth_weight": regridded.monitor_growth_weight,
        "monitor_smoothing_passes": regridded.monitor_smoothing_passes,
        "monitor_maximum_node_shift_panels": (
            regridded.monitor_maximum_node_shift_panels
        ),
        "target_jet_bie_panel_count": regridded.target_jet_bie_panel_count,
        "target_root_inner_tolerance": coupled.config.coupled_root_inner_tolerance,
        "source_jet_terminal_closure": (
            regridded.source_jet_terminal_closure
        ),
        "target_jet_terminal_closure": (
            regridded.target_jet_terminal_closure
        ),
        "target_far_field_panels": regridded.target_far_field_panels,
        "target_symmetry_panels": regridded.target_symmetry_panels,
        "asymptotic_extension_used": regridded.asymptotic_extension_used,
        "source_linear_gradient_recovery": (
            regridded.source_linear_gradient_recovery
        ),
        "target_linear_gradient_recovery": (
            regridded.target_linear_gradient_recovery
        ),
        "source_linear_corner_treatment": (
            regridded.source_linear_corner_treatment
        ),
        "target_linear_corner_treatment": (
            regridded.target_linear_corner_treatment
        ),
        "source_linear_far_corner_treatment": (
            regridded.source_linear_far_corner_treatment
        ),
        "target_linear_far_corner_treatment": (
            regridded.target_linear_far_corner_treatment
        ),
        "source_linear_cusp_velocity_recovery": (
            regridded.source_linear_cusp_velocity_recovery
        ),
        "target_linear_cusp_velocity_recovery": (
            regridded.target_linear_cusp_velocity_recovery
        ),
        "source_free_surface_update": regridded.source_free_surface_update,
        "target_free_surface_update": regridded.target_free_surface_update,
        "source_root_state_recovery": regridded.source_root_state_recovery,
        "target_root_state_recovery": regridded.target_root_state_recovery,
        "production_maintenance_maximum_midpoint_displacement_ratio": (
            regridded.production_maintenance_maximum_midpoint_displacement_ratio
        ),
        "production_maintenance_maximum_node_displacement": (
            regridded.production_maintenance_maximum_node_displacement
        ),
        "post_maintenance_maximum_midpoint_displacement_ratio": (
            regridded.post_maintenance_maximum_midpoint_displacement_ratio
        ),
        "post_maintenance_maximum_node_displacement": (
            regridded.post_maintenance_maximum_node_displacement
        ),
        "geometry_relative_l2": regridded.geometry_relative_l2,
        "geometry_maximum_absolute_error": (
            regridded.geometry_maximum_absolute_error
        ),
        "state_relative_changes": regridded.state_relative_changes,
        "reference_used_during_transformation": False,
    }
    checkpoint_path = str(
        write_coupled_self_similar_checkpoint(
            output,
            coupled,
            history,
            parent=checkpoint,
            transformation=transformation,
        )
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
        "status": "self_similar_coupled_regridded_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "source_checkpoint": {
            "path": str(source),
            "kind": checkpoint.source_kind,
            "source_hashes": checkpoint.source_hashes,
            "continuation_config_overrides": (
                checkpoint.continuation_config_overrides
            ),
        },
        "regrid": transformation,
        "continuation": {
            "requested_iterations": args.additional_iterations,
            "accepted_iterations": len(continuation.time_step_history),
            "termination_reason": continuation.termination_reason,
            "failure_message": continuation.failure_message,
            "pseudo_time": float(history.iloc[-1]["pseudo_time"]),
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
        "checkpoint": checkpoint_path,
    }
    (output / "regrid_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    _plot_resume_diagnostic(output, history, coupled, args.reference_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
