from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import (
    MovingWedgeConfig,
    run_steady_planing_wedge_entry,
)
from scripts.steady_surface_snapshot import export_surface_history


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check the Sun (2007) steady planing base flow at fixed spatial "
            "resolution while refining the BEM time step."
        )
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/sun2007_steady_planing_convergence"),
    )
    parser.add_argument("--substeps", type=int, nargs="+", default=[8, 16, 32])
    parser.add_argument("--body-panels", type=int, default=12)
    parser.add_argument("--free-surface-panels", type=int, default=15)
    parser.add_argument("--uniform-near-body-panels", type=int, default=6)
    parser.add_argument("--smoothing-node-count", type=int, default=7)
    parser.add_argument(
        "--smoothing",
        choices=("on", "off", "both"),
        default="both",
    )
    parser.add_argument(
        "--knuckle-separation-model",
        choices=("clamped", "artificial_surface"),
        default="clamped",
    )
    parser.add_argument(
        "--pressure-interpolation",
        choices=("constant_panel", "match_potential"),
        default="constant_panel",
    )
    parser.add_argument("--jet-cut-distance-fraction", type=float, default=0.25)
    parser.add_argument("--jet-cut-threshold-over-beam", type=float, default=None)
    parser.add_argument("--export-surface-history", action="store_true")
    return parser


def _integrate_station_load(
    x_from_transom_m: np.ndarray,
    force_density_n_m: np.ndarray,
    *,
    lower_bound_m: float,
) -> float:
    x = np.asarray(x_from_transom_m, dtype=float)
    force = np.asarray(force_density_n_m, dtype=float)
    if not x[0] <= lower_bound_m <= x[-1]:
        raise ValueError("Station history does not bracket the integration lower bound.")
    boundary_force = float(np.interp(lower_bound_m, x, force))
    retained = x > lower_bound_m
    integral_x = np.concatenate(([lower_bound_m], x[retained]))
    integral_force = np.concatenate(([boundary_force], force[retained]))
    return float(np.trapezoid(integral_force, integral_x))


def _run_case(
    *,
    substeps: int,
    smoothing_enabled: bool,
    body_panels: int,
    free_surface_panels: int,
    uniform_near_body_panels: int,
    smoothing_node_count: int,
    knuckle_separation_model: str,
    pressure_interpolation: str,
    jet_cut_distance_fraction: float,
    jet_cut_threshold_over_beam: float | None,
    surface_archive: Path | None = None,
) -> tuple[dict[str, object], list[dict[str, float | int]]]:
    beam = 0.318
    gravity = 9.80665
    rho = 1000.0
    trim = math.radians(4.0)
    deadrise = math.radians(20.0)
    speed = 2.5 * math.sqrt(gravity * beam)
    wetted_length = 3.8 * beam
    section_planes = 11
    leading_offset = wetted_length / section_planes
    initial_draft = leading_offset * math.tan(trim)
    plane_interval = leading_offset / speed
    time_step = plane_interval / int(substeps)
    config = MovingWedgeConfig(
        deadrise_rad=deadrise,
        mean_draft_m=0.266 * beam,
        chine_half_beam_m=0.5 * beam,
        free_surface_extent_m=3.0 * beam,
        water_depth_m=2.5 * beam,
        body_panels_per_side=int(body_panels),
        free_surface_panels_per_side=int(free_surface_panels),
        side_wall_panels=6,
        bottom_panels=18,
        gauss_order=8,
        element_interpolation="linear_node",
        pressure_interpolation=pressure_interpolation,
        damping_beach_length_m=beam,
        initializer="wagner",
        free_surface_spacing_mode="body_matched_geometric",
        free_surface_smoothing_enabled=bool(smoothing_enabled),
        free_surface_smoothing_node_count=int(smoothing_node_count),
        free_surface_uniform_near_body_panel_count=int(uniform_near_body_panels),
        enforce_lateral_symmetry=True,
        use_symmetry_half_domain=True,
        knuckle_separation_model=knuckle_separation_model,
        jet_cut_enabled=True,
        jet_cut_distance_fraction=float(jet_cut_distance_fraction),
        jet_cut_threshold_m=(
            None
            if jet_cut_threshold_over_beam is None
            else float(jet_cut_threshold_over_beam) * beam
        ),
    )
    started = time.perf_counter()
    result = run_steady_planing_wedge_entry(
        config,
        speed_mps=speed,
        trim_rad=trim,
        wetted_length_m=wetted_length,
        time_step_s=time_step,
        initial_draft_m=initial_draft,
        rho_water_kg_m3=rho,
        gravity_m_s2=gravity,
    )
    elapsed = time.perf_counter() - started
    if surface_archive is not None:
        export_surface_history(surface_archive, result, config, speed=speed, trim=trim,
                               length=wetted_length, initial_draft=initial_draft)
    x_from_transom = wetted_length - (
        leading_offset + result.x_from_leading_edge_m
    )
    order = np.argsort(x_from_transom)
    x = np.asarray(x_from_transom[order], dtype=float)
    force = np.asarray(result.vertical_force_per_length_n_m[order], dtype=float)
    raw_force = _integrate_station_load(x, force, lower_bound_m=0.0)
    corrected_force = _integrate_station_load(x, force, lower_bound_m=0.5 * beam)
    scale = rho * speed**2 * beam**2
    first_separation_from_leading_over_beam = (
        None
        if result.first_separation_time_s is None
        else (
            leading_offset + speed * float(result.first_separation_time_s)
        )
        / beam
    )
    row = {
        "smoothing_enabled": bool(smoothing_enabled),
        "substeps_per_plane_interval": int(substeps),
        "time_step_s": float(time_step),
        "body_panels_per_side": int(body_panels),
        "free_surface_panels_per_side": int(free_surface_panels),
        "uniform_near_body_panel_count": int(uniform_near_body_panels),
        "free_surface_smoothing_node_count": int(smoothing_node_count),
        "knuckle_separation_model": str(knuckle_separation_model),
        "pressure_interpolation": str(pressure_interpolation),
        "jet_cut_distance_fraction": float(jet_cut_distance_fraction),
        "jet_cut_threshold_over_beam": jet_cut_threshold_over_beam,
        "separation_event_count": int(result.separation_event_count),
        "first_separation_from_leading_over_beam": (
            first_separation_from_leading_over_beam
        ),
        "raw_vertical_force_coefficient": raw_force / scale,
        "stern_corrected_vertical_force_coefficient": corrected_force / scale,
        "max_potential_bvp_relative_residual": result.max_potential_bvp_relative_residual,
        "max_pressure_bvp_relative_residual": result.max_pressure_bvp_relative_residual,
        "max_contact_constraint_abs_m": result.max_contact_constraint_abs_m,
        "maximum_jet_cut_count": max(state.jet_cut_count for state in result.states),
        "runtime_s": float(elapsed),
        "response_calibration_used": False,
    }
    profile = []
    for index, (station, sectional_force, state) in enumerate(
        zip(x, force, reversed(result.states))
    ):
        profile.append(
            {
                "station_index": int(index),
                "x_from_transom_m": float(station),
                "x_from_leading_edge_m": float(wetted_length - station),
                "x_from_leading_edge_over_beam": float(
                    (wetted_length - station) / beam
                ),
                "sectional_force_n_m": float(sectional_force),
                # Retained for compatibility with the earlier diagnostic files.
                "sectional_force_coefficient": float(
                    sectional_force / (rho * speed**2 * beam)
                ),
                "sectional_force_over_rho_u2_b": float(
                    sectional_force / (rho * speed**2 * beam)
                ),
                "sectional_force_over_half_rho_u2_b": float(
                    sectional_force / (0.5 * rho * speed**2 * beam)
                ),
                "right_contact_half_beam_m": float(state.right_free_y_m[0]),
                "right_contact_half_beam_ratio": float(
                    state.right_free_y_m[0] / beam
                ),
                "jet_cut_count": int(state.jet_cut_count),
            }
        )
    return row, profile


