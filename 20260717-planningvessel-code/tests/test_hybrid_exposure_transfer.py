import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.free_surface_transfer import exposure_linear_bounded_edge_transfer
from scripts.audit_moving_free_surface_manufactured import simulate


def transfer(values):
    return exposure_linear_bounded_edge_transfer(
        np.array([-.4,-.3,-.2,.2,.3,.4]),np.array([-.35,-.19,-.17,.17,.19,.35]),values,
        previous_half_beam=.18,control_radius=.9,maximum_spacing_ratio=1.)


def test_new_region_affine_exact_but_old_edge_still_nearest():
    x=np.array([-.4,-.3,-.2,.2,.3,.4])
    values=(1+(2+3j)*x)[:,None]
    result=transfer(values)
    np.testing.assert_allclose(result.values[[2,3],0],1+(2+3j)*np.array([-.17,.17]))
    np.testing.assert_allclose(result.values[[1,4],0],values[[2,3],0])
    np.testing.assert_allclose(values[:,0],1+(2+3j)*x)
    assert result.exposed_source=='linear_exposure_bounded_edges_unvalidated'


def test_global_complex_phase_covariance():
    values=np.arange(12).reshape(6,2).astype(complex)
    phase=np.exp(.71j)
    np.testing.assert_allclose(transfer(values*phase).values,transfer(values).values*phase)


def test_excessive_release_is_rejected():
    with pytest.raises(ValueError,match='continuation distance'):
        exposure_linear_bounded_edge_transfer(
            np.array([-.4,-.3,-.2,.2,.3,.4]),np.array([-.02,.02]),np.ones((6,1)),
            previous_half_beam=.18,control_radius=.9,maximum_spacing_ratio=1.)


def test_manufactured_candidate_is_finite():
    result=simulate(2,'linear_exposure_bounded_edges_unvalidated')
    assert np.isfinite(result['final_values']).all()
    assert result['maximum_equation_error'] < 1e-10
