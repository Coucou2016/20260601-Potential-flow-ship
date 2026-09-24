from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scripts.run_regular_head_sea_gate2_acceptance import (
    MINIMUM_RESOLVED_BEGOVIC_PEAKS,
    _begovic_peak_metrics,
    _motion_metrics,
)


CANDIDATE_ROUTE = "matched_raw_station_phase_excitation"
SPEED_DIRECTORIES = ("fn167", "fn226", "fn282")
FROZEN_CONFIGURATION_FIELDS = (
    "base_route",
    "phase_length_route",
    "frequency_coordinate_route",
    "restoring_route",
    "force_component_route",
    "hydrodynamic_correction_source",
    "excitation_route",
    "phase_resolved_matrix_application",
    "wagner_pileup_factor",
    "transom_force_cutoff_length_beams",
    "transom_force_recovery_profile",
    "momentum_rate_formulation",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate the frozen three-speed Gate 2 frequency-dependent candidate.")
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def _load_candidate(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    comparisons: list[pd.DataFrame] = []
    dense: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    for directory_name in SPEED_DIRECTORIES:
        directory = root / directory_name
        comparisons.append(pd.read_csv(directory / f"{CANDIDATE_ROUTE}_comparison.csv"))
        dense.append(pd.read_csv(directory / f"{CANDIDATE_ROUTE}_dense_response.csv"))
        summaries.append(json.loads((directory / "probe_summary.json").read_text(encoding="utf-8")))
    return pd.concat(comparisons, ignore_index=True), pd.concat(dense, ignore_index=True), summaries


def _frozen_configuration(summaries: list[dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    if len(summaries) != len(SPEED_DIRECTORIES) or any(
        any(field not in summary or summary[field] is None for field in FROZEN_CONFIGURATION_FIELDS)
        for summary in summaries
    ):
        return False, {}
    reference = {field: summaries[0].get(field) for field in FROZEN_CONFIGURATION_FIELDS}
    consistent = all(
        {field: summary.get(field) for field in FROZEN_CONFIGURATION_FIELDS} == reference
        for summary in summaries[1:]
    )
    return consistent, reference


def _validated_provider_evidence(summaries: list[dict[str, Any]]) -> bool:
    # No candidate route currently has an approved full-band kernel certificate.
    # A status string supplied by the candidate cannot self-certify validation.
    return False


def _speed_motion_metrics(comparison: pd.DataFrame, model_name: str) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for configuration, group in comparison.groupby("configuration", sort=True):
        frame = _motion_metrics(group, scope=f"{model_name} {configuration}")
        frame.insert(0, "configuration", configuration)
        frame.insert(1, "model", model_name)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def _plot_comparison(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    candidate_dense: pd.DataFrame,
    path: Path,
) -> None:
    configurations = sorted(candidate["configuration"].unique())
    figure, axes = plt.subplots(2, 3, figsize=(13.2, 7.2), constrained_layout=True)
    definitions = (
        ("heave_rao_m_per_m", "reference_heave_rao_m_per_m", "Heave RAO"),
        ("pitch_rao_rad_per_wave_slope", "reference_pitch_rao_rad_per_wave_slope", "Pitch / wave slope"),
    )
    for column, configuration in enumerate(configurations):
        base_group = baseline[baseline["configuration"].eq(configuration)].sort_values("lambda_over_l")
        candidate_group = candidate[candidate["configuration"].eq(configuration)].sort_values("lambda_over_l")
        dense_group = candidate_dense[candidate_dense["configuration"].eq(configuration)].sort_values("lambda_over_l")
        for row, (computed, reference, ylabel) in enumerate(definitions):
            axis = axes[row, column]
            axis.plot(base_group["lambda_over_l"], base_group[computed], color="#7c858f", linewidth=1.3, label="locked baseline")
            axis.plot(dense_group["lambda_over_l"], dense_group[computed], color="#007c91", linewidth=1.8, label="frequency-dependent candidate")
            axis.errorbar(
                candidate_group["lambda_over_l"],
                candidate_group[reference],
                yerr=candidate_group["heave_digitization_uncertainty_abs" if row == 0 else "pitch_digitization_uncertainty_abs"],
                color="#c84630",
                marker="^",
                linestyle="none",
                capsize=2.0,
                label="Begovic experiment",
            )
            axis.set_title(configuration)
            axis.set_xlabel("Wavelength / hull length")
            axis.set_ylabel(ylabel)
            axis.grid(True, alpha=0.22)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    candidate, dense, summaries = _load_candidate(args.candidate_root)
    baseline = pd.read_csv(args.baseline / "begovic_efd_comparison.csv")
    baseline_dense = pd.read_csv(args.baseline / "begovic_dense_peak_scan.csv")
    configuration_consistent, frozen_configuration = _frozen_configuration(summaries)
    no_calibration = len(summaries) == 3 and all(
        summary.get("response_calibration_used") is False for summary in summaries
    )
    validity_values = {
        str(summary.get("correction_metadata", {}).get("validity_status", "missing")) for summary in summaries
    }
    provider_benchmark_validated = _validated_provider_evidence(summaries)

    candidate_motion = _motion_metrics(candidate, scope="three-speed frozen frequency-dependent candidate")
    baseline_motion = _motion_metrics(baseline, scope="locked Gate 2 baseline")
    candidate_speed_motion = _speed_motion_metrics(candidate, "frequency-dependent candidate")
    baseline_speed_motion = _speed_motion_metrics(baseline, "locked baseline")
    speed_motion = pd.concat((baseline_speed_motion, candidate_speed_motion), ignore_index=True)
    per_speed_pass = (
        len(candidate_speed_motion) == 6
        and candidate_speed_motion["configuration"].nunique() == 3
        and candidate_speed_motion["status"].eq("PASS").all()
    )
    candidate_peaks = _begovic_peak_metrics(candidate, dense)
    baseline_peaks = _begovic_peak_metrics(baseline, baseline_dense)

    resolved = candidate_peaks[candidate_peaks["peak_is_resolved"].astype(bool)]
    peak_coverage_pass = (
        len(resolved) >= MINIMUM_RESOLVED_BEGOVIC_PEAKS
        and resolved["configuration"].nunique() >= 2
        and resolved["metric"].nunique() == 2
    )
    peak_accuracy_pass = peak_coverage_pass and resolved["status"].eq("PASS").all()
    heave_pass = candidate_motion.loc[candidate_motion["metric"].eq("heave_motion"), "status"].iloc[0] == "PASS"
    pitch_pass = candidate_motion.loc[candidate_motion["metric"].eq("pitch_motion"), "status"].iloc[0] == "PASS"
    checks = pd.DataFrame(
        [
            ("frozen_configuration_across_three_speeds", configuration_consistent, "All theory and discretization choices are identical."),
            ("no_empirical_response_scaling", no_calibration, "No measured motion amplitude enters the hydrodynamic coefficients."),
            ("provider_kernel_benchmark_validated", provider_benchmark_validated, "; ".join(sorted(validity_values))),
            ("begovic_heave_global_accuracy", heave_pass, "Median relative error <=15% and NRMSE <=20%."),
            ("begovic_pitch_global_accuracy", pitch_pass, "Median relative error <=15% and NRMSE <=20%."),
            ("begovic_each_speed_motion_accuracy", per_speed_pass, "Every speed and both motions must independently meet 15%/20%; 20260915 contract."),
            ("begovic_peak_coverage", peak_coverage_pass, f"Resolved peaks={len(resolved)}; require >=4, >=2 speeds and both motions."),
            ("begovic_peak_frequency_accuracy", peak_accuracy_pass, "Every resolved peak frequency error must be <=10%."),
        ],
        columns=["check", "passed", "evidence"],
    )
    checks["status"] = np.where(checks["passed"], "PASS", "FAIL")
    status = "PASS" if checks["passed"].all() else "FAIL"

    candidate.to_csv(out / "candidate_begovic_comparison.csv", index=False)
    dense.to_csv(out / "candidate_dense_peak_scan.csv", index=False)
    candidate_motion.to_csv(out / "candidate_global_motion_metrics.csv", index=False)
    candidate_peaks.to_csv(out / "candidate_peak_metrics.csv", index=False)
    speed_motion.to_csv(out / "baseline_candidate_speed_motion_metrics.csv", index=False)
    checks.to_csv(out / "candidate_acceptance_checks.csv", index=False)
    figure_path = out / "gate2_frequency_candidate_vs_baseline.png"
    _plot_comparison(baseline, candidate, dense, figure_path)

    report = {
        "status": status,
        "interpretation": (
            "The candidate is a fixed, response-independent physics route. A FAIL result is retained and does not "
            "replace the locked Gate 2 baseline. Passing individual high-speed cases is diagnostic evidence only."
        ),
        "candidate_route": CANDIDATE_ROUTE,
        "frozen_configuration": frozen_configuration,
        "validity_status_values": sorted(validity_values),
        "global_motion_metrics": candidate_motion.to_dict(orient="records"),
        "resolved_peak_count": int(len(resolved)),
        "resolved_peak_max_relative_error": float(resolved["peak_frequency_relative_error"].max()),
        "checks": checks[["check", "status", "evidence"]].to_dict(orient="records"),
        "outputs": {
            "figure": str(figure_path.resolve()),
            "speed_motion_metrics": str((out / "baseline_candidate_speed_motion_metrics.csv").resolve()),
            "peak_metrics": str((out / "candidate_peak_metrics.csv").resolve()),
        },
    }
    (out / "gate2_frequency_candidate_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
