from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.audit_sun2007_longitudinal_load_distribution import (
    audit_longitudinal_load_distribution,
)


COEFFICIENTS = ("A33", "A35", "A53", "A55", "B33", "B35", "B53", "B55")


def _context() -> dict[str, object]:
    return {
        "target_identifier": "sun2007_troesch_prismatic_planing_hull",
        "beam_m": 0.318,
        "deadrise_deg": 20.0,
        "trim_deg": 4.0,
        "fn_b": 2.5,
        "mean_wetted_length_over_b": 3.0,
        "lcg_from_transom_m": 0.46746,
        "rho_water_kg_m3": 1000.0,
        "gravity_m_s2": 9.80665,
        "matrix_coordinate_contract": "heave_up_pitch_bow_up_force_and_moment_about_cg",
    }


def _write_run(
    path: Path,
    values: dict[str, float],
    *,
    corrected: bool,
    calibrated: bool = False,
) -> None:
    path.mkdir(parents=True)
    snapshot = {
        "arguments": {"transom_keel_reduction": corrected},
        "derived_target_context": _context(),
        "response_calibration_used": calibrated,
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
                    "response_calibration_used": calibrated,
                }
            )
            if not corrected:
                writer.writerow(
                    {
                        "component": "front",
                        "sigma": 1.4,
                        "coefficient": coefficient,
                        "value_nondimensional": 0.1 * value,
                        "response_calibration_used": calibrated,
                    }
                )


def _write_benchmark(path: Path, raw: dict[str, float], corrected: dict[str, float]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "model_variant",
                "omega_sqrt_B_over_g",
                "coefficient",
                "value_nondimensional",
            ),
        )
        writer.writeheader()
        for model_variant, values in (
            ("sun_2dt_without_stern_3d_correction", raw),
            ("sun_2dt_with_stern_3d_correction", corrected),
        ):
            for coefficient, value in values.items():
                writer.writerow(
                    {
                        "model_variant": model_variant,
                        "omega_sqrt_B_over_g": 1.4,
                        "coefficient": coefficient,
                        "value_nondimensional": value,
                    }
                )


def test_audit_writes_component_centers_and_source_deltas(tmp_path: Path) -> None:
    raw = {
        "A33": 1.0,
        "A35": 0.6,
        "A53": -0.2,
        "A55": 0.7,
        "B33": 2.5,
        "B35": -3.5,
        "B53": 1.7,
        "B55": 4.0,
    }
    source_corrected = {name: value + 0.1 for name, value in raw.items()}
    calculated = {name: value - 0.2 for name, value in raw.items()}
    calculated_corrected = {name: value + 0.1 for name, value in calculated.items()}
    baseline = tmp_path / "baseline"
    heave = tmp_path / "heave"
    pitch = tmp_path / "pitch"
    _write_run(baseline, calculated, corrected=False)
    _write_run(
        heave,
        {name: calculated_corrected[name] for name in ("A33", "A53", "B33", "B53")},
        corrected=True,
    )
    _write_run(
        pitch,
        {name: calculated_corrected[name] for name in ("A35", "A55", "B35", "B55")},
        corrected=True,
    )
    benchmark = tmp_path / "benchmark.csv"
    _write_benchmark(benchmark, raw, source_corrected)

    manifest = audit_longitudinal_load_distribution(
        baseline,
        heave,
        pitch,
        output=tmp_path / "audit",
        benchmark=benchmark,
    )

    assert manifest["status"] == "DIAGNOSTIC_ONLY_NOT_ACCEPTANCE"
    assert manifest["response_calibration_used"] is False
    assert (tmp_path / "audit" / "coefficient_component_breakdown.csv").exists()
    with (tmp_path / "audit" / "damping_load_center_audit.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        centers = list(csv.DictReader(handle))
    assert len(centers) == 2
    assert float(centers[0]["required_increment_force"]) == pytest.approx(0.2)
    with (tmp_path / "audit" / "transom_correction_delta_audit.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        deltas = list(csv.DictReader(handle))
    assert len(deltas) == 8
    assert max(abs(float(row["correction_delta_error"])) for row in deltas) < 1.0e-12


def test_audit_rejects_response_calibrated_input(tmp_path: Path) -> None:
    values = {name: 1.0 for name in COEFFICIENTS}
    baseline = tmp_path / "baseline"
    heave = tmp_path / "heave"
    pitch = tmp_path / "pitch"
    _write_run(baseline, values, corrected=False, calibrated=True)
    _write_run(heave, {name: 1.0 for name in ("A33", "A53", "B33", "B53")}, corrected=True)
    _write_run(pitch, {name: 1.0 for name in ("A35", "A55", "B35", "B55")}, corrected=True)
    benchmark = tmp_path / "benchmark.csv"
    _write_benchmark(benchmark, values, values)

    with pytest.raises(ValueError, match="Response-calibrated"):
        audit_longitudinal_load_distribution(
            baseline,
            heave,
            pitch,
            output=tmp_path / "audit",
            benchmark=benchmark,
        )
