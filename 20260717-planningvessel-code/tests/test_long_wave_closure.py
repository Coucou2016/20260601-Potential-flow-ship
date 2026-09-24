import numpy as np
from scripts.audit_long_wave_closure import translation_residual


def test_uniform_water_level_translation_uses_sine_reference_and_cross_term():
    c = np.array([[10.,2.],[-3.,4.]])
    np.testing.assert_array_equal(translation_residual(c,-1j*c[:,0]),0.)
    assert np.linalg.norm(translation_residual(c,1j*c[:,0])) > 0
