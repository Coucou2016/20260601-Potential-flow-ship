from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real

import numpy as np

from ..kernels.hydrofoil.linear import HydrofoilGeometry, HydrofoilState, hydrofoil_force
from ..types import HydroLoadResult, ModelCapabilities, ValidityReport


BODY_COORDINATE_CONVENTION = "x_forward_y_port_z_up_right_handed_moments_about_cg"
MAX_SMALL_ANGLE_RAD = math.radians(5.0)
KERNEL_SOURCE = "planing_seakeeping/kernels/hydrofoil/linear.py:hydrofoil_force"


def _finite_scalar(name: str, value: float) -> float:
    if not isinstance(value, Real) or isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a finite numeric scalar.")
    try:
        scalar = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite scalar.") from error
    if not math.isfinite(scalar):
        raise ValueError(f"{name} must be a finite scalar.")
    return scalar


@dataclass(frozen=True)
class LinearFiniteWingHydrofoilProvider:
    """Unvalidated, quasi-steady small-angle foil load, not a vessel solver.

    Geometry reference_point_body_m is the foil load point relative to the CG,
    in metres, in the declared right-handed x-forward/y-port/z-up body frame.
    tau is (Fx, Fy, Fz, Mx, My, Mz), in N and N*m. Positive lift acts along +z;
    drag acts along -x. No attitude rotation or moment-origin shift is implicit.
    source is a required provenance label for the caller's geometry/parameters;
    it is recorded, not treated as independently verified literature evidence.
    """

    geometry: HydrofoilGeometry
    source: str
    coordinate_convention: str = BODY_COORDINATE_CONVENTION
    production: bool = False

    def __post_init__(self) -> None:
        self._validate_geometry()

    def _validate_geometry(self) -> None:
        if self.production is not False:
            raise ValueError("The finite-wing hydrofoil provider cannot be production enabled.")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("A non-empty geometry/parameter source label is required.")
        if self.coordinate_convention != BODY_COORDINATE_CONVENTION:
            raise ValueError(f"coordinate_convention must be {BODY_COORDINATE_CONVENTION!r}.")
        if not isinstance(self.geometry, HydrofoilGeometry):
            raise ValueError("geometry must be HydrofoilGeometry.")
        for name in ("area_m2", "aspect_ratio", "oswald_efficiency"):
            value = _finite_scalar(name, getattr(self.geometry, name))
            if value <= 0.0:
                raise ValueError(f"{name} must be strictly positive.")
        if self.geometry.oswald_efficiency > 1.0:
            raise ValueError("oswald_efficiency must not exceed 1.")
        alpha_zero = _finite_scalar("zero_lift_alpha_rad", self.geometry.zero_lift_alpha_rad)
        if abs(alpha_zero) > MAX_SMALL_ANGLE_RAD:
            raise ValueError("zero_lift_alpha_rad lies outside the +/-5 degree applicability domain.")
        effectiveness = _finite_scalar("flap_lift_effectiveness", self.geometry.flap_lift_effectiveness)
        if effectiveness != 0.0:
            raise ValueError("Flap/control effectiveness is unsupported by this provider.")
        try:
            point = np.asarray(self.geometry.reference_point_body_m, dtype=float)
        except (TypeError, ValueError) as error:
            raise ValueError("reference_point_body_m must be a finite three-vector relative to CG.") from error
        if point.shape != (3,) or not np.isfinite(point).all():
            raise ValueError("reference_point_body_m must be a finite three-vector relative to CG.")

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            time_domain=True,
            six_dof=False,
            production=False,
            hydrofoil_control=False,
            validated_benchmarks=(),
            status="linear_finite_wing_hydrofoil_quasisteady_unvalidated",
            assumptions=(
                "Algebraic small-angle load only; no foil or vessel time-marching dynamics.",
                "Actual and zero-lift-relative attack angles must both lie within +/-5 degrees.",
                "No control, flap, actuator, free-surface, ventilation, cavitation, strut, or stall model.",
                "Six-component load storage does not imply a validated six-DOF hydrodynamic model.",
            ),
        )

    def load(self, state: HydrofoilState) -> HydroLoadResult:
        self._validate_geometry()
        if not isinstance(state, HydrofoilState):
            raise ValueError("state must be HydrofoilState.")
        for name in ("speed_mps", "water_density_kg_m3"):
            if _finite_scalar(name, getattr(state, name)) <= 0.0:
                raise ValueError(f"{name} must be strictly positive.")
        alpha = _finite_scalar("alpha_rad", state.alpha_rad)
        if abs(alpha) > MAX_SMALL_ANGLE_RAD or abs(alpha - self.geometry.zero_lift_alpha_rad) > MAX_SMALL_ANGLE_RAD:
            raise ValueError("Attack angle lies outside the +/-5 degree applicability domain.")
        if _finite_scalar("flap_rad", state.flap_rad) != 0.0:
            raise ValueError("Flap/control inputs are unsupported by this provider.")
        with np.errstate(over="ignore", invalid="ignore"):
            try:
                force, moment = hydrofoil_force(self.geometry, state)
            except OverflowError as error:
                raise ValueError("Finite-wing load overflowed; reduce the input magnitude.") from error
        tau = np.r_[force, moment]
        if not np.isfinite(tau).all():
            raise ValueError("Finite-wing load must remain finite.")
        arm = np.asarray(self.geometry.reference_point_body_m, dtype=float)
        lift_force = np.asarray([0.0, 0.0, force[2]])
        drag_force = np.asarray([force[0], 0.0, 0.0])
        return HydroLoadResult(
            tau=tau,
            components={
                "lift": np.r_[lift_force, np.cross(arm, lift_force)],
                "induced_drag": np.r_[drag_force, np.cross(arm, drag_force)],
            },
            validity=ValidityReport(
                status="not_validated",
                model_assumptions=self.capabilities.assumptions,
                notes=(
                    f"parameter_source={self.source.strip()}",
                    f"kernel_source={KERNEL_SOURCE}",
                    f"coordinate_convention={self.coordinate_convention}",
                    "Applicability bound is a conservative provider policy, not an experimental validation.",
                ),
            ),
        )

    def load_heave_up_pitch_bow_up(self, state: HydrofoilState) -> np.ndarray:
        """Return (F_heave_up, M_pitch_bow_up) = (Fz, -My), in N and N*m.

        In the right-handed z-up frame, a +z force forward of CG produces -My.
        This conversion is not a vessel-axis attitude transformation.
        """

        tau = self.load(state).tau
        return np.asarray([tau[2], -tau[4]])
