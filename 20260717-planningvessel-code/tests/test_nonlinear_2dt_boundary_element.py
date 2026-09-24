from __future__ import annotations

import unittest

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.boundary_element import (
    ClosedBoundary2D,
    _linear_panel_endpoint_influence_arrays,
    boundary_velocity,
    boundary_node_velocity,
    constant_panel_influence_matrices,
    linear_element_influence_rows,
    solve_linear_node_mixed_boundary_laplace,
    solve_linear_element_mixed_boundary_laplace,
    solve_pressure_auxiliary_bvp,
    solve_section_potential_bvp,
    solve_mixed_boundary_laplace,
)
from planing_seakeeping.kernels.nonlinear_2dt.section_geometry import (
    build_symmetric_wedge_fluid_boundary,
)


def _circle(panel_count: int) -> ClosedBoundary2D:
    theta = np.linspace(0.0, 2.0 * np.pi, panel_count + 1)
    return ClosedBoundary2D(
        node_y_m=np.cos(theta),
        node_z_up_m=np.sin(theta),
        panel_labels=tuple("dirichlet" if index % 3 == 0 else "neumann" for index in range(panel_count)),
    )


def _rectangular_fluid_domain(panel_count_per_side: int = 24) -> ClosedBoundary2D:
    n = int(panel_count_per_side)
    top_y = np.linspace(-1.0, 1.0, 2 * n + 1)
    right_z = np.linspace(0.0, -1.0, n + 1)[1:]
    bottom_y = np.linspace(1.0, -1.0, 2 * n + 1)[1:]
    left_z = np.linspace(-1.0, 0.0, n + 1)[1:]
    y = np.concatenate((top_y, np.ones(n), bottom_y, -np.ones(n)))
    z = np.concatenate((np.zeros(2 * n + 1), right_z, -np.ones(2 * n), left_z))
    labels = (
        ("free_surface",) * (2 * n)
        + ("wall",) * n
        + ("body",) * (2 * n)
        + ("wall",) * n
    )
    return ClosedBoundary2D(node_y_m=y, node_z_up_m=z, panel_labels=labels)


