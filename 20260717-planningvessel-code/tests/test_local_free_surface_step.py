import numpy as np
from scripts.audit_local_free_surface_step import step_matrix


def test_staggered_oscillator_stability_boundary():
    for dt, unstable in ((.1, False), (.8, True)):
        matrix = step_matrix(np.array([[1.]]), dt)
        radius = max(abs(np.linalg.eigvals(matrix)))
        assert (radius > 1+1e-10) == unstable


def test_block_matrix_matches_explicit_update():
    k = np.array([[2.,.3],[.2,1.]])
    phi, eta = np.array([1.+2j,3j]), np.array([.2j,1.])
    dt = .05
    eta_new = eta+dt*k@phi
    phi_new = phi-9.80665*dt*eta_new
    np.testing.assert_allclose(step_matrix(k,dt)@np.r_[phi,eta], np.r_[phi_new,eta_new])
