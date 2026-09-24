from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from planing_seakeeping.forced_motion_identification import ForcedMotionMatrices
from planing_seakeeping.forced_motion_validation import compare_sun2007_troesch


EXPECTED_SIGMAS = (0.85, 1.13, 1.4, 1.7, 1.95)
COEFFICIENT_INDEX = {
    "A33": ("added_mass", 0, 0),
    "A35": ("added_mass", 0, 1),
    "A53": ("added_mass", 1, 0),
    "A55": ("added_mass", 1, 1),
    "B33": ("damping", 0, 0),
    "B35": ("damping", 0, 1),
    "B53": ("damping", 1, 0),
    "B55": ("damping", 1, 1),
}
FROZEN_ARGUMENTS = (
    "target_identifier",
    "beam_m",
    "rho_water_kg_m3",
    "gravity_m_s2",
    "deadrise_deg",
    "trim_deg",
    "fn_b",
    "mean_wetted_length_over_beam",
    "chine_wetting_offset_over_beam",
    "keel_wetted_length_over_beam",
    "lcg_over_beam",
    "vcg_over_beam",
    "mean_draft_over_beam",
    "heave_amplitude_over_beam",
    "pitch_amplitude_deg",
    "cycles",
    "discard_cycles",
    "retained_cycles",
    "section_planes",
    "bem_substeps_per_plane",
    "ground_plane_handoff_mode",
    "ground_plane_spacing_rule",
    "body_panels",
    "free_surface_panels",
    "side_panels",
    "bottom_panels",
    "gauss_order",
    "element_interpolation",
    "pressure_interpolation",
    "symmetry_half_domain",
    "transom_correction",
    "transom_keel_reduction",
    "initial_leading_offset_beams",
    "knuckle_separation_model",
    "jet_cut",
    "jet_cut_distance_fraction",
    "jet_cut_threshold_over_beam",
    "jet_cut_max_corrective_passes",
    "free_surface_spacing_mode",
    "free_surface_remesh_updates_per_plane",
    "free_surface_smoothing",
    "free_surface_smoothing_node_count",
    "free_surface_smoothing_updates_per_plane",
    "uniform_near_body_panels",
    "restoring_mode",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate five independently checkpointed Sun--Troesch runs."
    )
    parser.add_argument("run_dirs", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("benchmarks/sun2007_troesch_forced_motion_coefficients.csv"),
    )
    parser.add_argument("--harmonic-residual-limit", type=float, default=0.05)
    parser.add_argument("--bvp-residual-limit", type=float, default=1.0e-8)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _all_coefficient_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    total_rows = [row for row in rows if row["component"] == "total"]
    if len(total_rows) != 8:
        raise ValueError(f"{path} must contain eight total-component coefficients.")
    if {row["coefficient"] for row in total_rows} != set(COEFFICIENT_INDEX):
        raise ValueError(f"{path} does not contain the required eight coefficients.")
    return rows


def _matrix_from_rows(rows: list[dict[str, str]]) -> ForcedMotionMatrices:
    added_mass = np.zeros((2, 2), dtype=float)
    damping = np.zeros((2, 2), dtype=float)
    omega_values = {float(row["omega_rad_s"]) for row in rows}
    if len(omega_values) != 1:
        raise ValueError("Each source run must contain one unique angular frequency.")
    for row in rows:
        matrix_name, matrix_row, matrix_column = COEFFICIENT_INDEX[row["coefficient"]]
        matrix = added_mass if matrix_name == "added_mass" else damping
        matrix[matrix_row, matrix_column] = float(row["value_dimensional"])
    if not np.isfinite(added_mass).all() or not np.isfinite(damping).all():
        raise ValueError("Forced-motion coefficients must be finite.")
    return ForcedMotionMatrices(
        omega_rad_s=omega_values.pop(),
        added_mass=added_mass,
        damping=damping,
        columns=(),  # type: ignore[arg-type]
        metadata={"aggregated_from_checkpointed_run": True},
    )


