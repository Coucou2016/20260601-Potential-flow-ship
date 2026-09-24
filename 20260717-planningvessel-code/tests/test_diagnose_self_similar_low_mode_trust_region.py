from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.diagnose_self_similar_low_mode_trust_region import (
    _build_candidate,
    admissible_one_sided_difference,
    basis_residual_coefficients,
    constrained_damped_gauss_newton_step,
    damped_gauss_newton_step,
    dct_nodal_basis,
    dual_endpoint_local_nodal_basis,
    exact_endpoint_residual_vector,
    far_local_nodal_basis,
    fix_far_basis_nodes,
    fix_root_basis_nodes,
    linear_nodal_mass_matrix,
    low_mode_residual_coefficients,
    polyline_curvature_metrics,
    root_local_nodal_basis,
    root_cosine_local_nodal_basis,
    root_feasibility_gate_limit,
    trust_region_scale,
)
from scripts.analyze_self_similar_multigrid_feasible_subspace import (
    residual_interval_energy_fraction,
    residual_segment_energy_fractions,
    root_constrained_linear_reachability,
)
from scripts.diagnose_self_similar_multigrid_trust_region import (
    apply_leading_panel_objective_weight,
    bounded_root_damped_gauss_newton_step,
    grid_objective_limit_rejection_reason,
    leading_panel_objective_by_grid,
    linearization_panel_counts,
    multigrid_shape_basis,
    multi_constraint_damped_gauss_newton_step,
    maximum_objective_ratio,
    normalized_multigrid_residual,
    resolved_source_jet_bie_panel_count,
    root_constraint_rhs,
    validate_reusable_jacobian_summary,
)
from scripts.reuse_self_similar_multigrid_direction import (
    accepted_trial_mask,
    reconstruct_multigrid_normal_direction,
)


