import numpy as np
import pytest
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.planing_frequency_correction import apply_transom_sectional_force_cutoff


@pytest.mark.parametrize("cutoff", [0., .212, .5, 1.])
def test_affine_complex_integral(cutoff):
    x = np.array([0., .1, .5, 1.])
    y = 2+3j+(4-2j)*x
    expected = (2+3j)*(1-cutoff)+(4-2j)*(1-cutoff**2)/2
    np.testing.assert_allclose(clipped_piecewise_linear_integral(x,y,cutoff),expected,atol=1e-14)


def test_radiation_cutoff_preserves_fixed_support_and_end_load():
    x=np.array([[0., .25, .5, 1.]])
    density=np.ones((1,4,2,2),complex)*(2+1j)
    end=np.ones((1,2,2),complex)
    _, corrected_end, total, _=apply_transom_sectional_force_cutoff(
        station_x_m=x,force_density_by_station=density,end_force_matrices=end,
        end_station_x_m=np.array([1.]),cutoff_length_m=.3,cutoff_quadrature="clipped_linear")
    np.testing.assert_allclose(total,(2+1j)*.7+1)
    np.testing.assert_allclose(corrected_end,end)


def test_invalid_stations_rejected():
    with pytest.raises(ValueError):
        clipped_piecewise_linear_integral([0,0,1],[1,2,3],.2)
