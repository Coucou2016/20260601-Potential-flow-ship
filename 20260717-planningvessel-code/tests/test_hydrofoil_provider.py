from dataclasses import replace
import math

import numpy as np
import pytest

from planing_seakeeping.kernels.hydrofoil.linear import HydrofoilGeometry, HydrofoilState
from planing_seakeeping.providers.hydrofoil import (
    BODY_COORDINATE_CONVENTION,
    LinearFiniteWingHydrofoilProvider,
    MAX_SMALL_ANGLE_RAD,
)


def _geometry() -> HydrofoilGeometry:
    return HydrofoilGeometry(area_m2=0.12, aspect_ratio=5.0, reference_point_body_m=(2.0, 0.0, -0.2))


def _provider(**kwargs) -> LinearFiniteWingHydrofoilProvider:
    return LinearFiniteWingHydrofoilProvider(_geometry(), source="synthetic unit-test geometry", **kwargs)


def test_zero_attack_angle_gives_zero_load() -> None:
    result = _provider().load(HydrofoilState(speed_mps=8.0, alpha_rad=0.0))
    np.testing.assert_array_equal(result.tau, np.zeros(6))
    assert not result.validity.is_validated


def test_nonzero_lift_moment_arm_and_longitudinal_conversion() -> None:
    provider = _provider()
    state = HydrofoilState(speed_mps=8.0, alpha_rad=0.04)
    result = provider.load(state)
    expected_lift = 0.5 * 1025.0 * 8.0**2 * 0.12 * (2.0 * math.pi * 5.0 / 7.0) * 0.04
    assert result.tau[2] == pytest.approx(expected_lift)
    assert result.tau[0] < 0.0
    np.testing.assert_allclose(result.tau[3:], np.cross(_geometry().reference_point_body_m, result.tau[:3]))
    np.testing.assert_allclose(sum(result.components.values()), result.tau)
    longitudinal = provider.load_heave_up_pitch_bow_up(state)
    np.testing.assert_allclose(longitudinal, [result.tau[2], -result.tau[4]])
    assert longitudinal[1] > 0.0
    assert any(BODY_COORDINATE_CONVENTION in note for note in result.validity.notes)
    assert any("synthetic unit-test geometry" in note for note in result.validity.notes)
    assert any("kernel_source=" in note for note in result.validity.notes)


@pytest.mark.parametrize("name,value", [
    ("area_m2", 0.0), ("area_m2", -1.0), ("area_m2", np.nan),
    ("aspect_ratio", 0.0), ("aspect_ratio", np.inf),
    ("oswald_efficiency", 0.0), ("oswald_efficiency", 1.1), ("oswald_efficiency", np.nan),
    ("zero_lift_alpha_rad", np.nan), ("zero_lift_alpha_rad", 0.2),
    ("flap_lift_effectiveness", 0.4), ("flap_lift_effectiveness", np.nan),
    ("reference_point_body_m", (0.0, np.nan, 0.0)),
    ("reference_point_body_m", (0.0, 0.0)),
])
def test_invalid_geometry_is_rejected(name: str, value) -> None:
    with pytest.raises(ValueError):
        LinearFiniteWingHydrofoilProvider(replace(_geometry(), **{name: value}), source="test")


@pytest.mark.parametrize("name,value", [
    ("speed_mps", 0.0), ("speed_mps", -1.0), ("speed_mps", np.nan), ("speed_mps", np.inf),
    ("speed_mps", "8.0"), ("speed_mps", True), ("speed_mps", np.asarray([8.0])),
    ("water_density_kg_m3", 0.0), ("water_density_kg_m3", -1.0), ("water_density_kg_m3", np.nan),
    ("alpha_rad", np.nan), ("alpha_rad", np.inf),
    ("alpha_rad", MAX_SMALL_ANGLE_RAD + 1e-6), ("alpha_rad", -MAX_SMALL_ANGLE_RAD - 1e-6),
    ("flap_rad", 0.01), ("flap_rad", np.nan),
])
def test_invalid_state_is_rejected(name: str, value) -> None:
    state = replace(HydrofoilState(speed_mps=8.0, alpha_rad=0.04), **{name: value})
    with pytest.raises(ValueError):
        _provider().load(state)


def test_effective_angle_domain_and_boundary() -> None:
    provider = LinearFiniteWingHydrofoilProvider(
        replace(_geometry(), zero_lift_alpha_rad=-0.04), source="test",
    )
    with pytest.raises(ValueError, match="applicability"):
        provider.load(HydrofoilState(speed_mps=8.0, alpha_rad=0.06))
    assert _provider().load(HydrofoilState(speed_mps=8.0, alpha_rad=MAX_SMALL_ANGLE_RAD)).tau[2] > 0.0


@pytest.mark.parametrize("source", ["", "  ", None])
def test_source_is_required(source) -> None:
    with pytest.raises(ValueError, match="source"):
        LinearFiniteWingHydrofoilProvider(_geometry(), source=source)


def test_coordinate_and_production_contracts_are_guarded() -> None:
    with pytest.raises(ValueError, match="coordinate_convention"):
        _provider(coordinate_convention="x_forward_y_starboard_z_down")
    with pytest.raises(ValueError, match="production"):
        _provider(production=True)
    capabilities = _provider().capabilities
    assert not capabilities.production
    assert not capabilities.six_dof
    assert not capabilities.hydrofoil_control
    assert not capabilities.nonlinear_free_surface
    assert capabilities.validated_benchmarks == ()
    with pytest.raises(ValueError):
        capabilities.require_production_ready()


def test_finite_inputs_that_overflow_load_are_rejected() -> None:
    with pytest.raises(ValueError, match="overflow|finite"):
        _provider().load(HydrofoilState(speed_mps=1e308, alpha_rad=0.04))
