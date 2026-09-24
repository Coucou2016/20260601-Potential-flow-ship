from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from scripts.analyze_self_similar_kinematic_residual import (
    continuous_geometry_normal_residual_endpoint,
    continuous_linear_projection_error_contribution,
    continuous_linear_weak_projection,
    kinematic_residual_frame,
    kinematic_residual_summary,
    linear_endpoint_residual_diagnostics,
    node_pseudo_velocity_similarity_identity,
    similarity_tangential_identity,
)


class SelfSimilarKinematicResidualAnalysisTests(unittest.TestCase):
    def test_nodal_pseudo_velocity_identity_accepts_exact_straight_chain(self) -> None:
        length = np.asarray([0.75, 1.25])
        tangent = np.asarray([[1.0, 0.0], [1.0, 0.0]])
        normal = np.asarray([[0.0, -1.0], [0.0, -1.0]])
        tau = np.asarray([0.5, 1.25, 2.5])
        gradient = -tau[:, None] * np.asarray([[1.0, 0.0]])

        result = node_pseudo_velocity_similarity_identity(
            length,
            tangent,
            normal,
            tau,
            gradient,
        )

        self.assertLess(result["tangential_integral"], 1.0e-28)
        self.assertLess(result["normal_integral"], 1.0e-28)
        self.assertLess(result["tangential_max_abs"], 1.0e-14)
        self.assertLess(result["normal_max_abs"], 1.0e-14)

    def test_similarity_tangential_identity_is_exact_for_element_gradient(self) -> None:
        nodes = np.asarray([[1.0, 0.2], [2.0, 0.3], [3.0, 0.25]])
        segment = np.linalg.norm(np.diff(nodes, axis=0), axis=1)
        tangent = np.diff(nodes, axis=0) / segment[:, None]
        midpoint = 0.5 * (nodes[:-1] + nodes[1:])
        arc = np.concatenate(([0.0], np.cumsum(segment)))
        tau_star = 0.75
        tau_mid = tau_star + 0.5 * (arc[:-1] + arc[1:])
        element_s_tau = -tau_mid
        panel_velocity = midpoint + element_s_tau[:, None] * tangent
        coupled = SimpleNamespace(
            boundary=SimpleNamespace(
                panel_labels=("outer_free_surface",) * 2,
                panel_count=2,
                panel_length_m=segment,
                panel_tangent=tangent,
                panel_mid_y_m=midpoint[:, 0],
                panel_mid_z_up_m=midpoint[:, 1],
            ),
            outer_free_surface=SimpleNamespace(
                node_xi=nodes[:, 0],
                node_eta=nodes[:, 1],
                arc_length=arc,
                tau_star=tau_star,
            ),
            panel_velocity=panel_velocity,
            jet_interface=SimpleNamespace(
                root_state=SimpleNamespace(s_tau=-tau_star)
            ),
        )

        result = similarity_tangential_identity(coupled)

        self.assertLess(result["element_integral"], 1.0e-28)
        self.assertLess(result["recovered_integral"], 1.0e-28)
        self.assertAlmostEqual(result["root_absolute_mismatch"], 0.0)

    def test_continuous_geometry_normal_matches_panel_normal_on_a_straight_chain(self) -> None:
        nodes = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        length = np.ones(2)
        normal = np.asarray([[0.0, -1.0], [0.0, -1.0]])
        tangent = np.asarray([[1.0, 0.0], [1.0, 0.0]])
        q = np.asarray([[0.25, 0.5], [-0.5, 0.75]])
        coupled = SimpleNamespace(
            boundary=SimpleNamespace(
                panel_labels=("outer_free_surface",) * 2,
                panel_count=2,
                panel_length_m=length,
                panel_tangent=tangent,
                panel_normal=normal,
            ),
            outer_free_surface=SimpleNamespace(
                node_xi=nodes[:, 0],
                node_eta=nodes[:, 1],
                arc_length=np.asarray([0.0, 1.0, 2.0]),
                tau_star=1.0,
            ),
            normal_derivative_endpoint=q,
        )

        residual = continuous_geometry_normal_residual_endpoint(coupled)

        np.testing.assert_allclose(residual, q, atol=1.0e-14)

    def test_weak_projection_is_exact_for_a_globally_continuous_linear_residual(self) -> None:
        length = np.asarray([0.5, 0.75, 1.25])
        node_residual = np.asarray([1.0, -0.25, 0.75, 0.5])
        endpoint = np.column_stack((node_residual[:-1], node_residual[1:]))

        projected, load, projected_integral, unresolved = (
            continuous_linear_weak_projection(length, endpoint)
        )
        exact = float(
            np.sum(
                length
                * (
                    np.square(endpoint[:, 0])
                    + endpoint[:, 0] * endpoint[:, 1]
                    + np.square(endpoint[:, 1])
                )
                / 3.0
            )
        )

        np.testing.assert_allclose(projected, node_residual, atol=1.0e-14)
        self.assertAlmostEqual(projected_integral, exact)
        self.assertAlmostEqual(unresolved, 0.0)
        self.assertAlmostEqual(float(np.dot(projected, load)), exact)

    def test_weak_projection_exposes_discontinuous_panel_residual_content(self) -> None:
        length = np.ones(4)
        endpoint = np.asarray(
            [[1.0, 1.0], [-1.0, -1.0], [1.0, 1.0], [-1.0, -1.0]]
        )

        _, _, projected_integral, unresolved = continuous_linear_weak_projection(
            length,
            endpoint,
        )

        self.assertGreater(unresolved, 0.0)
        self.assertLess(projected_integral, 4.0)
        self.assertAlmostEqual(projected_integral + unresolved, 4.0)

    def test_projection_error_contributions_are_nonnegative_and_exact(self) -> None:
        length = np.asarray([1.0, 2.0])
        endpoint = np.asarray([[1.0, 2.0], [-1.0, 3.0]])
        projected, _, projected_integral, unresolved = (
            continuous_linear_weak_projection(length, endpoint)
        )
        contribution = continuous_linear_projection_error_contribution(
            length, endpoint, projected
        )
        self.assertTrue(np.all(contribution >= 0.0))
        self.assertAlmostEqual(float(np.sum(contribution)), unresolved)
        exact = float(
            np.sum(
                length
                * (
                    np.square(endpoint[:, 0])
                    + endpoint[:, 0] * endpoint[:, 1]
                    + np.square(endpoint[:, 1])
                )
                / 3.0
            )
        )
        self.assertAlmostEqual(projected_integral + np.sum(contribution), exact)

    def test_panel_contributions_reconstruct_source_defined_integral(self) -> None:
        length = np.asarray([0.5, 0.75, 1.0, 1.25])
        residual = np.asarray([2.0, -1.0, 0.5, -0.25])
        coupled = SimpleNamespace(
            boundary=SimpleNamespace(
                panel_labels=("outer_free_surface",) * 4,
                panel_length_m=length,
                panel_mid_y_m=np.arange(4.0),
                panel_mid_z_up_m=np.zeros(4),
            ),
            outer_kinematic_residual=residual,
        )
        expected = float(np.sum(np.square(residual) * length))

        frame = kinematic_residual_frame(coupled)
        summary = kinematic_residual_summary(
            frame,
            source_hashes={"checkpoint": "a" * 64},
            expected_integral=expected,
        )

        self.assertAlmostEqual(float(frame["k_contribution"].sum()), expected)
        self.assertAlmostEqual(summary["kinematic_integral"], expected)
        self.assertAlmostEqual(float(frame.iloc[-1]["cumulative_k_fraction"]), 1.0)
        self.assertFalse(summary["reference_used"])

    def test_endpoint_frame_reports_weak_and_strong_integrals(self) -> None:
        length = np.asarray([0.5, 0.75, 1.0, 1.25])
        endpoint = np.asarray(
            [[1.0, 0.5], [0.25, -0.5], [-0.25, 0.75], [0.5, 0.0]]
        )
        residual = np.mean(endpoint, axis=1)
        coupled = SimpleNamespace(
            boundary=SimpleNamespace(
                panel_labels=("outer_free_surface",) * 4,
                panel_length_m=length,
                panel_mid_y_m=np.arange(4.0),
                panel_mid_z_up_m=np.zeros(4),
            ),
            outer_kinematic_residual=residual,
            outer_kinematic_residual_endpoint=endpoint,
        )
        midpoint_integral = float(np.sum(np.square(residual) * length))

        frame = kinematic_residual_frame(coupled)
        summary = kinematic_residual_summary(
            frame,
            source_hashes={"checkpoint": "b" * 64},
            expected_integral=midpoint_integral,
        )

        self.assertIn("k_contribution_weak_projected", frame)
        weak = summary["continuous_p1_weak_projection"]
        self.assertGreater(weak["kinematic_integral"], 0.0)
        self.assertLessEqual(
            weak["kinematic_integral"],
            summary["kinematic_integral_linear_exact"] + 1.0e-14,
        )

    def test_endpoint_decomposition_exposes_midpoint_blind_slope_energy(self) -> None:
        length = np.asarray([1.0, 2.0])
        endpoint = np.asarray([[-1.0, 1.0], [-2.0, 2.0]])
        midpoint = np.zeros(2)

        result = linear_endpoint_residual_diagnostics(
            length,
            endpoint,
            midpoint,
        )

        self.assertAlmostEqual(result["endpoint_average_integral"], 0.0)
        self.assertAlmostEqual(result["midpoint_integral"], 0.0)
        self.assertAlmostEqual(result["within_panel_slope_integral"], 3.0)
        self.assertAlmostEqual(result["exact_integral"], 3.0)
        self.assertAlmostEqual(result["slope_fraction_of_exact"], 1.0)
        self.assertTrue(result["discontinuous_trace_dominates"])


if __name__ == "__main__":
    unittest.main()
