from __future__ import annotations

import unittest

import numpy as np

from scripts.reuse_self_similar_trust_direction import (
    reconstruct_saved_trust_direction,
)
from scripts.diagnose_self_similar_low_mode_trust_region import trust_region_scale


class ReuseSelfSimilarTrustDirectionTests(unittest.TestCase):
    def test_reconstructed_direction_preserves_constraint_and_trust_radius(self) -> None:
        jacobian = np.eye(3)
        residual = np.asarray([1.0, -2.0, 0.5])
        basis = np.eye(3)
        nodes = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        gradient = np.asarray([1.0, 1.0, 0.0])

        direction = reconstruct_saved_trust_direction(
            jacobian,
            residual,
            basis,
            nodes,
            damping=0.0,
            trust_radius=0.2,
            trust_radius_safety_factor=1.0,
            root_constraint="preserve",
            root_defect_gradient=gradient,
        )

        self.assertAlmostEqual(float(np.dot(gradient, direction)), 0.0, places=13)
        self.assertAlmostEqual(
            trust_region_scale(nodes, direction, 0.2),
            1.0,
            places=13,
        )

    def test_reconstructed_direction_closes_root_defect_before_trust_scaling(self) -> None:
        jacobian = np.eye(3)
        residual = np.asarray([1.0, -2.0, 0.5])
        basis = np.eye(3)
        nodes = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        gradient = np.asarray([1.0, 1.0, 0.0])
        source_defect = 0.1

        direction = reconstruct_saved_trust_direction(
            jacobian,
            residual,
            basis,
            nodes,
            damping=0.0,
            trust_radius=10.0,
            trust_radius_safety_factor=1.0,
            root_constraint="close",
            root_defect_gradient=gradient,
            source_signed_root_defect=source_defect,
        )

        self.assertAlmostEqual(
            source_defect + float(np.dot(gradient, direction)),
            0.0,
            places=13,
        )


if __name__ == "__main__":
    unittest.main()
