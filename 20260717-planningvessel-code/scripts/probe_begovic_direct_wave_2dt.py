from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import MovingWedgeConfig
from planing_seakeeping.kernels.nonlinear_2dt.planing_forced_motion import (
    PlaningForcedMotionCase,
    identify_planing_incident_wave_excitation,
    run_planing_forced_motion_2dt,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Identify Begovic fixed-hull regular-wave excitation with the direct "
            "Sun--Faltinsen nonlinear 2D+t cross-plane formulation."
        )
    )
    parser.add_argument("--fn-b", type=float, default=2.82)
    parser.add_argument("--case-code", action="append", default=[])
    parser.add_argument("--cycles", type=float, default=3.0)
    parser.add_argument("--discard-cycles", type=float, default=1.5)
    parser.add_argument("--retained-cycles", type=float, default=1.5)
    parser.add_argument("--section-planes", type=int, default=11)
    parser.add_argument("--bem-substeps-per-plane", type=int, default=16)
    parser.add_argument("--body-panels", type=int, default=12)
    parser.add_argument("--free-surface-panels", type=int, default=15)
    parser.add_argument("--side-panels", type=int, default=6)
    parser.add_argument("--bottom-panels", type=int, default=18)
    parser.add_argument("--gauss-order", type=int, default=8)
    parser.add_argument("--parallel-workers", type=int, default=1)
    parser.add_argument("--wave-amplitude-scale", type=float, default=1.0)
    parser.add_argument(
        "--transom-correction",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Replace the aft 0.1B 2D+t load with the source-defined Sun "
            "Chapter 7 transom-separation patch. The default preserves the "
            "uncorrected 2D+t route."
        ),
    )
    parser.add_argument("--write-station-timeseries", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _progress(label: str):
    last_bucket = -1

    def report(index: int, count: int, time_s: float) -> None:
        nonlocal last_bucket
        bucket = int(20 * index / max(count, 1))
        if bucket != last_bucket or index == count:
            print(
                f"{label}: {100.0 * index / max(count, 1):5.1f}% "
                f"t={time_s:.6g} s",
                flush=True,
            )
            last_bucket = bucket

    return report


def _station_timeseries(result) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for time_index, time_s in enumerate(result.time_s):
        count = int(result.active_plane_count[time_index])
        for station_index in range(count):
            rows.append(
                {
                    "time_s": float(time_s),
                    "station_index": station_index,
                    "x_from_transom_m": float(
                        result.station_x_from_transom_m[time_index, station_index]
                    ),
                    "force_density_n_m": float(
                        result.station_force_density_n_m[time_index, station_index]
                    ),
                    "creation_parameter_s": float(
                        result.station_creation_parameter_s[time_index, station_index]
                    ),
                    "age_parameter_s": float(
                        result.station_age_parameter_s[time_index, station_index]
                    ),
                    "contact_half_beam_m": float(
                        result.station_contact_half_beam_m[time_index, station_index]
                    ),
                    "jet_cut_count": int(
                        result.station_jet_cut_count[time_index, station_index]
                    ),
                }
            )
    return pd.DataFrame(rows)


def main() -> int:
    args = _parser().parse_args()
    if not np.isfinite(args.wave_amplitude_scale) or args.wave_amplitude_scale <= 0.0:
        raise ValueError("--wave-amplitude-scale must be finite and positive.")
    root = Path(__file__).resolve().parents[1]
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    benchmark = root / "benchmarks" / "begovic2020"
    hull_path = benchmark / "begovic2020_mono_hull.csv"
    running_path = benchmark / "begovic2014_mono_calm_water_running_state.csv"
    wave_path = benchmark / "begovic2020_regular_wave_conditions.csv"
    hull = pd.read_csv(hull_path).iloc[0]
    running_table = pd.read_csv(running_path)
    selected_running = running_table[
        np.isclose(running_table["fn_b"].to_numpy(dtype=float), args.fn_b)
    ]
    if len(selected_running) != 1:
        raise ValueError(f"Exactly one Begovic running state is required for FnB={args.fn_b}.")
    running = selected_running.iloc[0]
    wave_table = pd.read_csv(wave_path)
    case_codes = args.case_code or ["C7"]
    if len(set(case_codes)) != len(case_codes):
        raise ValueError("--case-code values must be unique.")
    selected_waves = wave_table[wave_table["case_code"].isin(case_codes)].copy()
    missing = sorted(set(case_codes) - set(selected_waves["case_code"]))
    if missing:
        raise ValueError(f"Unknown Begovic case codes: {missing}")
    selected_waves["_order"] = selected_waves["case_code"].map(
        {code: index for index, code in enumerate(case_codes)}
    )
    selected_waves = selected_waves.sort_values("_order")

    beam = float(hull["beam_m"])
    rho = 1000.0
    gravity = 9.80665
    speed = float(args.fn_b) * math.sqrt(gravity * beam)
    trim = math.radians(float(running["running_trim_deg"]))
    mean_wetted_length_over_beam = float(running["mean_wetted_length_m"]) / beam
    if not np.isclose(args.fn_b, 2.82, rtol=1.0e-4, atol=1.0e-8):
        raise ValueError(
            "The current direct-wave prototype has a frozen, source-traced keel wet length only for FnB=2.82."
        )
    keel_wetted_length = 3.41460239534929 * beam
    initial_leading_offset = 0.3104183995772082 * beam
    initial_draft = initial_leading_offset * math.tan(trim)
    lcg = float(hull["lcg_from_transom_m"])
    active_duration = (keel_wetted_length - initial_leading_offset) / speed
    plane_interval = active_duration / float(args.section_planes - 1)
    remesh_interval = plane_interval / 8.0

    config = MovingWedgeConfig(
        deadrise_rad=math.radians(float(hull["deadrise_deg"])),
        mean_draft_m=0.239617422555 * beam,
        chine_half_beam_m=0.5 * beam,
        free_surface_extent_m=3.0 * beam,
        water_depth_m=2.5 * beam,
        body_panels_per_side=args.body_panels,
        free_surface_panels_per_side=args.free_surface_panels,
        side_wall_panels=args.side_panels,
        bottom_panels=args.bottom_panels,
        gauss_order=args.gauss_order,
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
        jet_cut_threshold_m=0.03325555538987225 * beam,
        jet_cut_max_corrective_passes=8,
    )

    excitation_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    snapshot = {
        "schema": "begovic_direct_incident_wave_2dt_input_v1",
        "source_files": {
            str(path.relative_to(root)): _sha256(path)
            for path in (hull_path, running_path, wave_path)
        },
        "fn_b": args.fn_b,
        "case_codes": case_codes,
        "wave_amplitude_scale": args.wave_amplitude_scale,
        "wave_amplitude_scale_role": (
            "production_source_amplitude"
            if np.isclose(args.wave_amplitude_scale, 1.0)
            else "linearity_and_stability_diagnostic_only"
        ),
        "running_state": running.to_dict(),
        "speed_mps_from_fn_b": speed,
        "reported_rounded_speed_mps": float(running["speed_m_s"]),
        "hull": hull.to_dict(),
        "keel_wetted_length_m": keel_wetted_length,
        "mean_wetted_length_over_beam": mean_wetted_length_over_beam,
        "initial_leading_offset_m": initial_leading_offset,
        "initial_draft_m": initial_draft,
        "ground_plane_interval_s": plane_interval,
        "parallel_workers": args.parallel_workers,
        "transom_correction_enabled": args.transom_correction,
        "transom_correction_source": (
            "Sun_2007_Eq7.19_to_7.22_aft_0.1B_patch"
            if args.transom_correction
            else "disabled"
        ),
        "moving_wedge_config": config.__dict__,
        "response_calibration_used": False,
    }
    (output / "run_input_snapshot.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    for wave in selected_waves.itertuples(index=False):
        omega0 = float(wave.wave_omega_rad_s)
        wavenumber = float(wave.wave_number_rad_m)
        encounter = omega0 + wavenumber * speed
        period = 2.0 * math.pi / encounter
        minimum_substeps = max(
            int(args.bem_substeps_per_plane),
            int(math.ceil(24.0 * plane_interval / period)),
        )
        time_step = plane_interval / float(minimum_substeps)
        case = PlaningForcedMotionCase(
            speed_mps=speed,
            mean_trim_rad=trim,
            wetted_length_m=keel_wetted_length,
            lcg_from_transom_m=lcg,
            motion_dof="fixed",
            motion_amplitude=0.0,
            omega_rad_s=encounter,
            duration_s=float(args.cycles) * period,
            time_step_s=time_step,
            initial_draft_m=initial_draft,
            ground_plane_interval_s=plane_interval,
            ground_plane_handoff_mode="fixed_earth_grid",
            rho_water_kg_m3=rho,
            gravity_m_s2=gravity,
            mean_wetted_length_beam_ratio=mean_wetted_length_over_beam,
            transom_correction_enabled=args.transom_correction,
            incident_wave_amplitude_m=(
                float(wave.wave_amplitude_m) * float(args.wave_amplitude_scale)
            ),
            incident_wave_omega0_rad_s=omega0,
            incident_wave_wavenumber_rad_m=wavenumber,
            metadata={
                "benchmark": "Begovic_2014_monohedral_EFD_republished_2020",
                "case_code": str(wave.case_code),
                "calculation_role": "direct_fixed_hull_incident_wave_excitation",
                "response_calibration_used": False,
                "transom_correction_enabled": args.transom_correction,
            },
        )
        result = run_planing_forced_motion_2dt(
            config,
            case,
            progress_callback=_progress(str(wave.case_code)),
            parallel_workers=args.parallel_workers,
        )
        identified = identify_planing_incident_wave_excitation(
            result,
            case,
            discard_cycles=float(args.discard_cycles),
            retained_cycles=float(args.retained_cycles),
            fitted_harmonics=3,
        )
        for component, values in identified.component_excitation_per_wave_amplitude.items():
            excitation_rows.append(
                {
                    "case_code": str(wave.case_code),
                    "fn_b": args.fn_b,
                    "omega0_rad_s": omega0,
                    "omega_e_rad_s": encounter,
                    "wavenumber_rad_m": wavenumber,
                    "wave_amplitude_m": case.incident_wave_amplitude_m,
                    "source_wave_amplitude_m": float(wave.wave_amplitude_m),
                    "wave_amplitude_scale": args.wave_amplitude_scale,
                    "component": component,
                    "transom_correction_enabled": args.transom_correction,
                    "heave_force_real_n_per_m": float(values[0].real),
                    "heave_force_imag_n_per_m": float(values[0].imag),
                    "pitch_moment_real_nm_per_m": float(values[1].real),
                    "pitch_moment_imag_nm_per_m": float(values[1].imag),
                    "response_calibration_used": False,
                }
            )
        diagnostic_rows.append(
            {
                "case_code": str(wave.case_code),
                "omega_e_rad_s": encounter,
                "time_step_s": time_step,
                "bem_substeps_per_plane": minimum_substeps,
                "maximum_harmonic_residual_nrmse": float(
                    np.max(identified.harmonic_fit.residual_nrmse)
                ),
                "maximum_potential_bvp_relative_residual": float(
                    np.max(result.max_potential_bvp_relative_residual)
                ),
                "maximum_pressure_bvp_relative_residual": float(
                    np.max(result.max_pressure_bvp_relative_residual)
                ),
                "maximum_free_surface_pressure_abs_pa": float(
                    np.max(result.max_free_surface_pressure_abs_pa)
                ),
                "minimum_active_plane_count": int(np.min(result.active_plane_count)),
                "maximum_active_plane_count": int(np.max(result.active_plane_count)),
                "transom_correction_enabled": args.transom_correction,
                "maximum_transom_correction_length_m": float(
                    np.max(result.transom_correction_length_m)
                ),
                "response_calibration_used": False,
            }
        )
        timeseries = pd.DataFrame(
            {
                "time_s": result.time_s,
                "vertical_force_n": result.generalized_load[:, 0],
                "pitch_moment_nm": result.generalized_load[:, 1],
                "bem_vertical_force_n": result.bem_generalized_load[:, 0],
                "bem_pitch_moment_nm": result.bem_generalized_load[:, 1],
                "front_vertical_force_n": result.front_generalized_load[:, 0],
                "front_pitch_moment_nm": result.front_generalized_load[:, 1],
                "transom_vertical_force_n": result.transom_generalized_load[:, 0],
                "transom_pitch_moment_nm": result.transom_generalized_load[:, 1],
                "transom_correction_length_m": result.transom_correction_length_m,
                "active_plane_count": result.active_plane_count,
                "max_potential_bvp_relative_residual": result.max_potential_bvp_relative_residual,
                "max_pressure_bvp_relative_residual": result.max_pressure_bvp_relative_residual,
            }
        )
        timeseries.to_csv(
            output / f"timeseries_{wave.case_code}.csv", index=False
        )
        if args.write_station_timeseries:
            _station_timeseries(result).to_csv(
                output / f"station_timeseries_{wave.case_code}.csv", index=False
            )

    excitation_table = pd.DataFrame(excitation_rows)
    diagnostics = pd.DataFrame(diagnostic_rows)
    excitation_table.to_csv(output / "direct_wave_excitation.csv", index=False)
    diagnostics.to_csv(output / "direct_wave_diagnostics.csv", index=False)
    status = bool(
        np.isfinite(excitation_table.select_dtypes(include=[np.number])).all().all()
        and (diagnostics["maximum_harmonic_residual_nrmse"] <= 0.05).all()
        and (diagnostics["maximum_potential_bvp_relative_residual"] <= 1.0e-8).all()
        and (diagnostics["maximum_pressure_bvp_relative_residual"] <= 1.0e-8).all()
    )
    summary = {
        "status": "prototype_pass" if status else "prototype_fail",
        "case_count": len(selected_waves),
        "maximum_harmonic_residual_nrmse": float(
            diagnostics["maximum_harmonic_residual_nrmse"].max()
        ),
        "transom_correction_enabled": args.transom_correction,
        "response_calibration_used": False,
        "gate2_acceptance_claimed": False,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if status else 2


if __name__ == "__main__":
    raise SystemExit(main())
