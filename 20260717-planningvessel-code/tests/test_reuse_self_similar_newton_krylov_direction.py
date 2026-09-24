from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.reuse_self_similar_newton_krylov_direction import (
    load_saved_normal_direction,
    map_saved_normal_direction,
    normalized_arc_coordinate,
)


class SavedNewtonDirectionTests(unittest.TestCase):
    def test_loads_last_iteration_in_node_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            pd.DataFrame(
                {
                    "outer_iteration": [1, 2, 2, 2],
                    "node_index": [0, 2, 0, 1],
                    "normal_displacement": [9.0, 3.0, 1.0, 2.0],
                }
            ).to_csv(path / "newton_krylov_direction_nodes.csv", index=False)
            direction, iteration = load_saved_normal_direction(path)
        self.assertEqual(iteration, 2)
        self.assertEqual(direction.tolist(), [1.0, 2.0, 3.0])

    def test_rejects_noncontiguous_node_indices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            pd.DataFrame(
                {
                    "outer_iteration": [1, 1],
                    "node_index": [0, 2],
                    "normal_displacement": [1.0, 2.0],
                }
            ).to_csv(path / "newton_krylov_direction_nodes.csv", index=False)
            with self.assertRaisesRegex(ValueError, "contiguous"):
                load_saved_normal_direction(path)

    def test_normalized_arc_coordinate_uses_physical_segment_length(self) -> None:
        arc = normalized_arc_coordinate(
            np.asarray([0.0, 3.0, 3.0]),
            np.asarray([0.0, 0.0, 4.0]),
        )
        np.testing.assert_allclose(arc, [0.0, 3.0 / 7.0, 1.0])

    def test_maps_direction_to_regridded_arc_without_amplitude_rescaling(self) -> None:
        mapped = map_saved_normal_direction(
            np.asarray([0.0, 2.0, 0.0]),
            np.asarray([0.0, 1.0, 2.0]),
            np.zeros(3),
            np.linspace(0.0, 2.0, 5),
            np.zeros(5),
            mapping="normalized_arc",
        )
        np.testing.assert_allclose(mapped, [0.0, 1.0, 2.0, 1.0, 0.0])

    def test_strict_mapping_rejects_a_different_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "different node counts"):
            map_saved_normal_direction(
                np.asarray([0.0, 1.0, 0.0]),
                np.asarray([0.0, 1.0, 2.0]),
                np.zeros(3),
                np.linspace(0.0, 2.0, 5),
                np.zeros(5),
                mapping="strict",
            )


if __name__ == "__main__":
    unittest.main()
