from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.compare_paired_sun2007_columns import compare_paired_columns


def _write_run(path: Path, *, motion: str, values: dict[str, float]) -> None:
    path.mkdir(parents=True)
    arguments = {
        "out": str(path),
        "heave_only": motion == "heave",
        "pitch_only": motion == "pitch",
        "sigmas": [1.4],
        "beam_m": 0.318,
        "transom_correction": False,
        "transom_keel_reduction": True,
    }
    snapshot = {
        "arguments": arguments,
        "derived_target_context": {"beam_m": 0.318},
        "derived_inputs": {"speed_mps": 4.0},
        "moving_wedge_config": {"body_panels_per_side": 12},
        "response_calibration_used": False,
    }
    (path / "run_input_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
    with (path / "identified_coefficients.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "component",
                "sigma",
                "coefficient",
                "value_nondimensional",
                "harmonic_fit_residual_nrmse",
                "response_calibration_used",
            ),
        )
        writer.writeheader()
        for coefficient, value in values.items():
            writer.writerow(
                {
                    "component": "total",
                    "sigma": 1.4,
                    "coefficient": coefficient,
                    "value_nondimensional": value,
                    "harmonic_fit_residual_nrmse": 0.01,
                    "response_calibration_used": False,
                }
            )
    (path / "run_diagnostics.json").write_text(
        json.dumps([{"maximum_potential_residual": 1.0e-12}]), encoding="utf-8"
    )
    (path / "restoring_diagnostics.json").write_text(
        json.dumps(
            {
                "source": "unit_test_restoring",
                "source_path": "fixture/restoring.csv",
                "source_sha256": "same-restoring",
            }
        ),
        encoding="utf-8",
    )


def _write_benchmark(path: Path, values: dict[str, float]) -> None:
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
        for coefficient, value in values.items():
            writer.writerow(
                {
                    "model_variant": "sun_2dt_with_stern_3d_correction",
                    "omega_sqrt_B_over_g": 1.4,
                    "coefficient": coefficient,
                    "value_nondimensional": value,
                    "digitization_uncertainty_nondimensional": 0.02,
                }
            )


def test_paired_columns_preserve_two_source_provenance(tmp_path: Path) -> None:
    values = {
        "A33": 1.0,
        "A35": 0.45,
        "A53": -0.2,
        "A55": 0.83,
        "B33": 2.48,
        "B35": -2.1,
        "B53": 1.76,
        "B55": 2.35,
    }
    heave = tmp_path / "heave"
    pitch = tmp_path / "pitch"
    benchmark = tmp_path / "benchmark.csv"
    _write_run(heave, motion="heave", values={key: values[key] for key in ("A33", "A53", "B33", "B53")})
    _write_run(pitch, motion="pitch", values={key: values[key] for key in ("A35", "A55", "B35", "B55")})
    _write_benchmark(benchmark, values)

    manifest = compare_paired_columns(
        heave,
        pitch,
        output=tmp_path / "comparison",
        benchmark=benchmark,
    )

    assert manifest["status"] == "PASS"
    assert manifest["coefficient_pass_count"] == 8
    assert manifest["single_frequency_screen_only"] is True
    assert manifest["used_for_five_frequency_acceptance"] is False
    assert manifest["restoring_matrix_provenance"]["source"] == "unit_test_restoring"
    assert manifest["restoring_matrix_provenance"]["source_sha256"] == "same-restoring"
    assert manifest["source_runs"]["heave"]["directory"] != manifest["source_runs"]["pitch"]["directory"]
    assert (tmp_path / "comparison" / "paired_coefficient_comparison.csv").exists()


def test_paired_columns_reject_physical_input_mismatch(tmp_path: Path) -> None:
    heave = tmp_path / "heave"
    pitch = tmp_path / "pitch"
    values_heave = {"A33": 1.0, "A53": -0.2, "B33": 2.48, "B53": 1.76}
    values_pitch = {"A35": 0.45, "A55": 0.83, "B35": -2.1, "B55": 2.35}
    _write_run(heave, motion="heave", values=values_heave)
    _write_run(pitch, motion="pitch", values=values_pitch)
    snapshot_path = pitch / "run_input_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["arguments"]["beam_m"] = 0.4
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    benchmark = tmp_path / "benchmark.csv"
    _write_benchmark(benchmark, {**values_heave, **values_pitch})

    with pytest.raises(ValueError, match="different physical inputs"):
        compare_paired_columns(
            heave,
            pitch,
            output=tmp_path / "comparison",
            benchmark=benchmark,
        )
