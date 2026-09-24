import numpy as np
import pytest
from scripts.summarize_kang_domain_sensitivity import compare


def test_complex_phase_change_is_not_hidden_by_equal_amplitude():
    np.testing.assert_allclose(compare(np.ones(2, complex), 1j*np.ones(2)), np.sqrt(2))


@pytest.mark.parametrize('bad', [np.zeros(2), np.array([1., np.nan]), np.ones(3)])
def test_invalid_or_near_zero_reference_is_rejected(bad):
    with pytest.raises(ValueError):
        compare(bad, np.ones(2))
