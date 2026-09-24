import numpy as np
import pytest

from scripts.replay_steady_surface_loads import integrate_exported_pressure, validate_indices


def test_physical_panels_only_and_symmetry():
    labels = ['body', 'artificial_body', 'free', 'body']
    pressure = [10., 900., 800., 20.]
    normals = np.array([[0., 1.], [0., 1.], [0., 1.], [0., -1.]])
    lengths = [2., 1., 1., .5]
    assert integrate_exported_pressure(labels, pressure, normals, lengths, False) == 10.
    assert integrate_exported_pressure(labels, pressure, normals, lengths, True) == 20.


@pytest.mark.parametrize('indices', [[], [0, 0], [-1], [3], [0.5], [True]])
def test_invalid_indices_rejected(indices):
    with pytest.raises(ValueError):
        validate_indices(indices, 3)


def test_valid_indices():
    validate_indices([0, 2], 3)


@pytest.mark.parametrize('labels,pressure,normals,lengths', [
    (['body'], [np.nan], [[0., 1.]], [1.]),
    (['body'], [1.], [[0., 1.]], [0.]),
    (['body'], [1., 2.], [[0., 1.]], [1.]),
    (['artificial_body'], [1.], [[0., 1.]], [1.]),
])
def test_invalid_panel_fields_rejected(labels, pressure, normals, lengths):
    with pytest.raises(ValueError):
        integrate_exported_pressure(labels, pressure, normals, lengths, False)
