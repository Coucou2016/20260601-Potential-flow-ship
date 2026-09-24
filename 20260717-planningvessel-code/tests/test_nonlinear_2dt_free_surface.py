from __future__ import annotations

import unittest

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.boundary_element import ClosedBoundary2D
from planing_seakeeping.kernels.nonlinear_2dt.free_surface import (
    LagrangianFreeSurfaceState,
    advance_free_surface_rk4,
)
from planing_seakeeping.kernels.nonlinear_2dt.section_geometry import (
    build_symmetric_wedge_fluid_boundary,
)


def _rectangular_fluid_domain(panel_count_per_side: int = 8) -> ClosedBoundary2D:
    n = int(panel_count_per_side)
    top_y = np.linspace(-1.0, 1.0, 2 * n + 1)
    right_z = np.linspace(0.0, -1.0, n + 1)[1:]
    bottom_y = np.linspace(1.0, -1.0, 2 * n + 1)[1:]
    left_z = np.linspace(-1.0, 0.0, n + 1)[1:]
    y = np.concatenate((top_y, np.ones(n), bottom_y, -np.ones(n)))
    z = np.concatenate((np.zeros(2 * n + 1), right_z, -np.ones(2 * n), left_z))
    labels = ("free_surface",) * (2 * n) + ("wall",) * n + ("bottom",) * (2 * n) + ("wall",) * n
    return ClosedBoundary2D(node_y_m=y, node_z_up_m=z, panel_labels=labels)


def _zero_body_velocity(boundary: ClosedBoundary2D, time_s: float) -> np.ndarray:
    del time_s
    labels = np.asarray(boundary.panel_labels, dtype=object)
    return np.zeros(np.count_nonzero(labels == "body"))


class Nonlinear2DtFreeSurfaceTests(unittest.TestCase):
    def test_static_wedge_free_surface_does_not_drift(self) -> None:
        boundary = build_symmetric_wedge_fluid_boundary(
            half_beam_m=0.4,
            draft_m=0.15,
            free_surface_extent_m=2.0,
            water_depth_m=1.5,
            body_panels_per_side=8,
            free_surface_panels_per_side=10,
            side_wall_panels=4,
            bottom_panels=12,
        )
        free_count = boundary.panel_labels.count("free_surface")
        initial = LagrangianFreeSurfaceState(boundary, np.zeros(free_count))
        advanced = advance_free_surface_rk4(
            initial,
            _zero_body_velocity,
            time_step_s=0.01,
            gravity_m_s2=9.81,
            gauss_order=8,
        )
        np.testing.assert_allclose(advanced.state.boundary.node_y_m, boundary.node_y_m, atol=1e-13)
        np.testing.assert_allclose(advanced.state.boundary.node_z_up_m, boundary.node_z_up_m, atol=1e-13)
        np.testing.assert_allclose(advanced.state.free_surface_potential_m2_s, 0.0, atol=1e-13)
        self.assertLess(advanced.max_bvp_relative_residual, 1e-11)

    def test_small_standing_wave_follows_linear_dispersion_phase(self) -> None:
        gravity = 9.81
        amplitude = 1e-4
        boundary = _rectangular_fluid_domain(7)
        labels = np.asarray(boundary.panel_labels, dtype=object)
        free_indices = np.flatnonzero(labels == "free_surface")
        free_node_indices = np.arange(free_indices[0], free_indices[-1] + 2)
        y = boundary.node_y_m.copy()
        z = boundary.node_z_up_m.copy()
        wave_number = np.pi
        z[free_node_indices] = amplitude * np.cos(wave_number * (y[free_node_indices] + 1.0))
        z[-1] = z[0]
        deformed = ClosedBoundary2D(y, z, boundary.panel_labels)
        state = LagrangianFreeSurfaceState(deformed, np.zeros(len(free_indices)))
        dt = 0.0025
        step_count = 20
        max_residual = 0.0
        for _ in range(step_count):
            result = advance_free_surface_rk4(
                state,
                _zero_body_velocity,
                time_step_s=dt,
                gravity_m_s2=gravity,
                gauss_order=8,
            )
            state = result.state
            max_residual = max(max_residual, result.max_bvp_relative_residual)
        free_mid_z = state.boundary.panel_mid_z_up_m[free_indices]
        mode = np.cos(wave_number * (state.boundary.panel_mid_y_m[free_indices] + 1.0))
        computed_amplitude = float(np.dot(free_mid_z, mode) / np.dot(mode, mode))
        omega = np.sqrt(gravity * wave_number * np.tanh(wave_number * 1.0))
        expected_amplitude = amplitude * np.cos(omega * step_count * dt)
        relative = abs(computed_amplitude - expected_amplitude) / amplitude
        self.assertLess(relative, 0.06)
        self.assertLess(max_residual, 1e-10)


if __name__ == "__main__":
    unittest.main()
