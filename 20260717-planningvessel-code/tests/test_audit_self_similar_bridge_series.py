from __future__ import annotations

from dataclasses import replace
import unittest

from scripts.audit_self_similar_bridge_series import (
    BridgePoint,
    continuity_metrics,
    within_rounded_upper_limit,
)


class AuditSelfSimilarBridgeSeriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.point = BridgePoint(
            run="run",
            deadrise_deg=12.425,
            formal_exact_objective=9.6e-4,
            root_relative_mismatch=1.0e-8,
            condition_number=2.5e5,
            dipole_coefficient=8.0,
            root_thickness=0.086,
            interface_s_lambda=3.13,
            measured_s_lambda=3.13,
            root_xi=4.57,
            reconstruction_relative_error=1.0e-16,
            reference_used_during_solve=False,
            summary_file="summary.json",
            checkpoint_sha256="a",
            outer_nodes_sha256="b",
        )

    def test_continuity_metrics_are_relative_to_previous_point(self) -> None:
        current = replace(
            self.point,
            deadrise_deg=12.4125,
            root_thickness=0.08643,
            interface_s_lambda=3.14565,
            dipole_coefficient=8.04,
            root_xi=4.59285,
            condition_number=2.525e5,
        )
        metrics = continuity_metrics(self.point, current)
        self.assertAlmostEqual(metrics["deadrise_step_deg"], 0.0125)
        self.assertAlmostEqual(metrics["root_thickness_relative_change"], 0.005)
        self.assertAlmostEqual(metrics["interface_s_lambda_relative_change"], 0.005)
        self.assertAlmostEqual(metrics["dipole_relative_change"], 0.005)
        self.assertAlmostEqual(metrics["root_xi_relative_change"], 0.005)
        self.assertAlmostEqual(metrics["condition_number_ratio"], 1.01)

    def test_deadrise_limit_accepts_only_binary_roundoff_above_boundary(self) -> None:
        self.assertTrue(within_rounded_upper_limit(0.012500000000001066, 0.0125))
        self.assertFalse(within_rounded_upper_limit(0.0125000001, 0.0125))


if __name__ == "__main__":
    unittest.main()
