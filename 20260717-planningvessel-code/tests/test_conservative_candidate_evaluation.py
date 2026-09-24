import numpy as np
import pytest
from scripts.evaluate_conservative_candidate import verify_saved_response


def test_csv_and_saved_dynamics_must_agree():
    record = dict(q3_real=1.,q3_imag=2.,q5_real=3.,q5_imag=4.,omega=5.)
    data = dict(response=np.array([1+2j,3+4j]),omega=5.)
    verify_saved_response(record,data)
    with pytest.raises(ValueError,match='response'):
        verify_saved_response(dict(record,q3_real=0.),data)
    with pytest.raises(ValueError,match='frequency'):
        verify_saved_response(dict(record,omega=6.),data)
