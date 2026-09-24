from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from planing_seakeeping.forced_motion_identification import ForcedMotionMatrices
from planing_seakeeping.forced_motion_validation import (
    compare_sun2007_troesch,
    load_sun2007_troesch_benchmark,
)


class ForcedMotionValidationTests(unittest.TestCase):
    @property
    def benchmark_path(self) -> Path:
        return Path(__file__).resolve().parents[1] / "benchmarks" / "sun2007_troesch_forced_motion_coefficients.csv"

    def _benchmark_matrices(self, *, force_reciprocal_cross_added_mass: bool = False):
        beam = 0.318
        rho = 1000.0
        gravity = 9.80665
        variant = "sun_2dt_with_stern_3d_correction"
        rows = load_sun2007_troesch_benchmark(self.benchmark_path, model_variant=variant)
        sigmas = sorted({row.sigma for row in rows})
        by_key = {(row.sigma, row.coefficient): row.reference_value for row in rows}

        def scale(coefficient: str) -> float:
            power = 3 if coefficient.endswith("33") else 5 if coefficient.endswith("55") else 4
            value = rho * beam**power
            if coefficient.startswith("B"):
                value *= np.sqrt(gravity / beam)
            return value

        results = []
        for sigma in sigmas:
            added = np.asarray(
                [
                    [by_key[(sigma, "A33")] * scale("A33"), by_key[(sigma, "A35")] * scale("A35")],
                    [by_key[(sigma, "A53")] * scale("A53"), by_key[(sigma, "A55")] * scale("A55")],
                ]
            )
            if force_reciprocal_cross_added_mass:
                added[1, 0] = added[0, 1]
            damping = np.asarray(
                [
                    [by_key[(sigma, "B33")] * scale("B33"), by_key[(sigma, "B35")] * scale("B35")],
                    [by_key[(sigma, "B53")] * scale("B53"), by_key[(sigma, "B55")] * scale("B55")],
                ]
            )
            results.append(
                ForcedMotionMatrices(
                    omega_rad_s=sigma * np.sqrt(gravity / beam),
                    added_mass=added,
                    damping=damping,
                    columns=(),  # type: ignore[arg-type]
                    metadata={"synthetic_from_benchmark": True},
                )
            )
        return beam, rho, gravity, variant, results

    def test_exact_dimensional_reconstruction_passes_all_eight_coefficients(self) -> None:
        beam, rho, gravity, variant, results = self._benchmark_matrices()
        acceptance = compare_sun2007_troesch(
            results,
            benchmark_csv_path=self.benchmark_path,
            model_variant=variant,
            beam_m=beam,
            rho_water_kg_m3=rho,
            gravity_m_s2=gravity,
        )
        self.assertTrue(acceptance.passed)
        self.assertEqual(acceptance.frequency_count, 5)
        self.assertEqual(acceptance.coefficient_count, 8)
        self.assertTrue(acceptance.a35_monotonic_decrease)
        self.assertTrue(acceptance.a35_a53_nonreciprocal)
        self.assertTrue(all(metric.median_relative_error < 1e-12 for metric in acceptance.metrics))

    def test_reciprocal_cross_added_mass_is_rejected(self) -> None:
        beam, rho, gravity, variant, results = self._benchmark_matrices(force_reciprocal_cross_added_mass=True)
        acceptance = compare_sun2007_troesch(
            results,
            benchmark_csv_path=self.benchmark_path,
            model_variant=variant,
            beam_m=beam,
            rho_water_kg_m3=rho,
            gravity_m_s2=gravity,
        )
        self.assertFalse(acceptance.passed)
        self.assertFalse(acceptance.a35_a53_nonreciprocal)
        self.assertFalse(next(metric for metric in acceptance.metrics if metric.coefficient == "A53").passed)


if __name__ == "__main__":
    unittest.main()
