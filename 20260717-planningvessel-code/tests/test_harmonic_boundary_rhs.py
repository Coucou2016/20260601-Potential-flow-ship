from types import SimpleNamespace
import numpy as np
from scripts.harmonic_boundary_rhs import integrated_known_term
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    build_control_surface_geometry,build_waterline_clipped_free_surface_geometry,
    _inner_b_matrix)
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


def test_constant_flux_matches_exact_panel_integral():
    source=build_waterline_clipped_free_surface_geometry(-2,2,.2,12)
    field=SimpleNamespace(mid_y_m=np.array([.1,.4]),mid_z_down_m=np.array([.3,.5]))
    with panel_integration_route('analytic_straight_midpoint_curved'):
        expected=_inner_b_matrix(field,source)@source.normal_z
    actual=integrated_known_term(field,source,'linear_z',kind='body_flux',order=64)
    np.testing.assert_allclose(actual,expected,atol=1e-12,rtol=1e-12)


def test_quadratic_control_self_integral():
    control=build_control_surface_geometry(1.3,24)
    actual=integrated_known_term(control,control,'quadratic',kind='control_potential',self_boundary=True)
    expected=-np.pi*(control.mid_y_m**2-control.mid_z_down_m**2)
    np.testing.assert_allclose(actual,expected,atol=1e-11,rtol=1e-11)


def test_zero_free_surface_known_potential():
    free=build_waterline_clipped_free_surface_geometry(-2,2,.2,12)
    actual=integrated_known_term(free,free,'linear_z',kind='free_potential',self_boundary=True)
    np.testing.assert_array_equal(actual,0.)
