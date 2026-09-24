from __future__ import annotations

import csv
import json
import math

import numpy as np
import pytest

from scripts.reprocess_sun2007_forced_motion_run import reprocess


def test_reprocess_recovers_both_forced_motion_columns(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "reprocessed"
    beam = 0.318
    gravity = 9.80665
    sigma = 1.4
    omega = sigma * math.sqrt(gravity / beam)
    heave_amplitude = 0.036 * beam
    pitch_amplitude = math.radians(0.43)
    arguments = {
        "target_identifier": "sun2007_troesch_prismatic_planing_hull",
        "beam_m": beam,
        "rho_water_kg_m3": 1000.0,
        "gravity_m_s2": gravity,
        "deadrise_deg": 20.0,
        "trim_deg": 4.0,
        "fn_b": 2.5,
        "mean_wetted_length_over_beam": 3.0,
        "lcg_over_beam": 1.47,
        "heave_amplitude_over_beam": 0.036,
        "pitch_amplitude_deg": 0.43,
        "sigmas": [sigma],
        "discard_cycles": 0.5,
        "retained_cycles": 1.5,
        "restoring_mode": "zero",
    }
    (source / "run_input_snapshot.json").write_text(
        json.dumps({"arguments": arguments, "response_calibration_used": False}),
        encoding="utf-8",
    )
    (source / "run_diagnostics.json").write_text(
        json.dumps([{"heave_max_potential_residual": 1e-12}]), encoding="utf-8"
    )
    restoring = np.asarray([[100.0, -20.0], [30.0, 40.0]])
    restoring_path = tmp_path / "restoring.csv"
    with restoring_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("component", "row", "column", "value", "units"))
        writer.writerow(("total", "heave_force", "heave", restoring[0, 0], "N/m"))
        writer.writerow(("total", "heave_force", "pitch", restoring[0, 1], "N/rad"))
        writer.writerow(("total", "pitch_moment", "heave", restoring[1, 0], "N"))
        writer.writerow(("total", "pitch_moment", "pitch", restoring[1, 1], "N m/rad"))
    added = np.asarray([[2.0, 3.0], [4.0, 5.0]])
    damping = np.asarray([[6.0, 7.0], [8.0, 9.0]])
    period = 2.0 * math.pi / omega
    time = np.linspace(0.0, 2.0 * period, 241)
    for column, (motion, amplitude) in enumerate(
        (("heave", heave_amplitude), ("pitch", pitch_amplitude))
    ):
        sine = restoring[:, column] * amplitude - omega**2 * amplitude * added[:, column]
        cosine = omega * amplitude * damping[:, column]
        loads = np.sin(omega * time)[:, None] * sine + np.cos(omega * time)[:, None] * cosine
        path = source / f"timeseries_sigma_1p4_{motion}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                (
                    "time_s",
                    "total_vertical_force_n",
                    "total_pitch_moment_nm",
                )
            )
            writer.writerows(zip(time, loads[:, 0], loads[:, 1]))

    reprocess(source, restoring_path, output)

    with (output / "identified_coefficients.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = {
            row["coefficient"]: float(row["value_dimensional"])
            for row in csv.DictReader(handle)
            if row["component"] == "total"
        }
    expected = {
        "A33": 2.0,
        "A35": 3.0,
        "A53": 4.0,
        "A55": 5.0,
        "B33": 6.0,
        "B35": 7.0,
        "B53": 8.0,
        "B55": 9.0,
    }
    assert set(rows) == set(expected)
    np.testing.assert_allclose(
        [rows[key] for key in sorted(expected)],
        [expected[key] for key in sorted(expected)],
        rtol=1e-12,
        atol=1e-12,
    )
    diagnostics = json.loads((output / "restoring_diagnostics.json").read_text())
    assert diagnostics["source"] == "external_reprocessing_restoring_matrix"
    assert diagnostics["source_manifest_sha256"] is None
    assert diagnostics["response_calibration_used"] is False


@pytest.mark.parametrize(
    ("motion", "column", "expected"),
    (
        ("heave", 0, {"A33": 2.0, "A53": 4.0, "B33": 6.0, "B53": 8.0}),
        ("pitch", 1, {"A35": 3.0, "A55": 5.0, "B35": 7.0, "B55": 9.0}),
    ),
)
def test_reprocess_recovers_independent_single_column_run(
    tmp_path, motion: str, column: int, expected: dict[str, float]
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "reprocessed"
    beam = 0.318
    gravity = 9.80665
    sigma = 1.4
    omega = sigma * math.sqrt(gravity / beam)
    amplitudes = (0.036 * beam, math.radians(0.43))
    arguments = {
        "target_identifier": "sun2007_troesch_prismatic_planing_hull",
        "beam_m": beam,
        "rho_water_kg_m3": 1000.0,
        "gravity_m_s2": gravity,
        "deadrise_deg": 20.0,
        "trim_deg": 4.0,
        "fn_b": 2.5,
        "mean_wetted_length_over_beam": 3.0,
        "lcg_over_beam": 1.47,
        "heave_amplitude_over_beam": 0.036,
        "pitch_amplitude_deg": 0.43,
        "sigmas": [sigma],
        "discard_cycles": 0.5,
        "retained_cycles": 1.5,
        "heave_only": motion == "heave",
        "pitch_only": motion == "pitch",
    }
    (source / "run_input_snapshot.json").write_text(
        json.dumps({"arguments": arguments, "response_calibration_used": False}),
        encoding="utf-8",
    )
    (source / "run_diagnostics.json").write_text("[]", encoding="utf-8")
    restoring = np.asarray([[100.0, -20.0], [30.0, 40.0]])
    restoring_path = tmp_path / "restoring.csv"
    with restoring_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("component", "row", "column", "value", "units"))
        writer.writerow(("total", "heave_force", "heave", restoring[0, 0], "N/m"))
        writer.writerow(("total", "heave_force", "pitch", restoring[0, 1], "N/rad"))
        writer.writerow(("total", "pitch_moment", "heave", restoring[1, 0], "N"))
        writer.writerow(("total", "pitch_moment", "pitch", restoring[1, 1], "N m/rad"))
    added = np.asarray([[2.0, 3.0], [4.0, 5.0]])
    damping = np.asarray([[6.0, 7.0], [8.0, 9.0]])
    amplitude = amplitudes[column]
    sine = restoring[:, column] * amplitude - omega**2 * amplitude * added[:, column]
    cosine = omega * amplitude * damping[:, column]
    period = 2.0 * math.pi / omega
    time = np.linspace(0.0, 2.0 * period, 241)
    loads = np.sin(omega * time)[:, None] * sine + np.cos(omega * time)[:, None] * cosine
    with (source / f"timeseries_sigma_1p4_{motion}.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(("time_s", "total_vertical_force_n", "total_pitch_moment_nm"))
        writer.writerows(zip(time, loads[:, 0], loads[:, 1]))

    reprocess(source, restoring_path, output)

    with (output / "identified_coefficients.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = {
            row["coefficient"]: float(row["value_dimensional"])
            for row in csv.DictReader(handle)
            if row["component"] == "total"
        }
    assert set(rows) == set(expected)
    np.testing.assert_allclose(
        [rows[key] for key in sorted(expected)],
        [expected[key] for key in sorted(expected)],
        rtol=1e-12,
        atol=1e-12,
    )
    snapshot = json.loads((output / "run_input_snapshot.json").read_text())
    assert snapshot["reprocessed_motion_dofs"] == [motion]
    assert snapshot["response_calibration_used"] is False
