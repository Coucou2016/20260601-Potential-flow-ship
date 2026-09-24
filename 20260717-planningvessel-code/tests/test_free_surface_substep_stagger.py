import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    initialize_free_surface_state, advance_free_surface_state_with_substeps,
)


@pytest.mark.parametrize('substeps', [1,2,4,8])
@pytest.mark.parametrize('direction', [1.,-1.])
def test_constant_velocity_subdivision_preserves_staggered_physics(substeps,direction):
    y=np.array([-1.,1.])
    state=initialize_free_surface_state(y,np.zeros(2),dt_s=1.,gravity_m_s2=1.,time_direction_sign=direction)
    result=advance_free_surface_state_with_substeps(state,y,np.full(2,2.),dt_s=1.,
        gravity_m_s2=1.,time_direction_sign=direction,substeps_per_station=substeps)
    np.testing.assert_allclose(result.elevation_m,2*direction,atol=1e-13)
    np.testing.assert_allclose(result.potential_m2_s,-2.,atol=1e-13)
    assert result.time_s == 2*direction
    assert result.half_step_time_s == 1.5*direction


@pytest.mark.parametrize('substeps', [1,2,4,8])
def test_initial_constant_velocity_has_exact_potential_and_common_half_level(substeps):
    y=np.array([-1.,1.])
    result=advance_free_surface_state_with_substeps(None,y,np.full(2,2.),dt_s=1.,
        gravity_m_s2=1.,substeps_per_station=substeps)
    np.testing.assert_allclose(result.elevation_m,1.,atol=1e-13)
    np.testing.assert_allclose(result.potential_m2_s,-1.,atol=1e-13)
    assert result.time_s == 1.
    assert result.half_step_time_s == .5
