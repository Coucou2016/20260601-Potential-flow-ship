import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.weighted_transport import clipped_transport_identity


def test_complex_moving_measure_chain_and_interior_cutoff():
    x=np.array([0.,.1,.4,1.2,2.])
    phi=(1+2j)*(2-x[:,None])*np.array([[1.,3.]])
    measure=(1+x[:,None,None])*np.array([[[1.,2.],[3.,4.]]])
    chain=(.2-.3j)*x[:,None]*np.ones((1,2))
    result=clipped_transport_identity(x,phi,measure,chain,.23)
    np.testing.assert_allclose(result['direct'],result['transformed'],rtol=1e-14,atol=2e-14)
    assert np.linalg.norm(result['chain'])>0
    assert np.linalg.norm(result['lower_edge'])>0


def test_fixed_measure_affine_potential_analytic_integral():
    x=np.array([0.,.4,1.,2.])
    phi=((2-x)*(1+.5j))[:,None]
    measure=np.ones((4,1,1))
    r=clipped_transport_identity(x,phi,measure,np.zeros_like(phi),.37)
    np.testing.assert_allclose(r['direct'],-(2-.37)*(1+.5j),atol=1e-14)
    np.testing.assert_allclose(r['transformed'],r['lower_edge'],atol=1e-14)


@pytest.mark.parametrize('cutoff',[-.1,2.,np.nan])
def test_no_silent_extrapolation(cutoff):
    with pytest.raises(ValueError):
        clipped_transport_identity([0.,1.,2.],np.ones((3,1)),np.ones((3,1,1)),np.zeros((3,1)),cutoff)
