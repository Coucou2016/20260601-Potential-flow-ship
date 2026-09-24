from __future__ import annotations

import unittest

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import MovingWedgeConfig
from planing_seakeeping.kernels.nonlinear_2dt.planing_forced_motion import PlaningForcedMotionCase
from planing_seakeeping.kernels.nonlinear_2dt.planing_restoring import (
    estimate_planing_restoring_matrix,
    run_steady_planing_offset,
    steady_average_wetted_length_eq_7_17,
)


class Nonlinear2DtPlaningRestoringTests(unittest.TestCase):
    def test_eq_7_17_returns_mean_length_at_zero_offset(self) -> None:
        length = steady_average_wetted_length_eq_7_17(
            mean_average_wetted_length_m=0.954,
            lcg_from_transom_m=0.46746,
            vcg_m=0.2067,
            mean_trim_rad=np.radians(4.0),
            heave_m=0.0,
            pitch_rad=0.0,
        )
        self.assertAlmostEqual(length, 0.954, delta=1e-13)

    def test_steady_offset_load_is_finite_and_component_disjoint(self) -> None:
        beam = 0.32
        trim = np.radians(4.0)
        case = PlaningForcedMotionCase(
            speed_mps=2.0,
            mean_trim_rad=trim,
            wetted_length_m=0.62,
            lcg_from_transom_m=0.22,
            motion_dof="heave",
            motion_amplitude=0.0005,
            omega_rad_s=8.0,
            duration_s=2.0 * (2.0 * np.pi / 8.0),
            time_step_s=0.04,
            initial_draft_m=0.012,
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.81,
            mean_wetted_length_beam_ratio=1.1,
            transom_correction_enabled=True,
        )
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.07,
            chine_half_beam_m=0.5 * beam,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.3,
            initializer="wagner",
        )
        result = run_steady_planing_offset(config, case, vcg_m=0.08)
        self.assertTrue(np.isfinite(result.generalized_load).all())
        np.testing.assert_allclose(
            result.generalized_load,
            result.bem_generalized_load
            + result.front_generalized_load
            + result.transom_generalized_load,
            rtol=0.0,
            atol=1e-12,
        )
        self.assertAlmostEqual(result.geometry.average_wetted_length_m, 1.1 * beam)
        self.assertGreater(result.geometry.chine_wetting_x_from_leading_m, 0.0)
        self.assertGreater(result.geometry.keel_wetted_length_m, result.geometry.average_wetted_length_m)
        self.assertGreater(result.station_count, 2)
        self.assertLess(result.max_potential_bvp_relative_residual, 1e-9)
        self.assertLess(result.max_pressure_bvp_relative_residual, 1e-9)
        self.assertFalse(result.metadata["response_calibration_used"])
        np.testing.assert_allclose(
            sum(result.longitudinal_bem_bin_generalized_load.values()),
            result.raw_bem_generalized_load,
            rtol=0.0,
            atol=1e-12,
        )

    def test_restoring_result_exposes_component_step_convergence(self) -> None:
        beam = 0.32
        trim = np.radians(4.0)
        case = PlaningForcedMotionCase(
            speed_mps=2.0,
            mean_trim_rad=trim,
            wetted_length_m=0.62,
            lcg_from_transom_m=0.22,
            motion_dof="heave",
            motion_amplitude=0.0005,
            omega_rad_s=8.0,
            duration_s=2.0 * (2.0 * np.pi / 8.0),
            time_step_s=0.04,
            initial_draft_m=0.012,
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.81,
            mean_wetted_length_beam_ratio=1.1,
        )
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.07,
            chine_half_beam_m=0.5 * beam,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.3,
            initializer="wagner",
        )
        result = estimate_planing_restoring_matrix(
            config,
            case,
            vcg_m=0.08,
            heave_step_m=0.002,
            pitch_step_rad=np.radians(0.05),
            richardson_extrapolation=False,
        )

        self.assertFalse(result.metadata["step_convergence_evaluated"])
        self.assertEqual(
            set(result.component_restoring_matrices),
            set(result.coarse_component_restoring_matrices),
        )
        for component, matrix in result.component_restoring_matrices.items():
            np.testing.assert_allclose(
                matrix,
                result.coarse_component_restoring_matrices[component],
                rtol=0.0,
                atol=0.0,
            )
            np.testing.assert_allclose(
                matrix,
                result.refined_component_restoring_matrices[component],
                rtol=0.0,
                atol=0.0,
            )


if __name__ == "__main__":
    unittest.main()
