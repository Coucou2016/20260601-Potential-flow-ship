from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    SelfSimilarCoupledCheckpoint,
    _acceleration_source_pseudo_times,
    _maximum_midpoint_displacement_ratio,
    accelerate_coupled_self_similar_checkpoints,
    infer_matching_surface_phase,
    load_coupled_self_similar_checkpoint,
    merge_coupled_checkpoint_history,
    regrid_coupled_self_similar_checkpoint,
    write_coupled_self_similar_checkpoint,
)
from scripts.resume_self_similar_wedge import _identity_resume_transformation
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    SelfSimilarWedgeConfig,
)
from scripts.verify_self_similar_checkpoint_equivalence import (
    compare_checkpoint_outputs,
)
from scripts.accelerate_self_similar_wedge import write_acceleration_rejection


class SelfSimilarCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.config = SelfSimilarWedgeConfig(
            jet_closure="truncated_control",
            coupled_element_interpolation="linear_node",
        )
        self.coupled = SimpleNamespace(
            config=self.config,
            kinematic_rms=0.5,
            kinematic_integral=0.25,
            kinematic_length_weighted_rms=0.4,
            dipole_coefficient=2.0,
            solution=SimpleNamespace(condition_number=10.0),
            body_pressure_coefficient=np.asarray([-1.0, 4.0]),
            body_vertical_force_coefficient=5.0,
            jet_interface=SimpleNamespace(
                root_state=SimpleNamespace(s_lambda=3.0, thickness=0.1)
            ),
            outer_free_surface=SimpleNamespace(
                node_xi=np.linspace(1.0, 5.0, 5),
                node_eta=np.linspace(0.2, 0.0, 5),
            ),
        )
        self.history = pd.DataFrame(
            {
                "iteration": [0, 1],
                "pseudo_time": [0.0, 0.01],
                "kinematic_rms": [0.6, 0.5],
                "dipole_coefficient": [1.9, 2.0],
                "root_thickness": [0.1, 0.1],
                "root_s_lambda": [2.9, 3.0],
                "root_measured_s_lambda": [3.0, 3.1],
                "root_relative_mismatch": [0.034, 0.1 / 3.0],
                "root_body_eta": [0.19, 0.2],
                "root_resolution_ratio": [1.0, 1.0],
                "bem_condition_number": [9.0, 10.0],
                "accepted_time_step": [np.nan, 0.01],
                "maximum_displacement_ratio": [np.nan, 0.2],
            }
        )

    @staticmethod
    def _measured(_coupled: object) -> SimpleNamespace:
        return SimpleNamespace(s_lambda=3.1)

    def test_formal_checkpoint_round_trip_and_history_merge(self) -> None:
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
            "derive_shallow_water_jet_root_state_from_coupled",
            side_effect=self._measured,
        ):
            write_coupled_self_similar_checkpoint(
                self.output,
                self.coupled,
                self.history,
            )
        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "_build_coupled_solution_from_outer_nodes",
                return_value=self.coupled,
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "derive_shallow_water_jet_root_state_from_coupled",
                side_effect=self._measured,
            ),
        ):
            checkpoint = load_coupled_self_similar_checkpoint(self.output)

        self.assertIsInstance(checkpoint, SelfSimilarCoupledCheckpoint)
        self.assertEqual(checkpoint.source_kind, "formal_v1")
        self.assertEqual(checkpoint.completed_iterations, 1)
        self.assertLess(max(checkpoint.reconstruction_relative_errors.values()), 1e-12)

        continuation = SimpleNamespace(
            pseudo_time_history=np.asarray([0.0, 0.02]),
            time_step_history=np.asarray([0.02]),
            kinematic_rms_history=np.asarray([0.5, 0.4]),
            kinematic_integral_history=np.asarray([0.25, 0.16]),
            dipole_coefficient_history=np.asarray([2.0, 2.1]),
            root_thickness_history=np.asarray([0.1, 0.11]),
            root_s_lambda_history=np.asarray([3.0, 3.2]),
            root_measured_s_lambda_history=np.asarray([3.1, 3.25]),
            root_relative_mismatch_history=np.asarray([0.1 / 3.0, 0.05 / 3.2]),
            root_body_eta_history=np.asarray([0.2, 0.21]),
            root_resolution_ratio_history=np.asarray([1.0, 1.1]),
            bem_condition_number_history=np.asarray([10.0, 11.0]),
            maximum_displacement_ratio_history=np.asarray([0.19]),
            provisional_matching_surface_shift_history=np.asarray([0.625]),
            final_matching_surface_shift_history=np.asarray([0.75]),
            provisional_matching_surface_root_displacement_history=np.asarray([0.61]),
            final_matching_surface_root_displacement_history=np.asarray([0.72]),
            provisional_matching_surface_trigger_history=np.asarray([1]),
            final_matching_surface_trigger_history=np.asarray([1]),
            rk2_rejected_attempt_count_history=np.asarray([2]),
            jet_point_count_history=np.asarray([101, 103]),
            shallow_jet_panel_count_per_side_history=np.asarray([50, 51]),
            boundary_panel_count_history=np.asarray([180, 182]),
            jet_tip_thickness_history=np.asarray([1.0e-4, 8.0e-5]),
            jet_tip_s_lambda_history=np.asarray([5.0e-3, 4.0e-3]),
        )
        merged = merge_coupled_checkpoint_history(checkpoint, continuation)
        self.assertEqual(merged["iteration"].tolist(), [0, 1, 2])
        self.assertAlmostEqual(float(merged.iloc[-1]["pseudo_time"]), 0.03)
        self.assertAlmostEqual(float(merged.iloc[-1]["accepted_time_step"]), 0.02)
        self.assertTrue(merged["kinematic_integral"].iloc[:2].isna().all())
        self.assertAlmostEqual(float(merged.iloc[-1]["kinematic_integral"]), 0.16)
        self.assertTrue(
            merged["final_matching_surface_shift_panels"].iloc[:2].isna().all()
        )
        self.assertAlmostEqual(
            float(merged.iloc[-1]["final_matching_surface_shift_panels"]),
            0.75,
        )
        self.assertEqual(
            float(merged.iloc[-1]["rk2_rejected_attempt_count"]),
            2.0,
        )
        self.assertTrue(merged["jet_point_count"].iloc[:2].isna().all())
        self.assertEqual(float(merged.iloc[-1]["jet_point_count"]), 103.0)
        self.assertEqual(float(merged.iloc[-1]["boundary_panel_count"]), 182.0)

    def test_formal_checkpoint_reads_outer_nodes_with_binary_round_trip(self) -> None:
        xi = np.asarray(
            [
                np.nextafter(4.3, np.inf),
                np.nextafter(4.31, -np.inf),
                np.nextafter(7.7, np.inf),
                np.nextafter(12.2, -np.inf),
                np.nextafter(20.0, -np.inf),
            ]
        )
        eta = np.asarray(
            [
                np.nextafter(0.41, np.inf),
                np.nextafter(0.40, -np.inf),
                np.nextafter(0.2, np.inf),
                np.nextafter(0.1, -np.inf),
                np.nextafter(0.04, np.inf),
            ]
        )
        coupled = SimpleNamespace(
            **{
                **self.coupled.__dict__,
                "outer_free_surface": SimpleNamespace(node_xi=xi, node_eta=eta),
            }
        )
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
            "derive_shallow_water_jet_root_state_from_coupled",
            side_effect=self._measured,
        ):
            write_coupled_self_similar_checkpoint(self.output, coupled, self.history)
        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "_build_coupled_solution_from_outer_nodes",
                return_value=coupled,
            ) as builder,
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "derive_shallow_water_jet_root_state_from_coupled",
                side_effect=self._measured,
            ),
        ):
            load_coupled_self_similar_checkpoint(self.output)
        loaded_nodes = builder.call_args.args[1]
        np.testing.assert_array_equal(loaded_nodes[:, 0], xi)
        np.testing.assert_array_equal(loaded_nodes[:, 1], eta)

    def test_zero_step_transformation_can_declare_new_outer_shape_dipole(self) -> None:
        parent = SimpleNamespace(
            outer_shape_dipole_coefficient=1.5,
            source_directory=self.output / "parent",
            source_kind="formal_v1",
            completed_iterations=10,
            source_hashes={"coupled_checkpoint.json": "parent-hash"},
            continuation_config_overrides={},
        )
        transformed_dipole = 2.75
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
            "derive_shallow_water_jet_root_state_from_coupled",
            side_effect=self._measured,
        ):
            write_coupled_self_similar_checkpoint(
                self.output,
                self.coupled,
                self.history.iloc[[0]].copy(),
                parent=parent,
                transformation={
                    "type": "shape_change",
                    "outer_shape_dipole_coefficient": transformed_dipole,
                },
            )
        metadata = json.loads(
            (self.output / "coupled_checkpoint.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            metadata["outer_shape_dipole_coefficient"],
            transformed_dipole,
        )

    def test_converged_zero_step_resume_declares_identity_transformation(self) -> None:
        checkpoint = SimpleNamespace(
            outer_shape_dipole_coefficient=2.75,
            continuation_config_overrides={"pseudo_cfl": 0.125},
        )
        stopped = SimpleNamespace(
            time_step_history=(),
            termination_reason="CONVERGED_INITIAL_STATE",
        )
        transformation = _identity_resume_transformation(checkpoint, stopped)
        self.assertEqual(
            transformation,
            {
                "type": "identity_resume_at_converged_source",
                "outer_shape_dipole_coefficient": 2.75,
                "termination_reason": "CONVERGED_INITIAL_STATE",
                "continuation_config_overrides": {"pseudo_cfl": 0.125},
                "reference_used_during_transformation": False,
            },
        )
        advanced = SimpleNamespace(
            time_step_history=(0.01,),
            termination_reason="MAXIMUM_ITERATIONS",
        )
        self.assertIsNone(
            _identity_resume_transformation(checkpoint, advanced)
        )

    def test_checkpoint_rejects_tampered_history(self) -> None:
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
            "derive_shallow_water_jet_root_state_from_coupled",
            side_effect=self._measured,
        ):
            write_coupled_self_similar_checkpoint(
                self.output,
                self.coupled,
                self.history,
            )
        history_path = self.output / "coupled_pseudo_time_history.csv"
        history_path.write_text(
            history_path.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "history SHA-256"):
            load_coupled_self_similar_checkpoint(self.output)

    def test_checkpoint_rejects_unsupported_schema(self) -> None:
        metadata_path = self.output / "coupled_checkpoint.json"
        metadata_path.write_text(
            json.dumps({"schema_version": 999}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "schema version"):
            load_coupled_self_similar_checkpoint(self.output)

    def test_checkpoint_allows_declared_numerical_continuation_overrides(self) -> None:
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
            "derive_shallow_water_jet_root_state_from_coupled",
            side_effect=self._measured,
        ):
            write_coupled_self_similar_checkpoint(
                self.output,
                self.coupled,
                self.history,
            )
        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "_build_coupled_solution_from_outer_nodes",
                return_value=self.coupled,
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "derive_shallow_water_jet_root_state_from_coupled",
                side_effect=self._measured,
            ),
        ):
            refined = load_coupled_self_similar_checkpoint(
                self.output,
                continuation_config_overrides={
                    "pseudo_cfl": 0.05,
                    "coupled_jet_bie_panel_count": 260,
                    "coupled_root_inner_tolerance": 1.0e-4,
                    "coupled_pseudo_time_preconditioner": "panel_length",
                    "coupled_pseudo_time_preconditioner_max_ratio": 8.0,
                },
            )
            self.assertEqual(refined.config.pseudo_cfl, 0.05)
            self.assertEqual(refined.config.coupled_jet_bie_panel_count, 260)
            self.assertEqual(refined.config.coupled_root_inner_tolerance, 1.0e-4)
            self.assertEqual(
                refined.config.coupled_pseudo_time_preconditioner,
                "panel_length",
            )
            self.assertEqual(
                refined.config.coupled_pseudo_time_preconditioner_max_ratio,
                8.0,
            )
            self.assertEqual(
                refined.continuation_config_overrides,
                {
                    "pseudo_cfl": 0.05,
                    "coupled_jet_bie_panel_count": 260,
                    "coupled_root_inner_tolerance": 1.0e-4,
                    "coupled_pseudo_time_preconditioner": "panel_length",
                    "coupled_pseudo_time_preconditioner_max_ratio": 8.0,
                },
            )
            with self.assertRaisesRegex(ValueError, "may only override"):
                load_coupled_self_similar_checkpoint(
                    self.output,
                    continuation_config_overrides={"deadrise_deg": 10.0},
                )

    def test_checkpoint_regrid_is_explicit_and_preserves_frozen_endpoints(self) -> None:
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
            "derive_shallow_water_jet_root_state_from_coupled",
            side_effect=self._measured,
        ):
            write_coupled_self_similar_checkpoint(
                self.output,
                self.coupled,
                self.history,
            )
        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "_build_coupled_solution_from_outer_nodes",
                return_value=self.coupled,
            ) as builder,
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "derive_shallow_water_jet_root_state_from_coupled",
                side_effect=self._measured,
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "_regrid_coupled_outer_nodes",
                side_effect=lambda _config, nodes: np.asarray(nodes).copy(),
            ),
        ):
            checkpoint = load_coupled_self_similar_checkpoint(self.output)
            regridded = regrid_coupled_self_similar_checkpoint(
                checkpoint,
                12,
                linear_corner_treatment="displaced_double_node",
                linear_cusp_velocity_recovery="split_average",
                free_surface_update="continuous_normal",
            )
        target_nodes = builder.call_args.args[1]
        self.assertEqual(regridded.source_panel_count, 4)
        self.assertEqual(regridded.target_panel_count, 12)
        self.assertEqual(target_nodes.shape, (13, 2))
        np.testing.assert_array_equal(target_nodes[0], [1.0, 0.2])
        np.testing.assert_array_equal(target_nodes[-1], [5.0, 0.0])
        self.assertLess(regridded.geometry_relative_l2, 1e-3)
        target_config = builder.call_args.args[0]
        self.assertEqual(
            target_config.coupled_linear_corner_treatment,
            "displaced_double_node",
        )
        self.assertEqual(regridded.source_linear_corner_treatment, "shared_node")
        self.assertEqual(
            regridded.target_linear_corner_treatment,
            "displaced_double_node",
        )
        self.assertEqual(
            target_config.coupled_linear_cusp_velocity_recovery,
            "split_average",
        )
        self.assertEqual(
            regridded.source_linear_cusp_velocity_recovery,
            "connected_average",
        )
        self.assertEqual(
            regridded.target_linear_cusp_velocity_recovery,
            "split_average",
        )
        self.assertEqual(regridded.source_free_surface_update, "full_gradient")
        self.assertEqual(
            regridded.target_free_surface_update,
            "continuous_normal",
        )
        self.assertEqual(
            target_config.coupled_free_surface_update,
            "continuous_normal",
        )
        self.assertEqual(
            regridded.production_maintenance_maximum_midpoint_displacement_ratio,
            0.0,
        )
        self.assertEqual(
            regridded.post_maintenance_maximum_midpoint_displacement_ratio,
            0.0,
        )

    def test_checkpoint_regrid_supports_double_ended_far_domain_extension(self) -> None:
        source_x = np.linspace(4.0, 20.0, 81)
        source_y = 8.0 / (3.0 * np.square(source_x))
        source_y[-1] = 0.0
        source_coupled = SimpleNamespace(
            **{
                **self.coupled.__dict__,
                "outer_free_surface": SimpleNamespace(
                    node_xi=source_x,
                    node_eta=source_y,
                ),
            }
        )
        checkpoint = SimpleNamespace(
            config=self.config,
            coupled=source_coupled,
            outer_shape_dipole_coefficient=8.0,
        )
        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "_build_coupled_solution_from_outer_nodes",
                return_value=source_coupled,
            ) as builder,
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "derive_shallow_water_jet_root_state_from_coupled",
                side_effect=self._measured,
            ),
        ):
            result = regrid_coupled_self_similar_checkpoint(
                checkpoint,
                96,
                target_far_radius=24.0,
                grid_mode="double_ended",
                root_spacing_ratio=0.08,
                far_spacing_ratio=0.25,
                endpoint_decay=4.0,
            )

        target_config = builder.call_args.args[0]
        target_nodes = builder.call_args.args[1]
        spacing = np.linalg.norm(np.diff(target_nodes, axis=0), axis=1)
        self.assertEqual(target_nodes.shape, (97, 2))
        np.testing.assert_allclose(target_nodes[0], [4.0, source_y[0]])
        self.assertAlmostEqual(float(np.linalg.norm(target_nodes[-1])), 24.0, places=10)
        self.assertEqual(target_config.coupled_outer_grid_mode, "double_ended")
        self.assertEqual(target_config.far_radius, 24.0)
        self.assertEqual(result.target_far_field_panels, 29)
        self.assertEqual(result.target_symmetry_panels, 19)
        self.assertTrue(result.asymptotic_extension_used)
        self.assertLess(spacing[0], np.median(spacing))
        self.assertLess(spacing[-1], np.median(spacing))
        self.assertTrue(
            np.isfinite(
                result.production_maintenance_maximum_midpoint_displacement_ratio
            )
        )
        self.assertLess(
            result.post_maintenance_maximum_midpoint_displacement_ratio,
            result.production_maintenance_maximum_midpoint_displacement_ratio,
        )

    def test_displacement_ratio_aligns_equivalent_different_node_counts(self) -> None:
        source = np.column_stack((np.linspace(0.0, 2.0, 3), np.zeros(3)))
        candidate = np.column_stack((np.linspace(0.0, 2.0, 9), np.zeros(9)))
        self.assertLess(
            _maximum_midpoint_displacement_ratio(source, candidate),
            1.0e-13,
        )

    def test_checkpoint_regrid_builds_and_freezes_reference_isolated_monitor(self) -> None:
        source_x = np.linspace(4.0, 20.0, 81)
        source_fraction = np.linspace(0.0, 1.0, 81)
        source_y = 0.2 * np.square(1.0 - source_fraction)
        source_coupled = SimpleNamespace(
            **{
                **self.coupled.__dict__,
                "outer_free_surface": SimpleNamespace(
                    node_xi=source_x,
                    node_eta=source_y,
                ),
                "outer_kinematic_residual": 0.01
                + np.exp(-np.square(source_fraction[:-1] - 0.5) / 0.004),
                "outer_kinematic_residual_endpoint": None,
                "boundary": SimpleNamespace(
                    panel_labels=("shallow_jet_body",) * 256,
                ),
            }
        )
        checkpoint = SimpleNamespace(
            config=self.config,
            coupled=source_coupled,
            outer_shape_dipole_coefficient=2.0,
        )
        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "_build_coupled_solution_from_outer_nodes",
                return_value=source_coupled,
            ) as builder,
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "derive_shallow_water_jet_root_state_from_coupled",
                side_effect=self._measured,
            ),
        ):
            result = regrid_coupled_self_similar_checkpoint(
                checkpoint,
                80,
                root_spacing_ratio=0.08,
                far_spacing_ratio=0.25,
                monitor_residual_weight=1.0,
                monitor_curvature_weight=0.25,
                monitor_growth_weight=0.15,
                monitor_maximum_node_shift_panels=2.0,
            )

        target_config = builder.call_args.args[0]
        fractions = np.asarray(target_config.coupled_outer_monitor_fractions)
        self.assertEqual(target_config.coupled_outer_grid_mode, "frozen_monitor")
        self.assertEqual(fractions.shape, (81,))
        self.assertTrue(np.all(np.diff(fractions) > 0.0))
        self.assertTrue(result.monitor_used)
        self.assertEqual(result.monitor_residual_weight, 1.0)
        self.assertEqual(result.monitor_maximum_node_shift_panels, 2.0)
        self.assertEqual(target_config.coupled_jet_bie_panel_count, 256)
        self.assertEqual(result.target_jet_bie_panel_count, 256)

    def test_vector_aitken_acceleration_requires_and_reduces_a_contraction(self) -> None:
        base = np.column_stack(
            (np.linspace(1.0, 5.0, 5), np.linspace(0.2, 0.0, 5))
        )
        increment = np.column_stack((np.zeros(5), np.linspace(0.0, 0.01, 5)))

        def matching_history(phase: int = 0) -> pd.DataFrame:
            count = 13 + phase
            thickness = np.ones(count)
            resolution = np.ones(count)
            level = 1.0
            for index in range(count):
                if index in (4, 8, 12):
                    level *= 1.1
                thickness[index] = level
                resolution[index] = level
            return pd.DataFrame(
                {
                    "iteration": np.arange(count),
                    "root_thickness": thickness,
                    "root_resolution_ratio": resolution,
                }
            )

        def checkpoint(nodes: np.ndarray, time: float) -> SimpleNamespace:
            coupled = SimpleNamespace(
                config=self.config,
                outer_free_surface=SimpleNamespace(
                    node_xi=nodes[:, 0], node_eta=nodes[:, 1]
                ),
                jet_interface=SimpleNamespace(
                    root_state=SimpleNamespace(s_lambda=3.0 - 0.01 * time)
                ),
                kinematic_rms=0.5,
                kinematic_integral=0.5,
                solution=SimpleNamespace(condition_number=10.0),
            )
            return SimpleNamespace(
                config=self.config,
                coupled=coupled,
                cumulative_pseudo_time=time,
                outer_shape_dipole_coefficient=2.0 + 0.1 * time,
                history=matching_history(),
            )

        sources = (
            checkpoint(base, 0.0),
            checkpoint(base + increment, 1.0),
            checkpoint(base + 1.5 * increment, 2.0),
        )
        rebuilt = SimpleNamespace(
            kinematic_rms=0.3,
            kinematic_integral=0.3,
            solution=SimpleNamespace(condition_number=20.0),
        )
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
            "_build_coupled_solution_from_outer_nodes",
            return_value=rebuilt,
        ) as builder:
            result = accelerate_coupled_self_similar_checkpoints(sources)
        self.assertAlmostEqual(result.vector_convergence_factor, 0.5)
        self.assertAlmostEqual(result.raw_extrapolation_factor, 1.0)
        self.assertFalse(result.extrapolation_was_clipped)
        self.assertAlmostEqual(result.residual_ratio, 0.6)
        self.assertAlmostEqual(result.legacy_unweighted_rms_ratio, 0.6)
        self.assertEqual(result.source_matching_surface_phases, (0, 0, 0))
        self.assertEqual(result.source_modal_cycle_lengths, (4, 4, 4))
        self.assertEqual(builder.call_args.args[1].shape, (5, 2))

    def test_vector_aitken_can_clip_to_explicit_displacement_trust_region(self) -> None:
        base = np.column_stack(
            (np.linspace(1.0, 5.0, 5), np.linspace(0.2, 0.0, 5))
        )
        increment = np.column_stack((np.zeros(5), np.linspace(0.0, 0.02, 5)))

        def checkpoint(nodes: np.ndarray, time: float) -> SimpleNamespace:
            return SimpleNamespace(
                config=self.config,
                coupled=SimpleNamespace(
                    config=self.config,
                    outer_free_surface=SimpleNamespace(
                        node_xi=nodes[:, 0], node_eta=nodes[:, 1]
                    ),
                    jet_interface=SimpleNamespace(
                        root_state=SimpleNamespace(s_lambda=3.0)
                    ),
                    kinematic_rms=0.5,
                    kinematic_integral=0.5,
                    solution=SimpleNamespace(condition_number=10.0),
                ),
                cumulative_pseudo_time=time,
                outer_shape_dipole_coefficient=2.0,
                history=pd.DataFrame(),
            )

        sources = (
            checkpoint(base, 0.0),
            checkpoint(base + increment, 1.0),
            checkpoint(base + 1.95 * increment, 2.0),
        )
        phase = SimpleNamespace(phase_index=0, modal_cycle_length=1, reset_count=0)
        rebuilt = SimpleNamespace(
            kinematic_rms=0.4,
            kinematic_integral=0.4,
            solution=SimpleNamespace(condition_number=20.0),
        )
        with (
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "infer_matching_surface_phase",
                return_value=phase,
            ),
            patch(
                "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
                "_build_coupled_solution_from_outer_nodes",
                return_value=rebuilt,
            ),
        ):
            result = accelerate_coupled_self_similar_checkpoints(
                sources,
                maximum_convergence_factor=0.99,
                maximum_displacement_ratio=0.05,
                clip_extrapolation_to_displacement_limit=True,
            )
        self.assertAlmostEqual(result.vector_convergence_factor, 0.95)
        self.assertGreater(result.raw_extrapolation_factor, result.extrapolation_factor)
        self.assertTrue(result.extrapolation_was_clipped)
        self.assertAlmostEqual(result.maximum_node_displacement_ratio, 0.05)

    def test_matching_surface_phase_inference_uses_joint_resets(self) -> None:
        history = pd.DataFrame(
            {
                "iteration": np.arange(15),
                "root_thickness": [
                    1.0, 1.0, 1.0, 1.0,
                    1.1, 1.1, 1.1, 1.1,
                    1.21, 1.21, 1.21, 1.21,
                    1.331, 1.331, 1.331,
                ],
                "root_resolution_ratio": [
                    1.0, 1.0, 1.0, 1.0,
                    1.1, 1.1, 1.1, 1.1,
                    1.21, 1.21, 1.21, 1.21,
                    1.331, 1.331, 1.331,
                ],
            }
        )
        phase = infer_matching_surface_phase(history)
        self.assertEqual(phase.modal_cycle_length, 4)
        self.assertEqual(phase.phase_index, 2)
        self.assertEqual(phase.reset_iterations, (4, 8, 12))

    def test_matching_surface_phase_accepts_explicit_no_reset_steady_history(self) -> None:
        history = pd.DataFrame(
            {
                "iteration": np.arange(8),
                "root_thickness": np.linspace(1.0, 1.01, 8),
                "root_resolution_ratio": np.linspace(1.0, 1.01, 8),
                "provisional_matching_surface_shift_panels": [np.nan] + [0.0] * 7,
                "final_matching_surface_shift_panels": [np.nan] + [0.0] * 7,
                "boundary_panel_count": [840.0] * 8,
            }
        )
        phase = infer_matching_surface_phase(history)
        self.assertEqual(phase.phase_index, 0)
        self.assertEqual(phase.modal_cycle_length, 1)
        self.assertEqual(phase.reset_count, 0)
        self.assertEqual(phase.reset_iterations, ())

    def test_matching_surface_phase_accepts_explicit_no_reset_smooth_history(self) -> None:
        history = pd.DataFrame(
            {
                "iteration": np.arange(8),
                "root_thickness": np.linspace(1.0, 1.02, 8),
                "root_resolution_ratio": np.linspace(1.0, 1.03, 8),
                "provisional_matching_surface_shift_panels": [np.nan]
                + list(np.linspace(0.04, 0.07, 7)),
                "final_matching_surface_shift_panels": [np.nan]
                + list(np.linspace(0.04, 0.07, 7)),
                "boundary_panel_count": [840.0] * 6 + [842.0] * 2,
            }
        )
        phase = infer_matching_surface_phase(history)
        self.assertEqual(phase.phase_index, 0)
        self.assertEqual(phase.modal_cycle_length, 1)
        self.assertEqual(phase.reset_count, 0)

    def test_matching_surface_phase_uses_smooth_trailing_window(self) -> None:
        count = 20
        thickness = np.linspace(1.0, 1.3, count)
        resolution = np.linspace(1.0, 1.3, count)
        provisional = np.linspace(0.04, 0.09, count)
        final = provisional.copy()
        thickness[5:] *= 1.1
        resolution[5:] *= 1.1
        provisional[6] = 0.4
        final[6] = 0.4
        history = pd.DataFrame(
            {
                "iteration": np.arange(count),
                "root_thickness": thickness,
                "root_resolution_ratio": resolution,
                "provisional_matching_surface_shift_panels": provisional,
                "final_matching_surface_shift_panels": final,
                "boundary_panel_count": [840.0] * count,
            }
        )
        phase = infer_matching_surface_phase(history)
        self.assertEqual(phase.phase_index, 0)
        self.assertEqual(phase.modal_cycle_length, 1)
        self.assertEqual(phase.reset_count, 1)
        self.assertEqual(phase.reset_iterations, (5,))
        self.assertEqual(phase.period_interval_count, 7)

    def test_matching_surface_phase_rejects_abrupt_no_reset_shift(self) -> None:
        history = pd.DataFrame(
            {
                "iteration": np.arange(8),
                "root_thickness": np.linspace(1.0, 1.02, 8),
                "root_resolution_ratio": np.linspace(1.0, 1.03, 8),
                "provisional_matching_surface_shift_panels": [
                    np.nan,
                    0.04,
                    0.05,
                    0.06,
                    0.35,
                    0.07,
                    0.08,
                    0.09,
                ],
                "final_matching_surface_shift_panels": [
                    np.nan,
                    0.04,
                    0.05,
                    0.06,
                    0.35,
                    0.07,
                    0.08,
                    0.09,
                ],
                "boundary_panel_count": [840.0] * 8,
            }
        )
        with self.assertRaisesRegex(ValueError, "zero/smooth shifts"):
            infer_matching_surface_phase(history)

    def test_matching_surface_phase_rejects_unproven_no_reset_history(self) -> None:
        history = pd.DataFrame(
            {
                "iteration": np.arange(8),
                "root_thickness": np.ones(8),
                "root_resolution_ratio": np.ones(8),
            }
        )
        with self.assertRaisesRegex(ValueError, "explicit zero/smooth shifts"):
            infer_matching_surface_phase(history)

    def test_acceleration_recovers_direct_parent_local_segment_times(self) -> None:
        directories = [self.output / f"segment_{index}" for index in range(3)]
        for directory in directories:
            directory.mkdir()
        for index in (1, 2):
            metadata = {
                "parent_checkpoint": {"path": str(directories[index - 1])}
            }
            (directories[index] / "coupled_checkpoint.json").write_text(
                json.dumps(metadata), encoding="utf-8"
            )
        checkpoints = tuple(
            SimpleNamespace(
                source_directory=directory,
                cumulative_pseudo_time=duration,
                completed_iterations=10,
            )
            for directory, duration in zip(directories, (0.010, 0.011, 0.012))
        )
        times, basis = _acceleration_source_pseudo_times(checkpoints)
        self.assertEqual(basis, "direct_parent_local_segment_durations")
        np.testing.assert_allclose(times, (0.0, 0.011, 0.023))

    def test_vector_aitken_rejects_phase_misaligned_sources_before_rebuild(self) -> None:
        base = np.column_stack(
            (np.linspace(1.0, 5.0, 5), np.linspace(0.2, 0.0, 5))
        )

        def checkpoint(phase: int, time: float) -> SimpleNamespace:
            count = 13 + phase
            scale = np.ones(count)
            level = 1.0
            for index in range(count):
                if index in (4, 8, 12):
                    level *= 1.1
                scale[index] = level
            return SimpleNamespace(
                config=self.config,
                coupled=SimpleNamespace(
                    outer_free_surface=SimpleNamespace(
                        node_xi=base[:, 0], node_eta=base[:, 1]
                    )
                ),
                cumulative_pseudo_time=time,
                history=pd.DataFrame(
                    {
                        "iteration": np.arange(count),
                        "root_thickness": scale,
                        "root_resolution_ratio": scale,
                    }
                ),
            )

        sources = (
            checkpoint(1, 0.0),
            checkpoint(0, 1.0),
            checkpoint(3, 2.0),
        )
        with patch(
            "planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint."
            "_build_coupled_solution_from_outer_nodes"
        ) as builder:
            with self.assertRaisesRegex(
                ValueError,
                r"phases=\[1, 0, 3\].*modal_periods=\[4, 4, 4\]",
            ):
                accelerate_coupled_self_similar_checkpoints(sources)
        builder.assert_not_called()

    def test_vector_aitken_rejection_writes_machine_evidence(self) -> None:
        sources = tuple(self.output / f"source_{index}" for index in range(3))
        checkpoints = tuple(
            SimpleNamespace(
                completed_iterations=10 * (index + 1),
                cumulative_pseudo_time=0.1 * (index + 1),
                source_hashes={"coupled_checkpoint.json": f"hash-{index}"},
                reconstruction_relative_errors={"kinematic_rms": 1.0e-12},
            )
            for index in range(3)
        )
        path = write_acceleration_rejection(
            self.output / "rejected",
            sources,
            checkpoints,
            reason="candidate residual ratio=0.98",
            maximum_displacement_ratio=4.0,
        )
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["qualification"]["result"], "REJECTED")
        self.assertEqual(report["sources"][2]["completed_iterations"], 30)
        self.assertFalse(report["reference_used_during_transformation"])

    def test_equivalence_verifier_detects_state_difference(self) -> None:
        direct = self.output / "direct"
        chained = self.output / "chained"
        final_state = {
            "kinematic_rms": 0.5,
            "solved_dipole_coefficient": 2.0,
        }
        for directory in (direct, chained):
            directory.mkdir()
            self.history.to_csv(
                directory / "coupled_pseudo_time_history.csv",
                index=False,
            )
            pd.DataFrame(
                {"xi": np.linspace(1.0, 5.0, 5), "eta": np.linspace(0.2, 0.0, 5)}
            ).to_csv(directory / "coupled_checkpoint_outer_nodes.csv", index=False)
            (directory / "coupled_checkpoint.json").write_text(
                json.dumps({"schema_version": 1}),
                encoding="utf-8",
            )
            (directory / "resume_summary.json").write_text(
                json.dumps(
                    {
                        "continuation": {"completed_iterations": 1},
                        "final_state": final_state,
                    }
                ),
                encoding="utf-8",
            )

        passed = compare_checkpoint_outputs(direct, chained)
        self.assertEqual(passed["status"], "PASS")
        changed = json.loads((chained / "resume_summary.json").read_text())
        changed["final_state"]["kinematic_rms"] = 0.6
        (chained / "resume_summary.json").write_text(
            json.dumps(changed),
            encoding="utf-8",
        )
        failed = compare_checkpoint_outputs(direct, chained)
        self.assertEqual(failed["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
