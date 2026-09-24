from __future__ import annotations

import unittest

import numpy as np

from scripts.predict_self_similar_deadrise_secant import (
    secant_prediction_normal_displacement,
)


class SelfSimilarDeadriseSecantTests(unittest.TestCase):
    def test_linear_normal_motion_is_extrapolated_without_rescaling(self) -> None:
        previous = np.column_stack((np.linspace(0.0, 2.0, 3), np.zeros(3)))
        current = previous + np.asarray([0.0, 1.0])
        target = current.copy()
        displacement, ratio, tangential_fraction = (
            secant_prediction_normal_displacement(
                previous,
                current,
                target,
                previous_parameter=13.0,
                current_parameter=12.75,
                target_parameter=12.5,
            )
        )
        np.testing.assert_allclose(displacement, np.ones(3))
        self.assertEqual(ratio, 1.0)
        self.assertAlmostEqual(tangential_fraction, 0.0)

    def test_rejects_duplicate_parameters(self) -> None:
        nodes = np.column_stack((np.linspace(0.0, 1.0, 3), np.zeros(3)))
        with self.assertRaisesRegex(ValueError, "distinct"):
            secant_prediction_normal_displacement(
                nodes,
                nodes,
                nodes,
                previous_parameter=12.75,
                current_parameter=12.75,
                target_parameter=12.5,
            )


if __name__ == "__main__":
    unittest.main()
