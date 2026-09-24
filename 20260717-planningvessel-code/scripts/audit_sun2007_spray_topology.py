from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import (
    MovingWedgeConfig,
    MovingWedgeContactExitError,
    advance_moving_wedge_rk4,
    initialize_moving_wedge_state,
)
from planing_seakeeping.kernels.nonlinear_2dt.planing_forced_motion import (
    GroundPlaneForcedMotionLaw,
    PlaningForcedMotionCase,
    fixed_ground_plane_activation_time_s,
    planing_forced_motion_kinematics,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = (
    ROOT
    / "benchmarks"
    / "sun2007_troesch_forced_motion_coefficients_manifest.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_activation_time(
    case: PlaningForcedMotionCase,
    motion: GroundPlaneForcedMotionLaw,
    *,
    minimum_draft_m: float,
    time_step_s: float,
) -> float:
    start = float(motion.creation_time_s)
    search_duration = max(
        2.0 * math.pi / float(case.omega_rad_s),
        float(case.wetted_length_m) / float(case.speed_mps),
    )
    step_count = int(math.ceil(search_duration / time_step_s)) + 1
    for index in range(step_count):
        end = start + float(time_step_s)
        activation = fixed_ground_plane_activation_time_s(
            case,
            motion,
            interval_start_s=start,
            interval_end_s=end,
            minimum_draft_m=minimum_draft_m,
        )
        if activation is not None:
            return float(activation)
        start = end
    raise RuntimeError("The scanned ground plane never reached the BEM handoff draft.")


def _audit_one_trajectory(job: tuple[MovingWedgeConfig, PlaningForcedMotionCase, float]) -> dict[str, Any]:
    config, case, creation_phase_rad = job
    creation_time = float(creation_phase_rad) / float(case.omega_rad_s)
    motion = GroundPlaneForcedMotionLaw(
        case=case,
        reference_draft_m=float(config.mean_draft_m),
        creation_time_s=creation_time,
        incident_wave_active=False,
    )
    activation_time = _find_activation_time(
        case,
        motion,
        minimum_draft_m=float(case.initial_draft_m),
        time_step_s=float(case.time_step_s),
    )
    state = initialize_moving_wedge_state(config, motion, time_s=activation_time)
    first_overturning_time: float | None = None
    maximum_potential_residual = 0.0
    status = "transom_exit"
    step_count = 0
    maximum_steps = int(
        math.ceil(
            1.5
            * float(case.wetted_length_m)
            / (float(case.speed_mps) * float(case.time_step_s))
        )
    )
    for _ in range(maximum_steps):
        next_time = float(state.time_s + case.time_step_s)
        _, x_from_transom, _ = motion.longitudinal_coordinates(next_time)
        instantaneous_wetted_length = planing_forced_motion_kinematics(
            case, next_time
        ).instantaneous_wetted_length_m
        remains_wet = bool(
            -1.0e-9 <= x_from_transom <= instantaneous_wetted_length + 1.0e-9
            and motion.submergence_m(next_time)
            >= float(case.initial_draft_m) * (1.0 - 1.0e-9)
        )
        if not remains_wet:
            status = "physical_wet_interval_exit"
            break
        try:
            step = advance_moving_wedge_rk4(
                config,
                motion,
                state,
                time_step_s=float(case.time_step_s),
                gravity_m_s2=float(case.gravity_m_s2),
            )
        except MovingWedgeContactExitError:
            status = "contact_exit"
            break
        state = step.state
        step_count += 1
        maximum_potential_residual = max(
            maximum_potential_residual,
            float(step.max_potential_relative_residual),
        )
        if (
            first_overturning_time is None
            and state.maximum_spray_overturning_panel_count > 0
        ):
            first_overturning_time = float(state.time_s)
    else:
        status = "maximum_step_guard"

    return {
        "motion_dof": case.motion_dof,
        "creation_phase_rad": float(creation_phase_rad),
        "creation_phase_deg": float(np.degrees(creation_phase_rad)),
        "creation_time_s": creation_time,
        "activation_time_s": activation_time,
        "activation_phase_deg": float(
            np.degrees((case.omega_rad_s * activation_time) % (2.0 * np.pi))
        ),
        "simulated_step_count": step_count,
        "simulated_duration_s": float(state.time_s - activation_time),
        "trajectory_status": status,
        "maximum_spray_overturning_panel_count": int(
            state.maximum_spray_overturning_panel_count
        ),
        "first_overturning_time_s": first_overturning_time,
        "minimum_spray_outward_tangent_cosine": (
            None
            if state.minimum_spray_outward_tangent_cosine is None
            else float(state.minimum_spray_outward_tangent_cosine)
        ),
        "minimum_spray_nonadjacent_distance_ratio": (
            None
            if state.minimum_spray_nonadjacent_distance_ratio is None
            else float(state.minimum_spray_nonadjacent_distance_ratio)
        ),
        "final_jet_cut_count": int(state.jet_cut_count),
        "maximum_potential_bvp_relative_residual": maximum_potential_residual,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit Sun 2007 spray-sheet topology precursors on phase-scanned ground planes."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/sun2007_spray_topology_audit"),
    )
    parser.add_argument("--sigma", type=float, default=1.4)
    parser.add_argument("--phase-count", type=int, default=4)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--body-panels", type=int, default=12)
    parser.add_argument("--free-surface-panels", type=int, default=15)
    parser.add_argument("--bem-substeps-per-plane", type=int, default=16)
    parser.add_argument("--section-planes", type=int, default=11)
    parser.add_argument("--initial-leading-offset-beams", type=float, default=None)
    parser.add_argument(
        "--reuse-existing-trajectories",
        action="store_true",
        help="Rebuild the manifest from an existing trajectory CSV without rerunning BEM.",
    )
    parser.add_argument(
        "--motion-dofs",
        nargs="+",
        choices=("heave", "pitch"),
        default=("heave", "pitch"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.sigma <= 0.0 or args.phase_count < 1 or args.workers < 1:
        raise ValueError("sigma, phase-count, and workers must be positive.")
    if args.bem_substeps_per_plane < 1 or args.section_planes < 2:
        raise ValueError("BEM substeps and section plane counts are too small.")

    beam = 0.318
    gravity = 9.80665
    rho = 1000.0
    speed = 2.5 * math.sqrt(gravity * beam)
    trim = math.radians(4.0)
    wetted_length = 3.8 * beam
    plane_spacing = wetted_length / float(args.section_planes)
    plane_interval = plane_spacing / speed
    time_step = plane_interval / float(args.bem_substeps_per_plane)
    initial_offset_beams = (
        plane_spacing / beam
        if args.initial_leading_offset_beams is None
        else float(args.initial_leading_offset_beams)
    )
    initial_draft = initial_offset_beams * beam * math.tan(trim)
    omega = float(args.sigma) * math.sqrt(gravity / beam)
    period = 2.0 * math.pi / omega
    reference_draft = max(0.266 * beam, wetted_length * math.tan(trim))
    remesh_interval = plane_interval / 8.0

    config = MovingWedgeConfig(
        deadrise_rad=math.radians(20.0),
        mean_draft_m=reference_draft,
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
        damping_beach_beta0=0.3,
        initializer="wagner",
        free_surface_remesh_enabled=True,
        free_surface_remesh_interval_s=remesh_interval,
        free_surface_spacing_mode="body_matched_geometric",
        free_surface_smoothing_enabled=True,
        free_surface_smoothing_node_count=7,
        free_surface_smoothing_interval_s=remesh_interval,
        free_surface_uniform_near_body_panel_count=6,
        enforce_lateral_symmetry=True,
        use_symmetry_half_domain=True,
        chine_separation_enabled=True,
        knuckle_separation_model="artificial_surface",
        jet_cut_enabled=True,
        jet_cut_distance_fraction=0.25,
    )
    phases = np.linspace(0.0, 2.0 * np.pi, int(args.phase_count), endpoint=False)
    jobs: list[tuple[MovingWedgeConfig, PlaningForcedMotionCase, float]] = []
    for motion_dof in args.motion_dofs:
        amplitude = 0.036 * beam if motion_dof == "heave" else math.radians(0.43)
        case = PlaningForcedMotionCase(
            speed_mps=speed,
            mean_trim_rad=trim,
            wetted_length_m=wetted_length,
            lcg_from_transom_m=1.47 * beam,
            omega_rad_s=omega,
            motion_dof=motion_dof,
            motion_amplitude=amplitude,
            duration_s=2.0 * period,
            time_step_s=time_step,
            initial_draft_m=initial_draft,
            ground_plane_interval_s=plane_interval,
            ground_plane_handoff_mode="fixed_earth_grid",
            rho_water_kg_m3=rho,
            gravity_m_s2=gravity,
            mean_wetted_length_beam_ratio=3.0,
            metadata={"audit": "sun2007_spray_topology_phase_scan"},
        )
        jobs.extend((config, case, float(phase)) for phase in phases)

    output = args.out if args.out.is_absolute() else ROOT / args.out
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "spray_topology_trajectories.csv"
    if args.reuse_existing_trajectories:
        if not csv_path.exists():
            raise FileNotFoundError(
                "--reuse-existing-trajectories requires spray_topology_trajectories.csv."
            )
        with csv_path.open("r", newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise ValueError("The existing spray topology trajectory CSV is empty.")
    else:
        if int(args.workers) == 1:
            rows = [_audit_one_trajectory(job) for job in jobs]
        else:
            with ProcessPoolExecutor(max_workers=int(args.workers)) as executor:
                rows = list(executor.map(_audit_one_trajectory, jobs))
        rows.sort(
            key=lambda row: (str(row["motion_dof"]), float(row["creation_phase_rad"]))
        )
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    maximum_overturning = max(
        int(row["maximum_spray_overturning_panel_count"]) for row in rows
    )
    minimum_cosine = min(
        float(row["minimum_spray_outward_tangent_cosine"])
        for row in rows
        if row["minimum_spray_outward_tangent_cosine"] is not None
    )
    minimum_distance_ratio = min(
        float(row["minimum_spray_nonadjacent_distance_ratio"])
        for row in rows
        if row["minimum_spray_nonadjacent_distance_ratio"] is not None
    )
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    manifest = {
        "schema": "sun2007_spray_topology_phase_scan_v1",
        "status": (
            "PRECURSOR_DETECTED_REQUIRES_SPRAY_CUT_IMPLEMENTATION"
            if maximum_overturning > 0
            else "NO_SPRAY_CUT_PRECURSOR_IN_SCANNED_TRAJECTORIES"
        ),
        "acceptance_role": "diagnostic_exclusion_only_not_coefficient_acceptance",
        "source": {
            "description": "Sun 2007 Sec. 2.5 and Fig. 2.3",
            "local_manifest_path": str(SOURCE_MANIFEST),
            "local_manifest_sha256": _sha256(SOURCE_MANIFEST),
            "source_pdf_sha256": source_manifest["source_pdf_sha256"],
            "related_source_location": source_manifest["source_location"],
            "source_rule": (
                "An overturning spray is cut normal to upper AB through the midpoint "
                "between spray tip B and the highest point C on the lower free surface."
            ),
        },
        "diagnostic_contract": (
            "Read-only necessary-precursor audit. No free-surface node, potential, "
            "pressure, force, or response is modified."
        ),
        "sigma": float(args.sigma),
        "phase_count_per_motion_dof": int(args.phase_count),
        "motion_dofs": list(args.motion_dofs),
        "trajectory_count": len(rows),
        "maximum_spray_overturning_panel_count": maximum_overturning,
        "minimum_spray_outward_tangent_cosine": minimum_cosine,
        "minimum_spray_nonadjacent_distance_ratio": minimum_distance_ratio,
        "configuration": asdict(config),
        "derived": {
            "beam_m": beam,
            "speed_mps": speed,
            "omega_rad_s": omega,
            "period_s": period,
            "ground_plane_spacing_m": plane_spacing,
            "ground_plane_interval_s": plane_interval,
            "time_step_s": time_step,
            "initial_leading_offset_over_beam": initial_offset_beams,
            "initial_draft_m": initial_draft,
        },
        "output_csv": str(csv_path),
        "response_calibration_used": False,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(manifest_path)
    print(manifest["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
