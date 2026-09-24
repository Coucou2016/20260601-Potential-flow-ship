from __future__ import annotations

import hashlib
import math
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.config import BoatConfig, PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.longitudinal_response import (
    build_faltinsen_planing_model,
    faltinsen_head_sea_excitation,
    finite_length_strip_factors,
    frequency_time_consistency,
    solve_longitudinal_frequency_response,
    wave_amplitude_linearity,
)


class LongitudinalResponseTests(unittest.TestCase):
    def _model(self):
        boat = BoatConfig(
            length_m=6.5,
            beam_m=1.0,
            deadrise_deg=20.0,
            mass_kg=1.28 * 1025.0,
            lcg_m=2.13,
            vcg_m=0.25,
            pitch_radius_gyration_m=1.3,
            rho_water_kg_m3=1025.0,
            wetted_lengths_type=1,
        )
        state = PrescribedRunningStateConfig(enabled=True, trim_deg=4.0, lambda_w=4.0)
        speed = 3.0 * math.sqrt(boat.gravity_m_s2 * boat.beam_m)
        equilibrium = make_prescribed_equilibrium(boat, speed, state)
        matrices = compute_hydro_matrices(boat, equilibrium)
        return build_faltinsen_planing_model(
            boat,
            equilibrium,
            matrices,
            np.asarray([6.0 * boat.length_m]),
            0.01,
            point_x_forward_m=boat.length_m - boat.lcg_m,
            phase_length_m=boat.length_m,
        )

    def test_finite_length_factors_have_correct_limit_and_known_value(self):
        phase_length = 2.0
        k = np.asarray([0.0, 0.5 * math.pi / phase_length])
        heave, pitch = finite_length_strip_factors(k, phase_length)
        self.assertAlmostEqual(heave[0], 1.0, places=14)
        self.assertAlmostEqual(pitch[0], 1.0, places=14)
        s = 0.5 * math.pi
        expected_heave = 2.0 * math.sin(0.5 * s) / s
        expected_pitch = 12.0 * (-s * math.cos(0.5 * s) + 2.0 * math.sin(0.5 * s)) / s**3
        self.assertAlmostEqual(heave[1], expected_heave, places=14)
        self.assertAlmostEqual(pitch[1], expected_pitch, places=14)

    def test_excitation_matches_faltinsen_equations(self):
        a = np.asarray([[[2.0, 0.3], [-0.2, 0.8]]])
        b = np.asarray([[[4.0, -0.5], [0.7, 1.2]]])
        c = np.asarray([[[10.0, 1.0], [2.0, 6.0]]])
        omega0 = np.asarray([1.1])
        omega_e = np.asarray([1.8])
        k = np.asarray([0.4])
        speed = 3.0
        excitation = faltinsen_head_sea_excitation(a, b, c, omega0, omega_e, k, speed)
        b35d = b[0, 0, 1] + speed * a[0, 0, 0]
        b55d = b[0, 1, 1] + speed * a[0, 0, 1]
        f3s = c[0, 0, 0] - a[0, 0, 0] * omega0[0] * omega_e[0] - b35d * omega0[0] * k[0]
        f3c = c[0, 0, 1] * k[0] - a[0, 0, 1] * omega0[0] * omega_e[0] * k[0] + b[0, 0, 0] * omega0[0]
        f5s = c[0, 1, 0] - a[0, 1, 0] * omega0[0] * omega_e[0] - b55d * omega0[0] * k[0]
        f5c = c[0, 1, 1] * k[0] - a[0, 1, 1] * omega0[0] * omega_e[0] * k[0] + b[0, 1, 0] * omega0[0]
        self.assertAlmostEqual(excitation[0, 0], f3c - 1j * f3s)
        self.assertAlmostEqual(excitation[0, 1], f5c - 1j * f5s)

    def test_frequency_time_linearity_and_kinematics(self):
        model = self._model()
        target = model.metadata["target_context"]
        self.assertEqual(target["matrix_coordinate_contract"], "heave_up_pitch_bow_up_force_and_moment_about_cg")
        self.assertAlmostEqual(target["beam_m"], 1.0)
        self.assertAlmostEqual(target["deadrise_deg"], 20.0)
        self.assertAlmostEqual(target["trim_deg"], 4.0)
        self.assertAlmostEqual(target["fn_b"], 3.0)
        self.assertAlmostEqual(target["mean_wetted_length_over_b"], 4.0)
        response = solve_longitudinal_frequency_response(model)
        self.assertEqual(response.iloc[0]["matrix_contract"], "heave_pitch_2x2_v1")
        self.assertLessEqual(response.iloc[0]["equation_relative_residual"], 1.0e-10)
        consistency = frequency_time_consistency(model, 0)
        self.assertLessEqual(consistency["heave_amplitude_relative_error"], 1.0e-7)
        self.assertLessEqual(consistency["pitch_amplitude_relative_error"], 1.0e-7)
        self.assertLessEqual(consistency["heave_phase_circular_error_deg"], 1.0e-5)
        self.assertLessEqual(consistency["pitch_phase_circular_error_deg"], 1.0e-5)
        self.assertLessEqual(consistency["point_acceleration_kinematic_relative_residual"], 1.0e-12)
        linearity = wave_amplitude_linearity(model, 0, 0.005)
        for value in linearity.values():
            self.assertAlmostEqual(value, 2.0, places=7)

    def test_fridsma_direct_table_contract_and_hashes(self):
        root = Path(__file__).resolve().parents[1]
        table1_path = root / "benchmarks" / "fridsma" / "fridsma1969_table1_configurations.csv"
        table2_path = root / "benchmarks" / "fridsma" / "fridsma1969_table2_regular_waves.csv"
        table1 = pd.read_csv(table1_path)
        table2 = pd.read_csv(table2_path)
        self.assertEqual(table1["configuration"].tolist(), ["A", "B"])
        self.assertEqual(table2.groupby("configuration").size().to_dict(), {"A": 5, "B": 6})
        self.assertEqual(len(table2), 11)
        self.assertFalse(
            table2[
                [
                    "heave_rao_m_per_m",
                    "pitch_rao_rad_per_wave_slope",
                    "cg_accel_g",
                    "bow_accel_g",
                ]
            ].isna().any().any()
        )
        self.assertEqual(
            hashlib.sha256(table1_path.read_bytes()).hexdigest(),
            "e7566c993bda7778d5d2a44296215891a90a72b5071db96d3904a5d5463fbb97",
        )
        self.assertEqual(
            hashlib.sha256(table2_path.read_bytes()).hexdigest(),
            "ac0b21feb5641bfd0423c8219947373ff88448bdc995382714d99b5e7898b84c",
        )


if __name__ == "__main__":
    unittest.main()
