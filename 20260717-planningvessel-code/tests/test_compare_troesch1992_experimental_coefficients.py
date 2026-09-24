from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.compare_troesch1992_experimental_coefficients import compare


ROOT = Path(__file__).resolve().parents[1]


def test_current_five_frequency_comparison_is_diagnostic_and_incomplete(
    tmp_path: Path,
) -> None:
    computed = (
        ROOT
        / "outputs"
        / "sun2007_num_reproduction_five_frequency_body12_sub16_acceptance_v7"
        / "combined_identified_coefficients.csv"
    )
    experiment = (
        ROOT
        / "benchmarks"
        / "troesch1992_experimental_forced_motion_coefficients.csv"
    )
    manifest = compare(computed, experiment, tmp_path)
    assert manifest["status"] == "DIAGNOSTIC_ONLY"
    assert manifest["used_for_acceptance"] is False
    assert manifest["response_calibration_used"] is False
    comparison = pd.read_csv(tmp_path / "troesch_exp_comparison.csv")
    assert len(comparison) == 40
    assert (comparison["used_for_acceptance"] == False).all()  # noqa: E712
    assert (comparison["evaluation"] == "NOT_EVALUATED").any()
    metrics = pd.read_csv(tmp_path / "troesch_exp_metrics.csv").set_index(
        "coefficient"
    )
    assert metrics.loc["A33", "relative_error_point_count"] == 5
    assert metrics.loc["B53", "relative_error_point_count"] == 5
    assert metrics.loc["A35", "relative_error_point_count"] == 0
    parsed = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert parsed["benchmark_role"] == "independent_EFD_digitization_not_acceptance_calibration"
