from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.boundary_element import (
    solve_linear_element_mixed_boundary_laplace,
)
from planing_seakeeping.kernels.nonlinear_2dt import moving_wedge as moving_wedge_module
from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import (
    LinearDraftEntryMotion,
    MovingWedgeConfig,
    MovingWedgeState,
    _linear_body_node_velocity,
    _linear_neumann_endpoint_values,
    _solve_linear_free_surface_normal_derivative,
    advance_moving_wedge_rk4,
    initialize_moving_wedge_state,
    moving_wedge_boundary,
    moving_wedge_load,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Sun's auxiliary potential psi with a body-following central "
            "time difference of the velocity potential during constant-speed wedge entry."
        )
    )
    parser.add_argument("--deadrise-deg", type=float, default=20.0)
    parser.add_argument("--entry-speed", type=float, default=1.0)
    parser.add_argument("--initial-draft", type=float, default=0.01)
    parser.add_argument("--target-draft", type=float, default=0.02)
    parser.add_argument("--time-step", type=float, default=0.00025)
    parser.add_argument("--body-panels", type=int, default=16)
    parser.add_argument("--free-panels", type=int, default=32)
    parser.add_argument(
        "--uniform-near-body-panels",
        type=int,
        default=6,
        help="Number of equal-size free-surface panels retained near the jet.",
    )
    parser.add_argument(
        "--smoothing-node-count",
        type=int,
        default=7,
        help="Near-body free-surface nodes included in Sun's smoothing formula.",
    )
    parser.add_argument(
        "--smoothing",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Apply Sun's five-point near-body smoothing at every remesh.",
    )
    parser.add_argument(
        "--smoothing-interval",
        type=float,
        default=None,
        help="Physical time between smoothing operations; defaults to every step.",
    )
    parser.add_argument(
        "--contact-potential-projection",
        choices=("none", "body_normal_taylor"),
        default="none",
        help=(
            "Diagnostic-only treatment for the free endpoint potential after its "
            "normal projection onto the moving body."
        ),
    )
    parser.add_argument(
        "--pressure-window-steps",
        type=int,
        default=12,
        help="Number of pre-target states used to quantify jet-cut pressure oscillation.",
    )
    parser.add_argument(
        "--cycle-search-steps",
        type=int,
        default=24,
        help="Steps advanced beyond the target to close a full jet-cut cycle.",
    )
    parser.add_argument(
        "--jet-cut-method",
        choices=("distance", "angle"),
        default="distance",
        help=(
            "Thin-jet topology rule. Angle selects the published 4-degree, "
            "lambda0=0.1L diagnostic construction; distance retains Sun's rule."
        ),
    )
    parser.add_argument(
        "--jet-cut-distance-fraction",
        type=float,
        default=0.25,
        help="Jet-cut threshold divided by the current wetted body-panel length.",
    )
    parser.add_argument(
        "--jet-cut-search-node-count",
        type=int,
        default=1,
        help=(
            "Number of near-tip nodes searched for point B; values above one are "
            "diagnostic because Sun (2007) did not specify the search algorithm."
        ),
    )
    parser.add_argument(
        "--ordering-safeguard",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Enable the legacy lateral-node-ordering safety cut. The default is "
            "off so this diagnostic tests Sun's normal-distance criterion alone."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/wedge_auxiliary_pressure_diagnostic"),
    )
    return parser.parse_args()


def _body_nodes(boundary) -> np.ndarray:
    labels = np.asarray(boundary.panel_labels, dtype=object)
    panels = np.flatnonzero(labels == "body")
    return np.unique(
        np.concatenate((panels, (panels + 1) % int(boundary.panel_count)))
    )


def _body_potential_profile(
    config: MovingWedgeConfig,
    motion: LinearDraftEntryMotion,
    state: MovingWedgeState,
) -> tuple[np.ndarray, np.ndarray]:
    boundary, _, potential = _solve_linear_free_surface_normal_derivative(
        config, motion, state
    )
    nodes = _body_nodes(boundary)
    order = np.argsort(boundary.node_y_m[nodes])
    return (
        np.asarray(boundary.node_y_m[nodes][order], dtype=float),
        np.asarray(potential.potential_m2_s[nodes][order], dtype=float),
    )


