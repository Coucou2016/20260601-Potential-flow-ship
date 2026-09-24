import numpy as np
import pytest
from scripts.audit_tangent_weak_form import weak_integral


@pytest.mark.parametrize("order",[1,2])
def test_affine_potential_weight_exact_including_end_terms(order):
    length=np.full(12,1/12)
    s=np.cumsum(length)-length/2
    phi=(2+3j)*s+(1-2j)
    np.testing.assert_allclose(weak_integral(length,phi,1+2*s,order),2*(2+3j),atol=1e-13)


def test_quadratic_potential_converges_with_endpoint_terms():
    errors=[]
    for n in (12,24,48):
        length=np.full(n,1/n)
        s=np.cumsum(length)-length/2
        errors.append(abs(weak_integral(length,s*s,1+2*s,2)-7/3))
    assert errors[-1] < errors[0]/10


def test_nonaffine_weight_rejected():
    length=np.full(12,1/12)
    s=np.cumsum(length)-length/2
    with pytest.raises(ValueError,match="affine"):
        weak_integral(length,s,s*s,2)
