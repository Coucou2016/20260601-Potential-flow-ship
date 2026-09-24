import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.free_surface_transfer import transfer_fields
from planing_seakeeping.kernels.linear_2p5d.free_surface_transfer import limited_linear_exposure


def test_piecewise_affine_fields_exact_including_edge_bands():
    x=np.array([-.9,-.5,-.3,.3,.5,.9])
    y=np.array([-.95,-.7,-.25,.25,.7,.95])
    def values(z):
        return np.c_[2*z+1j*z, np.where(z<0,10+z,-20+3*z)]
    r=transfer_fields(x,y,values(x),previous_half_beam=.2,control_radius=1.)
    np.testing.assert_allclose(r.values,values(y))
    assert r.edge_extrapolated.sum()==4 and not r.newly_exposed.any()


def test_exposed_region_requires_provenance_and_preserves_given_state():
    x=np.array([-.9,-.4,.4,.9]); y=np.array([-.8,-.2,.2,.8]); v=x[:,None]
    with pytest.raises(ValueError,match='Newly exposed'):
        transfer_fields(x,y,v,previous_half_beam=.3,control_radius=1.)
    fill=np.full((4,1),3+4j)
    r=transfer_fields(x,y,v,previous_half_beam=.3,control_radius=1.,
        exposed_values=fill,exposed_source='manufactured boundary state')
    assert r.newly_exposed.sum()==2
    np.testing.assert_allclose(r.values[r.newly_exposed],3+4j)


def test_domain_change_is_not_silently_clamped():
    with pytest.raises(ValueError):
        transfer_fields([-.8,-.4,.4,.8],[-1.2,.5],np.ones((4,1)),previous_half_beam=.2,control_radius=1.)


def test_explicit_continuation_is_affine_exact_and_distance_limited():
    x=np.array([-.8,-.4,.4,.8]); y=np.array([-.7,-.2,.2,.7])
    v=(2*x+1j*x)[:,None]
    fill,ratio=limited_linear_exposure(x,y,v,.3,maximum_spacing_ratio=1.)
    np.testing.assert_allclose(fill[[1,2],0],(2+1j)*y[[1,2]])
    assert ratio==pytest.approx(.5) and np.isnan(fill[[0,3]]).all()
    with pytest.raises(ValueError,match='exceeds'):
        limited_linear_exposure(x,y,v,.3,maximum_spacing_ratio=.1)
