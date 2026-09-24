import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.formulation import build_waterline_clipped_free_surface_geometry as build


@pytest.mark.parametrize('count',[48,72,96])
def test_graded_geometry(count):
    g=build(-3,3,.2,count,grading_exponent=1.5)
    np.testing.assert_allclose(g.mid_y_m,-g.mid_y_m[::-1],atol=1e-14)
    np.testing.assert_allclose(g.length_m,g.length_m[::-1],atol=1e-14)
    assert np.all(g.length_m>0)
    np.testing.assert_allclose(g.length_m.sum(),5.6)
    right=g.length_m[count//2:]
    assert np.all(np.diff(right)>0)
    np.testing.assert_allclose(right[0],2.8/(count//2)**1.5)
    assert np.all(np.abs(g.mid_y_m)>.2)


def test_uniform_default_unchanged():
    a=build(-3,3,.2,72)
    b=build(-3,3,.2,72,grading_exponent=1.)
    np.testing.assert_array_equal(a.node_y_m,b.node_y_m)


@pytest.mark.parametrize('value',[0.,.9,2.1,np.nan,np.inf])
def test_bad_exponent(value):
    with pytest.raises(ValueError,match='grading_exponent'):
        build(-3,3,.2,72,grading_exponent=value)
