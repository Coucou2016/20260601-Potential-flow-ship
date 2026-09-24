import numpy as np
import pytest
from scripts.audit_free_surface_fields import common_side_samples


def test_no_interpolation_across_gap_or_extrapolation():
    y=np.array([-4.,-2.5,-1.5,-.1,.1,1.5,2.5,4.])
    fy=np.array([-3.,-2.,-1.,1.,2.,3.])
    function=lambda x:(2+3j)*x+np.where(x<0,20.,-10.)
    indices,values=common_side_samples(y,function(y),fy,function(fy))
    np.testing.assert_array_equal(indices,[1,2,5,6])
    np.testing.assert_allclose(values,function(y[indices]))


def test_nonfinite_field_rejected():
    with pytest.raises(ValueError,match='Finite'):
        common_side_samples(np.array([-1.,1.]),np.array([np.nan,1]),np.array([-2.,-1.,1.,2.]),np.ones(4))


def test_exact_common_station_selection():
    from scripts.audit_free_surface_fields import common_station_pairs
    assert common_station_pairs(np.linspace(0,1,5),np.linspace(0,1,7))==[(0,0),(2,3),(4,6)]
    with pytest.raises(ValueError,match='three common'):
        common_station_pairs(np.array([0.,.2,1.]),np.array([0.,.3,1.]))


def test_clock_shift_allowed_but_drift_rejected():
    from scripts.audit_free_surface_fields import clock_origin_offset
    t=np.array([.1,.2,.3])
    assert clock_origin_offset(t,t-.04)==pytest.approx(-.04)
    with pytest.raises(ValueError,match='constant origin'):
        clock_origin_offset(t,np.array([.06,.16,.27]))
