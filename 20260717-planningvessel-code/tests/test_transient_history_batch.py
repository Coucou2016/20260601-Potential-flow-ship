import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    build_control_surface_geometry, build_transient_free_surface_history,
    _transient_green_matrices_for_lag,
)


@pytest.mark.parametrize('count,quadrature,cutoff',[(8,16,12.),(16,32,25.),(24,64,50.)])
def test_batched_history_matches_original_lagwise_quadrature(count,quadrature,cutoff):
    geometry=build_control_surface_geometry(radius_m=1.27,panel_count=count)
    result=build_transient_free_surface_history(geometry,.013,9,
        quadrature_count=quadrature,k_max=cutoff)
    for i,lag in enumerate(result.lag_s):
        green,normal=_transient_green_matrices_for_lag(geometry,geometry,lag,
            gravity_m_s2=9.80665,quadrature_count=quadrature,k_max=cutoff)
        np.testing.assert_allclose(result.green_potential[i],green,rtol=1e-12,atol=1e-13)
        np.testing.assert_allclose(result.green_normal_derivative[i],normal,rtol=1e-12,atol=1e-13)
