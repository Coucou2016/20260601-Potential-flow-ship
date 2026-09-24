from types import SimpleNamespace

import numpy as np
import pytest
from scipy.integrate import quad

from planing_seakeeping.kernels.linear_2p5d.panel_integrals import straight_log_integrals


def geometry(y, z, ny=0., nz=1., length=1.):
    return SimpleNamespace(mid_y_m=np.atleast_1d(y), mid_z_down_m=np.atleast_1d(z),
        normal_y=np.atleast_1d(ny), normal_z=np.atleast_1d(nz), length_m=np.atleast_1d(length))


@pytest.mark.parametrize('angle', [0., .3, 1.2])
@pytest.mark.parametrize('mirrored', [False, True])
@pytest.mark.parametrize('height', [.002, .1, 3., -.02])
def test_independent_adaptive_quadrature(angle, mirrored, height):
    center = np.array([.2, .4])
    normal = np.array([np.sin(angle), np.cos(angle)])
    source = geometry(*center, *normal, length=.7)
    if mirrored:
        center[1] *= -1
        normal[1] *= -1
    tangent = np.array([-normal[1], normal[0]])
    point = center + .2*tangent + height*normal
    field = geometry(*point)
    p, a = straight_log_integrals(field, source, mirrored_source=mirrored)
    def kernel(s, derivative=False):
        r = point-center-s*tangent
        return -np.dot(r,normal)/np.dot(r,r) if derivative else np.log(np.linalg.norm(r))
    expected_p = quad(kernel, -.35, .35, epsabs=1e-11, points=[.2])[0]
    expected_a = quad(lambda s: kernel(s, True), -.35, .35, epsabs=1e-11, points=[.2])[0]
    np.testing.assert_allclose([p[0,0],a[0,0]], [expected_p,expected_a], atol=1e-10, rtol=1e-10)


def test_self_and_coplanar_nonself():
    source = geometry([0., 2.], [0., 0.], [0., 0.], [1., 1.], [1., 1.])
    p, a = straight_log_integrals(source, source, same_boundary=True, diagonal_sign=-1)
    np.testing.assert_allclose(np.diag(p), np.log(.5)-1)
    np.testing.assert_allclose(a, -np.pi*np.eye(2))
    assert np.isfinite(p).all()


def test_nonunit_normal_rejected():
    with pytest.raises(ValueError, match='unit normals'):
        straight_log_integrals(geometry(1,1), geometry(0,0,nz=2))


def test_adjacent_selection_independent_of_body_order():
    from scripts.audit_waterline_panel_quadrature import adjacent_pairs
    for y in (np.array([.2,0.,-.2]),np.array([-.2,0.,.2])):
        pairs = adjacent_pairs(y,72)
        assert [(side,y[index],j) for side,index,j in pairs] == [('left',-.2,35),('right',.2,36)]


def test_explicit_route_dispatch_and_restore():
    from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route, use_exact_straight_panels
    from planing_seakeeping.kernels.linear_2p5d.formulation import (
        build_waterline_clipped_free_surface_geometry, build_control_surface_geometry,
        _log_potential_between_raw, _log_normal_derivative_between_raw)
    source = build_waterline_clipped_free_surface_geometry(-3,3,.2,12)
    field = geometry(.21,.002)
    old = _log_potential_between_raw(field,source)
    with pytest.raises(RuntimeError):
        with panel_integration_route('analytic_straight_midpoint_curved'):
            assert use_exact_straight_panels(source)
            assert not use_exact_straight_panels(build_control_surface_geometry(3,12))
            p,a = straight_log_integrals(field,source)
            np.testing.assert_array_equal(_log_potential_between_raw(field,source),p)
            np.testing.assert_array_equal(_log_normal_derivative_between_raw(field,source),a)
            assert not np.allclose(p,old)
            raise RuntimeError('restore on solve failure')
    np.testing.assert_array_equal(_log_potential_between_raw(field,source),old)
    with pytest.raises(ValueError,match='Unknown'):
        with panel_integration_route('not_a_backend'):
            pass
