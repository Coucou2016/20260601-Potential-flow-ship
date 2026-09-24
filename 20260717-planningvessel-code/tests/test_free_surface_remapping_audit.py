import numpy as np
import pytest
from scripts.audit_free_surface_remapping import side_extrapolation


def test_detects_inner_and_outer_extrapolation_without_crossing_center_gap():
    old = np.array([-3., -2., -1., 1., 2., 3.])
    new = np.array([-3.1, -2.5, -.9, .9, 2.5, 3.1])
    inner, outer, distance = side_extrapolation(old, new)
    np.testing.assert_array_equal(inner, [False,False,True,True,False,False])
    np.testing.assert_array_equal(outer, [True,False,False,False,False,True])
    np.testing.assert_allclose(distance, [.1,0,.1,.1,0,.1])


def test_bad_grid_rejected():
    with pytest.raises(ValueError):
        side_extrapolation([-2.,-1.,1.,2.], [-1.,np.nan,1.])


def test_small_but_nonzero_grid_motion_is_not_silently_skipped():
    from dataclasses import replace
    from planing_seakeeping.kernels.linear_2p5d.formulation import initialize_free_surface_state, resample_free_surface_state
    old = np.array([-4., -3., -2., -1., 1., 2., 3., 4.])
    new = old.copy()
    new[[1,2,5,6]] += 1e-7
    assert np.allclose(old, new)
    state = initialize_free_surface_state(old, np.zeros(8), dt_s=.1)
    state = replace(state, potential_m2_s=(1+2j)*old)
    result = resample_free_surface_state(state, new)
    np.testing.assert_array_equal(result.y_m, new)
    np.testing.assert_allclose(result.potential_m2_s, (1+2j)*new, atol=1e-14, rtol=1e-14)
    assert resample_free_surface_state(state, old) is state
