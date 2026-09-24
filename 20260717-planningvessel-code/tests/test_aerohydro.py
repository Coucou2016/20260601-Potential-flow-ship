import numpy as np
import pytest
from planing_seakeeping.aerohydro import (
    LinearAircraftPolar, longitudinal_air_load, relative_velocity_body,
    force_at_point, aircraft_to_longitudinal_load,
)


def polar():
    return LinearAircraftPolar(10., 1., .5, 4., .02, .05, 0., 0., .2, "synthetic algebraic test, not aircraft data")


def test_air_water_relative_speeds_are_distinct():
    np.testing.assert_allclose(relative_velocity_body([20,0,0],[-5,0,0],np.eye(3)), [25,0,0])
    np.testing.assert_allclose(relative_velocity_body([20,0,0],[2,0,0],np.eye(3)), [18,0,0])


def test_reject_reflection():
    with pytest.raises(ValueError):
        relative_velocity_body([20,0,0],[0,0,0],np.diag([1,1,-1]))


def test_dynamic_pressure_scaling_and_moment_arm():
    load = longitudinal_air_load(polar(), [10,0,0], 1.2, [2,0,0])
    np.testing.assert_allclose(aircraft_to_longitudinal_load(load.tau), [300,600])
    np.testing.assert_allclose(longitudinal_air_load(polar(), [20,0,0], 1.2, [2,0,0]).tau, 4*load.tau)
    np.testing.assert_allclose(sum(load.components.values()), load.tau)
    assert not load.validity.is_validated


def test_drag_dissipates_and_lift_is_normal_to_flow():
    velocity = np.array([10.,0.,1.])
    load = longitudinal_air_load(polar(), velocity, 1.2)
    assert np.dot(load.components["air_drag"][:3], velocity) < 0
    assert abs(np.dot(load.components["air_lift"][:3], velocity)) < 1e-10


@pytest.mark.parametrize("velocity", [[10,1,0],[-10,0,0],[1,0,1]])
def test_reject_unsupported_flow(velocity):
    with pytest.raises(ValueError):
        longitudinal_air_load(polar(), velocity, 1.2)


def test_zero_airspeed_and_force_arm():
    np.testing.assert_allclose(longitudinal_air_load(polar(), [0,0,0], 1.2).tau, 0)
    np.testing.assert_allclose(force_at_point([1,0,0],[0,0,2]), [1,0,0,0,2,0])