def main() -> None:
    args = _parse_args()
    if args.target_draft <= args.initial_draft:
        raise ValueError("target-draft must exceed initial-draft.")
    if args.time_step <= 0.0 or args.entry_speed <= 0.0:
        raise ValueError("time-step and entry-speed must be positive.")

    beta = np.radians(float(args.deadrise_deg))
    reference_draft = max(0.1, 2.0 * float(args.target_draft))
    config = MovingWedgeConfig(
        deadrise_rad=beta,
        mean_draft_m=reference_draft,
        chine_half_beam_m=1.5,
        free_surface_extent_m=2.0,
        water_depth_m=1.0,
        body_panels_per_side=int(args.body_panels),
        free_surface_panels_per_side=int(args.free_panels),
        side_wall_panels=6,
        bottom_panels=32,
        gauss_order=8,
        element_interpolation="linear_node",
        pressure_interpolation="match_potential",
        initializer="wagner",
        free_surface_remesh_enabled=True,
        free_surface_smoothing_enabled=bool(args.smoothing),
        free_surface_smoothing_node_count=int(args.smoothing_node_count),
        free_surface_smoothing_interval_s=(
            None
            if args.smoothing_interval is None
            else float(args.smoothing_interval)
        ),
        free_surface_spacing_mode="body_matched_geometric",
        free_surface_uniform_near_body_panel_count=int(
            args.uniform_near_body_panels
        ),
        enforce_lateral_symmetry=True,
        use_symmetry_half_domain=True,
        chine_separation_enabled=False,
        jet_cut_enabled=True,
        jet_cut_method=str(args.jet_cut_method),
        jet_cut_distance_fraction=float(args.jet_cut_distance_fraction),
        jet_cut_search_node_count=int(args.jet_cut_search_node_count),
        jet_cut_ordering_safeguard_enabled=bool(args.ordering_safeguard),
    )
    motion = LinearDraftEntryMotion(
        reference_draft_m=reference_draft,
        initial_draft_m=float(args.initial_draft),
        draft_rate_mps=float(args.entry_speed),
    )
    if args.contact_potential_projection == "body_normal_taylor":
        original_increment = moving_wedge_module._increment_moving_wedge_state

        def increment_with_projected_potential(config, motion, state, rhs, scale_s):
            scale = float(scale_s)
            provisional_right_z = float(
                state.right_free_z_up_m[0]
                + scale * rhs.right_node_velocity_mps[0, 1]
            )
            provisional_left_z = float(
                state.left_free_z_up_m[-1]
                + scale * rhs.left_node_velocity_mps[-1, 1]
            )
            updated = original_increment(config, motion, state, rhs, scale)
            velocity_z = float(motion.velocity_mps(updated.time_s))
            right_potential = np.asarray(
                updated.right_free_potential_m2_s, dtype=float
            ).copy()
            left_potential = np.asarray(
                updated.left_free_potential_m2_s, dtype=float
            ).copy()
            right_potential[0] += velocity_z * (
                float(updated.right_free_z_up_m[0]) - provisional_right_z
            )
            left_potential[-1] += velocity_z * (
                float(updated.left_free_z_up_m[-1]) - provisional_left_z
            )
            if config.enforce_lateral_symmetry:
                symmetric = 0.5 * (right_potential + left_potential[::-1])
                right_potential = symmetric
                left_potential = symmetric[::-1]
            return replace(
                updated,
                right_free_potential_m2_s=right_potential,
                left_free_potential_m2_s=left_potential,
            )

        moving_wedge_module._increment_moving_wedge_state = (
            increment_with_projected_potential
        )
    dt = float(args.time_step)
    target_time = (
        float(args.target_draft) - float(args.initial_draft)
    ) / float(args.entry_speed)
    target_step = int(round(target_time / dt))
    if target_step < 2 or not np.isclose(target_step * dt, target_time, atol=1e-12):
        raise ValueError("target-draft must lie exactly on the requested time-step grid.")

    state = initialize_moving_wedge_state(config, motion)
    states: dict[int, MovingWedgeState] = {}
    pressure_window_steps = max(1, int(args.pressure_window_steps))
    cycle_search_steps = max(1, int(args.cycle_search_steps))
    candidate_states: list[tuple[int, MovingWedgeState]] = []
    localized_jet_cut_event_times: list[float] = []
    pre_step_jet_margins: list[float] = []
    candidate_start_step = max(1, target_step - pressure_window_steps)
    final_step = target_step + cycle_search_steps
    for step in range(1, final_step + 1):
        pre_step_margin, _ = moving_wedge_module._right_jet_cut_event_geometry(
            config,
            motion,
            state,
        )
        pre_step_jet_margins.append(float(pre_step_margin))
        step_result = advance_moving_wedge_rk4(
            config,
            motion,
            state,
            time_step_s=dt,
            gravity_m_s2=0.0,
        )
        if step_result.jet_cut_event_time_s is not None:
            localized_jet_cut_event_times.append(
                float(step_result.jet_cut_event_time_s)
            )
        state = step_result.state
        if step in (target_step - 1, target_step, target_step + 1):
            states[step] = state
        if step >= candidate_start_step:
            candidate_states.append((step, state))

    event_indices = [
        index
        for index in range(1, len(candidate_states))
        if candidate_states[index][1].jet_cut_count
        != candidate_states[index - 1][1].jet_cut_count
    ]
    completed_cycles = [
        candidate_states[start:end]
        for start, end in zip(event_indices[:-1], event_indices[1:])
        if end > start
    ]
    if completed_cycles:
        selected_cycle = min(
            completed_cycles,
            key=lambda cycle: abs(
                0.5 * (cycle[0][0] + cycle[-1][0]) - target_step
            ),
        )
        pressure_window_states = [state for _, state in selected_cycle]
        pressure_window_selection = "complete_jet_cut_cycle"
    else:
        fallback = [
            state for step, state in candidate_states if step <= target_step
        ][-pressure_window_steps:]
        pressure_window_states = fallback
        pressure_window_selection = "pre_target_fallback_no_complete_cycle"

    previous = states[target_step - 1]
    center = states[target_step]
    following = states[target_step + 1]
    previous_y, previous_phi = _body_potential_profile(config, motion, previous)
    following_y, following_phi = _body_potential_profile(config, motion, following)

    boundary, free_panel_count, potential = _solve_linear_free_surface_normal_derivative(
        config, motion, center
    )
    nodes = _body_nodes(boundary)
    order = np.argsort(boundary.node_y_m[nodes])
    nodes = nodes[order]
    all_body_nodes = nodes.copy()
    all_body_y = np.asarray(boundary.node_y_m[nodes], dtype=float)
    all_body_phi = np.asarray(potential.potential_m2_s[nodes], dtype=float)
    physical_age = float(motion.draft_m(center.time_s)) / float(args.entry_speed)
    similarity_coordinate = all_body_y / (
        float(args.entry_speed) * physical_age
    )
    similarity_potential = all_body_phi / (
        float(args.entry_speed) ** 2 * physical_age
    )
    similarity_tangential_derivative = np.gradient(
        similarity_potential, similarity_coordinate, edge_order=2
    )
    similarity_material_derivative_all = float(args.entry_speed) ** 2 * (
        similarity_potential
        - similarity_coordinate * similarity_tangential_derivative
    )
    y = all_body_y
    contact_limit = min(previous_y[-1], y[-1], following_y[-1])
    interior = (y > y[0] + 1e-12) & (y < 0.9 * contact_limit)
    nodes = nodes[interior]
    y = y[interior]
    similarity_material_derivative = similarity_material_derivative_all[interior]
    material_difference = (
        np.interp(y, following_y, following_phi)
        - np.interp(y, previous_y, previous_phi)
    ) / (2.0 * dt)

    velocity_z = float(motion.velocity_mps(center.time_s))
    velocity = _linear_body_node_velocity(
        boundary,
        potential,
        body_velocity_z=velocity_z,
        free_panel_count=free_panel_count,
    )
    speed_squared = np.sum(velocity**2, axis=1)
    body_advection = velocity[:, 1] * velocity_z
    psi_known = np.zeros(boundary.panel_count, dtype=float)
    psi_known[: free_panel_count + 1] = (
        body_advection[: free_panel_count + 1]
        - 0.5 * speed_squared[: free_panel_count + 1]
    )
    dirichlet, acceleration = _linear_neumann_endpoint_values(
        boundary, body_vertical_value=0.0
    )
    auxiliary = solve_linear_element_mixed_boundary_laplace(
        boundary,
        dirichlet_panel_mask=dirichlet,
        dirichlet_node_values=psi_known,
        neumann_endpoint_values=acceleration,
        gauss_order=int(config.gauss_order),
    )
    free_slice = slice(0, free_panel_count + 1)
    free_phi_similarity = potential.potential_m2_s[free_slice] / (
        float(args.entry_speed) ** 2 * physical_age
    )
    free_eta = boundary.node_y_m[free_slice] / (
        float(args.entry_speed) * physical_age
    )
    free_zeta = boundary.node_z_up_m[free_slice] / (
        float(args.entry_speed) * physical_age
    )
    free_similarity_psi = float(args.entry_speed) ** 2 * (
        free_phi_similarity
        - free_eta * velocity[free_slice, 0] / float(args.entry_speed)
        - (free_zeta + 1.0)
        * velocity[free_slice, 1]
        / float(args.entry_speed)
    )
    free_supplied_psi = psi_known[free_slice]
    free_compare = slice(1, max(free_panel_count - 2, 2))
    free_similarity_scale = max(
        float(np.max(np.abs(free_similarity_psi[free_compare]))),
        np.finfo(float).eps,
    )
    free_psi_similarity_nrmse = float(
        np.sqrt(
            np.mean(
                (
                    free_supplied_psi[free_compare]
                    - free_similarity_psi[free_compare]
                )
                ** 2
            )
        )
        / free_similarity_scale
    )
    auxiliary_psi = np.asarray(auxiliary.potential_m2_s[nodes], dtype=float)
    difference = auxiliary_psi - material_difference
    scale = max(float(np.max(np.abs(material_difference))), np.finfo(float).eps)
    normalized_rmse = float(np.sqrt(np.mean(difference**2)) / scale)
    normalized_max_abs = float(np.max(np.abs(difference)) / scale)
    similarity_scale = max(
        float(np.max(np.abs(similarity_material_derivative))), np.finfo(float).eps
    )
    auxiliary_similarity_difference = auxiliary_psi - similarity_material_derivative
    finite_difference_similarity_difference = (
        material_difference - similarity_material_derivative
    )
    auxiliary_similarity_nrmse = float(
        np.sqrt(np.mean(auxiliary_similarity_difference**2)) / similarity_scale
    )
    finite_difference_similarity_nrmse = float(
        np.sqrt(np.mean(finite_difference_similarity_difference**2))
        / similarity_scale
    )
    node_speed_squared = speed_squared[nodes]
    node_body_advection = body_advection[nodes]
    auxiliary_cp = -2.0 * (
        auxiliary_psi - node_body_advection + 0.5 * node_speed_squared
    )
    finite_difference_cp = -2.0 * (
        material_difference - node_body_advection + 0.5 * node_speed_squared
    )
    similarity_cp = -2.0 * (
        similarity_material_derivative
        - node_body_advection
        + 0.5 * node_speed_squared
    )
    all_auxiliary_psi = np.asarray(
        auxiliary.potential_m2_s[all_body_nodes], dtype=float
    )
    all_node_body_advection = body_advection[all_body_nodes]
    all_node_speed_squared = speed_squared[all_body_nodes]
    all_auxiliary_cp = -2.0 * (
        all_auxiliary_psi
        - all_node_body_advection
        + 0.5 * all_node_speed_squared
    )
    all_similarity_cp = -2.0 * (
        similarity_material_derivative_all
        - all_node_body_advection
        + 0.5 * all_node_speed_squared
    )
    all_z_over_vt = boundary.node_z_up_m[all_body_nodes] / float(
        motion.draft_m(center.time_s)
    )
    reference_path = (
        ROOT
        / "benchmarks"
        / "sun2007_fig2_6_wedge_similarity"
        / "fig2_6_zhao_faltinsen_similarity_curves.csv"
    )
    with reference_path.open(encoding="utf-8", newline="") as stream:
        reference_rows = [
            row
            for row in csv.DictReader(stream)
            if float(row["beta_deg"]) == float(args.deadrise_deg)
            and row["quantity"] == "pressure"
        ]
    reference_z = np.asarray(
        [float(row["x_nondimensional"]) for row in reference_rows], dtype=float
    )
    reference_cp = np.asarray(
        [float(row["y_nondimensional"]) for row in reference_rows], dtype=float
    )
    reference_order = np.argsort(reference_z)
    reference_z = reference_z[reference_order]
    reference_cp = reference_cp[reference_order]
    overlap = (reference_z >= all_z_over_vt[0]) & (
        reference_z <= all_z_over_vt[-1]
    )
    reference_scale = max(
        float(np.max(np.abs(reference_cp[overlap]))), np.finfo(float).eps
    )
    interpolated_auxiliary_cp = np.interp(
        reference_z[overlap], all_z_over_vt, all_auxiliary_cp
    )
    interpolated_similarity_cp = np.interp(
        reference_z[overlap], all_z_over_vt, all_similarity_cp
    )
    auxiliary_pressure_reference_nrmse = float(
        np.sqrt(
            np.mean((interpolated_auxiliary_cp - reference_cp[overlap]) ** 2)
        )
        / reference_scale
    )
    similarity_pressure_reference_nrmse = float(
        np.sqrt(
            np.mean((interpolated_similarity_cp - reference_cp[overlap]) ** 2)
        )
        / reference_scale
    )
    auxiliary_peak_index = int(np.argmax(all_auxiliary_cp))
    similarity_peak_index = int(np.argmax(all_similarity_cp))
    reference_peak_index = int(np.argmax(reference_cp))
    vertical_force_factor = 2.0 / np.tan(beta)
    reference_vertical_force_coefficient = float(
        vertical_force_factor * np.trapezoid(reference_cp, reference_z)
    )
    window_curves = []
    window_metadata = []
    for window_state in pressure_window_states:
        window_boundary = moving_wedge_boundary(config, motion, window_state)
        window_load = moving_wedge_load(
            config,
            motion,
            window_state,
            rho_water_kg_m3=1.0,
            gravity_m_s2=0.0,
        )
        window_nodes = _body_nodes(window_boundary)
        window_order = np.argsort(window_boundary.node_z_up_m[window_nodes])
        window_nodes = window_nodes[window_order]
        window_draft = float(motion.draft_m(window_state.time_s))
        window_z = window_boundary.node_z_up_m[window_nodes] / window_draft
        window_cp = (
            2.0
            * window_load.pressure.gauge_pressure_pa[window_nodes]
            / float(args.entry_speed) ** 2
        )
        curve = np.full_like(reference_cp, np.nan, dtype=float)
        valid = (reference_z >= window_z[0]) & (reference_z <= window_z[-1])
        curve[valid] = np.interp(reference_z[valid], window_z, window_cp)
        window_curves.append(curve)
        state_scale = max(
            float(np.max(np.abs(reference_cp[valid]))), np.finfo(float).eps
        )
        state_nrmse = float(
            np.sqrt(np.mean((curve[valid] - reference_cp[valid]) ** 2))
            / state_scale
        )
        state_peak_index = int(np.nanargmax(curve))
        state_vertical_force_coefficient = float(
            vertical_force_factor
            * np.trapezoid(curve[valid], reference_z[valid])
        )
        window_metadata.append(
            {
                "time_s": float(window_state.time_s),
                "draft_m": window_draft,
                "jet_cut_count": int(window_state.jet_cut_count),
                "contact_y_over_Vt": float(
                    window_state.right_free_y_m[0] / window_draft
                ),
                "pressure_reference_nrmse": state_nrmse,
                "pressure_peak_z_over_Vt": float(reference_z[state_peak_index]),
                "pressure_peak_cp": float(curve[state_peak_index]),
                "vertical_force_coefficient": state_vertical_force_coefficient,
            }
        )
    window_matrix = np.asarray(window_curves, dtype=float)
    window_common = np.all(np.isfinite(window_matrix), axis=0)
    window_mean_cp = np.mean(window_matrix[:, window_common], axis=0)
    window_std_cp = np.std(window_matrix[:, window_common], axis=0, ddof=0)
    window_reference_cp = reference_cp[window_common]
    window_reference_scale = max(
        float(np.max(np.abs(window_reference_cp))), np.finfo(float).eps
    )
    pressure_window_mean_reference_nrmse = float(
        np.sqrt(np.mean((window_mean_cp - window_reference_cp) ** 2))
        / window_reference_scale
    )
    pressure_window_rms_std_normalized = float(
        np.sqrt(np.mean(window_std_cp**2)) / window_reference_scale
    )
    pressure_window_max_std_normalized = float(
        np.max(window_std_cp) / window_reference_scale
    )
    window_vertical_force_coefficients = np.asarray(
        [state["vertical_force_coefficient"] for state in window_metadata],
        dtype=float,
    )
    window_mean_vertical_force_coefficient = float(
        np.mean(window_vertical_force_coefficients)
    )
    window_vertical_force_relative_error = float(
        abs(
            window_mean_vertical_force_coefficient
            - reference_vertical_force_coefficient
        )
        / max(abs(reference_vertical_force_coefficient), np.finfo(float).eps)
    )
    window_vertical_force_relative_std = float(
        np.std(window_vertical_force_coefficients, ddof=0)
        / max(abs(reference_vertical_force_coefficient), np.finfo(float).eps)
    )

    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    draft = float(motion.draft_m(center.time_s))
    for (
        node,
        coordinate,
        finite_difference,
        similarity_derivative,
        psi,
        residual,
        cp_auxiliary,
        cp_finite_difference,
        cp_similarity,
    ) in zip(
        nodes,
        y,
        material_difference,
        similarity_material_derivative,
        auxiliary_psi,
        difference,
        auxiliary_cp,
        finite_difference_cp,
        similarity_cp,
    ):
        rows.append(
            {
                "node": int(node),
                "y_over_Vt": float(coordinate / draft),
                "material_dphi_dt_over_V2": float(
                    finite_difference / float(args.entry_speed) ** 2
                ),
                "similarity_material_dphi_dt_over_V2": float(
                    similarity_derivative / float(args.entry_speed) ** 2
                ),
                "auxiliary_psi_over_V2": float(
                    psi / float(args.entry_speed) ** 2
                ),
                "difference_over_V2": float(
                    residual / float(args.entry_speed) ** 2
                ),
                "cp_from_auxiliary": float(cp_auxiliary),
                "cp_from_finite_difference": float(cp_finite_difference),
                "cp_from_similarity_derivative": float(cp_similarity),
            }
        )
    with (output / "body_material_derivative_comparison.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    free_rows = []
    for index in range(free_panel_count + 1):
        free_rows.append(
            {
                "node": index,
                "y_over_Vt": float(free_eta[index]),
                "z_over_Vt": float(free_zeta[index]),
                "supplied_psi_over_V2": float(
                    free_supplied_psi[index] / float(args.entry_speed) ** 2
                ),
                "similarity_psi_over_V2": float(
                    free_similarity_psi[index] / float(args.entry_speed) ** 2
                ),
                "difference_over_V2": float(
                    (free_supplied_psi[index] - free_similarity_psi[index])
                    / float(args.entry_speed) ** 2
                ),
            }
        )
    with (output / "free_surface_auxiliary_boundary_comparison.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(free_rows[0]))
        writer.writeheader()
        writer.writerows(free_rows)
    with (output / "pressure_window_comparison.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        fieldnames = [
            "z_over_Vt",
            "reference_cp",
            "window_mean_cp",
            "window_std_cp",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for z_value, reference_value, mean_value, std_value in zip(
            reference_z[window_common],
            window_reference_cp,
            window_mean_cp,
            window_std_cp,
        ):
            writer.writerow(
                {
                    "z_over_Vt": float(z_value),
                    "reference_cp": float(reference_value),
                    "window_mean_cp": float(mean_value),
                    "window_std_cp": float(std_value),
                }
            )
    with (output / "pressure_window_states.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(window_metadata[0]))
        writer.writeheader()
        writer.writerows(window_metadata)

    summary = {
        "deadrise_deg": float(args.deadrise_deg),
        "entry_speed_mps": float(args.entry_speed),
        "target_draft_m": draft,
        "time_step_s": dt,
        "body_panels_per_side": int(args.body_panels),
        "free_surface_panels_per_side": int(args.free_panels),
        "uniform_near_body_panels": int(args.uniform_near_body_panels),
        "smoothing_node_count": int(args.smoothing_node_count),
        "free_surface_smoothing_enabled": bool(args.smoothing),
        "free_surface_smoothing_interval_s": (
            None
            if args.smoothing_interval is None
            else float(args.smoothing_interval)
        ),
        "contact_potential_projection": str(args.contact_potential_projection),
        "contact_y_over_Vt": float(center.right_free_y_m[0] / draft),
        "jet_cut_count": int(center.jet_cut_count),
        "localized_jet_cut_event_count": len(localized_jet_cut_event_times),
        "localized_jet_cut_event_times_s": localized_jet_cut_event_times,
        "minimum_pre_step_jet_margin_m": float(np.min(pre_step_jet_margins)),
        "nonpositive_pre_step_jet_margin_count": int(
            np.count_nonzero(np.asarray(pre_step_jet_margins) <= 0.0)
        ),
        "minimum_jet_normal_distance_ratio": (
            None
            if center.minimum_jet_normal_distance_ratio is None
            else float(center.minimum_jet_normal_distance_ratio)
        ),
        "jet_cut_distance_fraction": float(args.jet_cut_distance_fraction),
        "jet_cut_method": str(args.jet_cut_method),
        "jet_cut_search_node_count": int(args.jet_cut_search_node_count),
        "jet_cut_ordering_safeguard_enabled": bool(args.ordering_safeguard),
        "jet_cut_angle_threshold_deg": float(config.jet_cut_angle_threshold_deg),
        "jet_cut_angle_length_fraction": float(
            config.jet_cut_angle_length_fraction
        ),
        "jet_cut_angle_hull_arc_length_m": float(
            config.chine_half_beam_m / np.cos(config.deadrise_rad)
            if config.jet_cut_angle_hull_arc_length_m is None
            else config.jet_cut_angle_hull_arc_length_m
        ),
        "comparison_point_count": int(len(rows)),
        "material_derivative_scale_m2_s2": scale,
        "normalized_rmse": normalized_rmse,
        "normalized_max_abs_error": normalized_max_abs,
        "auxiliary_vs_similarity_nrmse": auxiliary_similarity_nrmse,
        "finite_difference_vs_similarity_nrmse": (
            finite_difference_similarity_nrmse
        ),
        "auxiliary_cp_max_on_interior_nodes": float(np.max(auxiliary_cp)),
        "finite_difference_cp_max_on_interior_nodes": float(
            np.max(finite_difference_cp)
        ),
        "similarity_cp_max_on_interior_nodes": float(np.max(similarity_cp)),
        "free_supplied_psi_vs_similarity_nrmse": free_psi_similarity_nrmse,
        "pressure_reference_overlap_point_count": int(np.count_nonzero(overlap)),
        "auxiliary_pressure_reference_nrmse": (
            auxiliary_pressure_reference_nrmse
        ),
        "similarity_pressure_reference_nrmse": (
            similarity_pressure_reference_nrmse
        ),
        "auxiliary_pressure_peak": {
            "z_over_Vt": float(all_z_over_vt[auxiliary_peak_index]),
            "cp": float(all_auxiliary_cp[auxiliary_peak_index]),
        },
        "similarity_pressure_peak": {
            "z_over_Vt": float(all_z_over_vt[similarity_peak_index]),
            "cp": float(all_similarity_cp[similarity_peak_index]),
        },
        "reference_pressure_peak": {
            "z_over_Vt": float(reference_z[reference_peak_index]),
            "cp": float(reference_cp[reference_peak_index]),
        },
        "pressure_window": {
            "selection": pressure_window_selection,
            "state_count": int(len(pressure_window_states)),
            "states": window_metadata,
            "common_reference_point_count": int(np.count_nonzero(window_common)),
            "mean_pressure_reference_nrmse": (
                pressure_window_mean_reference_nrmse
            ),
            "rms_temporal_std_normalized": pressure_window_rms_std_normalized,
            "max_temporal_std_normalized": pressure_window_max_std_normalized,
            "reference_vertical_force_coefficient": (
                reference_vertical_force_coefficient
            ),
            "mean_vertical_force_coefficient": (
                window_mean_vertical_force_coefficient
            ),
            "vertical_force_relative_error": (
                window_vertical_force_relative_error
            ),
            "vertical_force_relative_std": window_vertical_force_relative_std,
        },
        "potential_bvp_relative_residual": float(potential.relative_residual),
        "auxiliary_bvp_relative_residual": float(auxiliary.relative_residual),
        "interpretation": (
            "This is an independent diagnostic, not a Gate-2 pass criterion. "
            "Large disagreement means the pressure auxiliary BVP and the "
            "time-marched potential are not mutually consistent."
        ),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
