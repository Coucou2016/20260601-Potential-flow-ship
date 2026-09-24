"""Isolated aircraft load primitives; no validated takeoff/landing solver.

Aircraft body frame: x forward, y starboard, z down (right handed).
Do not add these vectors to marine-frame loads without an explicit transform.
"""
from dataclasses import dataclass
import numpy as np

from .types import HydroLoadResult, ValidityReport


def _vector(value, name):
    v = np.asarray(value, dtype=float)
    if v.shape != (3,) or not np.isfinite(v).all():
        raise ValueError(f"{name} must be a finite three-vector")
    return v


def relative_velocity_body(vehicle_velocity_earth, medium_velocity_earth, body_to_earth):
    """Use independently for air and water; both earth vectors must share a frame."""
    rotation = np.asarray(body_to_earth, dtype=float)
    if rotation.shape != (3, 3) or not np.isfinite(rotation).all():
        raise ValueError("body_to_earth must be a finite rotation matrix")
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-10, rtol=0) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-10, rtol=0):
        raise ValueError("body_to_earth must be a proper orthogonal rotation")
    return rotation.T @ (_vector(vehicle_velocity_earth, "vehicle velocity") - _vector(medium_velocity_earth, "medium velocity"))


def force_at_point(force_body, point_from_cg_body, intrinsic_moment_body=(0., 0., 0.)):
    force = _vector(force_body, "force")
    moment = _vector(intrinsic_moment_body, "moment") + np.cross(_vector(point_from_cg_body, "point"), force)
    return np.concatenate((force, moment))


@dataclass(frozen=True)
class LinearAircraftPolar:
    """User-supplied small-angle polar; stall and surface effects are excluded."""
    area_m2: float
    chord_m: float
    cl_zero: float
    cl_per_rad: float
    cd_zero: float
    induced_drag_factor: float
    cm_zero: float
    cm_per_rad: float
    alpha_limit_rad: float
    source: str

    def __post_init__(self):
        numbers = [v for k, v in vars(self).items() if k != "source"]
        if not np.isfinite(numbers).all() or min(self.area_m2, self.chord_m, self.alpha_limit_rad) <= 0:
            raise ValueError("Finite coefficients and positive geometry/domain required")
        if self.cd_zero < 0 or self.induced_drag_factor < 0 or self.alpha_limit_rad >= np.pi / 2:
            raise ValueError("Invalid drag coefficients or angle domain")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("Coefficient provenance is required")


def longitudinal_air_load(polar, relative_air_velocity_body, rho_air, point_from_cg_body=(0., 0., 0.)):
    velocity = _vector(relative_air_velocity_body, "relative air velocity")
    if not np.isfinite(rho_air) or rho_air <= 0:
        raise ValueError("Air density must be positive")
    if abs(velocity[1]) > 1e-10:
        raise ValueError("Sideslip is unsupported by the longitudinal polar")
    speed = float(np.linalg.norm(velocity))
    if speed == 0:
        return HydroLoadResult.zeros("Aircraft FRD frame; zero airspeed; unvalidated aerodynamic primitive")
    if velocity[0] <= 0:
        raise ValueError("Reverse inflow is outside this polar")
    alpha = float(np.arctan2(velocity[2], velocity[0]))
    if abs(alpha) > polar.alpha_limit_rad:
        raise ValueError("Angle of attack outside supplied polar domain; no stall extrapolation")
    cl = polar.cl_zero + polar.cl_per_rad * alpha
    cd = polar.cd_zero + polar.induced_drag_factor * cl**2
    cm = polar.cm_zero + polar.cm_per_rad * alpha
    q_area = .5 * rho_air * speed**2 * polar.area_m2
    drag_direction = -velocity / speed
    lift_direction = np.array([np.sin(alpha), 0., -np.cos(alpha)])
    drag = force_at_point(q_area * cd * drag_direction, point_from_cg_body)
    lift = force_at_point(q_area * cl * lift_direction, point_from_cg_body)
    moment = np.array([0., 0., 0., 0., q_area * polar.chord_m * cm, 0.])
    return HydroLoadResult(tau=drag + lift + moment,
        components={"air_drag": drag, "air_lift": lift, "air_intrinsic_moment": moment},
        validity=ValidityReport.unvalidated("Aircraft FRD; algebraic small-angle polar only", polar.source,
            "Not connected to a free-running water-entry or takeoff solver"))


def aircraft_to_longitudinal_load(tau_body):
    """FRD force/moment -> upward heave force, bow-up pitch moment about same CG."""
    tau = np.asarray(tau_body, dtype=float)
    if tau.shape != (6,) or not np.isfinite(tau).all():
        raise ValueError("Finite six-component FRD load required")
    return np.array([-tau[2], tau[4]])
