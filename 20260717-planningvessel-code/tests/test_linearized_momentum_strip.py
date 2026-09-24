from __future__ import annotations

import math
import unittest

import numpy as np

from planing_seakeeping.config import BoatConfig
from planing_seakeeping.equilibrium import solve_equilibrium
from planing_seakeeping.linearized_momentum_strip import (
    MomentumStripOptions,
    build_linearized_momentum_strip_model,
    linearize_momentum_strip,
    momentum_strip_wave_excitation_per_amplitude,
)
from planing_seakeeping.longitudinal_response import solve_longitudinal_frequency_response


class LinearizedMomentumStripTests(unittest.TestCase):
    @staticmethod
    def _boat() -> BoatConfig:
        return BoatConfig(
            length_m=1.9,
            beam_m=0.424,
            deadrise_deg=16.7,
            mass_kg=319.7 / 9.80665,
            lcg_m=0.697,
            vcg_m=0.143,
            pitch_radius_gyration_m=0.583,
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.80665,
            wetted_lengths_type=1,
        )

    def test_linearized_matrices_are_finite_and_have_positive_inertia(self) -> None:
        boat = self._boat()
        speed = 2.26 * math.sqrt(boat.gravity_m_s2 * boat.beam_m)
        equilibrium = solve_equilibrium(boat, speed)
        linearization = linearize_momentum_strip(
            boat, equilibrium, MomentumStripOptions(station_count=201)
        )
        self.assertTrue(np.isfinite(linearization.added_mass).all())
        self.assertTrue(np.isfinite(linearization.damping).all())
        self.assertTrue(np.isfinite(linearization.restoring).all())
        rigid = np.diag([boat.mass_kg, boat.mass_kg * boat.pitch_radius_gyration_m**2])
        self.assertTrue(np.all(np.linalg.eigvalsh(0.5 * (rigid + linearization.added_mass + (rigid + linearization.added_mass).T)) > 0.0))
        self.assertFalse(bool(linearization.metadata["response_calibration_used"]))

    def test_frequency_model_has_nonzero_physical_excitation_and_small_residual(self) -> None:
        boat = self._boat()
        speed = 2.26 * math.sqrt(boat.gravity_m_s2 * boat.beam_m)
        equilibrium = solve_equilibrium(boat, speed)
        model = build_linearized_momentum_strip_model(
            boat,
            equilibrium,
            np.asarray([2.0, 3.0, 4.0]) * boat.length_m,
            0.01,
            point_x_forward_m=boat.length_m - boat.lcg_m,
            options=MomentumStripOptions(station_count=201),
        )
        self.assertTrue((np.linalg.norm(model.excitation_per_wave_amplitude, axis=1) > 1.0e-12).all())
        response = solve_longitudinal_frequency_response(model)
        self.assertTrue(np.isfinite(response.select_dtypes(include=[np.number]).to_numpy()).all())
        self.assertLessEqual(float(response["equation_relative_residual"].max()), 1.0e-8)

    def test_station_wave_excitation_is_finite_and_changes_with_forward_speed(self) -> None:
        boat = self._boat()
        equilibrium = solve_equilibrium(boat, 2.26 * math.sqrt(boat.gravity_m_s2 * boat.beam_m))
        options = MomentumStripOptions(station_count=101)
        linearization = linearize_momentum_strip(boat, equilibrium, options)
        k = np.asarray([2.0 * math.pi / (3.0 * boat.length_m)])
        omega0 = np.sqrt(boat.gravity_m_s2 * k)
        encounter = omega0 + k * equilibrium.speed_through_water_mps
        with_speed = momentum_strip_wave_excitation_per_amplitude(
            boat,
            equilibrium,
            options,
            linearization.station_x_from_transom_m,
            k,
            omega0,
            encounter,
        )
        zero_encounter_increment = momentum_strip_wave_excitation_per_amplitude(
            boat,
            equilibrium,
            options,
            linearization.station_x_from_transom_m,
            k,
            omega0,
            omega0,
        )
        self.assertTrue(np.isfinite(with_speed.real).all())
        self.assertTrue(np.isfinite(with_speed.imag).all())
        self.assertGreater(float(np.linalg.norm(with_speed - zero_encounter_increment)), 1.0e-6)

    def test_sun_forced_motion_route_separates_material_and_entry_velocities(self) -> None:
        boat = self._boat()
        speed = 2.26 * math.sqrt(boat.gravity_m_s2 * boat.beam_m)
        equilibrium = solve_equilibrium(boat, speed)
        legacy = linearize_momentum_strip(
            boat,
            equilibrium,
            MomentumStripOptions(
                station_count=201,
                momentum_rate_formulation="relative_velocity_squared",
            ),
        )
        sun = linearize_momentum_strip(
            boat,
            equilibrium,
            MomentumStripOptions(
                station_count=201,
                momentum_rate_formulation="sun_faltinsen_2007_eq7_36_to_7_45",
            ),
        )
        np.testing.assert_allclose(sun.added_mass, legacy.added_mass, rtol=1.0e-10, atol=1.0e-10)
        np.testing.assert_allclose(sun.restoring, legacy.restoring, rtol=1.0e-10, atol=1.0e-10)
        self.assertGreater(float(np.linalg.norm(sun.damping - legacy.damping)), 1.0e-3)
        self.assertTrue(
            sun.metadata["added_mass_material_velocity_distinct_from_relative_entry_velocity"]
        )
        self.assertFalse(bool(sun.metadata["response_calibration_used"]))


if __name__ == "__main__":
    unittest.main()
