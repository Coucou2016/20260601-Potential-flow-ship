import numpy as np
import pytest
from scripts.audit_kang_smooth_forcing import ramp


def test_quintic_ramp_is_bounded_and_smooth_at_start():
    np.testing.assert_allclose(ramp(np.array([-1.,0.,.5,1.,2.]),1.),[0.,0.,.5,1.,1.])
    assert ramp(.001,1.)<1e-8
    assert 1-ramp(.999,1.)<1e-8


def test_invalid_ramp():
    with pytest.raises(ValueError):
        ramp(1.,0.)
    with pytest.raises(ValueError):
        ramp(np.nan,1.)
