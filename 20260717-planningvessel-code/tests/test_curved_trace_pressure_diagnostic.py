import numpy as np
import pytest
from scripts.curved_trace_pressure_diagnostic import recover_gradient


def manufactured(n):
    x = np.linspace(0., 2., n)
    u = np.linspace(.01, .99, n)
    uu = np.r_[u, u[::-1]][None, :]
    sign = np.r_[np.ones(n), -np.ones(n)][None, :]
    a, d = 1+.1*x[:, None], 1+.05*x[:, None]
    y, z = sign*a*(1-uu**2), d*uu
    # Increasing contour parameter is u on starboard, -u on port.
    ty = -2*a*uu
    tz = sign*d*np.ones_like(uu)
    length = np.hypot(ty, tz)
    ny, nz = tz/length, -ty/length
    phase = np.exp(1j*x[:, None])
    phi = phase*(y*y-z*z+.2*y+.1j*z)
    qn = phase*((2*y+.2)*ny+(-2*z+.1j)*nz)
    return x, y, z, phi, qn, ny, nz


def test_curved_moving_surface_chain_rule_converges():
    errors = []
    for n in (17, 33, 65):
        args = manufactured(n)
        recovered = recover_gradient(*args)
        exact = 1j*args[3]
        errors.append(np.linalg.norm(recovered['eulerian']-exact)/np.linalg.norm(exact))
        assert np.linalg.norm(recovered['material']-exact) > 10*np.linalg.norm(recovered['eulerian']-exact)
    assert errors[1] < .3*errors[0] and errors[2] < .3*errors[1]
    assert errors[-1] < .001


def test_normal_orientation_and_nonfinite_inputs_rejected():
    args = list(manufactured(9))
    args[-1] = -args[-1]
    args[-2] = -args[-2]
    with pytest.raises(ValueError, match='ordering'):
        recover_gradient(*args)
    args = list(manufactured(9))
    args[3][0, 0] = np.nan
    with pytest.raises(ValueError, match='finite'):
        recover_gradient(*args)
