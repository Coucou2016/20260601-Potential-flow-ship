from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import (
    MovingWedgeConfig,
    SinusoidalVerticalMotion,
    identify_moving_wedge_heave_coefficients,
    run_moving_wedge_time_history,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a non-production moving-wedge 2D free-surface BEM probe.")
    parser.add_argument("--out", type=Path, default=Path("outputs/moving_wedge_heave_probe"))
    parser.add_argument("--amplitude-m", type=float, default=0.001)
    parser.add_argument("--omega-rad-s", type=float, default=4.0)
    parser.add_argument("--cycles", type=float, default=3.0)
    parser.add_argument("--steps-per-cycle", type=int, default=48)
    parser.add_argument("--linearity-pair", action="store_true")
    parser.add_argument("--body-panels-per-side", type=int, default=5)
    parser.add_argument("--free-surface-panels-per-side", type=int, default=8)
    parser.add_argument("--gauss-order", type=int, default=6)
    return parser.parse_args()


def _run_case(config: MovingWedgeConfig, amplitude: float, args: argparse.Namespace):
    motion = SinusoidalVerticalMotion(amplitude_m=amplitude, omega_rad_s=args.omega_rad_s)
    period = 2.0 * np.pi / args.omega_rad_s
    dt = period / args.steps_per_cycle
    time = np.arange(0.0, args.cycles * period + 0.5 * dt, dt)
    started = perf_counter()
    history = run_moving_wedge_time_history(
        config,
        motion,
        time,
        rho_water_kg_m3=1000.0,
        gravity_m_s2=9.81,
    )
    coefficients = identify_moving_wedge_heave_coefficients(
        config,
        motion,
        history,
        rho_water_kg_m3=1000.0,
        gravity_m_s2=9.81,
        discard_cycles=1.0,
        retained_cycles=max(args.cycles - 1.0, 1.5),
    )
    return history, coefficients, perf_counter() - started


def main() -> None:
    args = _arguments()
    if args.cycles < 2.5 or args.steps_per_cycle < 24:
        raise ValueError("Probe requires at least 2.5 cycles and 24 steps per cycle.")
    args.out.mkdir(parents=True, exist_ok=True)
    config = MovingWedgeConfig(
        deadrise_rad=np.radians(20.0),
        mean_draft_m=0.12,
        chine_half_beam_m=0.55,
        free_surface_extent_m=3.0,
        water_depth_m=1.8,
        body_panels_per_side=args.body_panels_per_side,
        free_surface_panels_per_side=args.free_surface_panels_per_side,
        side_wall_panels=3,
        bottom_panels=10,
        gauss_order=args.gauss_order,
        damping_beach_length_m=1.0,
        damping_beach_beta0=0.3,
    )
    amplitudes = [args.amplitude_m]
    if args.linearity_pair:
        amplitudes.append(2.0 * args.amplitude_m)
    summaries = []
    first_harmonics = []
    for case_index, amplitude in enumerate(amplitudes):
        history, coefficients, runtime = _run_case(config, amplitude, args)
        first_harmonic = float(np.hypot(coefficients.harmonic_fit.sine[0], coefficients.harmonic_fit.cosine[0]))
        first_harmonics.append(first_harmonic)
        summaries.append(
            {
                "case_index": case_index,
                "amplitude_m": amplitude,
                "omega_rad_s": args.omega_rad_s,
                "sample_count": len(history.time_s),
                "runtime_s": runtime,
                "added_mass_per_length_kg_m": coefficients.added_mass_per_length_kg_m,
                "damping_per_length_kg_m_s": coefficients.damping_per_length_kg_m_s,
                "restoring_per_length_n_m2": coefficients.restoring_per_length_n_m2,
                "first_harmonic_force_amplitude_n_m": first_harmonic,
                "harmonic_fit_residual_nrmse": float(coefficients.harmonic_fit.residual_nrmse[0]),
                "max_potential_bvp_residual": float(np.max(history.potential_bvp_relative_residual)),
                "max_pressure_bvp_residual": float(np.max(history.pressure_bvp_relative_residual)),
                "max_free_surface_pressure_abs_pa": float(np.max(history.free_surface_pressure_max_abs_pa)),
                "max_contact_constraint_abs_m": float(np.max(history.contact_constraint_max_abs_m)),
                "response_calibration_used": False,
                "status": coefficients.status,
            }
        )
        with (args.out / f"timeseries_amplitude_{amplitude:.6g}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                (
                    "time_s",
                    "vertical_force_per_length_n_m",
                    "potential_bvp_relative_residual",
                    "pressure_bvp_relative_residual",
                    "free_surface_pressure_max_abs_pa",
                    "contact_constraint_max_abs_m",
                )
            )
            writer.writerows(
                zip(
                    history.time_s,
                    history.vertical_force_per_length_n_m,
                    history.potential_bvp_relative_residual,
                    history.pressure_bvp_relative_residual,
                    history.free_surface_pressure_max_abs_pa,
                    history.contact_constraint_max_abs_m,
                )
            )
    if len(first_harmonics) == 2:
        summaries[1]["first_harmonic_ratio_to_base"] = first_harmonics[1] / first_harmonics[0]
        summaries[1]["linearity_ratio_deviation_from_two"] = abs(first_harmonics[1] / first_harmonics[0] - 2.0)
    with (args.out / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = sorted({key for row in summaries for key in row})
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)
    manifest = {
        "model": "Sun_2007_Chapter2_moving_wedge_free_surface_BEM_development_probe",
        "formulae": ["Eq2.1-Eq2.11", "Eq6.1-Eq6.8"],
        "limitations": ["no_jet_cut", "no_spray_cut", "no_Troesch_acceptance"],
        "response_calibration_used": False,
        "config": config.__dict__,
        "summaries": summaries,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
