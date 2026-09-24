import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.trace_transport import (
    integrate_trace_transport, recover_straight_trace_pressure,
)


def test_affine_fields_match_analytic_integrals_on_nonuniform_cells():
    nodes = np.array([0., .02, .2, .7, 1.])
    mid = (nodes[:-1]+nodes[1:])/2
    r = integrate_trace_transport(nodes, (1+2j)*(1+mid), 2-3*mid)
    np.testing.assert_allclose(r['potential_average'], (1+2j)*(1+mid), atol=1e-14)
    np.testing.assert_allclose(r['derivative_weight_integral'],
                               (1+2j)*(2*np.diff(nodes)-1.5*np.diff(nodes**2)), atol=1e-14)
    np.testing.assert_allclose(r['residual'], 0, atol=1e-14)


def test_complex_nonpolynomial_cellwise_conservation():
    nodes = np.linspace(0, 1, 31)**1.5
    mid = (nodes[:-1]+nodes[1:])/2
    r = integrate_trace_transport(nodes, np.exp((1+2j)*mid), np.cos(mid))
    np.testing.assert_allclose(r['residual'], 0, atol=1e-14)


def test_smooth_weighted_derivative_converges_second_order():
    errors = []
    exact = np.e-.6
    for count in (20, 40, 80):
        nodes = np.linspace(0, 1, count+1)
        mid = (nodes[:-1]+nodes[1:])/2
        r = integrate_trace_transport(nodes, np.exp(mid), 1+.4*mid)
        errors.append(abs(r['derivative_weight_integral'].sum()-exact))
    assert errors[0]/errors[1] > 3.8
    assert errors[1]/errors[2] > 3.8


@pytest.mark.parametrize('nodes,phi,w', [([0, 0, 1], [1, 2], [0, 1]),
    ([0, 1, 2], [1], [0, 1]), ([0, 1, 2], [1, np.nan], [0, 1]),
    ([0, 1], [1], [0])])
def test_invalid_trace_rejected(nodes, phi, w):
    with pytest.raises(ValueError):
        integrate_trace_transport(nodes, phi, w)


def test_pressure_of_affine_spatial_potential_on_moving_straight_trace():
    nodes = np.array([0., .03, .2, .7, 1.])
    mid = (nodes[:-1]+nodes[1:])/2
    # phi=a*x+b*y+c*z, with a straight trace (ty,tz)=(.8,.6).
    a, b, c = 1+.3j, .7-.2j, -.4+.5j
    phi = a*.2+(b*.8+c*.6)*mid
    yt, zt = .2+.1*mid, -.3+.2*mid
    qn = np.full_like(phi, -.6*b+.8*c)
    material = a+b*yt+c*zt
    r = recover_straight_trace_pressure(nodes, phi, qn, material,
        .8*yt+.6*zt, -.6*yt+.8*zt, rho=1025., speed=8., omega=4.)
    expected = -1025*4j*phi+1025*8*a
    np.testing.assert_allclose(r['pressure_average'], expected, rtol=1e-13)
