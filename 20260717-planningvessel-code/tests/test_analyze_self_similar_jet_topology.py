from __future__ import annotations

import unittest

import pandas as pd

from scripts.analyze_self_similar_jet_topology import (
    jet_topology_event_frame,
    jet_topology_summary,
)


class SelfSimilarJetTopologyAnalysisTests(unittest.TestCase):
    def test_root_jump_and_topology_change_are_counted_independently(self) -> None:
        history = pd.DataFrame(
            {
                "iteration": [10, 11, 12, 13],
                "kinematic_integral": [0.4, 0.42, 0.36, 0.38],
                "root_thickness": [1.0, 0.95, 1.08, 1.02],
                "root_resolution_ratio": [2.0, 1.9, 2.16, 2.04],
                "bem_condition_number": [100.0, 150.0, 110.0, 105.0],
                "jet_point_count": [11, 10, 12, 11],
                "shallow_jet_panel_count_per_side": [5, 5, 6, 5],
                "boundary_panel_count": [80, 80, 82, 80],
                "provisional_matching_surface_shift_panels": [0.0] * 4,
                "final_matching_surface_shift_panels": [0.0] * 4,
                "rk2_rejected_attempt_count": [0.0] * 4,
            }
        )

        frame = jet_topology_event_frame(history)
        summary = jet_topology_summary(frame)

        self.assertEqual(summary["root_state_jump_count"], 1)
        self.assertEqual(summary["root_jumps_with_boundary_panel_change"], 1)
        self.assertEqual(summary["explicit_matching_surface_adjustment_count"], 0)
        self.assertEqual(
            summary["classification"],
            "TOPOLOGY_CHANGE_COINCIDENT_BUT_NOT_YET_CAUSAL",
        )

    def test_fixed_topology_is_not_misreported_as_cause(self) -> None:
        history = pd.DataFrame(
            {
                "iteration": [1, 2, 3, 4],
                "kinematic_integral": [0.4, 0.42, 0.36, 0.38],
                "root_thickness": [1.0, 0.95, 1.08, 1.02],
                "root_resolution_ratio": [2.0, 1.9, 2.16, 2.04],
                "bem_condition_number": [100.0, 101.0, 99.0, 100.0],
                "jet_point_count": [11, 10, 12, 11],
                "shallow_jet_panel_count_per_side": [5] * 4,
                "boundary_panel_count": [80] * 4,
            }
        )

        summary = jet_topology_summary(jet_topology_event_frame(history))

        self.assertEqual(
            summary["classification"],
            "FIXED_TOPOLOGY_DOES_NOT_REMOVE_ROOT_CYCLE",
        )


if __name__ == "__main__":
    unittest.main()
