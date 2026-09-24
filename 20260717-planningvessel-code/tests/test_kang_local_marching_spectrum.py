import numpy as np
import pytest
from scripts.audit_kang_local_marching_spectrum import marching_matrix
from planing_seakeeping.kernels.linear_2p5d.formulation import FreeSurfaceMarchingState, advance_free_surface_state
from planing_seakeeping.types import ValidityReport


def test_scalar_oscillator_threshold():
    assert max(abs(np.linalg.eigvals(marching_matrix(np.array([[4.]]), .9, gravity=1.)))) == pytest.approx(1.)
    assert max(abs(np.linalg.eigvals(marching_matrix(np.array([[4.]]), 1.1, gravity=1.)))) > 1.


def test_matrix_matches_production_staggered_update():
    k = np.array([[2., -.3], [-.3, 1.]])
    phi, eta = np.array([1.+.2j, -.7j]), np.array([.2j, -.1])
    state = FreeSurfaceMarchingState(y_m=np.array([-1.,1.]), potential_m2_s=phi,
        elevation_m=eta, time_s=0., half_step_time_s=-.05,
        validity=ValidityReport(status='manufactured', reference_cases=(), notes=()))
    advanced = advance_free_surface_state(state, k@phi, .1)
    np.testing.assert_allclose(marching_matrix(k, .1)@np.r_[phi, eta],
        np.r_[advanced.potential_m2_s, advanced.elevation_m])


def test_invalid_operator():
    with pytest.raises(ValueError):
        marching_matrix(np.array([[np.nan]]), .1)
