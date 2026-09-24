from __future__ import annotations

import argparse
from dataclasses import asdict, replace
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
    _build_coupled_solution_with_compatible_root,
    derive_shallow_water_jet_root_state_from_coupled,
    evaluate_self_similar_wedge_reference,
    evaluate_self_similar_wedge_scalar_reference,
    solve_coupled_self_similar_wedge_pseudo_time,
)
from scripts.resume_self_similar_wedge import _write_final_artifacts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Continue a converged self-similar wedge state to a nearby deadrise "
            "without reading reference curves during transformation or solve."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--target-deadrise-deg", type=float, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--root-xi-scales",
        type=float,
        nargs="+",
        default=(1.0, 0.98, 0.95, 0.90),
    )
    parser.add_argument("--taper-power", type=float, default=2.0)
    parser.add_argument(
        "--local-wedge-rotation",
        choices=("none", "follow_deadrise"),
        default="none",
        help=(
            "Rotate the root neighborhood about the wedge apex by the "
            "deadrise change and taper that rotation to zero at the far field."
        ),
    )
    parser.add_argument("--condition-number-ratio-limit", type=float, default=10.0)
    parser.add_argument("--additional-iterations", type=int, default=5)
    parser.add_argument("--pseudo-cfl", type=float, default=0.25)
    parser.add_argument("--root-inner-iterations", type=int, default=0)
    parser.add_argument(
        "--skip-reference-metrics",
        action="store_true",
        help=(
            "Write the transformed checkpoint and numerical diagnostics without "
            "opening any distributed or scalar physical-reference file."
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


def _state(coupled: object) -> dict[str, float | int | bool]:
    root = coupled.jet_interface.root_state
    measured = derive_shallow_water_jet_root_state_from_coupled(coupled)
    return {
        "kinematic_rms": float(coupled.kinematic_rms),
        "kinematic_integral": float(coupled.kinematic_integral),
        "kinematic_convergence_integral": float(
            coupled.kinematic_convergence_integral
        ),
        "dipole_coefficient": float(coupled.dipole_coefficient),
        "condition_number": float(coupled.solution.condition_number),
        "root_thickness": float(root.thickness),
        "interface_s_lambda": float(root.s_lambda),
        "measured_s_lambda": float(measured.s_lambda),
        "root_relative_mismatch": float(
            abs(measured.s_lambda - root.s_lambda)
            / max(abs(root.s_lambda), np.finfo(float).eps)
        ),
        "jet_reached_tip": bool(coupled.jet_interface.jet.reached_tip),
        "jet_point_count": int(len(coupled.jet_interface.jet.thickness)),
    }


def _transform_outer_nodes(
    nodes: np.ndarray,
    *,
    root_xi_scale: float,
    taper_power: float,
    local_rotation_deg: float = 0.0,
) -> np.ndarray:
    transformed = np.asarray(nodes, dtype=float).copy()
    panel_length = np.linalg.norm(np.diff(transformed, axis=0), axis=1)
    arc = np.concatenate(([0.0], np.cumsum(panel_length)))
    fraction = arc / arc[-1]
    weight = np.power(1.0 - fraction, float(taper_power))
    angle = np.deg2rad(float(local_rotation_deg)) * weight
    cosine = np.cos(angle)
    sine = np.sin(angle)
    relative_xi = transformed[:, 0].copy()
    relative_eta = transformed[:, 1].copy() + 1.0
    transformed[:, 0] = cosine * relative_xi - sine * relative_eta
    transformed[:, 1] = sine * relative_xi + cosine * relative_eta - 1.0
    transformed[:, 0] += (
        (float(root_xi_scale) - 1.0) * transformed[:, 0] * weight
    )
    transformed[-1] = nodes[-1]
    transformed_panel_length = np.linalg.norm(
        np.diff(transformed, axis=0), axis=1
    )
    if (
        not np.isfinite(transformed).all()
        or np.any(transformed_panel_length <= np.finfo(float).eps)
    ):
        raise ValueError("The deadrise homotopy produced a degenerate outer chain.")
    return transformed


def _post_solve_reference_metrics(
    coupled: object,
    *,
    reference_csv: Path,
    scalar_reference_csv: Path,
    skip: bool,
) -> tuple[dict[str, object], dict[str, object]]:
    if skip:
        skipped = {
            "status": "SKIPPED_BY_REQUEST",
            "used_during_solve": False,
        }
        return dict(skipped), dict(skipped)
    try:
        distributed = asdict(
            evaluate_self_similar_wedge_reference(coupled, reference_csv)
        )
    except (FileNotFoundError, ValueError) as error:
        distributed = {
            "status": "REFERENCE_NOT_AVAILABLE",
            "reason": str(error),
            "used_during_solve": False,
        }
    try:
        scalar = asdict(
            evaluate_self_similar_wedge_scalar_reference(
                coupled, scalar_reference_csv
            )
        )
    except (FileNotFoundError, ValueError) as error:
        scalar = {
            "status": "REFERENCE_NOT_AVAILABLE",
            "reason": str(error),
            "used_during_solve": False,
        }
    return distributed, scalar


def main() -> int:
    args = _parser().parse_args()
    if not 0.0 < args.target_deadrise_deg < 90.0:
        raise ValueError("--target-deadrise-deg must lie in (0, 90).")
    if args.additional_iterations < 0 or args.root_inner_iterations < 0:
        raise ValueError("Iteration counts must be non-negative.")
    if args.taper_power <= 0.0 or args.condition_number_ratio_limit <= 0.0:
        raise ValueError("Taper power and condition-number ratio limit must be positive.")
    if any(value <= 0.0 or not np.isfinite(value) for value in args.root_xi_scales):
        raise ValueError("All root-xi scales must be finite and positive.")

    checkpoint = load_coupled_self_similar_checkpoint(
        args.checkpoint,
        continuation_config_overrides={"pseudo_cfl": args.pseudo_cfl},
    )
    source_angle = float(checkpoint.config.deadrise_deg)
    if np.isclose(source_angle, args.target_deadrise_deg, atol=1.0e-12):
        raise ValueError("The target deadrise must differ from the source checkpoint.")
    target_config = replace(
        checkpoint.config,
        deadrise_deg=float(args.target_deadrise_deg),
        pseudo_cfl=float(args.pseudo_cfl),
    )
    source_nodes = np.column_stack(
        (
            checkpoint.coupled.outer_free_surface.node_xi,
            checkpoint.coupled.outer_free_surface.node_eta,
        )
    )
    source_condition = float(checkpoint.coupled.solution.condition_number)
    local_rotation_deg = (
        float(args.target_deadrise_deg) - source_angle
        if args.local_wedge_rotation == "follow_deadrise"
        else 0.0
    )
    trials: list[dict[str, object]] = []
    candidates: list[tuple[float, float, object, float, dict[str, object]]] = []
    for scale in args.root_xi_scales:
        trial: dict[str, object] = {"root_xi_scale": float(scale)}
        try:
            nodes = _transform_outer_nodes(
                source_nodes,
                root_xi_scale=float(scale),
                taper_power=float(args.taper_power),
                local_rotation_deg=local_rotation_deg,
            )
            adjustments = []
            coupled = _build_coupled_solution_with_compatible_root(
                target_config,
                nodes,
                checkpoint.outer_shape_dipole_coefficient,
                root_inner_iterations=int(args.root_inner_iterations),
                s_lambda_seed=None,
                diagnostic_sink=adjustments,
            )
            state = _state(coupled)
            condition_ratio = float(state["condition_number"]) / source_condition
            trial.update(
                {
                    "status": "PHYSICAL",
                    **state,
                    "condition_number_ratio": condition_ratio,
                    "matching_surface_shift_panels": (
                        adjustments[0].effective_panel_shift if adjustments else 0.0
                    ),
                }
            )
            if float(state["measured_s_lambda"]) <= 0.0:
                trial["status"] = "REJECTED_AUGMENTED_ROOT_DIRECTION"
            elif condition_ratio <= float(args.condition_number_ratio_limit):
                candidates.append(
                    (
                        float(state["kinematic_convergence_integral"]),
                        condition_ratio,
                        coupled,
                        float(scale),
                        trial,
                    )
                )
            else:
                trial["status"] = "REJECTED_CONDITION_NUMBER"
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            trial.update({"status": "REJECTED_PHYSICAL", "reason": str(error)})
        trials.append(trial)

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(trials).to_csv(output / "deadrise_homotopy_trials.csv", index=False)
    if not candidates:
        report = {
            "status": "self_similar_deadrise_homotopy_rejected",
            "validated": False,
            "production_enabled": False,
            "reference_used_during_transformation": False,
            "source_checkpoint": str(Path(args.checkpoint).resolve()),
            "source_deadrise_deg": source_angle,
            "target_deadrise_deg": float(args.target_deadrise_deg),
            "trials": trials,
        }
        (output / "deadrise_homotopy_rejection.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8"
        )
        return 2

    _, _, selected, selected_scale, selected_trial = min(
        candidates, key=lambda item: (item[0], item[1])
    )
    candidate_state = _state(selected)
    continuation = solve_coupled_self_similar_wedge_pseudo_time(
        selected,
        maximum_iterations=int(args.additional_iterations),
        root_inner_iterations=int(args.root_inner_iterations),
    )
    coupled = continuation.coupled
    history = coupled_pseudo_time_history_frame(continuation)
    transformation = {
        "type": "reference_isolated_deadrise_homotopy",
        "source_deadrise_deg": source_angle,
        "target_deadrise_deg": float(args.target_deadrise_deg),
        "root_xi_scale": selected_scale,
        "root_xi_scale_candidates": [float(value) for value in args.root_xi_scales],
        "selection_metric": "minimum_Iafrati_Eq52_kinematic_integral_then_condition",
        "taper_power": float(args.taper_power),
        "local_wedge_rotation": args.local_wedge_rotation,
        "local_rotation_deg": local_rotation_deg,
        "condition_number_ratio_limit": float(args.condition_number_ratio_limit),
        "outer_shape_dipole_coefficient": float(
            checkpoint.outer_shape_dipole_coefficient
        ),
        "reference_used_during_transformation": False,
    }
    checkpoint_path = write_coupled_self_similar_checkpoint(
        output,
        coupled,
        history,
        parent=checkpoint,
        transformation=transformation,
    )
    _write_final_artifacts(output, coupled)
    distributed, scalar = _post_solve_reference_metrics(
        coupled,
        reference_csv=args.reference_csv,
        scalar_reference_csv=args.scalar_reference_csv,
        skip=bool(args.skip_reference_metrics),
    )
    summary = {
        "status": "self_similar_deadrise_homotopy_diagnostic_unvalidated",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "reference_metrics_requested": not bool(args.skip_reference_metrics),
        "source_checkpoint": str(Path(args.checkpoint).resolve()),
        "source_deadrise_deg": source_angle,
        "target_deadrise_deg": float(args.target_deadrise_deg),
        "target_config": asdict(target_config),
        "transformation": transformation,
        "selected_trial": selected_trial,
        "candidate_state": candidate_state,
        "continuation": {
            "requested_iterations": int(args.additional_iterations),
            "accepted_iterations": int(len(continuation.time_step_history)),
            "termination_reason": continuation.termination_reason,
            "failure_message": continuation.failure_message,
            "pseudo_time": float(history.iloc[-1]["pseudo_time"]),
        },
        "final_state": _state(coupled),
        "post_solve_reference_metrics": distributed,
        "post_solve_scalar_reference_metrics": scalar,
        "checkpoint": str(checkpoint_path),
    }
    (output / "deadrise_homotopy_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
