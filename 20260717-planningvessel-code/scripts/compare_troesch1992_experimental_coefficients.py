from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(str(path), "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compare(
    computed_csv: Path,
    experiment_csv: Path,
    output: Path,
    *,
    frequency_tolerance: float = 0.035,
    near_zero_floor: float = 0.1,
) -> dict[str, object]:
    computed_csv = computed_csv.resolve()
    experiment_csv = experiment_csv.resolve()
    output = output.resolve()
    computed = pd.read_csv(computed_csv)
    experiment = pd.read_csv(experiment_csv)
    if "component" in computed.columns:
        computed = computed[computed["component"].eq("total")]
    required_computed = {"sigma", "coefficient", "value_nondimensional"}
    required_experiment = {
        "omega_sqrt_B_over_g",
        "coefficient",
        "value_nondimensional",
        "digitization_uncertainty_nondimensional",
        "response_calibration_used",
    }
    if not required_computed.issubset(computed.columns):
        raise ValueError("Computed coefficient table is missing required columns.")
    if not required_experiment.issubset(experiment.columns):
        raise ValueError("Experimental coefficient table is missing required columns.")
    if experiment["response_calibration_used"].astype(bool).any():
        raise ValueError("Experimental comparison rejects response-calibrated data.")

    rows: list[dict[str, object]] = []
    for row in computed.itertuples(index=False):
        sigma = float(row.sigma)
        coefficient = str(row.coefficient)
        local = experiment[
            experiment["coefficient"].eq(coefficient)
            & (
                (experiment["omega_sqrt_B_over_g"] - sigma).abs()
                <= float(frequency_tolerance)
            )
        ].copy()
        computed_value = float(row.value_nondimensional)
        if local.empty:
            rows.append(
                {
                    "sigma": sigma,
                    "coefficient": coefficient,
                    "computed_nondimensional": computed_value,
                    "experimental_point_count": 0,
                    "experimental_frequency_min": np.nan,
                    "experimental_frequency_max": np.nan,
                    "experimental_median_nondimensional": np.nan,
                    "experimental_min_nondimensional": np.nan,
                    "experimental_max_nondimensional": np.nan,
                    "experimental_max_digitization_uncertainty": np.nan,
                    "absolute_error": np.nan,
                    "relative_error": np.nan,
                    "evaluation": "NOT_EVALUATED",
                    "reason": "no isolated EXP marker inside frequency tolerance",
                    "used_for_acceptance": False,
                    "response_calibration_used": False,
                }
            )
            continue
        median = float(local["value_nondimensional"].median())
        uncertainty = float(
            local["digitization_uncertainty_nondimensional"].max()
        )
        absolute_error = abs(computed_value - median)
        relative_error = (
            absolute_error / abs(median)
            if abs(median) > max(float(near_zero_floor), 2.0 * uncertainty)
            else np.nan
        )
        rows.append(
            {
                "sigma": sigma,
                "coefficient": coefficient,
                "computed_nondimensional": computed_value,
                "experimental_point_count": len(local),
                "experimental_frequency_min": float(
                    local["omega_sqrt_B_over_g"].min()
                ),
                "experimental_frequency_max": float(
                    local["omega_sqrt_B_over_g"].max()
                ),
                "experimental_median_nondimensional": median,
                "experimental_min_nondimensional": float(
                    local["value_nondimensional"].min()
                ),
                "experimental_max_nondimensional": float(
                    local["value_nondimensional"].max()
                ),
                "experimental_max_digitization_uncertainty": uncertainty,
                "absolute_error": absolute_error,
                "relative_error": relative_error,
                "evaluation": (
                    "NEAR_ZERO_ABSOLUTE_ONLY"
                    if not np.isfinite(relative_error)
                    else "DIAGNOSTIC_ONLY"
                ),
                "reason": (
                    "relative error suppressed for near-zero experimental median"
                    if not np.isfinite(relative_error)
                    else "independent EFD diagnostic; no acceptance threshold applied"
                ),
                "used_for_acceptance": False,
                "response_calibration_used": False,
            }
        )

    comparison = pd.DataFrame(rows).sort_values(["coefficient", "sigma"])
    metric_rows: list[dict[str, object]] = []
    for coefficient, group in comparison.groupby("coefficient"):
        relative = group["relative_error"].dropna()
        metric_rows.append(
            {
                "coefficient": coefficient,
                "computed_frequency_count": len(group),
                "frequencies_with_exp_markers": int(
                    (group["experimental_point_count"] > 0).sum()
                ),
                "relative_error_point_count": len(relative),
                "median_relative_error": (
                    float(relative.median()) if len(relative) else np.nan
                ),
                "used_for_acceptance": False,
            }
        )
    metrics = pd.DataFrame(metric_rows)
    output.mkdir(parents=True, exist_ok=True)
    comparison_path = output / "troesch_exp_comparison.csv"
    metrics_path = output / "troesch_exp_metrics.csv"
    comparison.to_csv(comparison_path, index=False, float_format="%.12g")
    metrics.to_csv(metrics_path, index=False, float_format="%.12g")
    manifest = {
        "status": "DIAGNOSTIC_ONLY",
        "used_for_acceptance": False,
        "benchmark_role": "independent_EFD_digitization_not_acceptance_calibration",
        "frequency_tolerance": float(frequency_tolerance),
        "near_zero_floor": float(near_zero_floor),
        "computed_csv": str(computed_csv),
        "computed_csv_sha256": _sha256(computed_csv),
        "experiment_csv": str(experiment_csv),
        "experiment_csv_sha256": _sha256(experiment_csv),
        "comparison_csv_sha256": _sha256(comparison_path),
        "metrics_csv_sha256": _sha256(metrics_path),
        "response_calibration_used": False,
        "limitations": [
            "Only isolated visible EXP markers are compared.",
            "No response or coefficient multiplier is fitted.",
            "Missing or near-zero points cannot pass or fail an acceptance threshold.",
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare computed Sun coefficients with independently visible Troesch EXP markers."
    )
    parser.add_argument("computed_csv", type=Path)
    parser.add_argument(
        "--experiment",
        type=Path,
        default=Path("benchmarks/troesch1992_experimental_forced_motion_coefficients.csv"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frequency-tolerance", type=float, default=0.035)
    args = parser.parse_args()
    manifest = compare(
        args.computed_csv,
        args.experiment,
        args.out,
        frequency_tolerance=float(args.frequency_tolerance),
    )
    print(args.out.resolve())
    print(json.dumps(manifest, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
