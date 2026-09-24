import numpy as np
import pytest
from scripts.audit_kang_anchored_section_spectrum import trapezoidal_radius


def test_oscillatory_positive_operator_has_unit_radius():
    assert trapezoidal_radius([1.,10.,100.],.5)==pytest.approx(1.)


def test_unstable_operator_matches_explicit_trapezoidal_matrix():
    operator=np.diag([-2.,3.])
    generator=np.block([[np.zeros((2,2)),-np.eye(2)],[operator,np.zeros((2,2))]])
    dt=.1
    update=np.linalg.solve(np.eye(4)-dt*generator/2,np.eye(4)+dt*generator/2)
    assert trapezoidal_radius(np.diag(operator),dt,1.)==pytest.approx(max(abs(np.linalg.eigvals(update))))


def test_invalid_time_rejected():
    with pytest.raises(ValueError):
        trapezoidal_radius([1],0.)
