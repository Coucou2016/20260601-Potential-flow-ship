import numpy as np
import pytest
from scripts.decompose_radiation_pressure_gap import (
    geometry_and_stokes, graph_boundary_terms, tangential_transport_defect, bow_up_coefficients,
)
from planing_seakeeping.kernels.linear_2p5d.weighted_transport import clipped_pressure_identity


def test_full_domain_end_is_counted_once_with_nonzero_bow_potential():
    x = np.array([0., .4, 1., 2.])
    phi = (1+2j)*np.ones((len(x), 1))
    j3 = -np.ones_like(phi.real)
    measure = np.stack((j3, j3*(.7-x[:, None])), axis=2)
    rho, speed, omega = 1000., 3., 2.
    result = clipped_pressure_identity(x, phi, measure, np.zeros_like(phi), 0.,
                                      rho=rho, speed=speed, omega=omega)
    end = -rho*speed*np.sum(phi[0, :, None]*measure[0], axis=0)
    _, stokes = geometry_and_stokes(x, phi, j3, .7, 0.)
    production = result['time']+rho*speed*stokes+end
    np.testing.assert_allclose(end, result['lower_edge'])
    np.testing.assert_allclose(result['direct']-production, result['upper_edge'], atol=1e-10)
    assert np.linalg.norm(result['upper_edge']) > 0


@pytest.mark.parametrize('row,col,sign', [(3,3,1), (3,5,-1), (5,3,-1), (5,5,1)])
def test_coefficient_coordinates_and_damping_sign(row, col, sign):
    values = bow_up_coefficients(12-10j, row, col, 2.)
    assert values == dict(A=3*sign, B=5*sign)


@pytest.mark.parametrize('omega', [0., -1., np.nan])
def test_coefficient_invalid_frequency(omega):
    with pytest.raises(ValueError):
        bow_up_coefficients(1+2j, 5, 3, omega)


def test_fixed_heave_measure_has_only_pitch_stokes_term():
    x = np.array([0., .4, 1., 2.])
    p = (1+2j)*np.ones((4, 1))
    geometry, stokes = geometry_and_stokes(x, p, np.ones((4, 1)), 1., .2)
    np.testing.assert_allclose(geometry, 0, atol=1e-14)
    np.testing.assert_allclose(stokes, [0, 1.8*(1+2j)], atol=1e-14)


def test_varying_measure_against_independent_polynomial_integrals():
    x = np.array([0., .4, 1., 2.])
    p = (1+2j)*(1+x[:, None])
    j = 2+3*x[:, None]
    geometry, stokes = geometry_and_stokes(x, p, j, 1., .2)
    integrate = lambda coefficients: np.polyval(np.polyint(coefficients), 2.)-np.polyval(np.polyint(coefficients), .2)
    expected = (1+2j)*np.array([-3*integrate([1, 1]), -3*integrate([-1, 0, 1])])
    np.testing.assert_allclose(geometry, expected, rtol=1e-14)
    np.testing.assert_allclose(stokes, [0, (1+2j)*integrate([3, 5, 2])], rtol=1e-14)


def test_graph_waterline_and_submerged_terms_with_affine_potential():
    x = np.array([0., .4, 1., 2.])
    width = 2+.4*x
    y = width[:, None]*np.array([5, 3, 1, -1, -3, -5])[None, :]/12
    beta = .3
    z = beta*(width[:, None]/2-abs(y))
    a, b, c = .2+.3j, .7-.2j, 1+2j
    phi = a*y+b*z+c
    nz = 1/np.sqrt(1+beta**2)
    ny = np.sign(y)*beta*nz
    qn = a*ny+b*nz
    j3 = -width[:, None]*np.ones((1, 6))/6
    edge, interior = graph_boundary_terms(x, y, z, phi, qn, j3)
    np.testing.assert_allclose(edge, .4*c, rtol=1e-13)
    np.testing.assert_allclose(interior, b*beta*.4/2*width, rtol=1e-13)
    _, defect = tangential_transport_defect(x, y, phi, j3, edge)
    np.testing.assert_allclose(defect, 0, atol=1e-14)
