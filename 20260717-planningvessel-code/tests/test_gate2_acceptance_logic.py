from __future__ import annotations

import unittest

import pandas as pd

from scripts.run_regular_head_sea_gate2_acceptance import _peak_metrics_for_scope


class Gate2AcceptanceLogicTests(unittest.TestCase):
    @staticmethod
    def _comparison(reference: list[float], computed: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "configuration": ["A"] * len(reference),
                "omega_e_rad_s": list(range(1, len(reference) + 1)),
                "lambda_over_l": list(reversed(range(1, len(reference) + 1))),
                "heave_rao_m_per_m": computed,
                "reference_heave_rao_m_per_m": reference,
                "pitch_rao_rad_per_wave_slope": computed,
                "reference_pitch_rao_rad_per_wave_slope": reference,
            }
        )

    def test_boundary_maximum_is_not_a_resolved_linear_scope_peak(self):
        metrics = _peak_metrics_for_scope(
            self._comparison([1.0, 0.8, 0.6], [1.0, 0.8, 0.6]),
            scope="predeclared_linear_scope",
            minimum_points=3,
            require_interior_reference_peak=True,
        )
        self.assertFalse(metrics["peak_is_resolved"].any())
        self.assertTrue(metrics["status"].eq("UNRESOLVED").all())

    def test_bracketed_interior_peak_uses_frequency_error_limit(self):
        metrics = _peak_metrics_for_scope(
            self._comparison([0.7, 1.2, 0.8], [0.6, 1.1, 0.9]),
            scope="predeclared_linear_scope",
            minimum_points=3,
            require_interior_reference_peak=True,
        )
        self.assertTrue(metrics["peak_is_resolved"].all())
        self.assertTrue(metrics["status"].eq("PASS").all())
        self.assertTrue(metrics["peak_frequency_relative_error"].eq(0.0).all())


if __name__ == "__main__":
    unittest.main()
