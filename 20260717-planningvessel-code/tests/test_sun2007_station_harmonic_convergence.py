from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.summarize_sun2007_station_harmonic_convergence import (
    CUMULATIVE_CHANNELS,
    summarize_station_harmonic_convergence,
)


def _write_distribution(path: Path, sine_moment_slopes: tuple[float, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ("x_from_transom_m", *CUMULATIVE_CHANNELS)
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for x in (0.0, 1.0, 2.0):
            first_length = min(x, 1.0)
            second_length = max(x - 1.0, 0.0)
            sine_moment = (
                sine_moment_slopes[0] * first_length
                + sine_moment_slopes[1] * second_length
            )
            writer.writerow(
                {
                    "x_from_transom_m": x,
                    "cumulative_sine_vertical_force_n": x,
                    "cumulative_sine_pitch_moment_nm": sine_moment,
                    "cumulative_cosine_vertical_force_n": 2.0 * x,
                    "cumulative_cosine_pitch_moment_nm": 3.0 * x,
                }
            )


def test_station_harmonic_convergence_localizes_a53_change(tmp_path: Path) -> None:
    coarse = tmp_path / "coarse.csv"
    fine = tmp_path / "fine.csv"
    _write_distribution(coarse, (1.0, 2.0))
    _write_distribution(fine, (1.1, 3.0))

    result = summarize_station_harmonic_convergence(
        [("coarse", coarse), ("fine", fine)],
        edges_m=[0.0, 1.0, 2.0],
        output=tmp_path / "out",
        omega_rad_s=2.0,
        heave_amplitude_m=0.5,
        rho_water_kg_m3=1.0,
        beam_m=1.0,
    )

    pair = result["pair_summaries"][0]
    assert pair["dominant_interval_index"] == 1
    assert pair["total_sine_pitch_moment_change_nm"] == pytest.approx(1.1)
    assert pair["total_a53_nondimensional_change"] == pytest.approx(-0.55)
    assert pair["dominant_interval_fraction_of_sum_abs_changes"] == pytest.approx(
        1.0 / 1.1
    )
    assert result["response_calibration_used"] is False
    assert (tmp_path / "out" / "adjacent_interval_changes.csv").exists()
