from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


HEAVE_COEFFICIENTS = ("A33", "A53", "B33", "B53")
PITCH_COEFFICIENTS = ("A35", "A55", "B35", "B55")
ALL_COEFFICIENTS = (
    "A33",
    "A35",
    "A53",
    "A55",
    "B33",
    "B35",
    "B53",
    "B55",
)
IGNORED_ARGUMENT_DIFFERENCES = {"out", "heave_only", "pitch_only"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare independently checkpointed Sun forced-heave and forced-pitch columns."
    )
    parser.add_argument("heave_run", type=Path)
    parser.add_argument("pitch_run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("benchmarks/sun2007_troesch_forced_motion_coefficients.csv"),
    )
    parser.add_argument("--frequency-tolerance", type=float, default=5.0e-3)
    parser.add_argument("--relative-error-limit", type=float, default=0.10)
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _normalized_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in arguments.items()
        if key not in IGNORED_ARGUMENT_DIFFERENCES
    }


def _validate_and_read_column(
    run_dir: Path,
    *,
    expected_motion: str,
) -> tuple[dict[str, Any], list[dict[str, str]], float, float]:
    snapshot_path = run_dir / "run_input_snapshot.json"
    coefficients_path = run_dir / "identified_coefficients.csv"
    diagnostics_path = run_dir / "run_diagnostics.json"
    restoring_path = run_dir / "restoring_diagnostics.json"
    for path in (snapshot_path, coefficients_path, diagnostics_path, restoring_path):
        if not path.exists():
            raise FileNotFoundError(path)

    snapshot = _read_json(snapshot_path)
    arguments = snapshot["arguments"]
    if expected_motion == "heave":
        valid_mode = bool(arguments.get("heave_only")) and not bool(
            arguments.get("pitch_only")
        )
        expected_coefficients = set(HEAVE_COEFFICIENTS)
    else:
        valid_mode = bool(arguments.get("pitch_only")) and not bool(
            arguments.get("heave_only")
        )
        expected_coefficients = set(PITCH_COEFFICIENTS)
    if not valid_mode:
        raise ValueError(f"{run_dir} is not an explicit {expected_motion}-only source run.")

    rows = [
        row
        for row in _read_csv(coefficients_path)
        if row["component"] == "total"
    ]
    if {row["coefficient"] for row in rows} != expected_coefficients:
        raise ValueError(
            f"{run_dir} does not contain exactly the {expected_motion} coefficient column."
        )
    if any(_as_bool(row.get("response_calibration_used", False)) for row in rows):
        raise ValueError("Response-calibrated source coefficients are forbidden.")
    sigma_values = {float(row["sigma"]) for row in rows}
    if len(sigma_values) != 1:
        raise ValueError(f"{run_dir} must contain one nondimensional frequency.")

    diagnostics = _read_json(diagnostics_path)
    if not isinstance(diagnostics, list) or len(diagnostics) != 1:
        raise ValueError(f"{diagnostics_path} must contain one frequency diagnostic.")
    bvp_values = [
        float(value)
        for key, value in diagnostics[0].items()
        if key.endswith("_residual") and value is not None
    ]
    maximum_bvp_residual = max(bvp_values, default=0.0)
    maximum_harmonic_residual = max(
        float(row["harmonic_fit_residual_nrmse"]) for row in rows
    )
    return snapshot, rows, maximum_harmonic_residual, maximum_bvp_residual


