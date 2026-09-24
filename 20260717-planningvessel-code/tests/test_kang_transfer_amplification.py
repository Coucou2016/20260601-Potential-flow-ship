import numpy as np
from scripts.audit_kang_transfer_amplification import evaluate


def test_actual_grid_transfer_preserves_sidewise_affine_fields():
    frame,matrix=evaluate(161)
    assert np.isfinite(matrix).all()
    assert frame.constant_error.max()<1e-11
    assert frame.affine_error.max()<1e-11
    assert frame.cumulative_infinity_gain.max()>=1.