def main() -> int:
    args = _parser().parse_args()
    if any(value < 1 for value in args.substeps):
        raise ValueError("All substep counts must be positive.")
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), root/'scripts/steady_surface_snapshot.py',
               *sorted((root/'planing_seakeeping/kernels/nonlinear_2dt').rglob('*.py'))]
    (output/'run_contract.json').write_text(json.dumps({
        'scope': 'Existing steady 2Dt diagnostic rerun; not a matched linear baseflow or experimental acceptance',
        'arguments': {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        'source_sha256': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
        'response_calibration_used': False,
        'physical_acceptance': 'NOT_PASSED',
    }, indent=2), encoding='utf-8')
    smoothing_values = {
        "on": [True],
        "off": [False],
        "both": [False, True],
    }[args.smoothing]
    rows: list[dict[str, object]] = []
    for smoothing_enabled in smoothing_values:
        previous: dict[str, object] | None = None
        for substeps in sorted(set(args.substeps)):
            row, profile = _run_case(
                substeps=substeps,
                smoothing_enabled=smoothing_enabled,
                body_panels=args.body_panels,
                free_surface_panels=args.free_surface_panels,
                uniform_near_body_panels=args.uniform_near_body_panels,
                smoothing_node_count=args.smoothing_node_count,
                knuckle_separation_model=args.knuckle_separation_model,
                pressure_interpolation=args.pressure_interpolation,
                jet_cut_distance_fraction=args.jet_cut_distance_fraction,
                jet_cut_threshold_over_beam=args.jet_cut_threshold_over_beam,
                surface_archive=(output/f'surface_smoothing_{smoothing_enabled}_substeps_{substeps}.npz'
                                 if args.export_surface_history else None),
            )
            for key in (
                "raw_vertical_force_coefficient",
                "stern_corrected_vertical_force_coefficient",
            ):
                change_key = f"{key}_change_from_previous_percent"
                if previous is None:
                    row[change_key] = None
                else:
                    prior = float(previous[key])
                    row[change_key] = 100.0 * abs(float(row[key]) - prior) / abs(prior)
            rows.append(row)
            profile_path = output / (
                f"station_profile_smoothing_{str(smoothing_enabled).lower()}_"
                f"substeps_{substeps}_body_{args.body_panels}_"
                f"free_{args.free_surface_panels}_"
                f"separation_{args.knuckle_separation_model}.csv"
            )
            with profile_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(profile[0]))
                writer.writeheader()
                writer.writerows(profile)
            previous = row
            print(
                f"smoothing={smoothing_enabled} substeps={substeps} "
                f"raw={row['raw_vertical_force_coefficient']:.7f} "
                f"corrected={row['stern_corrected_vertical_force_coefficient']:.7f} "
                f"jet={row['maximum_jet_cut_count']}",
                flush=True,
            )

    csv_path = output / "steady_planing_convergence.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "physical_acceptance": "NOT_PASSED",
        "linear_background_connection": "NOT_IMPLEMENTED",
        "benchmark": "Sun_2007_Table7.1_Fig7.4_eta3_zero_steady_base_flow",
        "purpose": "numerical_diagnostic_not_a_Troesch_coefficient_acceptance",
        "sectional_force_normalization": {
            "legacy_column": "sectional_force_coefficient=F3_2D/(rho*U^2*B)",
            "sun_2007_fig7_10_column": (
                "sectional_force_over_half_rho_u2_b=F3_2D/(0.5*rho*U^2*B)"
            ),
        },
        "rows": rows,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
