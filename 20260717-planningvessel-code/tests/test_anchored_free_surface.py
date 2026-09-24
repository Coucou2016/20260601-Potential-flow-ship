import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.anchored_free_surface import build_anchored_free_surface


def test_outer_nodes_stay_fixed_and_no_zero_panels_at_maximum_beam():
    a=build_anchored_free_surface(.9,.15,.05,20,44)
    b=build_anchored_free_surface(.9,.15,.15,20,44)
    np.testing.assert_array_equal(a.mid_y_m[abs(a.mid_y_m)>.15],b.mid_y_m)
    assert b.panel_count==88 and a.panel_count>b.panel_count
    assert min(a.length_m)>0 and min(b.length_m)>0


@pytest.mark.parametrize('half',[0.,.03,.071,.15])
def test_symmetry_and_domain_length(half):
    grid=build_anchored_free_surface(.9,.15,half,20,44)
    np.testing.assert_allclose(grid.mid_y_m,-grid.mid_y_m[::-1])
    assert sum(grid.length_m)==pytest.approx(2*(.9-half))
    assert np.all(abs(grid.mid_y_m)>half)


def test_out_of_envelope_is_rejected():
    with pytest.raises(ValueError):
        build_anchored_free_surface(.9,.15,.2,20,44)


def test_near_coincident_waterline_is_not_silently_snapped():
    with pytest.raises(ValueError,match='resolution'):
        build_anchored_free_surface(.9,.15,np.nextafter(.15,0.),20,44)
