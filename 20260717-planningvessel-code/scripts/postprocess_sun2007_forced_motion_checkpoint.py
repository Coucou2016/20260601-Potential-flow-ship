from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from planing_seakeeping.forced_motion_identification import (
    extract_forced_motion_column,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Re-identify Sun (2007) forced-motion coefficients from a saved "
            "2D+t time-series checkpoint without rerunning the flow solver."
        )
    )
    parser.add_argument("timeseries", type=Path)
    parser.add_argument("restoring_matrices", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sigma", type=float, required=True)
    parser.add_argument("--motion-dof", choices=("heave", "pitch"), required=True)
    parser.add_argument("--motion-amplitude", type=float, default=None)
    parser.add_argument("--discard-cycles", type=float, default=0.75)
    parser.add_argument("--retained-cycles", type=float, default=2.0)
    parser.add_argument("--beam", type=float, default=0.318)
    parser.add_argument("--lcg-over-beam", type=float, default=1.47)
    parser.add_argument("--deadrise-deg", type=float, default=20.0)
    parser.add_argument("--trim-deg", type=float, default=4.0)
    parser.add_argument("--fn-b", type=float, default=2.5)
    parser.add_argument("--mean-wetted-length-over-b", type=float, default=3.0)
    parser.add_argument("--target-identifier", default="sun2007_troesch_prismatic_planing_hull")
    parser.add_argument("--rho", type=float, default=1000.0)
    parser.add_argument("--gravity", type=float, default=9.80665)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_restoring_matrices(path: Path) -> dict[str, np.ndarray]:
    matrices: dict[str, np.ndarray] = {}
    row_index = {"heave_force": 0, "pitch_moment": 1}
    column_index = {"heave": 0, "pitch": 1}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            component = row["component"]
            matrix = matrices.setdefault(component, np.zeros((2, 2), dtype=float))
            matrix[row_index[row["row"]], column_index[row["column"]]] = float(
                row["value"]
            )
    return matrices


def _read_component_loads(
    path: Path,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("The time-series checkpoint is empty.")
    time = np.asarray([float(row["time_s"]) for row in rows], dtype=float)
    suffix = "_vertical_force_n"
    components = sorted(
        key.removesuffix(suffix)
        for key in rows[0]
        if key.endswith(suffix)
        and f"{key.removesuffix(suffix)}_pitch_moment_nm" in rows[0]
    )
    loads = {
        component: np.asarray(
            [
                [
                    float(row[f"{component}_vertical_force_n"]),
                    float(row[f"{component}_pitch_moment_nm"]),
                ]
                for row in rows
            ],
            dtype=float,
        )
        for component in components
    }
    return time, loads


def _coefficient_scale(
    coefficient: str,
    *,
    beam: float,
    rho: float,
    gravity: float,
) -> float:
    if coefficient in ("A33", "B33"):
        length_power = 3
    elif coefficient in ("A35", "A53", "B35", "B53"):
        length_power = 4
    elif coefficient in ("A55", "B55"):
        length_power = 5
    else:
        raise ValueError(f"Unsupported forced-motion coefficient: {coefficient}.")
    scale = rho * beam**length_power
    if coefficient.startswith("B"):
        scale *= math.sqrt(gravity / beam)
    return float(scale)


def main() -> int:
    args = _parser().parse_args()
    timeseries = args.timeseries.resolve()
    restoring_path = args.restoring_matrices.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    beam = float(args.beam)
    rho = float(args.rho)
    gravity = float(args.gravity)
    lcg = float(args.lcg_over_beam) * beam
    omega = float(args.sigma) * math.sqrt(gravity / beam)
    amplitude = args.motion_amplitude
    if amplitude is None:
        amplitude = 0.036 * beam if args.motion_dof == "heave" else math.radians(0.43)

    time, component_loads = _read_component_loads(timeseries)
    restoring = _read_restoring_matrices(restoring_path)
    restoring_source_label = (
        f"external:{restoring_path.parent.name}/{restoring_path.name}"
    )
    restoring_source_sha256 = _sha256(restoring_path)
    rows: list[dict[str, object]] = []
    centers: list[dict[str, object]] = []
    coefficient_definition = (
        (("A33", 0), ("A53", 1), ("B33", 0), ("B53", 1))
        if args.motion_dof == "heave"
        else (("A35", 0), ("A55", 1), ("B35", 0), ("B55", 1))
    )
    for component, load in component_loads.items():
        matrix = restoring.get(component, np.zeros((2, 2), dtype=float))
        column_index = 0 if args.motion_dof == "heave" else 1
        identified = extract_forced_motion_column(
            time,
            load,
            motion_dof=args.motion_dof,
            omega_rad_s=omega,
            motion_amplitude=float(amplitude),
            restoring_column=matrix[:, column_index],
            discard_cycles=float(args.discard_cycles),
            retained_cycles=float(args.retained_cycles),
            fitted_harmonics=3,
        )
        for coefficient, row_index in coefficient_definition:
            dimensional = (
                identified.added_mass_column[row_index]
                if coefficient.startswith("A")
                else identified.damping_column[row_index]
            )
            rows.append(
                {
                    "component": component,
                    "sigma": float(args.sigma),
                    "omega_rad_s": omega,
                    "motion_dof": args.motion_dof,
                    "coefficient": coefficient,
                    "value_dimensional": float(dimensional),
                    "value_nondimensional": float(dimensional)
                    / _coefficient_scale(
                        coefficient,
                        beam=beam,
                        rho=rho,
                        gravity=gravity,
                    ),
                    "harmonic_fit_residual_nrmse": float(
                        identified.harmonic_fit.residual_nrmse[row_index]
                    ),
                    "restoring_matrix_is_zero": bool(not np.any(matrix)),
                    "restoring_subtraction": (
                        "zero_diagnostic_only"
                        if not np.any(matrix)
                        else restoring_source_label
                    ),
                    "restoring_matrices_sha256": restoring_source_sha256,
                    "target_identifier": args.target_identifier,
                    "beam_m": beam,
                    "deadrise_deg": float(args.deadrise_deg),
                    "trim_deg": float(args.trim_deg),
                    "fn_b": float(args.fn_b),
                    "mean_wetted_length_over_b": float(args.mean_wetted_length_over_b),
                    "lcg_from_transom_m": lcg,
                    "rho_water_kg_m3": rho,
                    "gravity_m_s2": gravity,
                    "matrix_coordinate_contract": (
                        "heave_up_pitch_bow_up_force_and_moment_about_cg"
                    ),
                    "response_calibration_used": False,
                }
            )
        if args.motion_dof == "heave":
            if abs(float(identified.damping_column[0])) <= 1e-14:
                damping_from_cg = float("nan")
                damping_from_transom = float("nan")
            else:
                damping_from_cg = float(
                    identified.damping_column[1] / identified.damping_column[0]
                )
                damping_from_transom = lcg + damping_from_cg
            centers.append(
                {
                    "component": component,
                    "sigma": float(args.sigma),
                    "damping_center_from_cg_m": damping_from_cg,
                    "damping_center_from_transom_m": damping_from_transom,
                    "damping_center_from_transom_over_beam": (
                        damping_from_transom / beam
                    ),
                    "response_calibration_used": False,
                }
            )

    coefficient_path = output / "identified_coefficients_reprocessed.csv"
    with coefficient_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if centers:
        with (output / "identified_load_centers_reprocessed.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(centers[0]))
            writer.writeheader()
            writer.writerows(centers)
    manifest = {
        "source": "Sun_2007_Eq7.46_to_7.47_checkpoint_reprocessing",
        "timeseries": str(timeseries),
        "timeseries_sha256": _sha256(timeseries),
        "restoring_matrices": str(restoring_path),
        "restoring_matrices_sha256": restoring_source_sha256,
        "restoring_subtraction": restoring_source_label,
        "sigma": float(args.sigma),
        "omega_rad_s": omega,
        "motion_dof": args.motion_dof,
        "motion_amplitude": float(amplitude),
        "discard_cycles": float(args.discard_cycles),
        "retained_cycles": float(args.retained_cycles),
        "beam_m": beam,
        "lcg_from_transom_m": lcg,
        "deadrise_deg": float(args.deadrise_deg),
        "trim_deg": float(args.trim_deg),
        "fn_b": float(args.fn_b),
        "mean_wetted_length_over_b": float(args.mean_wetted_length_over_b),
        "target_identifier": args.target_identifier,
        "matrix_coordinate_contract": "heave_up_pitch_bow_up_force_and_moment_about_cg",
        "rho_water_kg_m3": rho,
        "gravity_m_s2": gravity,
        "response_calibration_used": False,
    }
    (output / "postprocess_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
