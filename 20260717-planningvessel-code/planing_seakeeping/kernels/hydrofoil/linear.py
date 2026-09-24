from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class HydrofoilGeometry:
    area_m2: float
    aspect_ratio: float
    reference_point_body_m: tuple[float, float, float]
    oswald_efficiency: float = 0.85
    zero_lift_alpha_rad: float = 0.0
    flap_lift_effectiveness: float = 0.0

    def validate(self) -> None:
        if self.area_m2 <= 0.0:
            raise ValueError("Hydrofoil area_m2 must be positive.")
        if self.aspect_ratio <= 0.0:
            raise ValueError("Hydrofoil aspect_ratio must be positive.")
        if not 0.0 < self.oswald_efficiency <= 1.0:
            raise ValueError("Hydrofoil oswald_efficiency must lie in (0, 1].")


@dataclass(frozen=True)
class HydrofoilState:
    speed_mps: float
    alpha_rad: float
    flap_rad: float = 0.0
    water_density_kg_m3: float = 1025.0


def finite_wing_lift_slope(aspect_ratio: float) -> float:
    """Finite-wing lift slope for a first-stage low-angle hydrofoil model."""

    if aspect_ratio <= 0.0:
        raise ValueError("aspect_ratio must be positive.")
    return 2.0 * math.pi * aspect_ratio / (aspect_ratio + 2.0)


def hydrofoil_force(geometry: HydrofoilGeometry, state: HydrofoilState) -> tuple[np.ndarray, np.ndarray]:
    """Return body-axis force and moment for the linear finite-wing foil model.

    This first-stage model is suitable for controller plumbing and small-angle
    checks only. It does not model free-surface proximity, ventilation, cavitation,
    strut effects, or nonlinear stall.
    """

    geometry.validate()
    q = 0.5 * state.water_density_kg_m3 * state.speed_mps**2
    lift_slope = finite_wing_lift_slope(geometry.aspect_ratio)
    alpha_eff = state.alpha_rad - geometry.zero_lift_alpha_rad + geometry.flap_lift_effectiveness * state.flap_rad
    cl = lift_slope * alpha_eff
    cdi = cl**2 / (math.pi * geometry.oswald_efficiency * geometry.aspect_ratio)
    lift = q * geometry.area_m2 * cl
    drag = q * geometry.area_m2 * cdi
    force = np.asarray([-drag, 0.0, lift], dtype=float)
    moment = np.cross(np.asarray(geometry.reference_point_body_m, dtype=float), force)
    return force, moment


def routh_hurwitz_quartic(coefficients: tuple[float, float, float, float, float]) -> dict[str, object]:
    """Routh-Hurwitz stability test for a fourth-order polynomial.

    Coefficients are ordered as (a0, a1, a2, a3, a4) for
    a0*s^4 + a1*s^3 + a2*s^2 + a3*s + a4.
    """

    a0, a1, a2, a3, a4 = (float(value) for value in coefficients)
    if a0 <= 0.0:
        return {"stable": False, "reason": "leading coefficient must be positive"}
    normalized = (a1 / a0, a2 / a0, a3 / a0, a4 / a0)
    b1, b2, b3, b4 = normalized
    positive = all(value > 0.0 for value in normalized)
    determinant = b1 * b2 * b3 - b3**2 - b1**2 * b4
    return {
        "stable": bool(positive and determinant > 0.0),
        "positive_coefficients": bool(positive),
        "determinant_margin": determinant,
        "normalized_coefficients": normalized,
    }
