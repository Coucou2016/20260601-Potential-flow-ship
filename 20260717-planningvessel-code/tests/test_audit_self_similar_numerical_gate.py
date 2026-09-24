from __future__ import annotations

import unittest

from scripts.audit_self_similar_numerical_gate import evaluate_numerical_gate


def _level(
    panels: int,
    k: float,
    force: float,
    *,
    deadrise_deg: float = 12.75,
) -> dict[str, object]:
    return {
        "deadrise_deg": deadrise_deg,
        "outer_panel_count": panels,
        "kinematic_integral_linear_exact": k,
        "root_relative_mismatch": 1.0e-6,
        "body_vertical_force_coefficient": force,
        "finite": True,
        "reference_used_during_solve": False,
    }


class SelfSimilarNumericalGateTests(unittest.TestCase):
    def test_passes_declared_three_grid_gate(self) -> None:
        pairs, report = evaluate_numerical_gate(
            [
                _level(1280, 7.4e-4, 47.68),
                _level(320, 9.5e-4, 47.67),
                _level(640, 7.1e-4, 47.69),
            ]
        )
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["absolute_gate_pass"])
        self.assertTrue(report["deadrise_consistency_pass"])
        self.assertEqual(report["scope"], "12p75deg_three_grid_numerical_gate_only")
        self.assertEqual(pairs[-1]["fine_panel_count"], 1280)

    def test_supports_a_declared_12p5_degree_gate(self) -> None:
        _, report = evaluate_numerical_gate(
            [
                _level(320, 9.8e-4, 49.04, deadrise_deg=12.5),
                _level(640, 9.7e-4, 49.04, deadrise_deg=12.5),
                _level(1280, 9.9e-4, 49.06, deadrise_deg=12.5),
            ],
            expected_deadrise_deg=12.5,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["scope"], "12p5deg_three_grid_numerical_gate_only")

    def test_fails_when_a_checkpoint_has_a_different_deadrise(self) -> None:
        levels = [
            _level(320, 9.5e-4, 47.67),
            _level(640, 7.1e-4, 47.69, deadrise_deg=12.5),
            _level(1280, 7.4e-4, 47.68),
        ]
        _, report = evaluate_numerical_gate(levels)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["deadrise_consistency_pass"])

    def test_fails_when_finest_kinematic_change_exceeds_limit(self) -> None:
        _, report = evaluate_numerical_gate(
            [
                _level(320, 9.5e-4, 47.67),
                _level(640, 7.0e-4, 47.69),
                _level(1280, 8.0e-4, 47.68),
            ]
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["finest_pair_pass"])

    def test_fails_reference_isolation_or_absolute_gate(self) -> None:
        levels = [
            _level(320, 1.1e-3, 47.67),
            _level(640, 7.2e-4, 47.69),
            _level(1280, 7.4e-4, 47.68),
        ]
        levels[-1]["reference_used_during_solve"] = True
        _, report = evaluate_numerical_gate(levels)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["absolute_gate_pass"])
        self.assertFalse(report["reference_isolation_pass"])

    def test_rejects_a_different_panel_sequence(self) -> None:
        with self.assertRaisesRegex(ValueError, "Expected panel sequence"):
            evaluate_numerical_gate(
                [
                    _level(320, 9.0e-4, 47.67),
                    _level(640, 8.0e-4, 47.68),
                    _level(2560, 7.5e-4, 47.69),
                ]
            )


if __name__ == "__main__":
    unittest.main()
