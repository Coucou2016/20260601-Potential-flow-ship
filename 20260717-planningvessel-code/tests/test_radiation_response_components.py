import numpy as np
import pytest

from scripts.audit_radiation_response_components import decompose


def test_eight_components_reconstruct_finite_operator_change():
    rigid = np.diag([2., 3.])
    restoring = np.array([[30., 2.], [1., 40.]])
    old = np.array([[1.-2j, 2.+1j], [3.-1j, 4.-3j]])
    new = old + np.array([[.3+.4j, .5-.2j], [-.2+.1j, .7-.6j]])
    force = np.array([1.+2j, 3.-1j])
    omega = 2.
    q0 = np.linalg.solve(restoring-omega**2*rigid-old, force)
    q1 = np.linalg.solve(restoring-omega**2*rigid-new, force)
    parts = decompose(rigid, restoring, old, new, q0, omega)
    assert len(parts) == 8
    np.testing.assert_allclose(sum(parts.values()), q1-q0, atol=1e-15)


def test_unchanged_operator_has_zero_contributions():
    parts = decompose(np.eye(2), 4*np.eye(2), np.eye(2), np.eye(2), np.ones(2), 1.)
    np.testing.assert_array_equal(list(parts.values()), np.zeros((8, 2)))


@pytest.mark.parametrize('omega', [0., -1., np.nan])
def test_invalid_frequency_rejected(omega):
    with pytest.raises(ValueError):
        decompose(np.eye(2), 4*np.eye(2), np.eye(2), np.eye(2), np.ones(2), omega)
