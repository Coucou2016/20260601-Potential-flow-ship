from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt import moving_wedge as moving_wedge_module

from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import (
    ConstantVerticalMotion,
    LinearDraftEntryMotion,
    MovingWedgeConfig,
    RegularIncidentWave2D,
    SinusoidalVerticalMotion,
    advance_moving_wedge_rk4,
    diagnose_free_surface_spray_geometry,
    evaluate_moving_wedge_rhs,
    initialize_moving_wedge_state,
    moving_wedge_boundary,
    moving_wedge_load,
    remesh_moving_wedge_free_surface,
    run_steady_planing_wedge_entry,
    _sun_five_point_third_order_smooth,
    _smooth_free_surface_near_contact,
    _linear_physical_knuckle_velocity,
    _jet_cut_threshold_m,
    _free_surface_remesh_due,
    _free_surface_smoothing_due,
    _right_jet_cut_event_geometry,
    _right_angle_jet_cut_candidate,
    _apply_right_angle_jet_cut,
)


def _config() -> MovingWedgeConfig:
    return MovingWedgeConfig(
        deadrise_rad=np.radians(20.0),
        mean_draft_m=0.12,
        chine_half_beam_m=0.55,
        free_surface_extent_m=2.0,
        water_depth_m=1.4,
        body_panels_per_side=8,
        free_surface_panels_per_side=10,
        side_wall_panels=4,
        bottom_panels=12,
        gauss_order=8,
    )


