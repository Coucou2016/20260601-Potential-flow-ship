from __future__ import annotations

import unittest

import numpy as np

from scripts.diagnose_self_similar_low_mode_line_search import (
    angle_bisector_normals,
    cosine_low_pass,
    maximum_midpoint_displacement_ratio,
    trial_rejection_reason,
)


class SelfSimilarLowModeLineSearchTests(unittest.TestCase):
    def test_cosine_low_pass_preserves_only_requested_modes(self) -> None:
        index = np.arange(12, dtype=float)
        mode_zero = np.ones(12)
        mode_one = np.cos(np.pi * (index + 0.5) / 12.0)
        mode_four = np.cos(4.0 * np.pi * (index + 0.5) / 12.0)
        filtered = cosine_low_pass(mode_zero + 2.0 * mode_one + mode_four, 2)
        np.testing.assert_allclose(filtered, mode_zero + 2.0 * mode_one, atol=1.0e-12)

    def test_angle_bisector_normals_and_midpoint_displacement(self) -> None:
        nodes = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        normals = angle_bisector_normals(nodes)
        np.testing.assert_allclose(normals, [[0.0, 1.0]] * 3, atol=1.0e-14)
        shifted = nodes + np.asarray([0.0, 0.1])
        self.assertAlmostEqual(maximum_midpoint_displacement_ratio(nodes, shifted), 0.1)

    def test_trial_acceptance_requires_every_safeguard(self) -> None:
        common = {
            "source_objective": 1.0,
            "candidate_objective": 0.9,
            "minimum_relative_decrease": 0.01,
            "maximum_displacement_ratio_value": 0.1,
            "displacement_limit": 0.25,
            "source_condition_number": 100.0,
            "candidate_condition_number": 101.0,
            "condition_number_ratio_limit": 1.05,
            "dipole_coefficient": 2.0,
            "root_relative_mismatch": 1.0e-4,
            "root_mismatch_limit": 1.0e-3,
        }
        self.assertEqual(trial_rejection_reason(**common), "")
        for field, value, reason in (
            ("candidate_objective", 0.995, "insufficient_objective_decrease"),
            ("maximum_displacement_ratio_value", 0.3, "displacement_limit"),
            ("candidate_condition_number", 106.0, "condition_number_growth"),
            ("dipole_coefficient", 0.0, "nonpositive_dipole"),
            ("root_relative_mismatch", 0.01, "root_mismatch"),
        ):
            candidate = dict(common)
            candidate[field] = value
            self.assertEqual(trial_rejection_reason(**candidate), reason)


if __name__ == "__main__":
    unittest.main()