class Nonlinear2DtBoundaryElementTests(unittest.TestCase):
    def test_displaced_linear_rows_preserve_constant_potential_identity(self) -> None:
        boundary = _circle(32)
        panels = np.asarray([0, 7, 19], dtype=int)
        fractions = np.asarray([1.0 / 3.0, 0.5, 2.0 / 3.0])
        field_y = (
            (1.0 - fractions) * boundary.node_y_m[panels]
            + fractions * boundary.node_y_m[panels + 1]
        )
        field_z = (
            (1.0 - fractions) * boundary.node_z_up_m[panels]
            + fractions * boundary.node_z_up_m[panels + 1]
        )

        h_matrix, g_left, g_right = linear_element_influence_rows(
            boundary,
            field_y_m=field_y,
            field_z_up_m=field_z,
            field_panel_index=panels,
            field_panel_fraction=fractions,
            gauss_order=12,
        )

        self.assertEqual(h_matrix.shape, (3, boundary.panel_count))
        np.testing.assert_allclose(h_matrix @ np.ones(boundary.panel_count), 0.0, atol=1e-13)
        self.assertTrue(np.isfinite(g_left).all())
        self.assertTrue(np.isfinite(g_right).all())

    def test_displaced_double_nodes_recover_manufactured_corner_fluxes(self) -> None:
        boundary = ClosedBoundary2D(
            node_y_m=np.asarray([-1.0, 1.0, 1.0, -1.0, -1.0]),
            node_z_up_m=np.asarray([1.0, 1.0, -1.0, -1.0, 1.0]),
            panel_labels=("top", "right", "bottom", "left"),
        )
        panel_index = np.repeat(np.arange(boundary.panel_count), 2)
        fraction = np.tile(np.asarray([1.0 / 3.0, 2.0 / 3.0]), boundary.panel_count)
        field_y = (
            (1.0 - fraction) * boundary.node_y_m[panel_index]
            + fraction * boundary.node_y_m[panel_index + 1]
        )
        field_z = (
            (1.0 - fraction) * boundary.node_z_up_m[panel_index]
            + fraction * boundary.node_z_up_m[panel_index + 1]
        )
        h_matrix, g_left, g_right = linear_element_influence_rows(
            boundary,
            field_y_m=field_y,
            field_z_up_m=field_z,
            field_panel_index=panel_index,
            field_panel_fraction=fraction,
        )
        system = np.zeros((2 * boundary.panel_count, 2 * boundary.panel_count))
        for panel in range(boundary.panel_count):
            system[:, 2 * panel] = -g_left[:, panel]
            system[:, 2 * panel + 1] = -g_right[:, panel]

        for potential, gradient in (
            (boundary.node_y_m[:-1], np.asarray([1.0, 0.0])),
            (boundary.node_z_up_m[:-1], np.asarray([0.0, 1.0])),
        ):
            endpoint_q = np.linalg.solve(system, -h_matrix @ potential)
            exact_q = np.repeat(boundary.panel_normal @ gradient, 2)
            np.testing.assert_allclose(endpoint_q, exact_q, atol=2.0e-14)

        right_corner = np.asarray([endpoint_q[1], endpoint_q[2]])
        np.testing.assert_allclose(right_corner, [1.0, 0.0], atol=2.0e-14)

    def test_constant_panel_analytic_kernel_resolves_thin_parallel_panels(self) -> None:
        separation = 1.0e-6
        boundary = ClosedBoundary2D(
            node_y_m=np.asarray([0.0, 1.0, 1.0, 0.0, 0.0]),
            node_z_up_m=np.asarray([0.0, 0.0, -separation, -separation, 0.0]),
            panel_labels=("top", "right", "bottom", "left"),
        )

        h_matrix, g_matrix = constant_panel_influence_matrices(boundary)
        expected_opposite_normal = 2.0 * np.arctan(0.5 / separation)

        self.assertAlmostEqual(
            h_matrix[0, 2],
            expected_opposite_normal,
            places=12,
        )
        self.assertAlmostEqual(h_matrix[2, 0], expected_opposite_normal, places=12)
        self.assertAlmostEqual(h_matrix[0, 0], -np.pi, places=14)
        self.assertTrue(np.isfinite(g_matrix).all())

    def test_linear_element_analytic_kernel_resolves_thin_parallel_panels(self) -> None:
        separation = 1.0e-6
        boundary = ClosedBoundary2D(
            node_y_m=np.asarray([0.5, 1.0, 1.0, 0.0, 0.0, 0.5]),
            node_z_up_m=np.asarray([0.0, 0.0, -separation, -separation, 0.0, 0.0]),
            panel_labels=("top_right", "right", "bottom", "left", "top_left"),
        )

        h_left, h_right, g_left, g_right = (
            _linear_panel_endpoint_influence_arrays(boundary, gauss_order=4)
        )
        expected_endpoint_normal = np.arctan(0.5 / separation)

        self.assertAlmostEqual(h_left[0, 2], expected_endpoint_normal, places=12)
        self.assertAlmostEqual(h_right[0, 2], expected_endpoint_normal, places=12)
        self.assertAlmostEqual(g_left[0, 2], g_right[0, 2], places=12)
        self.assertTrue(np.isfinite(g_left).all())
        self.assertTrue(np.isfinite(g_right).all())

    def test_linear_element_mixed_boundary_preserves_corner_normal_discontinuity(self) -> None:
        boundary = _circle(96)
        y = boundary.node_y_m[:-1]
        z = boundary.node_z_up_m[:-1]
        exact_phi = y**2 - z**2
        gradient = np.column_stack((2.0 * y, -2.0 * z))
        panel_mask = np.zeros(boundary.panel_count, dtype=bool)
        panel_mask[:32] = True
        q_endpoints = np.zeros((boundary.panel_count, 2), dtype=float)
        for panel in range(boundary.panel_count):
            q_endpoints[panel, 0] = np.dot(gradient[panel], boundary.panel_normal[panel])
            q_endpoints[panel, 1] = np.dot(
                gradient[(panel + 1) % boundary.panel_count],
                boundary.panel_normal[panel],
            )
        solution = solve_linear_element_mixed_boundary_laplace(
            boundary,
            dirichlet_panel_mask=panel_mask,
            dirichlet_node_values=exact_phi,
            neumann_endpoint_values=q_endpoints,
            gauss_order=16,
        )
        relative_phi = np.linalg.norm(solution.potential_m2_s - exact_phi) / np.linalg.norm(exact_phi)

        self.assertLess(relative_phi, 0.015)
        self.assertLess(solution.relative_residual, 1e-11)

    def test_linear_nodal_mixed_boundary_recovers_quadratic_harmonic_potential(self) -> None:
        boundary = _circle(96)
        y = boundary.node_y_m[:-1]
        z = boundary.node_z_up_m[:-1]
        normal = boundary.node_normal
        exact_phi = y**2 - z**2
        exact_gradient = np.column_stack((2.0 * y, -2.0 * z))
        exact_q = np.sum(exact_gradient * normal, axis=1)
        mask = np.asarray([index % 3 == 0 for index in range(boundary.panel_count)])
        solution = solve_linear_node_mixed_boundary_laplace(
            boundary,
            dirichlet_mask=mask,
            known_value=np.where(mask, exact_phi, exact_q),
            gauss_order=16,
        )
        phi_error = np.linalg.norm(solution.potential_m2_s - exact_phi) / np.linalg.norm(exact_phi)
        q_error = np.linalg.norm(solution.normal_derivative_m_s - exact_q) / np.linalg.norm(exact_q)

        self.assertLess(phi_error, 0.01)
        self.assertLess(q_error, 0.02)
        self.assertLess(solution.relative_residual, 1e-11)

    def test_linear_nodal_velocity_recovers_uniform_harmonic_field(self) -> None:
        boundary = _circle(128)
        y = boundary.node_y_m[:-1]
        exact_gradient = np.column_stack((np.ones_like(y), np.zeros_like(y)))
        exact_phi = y
        exact_q = np.sum(exact_gradient * boundary.node_normal, axis=1)
        mask = np.asarray([index % 3 == 0 for index in range(boundary.panel_count)])
        solution = solve_linear_node_mixed_boundary_laplace(
            boundary,
            dirichlet_mask=mask,
            known_value=np.where(mask, exact_phi, exact_q),
            gauss_order=16,
        )
        velocity = boundary_node_velocity(boundary, solution)
        relative = np.linalg.norm(velocity - exact_gradient) / np.linalg.norm(exact_gradient)

        self.assertLess(relative, 0.02)

    def test_mixed_boundary_recovers_quadratic_harmonic_potential(self) -> None:
        boundary = _circle(160)
        y = boundary.panel_mid_y_m
        z = boundary.panel_mid_z_up_m
        normal = boundary.panel_normal
        exact_phi = y**2 - z**2
        exact_gradient = np.column_stack((2.0 * y, -2.0 * z))
        exact_q = np.sum(exact_gradient * normal, axis=1)
        mask = np.asarray([label == "dirichlet" for label in boundary.panel_labels])
        known = np.where(mask, exact_phi, exact_q)
        solution = solve_mixed_boundary_laplace(
            boundary,
            dirichlet_mask=mask,
            known_value=known,
            gauss_order=16,
        )
        phi_error = np.linalg.norm(solution.potential_m2_s - exact_phi) / np.linalg.norm(exact_phi)
        q_error = np.linalg.norm(solution.normal_derivative_m_s - exact_q) / np.linalg.norm(exact_q)
        self.assertLess(phi_error, 0.02)
        self.assertLess(q_error, 0.02)
        self.assertLess(solution.relative_residual, 1e-11)
        self.assertTrue(np.isfinite(solution.condition_number))

    def test_boundary_velocity_recovers_linear_harmonic_field(self) -> None:
        boundary = _circle(192)
        y = boundary.panel_mid_y_m
        normal = boundary.panel_normal
        exact_phi = y
        exact_gradient = np.column_stack((np.ones_like(y), np.zeros_like(y)))
        exact_q = np.sum(exact_gradient * normal, axis=1)
        mask = np.asarray([label == "dirichlet" for label in boundary.panel_labels])
        known = np.where(mask, exact_phi, exact_q)
        solution = solve_mixed_boundary_laplace(
            boundary,
            dirichlet_mask=mask,
            known_value=known,
            gauss_order=16,
        )
        velocity = boundary_velocity(boundary, solution)
        relative = np.linalg.norm(velocity - exact_gradient) / np.linalg.norm(exact_gradient)
        self.assertLess(relative, 0.025)

    def test_all_neumann_problem_is_rejected(self) -> None:
        boundary = _circle(32)
        with self.assertRaisesRegex(ValueError, "Dirichlet"):
            solve_mixed_boundary_laplace(
                boundary,
                dirichlet_mask=np.zeros(boundary.panel_count, dtype=bool),
                known_value=np.zeros(boundary.panel_count),
            )

    def test_pressure_auxiliary_enforces_zero_free_surface_gauge_pressure(self) -> None:
        boundary = _rectangular_fluid_domain()
        labels = np.asarray(boundary.panel_labels, dtype=object)
        free_mask = labels == "free_surface"
        body_mask = labels == "body"
        potential = solve_section_potential_bvp(
            boundary,
            free_surface_potential_m2_s=np.zeros(np.count_nonzero(free_mask)),
            body_normal_velocity_mps=np.full(np.count_nonzero(body_mask), 0.18),
            gauss_order=12,
        )
        pressure = solve_pressure_auxiliary_bvp(
            boundary,
            potential,
            body_velocity_yz_mps=(0.0, 0.18),
            body_acceleration_normal_mps2=np.full(np.count_nonzero(body_mask), -0.07),
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.81,
            gauss_order=12,
        )
        self.assertLess(potential.relative_residual, 1e-11)
        self.assertLess(pressure.auxiliary_solution.relative_residual, 1e-11)
        self.assertLess(pressure.free_surface_pressure_max_abs_pa, 1e-8)
        self.assertTrue(np.isfinite(pressure.body_vertical_force_per_length_n_m))
        self.assertEqual(pressure.body_panel_count, np.count_nonzero(body_mask))

    def test_incident_wave_pressure_terms_preserve_free_surface_zero_gauge(self) -> None:
        boundary = _rectangular_fluid_domain()
        labels = np.asarray(boundary.panel_labels, dtype=object)
        free_mask = labels == "free_surface"
        body_mask = labels == "body"
        potential = solve_section_potential_bvp(
            boundary,
            free_surface_potential_m2_s=np.zeros(np.count_nonzero(free_mask)),
            body_normal_velocity_mps=np.full(np.count_nonzero(body_mask), 0.11),
            gauss_order=12,
        )
        incident_vertical_velocity = 0.07 * np.exp(
            0.2 * boundary.panel_mid_z_up_m
        )
        incident_potential_time_derivative = -0.35 * np.exp(
            0.2 * boundary.panel_mid_z_up_m
        )
        pressure = solve_pressure_auxiliary_bvp(
            boundary,
            potential,
            body_velocity_yz_mps=(0.0, 0.18),
            body_acceleration_normal_mps2=np.full(
                np.count_nonzero(body_mask), -0.07
            ),
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.81,
            gauss_order=12,
            incident_vertical_velocity_mps=incident_vertical_velocity,
            incident_potential_time_derivative_m2_s2=(
                incident_potential_time_derivative
            ),
        )
        self.assertLess(pressure.auxiliary_solution.relative_residual, 1e-11)
        self.assertLess(pressure.free_surface_pressure_max_abs_pa, 1e-8)

    def test_static_wedge_pressure_integrates_to_hydrostatic_buoyancy(self) -> None:
        half_beam = 0.42
        draft = 0.16
        rho = 1000.0
        gravity = 9.81
        boundary = build_symmetric_wedge_fluid_boundary(
            half_beam_m=half_beam,
            draft_m=draft,
            free_surface_extent_m=3.0,
            water_depth_m=2.0,
            body_panels_per_side=28,
            free_surface_panels_per_side=36,
            side_wall_panels=8,
            bottom_panels=40,
        )
        labels = np.asarray(boundary.panel_labels, dtype=object)
        free_mask = labels == "free_surface"
        body_mask = labels == "body"
        potential = solve_section_potential_bvp(
            boundary,
            free_surface_potential_m2_s=np.zeros(np.count_nonzero(free_mask)),
            body_normal_velocity_mps=np.zeros(np.count_nonzero(body_mask)),
            gauss_order=12,
        )
        pressure = solve_pressure_auxiliary_bvp(
            boundary,
            potential,
            body_velocity_yz_mps=(0.0, 0.0),
            body_acceleration_normal_mps2=np.zeros(np.count_nonzero(body_mask)),
            rho_water_kg_m3=rho,
            gravity_m_s2=gravity,
            gauss_order=12,
        )
        expected = rho * gravity * half_beam * draft
        relative = abs(pressure.body_vertical_force_per_length_n_m - expected) / expected
        self.assertLess(relative, 1e-10)
        self.assertLess(pressure.free_surface_pressure_max_abs_pa, 1e-10)


if __name__ == "__main__":
    unittest.main()