class Nonlinear2DtMovingWedgeTests(unittest.TestCase):
    def test_angle_jet_cut_requires_nodal_potential_interpolation(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires linear_node"):
            MovingWedgeConfig(
                **{
                    **_config().__dict__,
                    "jet_cut_method": "angle",
                }
            )

    def test_angle_jet_cut_constructs_source_defined_b_c_d_and_potential(self) -> None:
        beta = np.radians(20.0)
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "chine_half_beam_m": 1.0,
                "element_interpolation": "linear_node",
                "enforce_lateral_symmetry": True,
                "use_symmetry_half_domain": True,
                "jet_cut_enabled": True,
                "jet_cut_method": "angle",
                "jet_cut_ordering_safeguard_enabled": False,
            }
        )
        apex_z = -config.mean_draft_m
        tangent = np.asarray((np.cos(beta), np.sin(beta)), dtype=float)
        normal = np.asarray((-np.sin(beta), np.cos(beta)), dtype=float)
        near_body = np.asarray(
            [
                np.asarray((0.0, apex_z)) + (y / tangent[0]) * tangent - offset * normal
                for y, offset in zip(
                    (1.0, 0.92, 0.84, 0.76),
                    (0.0, 0.003, 0.006, 0.025),
                )
            ]
        )
        points = np.vstack(
            (near_body, np.asarray(((0.9, 0.0), (1.25, 0.0), (1.6, 0.0), (2.0, 0.0))))
        )
        potential = np.arange(len(points), dtype=float)

        candidate = _right_angle_jet_cut_candidate(
            config,
            apex_z_up_m=apex_z,
            free_y_m=points[:, 0],
            free_z_up_m=points[:, 1],
            free_potential_m2_s=potential,
        )

        expected_lambda0 = 0.1 * config.chine_half_beam_m / np.cos(beta)
        self.assertTrue(candidate.eligible)
        self.assertAlmostEqual(candidate.lambda0_m, expected_lambda0)
        self.assertAlmostEqual(
            candidate.e_arclength_m - float(candidate.b_arclength_m),
            0.8 * expected_lambda0,
        )
        self.assertAlmostEqual(
            float(candidate.c_arclength_m) - float(candidate.b_arclength_m),
            0.1 * expected_lambda0,
        )
        relative_d = candidate.projection_d_m - np.asarray((0.0, apex_z))
        self.assertAlmostEqual(
            tangent[0] * relative_d[1] - tangent[1] * relative_d[0],
            0.0,
            places=13,
        )

        cut_y, cut_z, cut_phi, _, applied = _apply_right_angle_jet_cut(
            config,
            apex_z_up_m=apex_z,
            free_y_m=points[:, 0],
            free_z_up_m=points[:, 1],
            free_potential_m2_s=potential,
        )
        self.assertTrue(applied)
        np.testing.assert_allclose((cut_y[0], cut_z[0]), candidate.projection_d_m)
        np.testing.assert_allclose((cut_y[1], cut_z[1]), candidate.point_c_m)
        self.assertAlmostEqual(cut_phi[0], float(candidate.potential_d_m2_s))
        self.assertAlmostEqual(cut_phi[1], float(candidate.potential_c_m2_s))

    def test_spray_geometry_diagnostic_distinguishes_monotone_and_overturning_profiles(
        self,
    ) -> None:
        monotone = diagnose_free_surface_spray_geometry(
            np.asarray([0.0, 0.5, 1.0, 1.5, 2.0]),
            np.asarray([0.0, 0.2, 0.25, 0.15, 0.0]),
        )
        self.assertEqual(monotone.overturning_panel_count, 0)
        self.assertGreater(monotone.minimum_outward_tangent_cosine, 0.0)
        self.assertIsNotNone(monotone.minimum_nonadjacent_distance_ratio)

        overturning = diagnose_free_surface_spray_geometry(
            np.asarray([0.0, 0.8, 1.4, 1.1, 0.7, 1.5, 2.2]),
            np.asarray([0.0, 0.5, 0.2, -0.1, 0.05, 0.0, 0.0]),
        )
        self.assertEqual(overturning.overturning_panel_count, 2)
        self.assertLess(overturning.minimum_outward_tangent_cosine, 0.0)
        self.assertIsNotNone(overturning.minimum_nonadjacent_distance_ratio)

    def test_initialized_wedge_records_spray_precursor_diagnostics(self) -> None:
        state = initialize_moving_wedge_state(_config(), ConstantVerticalMotion())

        self.assertEqual(state.maximum_spray_overturning_panel_count, 0)
        self.assertIsNotNone(state.minimum_spray_outward_tangent_cosine)
        self.assertGreater(state.minimum_spray_outward_tangent_cosine, 0.0)
        self.assertIsNotNone(state.minimum_spray_nonadjacent_distance_ratio)

    def test_linear_node_direct_incident_wave_advances_and_preserves_pressure_identity(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "element_interpolation": "linear_node",
                "pressure_interpolation": "constant_panel",
                "enforce_lateral_symmetry": True,
                "use_symmetry_half_domain": True,
                "initializer": "wagner",
            }
        )
        motion = ConstantVerticalMotion()
        wave = RegularIncidentWave2D(
            amplitude_m=0.001,
            omega0_rad_s=np.sqrt(9.81),
            wavenumber_rad_m=1.0,
            phase_at_time_zero_rad=0.3,
            gravity_m_s2=9.81,
        )
        state = initialize_moving_wedge_state(
            config,
            motion,
            incident_wave=wave,
        )
        step = advance_moving_wedge_rk4(
            config,
            motion,
            state,
            time_step_s=0.001,
            gravity_m_s2=9.81,
            incident_wave=wave,
        )
        load = moving_wedge_load(
            config,
            motion,
            step.state,
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.81,
            incident_wave=wave,
        )
        self.assertTrue(np.isfinite(load.pressure.gauge_pressure_pa).all())
        self.assertLess(load.pressure.free_surface_pressure_max_abs_pa, 1e-7)
        self.assertLess(step.max_potential_relative_residual, 1e-10)

    def test_static_moving_wedge_state_preserves_hydrostatic_load(self) -> None:
        config = _config()
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)
        initial_load = moving_wedge_load(config, motion, state, rho_water_kg_m3=1000.0, gravity_m_s2=9.81)
        step = advance_moving_wedge_rk4(
            config,
            motion,
            state,
            time_step_s=0.005,
            gravity_m_s2=9.81,
        )
        final_load = moving_wedge_load(config, motion, step.state, rho_water_kg_m3=1000.0, gravity_m_s2=9.81)
        expected = 1000.0 * 9.81 * (config.mean_draft_m**2 / np.tan(config.deadrise_rad))
        self.assertAlmostEqual(initial_load.pressure.body_vertical_force_per_length_n_m, expected, delta=1e-8 * expected)
        self.assertAlmostEqual(final_load.pressure.body_vertical_force_per_length_n_m, expected, delta=1e-8 * expected)
        self.assertLess(final_load.contact_constraint_max_abs_m, 1e-13)
        self.assertLess(step.max_potential_relative_residual, 1e-11)

    def test_forced_heave_updates_body_contact_without_pressure_identity_loss(self) -> None:
        config = _config()
        motion = SinusoidalVerticalMotion(amplitude_m=0.002, omega_rad_s=4.0)
        state = initialize_moving_wedge_state(config, motion)
        initial_contact = float(state.right_free_y_m[0])
        for _ in range(4):
            state = advance_moving_wedge_rk4(
                config,
                motion,
                state,
                time_step_s=0.002,
                gravity_m_s2=9.81,
            ).state
        load = moving_wedge_load(config, motion, state, rho_water_kg_m3=1000.0, gravity_m_s2=9.81)
        self.assertNotAlmostEqual(float(state.right_free_y_m[0]), initial_contact, places=10)
        self.assertLess(load.contact_constraint_max_abs_m, 1e-13)
        self.assertLess(load.pressure.free_surface_pressure_max_abs_pa, 1e-7)
        self.assertLess(load.pressure.auxiliary_solution.relative_residual, 1e-10)
        self.assertTrue(np.isfinite(load.pressure.body_vertical_force_per_length_n_m))

    def test_wagner_initializer_matches_sun_eq_2_14_and_2_15(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "mean_draft_m": 0.04,
                "initializer": "wagner",
            }
        )
        state = initialize_moving_wedge_state(config, ConstantVerticalMotion())
        expected_contact = (
            np.pi * config.mean_draft_m / (2.0 * np.tan(config.deadrise_rad))
        )
        self.assertAlmostEqual(state.right_free_y_m[0], expected_contact)
        expected_z = (
            state.right_free_y_m
            * config.mean_draft_m
            / expected_contact
            * np.arcsin(np.clip(expected_contact / state.right_free_y_m, 0.0, 1.0))
            - config.mean_draft_m
        )
        np.testing.assert_allclose(state.right_free_z_up_m, expected_z, rtol=0.0, atol=1e-14)
        np.testing.assert_allclose(state.left_free_z_up_m, expected_z[::-1], rtol=0.0, atol=1e-14)
        np.testing.assert_allclose(state.right_free_potential_m2_s, 0.0)
        np.testing.assert_allclose(state.left_free_potential_m2_s, 0.0)

    def test_wagner_contact_advances_by_free_endpoint_then_body_projection(self) -> None:
        beta = np.radians(20.0)
        entry_speed = 1.0
        initial_draft = 0.01
        reference_draft = 0.1
        config = MovingWedgeConfig(
            deadrise_rad=beta,
            mean_draft_m=reference_draft,
            chine_half_beam_m=1.5,
            free_surface_extent_m=2.0,
            water_depth_m=1.0,
            body_panels_per_side=16,
            free_surface_panels_per_side=32,
            side_wall_panels=6,
            bottom_panels=32,
            gauss_order=8,
            element_interpolation="linear_node",
            pressure_interpolation="match_potential",
            initializer="wagner",
            free_surface_remesh_enabled=False,
            free_surface_smoothing_enabled=False,
            free_surface_spacing_mode="body_matched_geometric",
            enforce_lateral_symmetry=True,
            use_symmetry_half_domain=True,
            chine_separation_enabled=False,
            jet_cut_enabled=True,
        )
        motion = LinearDraftEntryMotion(
            reference_draft_m=reference_draft,
            initial_draft_m=initial_draft,
            draft_rate_mps=entry_speed,
        )
        state = initialize_moving_wedge_state(config, motion)
        time_step = 1e-6
        advanced = advance_moving_wedge_rk4(
            config,
            motion,
            state,
            time_step_s=time_step,
            gravity_m_s2=0.0,
        ).state
        numerical_contact_speed = (
            advanced.right_free_y_m[0] - state.right_free_y_m[0]
        ) / time_step
        wagner_contact_speed = np.pi * entry_speed / (2.0 * np.tan(beta))

        self.assertLess(
            abs(numerical_contact_speed / wagner_contact_speed - 1.0),
            0.15,
        )
        apex_z = -reference_draft + motion.displacement_m(advanced.time_s)
        self.assertAlmostEqual(
            advanced.right_free_z_up_m[0],
            apex_z + advanced.right_free_y_m[0] * np.tan(beta),
            places=12,
        )

    def test_cubic_remesh_preserves_contacts_and_reduces_panel_length_spread(self) -> None:
        config = _config()
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)
        right_y = state.right_free_y_m.copy()
        right_y[1:-1] = state.right_free_y_m[0] + (
            (state.right_free_y_m[1:-1] - state.right_free_y_m[0])
            / (state.right_free_y_m[-1] - state.right_free_y_m[0])
        ) ** 2 * (state.right_free_y_m[-1] - state.right_free_y_m[0])
        distorted = type(state)(
            right_free_y_m=right_y,
            right_free_z_up_m=state.right_free_z_up_m,
            left_free_y_m=state.left_free_y_m,
            left_free_z_up_m=state.left_free_z_up_m,
            right_free_potential_m2_s=np.sin(np.linspace(0.0, np.pi, len(right_y) - 1)),
            left_free_potential_m2_s=state.left_free_potential_m2_s,
            time_s=state.time_s,
        )
        before = np.ptp(np.hypot(np.diff(distorted.right_free_y_m), np.diff(distorted.right_free_z_up_m)))
        remeshed = remesh_moving_wedge_free_surface(config, motion, distorted)
        after = np.ptp(np.hypot(np.diff(remeshed.right_free_y_m), np.diff(remeshed.right_free_z_up_m)))
        self.assertLess(after, 0.05 * before)
        self.assertAlmostEqual(remeshed.right_free_y_m[0], distorted.right_free_y_m[0])
        self.assertAlmostEqual(remeshed.right_free_y_m[-1], config.free_surface_extent_m)
        load = moving_wedge_load(config, motion, remeshed)
        self.assertLess(load.contact_constraint_max_abs_m, 1e-13)

    def test_body_matched_geometric_spacing_resolves_contact_and_grows_outward(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "mean_draft_m": 0.08,
                "free_surface_spacing_mode": "body_matched_geometric",
            }
        )
        state = initialize_moving_wedge_state(config, ConstantVerticalMotion())
        free_panel_length = np.hypot(
            np.diff(state.right_free_y_m), np.diff(state.right_free_z_up_m)
        )
        body_panel_length = state.right_free_y_m[0] / (
            config.body_panels_per_side * np.cos(config.deadrise_rad)
        )

        self.assertLess(abs(free_panel_length[0] / body_panel_length - 1.0), 0.25)
        self.assertTrue(np.all(np.diff(free_panel_length) >= -1e-12))
        self.assertGreater(free_panel_length[-1], free_panel_length[0])

    def test_near_body_uniform_spacing_does_not_depend_on_smoothing_switch(self) -> None:
        base = {
            **_config().__dict__,
            "mean_draft_m": 0.08,
            "free_surface_spacing_mode": "body_matched_geometric",
            "free_surface_uniform_near_body_panel_count": 4,
        }
        enabled = initialize_moving_wedge_state(
            MovingWedgeConfig(**{**base, "free_surface_smoothing_enabled": True}),
            ConstantVerticalMotion(),
        )
        disabled = initialize_moving_wedge_state(
            MovingWedgeConfig(**{**base, "free_surface_smoothing_enabled": False}),
            ConstantVerticalMotion(),
        )

        np.testing.assert_allclose(enabled.right_free_y_m, disabled.right_free_y_m)
        enabled_lengths = np.hypot(
            np.diff(enabled.right_free_y_m), np.diff(enabled.right_free_z_up_m)
        )
        np.testing.assert_allclose(enabled_lengths[:4], enabled_lengths[0])

    def test_sun_five_point_smoother_preserves_cubic_sequences(self) -> None:
        abscissa = np.arange(9.0)
        values = 1.2 - 0.4 * abscissa + 0.3 * abscissa**2 - 0.07 * abscissa**3

        np.testing.assert_allclose(
            _sun_five_point_third_order_smooth(values),
            values,
            rtol=0.0,
            atol=2e-13,
        )

    def test_near_contact_smoothing_preserves_intersection_position_and_potential(
        self,
    ) -> None:
        y = np.linspace(0.12, 0.9, 8)
        z = np.asarray([0.03, 0.08, 0.02, 0.11, 0.04, 0.14, 0.05, 0.16])
        potential = np.asarray([1.7, 0.2, 1.1, -0.4, 0.8, -0.2, 0.5, 0.1])

        smooth_y, smooth_z, smooth_potential = _smooth_free_surface_near_contact(
            y,
            z,
            potential,
            node_count=7,
        )

        self.assertEqual(smooth_y[0], y[0])
        self.assertEqual(smooth_z[0], z[0])
        self.assertEqual(smooth_potential[0], potential[0])
        self.assertFalse(np.allclose(smooth_potential[1:7], potential[1:7]))

    def test_physical_time_smoothing_cadence_crosses_each_boundary_once(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "free_surface_smoothing_interval_s": 0.1,
            }
        )

        self.assertFalse(
            _free_surface_smoothing_due(config, start_time_s=0.0, end_time_s=0.05)
        )
        self.assertTrue(
            _free_surface_smoothing_due(config, start_time_s=0.05, end_time_s=0.1)
        )
        self.assertFalse(
            _free_surface_smoothing_due(config, start_time_s=0.1, end_time_s=0.15)
        )
        self.assertTrue(
            _free_surface_smoothing_due(config, start_time_s=0.15, end_time_s=0.2)
        )

    def test_physical_time_remesh_cadence_crosses_each_boundary_once(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "free_surface_remesh_interval_s": 0.1,
            }
        )

        self.assertFalse(
            _free_surface_remesh_due(config, start_time_s=0.0, end_time_s=0.05)
        )
        self.assertTrue(
            _free_surface_remesh_due(config, start_time_s=0.05, end_time_s=0.1)
        )
        self.assertFalse(
            _free_surface_remesh_due(config, start_time_s=0.1, end_time_s=0.15)
        )
        self.assertTrue(
            _free_surface_remesh_due(config, start_time_s=0.15, end_time_s=0.2)
        )

    def test_rk4_remesh_uses_physical_time_cadence(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "free_surface_remesh_interval_s": 0.01,
                "free_surface_smoothing_interval_s": 0.01,
            }
        )
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)

        with patch.object(
            moving_wedge_module,
            "remesh_moving_wedge_free_surface",
            wraps=remesh_moving_wedge_free_surface,
        ) as remesher:
            first = advance_moving_wedge_rk4(
                config,
                motion,
                state,
                time_step_s=0.005,
            )
            self.assertEqual(remesher.call_count, 0)
            advance_moving_wedge_rk4(
                config,
                motion,
                first.state,
                time_step_s=0.005,
            )
            self.assertEqual(remesher.call_count, 1)

    def test_remesh_can_skip_smoothing_without_disabling_remeshing(self) -> None:
        config = _config()
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)

        with patch.object(
            moving_wedge_module,
            "_smooth_free_surface_near_contact",
            wraps=_smooth_free_surface_near_contact,
        ) as smoother:
            remesh_moving_wedge_free_surface(
                config,
                motion,
                state,
                apply_smoothing=False,
            )
            self.assertEqual(smoother.call_count, 0)
            remesh_moving_wedge_free_surface(
                config,
                motion,
                state,
                apply_smoothing=True,
            )
            self.assertEqual(smoother.call_count, 2)

    def test_smoothing_interval_must_be_finite_and_positive(self) -> None:
        for invalid in (0.0, -0.1, np.inf, np.nan):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                MovingWedgeConfig(
                    **{
                        **_config().__dict__,
                        "free_surface_smoothing_interval_s": invalid,
                    }
                )

    def test_remesh_interval_must_be_finite_and_positive(self) -> None:
        for invalid in (0.0, -0.1, np.inf, np.nan):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                MovingWedgeConfig(
                    **{
                        **_config().__dict__,
                        "free_surface_remesh_interval_s": invalid,
                    }
                )

    def test_linear_rk4_freezes_one_normal_derivative_solve_per_step(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "element_interpolation": "linear_node",
                "enforce_lateral_symmetry": True,
                "use_symmetry_half_domain": True,
            }
        )
        motion = SinusoidalVerticalMotion(amplitude_m=0.001, omega_rad_s=3.0)
        state = initialize_moving_wedge_state(config, motion)
        original = moving_wedge_module._solve_linear_free_surface_normal_derivative

        with patch.object(
            moving_wedge_module,
            "_solve_linear_free_surface_normal_derivative",
            wraps=original,
        ) as solve:
            advance_moving_wedge_rk4(
                config,
                motion,
                state,
                time_step_s=0.002,
                gravity_m_s2=9.81,
            )

        solve.assert_called_once()

    def test_linear_free_surface_constant_panel_pressure_matches_direct_route(self) -> None:
        linear_config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "element_interpolation": "linear_node",
                "pressure_interpolation": "constant_panel",
                "enforce_lateral_symmetry": True,
                "use_symmetry_half_domain": True,
            }
        )
        motion = SinusoidalVerticalMotion(amplitude_m=0.001, omega_rad_s=3.0)
        state = initialize_moving_wedge_state(linear_config, motion)
        linear_load = moving_wedge_load(linear_config, motion, state)
        panel_state = type(state)(
            right_free_y_m=state.right_free_y_m,
            right_free_z_up_m=state.right_free_z_up_m,
            left_free_y_m=state.left_free_y_m,
            left_free_z_up_m=state.left_free_z_up_m,
            right_free_potential_m2_s=0.5
            * (
                state.right_free_potential_m2_s[:-1]
                + state.right_free_potential_m2_s[1:]
            ),
            left_free_potential_m2_s=0.5
            * (
                state.left_free_potential_m2_s[:-1]
                + state.left_free_potential_m2_s[1:]
            ),
            time_s=state.time_s,
        )
        panel_load = moving_wedge_load(
            MovingWedgeConfig(
                **{
                    **linear_config.__dict__,
                    "element_interpolation": "constant_panel",
                    "pressure_interpolation": "match_potential",
                }
            ),
            motion,
            panel_state,
        )

        self.assertAlmostEqual(
            linear_load.pressure.body_vertical_force_per_length_n_m,
            panel_load.pressure.body_vertical_force_per_length_n_m,
        )
        self.assertEqual(
            linear_load.pressure.status,
            "sun_ch2_linear_free_surface_constant_panel_pressure_bvp",
        )

    def test_body_matched_remesh_grows_away_from_both_contacts(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "mean_draft_m": 0.08,
                "free_surface_spacing_mode": "body_matched_geometric",
                "enforce_lateral_symmetry": True,
            }
        )
        state = initialize_moving_wedge_state(config, ConstantVerticalMotion())
        remeshed = remesh_moving_wedge_free_surface(
            config,
            ConstantVerticalMotion(),
            state,
        )
        right_length = np.hypot(
            np.diff(remeshed.right_free_y_m),
            np.diff(remeshed.right_free_z_up_m),
        )
        left_length_from_contact = np.hypot(
            np.diff(remeshed.left_free_y_m),
            np.diff(remeshed.left_free_z_up_m),
        )[::-1]

        self.assertTrue(np.all(np.diff(right_length) >= -1e-12))
        self.assertTrue(np.all(np.diff(left_length_from_contact) >= -1e-12))
        np.testing.assert_allclose(left_length_from_contact, right_length)

    def test_optional_symmetry_projection_removes_lateral_roundoff_mode(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "enforce_lateral_symmetry": True,
            }
        )
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)
        perturbed_right_z = state.right_free_z_up_m.copy()
        perturbed_right_z[2] += 1e-5
        perturbed = type(state)(
            right_free_y_m=state.right_free_y_m,
            right_free_z_up_m=perturbed_right_z,
            left_free_y_m=state.left_free_y_m,
            left_free_z_up_m=state.left_free_z_up_m,
            right_free_potential_m2_s=state.right_free_potential_m2_s,
            left_free_potential_m2_s=state.left_free_potential_m2_s,
            time_s=state.time_s,
        )
        remeshed = remesh_moving_wedge_free_surface(config, motion, perturbed)

        np.testing.assert_allclose(remeshed.left_free_y_m, -remeshed.right_free_y_m[::-1])
        np.testing.assert_allclose(remeshed.left_free_z_up_m, remeshed.right_free_z_up_m[::-1])
        np.testing.assert_allclose(
            remeshed.left_free_potential_m2_s,
            remeshed.right_free_potential_m2_s[::-1],
        )

    def test_symmetry_half_domain_matches_full_domain_force_and_contact_rhs(self) -> None:
        full_config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "enforce_lateral_symmetry": True,
            }
        )
        half_config = MovingWedgeConfig(
            **{
                **full_config.__dict__,
                "use_symmetry_half_domain": True,
            }
        )
        motion = SinusoidalVerticalMotion(amplitude_m=0.001, omega_rad_s=3.0)
        full_state = initialize_moving_wedge_state(full_config, motion)
        half_state = initialize_moving_wedge_state(half_config, motion)

        full_rhs = evaluate_moving_wedge_rhs(full_config, motion, full_state)
        half_rhs = evaluate_moving_wedge_rhs(half_config, motion, half_state)
        full_load = moving_wedge_load(full_config, motion, full_state)
        half_load = moving_wedge_load(half_config, motion, half_state)

        self.assertLess(half_load.boundary.panel_count, full_load.boundary.panel_count)
        self.assertAlmostEqual(
            half_rhs.right_node_velocity_mps[0, 0],
            full_rhs.right_node_velocity_mps[0, 0],
            delta=0.06 * max(abs(full_rhs.right_node_velocity_mps[0, 0]), 1e-12),
        )
        self.assertAlmostEqual(
            half_load.pressure.body_vertical_force_per_length_n_m,
            full_load.pressure.body_vertical_force_per_length_n_m,
            delta=0.03 * max(abs(full_load.pressure.body_vertical_force_per_length_n_m), 1.0),
        )
        np.testing.assert_allclose(
            half_rhs.left_node_velocity_mps,
            half_rhs.right_node_velocity_mps[::-1] * np.asarray((-1.0, 1.0)),
        )

    def test_chine_separation_clamps_contact_to_moving_hard_chine(self) -> None:
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.065,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.5,
            water_depth_m=1.0,
            body_panels_per_side=8,
            free_surface_panels_per_side=10,
            side_wall_panels=4,
            bottom_panels=12,
            gauss_order=8,
            chine_separation_enabled=True,
        )
        motion = SinusoidalVerticalMotion(amplitude_m=0.001, omega_rad_s=3.0)
        state = initialize_moving_wedge_state(config, motion)
        self.assertAlmostEqual(state.right_free_y_m[0], config.chine_half_beam_m)
        initial_chine_z = -config.mean_draft_m + config.chine_half_beam_m * np.tan(config.deadrise_rad)
        self.assertAlmostEqual(state.right_free_z_up_m[0], initial_chine_z)
        step = advance_moving_wedge_rk4(
            config,
            motion,
            state,
            time_step_s=0.002,
            gravity_m_s2=9.81,
        )
        self.assertAlmostEqual(step.state.right_free_y_m[0], config.chine_half_beam_m)
        expected_z = (
            -config.mean_draft_m
            + motion.displacement_m(step.state.time_s)
            + config.chine_half_beam_m * np.tan(config.deadrise_rad)
        )
        self.assertAlmostEqual(step.state.right_free_z_up_m[0], expected_z)
        load = moving_wedge_load(config, motion, step.state)
        self.assertLess(load.contact_constraint_max_abs_m, 1e-13)

    def test_artificial_surface_separation_converts_knuckle_extension(self) -> None:
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.065,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.5,
            water_depth_m=1.0,
            body_panels_per_side=8,
            free_surface_panels_per_side=10,
            side_wall_panels=4,
            bottom_panels=12,
            gauss_order=8,
            chine_separation_enabled=True,
            knuckle_separation_model="artificial_surface",
        )
        motion = SinusoidalVerticalMotion(amplitude_m=0.001, omega_rad_s=3.0)
        state = initialize_moving_wedge_state(config, motion)
        step = advance_moving_wedge_rk4(
            config,
            motion,
            state,
            time_step_s=0.002,
            gravity_m_s2=9.81,
        )
        self.assertGreater(step.state.right_free_y_m[0], config.chine_half_beam_m)
        boundary = moving_wedge_boundary(config, motion, step.state)
        labels = np.asarray(boundary.panel_labels, dtype=object)
        self.assertEqual(int(np.count_nonzero(labels == "artificial_body")), 2)
        load = moving_wedge_load(
            config,
            motion,
            step.state,
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.81,
        )
        self.assertEqual(load.pressure.body_panel_count, 2 * config.body_panels_per_side)
        self.assertTrue(np.isfinite(load.pressure.body_vertical_force_per_length_n_m))
        self.assertLess(load.contact_constraint_max_abs_m, 1e-10)

    def test_knuckle_velocity_uses_physical_panel_adjacent_to_separation_point(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "knuckle_separation_model": "artificial_surface",
            }
        )
        state = initialize_moving_wedge_state(config, ConstantVerticalMotion())
        boundary = moving_wedge_boundary(config, ConstantVerticalMotion(), state)
        labels = np.asarray(boundary.panel_labels, dtype=object)
        body = np.flatnonzero(
            (labels == "body") & (boundary.panel_mid_y_m >= -1e-12)
        )
        ordered = body[np.argsort(boundary.panel_mid_y_m[body])]
        knuckle_node = (int(ordered[-1]) + 1) % boundary.panel_count
        chine_y = float(boundary.node_y_m[knuckle_node])
        potential = np.zeros(boundary.panel_count, dtype=float)
        expected_speed = 1.7
        a_three_halves = 0.4
        for panel in ordered:
            right = (int(panel) + 1) % boundary.panel_count
            distance = (
                chine_y - float(boundary.panel_mid_y_m[panel])
            ) / abs(float(boundary.panel_tangent[panel, 0]))
            tangential_speed = expected_speed - 1.5 * a_three_halves * np.sqrt(
                max(distance, 0.0)
            )
            potential[right] = (
                potential[int(panel)]
                + tangential_speed * float(boundary.panel_length_m[panel])
            )

        velocity = _linear_physical_knuckle_velocity(
            boundary,
            SimpleNamespace(potential_m2_s=potential),
            body_velocity_z=0.0,
        )
        tangent = boundary.panel_tangent[int(ordered[-1])]
        normal = boundary.panel_normal[int(ordered[-1])]
        adjacent_panel = int(ordered[-1])
        adjacent_distance = (
            chine_y - float(boundary.panel_mid_y_m[adjacent_panel])
        ) / abs(float(boundary.panel_tangent[adjacent_panel, 0]))
        adjacent_speed = expected_speed - 1.5 * a_three_halves * np.sqrt(
            adjacent_distance
        )
        self.assertAlmostEqual(float(np.dot(velocity, tangent)), adjacent_speed, places=12)
        self.assertAlmostEqual(float(np.dot(velocity, normal)), 0.0, places=12)

    def test_knuckle_incident_wave_separates_disturbance_and_total_normal_velocity(
        self,
    ) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "knuckle_separation_model": "artificial_surface",
            }
        )
        state = initialize_moving_wedge_state(config, ConstantVerticalMotion())
        boundary = moving_wedge_boundary(config, ConstantVerticalMotion(), state)
        labels = np.asarray(boundary.panel_labels, dtype=object)
        physical = np.flatnonzero(
            (labels == "body") & (boundary.panel_mid_y_m >= -1e-12)
        )
        knuckle_panel = int(physical[np.argmax(boundary.panel_mid_y_m[physical])])
        potential = SimpleNamespace(
            potential_m2_s=np.zeros(boundary.panel_count, dtype=float)
        )
        body_velocity = 0.8
        incident_vertical_velocity = 0.3

        disturbance = _linear_physical_knuckle_velocity(
            boundary,
            potential,
            body_velocity_z=body_velocity,
            incident_vertical_velocity_mps=incident_vertical_velocity,
        )
        total = disturbance + np.asarray((0.0, incident_vertical_velocity))
        normal = boundary.panel_normal[knuckle_panel]

        self.assertAlmostEqual(
            float(np.dot(disturbance, normal)),
            float(normal[1] * (body_velocity - incident_vertical_velocity)),
            places=12,
        )
        self.assertAlmostEqual(
            float(np.dot(total, normal)),
            float(normal[1] * body_velocity),
            places=12,
        )

    def test_separated_linear_node_incident_wave_remains_finite_over_many_steps(
        self,
    ) -> None:
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.065,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.5,
            water_depth_m=1.0,
            body_panels_per_side=8,
            free_surface_panels_per_side=10,
            side_wall_panels=4,
            bottom_panels=12,
            gauss_order=8,
            element_interpolation="linear_node",
            pressure_interpolation="constant_panel",
            enforce_lateral_symmetry=True,
            use_symmetry_half_domain=True,
            chine_separation_enabled=True,
            knuckle_separation_model="artificial_surface",
        )
        motion = ConstantVerticalMotion()
        wave = RegularIncidentWave2D(
            amplitude_m=1e-4,
            omega0_rad_s=np.sqrt(9.81),
            wavenumber_rad_m=1.0,
            phase_at_time_zero_rad=0.3,
            gravity_m_s2=9.81,
        )
        state = initialize_moving_wedge_state(
            config,
            motion,
            incident_wave=wave,
        )
        self.assertAlmostEqual(state.right_free_y_m[0], config.chine_half_beam_m)

        for _ in range(25):
            step = advance_moving_wedge_rk4(
                config,
                motion,
                state,
                time_step_s=0.001,
                gravity_m_s2=9.81,
                incident_wave=wave,
            )
            state = step.state
            self.assertTrue(np.isfinite(state.right_free_y_m).all())
            self.assertTrue(np.isfinite(state.right_free_z_up_m).all())
            self.assertTrue(np.isfinite(state.right_free_potential_m2_s).all())
            self.assertLess(step.max_potential_relative_residual, 1e-9)

    def test_linear_pressure_uses_knuckle_velocity_after_artificial_separation(self) -> None:
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.065,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.5,
            water_depth_m=1.0,
            body_panels_per_side=8,
            free_surface_panels_per_side=10,
            side_wall_panels=4,
            bottom_panels=12,
            gauss_order=8,
            element_interpolation="linear_node",
            pressure_interpolation="match_potential",
            enforce_lateral_symmetry=True,
            use_symmetry_half_domain=True,
            chine_separation_enabled=True,
            knuckle_separation_model="artificial_surface",
        )
        motion = SinusoidalVerticalMotion(amplitude_m=0.001, omega_rad_s=3.0)
        state = initialize_moving_wedge_state(config, motion)
        state = advance_moving_wedge_rk4(
            config,
            motion,
            state,
            time_step_s=0.002,
            gravity_m_s2=9.81,
        ).state
        original = moving_wedge_module._linear_physical_knuckle_velocity

        with patch.object(
            moving_wedge_module,
            "_linear_physical_knuckle_velocity",
            wraps=original,
        ) as fit:
            moving_wedge_load(
                config,
                motion,
                state,
                rho_water_kg_m3=1000.0,
                gravity_m_s2=9.81,
            )

        fit.assert_called_once()

    def test_thin_jet_cut_replaces_contact_and_second_node_by_body_projection(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "mean_draft_m": 0.08,
                "jet_cut_enabled": True,
                "jet_cut_distance_fraction": 1.0,
            }
        )
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)
        old_contact = float(state.right_free_y_m[0])
        projected_y = 0.99 * old_contact
        tangent = np.asarray(
            (np.cos(config.deadrise_rad), np.sin(config.deadrise_rad)), dtype=float
        )
        outward_normal = np.asarray((-tangent[1], tangent[0]), dtype=float)
        apex_z = -config.mean_draft_m
        projected_point = np.asarray(
            (projected_y, apex_z + projected_y * np.tan(config.deadrise_rad)),
            dtype=float,
        )
        point_b = projected_point - 0.02 * outward_normal
        self.assertGreater(point_b[0], old_contact)

        right_y = state.right_free_y_m.copy()
        right_z = state.right_free_z_up_m.copy()
        right_y[1], right_z[1] = point_b
        left_y = -right_y[::-1]
        left_z = right_z[::-1]
        distorted = type(state)(
            right_free_y_m=right_y,
            right_free_z_up_m=right_z,
            left_free_y_m=left_y,
            left_free_z_up_m=left_z,
            right_free_potential_m2_s=state.right_free_potential_m2_s,
            left_free_potential_m2_s=state.left_free_potential_m2_s,
            time_s=state.time_s,
        )
        remeshed = remesh_moving_wedge_free_surface(config, motion, distorted)

        self.assertEqual(len(remeshed.right_free_y_m), len(state.right_free_y_m))
        self.assertEqual(remeshed.jet_cut_count, 2)
        self.assertIsNotNone(remeshed.minimum_jet_normal_distance_ratio)
        self.assertLess(remeshed.minimum_jet_normal_distance_ratio, 1.0)
        self.assertLess(remeshed.right_free_y_m[0], old_contact)
        self.assertAlmostEqual(remeshed.right_free_y_m[0], projected_y, places=12)
        self.assertAlmostEqual(
            remeshed.right_free_z_up_m[0],
            apex_z + projected_y * np.tan(config.deadrise_rad),
            places=12,
        )
        load = moving_wedge_load(config, motion, remeshed)
        self.assertLess(load.contact_constraint_max_abs_m, 1e-12)

    def test_thin_jet_lateral_overturning_alone_does_not_trigger_cut(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "mean_draft_m": 0.08,
                "jet_cut_enabled": True,
                "jet_cut_distance_fraction": 0.25,
                "jet_cut_ordering_safeguard_enabled": False,
                "enforce_lateral_symmetry": True,
            }
        )
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)
        contact = float(state.right_free_y_m[0])
        tangent = np.asarray(
            (np.cos(config.deadrise_rad), np.sin(config.deadrise_rad)), dtype=float
        )
        outward_normal = np.asarray((-tangent[1], tangent[0]), dtype=float)
        threshold = _jet_cut_threshold_m(config, contact_half_beam_m=contact)
        apex = np.asarray((0.0, -config.mean_draft_m), dtype=float)
        projection_y = 0.95 * contact
        point_on_body = apex + (projection_y / tangent[0]) * tangent
        point_b = point_on_body - 2.0 * threshold * outward_normal
        self.assertLess(point_b[0], contact)

        right_y = state.right_free_y_m.copy()
        right_z = state.right_free_z_up_m.copy()
        right_y[1], right_z[1] = point_b
        overturned = replace(
            state,
            right_free_y_m=right_y,
            right_free_z_up_m=right_z,
            left_free_y_m=-right_y[::-1],
            left_free_z_up_m=right_z[::-1],
            left_free_potential_m2_s=state.right_free_potential_m2_s[::-1],
        )

        remeshed = remesh_moving_wedge_free_surface(
            config,
            motion,
            overturned,
            apply_smoothing=False,
        )

        self.assertEqual(remeshed.jet_cut_count, overturned.jet_cut_count)
        safeguarded = remesh_moving_wedge_free_surface(
            replace(config, jet_cut_ordering_safeguard_enabled=True),
            motion,
            overturned,
            apply_smoothing=False,
        )
        self.assertEqual(safeguarded.jet_cut_count, overturned.jet_cut_count + 2)

    def test_thin_jet_cut_uses_outermost_node_inside_distance_threshold(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "mean_draft_m": 0.08,
                "element_interpolation": "linear_node",
                "pressure_interpolation": "match_potential",
                "initializer": "wagner",
                "jet_cut_enabled": True,
                "jet_cut_distance_fraction": 0.5,
                "jet_cut_search_node_count": 4,
                "free_surface_uniform_near_body_panel_count": 4,
                "enforce_lateral_symmetry": True,
                "use_symmetry_half_domain": True,
            }
        )
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)
        contact = float(state.right_free_y_m[0])
        threshold = _jet_cut_threshold_m(config, contact_half_beam_m=contact)
        tangent = np.asarray(
            (np.cos(config.deadrise_rad), np.sin(config.deadrise_rad)), dtype=float
        )
        outward_normal = np.asarray((-tangent[1], tangent[0]), dtype=float)
        apex = np.asarray((0.0, -config.mean_draft_m), dtype=float)

        def body_offset_point(projection_y: float, signed_distance: float) -> np.ndarray:
            body_point = apex + (projection_y / tangent[0]) * tangent
            return body_point + signed_distance * outward_normal

        right_y = state.right_free_y_m.copy()
        right_z = state.right_free_z_up_m.copy()
        first_b = body_offset_point(0.995 * contact, -0.5 * threshold)
        outermost_b = body_offset_point(0.98 * contact, -0.75 * threshold)
        outside_c = body_offset_point(0.95 * contact, -2.0 * threshold)
        right_y[1:4] = (first_b[0], outermost_b[0], outside_c[0])
        right_z[1:4] = (first_b[1], outermost_b[1], outside_c[1])
        right_phi = np.arange(len(right_y), dtype=float)
        modified = replace(
            state,
            right_free_y_m=right_y,
            right_free_z_up_m=right_z,
            left_free_y_m=-right_y[::-1],
            left_free_z_up_m=right_z[::-1],
            right_free_potential_m2_s=right_phi,
            left_free_potential_m2_s=right_phi[::-1],
        )

        remeshed = remesh_moving_wedge_free_surface(
            config,
            motion,
            modified,
            apply_smoothing=False,
        )

        self.assertEqual(remeshed.jet_cut_count, modified.jet_cut_count + 2)
        self.assertAlmostEqual(remeshed.right_free_y_m[0], 0.98 * contact)
        self.assertAlmostEqual(remeshed.right_free_potential_m2_s[0], right_phi[2])

    def test_steady_planing_entry_builds_traceable_ground_plane_age_states(self) -> None:
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.07,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.2,
            water_depth_m=0.9,
            body_panels_per_side=5,
            free_surface_panels_per_side=6,
            side_wall_panels=3,
            bottom_panels=8,
            gauss_order=6,
            damping_beach_length_m=0.4,
        )
        result = run_steady_planing_wedge_entry(
            config,
            speed_mps=2.0,
            trim_rad=np.radians(4.0),
            wetted_length_m=0.5,
            time_step_s=0.025,
            initial_draft_m=0.01,
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.81,
        )
        self.assertEqual(len(result.states), len(result.time_s))
        np.testing.assert_allclose(result.x_from_leading_edge_m, 2.0 * result.time_s)
        self.assertTrue(np.all(np.diff(result.draft_m) > 0.0))
        self.assertTrue(np.isfinite(result.vertical_force_per_length_n_m).all())
        self.assertLess(result.max_potential_bvp_relative_residual, 1e-10)
        self.assertLess(result.max_pressure_bvp_relative_residual, 1e-10)
        self.assertLess(result.max_contact_constraint_abs_m, 1e-12)
        self.assertIn("wagner_initializer_pending", result.status)
        self.assertGreaterEqual(result.final_jet_cut_count, 0)
        self.assertGreaterEqual(result.separated_state_count, 0)
        self.assertGreaterEqual(result.separation_event_count, 0)
        if result.first_separation_x_from_leading_m is not None:
            self.assertGreaterEqual(result.first_separation_x_from_leading_m, 0.0)

    def test_artificial_surface_separation_is_localized_inside_the_time_step(self) -> None:
        beta = np.radians(20.0)
        config = MovingWedgeConfig(
            deadrise_rad=beta,
            mean_draft_m=0.1,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            element_interpolation="linear_node",
            pressure_interpolation="match_potential",
            initializer="wagner",
            enforce_lateral_symmetry=True,
            use_symmetry_half_domain=True,
            knuckle_separation_model="artificial_surface",
            jet_cut_enabled=True,
        )
        initial_contact = 0.159
        initial_draft = initial_contact * np.tan(beta) * 2.0 / np.pi
        motion = LinearDraftEntryMotion(
            reference_draft_m=0.1,
            initial_draft_m=initial_draft,
            draft_rate_mps=0.5,
        )
        state = initialize_moving_wedge_state(config, motion)
        step = advance_moving_wedge_rk4(
            config,
            motion,
            state,
            time_step_s=0.05,
            gravity_m_s2=9.81,
        )

        self.assertAlmostEqual(state.right_free_y_m[0], initial_contact, places=13)
        self.assertIsNotNone(step.separation_event_time_s)
        event_time = float(step.separation_event_time_s)
        self.assertGreater(event_time, 0.0)
        self.assertLess(event_time, 0.05)
        self.assertGreater(step.state.right_free_y_m[0], config.chine_half_beam_m)
        self.assertAlmostEqual(step.state.time_s, 0.05, places=13)

    def test_jet_cut_event_geometry_detects_projection_beyond_chine(self) -> None:
        beta = np.radians(20.0)
        config = MovingWedgeConfig(
            deadrise_rad=beta,
            mean_draft_m=0.1,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            element_interpolation="linear_node",
            initializer="wagner",
            enforce_lateral_symmetry=True,
            use_symmetry_half_domain=True,
            knuckle_separation_model="artificial_surface",
            jet_cut_enabled=True,
        )
        initial_contact = 0.15
        initial_draft = initial_contact * np.tan(beta) * 2.0 / np.pi
        motion = LinearDraftEntryMotion(
            reference_draft_m=0.1,
            initial_draft_m=initial_draft,
            draft_rate_mps=0.2,
        )
        state = initialize_moving_wedge_state(config, motion)
        tangent = np.asarray((np.cos(beta), np.sin(beta)))
        normal = np.asarray((-np.sin(beta), np.cos(beta)))
        apex_z = -config.mean_draft_m + motion.displacement_m(state.time_s)
        point_on_body = np.asarray((0.17, apex_z)) + 0.17 * np.tan(beta) * np.asarray((0.0, 1.0))
        threshold = (
            config.jet_cut_distance_fraction
            * config.chine_half_beam_m
            / (config.body_panels_per_side * np.cos(beta))
        )
        point_b = point_on_body + 0.5 * threshold * normal
        right_y = state.right_free_y_m.copy()
        right_z = state.right_free_z_up_m.copy()
        right_y[1], right_z[1] = point_b
        distorted = type(state)(
            right_free_y_m=right_y,
            right_free_z_up_m=right_z,
            left_free_y_m=-right_y[::-1],
            left_free_z_up_m=right_z[::-1],
            right_free_potential_m2_s=state.right_free_potential_m2_s,
            left_free_potential_m2_s=state.right_free_potential_m2_s[::-1],
            time_s=state.time_s,
        )

        margin, projection_y = _right_jet_cut_event_geometry(config, motion, distorted)

        self.assertLess(margin, 0.0)
        self.assertGreater(projection_y, config.chine_half_beam_m)

    def test_thin_jet_cut_is_localized_at_prescribed_distance_inside_step(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "element_interpolation": "linear_node",
                "initializer": "wagner",
                "enforce_lateral_symmetry": True,
                "use_symmetry_half_domain": True,
                "chine_separation_enabled": False,
                "jet_cut_enabled": True,
                "jet_cut_distance_fraction": 0.25,
            }
        )
        motion = ConstantVerticalMotion()
        state = initialize_moving_wedge_state(config, motion)
        tangent = np.asarray(
            (np.cos(config.deadrise_rad), np.sin(config.deadrise_rad)), dtype=float
        )
        outward_normal = np.asarray((-tangent[1], tangent[0]), dtype=float)
        apex = np.asarray((0.0, -config.mean_draft_m), dtype=float)
        contact = float(state.right_free_y_m[0])
        threshold = _jet_cut_threshold_m(config, contact_half_beam_m=contact)
        projection_y = 1.05 * contact
        body_point = apex + (projection_y / tangent[0]) * tangent
        initial_signed_distance = -2.0 * threshold
        right_y = state.right_free_y_m.copy()
        right_z = state.right_free_z_up_m.copy()
        right_y[1], right_z[1] = body_point + initial_signed_distance * outward_normal
        distorted = replace(
            state,
            right_free_y_m=right_y,
            right_free_z_up_m=right_z,
            left_free_y_m=-right_y[::-1],
            left_free_z_up_m=right_z[::-1],
            left_free_potential_m2_s=state.right_free_potential_m2_s[::-1],
        )
        outer_dt = 0.04

        def synthetic_single_step(
            config,
            motion,
            stage_state,
            *,
            time_step_s,
            gravity_m_s2=9.80665,
            remesh_enabled=True,
            incident_wave=None,
        ):
            end_time = float(stage_state.time_s) + float(time_step_s)
            if stage_state.jet_cut_count > distorted.jet_cut_count:
                advanced = replace(stage_state, time_s=end_time)
            else:
                fraction = (end_time - distorted.time_s) / outer_dt
                signed_distance = initial_signed_distance + 4.0 * threshold * fraction
                synthetic_y = stage_state.right_free_y_m.copy()
                synthetic_z = stage_state.right_free_z_up_m.copy()
                synthetic_y[1], synthetic_z[1] = (
                    body_point + signed_distance * outward_normal
                )
                advanced = replace(
                    stage_state,
                    right_free_y_m=synthetic_y,
                    right_free_z_up_m=synthetic_z,
                    left_free_y_m=-synthetic_y[::-1],
                    left_free_z_up_m=synthetic_z[::-1],
                    time_s=end_time,
                )
            return moving_wedge_module.MovingWedgeStepResult(
                state=advanced,
                max_potential_relative_residual=0.0,
                max_potential_condition_number=1.0,
            )

        with patch.object(
            moving_wedge_module,
            "_advance_moving_wedge_rk4_single_step",
            side_effect=synthetic_single_step,
        ):
            step = advance_moving_wedge_rk4(
                config,
                motion,
                distorted,
                time_step_s=outer_dt,
            )

        self.assertIsNone(step.separation_event_time_s)
        self.assertIsNotNone(step.jet_cut_event_time_s)
        self.assertAlmostEqual(
            float(step.jet_cut_event_time_s),
            distorted.time_s + 0.25 * outer_dt,
            delta=outer_dt / 128.0,
        )
        self.assertEqual(step.state.jet_cut_count, distorted.jet_cut_count + 2)
        self.assertIsNotNone(step.state.minimum_jet_normal_distance_ratio)
        self.assertLessEqual(step.state.minimum_jet_normal_distance_ratio, 1.01)
        self.assertAlmostEqual(step.state.time_s, distorted.time_s + outer_dt)

    def test_fixed_jet_cut_threshold_is_independent_of_body_panel_count(self) -> None:
        threshold = 0.0025
        coarse = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "body_panels_per_side": 8,
                "jet_cut_threshold_m": threshold,
            }
        )
        fine = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "body_panels_per_side": 20,
                "jet_cut_threshold_m": threshold,
            }
        )

        self.assertEqual(_jet_cut_threshold_m(coarse), threshold)
        self.assertEqual(_jet_cut_threshold_m(fine), threshold)

    def test_default_jet_cut_threshold_uses_current_wetted_body_panel(self) -> None:
        config = MovingWedgeConfig(
            **{
                **_config().__dict__,
                "body_panels_per_side": 8,
                "jet_cut_threshold_m": None,
                "jet_cut_distance_fraction": 0.25,
            }
        )
        contact = 0.2
        expected = (
            config.jet_cut_distance_fraction
            * contact
            / (config.body_panels_per_side * np.cos(config.deadrise_rad))
        )

        self.assertAlmostEqual(
            _jet_cut_threshold_m(config, contact_half_beam_m=contact),
            expected,
        )

    def test_steady_reference_draft_is_continuous_across_step_count_boundary(self) -> None:
        trim = np.radians(4.0)
        speed = 2.0
        time_step = 0.025
        initial_draft = 0.01
        boundary_duration = 5.0 * time_step
        boundary_length = initial_draft / np.tan(trim) + speed * boundary_duration
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.02,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.2,
            water_depth_m=0.9,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.4,
        )
        epsilon = 1e-6
        results = [
            run_steady_planing_wedge_entry(
                config,
                speed_mps=speed,
                trim_rad=trim,
                wetted_length_m=boundary_length + sign * epsilon,
                time_step_s=time_step,
                initial_draft_m=initial_draft,
                rho_water_kg_m3=1000.0,
                gravity_m_s2=9.81,
            )
            for sign in (-1.0, 1.0)
        ]

        self.assertNotEqual(len(results[0].time_s), len(results[1].time_s))
        expected_change = 2.0 * epsilon * np.tan(trim)
        self.assertAlmostEqual(
            results[1].reference_draft_m - results[0].reference_draft_m,
            expected_change,
            delta=1e-13,
        )


if __name__ == "__main__":
    unittest.main()