def compare_paired_columns(
    heave_run: Path,
    pitch_run: Path,
    *,
    output: Path,
    benchmark: Path,
    frequency_tolerance: float = 5.0e-3,
    relative_error_limit: float = 0.10,
    harmonic_residual_limit: float = 0.05,
    bvp_residual_limit: float = 1.0e-8,
) -> dict[str, Any]:
    heave_run = heave_run.resolve()
    pitch_run = pitch_run.resolve()
    output = output.resolve()
    benchmark = benchmark.resolve()
    if frequency_tolerance <= 0.0 or not 0.0 < relative_error_limit < 1.0:
        raise ValueError("Frequency and relative-error limits must be positive and bounded.")
    output.mkdir(parents=True, exist_ok=True)

    heave_snapshot, heave_rows, heave_harmonic, heave_bvp = _validate_and_read_column(
        heave_run,
        expected_motion="heave",
    )
    pitch_snapshot, pitch_rows, pitch_harmonic, pitch_bvp = _validate_and_read_column(
        pitch_run,
        expected_motion="pitch",
    )
    heave_arguments = heave_snapshot["arguments"]
    pitch_arguments = pitch_snapshot["arguments"]
    if _normalized_arguments(heave_arguments) != _normalized_arguments(pitch_arguments):
        differing = sorted(
            key
            for key in set(heave_arguments) | set(pitch_arguments)
            if key not in IGNORED_ARGUMENT_DIFFERENCES
            and heave_arguments.get(key) != pitch_arguments.get(key)
        )
        raise ValueError(f"Heave and pitch source runs use different physical inputs: {differing}.")
    for key in ("derived_target_context", "derived_inputs", "moving_wedge_config"):
        if heave_snapshot.get(key) != pitch_snapshot.get(key):
            raise ValueError(f"Heave and pitch source runs differ in {key}.")

    heave_restoring = heave_run / "restoring_diagnostics.json"
    pitch_restoring = pitch_run / "restoring_diagnostics.json"
    heave_restoring_diagnostics = _read_json(heave_restoring)
    pitch_restoring_diagnostics = _read_json(pitch_restoring)
    if heave_restoring_diagnostics.get("source_sha256") != (
        pitch_restoring_diagnostics.get("source_sha256")
    ):
        raise ValueError("Heave and pitch source runs use different restoring matrices.")

    source_rows = {row["coefficient"]: row for row in heave_rows + pitch_rows}
    sigma_values = {float(row["sigma"]) for row in source_rows.values()}
    if len(sigma_values) != 1:
        raise ValueError("Heave and pitch columns use different frequencies.")
    sigma = sigma_values.pop()
    corrected = bool(heave_arguments.get("transom_correction")) or bool(
        heave_arguments.get("transom_keel_reduction")
    )
    model_variant = (
        "sun_2dt_with_stern_3d_correction"
        if corrected
        else "sun_2dt_without_stern_3d_correction"
    )
    benchmark_rows = [
        row
        for row in _read_csv(benchmark)
        if row["model_variant"] == model_variant
        and abs(float(row["omega_sqrt_B_over_g"]) - sigma) <= frequency_tolerance
    ]
    targets = {row["coefficient"]: row for row in benchmark_rows}
    if set(targets) != set(ALL_COEFFICIENTS):
        raise ValueError(
            f"Benchmark does not provide all eight coefficients at sigma={sigma} for {model_variant}."
        )

    comparison_rows: list[dict[str, Any]] = []
    for coefficient in ALL_COEFFICIENTS:
        source = source_rows[coefficient]
        target = targets[coefficient]
        calculated = float(source["value_nondimensional"])
        reference = float(target["value_nondimensional"])
        absolute_error = abs(calculated - reference)
        relative_error = absolute_error / abs(reference)
        comparison_rows.append(
            {
                "sigma": sigma,
                "coefficient": coefficient,
                "calculated_nondimensional": calculated,
                "reference_nondimensional": reference,
                "absolute_error_nondimensional": absolute_error,
                "relative_error": relative_error,
                "relative_error_limit": relative_error_limit,
                "passed": relative_error <= relative_error_limit,
                "digitization_uncertainty_nondimensional": float(
                    target["digitization_uncertainty_nondimensional"]
                ),
                "source_column": "heave" if coefficient in HEAVE_COEFFICIENTS else "pitch",
            }
        )

    with (output / "paired_coefficient_comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0]))
        writer.writeheader()
        writer.writerows(comparison_rows)

    maximum_harmonic = max(heave_harmonic, pitch_harmonic)
    maximum_bvp = max(heave_bvp, pitch_bvp)
    coefficients_passed = all(bool(row["passed"]) for row in comparison_rows)
    manifest: dict[str, Any] = {
        "schema": "sun2007_paired_forced_motion_column_screen_v1",
        "status": "PASS" if coefficients_passed and maximum_harmonic <= harmonic_residual_limit and maximum_bvp <= bvp_residual_limit else "FAIL",
        "single_frequency_screen_only": True,
        "used_for_five_frequency_acceptance": False,
        "sigma": sigma,
        "model_variant": model_variant,
        "transom_correction_mode": (
            "source_keel_wetted_length_reduction_0p5B"
            if heave_arguments.get("transom_keel_reduction")
            else "local_analytic_pressure_patch_0p1B"
            if heave_arguments.get("transom_correction")
            else "none"
        ),
        "coefficient_pass_count": sum(bool(row["passed"]) for row in comparison_rows),
        "coefficient_count": len(comparison_rows),
        "maximum_harmonic_residual_nrmse": maximum_harmonic,
        "harmonic_residual_limit": harmonic_residual_limit,
        "maximum_bvp_relative_residual": maximum_bvp,
        "bvp_residual_limit": bvp_residual_limit,
        "response_calibration_used": False,
        "restoring_matrix_provenance": {
            "source": heave_restoring_diagnostics.get("source"),
            "source_path": heave_restoring_diagnostics.get("source_path"),
            "source_sha256": heave_restoring_diagnostics.get("source_sha256"),
            "source_manifest_path": heave_restoring_diagnostics.get(
                "source_manifest_path"
            ),
            "source_manifest_sha256": heave_restoring_diagnostics.get(
                "source_manifest_sha256"
            ),
            "heave_diagnostics_sha256": _sha256(heave_restoring),
            "pitch_diagnostics_sha256": _sha256(pitch_restoring),
        },
        "source_runs": {
            "heave": {
                "directory": str(heave_run),
                "input_snapshot_sha256": _sha256(heave_run / "run_input_snapshot.json"),
                "identified_coefficients_sha256": _sha256(
                    heave_run / "identified_coefficients.csv"
                ),
                "run_diagnostics_sha256": _sha256(heave_run / "run_diagnostics.json"),
            },
            "pitch": {
                "directory": str(pitch_run),
                "input_snapshot_sha256": _sha256(pitch_run / "run_input_snapshot.json"),
                "identified_coefficients_sha256": _sha256(
                    pitch_run / "identified_coefficients.csv"
                ),
                "run_diagnostics_sha256": _sha256(pitch_run / "run_diagnostics.json"),
            },
        },
        "benchmark": {
            "path": str(benchmark),
            "sha256": _sha256(benchmark),
            "role": "same_model_NUM_reproduction_not_independent_EFD",
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    args = _parser().parse_args()
    manifest = compare_paired_columns(
        args.heave_run,
        args.pitch_run,
        output=args.out,
        benchmark=args.benchmark,
        frequency_tolerance=args.frequency_tolerance,
        relative_error_limit=args.relative_error_limit,
        harmonic_residual_limit=args.harmonic_residual_limit,
        bvp_residual_limit=args.bvp_residual_limit,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=True))
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
