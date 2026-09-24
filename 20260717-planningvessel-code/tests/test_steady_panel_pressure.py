import numpy as np
import pytest
from scripts.compare_steady_panel_pressure import compare, localize


def field(nodes, pressure):
    return dict(symmetry_multiplier=2, panel_labels=np.array(['body']*len(pressure)),
        node_y_m=np.array(nodes), pressure_pa=np.array(pressure),
        transverse_velocity_mps=np.zeros((len(pressure), 2)))


def test_exact_overlap_not_interpolated():
    a = field([0., 1., 2.], [0., 2.])
    b = field([0., .5, 2.], [0., 2.])
    rms, maximum, coverage = compare(a, b)
    np.testing.assert_allclose(rms, [1., 0., 0.])
    np.testing.assert_allclose(maximum, [2., 0., 0.])
    assert coverage == 1.


def test_partial_coverage_is_reported():
    rms, _, coverage = compare(field([0., 1.], [2.]), field([.5, 1.5], [2.]))
    np.testing.assert_array_equal(rms, [0., 0., 0.])
    assert coverage == pytest.approx(1/3)


def test_disjoint_rejected():
    with pytest.raises(ValueError, match='No common'):
        compare(field([0., 1.], [2.]), field([2., 3.], [2.]))


def test_peak_location_uses_overlap_not_panel_centre():
    result = localize(field([0., 1., 2.], [0., 2.]), field([0., .5, 2.], [0., 2.]))[0]
    assert result['coarse_sorted_panel'] == 0
    assert result['fine_sorted_panel'] == 1
    assert result['overlap_left_m'] == .5
    assert result['overlap_right_m'] == 1.
    assert result['difference'] == -2.
    assert result['coarse_span_fraction'] == .375
