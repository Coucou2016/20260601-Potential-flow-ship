import numpy as np
import pytest
from scripts.audit_kang_incident_force import incident_force


def test_long_wave_waterplane_limit():
    force, direct = incident_force(0.)
    assert force[0] == pytest.approx(-1000*9.80665*(3*.3*52/75))
    assert abs(force[1]) < 1e-10
    np.testing.assert_allclose(force, direct, atol=1e-10)


@pytest.mark.parametrize('k', [.1, 1., 3., 8.])
def test_independent_integrals_and_symmetry(k):
    force, direct = incident_force(k)
    low, _ = incident_force(k, order=24)
    np.testing.assert_allclose(force, direct, rtol=1e-11, atol=1e-10)
    np.testing.assert_allclose(force, low, rtol=1e-11, atol=1e-10)
    assert abs(force[0].imag) < 1e-10
    assert abs(force[1].real) < 1e-10


def test_origin_changes_phase_and_moment_not_physics():
    k, shift = 1.2, .3
    a, _ = incident_force(k)
    b, _ = incident_force(k, origin=1.5+shift)
    np.testing.assert_allclose(b, np.exp(-1j*k*shift)*np.array([a[0], a[1]+shift*a[0]]))


@pytest.mark.parametrize('kwargs', [{'k': -1.}, {'k': np.nan}, {'k': 1., 'order': 7},
                                   {'k': 1., 'draft': 0.}])
def test_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        incident_force(**kwargs)
