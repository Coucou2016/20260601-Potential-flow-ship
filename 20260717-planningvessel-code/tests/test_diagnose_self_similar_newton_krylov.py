from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from scripts.diagnose_self_similar_newton_krylov import (
    MAPPING_VERSION,
    _parser,
    apply_source_aligned_exact_sketch,
    build_candidate_map,
    formal_outer_state,
    exact_krylov_subspace_gauss_newton_step,
    endpoint_block_residual,
    _basis,
    free_nodal_arc_basis,
    geometric_right_preconditioner_scale,
    matrix_free_directional_product,
    newton_krylov_transformation,
    rebase_candidate_map_source,
    solve_matrix_free_newton_step,
    source_aligned_householder_vector,
)
from scripts.diagnose_self_similar_low_mode_line_search import (
    maximum_midpoint_displacement_ratio,
)


class MatrixFreeDirectionalProductTests(unittest.TestCase):
    def setUp(self) -> None:
        self.nodes = np.column_stack((np.arange(4, dtype=float), np.zeros(4)))
        self.basis = np.eye(4)
        self.base = np.asarray([0.3, -0.2, 0.1, 0.4])
        self.matrix = np.asarray(
            [
                [2.0, -0.5, 0.0, 0.2],
                [0.1, 1.5, -0.3, 0.0],
                [0.0, 0.4, 1.2, -0.2],
                [-0.1, 0.0, 0.3, 0.8],
            ]
        )

    def test_affine_directional_product_preserves_direction_scale(self) -> None:
        direction = np.asarray([0.4, -0.2, 0.3, 0.1])

        def evaluate(displacement: np.ndarray) -> np.ndarray:
            return self.base + self.matrix @ displacement

        product, record = matrix_free_directional_product(
            self.base,
            direction,
            self.basis,
            self.nodes,
            1.0e-3,
            evaluate,
        )
        doubled, _ = matrix_free_directional_product(
            self.base,
            2.0 * direction,
            self.basis,
            self.nodes,
            1.0e-3,
            evaluate,
        )
        np.testing.assert_allclose(product, self.matrix @ direction, rtol=1e-11)
        np.testing.assert_allclose(doubled, 2.0 * product, rtol=1e-11)
        self.assertGreater(record.signed_finite_difference_step, 0.0)
        unit_direction = direction / np.linalg.norm(direction)
        expected_midpoint_ratio = np.max(
            np.abs(0.5 * (unit_direction[:-1] + unit_direction[1:]))
        )
        self.assertAlmostEqual(
            record.maximum_unit_displacement_ratio,
            expected_midpoint_ratio,
        )

    def test_rebase_synchronizes_shape_dipole_outside_candidate_derivative(self) -> None:
        nodes = np.asarray([[1.0, 0.2], [2.0, 0.1], [3.0, 0.0]])
        coupled = SimpleNamespace(
            dipole_coefficient=4.2,
            outer_free_surface=SimpleNamespace(
                node_xi=nodes[:, 0],
                node_eta=nodes[:, 1],
            ),
        )
        rebased = SimpleNamespace()
        source_state = SimpleNamespace(
            exact_objective=2.0,
            root_relative_mismatch=2.0e-5,
            condition_number=10.0,
        )
        rebased_state = SimpleNamespace(
            exact_objective=1.5,
            root_relative_mismatch=3.0e-6,
            condition_number=11.0,
        )
        module = "scripts.diagnose_self_similar_newton_krylov"
        with (
            patch(
                f"{module}.formal_outer_state",
                side_effect=(source_state, rebased_state),
            ),
            patch(
                f"{module}._build_candidate",
                return_value=(rebased, nodes, 0.002),
            ) as build,
        ):
            result, coefficient, record = rebase_candidate_map_source(
                coupled,
                source_shape_dipole_coefficient=4.0,
                root_inner_iterations=8,
                matching_surface_policy="relocate",
                outer_iteration=2,
                phase="pre_linearization",
            )
        self.assertIs(result, rebased)
        self.assertAlmostEqual(coefficient, 4.2)
        np.testing.assert_array_equal(build.call_args.args[2], np.zeros(3))
        self.assertAlmostEqual(
            build.call_args.kwargs["far_shape_dipole_coefficient"], 4.2
        )
        self.assertTrue(build.call_args.kwargs["regrid_candidate"])
        self.assertAlmostEqual(record.formal_exact_relative_change, -0.25)

    def test_default_candidate_map_keeps_frozen_rebased_source_behavior(self) -> None:
        source_nodes = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        normal_displacement = np.asarray([0.0, 0.1, 0.0])
        source = SimpleNamespace()
        candidate = SimpleNamespace()
        candidate_nodes = np.asarray([[0.0, 0.0], [1.0, 0.1], [2.0, 0.0]])
        module = "scripts.diagnose_self_similar_newton_krylov"
        with patch(
            f"{module}._build_candidate",
            return_value=(candidate, candidate_nodes, 0.05),
        ) as build:
            result, nodes, displacement = build_candidate_map(
                source,
                source_nodes,
                normal_displacement,
                root_inner_iterations=8,
                matching_surface_policy="relocate",
                far_shape_dipole_coefficient=4.0,
            )
        self.assertIs(result, candidate)
        np.testing.assert_array_equal(nodes, candidate_nodes)
        self.assertAlmostEqual(displacement, 0.05)
        self.assertEqual(build.call_count, 1)
        self.assertIs(build.call_args.args[0], source)
        np.testing.assert_array_equal(build.call_args.args[1], source_nodes)
        np.testing.assert_array_equal(
            build.call_args.args[2], normal_displacement
        )
        self.assertEqual(build.call_args.kwargs["far_shape_dipole_coefficient"], 4.0)
        self.assertFalse(build.call_args.kwargs["regrid_candidate"])

    def test_synchronized_candidate_uses_solved_dipole_and_final_geometry(self) -> None:
        source_nodes = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        raw_candidate = SimpleNamespace(dipole_coefficient=4.5)
        synchronized_candidate = SimpleNamespace()
        raw_nodes = source_nodes.copy()
        synchronized_nodes = np.asarray(
            [[0.0, 0.0], [1.0, 0.2], [2.0, 0.0]]
        )
        module = "scripts.diagnose_self_similar_newton_krylov"
        with patch(
            f"{module}._build_candidate",
            side_effect=(
                (raw_candidate, raw_nodes, 0.0),
                (synchronized_candidate, synchronized_nodes, 0.0),
            ),
        ) as build:
            result, nodes, displacement = build_candidate_map(
                SimpleNamespace(),
                source_nodes,
                np.zeros(len(source_nodes)),
                root_inner_iterations=8,
                matching_surface_policy="relocate",
                far_shape_dipole_coefficient=4.0,
                candidate_map_policy="synchronize_candidate",
            )
        self.assertIs(result, synchronized_candidate)
        np.testing.assert_array_equal(nodes, synchronized_nodes)
        self.assertEqual(build.call_count, 2)
        first, second = build.call_args_list
        self.assertFalse(first.kwargs["regrid_candidate"])
        self.assertEqual(first.kwargs["far_shape_dipole_coefficient"], 4.0)
        self.assertIs(second.args[0], raw_candidate)
        np.testing.assert_array_equal(second.args[1], raw_nodes)
        np.testing.assert_array_equal(second.args[2], np.zeros(len(raw_nodes)))
        self.assertTrue(second.kwargs["regrid_candidate"])
        self.assertEqual(second.kwargs["far_shape_dipole_coefficient"], 4.5)
        self.assertAlmostEqual(
            displacement,
            maximum_midpoint_displacement_ratio(source_nodes, synchronized_nodes),
        )
        self.assertGreater(displacement, 0.0)

    def test_negative_fallback_retains_signed_derivative(self) -> None:
        direction = np.asarray([1.0, 0.2, 0.1, 0.0])

        def evaluate(displacement: np.ndarray) -> np.ndarray:
            if displacement[0] > 0.0:
                raise ValueError("positive branch is deliberately unavailable")
            return self.base + self.matrix @ displacement

        product, record = matrix_free_directional_product(
            self.base,
            direction,
            self.basis,
            self.nodes,
            1.0e-3,
            evaluate,
        )
        np.testing.assert_allclose(product, self.matrix @ direction, rtol=1e-11)
        self.assertLess(record.signed_finite_difference_step, 0.0)

    def test_zero_direction_does_not_evaluate_nonlinear_map(self) -> None:
        calls = 0

        def evaluate(displacement: np.ndarray) -> np.ndarray:
            nonlocal calls
            calls += 1
            return self.base + displacement

        product, record = matrix_free_directional_product(
            self.base,
            np.zeros(4),
            self.basis,
            self.nodes,
            1.0e-3,
            evaluate,
        )
        np.testing.assert_array_equal(product, np.zeros(4))
        self.assertEqual(calls, 0)
        self.assertEqual(record.signed_finite_difference_step, 0.0)


