from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from scripts.analyze_self_similar_long_time_convergence import (
    analyze_long_time_convergence,
)


def _history(cycle_minima: list[float]) -> pd.DataFrame:
    rows = []
    iteration = 0
    for cycle, minimum in enumerate(cycle_minima):
        for local, factor in enumerate((1.10, 1.04, 1.0)):
            rows.append(
                {
                    "iteration": iteration,
                    "pseudo_time": 0.01 * iteration,
                    "kinematic_rms": minimum * factor,
                    "root_resolution_ratio": 1.0 if local < 2 else 1.3,
                    "bem_condition_number": (
                        100.0 if local < 2 else 60.0
                    ),
                }
            )
            iteration += 1
    return pd.DataFrame(rows)


class SelfSimilarLongTimeConvergenceTests(unittest.TestCase):
    def test_descending_cycle_envelope_is_not_declared_converged(self) -> None:
        cycles, report = analyze_long_time_convergence(
            _history([0.5, 0.45, 0.4, 0.35, 0.3, 0.25])
        )
        self.assertGreaterEqual(len(cycles), 5)
        self.assertEqual(report["classification"], "DESCENDING_NOT_CONVERGED")
        self.assertEqual(report["physical_validation_status"], "FAIL")

    def test_flat_cycle_envelope_is_classified_as_limit_cycle(self) -> None:
        _, report = analyze_long_time_convergence(
            _history([0.30, 0.301, 0.299, 0.300, 0.301, 0.300])
        )
        self.assertEqual(report["classification"], "LIMIT_CYCLE_NOT_CONVERGED")


if __name__ == "__main__":
    unittest.main()
