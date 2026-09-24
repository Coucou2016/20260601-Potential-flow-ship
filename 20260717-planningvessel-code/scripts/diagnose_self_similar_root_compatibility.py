from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    SelfSimilarWedgeConfig,
    _build_coupled_solution_from_outer_nodes,
    _project_root_to_wedge,
    _regrid_coupled_outer_nodes,
    build_self_similar_free_surface_from_nodes,
    derive_shallow_water_jet_root_state_from_coupled,
    iterate_shallow_jet_root_coupling,
    solve_self_similar_wedge_bvp_for_free_surface,
    truncate_self_similar_wedge_to_shallow_jet,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct a saved body-root wedge state and audit whether moving "
            "the numerical outer/shallow-jet matching surface creates a "
            "root-consistent augmented-BIE solution."
        )
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--maximum-panel-shifts", type=int, default=12)
    parser.add_argument("--minimum-panel-shift", type=float, default=0.0)
    parser.add_argument("--fractional-subdivisions", type=int, default=1)
    parser.add_argument("--root-inner-iterations", type=int, default=12)
    parser.add_argument("--root-inner-relaxation", type=float, default=0.5)
    parser.add_argument("--root-inner-tolerance", type=float, default=1.0e-3)
    parser.add_argument(
        "--root-state-recovery",
        choices=("first_panel_midpoint", "quadratic_root_extrapolation"),
        default=None,
    )
    parser.add_argument("--jet-bie-panels", type=int, default=None)
    parser.add_argument(
        "--terminal-closure",
        choices=("legacy_parity", "continuous_tip"),
        default=None,
    )
    parser.add_argument(
        "--corner-treatment",
        choices=("shared_node", "displaced_double_node"),
        default=None,
    )
    parser.add_argument(
        "--linear-gradient-recovery",
        choices=("element", "connected_nodal"),
        default=None,
    )
    parser.add_argument(
        "--element-interpolation",
        choices=("constant_panel", "linear_node"),
        default=None,
    )
    parser.add_argument(
        "--cusp-velocity-recovery",
        choices=("connected_average", "split_average", "split_outer_side"),
        default=None,
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if (
        args.maximum_panel_shifts < 0
        or args.minimum_panel_shift < 0.0
        or args.minimum_panel_shift > args.maximum_panel_shifts
        or args.fractional_subdivisions < 1
        or args.root_inner_iterations < 1
    ):
        raise ValueError(
            "Panel shifts must be non-negative; subdivisions and root iterations "
            "must be positive."
        )

    source = args.source.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(source / "free_surface.csv")
    config_values = dict(summary["config"])
    config_values["coupled_root_inner_relaxation"] = float(
        args.root_inner_relaxation
    )
    config_values["coupled_root_inner_tolerance"] = float(
        args.root_inner_tolerance
    )
    if args.root_state_recovery is not None:
        config_values["coupled_root_state_recovery"] = args.root_state_recovery
    if args.jet_bie_panels is not None:
        config_values["coupled_jet_bie_panel_count"] = int(args.jet_bie_panels)
    if args.terminal_closure is not None:
        config_values["coupled_jet_terminal_closure"] = args.terminal_closure
    if args.corner_treatment is not None:
        config_values["coupled_linear_corner_treatment"] = args.corner_treatment
    if args.linear_gradient_recovery is not None:
        config_values["coupled_linear_gradient_recovery"] = (
            args.linear_gradient_recovery
        )
    if args.element_interpolation is not None:
        config_values["coupled_element_interpolation"] = args.element_interpolation
    if args.cusp_velocity_recovery is not None:
        config_values["coupled_linear_cusp_velocity_recovery"] = (
            args.cusp_velocity_recovery
        )
    source_config = SelfSimilarWedgeConfig(**config_values)
    surface = build_self_similar_free_surface_from_nodes(
        source_config,
        frame["xi"].to_numpy(dtype=float),
        frame["eta"].to_numpy(dtype=float),
        far_dipole_coefficient=float(summary["dipole_coefficient"]),
    )
    bvp = solve_self_similar_wedge_bvp_for_free_surface(source_config, surface)
    pseudo = SimpleNamespace(termination_reason="JET_MODEL_REQUIRED", bvp=bvp)
    truncation = truncate_self_similar_wedge_to_shallow_jet(source_config, pseudo)

    candidate = np.column_stack(
        (
            truncation.bvp.free_surface.node_xi,
            truncation.bvp.free_surface.node_eta,
        )
    )
    rows: list[dict[str, object]] = []
    accepted = None

    def evaluate_candidate(
        trial_nodes: np.ndarray,
        effective_shift: float,
    ) -> object | None:
        row: dict[str, object] = {
            "panel_shift": effective_shift,
            "outer_root_xi": float(trial_nodes[0, 0]),
            "outer_root_eta": float(trial_nodes[0, 1]),
            "outer_panel_count": len(trial_nodes) - 1,
        }
        result = None
        try:
            initial = _build_coupled_solution_from_outer_nodes(
                truncation.config,
                trial_nodes,
                bvp.dipole_coefficient,
                root_inner_iterations=0,
                s_lambda_seed=None,
            )
            iteration = iterate_shallow_jet_root_coupling(
                initial,
                maximum_iterations=int(args.root_inner_iterations),
                relative_tolerance=float(args.root_inner_tolerance),
                relaxation=float(args.root_inner_relaxation),
            )
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            row.update(
                {
                    "status": "INELIGIBLE",
                    "reason": str(error),
                }
            )
        else:
            measured = derive_shallow_water_jet_root_state_from_coupled(
                iteration.coupled
            )
            labels = np.asarray(iteration.coupled.boundary.panel_labels, dtype=object)
            root_panels = np.flatnonzero(labels == "shallow_jet_body")[:3]
            beta = np.deg2rad(iteration.coupled.config.deadrise_deg)
            tangent = np.asarray([np.cos(beta), np.sin(beta)])
            free_root = np.asarray(
                [
                    iteration.coupled.outer_free_surface.node_xi[0],
                    iteration.coupled.outer_free_surface.node_eta[0],
                ]
            )
            body_root = _project_root_to_wedge(free_root, beta)
            root_position = np.column_stack(
                (
                    iteration.coupled.boundary.panel_mid_y_m[root_panels],
                    iteration.coupled.boundary.panel_mid_z_up_m[root_panels],
                )
            )
            root_distance = (root_position - body_root) @ tangent
            panel_s_lambda = np.sum(
                (
                    iteration.coupled.panel_velocity[root_panels]
                    - root_position
                )
                * tangent[None, :],
                axis=1,
            )
            row.update(
                {
                    "status": (
                        "ROOT_CONSISTENT" if iteration.converged else "ROOT_NOT_CONSISTENT"
                    ),
                    "termination_reason": iteration.termination_reason,
                    "iteration_count": len(iteration.s_lambda_history) - 1,
                    "initial_s_lambda": float(iteration.s_lambda_history[0]),
                    "final_s_lambda": float(iteration.s_lambda_history[-1]),
                    "measured_s_lambda": float(measured.s_lambda),
                    "relative_mismatch": float(
                        iteration.relative_mismatch_history[-1]
                    ),
                    "root_thickness": float(
                        iteration.coupled.jet_interface.root_state.thickness
                    ),
                    "root_s_tau": float(
                        iteration.coupled.jet_interface.root_state.s_tau
                    ),
                    "delta_lambda": float(
                        iteration.coupled.jet_interface.root_state.delta_lambda
                    ),
                    **{
                        f"root_panel_distance_{index}": float(value)
                        for index, value in enumerate(root_distance)
                    },
                    **{
                        f"root_panel_s_lambda_{index}": float(value)
                        for index, value in enumerate(panel_s_lambda)
                    },
                }
            )
            if iteration.converged:
                result = iteration.coupled
            else:
                result = None
        rows.append(row)
        return result

    maximum_shift = int(args.maximum_panel_shifts)
    subdivisions = int(args.fractional_subdivisions)
    for shift in range(maximum_shift + 1):
        accepted = (
            evaluate_candidate(candidate, float(shift))
            if shift >= float(args.minimum_panel_shift)
            else None
        )
        if accepted is not None or len(candidate) <= 5 or shift == maximum_shift:
            break
        shifted = _regrid_coupled_outer_nodes(
            truncation.config,
            candidate[1:],
        )
        for subdivision in range(1, subdivisions):
            fraction = subdivision / subdivisions
            interpolated = _regrid_coupled_outer_nodes(
                truncation.config,
                (1.0 - fraction) * candidate + fraction * shifted,
            )
            effective_shift = shift + fraction
            if effective_shift < float(args.minimum_panel_shift):
                continue
            accepted = evaluate_candidate(interpolated, effective_shift)
            if accepted is not None:
                break
        if accepted is not None:
            break
        candidate = shifted

    audit = pd.DataFrame(rows)
    audit.to_csv(output / "root_compatibility_by_matching_surface.csv", index=False)
    result = {
        "status": "PASS" if accepted is not None else "FAIL",
        "source": str(source),
        "source_config": asdict(source_config),
        "reconstructed_bem_relative_residual": bvp.solution.relative_residual,
        "reconstructed_dipole_coefficient": bvp.dipole_coefficient,
        "initial_cut_node_index": truncation.original_cut_node_index,
        "initial_cut_angle_deg": truncation.cut_angle_deg,
        "tested_matching_surfaces": len(rows),
        "accepted_panel_shift": (
            None if accepted is None else float(rows[-1]["panel_shift"])
        ),
        "rows": rows,
    }
    (output / "root_compatibility_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if accepted is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
