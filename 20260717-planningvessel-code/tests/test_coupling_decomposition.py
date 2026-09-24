import numpy as np
import pytest
from scripts.diagnose_longitudinal_coupling import decompose


def test_complex_superposition_and_elimination():
    matrix = np.array([[2+1j, .4-.2j], [-.3+.1j, 3+2j]])
    incident, diffraction = np.array([1+2j, 3-1j]), np.array([-.4j, -.7+1j])
    parts, total, schur, effective = decompose(matrix, incident, diffraction)
    np.testing.assert_allclose(parts.sum(axis=1), total, atol=1e-14)
    np.testing.assert_allclose(effective.sum()/schur, total[1], atol=1e-14)
    np.testing.assert_allclose(matrix @ total, incident+diffraction, atol=1e-14)


def test_small_heave_pivot_cannot_produce_misleading_schur():
    with pytest.raises(ValueError, match="pivot"):
        decompose([[0,1],[1,2]], [1,0], [0,1])
