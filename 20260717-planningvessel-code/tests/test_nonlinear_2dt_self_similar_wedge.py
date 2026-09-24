from __future__ import annotations

import csv
import json
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    SELF_SIMILAR_WEDGE_STATUS,
    SelfSimilarWedgeConfig,
    _double_ended_panel_fractions,
    _geometry_maintenance_adjustment,
    _linear_residual_square_integral,
    _outer_panel_fractions,
    _resample_coupled_outer_nodes,
    _connected_self_similar_boundary_velocity,
    _continuous_normal_shape_velocity,
    _build_coupled_solution_with_compatible_root,
    _coupled_jet_interface_resolution_ratio,
    _coupled_root_predictor_seed,
    _coupled_outer_pseudo_velocity,
    _maximum_coupled_outer_turn_deg,
    _paired_shallow_jet_bie_discretization,
    _reconstruct_coupled_root_nodes,
    _regrid_coupled_outer_nodes,
    _smooth_oscillatory_coupled_outer_nodes,
    _panel_length_pseudo_time_scale,
    _quadratic_peak_location_and_value,
    _wedge_pressure_vertical_force_coefficient,
    _trim_shallow_angle_coupled_root_panels,
    advance_coupled_self_similar_wedge_pseudo_time_rk2,
    advance_self_similar_wedge_pseudo_time_rk2,
    build_iafrati_dipole_initial_free_surface,
    build_residual_curvature_monitor_fractions,
    build_self_similar_free_surface,
    build_self_similar_wedge_boundary,
    derive_shallow_water_jet_root_state,
    derive_shallow_water_jet_root_state_from_coupled,
    evaluate_self_similar_wedge_reference,
    evaluate_self_similar_wedge_scalar_reference,
    iterate_shallow_jet_root_coupling,
    march_iafrati_shallow_water_jet,
    march_shallow_water_jet_from_outer_solution,
    solve_coupled_self_similar_wedge_pseudo_time,
    solve_self_similar_wedge,
    solve_self_similar_wedge_bvp,
    solve_iafrati_dipole_preliminary_iterations,
    solve_self_similar_wedge_pseudo_time,
    solve_self_similar_wedge_with_shallow_jet,
    rebuild_shallow_jet_from_coupled_root,
    truncate_self_similar_wedge_to_shallow_jet,
)


