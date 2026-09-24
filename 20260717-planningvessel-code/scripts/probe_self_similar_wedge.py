from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    SelfSimilarWedgeConfig,
    derive_shallow_water_jet_root_state,
    derive_shallow_water_jet_root_state_from_coupled,
    evaluate_self_similar_wedge_reference,
    evaluate_self_similar_wedge_scalar_reference,
    march_shallow_water_jet_from_outer_solution,
    solve_iafrati_dipole_preliminary_iterations,
    solve_self_similar_wedge,
    solve_self_similar_wedge_pseudo_time,
    solve_self_similar_wedge_with_shallow_jet,
    solve_coupled_self_similar_wedge_pseudo_time,
    iterate_shallow_jet_root_coupling,
    truncate_self_similar_wedge_to_shallow_jet,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    coupled_pseudo_time_history_frame,
    write_coupled_self_similar_checkpoint,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the source-based Iafrati self-similar wedge diagnostic."
    )
    parser.add_argument("--deadrise-deg", type=float, default=20.0)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reference-csv", type=Path)
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
    parser.add_argument("--free-panels", type=int, default=36)
    parser.add_argument("--body-panels", type=int, default=24)
    parser.add_argument("--max-nfev", type=int, default=60)
    parser.add_argument(
        "--solver-mode",
        choices=("pseudo_time", "parametric_optimizer"),
        default="pseudo_time",
    )
    parser.add_argument("--preliminary-iterations", type=int, default=8)
    parser.add_argument("--pseudo-max-iterations", type=int, default=100)
    parser.add_argument("--pseudo-cfl", type=float, default=0.20)
    parser.add_argument("--jet-angle-threshold-deg", type=float, default=10.0)
    parser.add_argument("--root-inner-iterations", type=int, default=12)
    parser.add_argument("--root-inner-relaxation", type=float, default=0.5)
    parser.add_argument("--root-inner-tolerance", type=float, default=1.0e-3)
    parser.add_argument("--coupled-pseudo-iterations", type=int, default=0)
    parser.add_argument("--enable-coupled-root-reconstruction", action="store_true")
    parser.add_argument("--coupled-root-reconstruction-panels", type=int, default=12)
    parser.add_argument("--coupled-root-reconstruction-added-panels", type=int, default=24)
    parser.add_argument(
        "--coupled-element-interpolation",
        choices=("constant_panel", "linear_node"),
        default="constant_panel",
    )
    parser.add_argument(
        "--coupled-linear-gradient-recovery",
        choices=("element", "connected_nodal"),
        default="element",
    )
    parser.add_argument(
        "--coupled-free-surface-update",
        choices=("full_gradient", "continuous_normal"),
        default="full_gradient",
    )
    parser.add_argument("--enable-coupled-root-smoothing", action="store_true")
    parser.add_argument("--coupled-smoothing-root-panels", type=int, default=12)
    parser.add_argument(
        "--jet-closure",
        choices=("body_root", "truncated_control"),
        default="body_root",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.root_inner_iterations < 0:
        raise ValueError("--root-inner-iterations must be non-negative.")
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = SelfSimilarWedgeConfig(
        deadrise_deg=args.deadrise_deg,
        free_surface_panels=args.free_panels,
        body_panels=args.body_panels,
        max_nfev=args.max_nfev,
        jet_closure=args.jet_closure,
        preliminary_iterations=args.preliminary_iterations,
        pseudo_max_iterations=args.pseudo_max_iterations,
        pseudo_cfl=args.pseudo_cfl,
        jet_angle_threshold_deg=args.jet_angle_threshold_deg,
        coupled_root_inner_relaxation=args.root_inner_relaxation,
        coupled_root_inner_tolerance=args.root_inner_tolerance,
        coupled_root_reconstruction_enabled=(
            args.enable_coupled_root_reconstruction
        ),
        coupled_root_reconstruction_panels=(
            args.coupled_root_reconstruction_panels
        ),
        coupled_root_reconstruction_added_panels=(
            args.coupled_root_reconstruction_added_panels
        ),
        coupled_element_interpolation=args.coupled_element_interpolation,
        coupled_linear_gradient_recovery=args.coupled_linear_gradient_recovery,
        coupled_free_surface_update=args.coupled_free_surface_update,
        coupled_smoothing_enabled=args.enable_coupled_root_smoothing,
        coupled_smoothing_root_panels=args.coupled_smoothing_root_panels,
    )
    preliminary = None
    if args.solver_mode == "pseudo_time":
        if config.jet_closure != "body_root":
            raise ValueError("pseudo_time mode requires --jet-closure body_root.")
        preliminary = solve_iafrati_dipole_preliminary_iterations(config)
        result = solve_self_similar_wedge_pseudo_time(
            config,
            initial_bvp=preliminary.bvp,
        )
    else:
        result = solve_self_similar_wedge(config)
    bvp = result.bvp
    labels = np.asarray(bvp.boundary.panel_labels, dtype=object)
    body_mask = labels == "body"

    pd.DataFrame(
        {
            "xi": bvp.boundary.node_y_m,
            "eta": bvp.boundary.node_z_up_m,
            "node_index": np.arange(len(bvp.boundary.node_y_m)),
        }
    ).to_csv(output / "boundary_nodes.csv", index=False)
    pd.DataFrame(
        {
            "xi": bvp.free_surface.node_xi,
            "eta": bvp.free_surface.node_eta,
            "arc_length": bvp.free_surface.arc_length,
        }
    ).to_csv(output / "free_surface.csv", index=False)
    pd.DataFrame(
        {
            "eta": bvp.boundary.panel_mid_z_up_m[body_mask],
            "xi": bvp.boundary.panel_mid_y_m[body_mask],
            "pressure_coefficient": bvp.body_pressure_coefficient,
        }
    ).to_csv(output / "body_pressure.csv", index=False)
    pd.DataFrame(
        {
            "panel_index": np.arange(config.free_surface_panels),
            "kinematic_residual": bvp.kinematic_residual,
            "scaled_kinematic_residual": bvp.scaled_kinematic_residual,
        }
    ).to_csv(output / "kinematic_residual.csv", index=False)

    summary: dict[str, object] = {
        "status": result.status,
        "solver_mode": args.solver_mode,
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "config": asdict(config),
        "final_kinematic_rms": bvp.kinematic_rms,
        "bem_relative_residual": bvp.solution.relative_residual,
        "bem_condition_number": bvp.solution.condition_number,
        "flux_residual": bvp.flux_residual,
        "dipole_coefficient": bvp.dipole_coefficient,
        "tau_star": bvp.free_surface.tau_star,
        "root_xi": float(bvp.free_surface.node_xi[0]),
        "root_eta": float(bvp.free_surface.node_eta[0]),
        "jet_control_normal_derivative": bvp.jet_control_normal_derivative,
        "body_vertical_force_coefficient": bvp.body_vertical_force_coefficient,
    }
    coupled_result = None
    if args.solver_mode == "pseudo_time":
        assert preliminary is not None
        summary["preliminary_iteration"] = {
            "status": preliminary.status,
            "converged": preliminary.converged,
            "iteration_count": len(preliminary.dipole_coefficient_history),
            "initial_dipole_coefficient": float(
                preliminary.dipole_coefficient_history[0]
            ),
            "final_shape_dipole_coefficient": float(
                preliminary.dipole_coefficient_history[-1]
            ),
            "final_solved_dipole_coefficient": preliminary.bvp.dipole_coefficient,
            "final_relative_change": float(preliminary.relative_change_history[-1]),
        }
        summary["pseudo_time"] = {
            "status": result.status,
            "converged": result.converged,
            "termination_reason": result.termination_reason,
            "failure_message": result.failure_message,
            "step_count": len(result.time_step_history),
            "final_pseudo_time": float(result.pseudo_time_history[-1]),
            "maximum_displacement_ratio": float(
                np.max(result.maximum_displacement_ratio_history, initial=0.0)
            ),
            "initial_root_angle_deg": float(result.root_angle_deg_history[0]),
            "final_root_angle_deg": float(result.root_angle_deg_history[-1]),
        }
        pd.DataFrame(
            {
                "iteration": np.arange(len(preliminary.dipole_coefficient_history)),
                "shape_dipole_coefficient": preliminary.dipole_coefficient_history,
                "relative_change": preliminary.relative_change_history,
            }
        ).to_csv(output / "preliminary_dipole_history.csv", index=False)
        state_count = len(result.pseudo_time_history)
        pd.DataFrame(
            {
                "iteration": np.arange(state_count),
                "pseudo_time": result.pseudo_time_history,
                "kinematic_rms": result.kinematic_rms_history,
                "dipole_coefficient": result.dipole_coefficient_history,
                "root_angle_deg": result.root_angle_deg_history,
                "accepted_time_step": np.concatenate(
                    ([np.nan], result.time_step_history)
                ),
                "maximum_displacement_ratio": np.concatenate(
                    ([np.nan], result.maximum_displacement_ratio_history)
                ),
            }
        ).to_csv(output / "pseudo_time_history.csv", index=False)
    else:
        summary.update(
            {
                "optimizer_success": result.optimizer_success,
                "optimizer_message": result.optimizer_message,
                "optimizer_function_evaluations": result.optimizer_function_evaluations,
                "initial_kinematic_rms": result.initial_kinematic_rms,
            }
        )
    if config.jet_closure == "truncated_control":
        root_state = derive_shallow_water_jet_root_state(
            bvp, deadrise_deg=config.deadrise_deg
        )
        summary["shallow_water_root_state"] = {
            "thickness": root_state.thickness,
            "s_lambda": root_state.s_lambda,
            "s_tau": root_state.s_tau,
            "delta_lambda": root_state.delta_lambda,
            "lambda_tangent": root_state.lambda_tangent.tolist(),
        }
        try:
            jet = march_shallow_water_jet_from_outer_solution(
                bvp, deadrise_deg=config.deadrise_deg
            )
        except ValueError as error:
            summary["shallow_water_coupling"] = {
                "status": "NOT_ELIGIBLE",
                "reason": str(error),
            }
        else:
            summary["shallow_water_coupling"] = {
                "status": "DIAGNOSTIC_COMPLETED",
                "reached_tip": jet.reached_tip,
                "point_count": len(jet.thickness),
            }
            pd.DataFrame(
                {
                    "lambda": jet.lambda_coordinate,
                    "thickness": jet.thickness,
                    "s_lambda": jet.s_lambda,
                    "s_tau": jet.s_tau,
                    "subiterations": jet.subiterations,
                }
            ).to_csv(output / "shallow_water_jet.csv", index=False)
    else:
        if (
            args.solver_mode == "pseudo_time"
            and result.termination_reason == "JET_MODEL_REQUIRED"
        ):
            try:
                truncation = truncate_self_similar_wedge_to_shallow_jet(
                    config,
                    result,
                )
            except ValueError as error:
                summary["shallow_water_coupling"] = {
                    "status": "NOT_ELIGIBLE",
                    "reason": str(error),
                }
            else:
                coupling_summary: dict[str, object] = {
                    "status": "ROOT_AND_SPACE_MARCH_COMPLETED",
                    "source_status": truncation.status,
                    "original_cut_node_index": truncation.original_cut_node_index,
                    "cut_angle_deg": truncation.cut_angle_deg,
                    "root_thickness": truncation.root_state.thickness,
                    "root_s_lambda": truncation.root_state.s_lambda,
                    "root_s_tau": truncation.root_state.s_tau,
                    "delta_lambda": truncation.root_state.delta_lambda,
                    "point_count": len(truncation.jet.thickness),
                    "reached_tip": truncation.jet.reached_tip,
                    "tip_thickness": float(truncation.jet.thickness[-1]),
                    "outer_bem_relative_residual": (
                        truncation.bvp.solution.relative_residual
                    ),
                }
                pd.DataFrame(
                    {
                        "lambda": truncation.jet.lambda_coordinate,
                        "thickness": truncation.jet.thickness,
                        "s_lambda": truncation.jet.s_lambda,
                        "s_tau": truncation.jet.s_tau,
                        "subiterations": truncation.jet.subiterations,
                        "body_xi": truncation.body_node_xi,
                        "body_eta": truncation.body_node_eta,
                        "free_xi": truncation.free_node_xi,
                        "free_eta": truncation.free_node_eta,
                    }
                ).to_csv(output / "shallow_water_jet.csv", index=False)
                try:
                    coupled = solve_self_similar_wedge_with_shallow_jet(truncation)
                except ValueError as error:
                    coupling_summary["augmented_bie"] = {
                        "status": "NOT_ELIGIBLE",
                        "reason": str(error),
                    }
                else:
                    root_iteration = None
                    coupled_pseudo = None
                    if args.root_inner_iterations > 0:
                        root_iteration = iterate_shallow_jet_root_coupling(
                            coupled,
                            maximum_iterations=args.root_inner_iterations,
                            relative_tolerance=args.root_inner_tolerance,
                            relaxation=args.root_inner_relaxation,
                        )
                        coupled = root_iteration.coupled
                    if args.coupled_pseudo_iterations > 0:
                        coupled_pseudo = solve_coupled_self_similar_wedge_pseudo_time(
                            coupled,
                            maximum_iterations=args.coupled_pseudo_iterations,
                            root_inner_iterations=args.root_inner_iterations,
                        )
                        coupled = coupled_pseudo.coupled
                        coupling_summary["coupled_pseudo_time"] = {
                            "status": coupled_pseudo.status,
                            "converged": coupled_pseudo.converged,
                            "termination_reason": (
                                coupled_pseudo.termination_reason
                            ),
                            "failure_message": coupled_pseudo.failure_message,
                            "iteration_count": len(
                                coupled_pseudo.time_step_history
                            ),
                            "initial_kinematic_rms": float(
                                coupled_pseudo.kinematic_rms_history[0]
                            ),
                            "final_kinematic_rms": float(
                                coupled_pseudo.kinematic_rms_history[-1]
                            ),
                            "initial_dipole_coefficient": float(
                                coupled_pseudo.dipole_coefficient_history[0]
                            ),
                            "final_dipole_coefficient": float(
                                coupled_pseudo.dipole_coefficient_history[-1]
                            ),
                        }
                        coupled_history = coupled_pseudo_time_history_frame(
                            coupled_pseudo
                        )
                        if len(coupled_history) >= 2:
                            checkpoint_path = write_coupled_self_similar_checkpoint(
                                output,
                                coupled,
                                coupled_history,
                            )
                            coupling_summary["checkpoint"] = {
                                "status": "WRITTEN",
                                "path": str(checkpoint_path),
                            }
                        else:
                            coupling_summary["checkpoint"] = {
                                "status": "NOT_WRITTEN",
                                "reason": "No coupled pseudo-time step was accepted.",
                            }
                    coupled_result = coupled
                    if root_iteration is None:
                        coupling_summary["status"] = (
                            "SOURCE_ROOT_AUGMENTED_BIE_COMPLETED_OUTER_PSEUDO_ITERATION_PENDING"
                        )
                        coupling_summary["root_inner_iteration"] = {
                            "status": "NOT_RUN",
                            "reason": "Disabled by --root-inner-iterations 0.",
                        }
                    else:
                        coupling_summary["status"] = (
                            "ROOT_CONSISTENT_AUGMENTED_BIE_COMPLETED_OUTER_PSEUDO_ITERATION_PENDING"
                            if root_iteration.converged
                            else "ROOT_INNER_ITERATION_NOT_CONVERGED"
                        )
                        coupling_summary["root_inner_iteration"] = {
                            "status": root_iteration.status,
                            "converged": root_iteration.converged,
                            "termination_reason": root_iteration.termination_reason,
                            "iteration_count": len(root_iteration.s_lambda_history) - 1,
                            "initial_s_lambda": float(
                                root_iteration.s_lambda_history[0]
                            ),
                            "final_s_lambda": float(
                                root_iteration.s_lambda_history[-1]
                            ),
                            "final_relative_change": float(
                                root_iteration.relative_change_history[-1]
                            ),
                            "final_relative_mismatch": float(
                                root_iteration.relative_mismatch_history[-1]
                            ),
                        }
                        pd.DataFrame(
                            {
                                "iteration": np.arange(
                                    len(root_iteration.s_lambda_history)
                                ),
                                "s_lambda": root_iteration.s_lambda_history,
                                "measured_s_lambda": (
                                    root_iteration.measured_s_lambda_history
                                ),
                                "relative_mismatch": (
                                    root_iteration.relative_mismatch_history
                                ),
                                "relative_change": (
                                    root_iteration.relative_change_history
                                ),
                            }
                        ).to_csv(output / "root_inner_iteration.csv", index=False)
                    coupling_summary["augmented_bie"] = {
                        "status": coupled.solution.status,
                        "panel_count": coupled.boundary.panel_count,
                        "relative_residual": coupled.solution.relative_residual,
                        "condition_number": coupled.solution.condition_number,
                        "flux_residual": coupled.flux_residual,
                        "dipole_coefficient": coupled.dipole_coefficient,
                        "outer_kinematic_rms": coupled.kinematic_rms,
                        "body_pressure_min": float(
                            np.min(coupled.body_pressure_coefficient)
                        ),
                        "body_pressure_max": float(
                            np.max(coupled.body_pressure_coefficient)
                        ),
                        "body_vertical_force_coefficient": (
                            coupled.body_vertical_force_coefficient
                        ),
                        "validated": False,
                        "remaining_requirement": (
                            "Continue pseudo-time with the coupled outer/jet BIE "
                            "until the kinematic condition and pressure benchmarks converge."
                        ),
                    }
                    final_root = coupled.jet_interface.root_state
                    final_free_root = np.asarray(
                        [
                            coupled.outer_free_surface.node_xi[0],
                            coupled.outer_free_surface.node_eta[0],
                        ]
                    )
                    coupling_summary["final_root_state"] = {
                        "thickness": final_root.thickness,
                        "s_lambda": final_root.s_lambda,
                        "s_tau": final_root.s_tau,
                        "delta_lambda": final_root.delta_lambda,
                        "cut_angle_deg": coupled.jet_interface.cut_angle_deg,
                        "free_root_xi": float(final_free_root[0]),
                        "free_root_eta": float(final_free_root[1]),
                        "body_root_eta": float(
                            -1.0
                            + np.dot(
                                final_free_root - np.asarray([0.0, -1.0]),
                                np.asarray(
                                    [
                                        np.cos(np.deg2rad(config.deadrise_deg)),
                                        np.sin(np.deg2rad(config.deadrise_deg)),
                                    ]
                                ),
                            )
                            * np.sin(np.deg2rad(config.deadrise_deg))
                        ),
                        "thickness_panel_ratio": float(
                            coupled_pseudo.root_resolution_ratio_history[-1]
                            if coupled_pseudo is not None
                            else final_root.thickness
                            / np.diff(coupled.outer_free_surface.arc_length)[0]
                        ),
                    }
                    measured_root = derive_shallow_water_jet_root_state_from_coupled(
                        coupled
                    )
                    coupling_summary["final_measured_root_state"] = {
                        "thickness": measured_root.thickness,
                        "s_lambda": measured_root.s_lambda,
                        "s_tau": measured_root.s_tau,
                        "delta_lambda": measured_root.delta_lambda,
                        "interface_s_lambda": final_root.s_lambda,
                        "relative_s_lambda_mismatch": (
                            abs(measured_root.s_lambda - final_root.s_lambda)
                            / max(abs(final_root.s_lambda), np.finfo(float).eps)
                        ),
                    }
                    final_jet = coupled.jet_interface.jet
                    pd.DataFrame(
                        {
                            "lambda": final_jet.lambda_coordinate,
                            "thickness": final_jet.thickness,
                            "s_lambda": final_jet.s_lambda,
                            "s_tau": final_jet.s_tau,
                            "subiterations": final_jet.subiterations,
                            "body_xi": coupled.jet_interface.body_node_xi,
                            "body_eta": coupled.jet_interface.body_node_eta,
                            "free_xi": coupled.jet_interface.free_node_xi,
                            "free_eta": coupled.jet_interface.free_node_eta,
                        }
                    ).to_csv(output / "coupled_shallow_water_jet.csv", index=False)
                    coupled_labels = np.asarray(
                        coupled.boundary.panel_labels,
                        dtype=object,
                    )
                    coupled_body = (coupled_labels == "body") | (
                        coupled_labels == "shallow_jet_body"
                    )
                    pd.DataFrame(
                        {
                            "xi": coupled.boundary.node_y_m,
                            "eta": coupled.boundary.node_z_up_m,
                            "node_index": np.arange(
                                len(coupled.boundary.node_y_m)
                            ),
                        }
                    ).to_csv(output / "coupled_boundary_nodes.csv", index=False)
                    pd.DataFrame(
                        {
                            "eta": coupled.boundary.panel_mid_z_up_m[coupled_body],
                            "xi": coupled.boundary.panel_mid_y_m[coupled_body],
                            "pressure_coefficient": (
                                coupled.body_pressure_coefficient
                            ),
                            "potential": (
                                coupled.solution.potential_m2_s[coupled_body]
                            ),
                            "normal_derivative": (
                                coupled.solution.normal_derivative_m_s[coupled_body]
                            ),
                            "segment": coupled_labels[coupled_body],
                        }
                    ).to_csv(output / "coupled_body_pressure.csv", index=False)
                summary["shallow_water_coupling"] = coupling_summary
        else:
            summary["shallow_water_coupling"] = {
                "status": "NOT_APPLICABLE",
                "reason": "body_root closure has not reached the source jet interface.",
            }
    if args.reference_csv is not None:
        reference_metrics = evaluate_self_similar_wedge_reference(result, args.reference_csv)
        summary["post_solve_reference_metrics"] = asdict(reference_metrics)
        summary["distributed_reference"] = {
            "path": str(args.reference_csv.resolve()),
            "sha256": hashlib.sha256(args.reference_csv.read_bytes()).hexdigest(),
            "used_during_solve": False,
        }
        if coupled_result is not None:
            summary["post_solve_coupled_reference_metrics"] = asdict(
                evaluate_self_similar_wedge_reference(
                    coupled_result,
                    args.reference_csv,
                )
            )
    if args.scalar_reference_csv is not None:
        scalar_metrics = evaluate_self_similar_wedge_scalar_reference(
            result, args.scalar_reference_csv
        )
        summary["post_solve_scalar_reference_metrics"] = asdict(scalar_metrics)
        summary["scalar_reference"] = {
            "path": str(args.scalar_reference_csv.resolve()),
            "sha256": hashlib.sha256(args.scalar_reference_csv.read_bytes()).hexdigest(),
            "used_during_solve": False,
        }
        if coupled_result is not None:
            summary["post_solve_coupled_scalar_reference_metrics"] = asdict(
                evaluate_self_similar_wedge_scalar_reference(
                    coupled_result,
                    args.scalar_reference_csv,
                )
            )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 3, figsize=(14.0, 4.2))
    axes[0].plot(bvp.boundary.node_y_m, bvp.boundary.node_z_up_m, "k-", lw=0.8)
    axes[0].plot(bvp.free_surface.node_xi, bvp.free_surface.node_eta, "C0.-", ms=3)
    axes[0].set_aspect("equal", adjustable="box")
    axes[0].set_xlim(0.0, min(config.far_radius, 11.0))
    axes[0].set_ylim(-1.2, 2.2)
    axes[0].set_xlabel(r"$\xi$")
    axes[0].set_ylabel(r"$\eta$")
    axes[0].set_title("Similarity boundary")

    axes[1].plot(
        bvp.boundary.panel_mid_z_up_m[body_mask],
        bvp.body_pressure_coefficient,
        "C1-",
        label="computed",
    )
    axes[1].set_xlabel(r"body $\eta$")
    axes[1].set_ylabel(r"$C_p$")
    axes[1].set_title("Body pressure")
    axes[1].legend()

    axes[2].plot(bvp.scaled_kinematic_residual, "C2-")
    axes[2].axhline(0.0, color="0.4", lw=0.8)
    axes[2].set_xlabel("free-surface panel")
    axes[2].set_ylabel(r"scaled $S_n$")
    axes[2].set_title("Kinematic residual")
    figure.suptitle(
        f"Iafrati outer-flow diagnostic ({config.jet_closure}), "
        f"beta={config.deadrise_deg:g} deg; "
        f"RMS={bvp.kinematic_rms:.4g}"
    )
    figure.tight_layout()
    figure.savefig(output / "self_similar_wedge_diagnostic.png", dpi=180)
    plt.close(figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
