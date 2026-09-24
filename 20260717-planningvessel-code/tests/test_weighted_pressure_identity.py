import numpy as np
import pytest
from scripts.audit_weighted_pressure_identity import counterexample


@pytest.mark.parametrize('cutoff',[.2,.37,.8])
def test_window_boundary_term_is_required(cutoff):
    row=counterexample(cutoff)
    np.testing.assert_allclose(row['corrected'],row['pressure_integral'],atol=1e-12,rtol=0)
    assert abs(row['clipped_transformed_integral']-row['pressure_integral']) > 1.