class SelfSimilarWedgeTests(unittest.TestCase):
    def test_quadratic_peak_interpolates_nonuniform_samples(self) -> None:
        coordinate = np.asarray([0.0, 1.0, 2.5])
        values = 4.0 - np.square(coordinate - 1.2)
        peak_x, peak_y = _quadratic_peak_location_and_value(coordinate, values)
        self.assertAlmostEqual(peak_x, 1.2, places=12)
        self.assertAlmostEqual(peak_y, 4.0, places=12)

    def test_quadratic_peak_preserves_endpoint_maximum(self) -> None:
        peak_x, peak_y = _quadratic_peak_location_and_value(
            np.asarray([0.0, 1.0, 2.0]), np.asarray([3.0, 2.0, 1.0])
        )
        self.assertEqual(peak_x, 0.0)
        self.assertEqual(peak_y, 3.0)

    def test_wedge_pressure_force_uses_deadrise_projection(self) -> None:
        force = _wedge_pressure_vertical_force_coefficient(
            np.asarray([-1.0, 0.0, 1.0]),
            np.asarray([2.0, 2.0, 2.0]),
            45.0,
        )
        self.assertAlmostEqual(force, 4.0, places=12)

    @staticmethod
    def _small_config(**overrides: object) -> SelfSimilarWedgeConfig:
        values: dict[str, object] = {
            "deadrise_deg": 20.0,
            "far_radius": 14.0,
            "free_surface_panels": 16,
            "body_panels": 10,
            "far_field_panels": 10,
            "symmetry_panels": 6,
            "free_surface_control_points": 5,
            "gauss_order": 8,
            "max_nfev": 3,
        }
        values.update(overrides)
        return SelfSimilarWedgeConfig(**values)

    def test_config_rejects_under_resolved_free_surface(self) -> None:
        with self.assertRaisesRegex(ValueError, "free_surface_panels"):
            SelfSimilarWedgeConfig(free_surface_panels=8)

    def test_config_exposes_auditable_shallow_jet_point_limit(self) -> None:
        self.assertEqual(SelfSimilarWedgeConfig().shallow_jet_maximum_points, 20000)
        with self.assertRaisesRegex(ValueError, "shallow_jet_maximum_points"):
            SelfSimilarWedgeConfig(shallow_jet_maximum_points=99)

    def test_geometry_maintenance_separates_tangential_redistribution(self) -> None:
        old = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        raw = old.copy()
        tangentially_redistributed = np.asarray(
            [[0.0, 0.0], [0.7, 0.0], [2.0, 0.0]]
        )
        tangential = _geometry_maintenance_adjustment(
            old,
            raw,
            tangentially_redistributed,
            0.1,
        )
        self.assertAlmostEqual(tangential.raw_normal_velocity_integral, 0.0)
        self.assertAlmostEqual(tangential.normal_velocity_integral, 0.0)
        self.assertAlmostEqual(tangential.net_normal_velocity_integral, 0.0)

        normally_shifted = old + np.asarray([0.0, 0.1])
        normal = _geometry_maintenance_adjustment(
            old,
            raw,
            normally_shifted,
            0.1,
        )
        self.assertAlmostEqual(normal.raw_normal_velocity_integral, 0.0)
        self.assertAlmostEqual(normal.normal_velocity_integral, 2.0)
        self.assertAlmostEqual(normal.tangential_velocity_integral, 0.0)
        self.assertAlmostEqual(normal.net_normal_velocity_integral, 2.0)
        self.assertAlmostEqual(normal.maximum_normal_displacement_ratio, 0.1)

        raw_normal = old + np.asarray([0.0, 0.2])
        cancelled = _geometry_maintenance_adjustment(
            old,
            raw_normal,
            old,
            0.1,
        )
        self.assertAlmostEqual(cancelled.raw_normal_velocity_integral, 8.0)
        self.assertAlmostEqual(cancelled.normal_velocity_integral, 8.0)
        self.assertAlmostEqual(cancelled.net_normal_velocity_integral, 0.0)
        self.assertAlmostEqual(cancelled.normal_velocity_correlation, -1.0)
        self.assertAlmostEqual(cancelled.normal_cancellation_fraction, 1.0)

    def test_double_ended_panel_fractions_refine_both_endpoints_smoothly(self) -> None:
        fractions = _double_ended_panel_fractions(80, 0.08, 0.25, 4.0)
        spacing = np.diff(fractions)

        self.assertEqual(fractions.shape, (81,))
        self.assertAlmostEqual(float(fractions[0]), 0.0)
        self.assertAlmostEqual(float(fractions[-1]), 1.0)
        self.assertTrue(np.all(spacing > 0.0))
        self.assertLess(spacing[0], np.median(spacing))
        self.assertLess(spacing[-1], np.median(spacing))
        self.assertLess(float(np.max(spacing[1:] / spacing[:-1])), 1.25)

    def test_config_rejects_invalid_double_ended_spacing(self) -> None:
        with self.assertRaisesRegex(ValueError, "root_spacing_ratio"):
            SelfSimilarWedgeConfig(coupled_outer_root_spacing_ratio=0.0)

    def test_config_rejects_unknown_linear_corner_treatment(self) -> None:
        with self.assertRaisesRegex(ValueError, "linear_corner_treatment"):
            self._small_config(coupled_linear_corner_treatment="unknown")
        with self.assertRaisesRegex(ValueError, "far_corner_treatment"):
            self._small_config(coupled_linear_far_corner_treatment="unknown")

    def test_config_rejects_unknown_or_incompatible_cusp_velocity_recovery(self) -> None:
        with self.assertRaisesRegex(ValueError, "cusp_velocity_recovery"):
            self._small_config(coupled_linear_cusp_velocity_recovery="unknown")
        with self.assertRaisesRegex(ValueError, "requires displaced_double_node"):
            self._small_config(coupled_linear_cusp_velocity_recovery="split_average")

    def test_config_requires_linear_elements_for_continuous_normal_update(self) -> None:
        with self.assertRaisesRegex(ValueError, "require linear_node"):
            self._small_config(coupled_free_surface_update="continuous_normal")
        config = self._small_config(
            coupled_element_interpolation="linear_node",
            coupled_free_surface_update="continuous_normal",
        )
        self.assertEqual(config.coupled_free_surface_update, "continuous_normal")

    def test_panel_length_pseudo_time_scale_is_positive_local_and_capped(self) -> None:
        scale = _panel_length_pseudo_time_scale(
            np.asarray([1.0, 2.0, 8.0]),
            4.0,
        )

        np.testing.assert_allclose(scale, [1.0, 1.0, 2.0, 4.0])
        with self.assertRaisesRegex(ValueError, "at least one"):
            _panel_length_pseudo_time_scale(np.asarray([1.0, 2.0]), 0.5)

    def test_config_rejects_invalid_pseudo_time_preconditioner(self) -> None:
        with self.assertRaisesRegex(ValueError, "preconditioner"):
            self._small_config(coupled_pseudo_time_preconditioner="unknown")
        with self.assertRaisesRegex(ValueError, "max_ratio"):
            self._small_config(coupled_pseudo_time_preconditioner_max_ratio=0.5)

    def test_continuous_normal_shape_velocity_recovers_linear_straight_field(self) -> None:
        velocity = _continuous_normal_shape_velocity(
            np.asarray([1.0, 1.0]),
            np.asarray([[1.0, 0.0], [1.0, 0.0]]),
            np.asarray([[0.0, 1.0], [0.0, 1.0]]),
            np.asarray([[1.0, 2.0], [2.0, 3.0]]),
        )
        np.testing.assert_allclose(
            velocity,
            [[0.0, 1.0], [0.0, 2.0], [0.0, 3.0]],
            atol=1.0e-13,
        )

    def test_config_requires_and_preserves_frozen_monitor_fractions(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires.*fractions"):
            self._small_config(coupled_outer_grid_mode="frozen_monitor")

        fractions = tuple(np.linspace(0.0, 1.0, 17))
        config = self._small_config(
            coupled_outer_grid_mode="frozen_monitor",
            coupled_outer_monitor_fractions=fractions,
        )
        np.testing.assert_allclose(_outer_panel_fractions(config), fractions)

    def test_residual_curvature_monitor_is_bounded_and_reference_isolated(self) -> None:
        count = 20
        source_fraction = np.linspace(0.0, 1.0, count + 1)
        residual = 0.02 + np.exp(
            -np.square((np.arange(count) + 0.5) / count - 0.5) / 0.002
        )
        coupled = SimpleNamespace(
            config=SelfSimilarWedgeConfig(
                free_surface_panels=count,
                coupled_outer_grid_mode="double_ended",
                coupled_outer_root_spacing_ratio=0.25,
                coupled_outer_far_spacing_ratio=0.5,
            ),
            outer_free_surface=SimpleNamespace(
                node_xi=4.0 + 16.0 * source_fraction,
                node_eta=0.2 * np.square(1.0 - source_fraction),
            ),
            outer_kinematic_residual=residual,
            outer_kinematic_residual_endpoint=None,
        )
        base = _double_ended_panel_fractions(count, 0.25, 0.5, 4.0)

        monitored = build_residual_curvature_monitor_fractions(
            coupled,
            count,
            residual_weight=2.0,
            curvature_weight=0.0,
            growth_weight=0.0,
            smoothing_passes=1,
            maximum_node_shift_panels=2.0,
        )

        self.assertEqual(monitored.shape, (count + 1,))
        self.assertTrue(np.all(np.diff(monitored) > 0.0))
        self.assertAlmostEqual(float(monitored[0]), 0.0)
        self.assertAlmostEqual(float(monitored[-1]), 1.0)
        self.assertLess(np.min(np.diff(monitored)[8:12]), np.min(np.diff(base)[8:12]))
        self.assertLessEqual(
            float(np.max(np.abs(monitored - base))),
            2.0 / count + 1.0e-12,
        )

    def test_linear_residual_square_integral_is_exact_for_linear_panels(self) -> None:
        residual = np.asarray([[1.0, 2.0], [-1.0, 1.0]])
        length = np.asarray([3.0, 6.0])

        actual = _linear_residual_square_integral(residual, length)

        expected = 3.0 * (1.0 + 2.0 + 4.0) / 3.0 + 6.0 * (
            1.0 - 1.0 + 1.0
        ) / 3.0
        self.assertAlmostEqual(actual, expected)

    def test_coupled_resampling_preserves_declared_double_ended_grid(self) -> None:
        config = self._small_config(
            coupled_outer_grid_mode="double_ended",
            coupled_outer_root_spacing_ratio=0.08,
            coupled_outer_far_spacing_ratio=0.25,
            coupled_outer_endpoint_decay=4.0,
        )
        fractions = np.linspace(0.0, 1.0, config.free_surface_panels + 1)
        nodes = np.column_stack(
            (
                4.0 + 10.0 * fractions,
                0.2 * np.square(1.0 - fractions),
            )
        )
        nodes[-1] *= config.far_radius / np.linalg.norm(nodes[-1])

        resampled = _resample_coupled_outer_nodes(config, nodes)
        spacing = np.linalg.norm(np.diff(resampled, axis=0), axis=1)

        self.assertLess(spacing[0], np.median(spacing))
        self.assertLess(spacing[-1], np.median(spacing))
        self.assertLess(spacing[-1] / spacing[0], 4.0)

    def test_coupled_resampling_accepts_finite_angle_root_past_ninety_degrees(
        self,
    ) -> None:
        config = SelfSimilarWedgeConfig(
            deadrise_deg=30.0,
            far_radius=20.0,
            free_surface_panels=80,
            body_panels=48,
            far_field_panels=24,
            symmetry_panels=16,
            coupled_outer_grid_mode="geometric_root",
            coupled_outer_root_spacing_ratio=0.08,
        )
        root_nodes = np.asarray(
            [
                [2.242464434020834, 0.27996859545691777],
                [2.251348918382728, 0.26460071203735275],
                [2.2606443911354325, 0.24724321182807302],
                [2.2756868291801466, 0.23405954263154896],
                [2.292508842150248, 0.2204980491733735],
                [2.3122523072996443, 0.21066869224705257],
            ]
        )
        far_tail = np.linspace(root_nodes[-1], np.asarray([20.0, 0.0]), 76)[1:]
        nodes = np.vstack((root_nodes, far_tail))
        nodes[-1] *= config.far_radius / np.linalg.norm(nodes[-1])
        beta = np.deg2rad(config.deadrise_deg)
        body_tangent = np.asarray([np.cos(beta), np.sin(beta)])

        resampled = _resample_coupled_outer_nodes(config, nodes)

        self.assertGreater(float(np.dot(nodes[1] - nodes[0], body_tangent)), 0.0)
        self.assertLess(
            float(np.dot(resampled[1] - resampled[0], body_tangent)), 0.0
        )
        np.testing.assert_allclose(resampled[[0, -1]], nodes[[0, -1]], atol=1.0e-14)

    def test_config_rejects_inverted_jet_interface_resolution_hysteresis(self) -> None:
        with self.assertRaisesRegex(ValueError, "target.*at least"):
            SelfSimilarWedgeConfig(
                jet_interface_min_thickness_panel_ratio=1.0,
                jet_interface_target_thickness_panel_ratio=0.5,
            )

    def test_root_coupling_solves_measured_equals_supplied_velocity(self) -> None:
        def coupled(value: float) -> SimpleNamespace:
            return SimpleNamespace(
                jet_interface=SimpleNamespace(
                    root_state=SimpleNamespace(s_lambda=float(value))
                )
            )

        def measured(state: SimpleNamespace) -> SimpleNamespace:
            supplied = state.jet_interface.root_state.s_lambda
            return SimpleNamespace(s_lambda=0.5 * supplied + 2.0)

        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
                "derive_shallow_water_jet_root_state_from_coupled",
                side_effect=measured,
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
                "rebuild_shallow_jet_from_coupled_root",
                side_effect=lambda _state, s_lambda_override: s_lambda_override,
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
                "solve_self_similar_wedge_with_shallow_jet",
                side_effect=coupled,
            ),
        ):
            result = iterate_shallow_jet_root_coupling(
                coupled(2.0),
                maximum_iterations=8,
                relative_tolerance=1.0e-8,
                relaxation=0.5,
            )

        self.assertTrue(result.converged)
        self.assertAlmostEqual(result.s_lambda_history[-1], 4.0, places=8)
        self.assertAlmostEqual(
            result.measured_s_lambda_history[-1],
            result.s_lambda_history[-1],
            places=8,
        )
        self.assertLessEqual(result.relative_mismatch_history[-1], 1.0e-8)
        self.assertEqual(result.termination_reason, "ROOT_CONSISTENT")

    def test_root_coupling_stops_at_unbracketed_physical_boundary(self) -> None:
        def coupled(value: float) -> SimpleNamespace:
            return SimpleNamespace(
                jet_interface=SimpleNamespace(
                    root_state=SimpleNamespace(s_lambda=float(value))
                )
            )

        def rebuild(_state: SimpleNamespace, s_lambda_override: float) -> float:
            if s_lambda_override > 3.0:
                raise ValueError(
                    "The shallow-water root state has no physical first-step solution"
                )
            return float(s_lambda_override)

        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
                "derive_shallow_water_jet_root_state_from_coupled",
                side_effect=lambda state: SimpleNamespace(
                    s_lambda=state.jet_interface.root_state.s_lambda + 1.0
                ),
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
                "rebuild_shallow_jet_from_coupled_root",
                side_effect=rebuild,
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
                "solve_self_similar_wedge_with_shallow_jet",
                side_effect=coupled,
            ),
        ):
            result = iterate_shallow_jet_root_coupling(
                coupled(2.0),
                maximum_iterations=8,
                relative_tolerance=1.0e-8,
                relaxation=1.0,
            )

        self.assertFalse(result.converged)
        self.assertEqual(
            result.termination_reason,
            "NO_BRACKET_IN_PHYSICAL_DOMAIN",
        )
        self.assertLessEqual(len(result.s_lambda_history), 3)

    def test_source_root_mode_disables_augmented_bie_predictor_seed(self) -> None:
        coupled = SimpleNamespace(
            config=SimpleNamespace(coupled_root_predictor_relaxation=0.1),
            jet_interface=SimpleNamespace(
                root_state=SimpleNamespace(s_lambda=1.0)
            ),
        )
        measured = SimpleNamespace(s_lambda=3.0)

        self.assertIsNone(
            _coupled_root_predictor_seed(
                coupled,
                measured,
                root_inner_iterations=0,
            )
        )
        self.assertAlmostEqual(
            _coupled_root_predictor_seed(
                coupled,
                measured,
                root_inner_iterations=8,
            ),
            1.2,
        )

    def test_config_rejects_simultaneous_root_reconstruction_and_smoothing(self) -> None:
        with self.assertRaisesRegex(ValueError, "alternative diagnostics"):
            SelfSimilarWedgeConfig(
                coupled_root_reconstruction_enabled=True,
                coupled_smoothing_enabled=True,
            )

    def test_root_reconstruction_refines_first_arc_and_preserves_anchor_tail(self) -> None:
        config = self._small_config(
            coupled_root_reconstruction_enabled=True,
            coupled_root_reconstruction_panels=8,
            coupled_root_reconstruction_added_panels=12,
            jet_interface_target_thickness_panel_ratio=1.0,
        )
        beta = np.deg2rad(config.deadrise_deg)
        tangent = np.asarray([np.cos(beta), np.sin(beta)])
        fluid_normal = np.asarray([np.sin(beta), -np.cos(beta)])
        apex = np.asarray([0.0, -1.0])
        body_arc = np.linspace(3.0, 15.0, config.free_surface_panels + 1)
        thickness = 0.01 + 0.08 * (body_arc - body_arc[0])
        nodes = (
            apex[None, :]
            + body_arc[:, None] * tangent[None, :]
            + thickness[:, None] * fluid_normal[None, :]
        )
        nodes[-1] *= config.far_radius / np.linalg.norm(nodes[-1])
        initial_ratio = _coupled_jet_interface_resolution_ratio(config, nodes)

        reconstructed = _reconstruct_coupled_root_nodes(config, nodes)

        self.assertLess(initial_ratio, 0.5)
        np.testing.assert_allclose(reconstructed[0], nodes[0], atol=0.0)
        self.assertEqual(len(reconstructed), len(nodes) + 12)
        np.testing.assert_allclose(reconstructed[20:], nodes[8:], atol=0.0)
        self.assertGreaterEqual(
            _coupled_jet_interface_resolution_ratio(config, reconstructed),
            config.jet_interface_target_thickness_panel_ratio - 1.0e-10,
        )
        local_panel = np.linalg.norm(np.diff(reconstructed[:21], axis=0), axis=1)
        self.assertTrue(np.all(np.diff(local_panel) > 0.0))

    def test_gcv_smoothing_removes_panel_scale_turning_and_fixes_endpoints(self) -> None:
        config = self._small_config(
            coupled_smoothing_enabled=True,
            coupled_smoothing_turn_threshold_deg=10.0,
            coupled_smoothing_max_local_displacement=1.0,
        )
        xi = np.linspace(3.0, 8.0, config.free_surface_panels + 1)
        eta = 0.4 * np.exp(-0.25 * (xi - xi[0]))
        eta[1:6] += np.asarray([0.0, -0.12, 0.10, -0.08, 0.05])
        nodes = np.column_stack((xi, eta))
        panel_length = np.linalg.norm(np.diff(nodes, axis=0), axis=1)
        local_length = np.concatenate(
            (
                [panel_length[0]],
                np.minimum(panel_length[:-1], panel_length[1:]),
                [panel_length[-1]],
            )
        )

        smoothed = _smooth_oscillatory_coupled_outer_nodes(config, nodes)

        np.testing.assert_allclose(smoothed[[0, -1]], nodes[[0, -1]], atol=0.0)
        self.assertLess(
            _maximum_coupled_outer_turn_deg(smoothed),
            _maximum_coupled_outer_turn_deg(nodes),
        )
        self.assertLessEqual(
            float(np.max(np.linalg.norm(smoothed - nodes, axis=1) / local_length)),
            config.coupled_smoothing_max_local_displacement + 1.0e-12,
        )

    def test_underresolved_coupled_root_is_relocated_along_outer_surface(self) -> None:
        config = self._small_config(
            jet_interface_min_thickness_panel_ratio=0.5,
            jet_interface_target_thickness_panel_ratio=1.0,
            jet_angle_threshold_deg=1.0,
        )
        beta = np.deg2rad(config.deadrise_deg)
        tangent = np.asarray([np.cos(beta), np.sin(beta)])
        fluid_normal = np.asarray([np.sin(beta), -np.cos(beta)])
        apex = np.asarray([0.0, -1.0])
        body_arc = np.linspace(3.0, 16.0, config.free_surface_panels + 1)
        thickness = np.linspace(1.0e-3, 1.5, config.free_surface_panels + 1)
        nodes = (
            apex[None, :]
            + body_arc[:, None] * tangent[None, :]
            + thickness[:, None] * fluid_normal[None, :]
        )
        nodes[-1] *= config.far_radius / np.linalg.norm(nodes[-1])
        initial_root_projection = float(np.dot(nodes[0] - apex, tangent))

        relocated = _regrid_coupled_outer_nodes(config, nodes)
        relocated_root_projection = float(np.dot(relocated[0] - apex, tangent))

        self.assertEqual(relocated.shape, nodes.shape)
        self.assertGreater(relocated_root_projection, initial_root_projection)
        self.assertGreaterEqual(
            _coupled_jet_interface_resolution_ratio(config, relocated),
            config.jet_interface_min_thickness_panel_ratio,
        )
        self.assertAlmostEqual(np.linalg.norm(relocated[-1]), config.far_radius, places=11)

    def test_finite_angle_leading_panel_is_not_transferred_by_projection_sign(
        self,
    ) -> None:
        config = self._small_config(jet_angle_threshold_deg=1.0)
        beta = np.deg2rad(config.deadrise_deg)
        tangent = np.asarray([np.cos(beta), np.sin(beta)])
        fluid_normal = np.asarray([np.sin(beta), -np.cos(beta)])
        apex = np.asarray([0.0, -1.0])
        body_arc = np.linspace(3.0, 16.0, config.free_surface_panels + 1)
        thickness = np.linspace(0.2, 1.5, config.free_surface_panels + 1)
        nodes = (
            apex[None, :]
            + body_arc[:, None] * tangent[None, :]
            + thickness[:, None] * fluid_normal[None, :]
        )
        nodes[1] = nodes[0] - 0.05 * tangent + 0.01 * fluid_normal
        nodes[-1] *= config.far_radius / np.linalg.norm(nodes[-1])

        relocated = _regrid_coupled_outer_nodes(config, nodes)

        np.testing.assert_allclose(relocated[0], nodes[0], atol=1.0e-14)
        self.assertLess(float(np.dot(relocated[1] - relocated[0], tangent)), 0.0)

    def test_shallow_angle_leading_panels_are_transferred_to_jet(self) -> None:
        config = self._small_config(jet_angle_threshold_deg=10.0)
        beta = np.deg2rad(config.deadrise_deg)
        origin = np.asarray([3.0, 0.2])
        panel_angle = beta + np.deg2rad(
            np.asarray([2.0, 5.0, 18.0, 20.0, 22.0, 24.0, 25.0, 26.0])
        )
        segment = np.column_stack((np.cos(panel_angle), np.sin(panel_angle)))
        nodes = np.vstack((origin, origin + np.cumsum(segment, axis=0)))

        trimmed = _trim_shallow_angle_coupled_root_panels(config, nodes)

        expected_fraction = 0.5 + (10.0 - 5.0) / (18.0 - 5.0)
        expected_root = nodes[1] + expected_fraction * (nodes[2] - nodes[1])
        np.testing.assert_allclose(trimmed[0], expected_root, atol=1.0e-14)
        np.testing.assert_allclose(trimmed[1:], nodes[2:], atol=0.0)

    def test_shallow_angle_matching_root_changes_continuously(self) -> None:
        config = self._small_config(jet_angle_threshold_deg=10.0)
        beta = np.deg2rad(config.deadrise_deg)
        origin = np.asarray([3.0, 0.2])

        def root_for(second_angle_deg: float) -> np.ndarray:
            panel_angle = beta + np.deg2rad(
                np.asarray([5.0, second_angle_deg, 18.0, 22.0, 24.0, 26.0, 28.0])
            )
            segment = np.column_stack((np.cos(panel_angle), np.sin(panel_angle)))
            nodes = np.vstack((origin, origin + np.cumsum(segment, axis=0)))
            return _trim_shallow_angle_coupled_root_panels(config, nodes)[0]

        root_low = root_for(9.9)
        root_high = root_for(10.1)

        self.assertLess(float(np.linalg.norm(root_high - root_low)), 0.05)

    def test_inadmissible_matching_surface_is_bisected_to_minimum_valid_root(self) -> None:
        config = self._small_config(
            free_surface_panels=12,
            coupled_matching_surface_bisection_iterations=8,
        )
        nodes = np.column_stack((np.linspace(0.0, 12.0, 13), np.zeros(13)))

        def fake_regrid(_config: object, trial: np.ndarray) -> np.ndarray:
            return np.column_stack(
                (
                    np.linspace(float(trial[0, 0]), 12.0, 13),
                    np.zeros(13),
                )
            )

        def fake_build(
            _config: object,
            trial: np.ndarray,
            _dipole: float,
            **_kwargs: object,
        ) -> SimpleNamespace:
            if float(trial[0, 0]) < 0.3:
                raise ValueError(
                    "The jet root requires thickness>0, S_lambda>0, S_tau<0 "
                    "and delta_lambda>0; invalid=S_lambda<=0."
                )
            if float(trial[0, 0]) < 0.6:
                raise ValueError(
                    "The shallow-water root state has no physical first-step solution."
                )
            return SimpleNamespace(
                root_xi=float(trial[0, 0]),
                outer_free_surface=SimpleNamespace(
                    node_xi=trial[:, 0],
                    node_eta=trial[:, 1],
                ),
            )

        diagnostics = []
        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
                "_regrid_coupled_outer_nodes",
                side_effect=fake_regrid,
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
                "_build_coupled_solution_from_outer_nodes",
                side_effect=fake_build,
            ),
        ):
            result = _build_coupled_solution_with_compatible_root(
                config,
                nodes,
                4.0,
                root_inner_iterations=0,
                s_lambda_seed=2.0,
                diagnostic_sink=diagnostics,
            )

        self.assertGreaterEqual(result.root_xi, 0.6)
        self.assertLess(result.root_xi, 0.61)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].full_panel_shifts, 0)
        self.assertGreaterEqual(diagnostics[0].fractional_panel_shift, 0.6)
        self.assertLess(diagnostics[0].fractional_panel_shift, 0.61)
        self.assertEqual(diagnostics[0].bisection_iterations, 8)
        self.assertEqual(diagnostics[0].trigger_code, 1)
        self.assertGreater(diagnostics[0].root_displacement_ratio, 0.0)

    def test_odd_shallow_water_step_count_gets_paired_terminal_substep(self) -> None:
        truncation = SimpleNamespace(
            body_node_xi=np.asarray([0.0, 1.0, 2.0, 3.0]),
            body_node_eta=np.zeros(4),
            free_node_xi=np.asarray([0.0, 1.0, 2.0, 3.0]),
            free_node_eta=np.asarray([1.0, 0.7, 0.3, 0.1]),
            root_state=SimpleNamespace(delta_lambda=0.5),
            jet=SimpleNamespace(
                s_lambda=np.asarray([2.0, 1.0, 0.6, 0.25]),
                s_tau=np.asarray([-4.0, -3.0, -2.0, -1.0]),
            ),
        )

        body, free, s_tau, panel_nodes = _paired_shallow_jet_bie_discretization(
            truncation,
            body_tangent=np.asarray([1.0, 0.0]),
            terminal_closure="continuous_tip",
        )

        self.assertEqual(len(body) - 1, 4)
        np.testing.assert_array_equal(np.diff(panel_nodes), 2)
        np.testing.assert_allclose(body[-1], [3.25, 0.0], atol=1.0e-14)
        np.testing.assert_allclose(free[-1], body[-1], atol=0.0)
        self.assertAlmostEqual(s_tau[-1], -1.0 + np.hypot(0.25, 0.1))

        fixed_body, fixed_free, _, fixed_panel_nodes = (
            _paired_shallow_jet_bie_discretization(
                truncation,
                body_tangent=np.asarray([1.0, 0.0]),
                target_panel_count=3,
            )
        )
        self.assertEqual(len(fixed_body), 7)
        np.testing.assert_array_equal(np.diff(fixed_panel_nodes), 2)
        np.testing.assert_allclose(fixed_body[[0, -1]], body[[0, -1]], atol=0.0)
        np.testing.assert_allclose(fixed_free[-1], fixed_body[-1], atol=0.0)

    def test_even_shallow_water_step_count_splits_the_terminal_closure(self) -> None:
        truncation = SimpleNamespace(
            body_node_xi=np.asarray([0.0, 1.0, 2.0]),
            body_node_eta=np.zeros(3),
            free_node_xi=np.asarray([0.0, 1.0, 2.0]),
            free_node_eta=np.asarray([1.0, 0.5, 0.1]),
            root_state=SimpleNamespace(delta_lambda=0.5),
            jet=SimpleNamespace(
                s_lambda=np.asarray([2.0, 0.8, 0.25]),
                s_tau=np.asarray([-3.0, -2.0, -1.0]),
            ),
        )

        body, free, s_tau, panel_nodes = _paired_shallow_jet_bie_discretization(
            truncation,
            body_tangent=np.asarray([1.0, 0.0]),
            terminal_closure="continuous_tip",
        )

        self.assertEqual(len(body) - 1, 4)
        np.testing.assert_array_equal(np.diff(panel_nodes), 2)
        np.testing.assert_allclose(body[-1], [2.25, 0.0], atol=1.0e-14)
        np.testing.assert_allclose(body[-2], [2.125, 0.0], atol=1.0e-14)
        np.testing.assert_allclose(free[-1], body[-1], atol=0.0)
        self.assertAlmostEqual(s_tau[-1], -1.0 + np.hypot(0.25, 0.1))

    def test_iafrati_table1_scalar_reference_is_frozen_and_post_solve_only(self) -> None:
        root = (
            Path(__file__).resolve().parents[1]
            / "benchmarks"
            / "iafrati2013_self_similar_wedge"
        )
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        with (root / "table1_pressure_peak.csv").open(
            "r", encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))

        self.assertFalse(manifest["solver_reads_this_file"])
        self.assertEqual(len(manifest["source_pdf_sha256"]), 64)
        row20 = next(row for row in rows if float(row["deadrise_deg"]) == 20.0)
        self.assertEqual(float(row20["pressure_coefficient_peak"]), 17.77)
        self.assertEqual(float(row20["peak_eta"]), 0.5087)

    def test_boundary_has_source_defined_segment_order_and_outward_normals(self) -> None:
        config = self._small_config(jet_closure="truncated_control")
        controls = np.asarray([4.1, 0.36, 0.20, 0.08, 0.0])
        free_surface = build_self_similar_free_surface(config, controls)
        boundary = build_self_similar_wedge_boundary(config, free_surface)
        labels = np.asarray(boundary.panel_labels, dtype=object)

        self.assertLess(boundary.signed_area_m2, 0.0)
        self.assertEqual(np.count_nonzero(labels == "free_surface"), 16)
        self.assertEqual(np.count_nonzero(labels == "far_field"), 10)
        self.assertEqual(np.count_nonzero(labels == "symmetry"), 6)
        self.assertEqual(np.count_nonzero(labels == "body"), 10)
        self.assertEqual(np.count_nonzero(labels == "jet_control"), 1)
        self.assertTrue(np.all(boundary.panel_normal[labels == "free_surface", 1] > 0.0))
        np.testing.assert_allclose(
            [boundary.node_y_m[-1], boundary.node_z_up_m[-1]],
            [boundary.node_y_m[0], boundary.node_z_up_m[0]],
            atol=1.0e-14,
        )

    def test_fixed_shape_augmented_bvp_closes_identity_and_flux(self) -> None:
        config = self._small_config()
        controls = np.asarray([4.1, 0.28, 0.12, 0.04])
        result = solve_self_similar_wedge_bvp(config, controls)

        self.assertEqual(result.status, SELF_SIMILAR_WEDGE_STATUS)
        self.assertLess(result.solution.relative_residual, 1.0e-11)
        self.assertLess(abs(result.flux_residual), 1.0e-10)
        self.assertTrue(np.isfinite(result.solution.condition_number))
        self.assertTrue(np.isfinite(result.body_pressure_coefficient).all())
        self.assertEqual(result.scaled_kinematic_residual.shape, (16,))
        self.assertNotIn("jet_control", result.boundary.panel_labels)

    def test_iafrati_eq51_initial_surface_matches_body_far_circle_and_dipole(self) -> None:
        config = self._small_config()
        coefficient = 4.0
        free_surface = build_iafrati_dipole_initial_free_surface(
            config,
            coefficient,
        )
        beta = np.deg2rad(config.deadrise_deg)

        np.testing.assert_allclose(
            free_surface.node_eta,
            coefficient / (3.0 * np.square(free_surface.node_xi)),
            rtol=0.0,
            atol=1.0e-13,
        )
        self.assertAlmostEqual(
            free_surface.node_eta[0],
            -1.0 + free_surface.node_xi[0] * np.tan(beta),
            places=12,
        )
        self.assertAlmostEqual(
            np.hypot(free_surface.node_xi[-1], free_surface.node_eta[-1]),
            config.far_radius,
            places=11,
        )
        tau_far = free_surface.tau_star + free_surface.arc_length[-1]
        reconstructed_far_phi = 0.5 * (config.far_radius**2 - tau_far**2)
        expected_far_phi = (
            coefficient
            * free_surface.node_eta[-1]
            / config.far_radius**2
        )
        self.assertAlmostEqual(reconstructed_far_phi, expected_far_phi, places=11)
        boundary = build_self_similar_wedge_boundary(config, free_surface)
        free_far_node = np.asarray(
            [free_surface.node_xi[-1], free_surface.node_eta[-1]]
        )
        np.testing.assert_allclose(
            [
                boundary.node_y_m[config.free_surface_panels],
                boundary.node_z_up_m[config.free_surface_panels],
            ],
            free_far_node,
            atol=1.0e-13,
        )

    def test_dipole_preliminary_iteration_is_self_consistent_without_reference(self) -> None:
        config = self._small_config(preliminary_iterations=8)
        result = solve_iafrati_dipole_preliminary_iterations(config)

        self.assertTrue(result.converged)
        self.assertGreater(result.dipole_coefficient_history[-1], 0.0)
        self.assertLess(
            result.relative_change_history[-1],
            result.relative_change_history[0],
        )
        self.assertLessEqual(
            result.relative_change_history[-1],
            config.preliminary_relative_tolerance,
        )
        self.assertLess(result.bvp.solution.relative_residual, 1.0e-11)
        self.assertNotIn("reference", result.status.lower())

    def test_pseudo_time_rk2_respects_geometry_and_quarter_panel_cfl(self) -> None:
        config = self._small_config(preliminary_iterations=8)
        preliminary = solve_iafrati_dipole_preliminary_iterations(config)
        advanced, time_step, displacement_ratio = (
            advance_self_similar_wedge_pseudo_time_rk2(
                config,
                preliminary.bvp,
            )
        )
        beta = np.deg2rad(config.deadrise_deg)

        self.assertGreater(time_step, 0.0)
        self.assertLessEqual(displacement_ratio, 0.25 + 1.0e-12)
        self.assertAlmostEqual(
            advanced.free_surface.node_eta[0],
            -1.0 + advanced.free_surface.node_xi[0] * np.tan(beta),
            places=11,
        )
        self.assertAlmostEqual(
            np.hypot(
                advanced.free_surface.node_xi[-1],
                advanced.free_surface.node_eta[-1],
            ),
            config.far_radius,
            places=11,
        )
        self.assertLess(advanced.solution.relative_residual, 1.0e-11)

    def test_pseudo_time_stops_at_source_jet_angle_interface(self) -> None:
        config = self._small_config(
            preliminary_iterations=8,
            pseudo_max_iterations=10,
        )
        result = solve_self_similar_wedge_pseudo_time(config)

        self.assertEqual(result.termination_reason, "JET_MODEL_REQUIRED")
        self.assertFalse(result.converged)
        self.assertIsNone(result.failure_message)
        self.assertGreater(len(result.time_step_history), 0)
        self.assertTrue(
            np.all(result.maximum_displacement_ratio_history <= 0.25 + 1.0e-12)
        )
        self.assertLessEqual(
            result.root_angle_deg_history[-1],
            config.jet_angle_threshold_deg,
        )
        self.assertGreater(
            result.kinematic_rms_history[-1],
            config.pseudo_kinematic_tolerance,
        )

    def test_source_angle_truncation_builds_positive_root_and_tip_geometry(self) -> None:
        config = SelfSimilarWedgeConfig(
            deadrise_deg=20.0,
            far_radius=20.0,
            free_surface_panels=80,
            body_panels=48,
            far_field_panels=40,
            symmetry_panels=24,
            free_surface_control_points=12,
            gauss_order=12,
            preliminary_iterations=8,
            pseudo_max_iterations=20,
        )
        pseudo = solve_self_similar_wedge_pseudo_time(config)
        truncation = truncate_self_similar_wedge_to_shallow_jet(config, pseudo)
        beta = np.deg2rad(config.deadrise_deg)

        self.assertGreaterEqual(truncation.original_cut_node_index, 1)
        self.assertGreater(truncation.cut_angle_deg, config.jet_angle_threshold_deg)
        self.assertGreater(truncation.root_state.thickness, 0.0)
        self.assertGreater(truncation.root_state.s_lambda, 0.0)
        np.testing.assert_allclose(
            truncation.root_state.lambda_tangent,
            [np.cos(beta), np.sin(beta)],
            atol=1.0e-13,
        )
        self.assertTrue(truncation.jet.reached_tip)
        self.assertGreater(len(truncation.jet.thickness), 100)
        self.assertLess(
            truncation.jet.thickness[-1],
            truncation.jet.thickness[0],
        )
        continued_config = replace(
            truncation.config,
            pseudo_cfl=0.02,
            pseudo_max_iterations=1,
        )
        continued = solve_self_similar_wedge_pseudo_time(
            continued_config,
            initial_bvp=truncation.bvp,
        )
        continued_root = np.asarray(
            [
                continued.bvp.free_surface.node_xi[0],
                continued.bvp.free_surface.node_eta[0],
            ]
        )
        apex = np.asarray([0.0, -1.0])
        body_tangent = np.asarray([np.cos(beta), np.sin(beta)])
        body_projection = apex + np.dot(
            continued_root - apex,
            body_tangent,
        ) * body_tangent
        self.assertEqual(continued.termination_reason, "MAXIMUM_ITERATIONS")
        self.assertEqual(len(continued.time_step_history), 1)

        self.assertGreater(np.linalg.norm(continued_root - body_projection), 1.0e-10)
        np.testing.assert_allclose(
            [truncation.free_node_xi[0], truncation.free_node_eta[0]],
            [
                truncation.bvp.free_surface.node_xi[0],
                truncation.bvp.free_surface.node_eta[0],
            ],
            atol=1.0e-13,
        )
        coupled = solve_self_similar_wedge_with_shallow_jet(truncation)
        labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
        body_panel_length = coupled.boundary.panel_length_m[labels == "body"]
        np.testing.assert_allclose(
            body_panel_length,
            body_panel_length[0],
            rtol=1.0e-12,
            atol=1.0e-14,
        )
        expected_jet_panels_per_side = int(
            np.ceil((len(truncation.jet.thickness) - 1) / 2.0)
        )
        self.assertEqual(
            np.count_nonzero(labels == "shallow_jet_body"),
            expected_jet_panels_per_side,
        )
        self.assertEqual(
            np.count_nonzero(labels == "shallow_jet_free_surface"),
            expected_jet_panels_per_side,
        )
        self.assertLess(coupled.solution.relative_residual, 1.0e-11)
        self.assertTrue(np.isfinite(coupled.body_pressure_coefficient).all())
        all_velocity = _connected_self_similar_boundary_velocity(
            coupled.boundary,
            coupled.solution,
        )
        all_position = np.column_stack(
            (
                coupled.boundary.panel_mid_y_m,
                coupled.boundary.panel_mid_z_up_m,
            )
        )
        all_gradient = all_velocity - all_position
        jet_free = np.flatnonzero(labels == "shallow_jet_free_surface")
        outer_free = np.flatnonzero(labels == "outer_free_surface")
        jet_length = coupled.boundary.panel_length_m[jet_free[-1]]
        outer_length = coupled.boundary.panel_length_m[outer_free[0]]
        expected_root_gradient = (
            outer_length * all_gradient[jet_free[-1]]
            + jet_length * all_gradient[outer_free[0]]
        ) / (jet_length + outer_length)
        np.testing.assert_allclose(
            _coupled_outer_pseudo_velocity(coupled)[0],
            expected_root_gradient,
            atol=1.0e-12,
        )
        advanced_coupled, _, _ = advance_coupled_self_similar_wedge_pseudo_time_rk2(
            coupled,
            root_inner_iterations=0,
        )
        self.assertGreater(advanced_coupled.jet_interface.root_state.thickness, 0.0)
        self.assertAlmostEqual(
            advanced_coupled.jet_interface.jet.s_lambda[0],
            advanced_coupled.jet_interface.root_state.s_lambda,
            places=12,
        )
        coupled_root = derive_shallow_water_jet_root_state_from_coupled(coupled)
        self.assertGreater(coupled_root.s_lambda, 0.0)
        jet_body = np.flatnonzero(labels == "shallow_jet_body")
        root_panels = jet_body[:3]
        position = np.column_stack(
            (
                coupled.boundary.panel_mid_y_m[root_panels],
                coupled.boundary.panel_mid_z_up_m[root_panels],
            )
        )
        free_root = np.asarray(
            [
                coupled.outer_free_surface.node_xi[0],
                coupled.outer_free_surface.node_eta[0],
            ]
        )
        apex = np.asarray([0.0, -1.0])
        body_root = apex + coupled_root.lambda_tangent * np.dot(
            free_root - apex,
            coupled_root.lambda_tangent,
        )
        distance = (position - body_root) @ coupled_root.lambda_tangent
        midpoint_value = np.sum(
            (coupled.panel_velocity[root_panels] - position)
            * coupled_root.lambda_tangent[None, :],
            axis=1,
        )
        expected_s_lambda = float(np.polyfit(distance, midpoint_value, 2)[2])
        first_panel_s_lambda = float(midpoint_value[0])
        self.assertAlmostEqual(
            coupled_root.s_lambda,
            first_panel_s_lambda,
            places=12,
        )
        extrapolated_root = derive_shallow_water_jet_root_state_from_coupled(
            replace(
                coupled,
                config=replace(
                    coupled.config,
                    coupled_root_state_recovery="quadratic_root_extrapolation",
                ),
            )
        )
        self.assertAlmostEqual(
            extrapolated_root.s_lambda,
            expected_s_lambda,
            places=12,
        )
        # This diagnostic coupled root lies outside the admissible shallow-jet
        # branch: its first algebraic step can only increase the thickness.
        # Rebuilding must reject that state instead of silently switching to the
        # nonphysical branch.
        with self.assertRaisesRegex(
            ValueError,
            "no physical first-step solution",
        ):
            rebuild_shallow_jet_from_coupled_root(coupled)
        root = Path(__file__).resolve().parents[1] / "benchmarks"
        coupled_metrics = evaluate_self_similar_wedge_reference(
            coupled,
            root
            / "sun2007_fig2_6_wedge_similarity"
            / "fig2_6_zhao_faltinsen_similarity_curves.csv",
        )
        coupled_scalar = evaluate_self_similar_wedge_scalar_reference(
            coupled,
            root
            / "iafrati2013_self_similar_wedge"
            / "table1_pressure_peak.csv",
        )
        self.assertTrue(np.isfinite(coupled_metrics.pressure_nrmse))
        self.assertTrue(np.isfinite(coupled_scalar.pressure_peak_relative_error))
        linear_truncation = replace(
            truncation,
            config=replace(
                truncation.config,
                coupled_element_interpolation="linear_node",
            ),
        )
        linear_coupled = solve_self_similar_wedge_with_shallow_jet(
            linear_truncation
        )
        self.assertIn("continuous_linear", linear_coupled.solution.status)
        self.assertLess(linear_coupled.solution.relative_residual, 1.0e-10)
        self.assertGreater(linear_coupled.dipole_coefficient, 0.0)
        self.assertTrue(np.isfinite(linear_coupled.panel_velocity).all())
        self.assertIsNotNone(linear_coupled.outer_kinematic_residual_endpoint)
        self.assertIsNotNone(linear_coupled.kinematic_integral_linear_exact)
        self.assertGreaterEqual(linear_coupled.kinematic_integral_linear_exact, 0.0)
        self.assertAlmostEqual(
            linear_coupled.kinematic_convergence_integral,
            linear_coupled.kinematic_integral_linear_exact,
        )
        self.assertGreaterEqual(
            linear_coupled.kinematic_convergence_integral,
            linear_coupled.kinematic_integral,
        )
        self.assertAlmostEqual(
            linear_coupled.kinematic_integral_endpoint_gradient,
            linear_coupled.kinematic_integral_linear_exact
            - linear_coupled.kinematic_integral,
        )
        frozen = solve_coupled_self_similar_wedge_pseudo_time(
            linear_coupled,
            maximum_iterations=0,
            root_inner_iterations=0,
        )
        self.assertEqual(len(frozen.pseudo_time_history), 1)
        self.assertEqual(len(frozen.time_step_history), 0)
        self.assertAlmostEqual(
            frozen.kinematic_convergence_integral_history[0],
            linear_coupled.kinematic_integral_linear_exact,
        )
        converged_coupled = replace(
            linear_coupled,
            config=replace(
                linear_coupled.config,
                coupled_kinematic_integral_tolerance=1.0e9,
            ),
        )
        matching = SimpleNamespace(
            effective_panel_shift=0.0,
            root_displacement_ratio=0.0,
            trigger_code=0,
        )
        diagnostics = SimpleNamespace(
            provisional=matching,
            final=matching,
            rejected_attempt_count=0,
        )
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge."
            "_advance_coupled_self_similar_wedge_pseudo_time_rk2_with_diagnostics",
            return_value=(converged_coupled, 0.01, 0.0, diagnostics),
        ) as advance:
            stopped = solve_coupled_self_similar_wedge_pseudo_time(
                converged_coupled,
                maximum_iterations=1,
                root_inner_iterations=0,
            )
            advance.assert_not_called()
            forced = solve_coupled_self_similar_wedge_pseudo_time(
                converged_coupled,
                maximum_iterations=1,
                root_inner_iterations=0,
                stop_when_converged=False,
            )
        self.assertEqual(len(stopped.time_step_history), 0)
        self.assertEqual(len(forced.time_step_history), 1)
        self.assertEqual(forced.termination_reason, "MAXIMUM_ITERATIONS")
        self.assertTrue(forced.converged)
        double_node_coupled = solve_self_similar_wedge_with_shallow_jet(
            replace(
                linear_truncation,
                config=replace(
                    linear_truncation.config,
                    coupled_linear_corner_treatment="displaced_double_node",
                ),
            )
        )
        self.assertIn("displaced_double_node", double_node_coupled.solution.status)
        self.assertLess(double_node_coupled.solution.relative_residual, 1.0e-10)
        self.assertGreater(double_node_coupled.dipole_coefficient, 0.0)
        self.assertTrue(np.isfinite(double_node_coupled.panel_velocity).all())
        self.assertIsNotNone(double_node_coupled.normal_derivative_endpoint)
        self.assertIsNotNone(double_node_coupled.spray_root_normal_derivative_sides)
        self.assertGreater(double_node_coupled.spray_root_corner_angle_deg, 0.0)
        self.assertNotAlmostEqual(
            *double_node_coupled.spray_root_normal_derivative_sides,
            places=10,
        )
        self.assertIsNotNone(double_node_coupled.kinematic_integral_linear_exact)
        double_labels = np.asarray(
            double_node_coupled.boundary.panel_labels,
            dtype=object,
        )
        first_outer = int(np.flatnonzero(double_labels == "outer_free_surface")[0])
        double_outer = double_node_coupled.outer_free_surface
        double_tau = double_outer.tau_star + double_outer.arc_length
        double_phi = 0.5 * (
            np.square(double_outer.node_xi)
            + np.square(double_outer.node_eta)
            - np.square(double_tau)
        )
        double_tangential = (
            double_phi[1] - double_phi[0]
        ) / double_node_coupled.boundary.panel_length_m[first_outer]
        expected_outer_root_pseudo_velocity = (
            double_tangential
            * double_node_coupled.boundary.panel_tangent[first_outer]
            + double_node_coupled.normal_derivative_endpoint[first_outer, 0]
            * double_node_coupled.boundary.panel_normal[first_outer]
            - np.asarray([double_outer.node_xi[0], double_outer.node_eta[0]])
        )
        double_midpoint = np.column_stack(
            (
                double_node_coupled.boundary.panel_mid_y_m,
                double_node_coupled.boundary.panel_mid_z_up_m,
            )
        )
        double_panel_gradient = double_node_coupled.panel_velocity - double_midpoint
        last_jet_free = int(
            np.flatnonzero(double_labels == "shallow_jet_free_surface")[-1]
        )
        jet_length = double_node_coupled.boundary.panel_length_m[last_jet_free]
        outer_length = double_node_coupled.boundary.panel_length_m[first_outer]
        expected_connected_root_pseudo_velocity = (
            outer_length * double_panel_gradient[last_jet_free]
            + jet_length * double_panel_gradient[first_outer]
        ) / (jet_length + outer_length)
        np.testing.assert_allclose(
            _coupled_outer_pseudo_velocity(double_node_coupled)[0],
            expected_connected_root_pseudo_velocity,
            atol=1.0e-12,
        )
        np.testing.assert_allclose(
            _coupled_outer_pseudo_velocity(
                solve_self_similar_wedge_with_shallow_jet(
                    replace(
                        linear_truncation,
                        config=replace(
                            linear_truncation.config,
                            coupled_linear_corner_treatment="displaced_double_node",
                            coupled_linear_cusp_velocity_recovery="split_outer_side",
                        ),
                    )
                )
            )[0],
            expected_outer_root_pseudo_velocity,
            atol=1.0e-12,
        )
        recovered_coupled = solve_self_similar_wedge_with_shallow_jet(
            replace(
                linear_truncation,
                config=replace(
                    linear_truncation.config,
                    coupled_linear_gradient_recovery="connected_nodal",
                ),
            )
        )
        self.assertIn("connected_nodal", recovered_coupled.solution.status)
        self.assertTrue(np.isfinite(recovered_coupled.panel_velocity).all())

    def test_source_angle_truncation_relocates_ineligible_30deg_root(self) -> None:
        config = SelfSimilarWedgeConfig(
            deadrise_deg=30.0,
            far_radius=20.0,
            free_surface_panels=80,
            body_panels=48,
            far_field_panels=24,
            symmetry_panels=16,
            gauss_order=12,
            preliminary_iterations=8,
            pseudo_max_iterations=20,
        )
        pseudo = solve_self_similar_wedge_pseudo_time(config)
        nodes = np.column_stack(
            (
                pseudo.bvp.free_surface.node_xi,
                pseudo.bvp.free_surface.node_eta,
            )
        )
        segment = np.diff(nodes, axis=0)
        segment /= np.linalg.norm(segment, axis=1)[:, None]
        beta = np.deg2rad(config.deadrise_deg)
        body_tangent = np.asarray([np.cos(beta), np.sin(beta)])
        panel_angle = np.rad2deg(
            np.arccos(np.clip(segment @ body_tangent, -1.0, 1.0))
        )
        first_cut = int(
            np.flatnonzero(
                panel_angle[1:] > config.jet_angle_threshold_deg
            )[0]
            + 1
        )

        truncation = truncate_self_similar_wedge_to_shallow_jet(config, pseudo)

        self.assertGreater(truncation.original_cut_node_index, first_cut)
        self.assertTrue(truncation.jet.reached_tip)
        self.assertGreater(truncation.root_state.thickness, 0.0)

    def test_source_angle_truncation_exhausts_negative_10deg_roots(self) -> None:
        config = SelfSimilarWedgeConfig(
            deadrise_deg=10.0,
            far_radius=20.0,
            free_surface_panels=80,
            body_panels=48,
            far_field_panels=24,
            symmetry_panels=16,
            gauss_order=12,
            preliminary_iterations=8,
            pseudo_max_iterations=20,
        )
        pseudo = solve_self_similar_wedge_pseudo_time(config)
        with self.assertRaisesRegex(
            ValueError,
            "No shallow-water-compatible initial matching surface remains.*S_lambda",
        ):
            truncate_self_similar_wedge_to_shallow_jet(config, pseudo)

    def test_optimizer_reduces_kinematic_residual_without_reference_input(self) -> None:
        config = self._small_config(max_nfev=5)
        result = solve_self_similar_wedge(config)

        self.assertEqual(result.status, SELF_SIMILAR_WEDGE_STATUS)
        self.assertLessEqual(result.final_kinematic_rms, result.initial_kinematic_rms + 1.0e-12)
        self.assertTrue(np.isfinite(result.control_values).all())
        self.assertGreater(result.bvp.free_surface.tau_star, 0.0)
        self.assertNotIn("reference", result.optimizer_message.lower())
        reference = (
            Path(__file__).resolve().parents[1]
            / "benchmarks"
            / "sun2007_fig2_6_wedge_similarity"
            / "fig2_6_zhao_faltinsen_similarity_curves.csv"
        )
        metrics = evaluate_self_similar_wedge_reference(result, reference)
        self.assertGreater(metrics.free_surface_point_count, 0)
        self.assertGreater(metrics.pressure_point_count, 0)
        self.assertTrue(np.isfinite(metrics.free_surface_nrmse))
        self.assertTrue(np.isfinite(metrics.pressure_nrmse))
        scalar_metrics = evaluate_self_similar_wedge_scalar_reference(
            result,
            (
                Path(__file__).resolve().parents[1]
                / "benchmarks"
                / "iafrati2013_self_similar_wedge"
                / "table1_pressure_peak.csv"
            ),
        )
        self.assertEqual(scalar_metrics.reference_pressure_peak, 17.77)
        self.assertEqual(scalar_metrics.reference_peak_eta, 0.5087)
        self.assertTrue(np.isfinite(scalar_metrics.pressure_peak_relative_error))

    def test_shallow_water_jet_march_satisfies_iafrati_equations(self) -> None:
        step = 0.02
        result = march_iafrati_shallow_water_jet(
            initial_thickness=0.02,
            initial_s_lambda=0.5,
            initial_s_tau=-1.0,
            delta_lambda=step,
        )

        self.assertTrue(result.reached_tip)
        self.assertLess(abs(result.s_lambda[-1]), step)
        self.assertTrue(np.all(result.thickness >= 0.0))
        self.assertTrue(np.all(np.diff(result.thickness) <= 1.0e-10))
        for index in range(1, len(result.thickness)):
            thickness_slope = (
                result.thickness[index] - result.thickness[index - 1]
            ) / step
            expected_s_tau = result.s_tau[index - 1] + np.hypot(
                step,
                result.thickness[index] - result.thickness[index - 1],
            )
            expected_s_lambda = -expected_s_tau / np.sqrt(
                1.0 + thickness_slope**2
            )
            fixed_point_thickness = -result.thickness[index - 1] * (
                step - result.s_lambda[index - 1]
            ) / (step + result.s_lambda[index])
            self.assertAlmostEqual(result.s_tau[index], expected_s_tau, places=9)
            self.assertAlmostEqual(result.s_lambda[index], expected_s_lambda, places=9)
            self.assertAlmostEqual(
                result.thickness[index], fixed_point_thickness, places=8
            )

    def test_shallow_water_jet_rejects_increasing_algebraic_branch(self) -> None:
        result = march_iafrati_shallow_water_jet(
            initial_thickness=0.15235219111164,
            initial_s_lambda=2.0141982466147197,
            initial_s_tau=-4.25972692569556,
            delta_lambda=0.00252046639857356,
        )

        self.assertTrue(result.reached_tip)
        self.assertTrue(np.all(np.diff(result.thickness) <= 1.0e-10))

    def test_shallow_water_jet_rejects_nonphysical_root_state(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            r"invalid=thickness<=0.*thickness=0.*S_lambda=0.5.*S_tau=-1",
        ):
            march_iafrati_shallow_water_jet(
                initial_thickness=0.0,
                initial_s_lambda=0.5,
                initial_s_tau=-1.0,
                delta_lambda=0.02,
            )

    def test_shallow_water_jet_rejects_an_unreached_capped_tip(self) -> None:
        with self.assertRaisesRegex(ValueError, "maximum_points before the jet tip"):
            march_iafrati_shallow_water_jet(
                initial_thickness=0.02,
                initial_s_lambda=0.5,
                initial_s_tau=-1.0,
                delta_lambda=0.02,
                maximum_points=2,
            )

    def test_under_resolved_truncated_outer_solution_is_not_forced_into_jet(self) -> None:
        config = self._small_config(jet_closure="truncated_control")
        controls = np.asarray([4.1, 0.36, 0.20, 0.08, 0.0])
        bvp = solve_self_similar_wedge_bvp(config, controls)
        root = derive_shallow_water_jet_root_state(
            bvp, deadrise_deg=config.deadrise_deg
        )

        self.assertGreater(root.thickness, 0.0)
        self.assertGreater(root.delta_lambda, 0.0)
        self.assertAlmostEqual(root.s_tau, -bvp.free_surface.tau_star)
        self.assertLess(root.s_lambda, 0.0)
        with self.assertRaisesRegex(ValueError, "S_lambda<=0"):
            march_shallow_water_jet_from_outer_solution(
                bvp, deadrise_deg=config.deadrise_deg
            )


if __name__ == "__main__":
    unittest.main()
