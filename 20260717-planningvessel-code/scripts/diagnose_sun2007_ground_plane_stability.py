from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import (
    MovingWedgeConfig,
    advance_moving_wedge_rk4,
    run_steady_planing_wedge_entry,
)
from planing_seakeeping.kernels.nonlinear_2dt.planing_forced_motion import (
    GroundPlaneForcedMotionLaw,
    PlaningForcedMotionCase,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Advance the Sun (2007) creation-time-zero ground plane in isolation "
            "to diagnose spatial/time-step stability without weakening the two-cycle "
            "forced-motion identification contract."
        )
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--substeps", type=int, nargs="+", default=[8, 16])
    parser.add_argument("--end-time", type=float, default=0.2)
    parser.add_argument("--section-planes", type=int, default=11)
    parser.add_argument("--body-panels", type=int, default=28)
    parser.add_argument("--free-surface-panels", type=int, default=35)
    parser.add_argument("--uniform-near-body-panels", type=int, default=11)
    parser.add_argument("--free-surface-smoothing-node-count", type=int, default=12)
    parser.add_argument("--jet-cut-threshold-over-beam", type=float, default=0.03325555538987225)
    return parser


def _run_case(*, substeps: int, end_time_s: float, args: argparse.Namespace) -> dict[str, object]:
    beam = 0.318
    gravity = 9.80665
    rho = 1000.0
    trim = math.radians(4.0)
    deadrise = math.radians(20.0)
    speed = 2.5 * math.sqrt(gravity * beam)
    sigma = 1.4
    omega = sigma * math.sqrt(gravity / beam)
    period = 2.0 * math.pi / omega
    mean_wetted_length_beam_ratio = 3.0
    chine_wetting_offset_beams = 1.6
    wetted_length = (
        mean_wetted_length_beam_ratio + 0.5 * chine_wetting_offset_beams
    ) * beam
    lcg = 1.47 * beam
    initial_leading_offset_beams = 0.8
    initial_draft = initial_leading_offset_beams * beam * math.tan(trim)
    active_duration = (
        wetted_length - initial_draft / math.tan(trim)
    ) / speed
    plane_interval = active_duration / float(args.section_planes - 1)
    minimum_substeps = max(
        int(substeps),
        int(math.ceil(24.0 * plane_interval / period)),
    )
    dt = plane_interval / float(minimum_substeps)
    config = MovingWedgeConfig(
        deadrise_rad=deadrise,
        mean_draft_m=0.266 * beam,
        chine_half_beam_m=0.5 * beam,
        free_surface_extent_m=3.0 * beam,
        water_depth_m=2.5 * beam,
        body_panels_per_side=int(args.body_panels),
        free_surface_panels_per_side=int(args.free_surface_panels),
        side_wall_panels=6,
        bottom_panels=18,
        gauss_order=8,
        element_interpolation="linear_node",
        pressure_interpolation="constant_panel",
        damping_beach_length_m=beam,
        initializer="wagner",
        free_surface_spacing_mode="body_matched_geometric",
        free_surface_smoothing_enabled=True,
        free_surface_smoothing_node_count=int(args.free_surface_smoothing_node_count),
        free_surface_uniform_near_body_panel_count=int(args.uniform_near_body_panels),
        enforce_lateral_symmetry=True,
        use_symmetry_half_domain=True,
        knuckle_separation_model="artificial_surface",
        jet_cut_enabled=True,
        jet_cut_distance_fraction=0.25,
        jet_cut_threshold_m=float(args.jet_cut_threshold_over_beam) * beam,
        jet_cut_max_corrective_passes=8,
    )
    case = PlaningForcedMotionCase(
        speed_mps=speed,
        mean_trim_rad=trim,
        wetted_length_m=wetted_length,
        lcg_from_transom_m=lcg,
        motion_dof="heave",
        motion_amplitude=0.036 * beam,
        omega_rad_s=omega,
        duration_s=2.0 * period,
        time_step_s=dt,
        initial_draft_m=initial_draft,
        ground_plane_interval_s=plane_interval,
        rho_water_kg_m3=rho,
        gravity_m_s2=gravity,
        mean_wetted_length_beam_ratio=mean_wetted_length_beam_ratio,
    )
    base = run_steady_planing_wedge_entry(
        config,
        speed_mps=speed,
        trim_rad=trim,
        wetted_length_m=wetted_length,
        time_step_s=dt,
        initial_draft_m=initial_draft,
        rho_water_kg_m3=rho,
        gravity_m_s2=gravity,
    )
    reference_draft = max(float(config.mean_draft_m), float(np.max(base.draft_m)))
    config = replace(config, mean_draft_m=reference_draft)
    motion = GroundPlaneForcedMotionLaw(
        case=case,
        reference_draft_m=reference_draft,
        creation_time_s=0.0,
    )
    state = replace(base.states[0], time_s=0.0)
    maximum_condition = 0.0
    separation_times: list[float] = []
    contact_min = float(state.right_free_y_m[0])
    contact_max = contact_min
    step_count = int(math.ceil(float(end_time_s) / dt))
    status = "passed_end_time"
    failure = None
    for _ in range(step_count):
        try:
            step = advance_moving_wedge_rk4(
                config,
                motion,
                state,
                time_step_s=dt,
                gravity_m_s2=gravity,
            )
        except ValueError as exc:
            status = "failed"
            failure = str(exc)
            break
        state = step.state
        maximum_condition = max(maximum_condition, float(step.max_potential_condition_number))
        contact = float(state.right_free_y_m[0])
        contact_min = min(contact_min, contact)
        contact_max = max(contact_max, contact)
        if step.separation_event_time_s is not None:
            separation_times.append(float(step.separation_event_time_s))
        if state.time_s >= float(end_time_s) - 1e-14:
            break
    return {
        "status": status,
        "failure": failure,
        "requested_substeps_per_ground_plane_interval": int(substeps),
        "effective_substeps_per_ground_plane_interval": int(minimum_substeps),
        "time_step_s": float(dt),
        "target_end_time_s": float(end_time_s),
        "last_completed_time_s": float(state.time_s),
        "completed_step_count": int(round(float(state.time_s) / dt)),
        "maximum_potential_condition_number": float(maximum_condition),
        "contact_min_m": float(contact_min),
        "contact_max_m": float(contact_max),
        "chine_half_beam_m": float(config.chine_half_beam_m),
        "free_surface_extent_m": float(config.free_surface_extent_m),
        "separation_event_count": len(separation_times),
        "first_separation_event_time_s": (
            None if not separation_times else float(separation_times[0])
        ),
        "jet_cut_count": int(state.jet_cut_count),
        "body_panels_per_side": int(config.body_panels_per_side),
        "free_surface_panels_per_side": int(config.free_surface_panels_per_side),
        "response_calibration_used": False,
    }


def main() -> int:
    args = _parser().parse_args()
    if any(value < 1 for value in args.substeps):
        raise ValueError("substeps must be positive integers.")
    if args.end_time <= 0.0:
        raise ValueError("end-time must be positive.")
    results = [
        _run_case(substeps=int(substeps), end_time_s=float(args.end_time), args=args)
        for substeps in args.substeps
    ]
    payload = {
        "diagnostic": "Sun_2007_creation_time_zero_ground_plane_stability",
        "purpose": "separate time-step instability from spatial-grid divergence",
        "results": results,
    }
    output = args.out.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(output)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if all(row["status"] == "passed_end_time" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