class SelfSimilarLowModeTrustRegionTests(unittest.TestCase):
    def test_candidate_preserves_root_seed_without_inner_iterations(self) -> None:
        source_nodes = np.asarray([[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]])
        coupled = SimpleNamespace(
            config=SimpleNamespace(),
            dipole_coefficient=4.0,
            jet_interface=SimpleNamespace(
                root_state=SimpleNamespace(s_lambda=3.25)
            ),
        )
        candidate = SimpleNamespace(
            outer_free_surface=SimpleNamespace(
                node_xi=source_nodes[:, 0],
                node_eta=source_nodes[:, 1],
            )
        )
        module = "scripts.diagnose_self_similar_low_mode_trust_region"
        with (
            patch(f"{module}._constrain_coupled_outer_nodes", return_value=source_nodes),
            patch(f"{module}._regrid_coupled_outer_nodes", return_value=source_nodes),
            patch(
                f"{module}._build_coupled_solution_from_outer_nodes",
                return_value=candidate,
            ) as build,
        ):
            rebuilt, _, displacement = _build_candidate(
                coupled,
                source_nodes,
                np.zeros(3),
                root_inner_iterations=0,
                matching_surface_policy="fixed_branch",
            )
        self.assertIs(rebuilt, candidate)
        self.assertAlmostEqual(displacement, 0.0)
        self.assertAlmostEqual(build.call_args.kwargs["s_lambda_seed"], 3.25)

    def test_candidate_can_freeze_far_shape_dipole_without_regridding(self) -> None:
        source_nodes = np.asarray([[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]])
        coupled = SimpleNamespace(
            config=SimpleNamespace(),
            dipole_coefficient=4.0,
            jet_interface=SimpleNamespace(
                root_state=SimpleNamespace(s_lambda=3.25)
            ),
        )
        candidate = SimpleNamespace(
            outer_free_surface=SimpleNamespace(
                node_xi=source_nodes[:, 0],
                node_eta=source_nodes[:, 1],
            )
        )
        module = "scripts.diagnose_self_similar_low_mode_trust_region"
        with (
            patch(f"{module}._constrain_coupled_outer_nodes", return_value=source_nodes),
            patch(f"{module}._regrid_coupled_outer_nodes") as regrid,
            patch(
                f"{module}._build_coupled_solution_from_outer_nodes",
                return_value=candidate,
            ) as build,
        ):
            _build_candidate(
                coupled,
                source_nodes,
                np.zeros(3),
                root_inner_iterations=0,
                matching_surface_policy="fixed_branch",
                far_shape_dipole_coefficient=3.5,
                regrid_candidate=False,
            )
        regrid.assert_not_called()
        self.assertAlmostEqual(build.call_args.args[2], 3.5)

    def test_linearization_counts_exclude_validation_only_grids(self) -> None:
        self.assertEqual(
            linearization_panel_counts((320,), (320,), "none"),
            (320,),
        )
        self.assertEqual(
            linearization_panel_counts((320,), (640,), "bounded"),
            (320, 640),
        )
        with self.assertRaisesRegex(ValueError, "objective grid"):
            linearization_panel_counts((), (320,), "none")

    def test_residual_interval_energy_is_independent_of_report_bins(self) -> None:
        midpoint = np.asarray([0.05, 0.15, 0.85, 0.95])
        residual = np.asarray([1.0, 0.0, 2.0, 0.0, 3.0, 0.0, 4.0, 0.0])
        fraction = residual_interval_energy_fraction(
            residual, midpoint, lower=0.90, upper=1.0
        )
        self.assertAlmostEqual(fraction, 16.0 / 30.0)

    def test_root_feasibility_gate_uses_hard_limit_or_monotonic_repair(self) -> None:
        self.assertEqual(root_feasibility_gate_limit(5.0e-4, 1.0e-3), 1.0e-3)
        self.assertEqual(root_feasibility_gate_limit(2.5e-3, 1.0e-3), 2.5e-3)
        with self.assertRaisesRegex(ValueError, "finite and admissible"):
            root_feasibility_gate_limit(-1.0, 1.0e-3)

    def test_dct_basis_is_orthonormal_and_low_ordered(self) -> None:
        basis = dct_nodal_basis(16, 4)
        np.testing.assert_allclose(basis.T @ basis, np.eye(4), atol=1.0e-13)
        self.assertLess(np.ptp(basis[:, 0]), 1.0e-13)

    def test_low_mode_coefficients_recover_constant_weak_residual(self) -> None:
        length = np.ones(4)
        endpoint = np.ones((4, 2)) * 2.0
        coefficients, projected, unresolved = low_mode_residual_coefficients(
            length, endpoint, 2
        )
        self.assertAlmostEqual(coefficients[0], 2.0 * np.sqrt(5.0))
        self.assertAlmostEqual(coefficients[1], 0.0, places=13)
        self.assertAlmostEqual(projected, 16.0)
        self.assertAlmostEqual(unresolved, 0.0)

    def test_root_local_basis_is_arc_weighted_orthonormal(self) -> None:
        length = np.geomspace(0.01, 1.0, 20)
        basis = root_local_nodal_basis(
            length,
            6,
            global_mode_count=2,
            support_fraction=0.2,
        )
        mass = linear_nodal_mass_matrix(length)
        np.testing.assert_allclose(
            basis.T @ mass @ basis,
            np.eye(6),
            atol=2.0e-12,
        )
        arc = np.concatenate(([0.0], np.cumsum(length)))
        arc /= arc[-1]
        root = arc <= 0.25
        root_energy_fraction = np.sum(np.square(basis[root, 2:]), axis=0) / np.sum(
            np.square(basis[:, 2:]), axis=0
        )
        self.assertTrue(np.all(root_energy_fraction > 0.95))

    def test_root_cosine_local_basis_resolves_high_modes_on_nonuniform_grid(self) -> None:
        length = np.geomspace(0.002, 1.0, 80)
        basis = root_cosine_local_nodal_basis(
            length,
            36,
            global_mode_count=2,
            support_fraction=0.10,
        )
        mass = linear_nodal_mass_matrix(length)
        np.testing.assert_allclose(
            basis.T @ mass @ basis,
            np.eye(36),
            rtol=1.0e-9,
            atol=1.0e-9,
        )
        arc = np.concatenate(([0.0], np.cumsum(length)))
        local = basis[:, 2:]
        root_energy = np.sum(np.square(local[arc / arc[-1] <= 0.10]), axis=0)
        total_energy = np.sum(np.square(local), axis=0)
        self.assertTrue(np.all(root_energy / total_energy > 0.90))

    def test_root_cosine_local_basis_rejects_unresolved_mode_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "exceeds the nodes"):
            root_cosine_local_nodal_basis(
                np.ones(20),
                12,
                global_mode_count=2,
                support_fraction=0.10,
            )

    def test_far_local_basis_is_arc_weighted_and_tail_localized(self) -> None:
        length = np.geomspace(1.0, 0.01, 20)
        basis = far_local_nodal_basis(
            length,
            6,
            global_mode_count=2,
            support_fraction=0.2,
        )
        mass = linear_nodal_mass_matrix(length)
        np.testing.assert_allclose(
            basis.T @ mass @ basis,
            np.eye(6),
            atol=2.0e-12,
        )
        arc = np.concatenate(([0.0], np.cumsum(length)))
        arc /= arc[-1]
        tail = arc >= 0.75
        tail_energy_fraction = np.sum(np.square(basis[tail, 2:]), axis=0) / np.sum(
            np.square(basis[:, 2:]), axis=0
        )
        self.assertTrue(np.all(tail_energy_fraction > 0.95))

    def test_dual_endpoint_basis_is_orthonormal_and_localized_at_both_ends(self) -> None:
        length = np.ones(40)
        basis = dual_endpoint_local_nodal_basis(
            length,
            10,
            global_mode_count=2,
            support_fraction=0.2,
        )
        mass = linear_nodal_mass_matrix(length)
        np.testing.assert_allclose(
            basis.T @ mass @ basis,
            np.eye(10),
            atol=2.0e-12,
        )
        root_modes = basis[:, 2:6]
        far_modes = basis[:, 6:]
        root_fraction = np.sum(np.square(root_modes[:10]), axis=0) / np.sum(
            np.square(root_modes), axis=0
        )
        far_fraction = np.sum(np.square(far_modes[-10:]), axis=0) / np.sum(
            np.square(far_modes), axis=0
        )
        self.assertTrue(np.all(root_fraction > 0.90))
        self.assertTrue(np.all(far_fraction > 0.90))

    def test_basis_residual_coefficients_use_arc_metric(self) -> None:
        length = np.ones(4)
        endpoint = np.ones((4, 2)) * 2.0
        basis = root_local_nodal_basis(
            length,
            3,
            global_mode_count=1,
            support_fraction=0.5,
        )
        coefficients, projected, unresolved = basis_residual_coefficients(
            length,
            endpoint,
            basis,
        )
        self.assertAlmostEqual(float(np.dot(coefficients, coefficients)), 16.0)
        self.assertAlmostEqual(projected, 16.0)
        self.assertAlmostEqual(unresolved, 0.0)

    def test_fixed_root_basis_preserves_rank_and_zeroes_leading_nodes(self) -> None:
        length = np.geomspace(0.01, 1.0, 20)
        basis = root_local_nodal_basis(
            length,
            6,
            global_mode_count=2,
            support_fraction=0.2,
        )
        fixed = fix_root_basis_nodes(basis, length, 2)
        mass = linear_nodal_mass_matrix(length)
        np.testing.assert_allclose(fixed[:2], 0.0, atol=1.0e-14)
        np.testing.assert_allclose(
            fixed.T @ mass @ fixed,
            np.eye(6),
            atol=2.0e-12,
        )

    def test_fixed_far_basis_preserves_rank_and_zeroes_trailing_nodes(self) -> None:
        length = np.geomspace(0.01, 1.0, 20)
        basis = dct_nodal_basis(len(length) + 1, 6)
        fixed = fix_far_basis_nodes(basis, length, 2)
        mass = linear_nodal_mass_matrix(length)
        np.testing.assert_allclose(fixed[-2:], 0.0, atol=1.0e-14)
        np.testing.assert_allclose(
            fixed.T @ mass @ fixed,
            np.eye(6),
            atol=2.0e-12,
        )

    def test_exact_endpoint_vector_norm_equals_linear_integral(self) -> None:
        length = np.asarray([2.0, 3.0])
        endpoint = np.asarray([[1.0, 2.0], [-3.0, 4.0]])
        vector = exact_endpoint_residual_vector(length, endpoint)
        expected = np.sum(
            length
            / 3.0
            * (
                np.square(endpoint[:, 0])
                + endpoint[:, 0] * endpoint[:, 1]
                + np.square(endpoint[:, 1])
            )
        )
        self.assertAlmostEqual(float(np.dot(vector, vector)), float(expected))

    def test_damped_gauss_newton_solves_linear_residual(self) -> None:
        jacobian = np.asarray([[2.0, 0.0], [0.0, 4.0]])
        residual = np.asarray([2.0, -8.0])
        step = damped_gauss_newton_step(jacobian, residual, 0.0)
        np.testing.assert_allclose(step, [-1.0, 2.0], atol=1.0e-13)
        damped = damped_gauss_newton_step(jacobian, residual, 1.0)
        self.assertLess(np.linalg.norm(damped), np.linalg.norm(step))

    def test_constrained_gauss_newton_preserves_linear_root_defect(self) -> None:
        jacobian = np.eye(2)
        residual = np.asarray([1.0, 2.0])
        gradient = np.asarray([1.0, 1.0])
        step = constrained_damped_gauss_newton_step(
            jacobian,
            residual,
            0.0,
            gradient,
        )
        self.assertAlmostEqual(float(np.dot(gradient, step)), 0.0, places=13)
        self.assertLess(
            np.linalg.norm(residual + jacobian @ step),
            np.linalg.norm(residual),
        )

    def test_constrained_gauss_newton_closes_linear_root_defect(self) -> None:
        jacobian = np.eye(2)
        residual = np.asarray([1.0, 2.0])
        gradient = np.asarray([1.0, 1.0])
        source_defect = 0.3

        step = constrained_damped_gauss_newton_step(
            jacobian,
            residual,
            0.0,
            gradient,
            -source_defect,
        )

        self.assertAlmostEqual(
            source_defect + float(np.dot(gradient, step)),
            0.0,
            places=13,
        )

    def test_trust_region_scale_limits_midpoint_motion(self) -> None:
        nodes = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        displacement = np.asarray([0.5, 0.5, 0.5])
        scale = trust_region_scale(nodes, displacement, 0.2)
        self.assertAlmostEqual(scale, 0.4)
        self.assertEqual(trust_region_scale(nodes, displacement * 0.1, 0.2), 1.0)

    def test_polyline_curvature_metrics_detect_zigzag_without_scale_bias(self) -> None:
        straight = np.column_stack((np.arange(5, dtype=float), np.zeros(5)))
        zigzag = straight.copy()
        zigzag[1::2, 1] = 0.2
        straight_energy, straight_turn = polyline_curvature_metrics(straight)
        zigzag_energy, zigzag_turn = polyline_curvature_metrics(zigzag)
        scaled_energy, scaled_turn = polyline_curvature_metrics(2.0 * zigzag)
        self.assertAlmostEqual(straight_energy, 0.0)
        self.assertAlmostEqual(straight_turn, 0.0)
        self.assertGreater(zigzag_energy, 0.0)
        self.assertGreater(zigzag_turn, 0.0)
        self.assertAlmostEqual(scaled_energy, 0.5 * zigzag_energy)
        self.assertAlmostEqual(scaled_turn, zigzag_turn)

    def test_one_sided_difference_falls_back_to_negative_perturbation(self) -> None:
        source = np.asarray([1.0, -2.0])

        def residual(step: float) -> np.ndarray:
            if step > 0.0:
                raise ValueError("positive side is outside the physical branch")
            return source + step * np.asarray([3.0, -4.0])

        derivative, signed_step = admissible_one_sided_difference(
            source,
            0.1,
            residual,
        )
        self.assertAlmostEqual(signed_step, -0.1)
        np.testing.assert_allclose(derivative, [3.0, -4.0])

    def test_one_sided_difference_reports_both_inadmissible_sides(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Both signed finite-difference perturbations are inadmissible",
        ):
            admissible_one_sided_difference(
                np.asarray([1.0]),
                0.1,
                lambda step: (_ for _ in ()).throw(ValueError(f"bad {step}")),
            )

    def test_multigrid_residual_has_weighted_relative_norm(self) -> None:
        residual = {
            320: np.asarray([3.0, 4.0]),
            640: np.asarray([0.0, 2.0]),
        }
        source = {320: 25.0, 640: 4.0}
        weights = {320: 1.0, 640: 3.0}
        combined = normalized_multigrid_residual(residual, source, weights)
        self.assertAlmostEqual(float(np.dot(combined, combined)), 1.0)
        candidate = normalized_multigrid_residual(
            {320: 0.5 * residual[320], 640: residual[640]},
            source,
            weights,
        )
        self.assertAlmostEqual(
            float(np.dot(candidate, candidate)),
            0.25 * 0.25 + 0.75,
        )

    def test_leading_panel_weight_scales_each_grid_prefix_only(self) -> None:
        residual = np.arange(1.0, 15.0)
        jacobian = np.arange(28.0).reshape(14, 2)
        weighted_residual, weighted_jacobian = apply_leading_panel_objective_weight(
            residual,
            jacobian,
            (3, 4),
            leading_panel_count=2,
            leading_panel_weight=4.0,
        )
        expected_scale = np.ones(14)
        expected_scale[0:4] = 2.0
        expected_scale[6:10] = 2.0
        np.testing.assert_allclose(weighted_residual, residual * expected_scale)
        np.testing.assert_allclose(
            weighted_jacobian,
            jacobian * expected_scale[:, None],
        )
        np.testing.assert_allclose(residual, np.arange(1.0, 15.0))
        np.testing.assert_allclose(jacobian, np.arange(28.0).reshape(14, 2))

    def test_leading_panel_weight_default_is_no_op_copy(self) -> None:
        residual = np.arange(1.0, 7.0)
        jacobian = np.eye(6)
        weighted_residual, weighted_jacobian = apply_leading_panel_objective_weight(
            residual,
            jacobian,
            (3,),
            leading_panel_count=0,
            leading_panel_weight=1.0,
        )
        np.testing.assert_allclose(weighted_residual, residual)
        np.testing.assert_allclose(weighted_jacobian, jacobian)
        self.assertIsNot(weighted_residual, residual)
        self.assertIsNot(weighted_jacobian, jacobian)

    def test_leading_panel_weight_rejects_invalid_metadata(self) -> None:
        residual = np.ones(6)
        jacobian = np.ones((6, 2))
        with self.assertRaisesRegex(ValueError, "fit every objective grid"):
            apply_leading_panel_objective_weight(residual, jacobian, (3,), 4, 2.0)
        with self.assertRaisesRegex(ValueError, "positive and finite"):
            apply_leading_panel_objective_weight(residual, jacobian, (3,), 2, 0.0)
        with self.assertRaisesRegex(ValueError, "two residual rows per panel"):
            apply_leading_panel_objective_weight(
                np.ones(5), np.ones((5, 2)), (3,), 2, 2.0
            )

    def test_leading_panel_objective_reconstructs_window_energy(self) -> None:
        residuals = {
            3: np.asarray([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            4: np.asarray([2.0, 0.0, 1.0, 2.0, 9.0, 9.0, 9.0, 9.0]),
        }
        source = leading_panel_objective_by_grid(residuals, 2)
        self.assertEqual(source, {3: 30.0, 4: 9.0})
        candidate = {3: 27.0, 4: 9.9}
        self.assertAlmostEqual(maximum_objective_ratio(source, candidate), 1.1)
        with self.assertRaisesRegex(ValueError, "incompatible shapes"):
            leading_panel_objective_by_grid({3: np.ones(5)}, 2)
        with self.assertRaisesRegex(ValueError, "must align"):
            maximum_objective_ratio(source, {3: 27.0})

    def test_multigrid_regrid_preserves_realized_legacy_jet_topology(self) -> None:
        legacy = SimpleNamespace(
            config=SimpleNamespace(coupled_jet_bie_panel_count=None),
            boundary=SimpleNamespace(
                panel_labels=("body", "shallow_jet_body", "shallow_jet_body")
            ),
        )
        self.assertEqual(resolved_source_jet_bie_panel_count(legacy), 2)

        explicit = SimpleNamespace(
            config=SimpleNamespace(coupled_jet_bie_panel_count=256),
            boundary=SimpleNamespace(panel_labels=()),
        )
        self.assertEqual(resolved_source_jet_bie_panel_count(explicit), 256)

        unresolved = SimpleNamespace(
            config=SimpleNamespace(coupled_jet_bie_panel_count=None),
            boundary=SimpleNamespace(panel_labels=("body", "outer_free_surface")),
        )
        with self.assertRaisesRegex(ValueError, "no resolved shallow-jet topology"):
            resolved_source_jet_bie_panel_count(unresolved)

    def test_multiconstraint_gauss_newton_satisfies_two_root_closures(self) -> None:
        jacobian = np.eye(3)
        residual = np.asarray([1.0, -2.0, 3.0])
        constraints = np.asarray([[1.0, 1.0, 0.0], [0.0, 1.0, 1.0]])
        right = np.asarray([-0.2, 0.3])
        step = multi_constraint_damped_gauss_newton_step(
            jacobian,
            residual,
            0.0,
            constraints,
            right,
        )
        np.testing.assert_allclose(constraints @ step, right, atol=1.0e-13)
        self.assertTrue(np.isfinite(step).all())

    def test_reusable_multigrid_root_jacobian_allows_row_subset(self) -> None:
        source = Path("source-checkpoint").resolve()
        summary = {
            "source_checkpoint": str(source),
            "objective_panel_counts": [320, 640],
            "objective_panel_weights": [1.0, 1.0],
            "candidate_root_seed_policy": "inherit_source",
            "root_inner_iterations": 0,
            "matching_surface_policy": "fixed_branch",
            "root_constraint_panel_counts": [320, 640],
            "mode_count": 16,
            "reference_used_during_solve": False,
        }
        self.assertEqual(
            validate_reusable_jacobian_summary(
                summary,
                source_checkpoint=source,
                objective_panel_counts=(320, 640),
                objective_panel_weights=(1.0, 1.0),
                root_constraint_panel_counts=(640,),
                mode_count=32,
            ),
            16,
        )
        validate_reusable_jacobian_summary(
            summary,
            source_checkpoint=source,
            objective_panel_counts=(320, 640),
            objective_panel_weights=(1.0, 1.0),
            root_constraint_panel_counts=(640,),
            mode_count=16,
        )

        legacy_summary = dict(summary)
        legacy_summary.pop("candidate_root_seed_policy")
        with self.assertRaisesRegex(ValueError, "candidate_root_seed_policy"):
            validate_reusable_jacobian_summary(
                legacy_summary,
                source_checkpoint=source,
                objective_panel_counts=(320, 640),
                objective_panel_weights=(1.0, 1.0),
                root_constraint_panel_counts=(640,),
                mode_count=16,
            )

        different_root_mapping = dict(summary)
        different_root_mapping["root_inner_iterations"] = 8
        with self.assertRaisesRegex(ValueError, "root_inner_iterations"):
            validate_reusable_jacobian_summary(
                different_root_mapping,
                source_checkpoint=source,
                objective_panel_counts=(320, 640),
                objective_panel_weights=(1.0, 1.0),
                root_constraint_panel_counts=(640,),
                mode_count=16,
            )

        different_matching_policy = dict(summary)
        different_matching_policy["matching_surface_policy"] = "relocate"
        with self.assertRaisesRegex(ValueError, "matching_surface_policy"):
            validate_reusable_jacobian_summary(
                different_matching_policy,
                source_checkpoint=source,
                objective_panel_counts=(320, 640),
                objective_panel_weights=(1.0, 1.0),
                root_constraint_panel_counts=(640,),
                mode_count=16,
            )

        with self.assertRaisesRegex(ValueError, "lacks requested panel counts"):
            validate_reusable_jacobian_summary(
                summary,
                source_checkpoint=source,
                objective_panel_counts=(320, 640),
                objective_panel_weights=(1.0, 1.0),
                root_constraint_panel_counts=(1280,),
                mode_count=16,
            )
        with self.assertRaisesRegex(ValueError, "incompatible mode prefix"):
            validate_reusable_jacobian_summary(
                summary,
                source_checkpoint=source,
                objective_panel_counts=(320, 640),
                objective_panel_weights=(1.0, 1.0),
                root_constraint_panel_counts=(640,),
                mode_count=8,
            )

    def test_endpoint_local_multigrid_jacobian_rejects_prefix_reuse(self) -> None:
        source = Path("source-checkpoint").resolve()
        summary = {
            "source_checkpoint": str(source),
            "objective_panel_counts": [320, 640],
            "objective_panel_weights": [1.0, 1.0],
            "candidate_root_seed_policy": "inherit_source",
            "root_inner_iterations": 0,
            "matching_surface_policy": "fixed_branch",
            "root_constraint_panel_counts": [640],
            "mode_count": 16,
            "basis": "far_local",
            "global_mode_count": 2,
            "local_support_fraction": 0.15,
            "reference_used_during_solve": False,
        }
        with self.assertRaisesRegex(ValueError, "cannot be reused as mode prefixes"):
            validate_reusable_jacobian_summary(
                summary,
                source_checkpoint=source,
                objective_panel_counts=(320, 640),
                objective_panel_weights=(1.0, 1.0),
                root_constraint_panel_counts=(640,),
                mode_count=32,
                basis="far_local",
                global_mode_count=2,
                local_support_fraction=0.15,
            )

    def test_far_local_multigrid_basis_concentrates_local_modes_at_tail(self) -> None:
        basis = multigrid_shape_basis(
            np.ones(40),
            8,
            basis="far_local",
            global_mode_count=2,
            local_support_fraction=0.2,
        )
        local = basis[:, 2:]
        tail = np.sum(np.square(local[-10:]), axis=0)
        total = np.sum(np.square(local), axis=0)
        self.assertTrue(np.all(tail / total > 0.90))

    def test_dual_endpoint_multigrid_basis_concentrates_modes_at_both_ends(self) -> None:
        basis = multigrid_shape_basis(
            np.ones(40),
            10,
            basis="dual_endpoint_local",
            global_mode_count=2,
            local_support_fraction=0.2,
        )
        root = basis[:, 2:6]
        far = basis[:, 6:]
        self.assertTrue(
            np.all(
                np.sum(np.square(root[:10]), axis=0)
                / np.sum(np.square(root), axis=0)
                > 0.90
            )
        )
        self.assertTrue(
            np.all(
                np.sum(np.square(far[-10:]), axis=0)
                / np.sum(np.square(far), axis=0)
                > 0.90
            )
        )

    def test_endpoint_local_basis_rejects_numerically_singular_normalization(self) -> None:
        with self.assertRaisesRegex(ValueError, "ill-conditioned"):
            far_local_nodal_basis(
                np.geomspace(1.0, 1.0e-3, 320),
                64,
                global_mode_count=2,
                support_fraction=0.2,
            )

    def test_root_constraint_target_uses_signed_defect_increment(self) -> None:
        source = np.asarray([2.0e-4, -3.0e-4])
        target = np.asarray([-9.0e-4, 8.0e-4])
        np.testing.assert_allclose(
            root_constraint_rhs(source, "target", target),
            target - source,
        )
        np.testing.assert_allclose(root_constraint_rhs(source, "preserve"), 0.0)
        np.testing.assert_allclose(root_constraint_rhs(source, "close"), -source)

    def test_bounded_root_step_keeps_unconstrained_feasible_solution(self) -> None:
        jacobian = np.eye(2)
        residual = np.asarray([0.2, -0.3])
        constraints = np.asarray([[1.0, 0.0]])
        step, active, predicted = bounded_root_damped_gauss_newton_step(
            jacobian,
            residual,
            0.0,
            constraints,
            np.asarray([0.0]),
            0.5,
        )
        np.testing.assert_allclose(step, [-0.2, 0.3], atol=1.0e-13)
        self.assertEqual(active, ("free",))
        np.testing.assert_allclose(predicted, [-0.2], atol=1.0e-13)

    def test_bounded_root_step_activates_two_symmetric_limits(self) -> None:
        jacobian = np.eye(2)
        residual = np.asarray([2.0, -3.0])
        constraints = np.eye(2)
        step, active, predicted = bounded_root_damped_gauss_newton_step(
            jacobian,
            residual,
            0.0,
            constraints,
            np.zeros(2),
            0.5,
        )
        np.testing.assert_allclose(step, [-0.5, 0.5], atol=1.0e-13)
        self.assertEqual(active, ("lower", "upper"))
        np.testing.assert_allclose(predicted, [-0.5, 0.5], atol=1.0e-13)

    def test_bounded_root_step_repairs_source_outside_tightened_bound(self) -> None:
        step, active, predicted = bounded_root_damped_gauss_newton_step(
            np.eye(2),
            np.zeros(2),
            0.0,
            np.asarray([[1.0, 0.0]]),
            np.asarray([0.6]),
            0.5,
        )
        np.testing.assert_allclose(step, [-0.1, 0.0], atol=1.0e-13)
        self.assertEqual(active, ("upper",))
        np.testing.assert_allclose(predicted, [0.5], atol=1.0e-13)

    def test_grid_objective_limit_preserves_feasible_and_improves_violation(self) -> None:
        source = {640: 1.02e-3, 1280: 0.92e-3}
        self.assertEqual(
            grid_objective_limit_rejection_reason(
                source,
                {640: 1.01e-3, 1280: 0.99e-3},
                1.0e-3,
            ),
            "",
        )
        self.assertEqual(
            grid_objective_limit_rejection_reason(
                source,
                {640: 1.021e-3, 1280: 0.92e-3},
                1.0e-3,
            ),
            "violating_grid_not_improved",
        )
        self.assertEqual(
            grid_objective_limit_rejection_reason(
                source,
                {640: 1.01e-3, 1280: 1.001e-3},
                1.0e-3,
            ),
            "feasible_grid_left_objective_limit",
        )

    def test_multigrid_direction_reconstruction_applies_bounded_root_step(self) -> None:
        jacobian = np.eye(3)
        residual = np.asarray([2.0, -3.0, 0.25])
        basis = np.eye(3)
        source_nodes = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        direction = reconstruct_multigrid_normal_direction(
            jacobian,
            residual,
            basis,
            source_nodes,
            damping=0.0,
            trust_radius=10.0,
            trust_radius_safety_factor=1.0,
            root_constraint="bounded",
            constraint_jacobian=np.asarray([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            source_root_defect=np.zeros(2),
            root_bound=0.5,
        )
        np.testing.assert_allclose(direction, [-0.5, 0.5, -0.25], atol=1.0e-13)

    def test_persisted_trial_acceptance_parses_boolean_strings_strictly(self) -> None:
        mask = accepted_trial_mask(
            pd.Series([True, False, "true", "FALSE", None], dtype="object")
        )
        self.assertEqual(mask.tolist(), [True, False, True, False, False])
        with self.assertRaisesRegex(ValueError, "invalid values"):
            accepted_trial_mask(pd.Series(["yes"], dtype="object"))

    def test_root_constrained_reachability_stays_in_constraint_nullspace(self) -> None:
        metrics = root_constrained_linear_reachability(
            np.eye(3),
            np.asarray([1.0, 2.0, 3.0]),
            np.asarray([[1.0, 0.0, 0.0]]),
            np.eye(3),
            np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]),
            np.asarray([[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]),
            trust_radius=10.0,
        )
        self.assertEqual(metrics["root_rank"], 1)
        self.assertEqual(metrics["nullspace_dimension"], 2)
        self.assertAlmostEqual(metrics["maximum_absolute_root_increment"], 0.0)
        self.assertAlmostEqual(metrics["linear_floor_objective_ratio"], 1.0 / 14.0)

    def test_residual_segment_energy_uses_exact_vector_pairs(self) -> None:
        fractions = residual_segment_energy_fractions(
            np.asarray([1.0, 0.0, 0.0, 2.0]),
            np.asarray([0.25, 0.75]),
            np.asarray([0.0, 0.5, 1.0]),
        )
        np.testing.assert_allclose(fractions, [0.2, 0.8], atol=1.0e-13)


if __name__ == "__main__":
    unittest.main()
