from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from planing_seakeeping.forced_motion_identification import fit_periodic_harmonics
from planing_seakeeping.kernels.nonlinear_2dt.planing_forced_motion import (
    _extend_station_load_to_transom,
    _integrate_station_interval,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cumulative_trapezoid(values: np.ndarray, x: np.ndarray) -> np.ndarray:
    result = np.zeros_like(values, dtype=float)
    result[1:] = np.cumsum(0.5 * np.diff(x) * (values[:-1] + values[1:]))
    return result


def load_station_checkpoint(
    path: Path,
) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
    grouped: dict[int, list[tuple[float, float, float]]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            index = int(row["time_index"])
            grouped.setdefault(index, []).append(
                (
                    float(row["time_s"]),
                    float(row["x_from_transom_m"]),
                    float(row["force_density_n_m"]),
                )
            )
    if not grouped or sorted(grouped) != list(range(len(grouped))):
        raise ValueError("Station checkpoint needs contiguous zero-based time indices.")
    time: list[float] = []
    station_x: list[np.ndarray] = []
    station_force: list[np.ndarray] = []
    for index in range(len(grouped)):
        rows = sorted(grouped[index], key=lambda item: item[1])
        row_time = np.asarray([item[0] for item in rows], dtype=float)
        x = np.asarray([item[1] for item in rows], dtype=float)
        force = np.asarray([item[2] for item in rows], dtype=float)
        if len(x) < 2 or np.any(np.diff(x) <= 0.0):
            raise ValueError(f"Time index {index} needs two or more sorted stations.")
        if not np.allclose(row_time, row_time[0], rtol=0.0, atol=1e-12):
            raise ValueError(f"Time index {index} contains inconsistent time values.")
        time.append(float(row_time[0]))
        station_x.append(x)
        station_force.append(force)
    time_array = np.asarray(time, dtype=float)
    if np.any(np.diff(time_array) <= 0.0):
        raise ValueError("Station checkpoint times must be strictly increasing.")
    return time_array, station_x, station_force


def analyze_station_harmonics(
    time_s: np.ndarray,
    station_x_from_transom_m: list[np.ndarray],
    station_force_density_n_m: list[np.ndarray],
    *,
    omega_rad_s: float,
    lcg_from_transom_m: float,
    discard_cycles: float,
    retained_cycles: float,
    x_point_count: int = 801,
) -> tuple[list[dict[str, float]], dict[str, float | int]]:
    if len(time_s) != len(station_x_from_transom_m) or len(time_s) != len(
        station_force_density_n_m
    ):
        raise ValueError("Station histories must match the time axis.")
    if x_point_count < 101:
        raise ValueError("x_point_count must be at least 101 for moment closure.")
    maximum_x = max(float(np.max(values)) for values in station_x_from_transom_m)
    x_grid = np.linspace(0.0, maximum_x, int(x_point_count))
    density = np.zeros((len(time_s), len(x_grid)), dtype=float)
    exact_load = np.zeros((len(time_s), 2), dtype=float)
    for index, (x_raw, force_raw) in enumerate(
        zip(station_x_from_transom_m, station_force_density_n_m)
    ):
        x, force, _ = _extend_station_load_to_transom(x_raw, force_raw)
        density[index] = np.interp(x_grid, x, force, left=float(force[0]), right=0.0)
        exact_load[index] = _integrate_station_interval(
            x,
            force,
            lower_m=0.0,
            upper_m=float(x[-1]),
            lcg_from_transom_m=float(lcg_from_transom_m),
        )

    density_fit = fit_periodic_harmonics(
        time_s,
        density,
        omega_rad_s,
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=3,
    )
    exact_fit = fit_periodic_harmonics(
        time_s,
        exact_load,
        omega_rad_s,
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=3,
    )
    lever = x_grid - float(lcg_from_transom_m)
    sine_force_cumulative = _cumulative_trapezoid(density_fit.sine, x_grid)
    cosine_force_cumulative = _cumulative_trapezoid(density_fit.cosine, x_grid)
    sine_moment_cumulative = _cumulative_trapezoid(density_fit.sine * lever, x_grid)
    cosine_moment_cumulative = _cumulative_trapezoid(density_fit.cosine * lever, x_grid)
    mean_force_cumulative = _cumulative_trapezoid(density_fit.mean, x_grid)
    mean_moment_cumulative = _cumulative_trapezoid(density_fit.mean * lever, x_grid)

    rows: list[dict[str, float]] = []
    for index, x in enumerate(x_grid):
        rows.append(
            {
                "x_from_transom_m": float(x),
                "mean_force_density_n_m": float(density_fit.mean[index]),
                "sine_force_density_n_m": float(density_fit.sine[index]),
                "cosine_force_density_n_m": float(density_fit.cosine[index]),
                "harmonic_fit_residual_nrmse": float(density_fit.residual_nrmse[index]),
                "cumulative_mean_vertical_force_n": float(mean_force_cumulative[index]),
                "cumulative_mean_pitch_moment_nm": float(mean_moment_cumulative[index]),
                "cumulative_sine_vertical_force_n": float(sine_force_cumulative[index]),
                "cumulative_sine_pitch_moment_nm": float(sine_moment_cumulative[index]),
                "cumulative_cosine_vertical_force_n": float(cosine_force_cumulative[index]),
                "cumulative_cosine_pitch_moment_nm": float(cosine_moment_cumulative[index]),
            }
        )

    spatial = np.asarray(
        [
            [sine_force_cumulative[-1], sine_moment_cumulative[-1]],
            [cosine_force_cumulative[-1], cosine_moment_cumulative[-1]],
        ]
    )
    direct = np.vstack((exact_fit.sine, exact_fit.cosine))
    absolute_error = np.abs(spatial - direct)
    relative_error = absolute_error / np.maximum(np.abs(direct), np.finfo(float).eps)
    diagnostics: dict[str, float | int] = {
        "time_sample_count": int(len(time_s)),
        "retained_sample_count": int(density_fit.retained_sample_count),
        "retained_cycle_count": float(density_fit.retained_cycle_count),
        "x_point_count": int(len(x_grid)),
        "maximum_resolved_station_x_m": float(maximum_x),
        "max_density_fit_residual_nrmse": float(np.max(density_fit.residual_nrmse)),
        "direct_sine_vertical_force_n": float(direct[0, 0]),
        "direct_sine_pitch_moment_nm": float(direct[0, 1]),
        "direct_cosine_vertical_force_n": float(direct[1, 0]),
        "direct_cosine_pitch_moment_nm": float(direct[1, 1]),
        "spatial_sine_vertical_force_n": float(spatial[0, 0]),
        "spatial_sine_pitch_moment_nm": float(spatial[0, 1]),
        "spatial_cosine_vertical_force_n": float(spatial[1, 0]),
        "spatial_cosine_pitch_moment_nm": float(spatial[1, 1]),
        "max_spatial_harmonic_closure_relative_error": float(np.max(relative_error)),
    }
    return rows, diagnostics


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve a planing 2D+t sectional-load checkpoint into longitudinal harmonics."
    )
    parser.add_argument("station_csv", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--omega-rad-s", type=float, required=True)
    parser.add_argument("--lcg-from-transom-m", type=float, required=True)
    parser.add_argument("--discard-cycles", type=float, default=0.75)
    parser.add_argument("--retained-cycles", type=float, default=2.0)
    parser.add_argument("--x-points", type=int, default=801)
    return parser


def main() -> int:
    args = _parser().parse_args()
    source = args.station_csv.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    time, x, force = load_station_checkpoint(source)
    rows, diagnostics = analyze_station_harmonics(
        time,
        x,
        force,
        omega_rad_s=float(args.omega_rad_s),
        lcg_from_transom_m=float(args.lcg_from_transom_m),
        discard_cycles=float(args.discard_cycles),
        retained_cycles=float(args.retained_cycles),
        x_point_count=int(args.x_points),
    )
    csv_path = output / "station_first_harmonic_distribution.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "source": str(source),
        "source_sha256": _sha256(source),
        "method": "Sun_2007_Eq7.46_station_density_fit_then_longitudinal_integration",
        "coordinate_contract": "x_from_transom_positive_forward_force_up_moment_bow_up_about_cg",
        "omega_rad_s": float(args.omega_rad_s),
        "lcg_from_transom_m": float(args.lcg_from_transom_m),
        "discard_cycles": float(args.discard_cycles),
        "retained_cycles": float(args.retained_cycles),
        "response_calibration_used": False,
        "diagnostics": diagnostics,
        "output_csv_sha256": _sha256(csv_path),
    }
    (output / "station_harmonic_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
