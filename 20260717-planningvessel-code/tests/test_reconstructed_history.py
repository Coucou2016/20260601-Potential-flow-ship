from dataclasses import replace
import numpy as np
import pytest
from scipy.integrate import quad_vec

from planing_seakeeping.kernels.linear_2p5d.formulation import build_control_surface_geometry, _transient_green_matrices_for_lag
from planing_seakeeping.kernels.linear_2p5d.reconstructed_history import reconstructed_history_operators


@pytest.mark.parametrize('slope', [0., .4 + .2j])
def test_affine_trace_against_independent_adaptive_arc_integration(slope):
    source = build_control_surface_geometry(1.3, 8)
    field = build_control_surface_geometry(.7, 4)
    lag = np.array([.03, .4, 1.2])
    p, a = reconstructed_history_operators(field, source, lag, spectral_count=64, order=32)
    arc = np.cumsum(source.length_m) - source.length_m / 2
    samples = 1.2 - .3j + slope * arc
    reference = np.zeros((2, len(lag), field.panel_count), complex)
    for j in range(source.panel_count):
        center = np.arctan2(source.mid_z_down_m[j], source.mid_y_m[j])
        def integrand(offset):
            theta = center + offset / 1.3
            point = replace(source, mid_y_m=np.array([1.3*np.cos(theta)]),
                mid_z_down_m=np.array([1.3*np.sin(theta)]), normal_y=np.array([np.cos(theta)]),
                normal_z=np.array([np.sin(theta)]), length_m=np.ones(1))
            blocks = [_transient_green_matrices_for_lag(field, point, t,
                gravity_m_s2=9.80665, quadrature_count=64, k_max=25.) for t in lag]
            return np.asarray(blocks).transpose(1, 0, 2, 3)[..., 0] * (samples[j] + slope*offset)
        reference += quad_vec(integrand, -source.length_m[j]/2, source.length_m[j]/2,
                              epsabs=1e-11, epsrel=1e-11)[0]
    np.testing.assert_allclose(p @ samples, reference[0], atol=2e-11, rtol=2e-11)
    np.testing.assert_allclose(a @ samples, reference[1], atol=2e-11, rtol=2e-11)


def test_spatial_order_convergence_and_lag_causality():
    source = build_control_surface_geometry(1.3, 12)
    first = reconstructed_history_operators(source, source, [.1, .3], order=32)
    refined = reconstructed_history_operators(source, source, [.1, .3, .8], order=64)
    for a, b in zip(first, refined):
        np.testing.assert_allclose(a, b[:2], atol=1e-11, rtol=1e-11)


@pytest.mark.parametrize('kwargs', [{'lag_s':[0.]}, {'lag_s':[-1.]}, {'lag_s':[np.nan]},
    {'lag_s':[.1], 'gravity':0.}, {'lag_s':[.1], 'k_max':np.inf},
    {'lag_s':[.1], 'order':4}, {'lag_s':[.1], 'spectral_count':12}])
def test_invalid_inputs_rejected(kwargs):
    source = build_control_surface_geometry(1., 8)
    with pytest.raises(ValueError):
        reconstructed_history_operators(source, source, **kwargs)


def test_explicit_route_connects_history_and_rejects_mixed_assembly():
    from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route, current_panel_integration_route
    from planing_seakeeping.kernels.linear_2p5d.formulation import build_transient_free_surface_history, assemble_outer_control_surface_system
    source = build_control_surface_geometry(1.3, 8)
    zeros = np.zeros((2, 8), complex)
    old = build_transient_free_surface_history(source, .1, 2, quadrature_count=32, k_max=25.)
    with panel_integration_route('reconstructed_symmetric'):
        new = build_transient_free_surface_history(source, .1, 2, quadrature_count=32, k_max=25.)
        expected = reconstructed_history_operators(source, source, [.1, .2], spectral_count=32)
        np.testing.assert_array_equal(new.green_potential, expected[0])
        np.testing.assert_array_equal(new.green_normal_derivative, expected[1])
        system = assemble_outer_control_surface_system(source, new, zeros, zeros)
        assert np.isfinite(system.matrix).all()
        with pytest.raises(ValueError, match='must match'):
            assemble_outer_control_surface_system(source, old, zeros, zeros)
    assert current_panel_integration_route() == 'midpoint'
    with pytest.raises(ValueError, match='must match'):
        assemble_outer_control_surface_system(source, new, zeros, zeros)