def _restoring_offset_diagnostics(
    comparison_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    point_rows: list[dict[str, object]] = []
    for row in comparison_rows:
        coefficient = str(row["coefficient"])
        if not coefficient.startswith("A"):
            continue
        sigma = float(row["sigma"])
        delta = (float(row["reference_value"]) - float(row["computed_value"])) * sigma**2
        point_rows.append(
            {
                "coefficient": coefficient,
                "sigma": sigma,
                "reference_minus_computed_added_mass": float(row["reference_value"])
                - float(row["computed_value"]),
                "equivalent_restoring_offset_nondimensional": delta,
                "interpretation": (
                    "A frequency-independent value across sigma is the 1/omega^2 "
                    "signature of a restoring-coefficient mismatch."
                ),
                "used_for_acceptance": False,
            }
        )

    summary_rows: list[dict[str, object]] = []
    for coefficient in ("A33", "A35", "A53", "A55"):
        values = np.asarray(
            [
                float(row["equivalent_restoring_offset_nondimensional"])
                for row in point_rows
                if row["coefficient"] == coefficient
            ],
            dtype=float,
        )
        if values.size != len(EXPECTED_SIGMAS):
            raise ValueError(f"Restoring-offset diagnosis requires five {coefficient} values.")
        mean = float(np.mean(values))
        standard_deviation = float(np.std(values))
        span = float(np.max(values) - np.min(values))
        relative_standard_deviation = (
            standard_deviation / abs(mean) if abs(mean) > 1.0e-12 else 0.0
        )
        restoring_offset_like = bool(
            abs(mean) > 1.0e-6 and relative_standard_deviation <= 0.10
        )
        summary_rows.append(
            {
                "coefficient": coefficient,
                "point_count": int(values.size),
                "mean_equivalent_restoring_offset_nondimensional": mean,
                "minimum_equivalent_restoring_offset_nondimensional": float(np.min(values)),
                "maximum_equivalent_restoring_offset_nondimensional": float(np.max(values)),
                "standard_deviation": standard_deviation,
                "relative_standard_deviation": relative_standard_deviation,
                "restoring_offset_like": restoring_offset_like,
                "used_for_acceptance": False,
            }
        )
    return point_rows, summary_rows


def _damping_load_center_diagnostics(
    combined_rows: list[dict[str, object]],
    comparison_rows: list[dict[str, object]],
    *,
    lcg_over_beam: float,
) -> list[dict[str, object]]:
    reference = {
        (float(row["sigma"]), str(row["coefficient"])): float(row["reference_value"])
        for row in comparison_rows
        if str(row["coefficient"]).startswith("B")
    }
    grouped: dict[tuple[float, str], dict[str, float]] = {}
    for row in combined_rows:
        coefficient = str(row["coefficient"])
        if not coefficient.startswith("B"):
            continue
        key = (float(row["sigma"]), str(row["component"]))
        grouped.setdefault(key, {})[coefficient] = float(row["value_nondimensional"])

    rows: list[dict[str, object]] = []
    for (sigma, component), values in sorted(grouped.items()):
        for motion_column, force_name, moment_name in (
            ("heave", "B33", "B53"),
            ("pitch", "B35", "B55"),
        ):
            if force_name not in values or moment_name not in values:
                continue
            force = values[force_name]
            moment = values[moment_name]
            computed_center = (
                float("nan") if abs(force) <= 1.0e-12 else lcg_over_beam + moment / force
            )
            reference_force = reference[(sigma, force_name)]
            reference_moment = reference[(sigma, moment_name)]
            reference_center = lcg_over_beam + reference_moment / reference_force
            rows.append(
                {
                    "component": component,
                    "sigma": sigma,
                    "motion_column": motion_column,
                    "force_damping_coefficient": force_name,
                    "moment_damping_coefficient": moment_name,
                    "computed_force_damping_nondimensional": force,
                    "computed_moment_damping_nondimensional": moment,
                    "computed_center_from_transom_over_beam": computed_center,
                    "reference_center_from_transom_over_beam": reference_center,
                    "center_error_over_beam": computed_center - reference_center,
                    "used_for_acceptance": False,
                }
            )
    return rows


def aggregate(
    run_dirs: list[Path],
    *,
    output: Path,
    benchmark: Path,
    harmonic_residual_limit: float = 0.05,
    bvp_residual_limit: float = 1.0e-8,
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    if len(run_dirs) != 5:
        raise ValueError("Exactly five one-frequency run directories are required.")

    matrices: list[ForcedMotionMatrices] = []
    combined_rows: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []
    frozen_reference: dict[str, object] | None = None
    restoring_sha_reference: str | None = None
    sigma_values: list[float] = []
    maximum_harmonic_residual = 0.0
    maximum_bvp_residual = 0.0
    response_calibration_used = False

    for raw_directory in run_dirs:
        directory = raw_directory.resolve()
        snapshot_path = directory / "run_input_snapshot.json"
        coefficient_path = directory / "identified_coefficients.csv"
        diagnostics_path = directory / "run_diagnostics.json"
        restoring_path = directory / "restoring_diagnostics.json"
        for required_path in (
            snapshot_path,
            coefficient_path,
            diagnostics_path,
            restoring_path,
        ):
            if not required_path.exists():
                raise FileNotFoundError(required_path)

        snapshot = _read_json(snapshot_path)
        arguments = snapshot["arguments"]
        sigmas = [float(value) for value in arguments["sigmas"]]
        if len(sigmas) != 1:
            raise ValueError(f"{directory} is not a one-frequency run.")
        sigma = sigmas[0]
        sigma_values.append(sigma)
        frozen = {key: arguments.get(key) for key in FROZEN_ARGUMENTS}
        if frozen_reference is None:
            frozen_reference = frozen
        elif frozen != frozen_reference:
            differing = [key for key in FROZEN_ARGUMENTS if frozen[key] != frozen_reference[key]]
            raise ValueError(f"Source runs use inconsistent arguments: {differing}.")

        restoring = _read_json(restoring_path)
        restoring_sha = str(restoring.get("source_sha256", ""))
        if not restoring_sha:
            raise ValueError("A traced external restoring-matrix SHA-256 is required.")
        if restoring_sha_reference is None:
            restoring_sha_reference = restoring_sha
        elif restoring_sha != restoring_sha_reference:
            raise ValueError("Source runs use different restoring matrices.")

        all_rows = _all_coefficient_rows(coefficient_path)
        rows = [row for row in all_rows if row["component"] == "total"]
        row_sigmas = {float(row["sigma"]) for row in rows}
        if len(row_sigmas) != 1 or not math.isclose(row_sigmas.pop(), sigma, abs_tol=5e-9):
            raise ValueError(f"Coefficient sigma does not match {directory} input snapshot.")
        matrices.append(_matrix_from_rows(rows))
        for row in rows:
            maximum_harmonic_residual = max(
                maximum_harmonic_residual,
                float(row["harmonic_fit_residual_nrmse"]),
            )
            response_calibration_used = response_calibration_used or _as_bool(
                row["response_calibration_used"]
            )
        for row in all_rows:
            combined_rows.append({"source_directory": str(directory), **row})

        run_diagnostics = _read_json(diagnostics_path)
        if not isinstance(run_diagnostics, list) or len(run_diagnostics) != 1:
            raise ValueError(f"{diagnostics_path} must contain one frequency diagnostic.")
        diagnostic = run_diagnostics[0]
        residual_values = [
            float(value)
            for key, value in diagnostic.items()
            if key.endswith("_residual") and value is not None
        ]
        if residual_values:
            maximum_bvp_residual = max(maximum_bvp_residual, max(residual_values))
        response_calibration_used = response_calibration_used or bool(
            snapshot.get("response_calibration_used", False)
        )
        source_rows.append(
            {
                "source_directory": str(directory),
                "sigma": sigma,
                "input_snapshot_sha256": _sha256(snapshot_path),
                "identified_coefficients_sha256": _sha256(coefficient_path),
                "run_diagnostics_sha256": _sha256(diagnostics_path),
                "restoring_source_sha256": restoring_sha,
                "maximum_harmonic_residual_nrmse": max(
                    float(row["harmonic_fit_residual_nrmse"]) for row in rows
                ),
                "maximum_bvp_relative_residual": max(residual_values, default=0.0),
                "response_calibration_used": False,
            }
        )

    if not np.allclose(sorted(sigma_values), EXPECTED_SIGMAS, atol=5e-9, rtol=0.0):
        raise ValueError(f"Runs must cover exactly {EXPECTED_SIGMAS}; received {sigma_values}.")
    assert frozen_reference is not None
    model_variant = (
        "sun_2dt_with_stern_3d_correction"
        if bool(frozen_reference["transom_correction"])
        or bool(frozen_reference["transom_keel_reduction"])
        else "sun_2dt_without_stern_3d_correction"
    )
    comparison = compare_sun2007_troesch(
        matrices,
        benchmark_csv_path=benchmark,
        model_variant=model_variant,
        beam_m=float(frozen_reference["beam_m"]),
        rho_water_kg_m3=float(frozen_reference["rho_water_kg_m3"]),
        gravity_m_s2=float(frozen_reference["gravity_m_s2"]),
        frequency_match_tolerance=5e-3,
    )
    harmonic_passed = maximum_harmonic_residual <= harmonic_residual_limit
    bvp_passed = maximum_bvp_residual <= bvp_residual_limit
    passed = bool(
        comparison.passed
        and harmonic_passed
        and bvp_passed
        and not response_calibration_used
    )

    def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(output / "combined_identified_coefficients.csv", combined_rows)
    write_csv(output / "source_runs.csv", sorted(source_rows, key=lambda row: float(row["sigma"])))
    comparison_rows = [row.__dict__ for row in comparison.comparisons]
    restoring_offset_points, restoring_offset_summary = _restoring_offset_diagnostics(
        comparison_rows
    )
    damping_load_centers = _damping_load_center_diagnostics(
        combined_rows,
        comparison_rows,
        lcg_over_beam=float(frozen_reference["lcg_over_beam"]),
    )
    write_csv(output / "coefficient_comparison.csv", comparison_rows)
    write_csv(output / "coefficient_metrics.csv", [row.__dict__ for row in comparison.metrics])
    write_csv(output / "restoring_offset_diagnostics.csv", restoring_offset_points)
    write_csv(output / "restoring_offset_summary.csv", restoring_offset_summary)
    write_csv(output / "damping_load_center_diagnostics.csv", damping_load_centers)
    restoring_offset_like_coefficients = [
        str(row["coefficient"])
        for row in restoring_offset_summary
        if bool(row["restoring_offset_like"])
    ]
    total_center_rows = [row for row in damping_load_centers if row["component"] == "total"]
    center_errors = {
        motion_column: float(
            np.median(
                [
                    abs(float(row["center_error_over_beam"]))
                    for row in total_center_rows
                    if row["motion_column"] == motion_column
                ]
            )
        )
        for motion_column in ("heave", "pitch")
    }
    acceptance = {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "benchmark_role": "same_model_NUM_reproduction_not_independent_EFD",
        "benchmark_series": "Sun_2007_Figs_7.13_7.14_NUM_open_markers",
        "model_variant": model_variant,
        "frequency_count": comparison.frequency_count,
        "coefficient_count": comparison.coefficient_count,
        "coefficient_metrics_passed": bool(all(row.passed for row in comparison.metrics)),
        "a35_monotonic_decrease": comparison.a35_monotonic_decrease,
        "a35_a53_nonreciprocal": comparison.a35_a53_nonreciprocal,
        "maximum_harmonic_residual_nrmse": maximum_harmonic_residual,
        "harmonic_residual_limit": harmonic_residual_limit,
        "harmonic_residual_passed": harmonic_passed,
        "maximum_bvp_relative_residual": maximum_bvp_residual,
        "bvp_residual_limit": bvp_residual_limit,
        "bvp_residual_passed": bvp_passed,
        "response_calibration_used": response_calibration_used,
        "restoring_offset_diagnostic_used_for_acceptance": False,
        "restoring_offset_like_added_mass_coefficients": restoring_offset_like_coefficients,
        "damping_load_center_diagnostic_used_for_acceptance": False,
        "heave_damping_center_median_abs_error_over_beam": center_errors["heave"],
        "pitch_damping_center_median_abs_error_over_beam": center_errors["pitch"],
        "restoring_source_sha256": restoring_sha_reference,
        "frozen_arguments": frozen_reference,
        "benchmark": str(benchmark.resolve()),
        "benchmark_sha256": _sha256(benchmark.resolve()),
    }
    (output / "acceptance.json").write_text(
        json.dumps(acceptance, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return acceptance


def main() -> int:
    args = _parser().parse_args()
    acceptance = aggregate(
        args.run_dirs,
        output=args.out.resolve(),
        benchmark=args.benchmark.resolve(),
        harmonic_residual_limit=float(args.harmonic_residual_limit),
        bvp_residual_limit=float(args.bvp_residual_limit),
    )
    print(args.out.resolve())
    print(json.dumps(acceptance, indent=2, ensure_ascii=True))
    return 0 if acceptance["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
