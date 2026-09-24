import numpy as np
import pytest
from scripts.audit_kang_contact_trace import endpoint_trace


def test_complex_affine_trace_is_exact_with_unordered_samples():
    distances=np.array([.3,.1,.2])
    values=2+3j+distances*(4-5j)
    assert endpoint_trace(distances,values)==pytest.approx(2+3j)


@pytest.mark.parametrize('distances',[[0.,.1],[.1,.1],[.1,float('nan')]])
def test_invalid_contact_distances_rejected(distances):
    with pytest.raises(ValueError):
        endpoint_trace(distances,[1.,2.])
