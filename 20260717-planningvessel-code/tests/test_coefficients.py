from __future__ import annotations

import math
import unittest

from planing_seakeeping.coefficients import savitsky_deadrise_lift_slope_per_rad


class PlaningCoefficientTests(unittest.TestCase):
    def test_full_savitsky_lift_slope_matches_calm_water_formula_derivative(self) -> None:
        trim_rad = math.radians(4.0)
        lambda_w = 2.8
        fn_b = 1.67
        deadrise_deg = 16.7

        def lift_coefficient(angle_rad: float) -> float:
            angle_deg = math.degrees(angle_rad)
            bracket = (
                0.012 * math.sqrt(lambda_w)
                + 0.0055 * lambda_w**2.5 / fn_b**2
            )
            cl0 = angle_deg**1.1 * bracket
            return cl0 - 0.0065 * deadrise_deg * cl0**0.6

        step = 1.0e-7
        finite_difference = (
            lift_coefficient(trim_rad + step) - lift_coefficient(trim_rad - step)
        ) / (2.0 * step)
        analytic = savitsky_deadrise_lift_slope_per_rad(
            trim_rad,
            lambda_w,
            fn_b,
            deadrise_deg,
        )
        self.assertAlmostEqual(analytic, finite_difference, places=8)

        high_speed_only = savitsky_deadrise_lift_slope_per_rad(
            trim_rad,
            lambda_w,
            1.0e6,
            deadrise_deg,
        )
        self.assertGreater(analytic, 1.5 * high_speed_only)


if __name__ == "__main__":
    unittest.main()
