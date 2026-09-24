import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.implicit_free_surface import ImplicitFreeSurfaceStep


def oscillator(dt, duration=2.):
    step = ImplicitFreeSurfaceStep([[1.]], [[4.]], 0, dt, gravity=1.)
    phi, eta, q = np.array([1.+0j]), np.array([0j]), np.array([4.+0j])
    for _ in range(round(duration/dt)):
        state = step.advance(phi, eta, q, np.zeros(1))
        phi, eta, q = state['phi'], state['eta'], state['q']
    return np.r_[phi, eta]


def test_second_order_phase_and_amplitude_convergence():
    exact = np.array([np.cos(4.), 2*np.sin(4.)])
    errors = [np.linalg.norm(oscillator(dt)-exact) for dt in (.1,.05,.025)]
    assert errors[1] < .27*errors[0] and errors[2] < .27*errors[1]


def test_no_artificial_damping_for_scalar_oscillator_large_step():
    phi, eta = oscillator(2., duration=200.)
    assert abs(phi)**2+abs(eta)**2/4 == pytest.approx(1., abs=1e-12)


def test_new_time_forcing_and_all_equations_are_satisfied():
    m = np.array([[2., .3], [-.2, 1.]])
    r = np.array([[.5], [1.2]])
    dt, g = .2, 9.80665
    step = ImplicitFreeSurfaceStep(m, r, 1, dt, gravity=g)
    phi, eta, q = np.array([.4+.1j]), np.array([.2j]), np.array([-.3j])
    h = np.array([1.+.2j, -.4])
    state = step.advance(phi, eta, q, h)
    np.testing.assert_allclose(m@state['values'], r@state['phi']+h)
    np.testing.assert_allclose(state['phi']-phi, -g*dt/2*(eta+state['eta']))
    np.testing.assert_allclose(state['eta']-eta, dt/2*(q+state['q']))


def test_invalid_inputs():
    with pytest.raises(ValueError):
        ImplicitFreeSurfaceStep([[1.]], [[1.]], 1, .1)
    step = ImplicitFreeSurfaceStep([[1.]], [[1.]], 0, .1)
    with pytest.raises(ValueError):
        step.advance([np.nan], [0], [0], [0])
