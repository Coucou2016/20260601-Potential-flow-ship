import numpy as np
import pytest

from planing_seakeeping.kernels.linear_2p5d.formulation import (
    DEFAULT_A1_HEAVE_PITCH_CONVENTION,
)
from planing_seakeeping.kernels.linear_2p5d.weighted_transport import clipped_pressure_identity


def test_pressure_sign_and_lever_match_existing_convention():
    x = np.array([0., .4, 1., 2.])
    phi = np.full((4, 1), 1+2j)
    rows = [DEFAULT_A1_HEAVE_PITCH_CONVENTION.pressure_generalized_rows(
        np.array([1.]), np.array([2.]), lever_arm_m=1-position) for position in x]
    measure = np.asarray(rows).transpose(0, 2, 1)
    result = clipped_pressure_identity(x, phi, measure, np.zeros_like(phi), .2,
                                      rho=1000., speed=0., omega=3.)
    # Constant pressure; integrate -2 and -2*(1-x) independently.
    pressure = -1000*3j*(1+2j)
    expected = pressure*np.array([-3.6, .36])
    np.testing.assert_allclose(result['direct'], expected)
    np.testing.assert_allclose(result['transformed'], expected)


def test_moving_measure_pressure_identity_with_interior_cut():
    x = np.array([0., .4, 1., 2.])
    phi = (1+2j)*(2-x[:, None])
    measure = (1+x[:, None, None])*np.ones((1, 1, 2))
    result = clipped_pressure_identity(x, phi, measure, .1*phi, .23,
                                      rho=1025., speed=8., omega=4.)
    np.testing.assert_allclose(result['direct'], result['transformed'], rtol=1e-13)
    assert np.linalg.norm(result['lower_edge']) > 0


@pytest.mark.parametrize('rho,speed,omega', [(0, 1, 1), (1, -1, 1), (1, 1, 0), (1, np.nan, 1)])
def test_reject_invalid_physics(rho, speed, omega):
    with pytest.raises(ValueError):
        clipped_pressure_identity([0, 1], np.ones((2, 1)), np.ones((2, 1, 1)),
                                  np.zeros((2, 1)), 0, rho=rho, speed=speed, omega=omega)
