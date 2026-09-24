from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.summarize_sun2007_fixed_earth_time_convergence import summarize


def _write_coefficients(path: Path, values: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "component",
                "coefficient",
                "value_nondimensional",
                "harmonic_fit_residual_nrmse",
            ),
        )
        writer.writeheader()
        for coefficient, value in values.items():
            writer.writerow(
                {
                    "component": "total",
                    "coefficient": coefficient,
                    "value_nondimensional": value,
                    "harmonic_fit_residual_nrmse": 0.01,
                }
            )


def _write_benchmark(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "model_variant",
                "omega_sqrt_B_over_g",
                "coefficient",
                "value_nondimensional",
                "digitization_uncertainty_nondimensional",
            ),
        )
        writer.writeheader()
        for coefficient in ("A33", "A53", "B33", "B53"):
            writer.writerow(
                {
                    "model_variant": "sun_2dt_without_stern_3d_correction",
                    "omega_sqrt_B_over_g": 1.4,
                    "coefficient": coefficient,
                    "value_nondimensional": 1.0,
                    "digitization_uncertainty_nondimensional": 0.1,
                }
            )


def test_time_convergence_summary_keeps_near_zero_relative_failure_strict(
    tmp_path: Path,
) -> None:
    benchmark = tmp_path / "benchmark.csv"
    coarse = tmp_path / "coarse" / "identified_coefficients_reprocessed.csv"
    fine = tmp_path / "fine" / "identified_coefficients_reprocessed.csv"
    _write_benchmark(benchmark)
    _write_coefficients(
        coarse,
        {"A33": 1.02, "A53": -0.02, "B33": 1.03, "B53": 1.04},
    )
    _write_coefficients(
        fine,
        {"A33": 1.00, "A53": -0.04, "B33": 1.00, "B53": 1.00},
    )

    result = summarize(
        [("coarse", coarse), ("fine", fine)],
        benchmark_path=benchmark,
        output=tmp_path / "summary",
    )

    assert result["status"] == "FAIL"
    assert result["failed_coefficients"] == ["A53"]
    changes = list(
        csv.DictReader(
            (tmp_path / "summary" / "adjacent_changes.csv").open(
                encoding="utf-8", newline=""
            )
        )
    )
    a53 = next(row for row in changes if row["coefficient"] == "A53")
    assert a53["strict_relative_status"] == "FAIL"
    assert a53["absolute_change_within_digitization_uncertainty"] == "True"
    summary = json.loads((tmp_path / "summary" / "summary.json").read_text())
    assert summary["response_calibration_used"] is False
