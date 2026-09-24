from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from scripts.analyze_self_similar_matching_cycles import (
    analyze_matching_surface_cycles,
    detect_matching_surface_resets,
)


def _synthetic_history(*, decaying: bool) -> pd.DataFrame:
    rows = []
    for iteration in range(100):
        cycle = iteration // 4
        phase = iteration % 4
        base = np.exp(-0.025 * iteration) if decaying else 1.0
        rows.append(
            {
                "iteration": iteration,
                "pseudo_time": 0.01 * iteration,
                "kinematic_rms": 0.1 * base * (1.06 - 0.015 * phase),
                "root_thickness": (0.15 - 0.005 * phase) * (1.0 + 0.001 * cycle),
                "root_resolution_ratio": (9.0 - 0.3 * phase) * (1.0 + 0.001 * cycle),
                "bem_condition_number": 3.5e4 if phase < 2 else 7.0e4,
            }
        )
    return pd.DataFrame(rows)


class SelfSimilarMatchingCycleTests(unittest.TestCase):
    def test_detects_one_reset_per_four_phase_cycle(self) -> None:
        history = _synthetic_history(decaying=True)
        resets = detect_matching_surface_resets(history)
        np.testing.assert_array_equal(resets, np.arange(4, 100, 4))

    def test_phase_aligned_decay_is_not_mistaken_for_a_plateau(self) -> None:
        history = _synthetic_history(decaying=True)
        cycles, phases, resets, report = analyze_matching_surface_cycles(
            history, recent_cycle_count=16
        )
        self.assertEqual(report["classification"], "PHASE_ALIGNED_DECAY")
        self.assertEqual(report["modal_cycle_length_steps"], 4)
        self.assertEqual(report["final_cycle_phase_index"], 3)
        self.assertTrue((phases["relative_change_over_window"] < -0.02).all())
        self.assertGreater(len(cycles), 20)
        self.assertGreater(len(resets), 20)

    def test_phase_aligned_plateau_remains_a_physical_failure(self) -> None:
        history = _synthetic_history(decaying=False)
        _, _, _, report = analyze_matching_surface_cycles(
            history, recent_cycle_count=16
        )
        self.assertEqual(report["classification"], "PHASE_ALIGNED_PLATEAU")
        self.assertEqual(report["physical_validation_status"], "FAIL")

    def test_prefers_source_defined_kinematic_integral_when_available(self) -> None:
        history = _synthetic_history(decaying=False)
        history["kinematic_integral"] = 0.01 * np.exp(
            -0.01 * history["iteration"]
        )
        _, phases, _, report = analyze_matching_surface_cycles(
            history, recent_cycle_count=16
        )
        self.assertEqual(report["kinematic_metric"], "kinematic_integral")
        self.assertEqual(report["classification"], "PHASE_ALIGNED_DECAY")
        self.assertTrue((phases["metric_name"] == "kinematic_integral").all())
        self.assertIn("first_metric", phases)
        self.assertIn("last_metric", phases)


if __name__ == "__main__":
    unittest.main()
