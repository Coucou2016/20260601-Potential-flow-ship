from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from scripts.continue_self_similar_wedge_deadrise import (
    _parser,
    _post_solve_reference_metrics,
    _transform_outer_nodes,
)


class ContinueSelfSimilarWedgeDeadriseTests(unittest.TestCase):
    def test_skip_reference_metrics_never_opens_reference_evaluators(self) -> None:
        with (
            patch(
                "scripts.continue_self_similar_wedge_deadrise."
                "evaluate_self_similar_wedge_reference"
            ) as distributed,
            patch(
                "scripts.continue_self_similar_wedge_deadrise."
                "evaluate_self_similar_wedge_scalar_reference"
            ) as scalar,
        ):
            result = _post_solve_reference_metrics(
                object(),
                reference_csv=Path("missing-distributed.csv"),
                scalar_reference_csv=Path("missing-scalar.csv"),
                skip=True,
            )

        distributed.assert_not_called()
        scalar.assert_not_called()
        self.assertEqual(result[0]["status"], "SKIPPED_BY_REQUEST")
        self.assertEqual(result[1]["status"], "SKIPPED_BY_REQUEST")
        self.assertFalse(result[0]["used_during_solve"])

    def test_parser_exposes_reference_isolated_output_mode(self) -> None:
        args = _parser().parse_args(
            [
                "--checkpoint",
                "checkpoint",
                "--target-deadrise-deg",
                "12.4",
                "--out",
                "output",
                "--skip-reference-metrics",
            ]
        )
        self.assertTrue(args.skip_reference_metrics)

    def test_root_local_xi_scale_preserves_far_endpoint_and_regular_chain(self) -> None:
        nodes = np.column_stack(
            (
                np.linspace(4.0, 20.0, 9),
                np.linspace(0.4, 0.0, 9),
            )
        )

        transformed = _transform_outer_nodes(
            nodes,
            root_xi_scale=0.98,
            taper_power=2.0,
        )

        self.assertAlmostEqual(transformed[0, 0], 0.98 * nodes[0, 0])
        np.testing.assert_allclose(transformed[-1], nodes[-1], atol=0.0)
        np.testing.assert_allclose(transformed[:, 1], nodes[:, 1], atol=0.0)
        self.assertTrue(np.all(np.diff(transformed[:, 0]) > 0.0))

    def test_transform_accepts_source_defined_overhanging_free_surface(self) -> None:
        nodes = np.asarray(
            [
                [4.4, 0.50],
                [4.3, 0.45],
                [4.25, 0.35],
                [4.35, 0.20],
                [8.0, 0.05],
            ]
        )

        transformed = _transform_outer_nodes(
            nodes,
            root_xi_scale=0.99,
            taper_power=2.0,
        )

        self.assertLess(transformed[1, 0], transformed[0, 0])
        np.testing.assert_allclose(transformed[-1], nodes[-1], atol=0.0)
        self.assertTrue(
            np.all(np.linalg.norm(np.diff(transformed, axis=0), axis=1) > 0.0)
        )

    def test_local_rotation_follows_wedge_at_root_and_tapers_to_far_field(self) -> None:
        nodes = np.asarray(
            [[4.0, 0.4], [6.0, 0.2], [10.0, 0.05], [20.0, 0.0]]
        )
        angle_deg = -0.5

        transformed = _transform_outer_nodes(
            nodes,
            root_xi_scale=1.0,
            taper_power=2.0,
            local_rotation_deg=angle_deg,
        )

        angle = np.deg2rad(angle_deg)
        root_relative = nodes[0] - np.asarray([0.0, -1.0])
        expected_root = np.asarray(
            [
                np.cos(angle) * root_relative[0]
                - np.sin(angle) * root_relative[1],
                np.sin(angle) * root_relative[0]
                + np.cos(angle) * root_relative[1],
            ]
        ) + np.asarray([0.0, -1.0])
        np.testing.assert_allclose(transformed[0], expected_root, atol=1.0e-14)
        np.testing.assert_allclose(transformed[-1], nodes[-1], atol=0.0)


if __name__ == "__main__":
    unittest.main()
