import numpy as np
import pytest
from scripts.kang_reference_geometry import build_hull, half_breadth
from planing_seakeeping.kernels.linear_2p5d.formulation import _station_offsets_for_matched_2p5d


def test_geometry_symmetry_and_tip():
    z = np.linspace(0, .1875, 21)
    np.testing.assert_allclose(half_breadth(.7,z,3,.3,.1875), half_breadth(2.3,z,3,.3,.1875))
    np.testing.assert_array_equal(half_breadth(0,z,3,.3,.1875), np.zeros(21))


def test_offsets_override_parametric_fallback():
    s = build_hull(9, 21, moment_reference_x=1.5).stations[4]
    actual = _station_offsets_for_matched_2p5d(s, parametric_section_shape='unsupported', point_count_per_side=5)
    np.testing.assert_array_equal(actual.y_m, np.array(s.offset_points_m)[:,0])
    assert actual.y_m[0] > 0 and actual.y_m[-1] < 0
    assert actual.z_down_m[0] == actual.z_down_m[-1] == 0


def test_geometry_converges_without_area_overrides():
    exact = 29144/51975*3*.3*.1875
    errors = [abs(build_hull(n,n,moment_reference_x=1.5).hydrostatics().displacement_volume_m3/exact-1) for n in (21,41,81)]
    assert errors[2] < errors[1] < errors[0]
    assert errors[2] < .001


def test_reference_required():
    with pytest.raises(ValueError, match='reference'):
        build_hull(9, 21)