class MatrixFreeNewtonSolveTests(unittest.TestCase):
    def test_exact_krylov_subspace_minimizes_rectangular_endpoint_residual(self) -> None:
        jacobian = np.asarray(
            [[2.0, 0.0], [0.0, 3.0], [1.0, -1.0], [0.5, 0.25]]
        )
        residual = np.asarray([1.0, -2.0, 0.5, 0.25])
        directions = [np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0])]
        products = [jacobian @ item for item in directions]
        step, product, rank, condition = exact_krylov_subspace_gauss_newton_step(
            residual,
            directions,
            products,
            damping=0.0,
        )
        expected, _, _, _ = np.linalg.lstsq(jacobian, -residual, rcond=None)
        np.testing.assert_allclose(step, expected, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(product, jacobian @ expected, rtol=1e-12)
        self.assertEqual(rank, 2)
        self.assertTrue(np.isfinite(condition))

    def test_gmres_solves_declared_damped_newton_system(self) -> None:
        matrix = np.asarray(
            [[3.0, 0.5, 0.0], [0.2, 2.5, -0.1], [0.0, 0.3, 1.8]]
        )
        residual = np.asarray([1.0, -0.5, 0.25])
        damping = 0.04
        step, info, history = solve_matrix_free_newton_step(
            residual,
            lambda vector: matrix @ vector,
            damping=damping,
            relative_tolerance=1.0e-12,
            maximum_iterations=3,
        )
        expected = np.linalg.solve(matrix + damping * np.eye(3), -residual)
        np.testing.assert_allclose(step, expected, rtol=1e-11, atol=1e-12)
        self.assertEqual(info, 0)
        self.assertGreaterEqual(len(history), 1)

    def test_right_preconditioner_returns_physical_newton_step(self) -> None:
        matrix = np.diag([1.0, 10.0, 100.0])
        residual = np.asarray([1.0, 1.0, 1.0])
        scale = np.asarray([1.0, 0.1, 0.01])
        step, info, _ = solve_matrix_free_newton_step(
            residual,
            lambda vector: matrix @ vector,
            damping=0.0,
            relative_tolerance=1.0e-12,
            maximum_iterations=3,
            right_preconditioner_scale=scale,
        )
        np.testing.assert_allclose(step, -1.0 / np.diag(matrix), rtol=1e-12)
        self.assertEqual(info, 0)

    def test_rejects_iteration_count_above_reduced_dimension(self) -> None:
        with self.assertRaisesRegex(ValueError, "system size"):
            solve_matrix_free_newton_step(
                np.ones(2),
                lambda vector: vector,
                damping=0.0,
                relative_tolerance=1.0e-3,
                maximum_iterations=3,
            )


class FormalObjectiveAndMetadataTests(unittest.TestCase):
    def test_parser_defaults_to_frozen_rebased_candidate_map(self) -> None:
        args = _parser().parse_args(
            ("--checkpoint", "source", "--out", "diagnostic")
        )
        self.assertEqual(args.candidate_map_policy, "freeze_rebased_source")

    def test_full_endpoint_block_recovers_exact_integral(self) -> None:
        length = np.asarray([0.5, 1.25, 2.0])
        endpoint = np.asarray([[1.0, -0.5], [0.2, 0.7], [-1.0, 2.0]])
        block = endpoint_block_residual(
            length,
            endpoint,
            average_mode_count=3,
            jump_mode_count=3,
        )
        expected = np.sum(
            length
            * (
                endpoint[:, 0] ** 2
                + endpoint[:, 0] * endpoint[:, 1]
                + endpoint[:, 1] ** 2
            )
            / 3.0
        )
        self.assertAlmostEqual(float(np.dot(block, block)), expected)

    def test_endpoint_block_keeps_declared_low_jump_modes(self) -> None:
        panel_count = 16
        length = np.ones(panel_count)
        jump_coefficients = np.zeros(panel_count)
        jump_coefficients[3] = 2.0
        from scipy.fft import idct

        jump = idct(jump_coefficients, type=2, norm="ortho")
        endpoint = np.column_stack((np.sqrt(3.0) * jump, -np.sqrt(3.0) * jump))
        block = endpoint_block_residual(
            length,
            endpoint,
            average_mode_count=8,
            jump_mode_count=4,
        )
        np.testing.assert_allclose(block[:8], np.zeros(8), atol=1e-12)
        np.testing.assert_allclose(block[8:], jump_coefficients[:4], atol=1e-12)

    def test_source_aligned_sketch_preserves_source_exact_norm(self) -> None:
        source = np.asarray([0.2, -0.8, 1.1, 0.4, -0.3, 0.7])
        vector = source_aligned_householder_vector(source, reduced_size=4)
        reduced = apply_source_aligned_exact_sketch(
            source,
            vector,
            reduced_size=4,
        )
        self.assertAlmostEqual(float(np.dot(reduced, reduced)), float(np.dot(source, source)))
        np.testing.assert_allclose(reduced[1:], np.zeros(3), atol=1e-14)

    def test_source_aligned_sketch_is_linear_and_contracting(self) -> None:
        source = np.asarray([0.2, -0.8, 1.1, 0.4, -0.3, 0.7])
        first = np.asarray([-0.1, 0.5, 0.6, -0.2, 0.8, 0.3])
        second = np.asarray([0.7, -0.4, 0.1, 0.9, -0.2, 0.6])
        vector = source_aligned_householder_vector(source, reduced_size=4)
        transform = lambda value: apply_source_aligned_exact_sketch(
            value,
            vector,
            reduced_size=4,
        )
        np.testing.assert_allclose(
            transform(2.0 * first - 0.5 * second),
            2.0 * transform(first) - 0.5 * transform(second),
            atol=1e-14,
        )
        self.assertLessEqual(np.linalg.norm(transform(first)), np.linalg.norm(first))

    def test_source_aligned_sketch_rejects_zero_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-zero"):
            source_aligned_householder_vector(np.zeros(6), reduced_size=4)

    def test_full_nodal_basis_spans_all_unfixed_nodes_in_arc_metric(self) -> None:
        length = np.asarray([0.5, 1.0, 1.5, 2.0])
        basis = free_nodal_arc_basis(
            length,
            fixed_root_node_count=1,
            fixed_far_node_count=1,
        )
        from scripts.diagnose_self_similar_low_mode_trust_region import (
            linear_nodal_mass_matrix,
        )

        mass = linear_nodal_mass_matrix(length)
        self.assertEqual(basis.shape, (5, 3))
        np.testing.assert_array_equal(basis[0], np.zeros(3))
        np.testing.assert_array_equal(basis[-1], np.zeros(3))
        np.testing.assert_allclose(basis.T @ mass @ basis, np.eye(3), atol=1e-12)

    def test_global_dct_basis_is_arc_orthonormal_and_fixes_far_nodes(self) -> None:
        length = np.asarray([0.5, 1.0, 1.5, 2.0, 2.5])
        basis = _basis(
            "global_dct",
            length,
            mode_count=4,
            global_mode_count=1,
            support_fraction=0.3,
            fixed_root_node_count=0,
            fixed_far_node_count=2,
        )
        from scripts.diagnose_self_similar_low_mode_trust_region import (
            linear_nodal_mass_matrix,
        )

        mass = linear_nodal_mass_matrix(length)
        self.assertEqual(basis.shape, (6, 4))
        np.testing.assert_array_equal(basis[-2:], np.zeros((2, 4)))
        np.testing.assert_allclose(basis.T @ mass @ basis, np.eye(4), atol=1e-12)

    def test_geometric_preconditioner_equalizes_column_motion(self) -> None:
        nodes = np.column_stack((np.arange(4, dtype=float), np.zeros(4)))
        basis = np.diag([1.0, 2.0, 4.0, 8.0])
        scale, ratios = geometric_right_preconditioner_scale(basis, nodes)
        self.assertTrue(np.all(ratios > 0.0))
        median = np.median(ratios)
        np.testing.assert_allclose(scale * ratios, np.full(4, median))

    def test_formal_state_uses_piecewise_linear_exact_integral(self) -> None:
        endpoint = np.asarray([[1.0, 2.0], [2.0, -1.0]])
        coupled = SimpleNamespace(
            outer_kinematic_residual_endpoint=endpoint,
            boundary=SimpleNamespace(
                panel_labels=np.asarray(
                    ["body", "outer_free_surface", "outer_free_surface"],
                    dtype=object,
                ),
                panel_length_m=np.asarray([5.0, 3.0, 6.0]),
            ),
            jet_interface=SimpleNamespace(
                root_state=SimpleNamespace(s_lambda=4.0)
            ),
            solution=SimpleNamespace(condition_number=123.0),
            dipole_coefficient=2.5,
        )
        measured = SimpleNamespace(s_lambda=4.004)
        with patch(
            "scripts.diagnose_self_similar_newton_krylov."
            "derive_shallow_water_jet_root_state_from_coupled",
            return_value=measured,
        ):
            state = formal_outer_state(coupled)
        expected = 3.0 * (1.0 + 2.0 + 4.0) / 3.0
        expected += 6.0 * (4.0 - 2.0 + 1.0) / 3.0
        self.assertAlmostEqual(state.exact_objective, expected)
        self.assertAlmostEqual(state.root_relative_mismatch, 1.0e-3)

    def test_transformation_freezes_joint_root_mapping_and_reference_isolation(self) -> None:
        metadata = newton_krylov_transformation(
            basis_name="root_local",
            mode_count=64,
            global_mode_count=4,
            support_fraction=0.30,
            fixed_root_node_count=0,
            fixed_far_node_count=2,
            root_inner_iterations=8,
            matching_surface_policy="relocate",
            finite_difference_ratio=1.0e-3,
            damping=1.0e-3,
            krylov_relative_tolerance=1.0e-2,
            krylov_maximum_iterations=16,
            right_preconditioner="geometric_midpoint",
            outer_shape_dipole_coefficient=3.25,
            direction_solver="exact_krylov_subspace",
            residual_generator="endpoint_block",
            jump_mode_count=32,
        )
        self.assertEqual(metadata["mapping_version"], MAPPING_VERSION)
        self.assertEqual(metadata["candidate_map_policy"], "freeze_rebased_source")
        self.assertEqual(metadata["root_inner_iterations"], 8)
        self.assertEqual(metadata["matching_surface_policy"], "relocate")
        self.assertEqual(metadata["candidate_root_seed_policy"], "inherit_source")
        self.assertFalse(metadata["reference_used_during_solve"])
        self.assertEqual(metadata["right_preconditioner"], "geometric_midpoint")
        self.assertEqual(metadata["outer_shape_dipole_coefficient"], 3.25)
        self.assertEqual(metadata["direction_solver"], "exact_krylov_subspace")
        self.assertEqual(metadata["residual_generator"], "endpoint_block")
        self.assertEqual(metadata["average_mode_count"], 32)
        self.assertEqual(metadata["jump_mode_count"], 32)
        self.assertEqual(
            metadata["acceptance_objective"],
            "unweighted_piecewise_linear_exact_integral",
        )
        self.assertEqual(
            metadata["candidate_map_far_shape_dipole_policy"],
            "freeze_rebased_source",
        )
        self.assertEqual(
            metadata["candidate_map_regrid_policy"],
            "frozen_nodes_during_linearization",
        )
        self.assertEqual(
            metadata["candidate_map_source_residual_policy"],
            "rebased_source_is_F0",
        )

    def test_transformation_records_synchronized_candidate_map(self) -> None:
        metadata = newton_krylov_transformation(
            basis_name="root_local",
            mode_count=64,
            global_mode_count=4,
            support_fraction=0.30,
            fixed_root_node_count=0,
            fixed_far_node_count=2,
            root_inner_iterations=8,
            matching_surface_policy="relocate",
            finite_difference_ratio=1.0e-3,
            damping=1.0e-3,
            krylov_relative_tolerance=1.0e-2,
            krylov_maximum_iterations=16,
            right_preconditioner="geometric_midpoint",
            outer_shape_dipole_coefficient=3.25,
            direction_solver="exact_krylov_subspace",
            residual_generator="endpoint_block",
            jump_mode_count=32,
            candidate_map_policy="synchronize_candidate",
        )
        self.assertEqual(metadata["candidate_map_policy"], "synchronize_candidate")
        self.assertEqual(
            metadata["candidate_map_far_shape_dipole_policy"],
            "synchronize_candidate_solved_dipole",
        )
        self.assertEqual(
            metadata["candidate_map_regrid_policy"],
            "canonical_regrid_after_candidate_dipole_sync",
        )
        self.assertEqual(
            metadata["candidate_map_source_residual_policy"],
            "evaluate_synchronized_candidate_map_at_zero_displacement",
        )


if __name__ == "__main__":
    unittest.main()
