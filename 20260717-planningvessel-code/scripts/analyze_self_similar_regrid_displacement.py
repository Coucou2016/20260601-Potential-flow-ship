from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    load_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    SelfSimilarGeometryMaintenanceAdjustment,
    _advance_coupled_self_similar_wedge_pseudo_time_rk2_with_diagnostics,
    derive_shallow_water_jet_root_state_from_coupled,
)


def _geometry_metrics(
    prefix: str,
    adjustment: SelfSimilarGeometryMaintenanceAdjustment,
) -> dict[str, float]:
    raw = float(adjustment.raw_normal_velocity_integral)
    denominator = max(raw, np.finfo(float).eps)
    return {
        f"{prefix}_raw_normal_velocity_integral": raw,
        f"{prefix}_maintenance_normal_velocity_integral": float(
            adjustment.normal_velocity_integral
        ),
        f"{prefix}_maintenance_tangential_velocity_integral": float(
            adjustment.tangential_velocity_integral
        ),
        f"{prefix}_net_normal_velocity_integral": float(
            adjustment.net_normal_velocity_integral
        ),
        f"{prefix}_maintenance_to_raw_normal_ratio": float(
            adjustment.normal_velocity_integral / denominator
        ),
        f"{prefix}_net_to_raw_normal_ratio": float(
            adjustment.net_normal_velocity_integral / denominator
        ),
        f"{prefix}_normal_velocity_correlation": float(
            adjustment.normal_velocity_correlation
        ),
        f"{prefix}_normal_cancellation_fraction": float(
            adjustment.normal_cancellation_fraction
        ),
        f"{prefix}_maximum_normal_displacement_ratio": float(
            adjustment.maximum_normal_displacement_ratio
        ),
    }


def _correlation(first: np.ndarray, second: np.ndarray) -> float | None:
    if len(first) < 2 or np.ptp(first) <= np.finfo(float).eps:
        return None
    if np.ptp(second) <= np.finfo(float).eps:
        return None
    return float(np.corrcoef(first, second)[0, 1])


def _root_relative_mismatch(coupled: object) -> float:
    supplied = float(coupled.jet_interface.root_state.s_lambda)
    measured = float(
        derive_shallow_water_jet_root_state_from_coupled(coupled).s_lambda
    )
    return abs(measured - supplied) / max(
        abs(supplied),
        np.finfo(float).eps,
    )


def audit_regrid_displacement(
    checkpoint_path: Path,
    *,
    steps: int,
    root_inner_iterations: int,
) -> tuple[dict[str, object], list[dict[str, float | int]]]:
    if int(steps) < 1:
        raise ValueError("steps must be at least one.")
    if int(root_inner_iterations) < 0:
        raise ValueError("root_inner_iterations must be non-negative.")

    checkpoint = load_coupled_self_similar_checkpoint(checkpoint_path)
    coupled = checkpoint.coupled
    initial_integral = float(coupled.kinematic_integral_linear_exact)
    records: list[dict[str, float | int]] = []
    last_diagnostics = None

    for iteration in range(1, int(steps) + 1):
        before_integral = float(coupled.kinematic_integral_linear_exact)
        before_dipole = float(coupled.dipole_coefficient)
        before_root_mismatch = _root_relative_mismatch(coupled)
        advanced, time_step, raw_ratio, diagnostics = (
            _advance_coupled_self_similar_wedge_pseudo_time_rk2_with_diagnostics(
                coupled,
                root_inner_iterations=int(root_inner_iterations),
            )
        )
        after_integral = float(advanced.kinematic_integral_linear_exact)
        record: dict[str, float | int] = {
            "iteration": iteration,
            "accepted_time_step": float(time_step),
            "maximum_raw_displacement_ratio": float(raw_ratio),
            "kinematic_integral_before": before_integral,
            "kinematic_integral_after": after_integral,
            "kinematic_integral_change": after_integral - before_integral,
            "kinematic_integral_ratio_after_before": (
                after_integral / before_integral
            ),
            "dipole_coefficient_before": before_dipole,
            "dipole_coefficient_after": float(advanced.dipole_coefficient),
            "root_relative_mismatch_before": before_root_mismatch,
            "root_relative_mismatch_after": _root_relative_mismatch(advanced),
            "rk2_rejected_attempt_count": int(diagnostics.rejected_attempt_count),
            "provisional_matching_surface_shift_panels": float(
                diagnostics.provisional.effective_panel_shift
            ),
            "final_matching_surface_shift_panels": float(
                diagnostics.final.effective_panel_shift
            ),
        }
        record.update(
            _geometry_metrics(
                "provisional",
                diagnostics.provisional_geometry_maintenance,
            )
        )
        record.update(
            _geometry_metrics("final", diagnostics.final_geometry_maintenance)
        )
        records.append(record)
        coupled = advanced
        last_diagnostics = diagnostics

    final_integral = float(coupled.kinematic_integral_linear_exact)
    changes = np.asarray(
        [float(item["kinematic_integral_change"]) for item in records]
    )
    cancellation = np.asarray(
        [float(item["final_normal_cancellation_fraction"]) for item in records]
    )
    maintenance_ratio = np.asarray(
        [float(item["final_maintenance_to_raw_normal_ratio"]) for item in records]
    )
    net_ratio = np.asarray(
        [float(item["final_net_to_raw_normal_ratio"]) for item in records]
    )
    payload: dict[str, object] = {
        "status": "diagnostic_only_solver_behavior_unchanged",
        "source_checkpoint": str(checkpoint_path.resolve()),
        "completed_iterations_before_replay": checkpoint.completed_iterations,
        "cumulative_pseudo_time_before_replay": checkpoint.cumulative_pseudo_time,
        "steps_requested": int(steps),
        "steps_completed": len(records),
        "root_inner_iterations": int(root_inner_iterations),
        "kinematic_integral_initial": initial_integral,
        "kinematic_integral_final": final_integral,
        "kinematic_integral_minimum": float(
            min([initial_integral, *(float(item["kinematic_integral_after"]) for item in records)])
        ),
        "kinematic_integral_final_to_initial_ratio": final_integral
        / initial_integral,
        "final_maintenance_to_raw_normal_ratio_median": float(
            np.median(maintenance_ratio)
        ),
        "final_maintenance_to_raw_normal_ratio_maximum": float(
            np.max(maintenance_ratio)
        ),
        "final_net_to_raw_normal_ratio_median": float(np.median(net_ratio)),
        "final_normal_cancellation_fraction_median": float(
            np.median(cancellation)
        ),
        "kinematic_change_cancellation_correlation": _correlation(
            changes,
            cancellation,
        ),
        "reference_used_during_audit": False,
        "last_step_diagnostics": (
            None if last_diagnostics is None else asdict(last_diagnostics)
        ),
    }
    return payload, records


def _write_history(path: Path, records: list[dict[str, float | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit normal/tangential geometry motion injected by repeated accepted "
            "coupled self-similar RK2 regrid steps."
        )
    )
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--history-out", type=Path)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--root-inner-iterations", type=int, default=8)
    args = parser.parse_args()

    payload, records = audit_regrid_displacement(
        args.checkpoint,
        steps=args.steps,
        root_inner_iterations=args.root_inner_iterations,
    )
    history_path = (
        args.history_out
        if args.history_out is not None
        else args.out.with_name(f"{args.out.stem}_history.csv")
    )
    _write_history(history_path, records)
    payload["history_csv"] = str(history_path.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
