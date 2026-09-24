import math
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.config import load_config
from planing_seakeeping.solver import analyze_speed
from planing_seakeeping.types import FrequencyDomainHydrodynamics
from scripts.run_ma2005_gate1_acceptance import (
    APPROVED_REFERENCE_SHA256,
    BASE_BODY_PANELS,
    BASE_FREE_SURFACE_PANELS,
    MATRIX_RESIDUAL_TOLERANCE,
    MAX_GRID_CHANGE,
    REFINED_BODY_PANELS,
    REFINED_FREE_SURFACE_PANELS,
    RELATIVE_TOLERANCE,
    _sha256,
    _solver_input_row,
)


ROOT = Path(__file__).resolve().parents[1]


class CoreModelTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs" / "example_planing.yml")
        self.config.simulation.duration_s = 8.0
        self.config.simulation.discard_initial_s = 2.0
        self.config.simulation.time_step_s = 0.08
        self.config.waves.component_count = 16
        self.config.waves.period_count = 20

    def test_config_and_equilibrium(self):
        speed = self.config.speeds()[1]
        result = analyze_speed(self.config, speed)
        self.assertTrue(result.equilibrium.converged)
        self.assertGreater(result.equilibrium.trim_deg, 0.5)
        self.assertGreater(result.equilibrium.geometry.keel_wetted_length_m, 0.0)

    def test_matrices_and_rao_are_finite(self):
        speed = self.config.speeds()[1]
        result = analyze_speed(self.config, speed)
        self.assertGreater(np.linalg.det(result.matrices.total_mass), 0.0)
        self.assertTrue(np.isfinite(result.rao["heave_rao_m_per_m"]).all())
        self.assertTrue(np.isfinite(result.rao["pitch_rao_rad_per_m"]).all())

    def test_irregular_rms_positive(self):
        speed = self.config.speeds()[0]
        result = analyze_speed(self.config, speed)
        self.assertGreater(result.summary["heave_m_rms"], 0.0)
        self.assertGreater(result.summary["bow_vertical_accel_mps2_rms"], 0.0)
        self.assertLess(abs(result.regular_timeseries["sway_m"]).max(), 1e-12)


class FrequencyDomainContractTests(unittest.TestCase):
    def test_longitudinal_heave_pitch_matrix_contract(self):
        omega = np.array([2.0, 3.0])
        added = np.zeros((2, 6, 6))
        damping = np.zeros((2, 6, 6))
        added[:, 2:5:2, 2:5:2] = np.array([[[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]]])
        damping[:, 2:5:2, 2:5:2] = np.array(
            [[[0.1, 0.2], [0.3, 0.4]], [[0.5, 0.6], [0.7, 0.8]]]
        )
        hydro = FrequencyDomainHydrodynamics(
            omega=omega,
            encounter_omega=omega + 0.25,
            added_mass=added,
            radiation_damping=damping,
            excitation=np.zeros((2, 6), dtype=complex),
            restoring=np.zeros((2, 6, 6)),
            metadata={"provider_route": "unit_test"},
        )

        block = hydro.longitudinal_heave_pitch_matrices()

        self.assertEqual(block.added_mass.shape, (2, 2, 2))
        self.assertEqual(block.radiation_damping.shape, (2, 2, 2))
        self.assertEqual(block.row_dofs, ("heave", "pitch"))
        self.assertEqual(block.col_dofs, ("heave", "pitch"))
        self.assertEqual(block.source_dof_indices, (2, 4))
        self.assertEqual(block.metadata["matrix_contract"], "heave_pitch_2x2_v1")
        self.assertEqual(block.metadata["force_harmonic_convention"], "F=omega^2*A-i*omega*B")
        expected_force = omega[:, None, None] ** 2 * block.added_mass - 1j * omega[:, None, None] * block.radiation_damping
        self.assertTrue(np.allclose(block.complex_force_matrix, expected_force))
        self.assertAlmostEqual(block.reconstruction_relative_residual(expected_force), 0.0)


class Gate1AcceptanceProfileTests(unittest.TestCase):
    def test_gate1_profile_and_reference_hash_are_frozen(self):
        self.assertEqual((BASE_BODY_PANELS, BASE_FREE_SURFACE_PANELS), (30, 20))
        self.assertEqual((REFINED_BODY_PANELS, REFINED_FREE_SURFACE_PANELS), (40, 30))
        self.assertGreater(REFINED_BODY_PANELS, BASE_BODY_PANELS)
        self.assertGreater(REFINED_FREE_SURFACE_PANELS, BASE_FREE_SURFACE_PANELS)
        self.assertEqual(RELATIVE_TOLERANCE, 0.15)
        self.assertEqual(MAX_GRID_CHANGE, 0.02)
        self.assertEqual(MATRIX_RESIDUAL_TOLERANCE, 1.0e-8)
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        self.assertEqual(_sha256(reference), APPROVED_REFERENCE_SHA256)

    def test_reference_outputs_are_removed_before_hydrodynamic_solve(self):
        source = pd.Series(
            {
                "coefficient": "B55",
                "normalization": "ma2005",
                "length_m": 3.0,
                "reference_value": 0.0703,
                "digitization_uncertainty": 0.002,
                "reference_role": "diagnostic_reference",
                "source_figure": "Fig.18",
            }
        )

        solver_row = _solver_input_row(source)

        self.assertEqual(solver_row["coefficient"], "B55")
        self.assertEqual(solver_row["normalization"], "ma2005")
        self.assertNotIn("reference_value", solver_row)
        self.assertNotIn("digitization_uncertainty", solver_row)
        self.assertNotIn("reference_role", solver_row)
        self.assertNotIn("source_figure", solver_row)


if __name__ == "__main__":
    unittest.main()
