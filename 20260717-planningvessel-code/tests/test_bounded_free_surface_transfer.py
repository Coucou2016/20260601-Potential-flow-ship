import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.free_surface_transfer import bounded_trace_transfer


def test_convex_extension_is_constant_preserving_and_phase_covariant():
    source=np.array([-.8,-.4,-.2,.2,.4,.8])
    target=np.array([-.85,-.3,-.12,.12,.3,.85])
    kwargs=dict(previous_half_beam=.15,control_radius=.9,maximum_spacing_ratio=1.)
    matrix=bounded_trace_transfer(source,target,np.eye(6),**kwargs).values
    assert np.min(matrix.real)>=0
    np.testing.assert_allclose(matrix.sum(axis=1),1)
    vector=np.arange(6)+1j*np.arange(6)[::-1]
    phi=bounded_trace_transfer(source,target,vector[:,None],**kwargs).values
    rotated=bounded_trace_transfer(source,target,(vector*np.exp(.73j))[:,None],**kwargs).values
    np.testing.assert_allclose(rotated,phi*np.exp(.73j))
    assert max(abs(phi[:,0]))<=max(abs(vector))


def test_exposure_distance_is_not_relaxed():
    with pytest.raises(ValueError,match='continuation distance'):
        bounded_trace_transfer(np.array([-.4,-.3,.3,.4]),np.array([-.1,.1]),np.ones((4,1)),
            previous_half_beam=.2,control_radius=.9,maximum_spacing_ratio=1.)


def test_edge_extension_is_not_affine_exact():
    source=np.array([-.8,-.2,.2,.8]); target=np.array([-.1,.1])
    result=bounded_trace_transfer(source,target,abs(source)[:,None],previous_half_beam=.15,
        control_radius=.9,maximum_spacing_ratio=1.)
    np.testing.assert_allclose(result.values[:,0],.2)
    assert result.newly_exposed.all()


def test_invalid_limit_rejected_even_without_exposure():
    with pytest.raises(ValueError,match='positive continuation limit'):
        bounded_trace_transfer(np.array([-.8,-.2,.2,.8]),np.array([-.4,.4]),np.ones((4,1)),
            previous_half_beam=.1,control_radius=.9,maximum_spacing_ratio=np.nan)
