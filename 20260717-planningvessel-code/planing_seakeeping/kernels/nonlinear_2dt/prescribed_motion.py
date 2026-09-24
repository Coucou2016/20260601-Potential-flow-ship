from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from ...forced_motion_identification import ForcedMotionColumn, MotionDof, extract_forced_motion_column
from ...station_2p5d import StationHull


PRESCRIBED_MOTION_CONTRACT_STATUS = (
    "sun_faltinsen_2dt_prescribed_motion_orchestration_section_bem_pending"
)


@dataclass(frozen=True)
class PrescribedMotion2DtCase:
    """One Sun--Faltinsen forced-heave or forced-pitch calculation.

    The hull longitudinal coordinate is measured forward from the transom.
    Heave is positive upward and pitch is positive bow-up. Forced motion uses
    ``eta_j=-eta_ja*sin(omega*t)`` as in Sun (2007), Eqs. (7.27)-(7.28).
    """

    hull: StationHull
    speed_mps: float
    mean_trim_rad: float
    motion_dof: MotionDof
    motion_amplitude: float
    omega_rad_s: float
    duration_s: float
    time_step_s: float
    rho_water_kg_m3: float = 1025.0
    gravity_m_s2: float = 9.80665
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.motion_dof not in ("heave", "pitch"):
            raise ValueError("motion_dof must be heave or pitch.")
        positive = {
            "speed_mps": self.speed_mps,
            "motion_amplitude": self.motion_amplitude,
            "omega_rad_s": self.omega_rad_s,
            "duration_s": self.duration_s,
            "time_step_s": self.time_step_s,
            "rho_water_kg_m3": self.rho_water_kg_m3,
            "gravity_m_s2": self.gravity_m_s2,
        }
        for name, value in positive.items():
            if not np.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{name} must be finite and positive.")
        if not np.isfinite(float(self.mean_trim_rad)):
            raise ValueError("mean_trim_rad must be finite.")
        period = 2.0 * np.pi / float(self.omega_rad_s)
        if float(self.duration_s) < 2.0 * period:
            raise ValueError("duration_s must cover at least two forced-motion periods.")
        if float(self.time_step_s) > period / 16.0:
            raise ValueError("time_step_s must provide at least 16 steps per period.")
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def period_s(self) -> float:
        return float(2.0 * np.pi / self.omega_rad_s)

    @property
    def time_s(self) -> np.ndarray:
        step_count = int(np.ceil(self.duration_s / self.time_step_s))
        return np.linspace(0.0, step_count * self.time_step_s, step_count + 1)


@dataclass(frozen=True)
class PrescribedMotionKinematics:
    """Global and station-local kinematics for one prescribed-motion case."""

    time_s: np.ndarray
    station_x_from_transom_m: np.ndarray
    station_x_from_cg_m: np.ndarray
    heave_m: np.ndarray
    heave_velocity_mps: np.ndarray
    heave_acceleration_mps2: np.ndarray
    pitch_rad: np.ndarray
    pitch_rate_rad_s: np.ndarray
    pitch_acceleration_rad_s2: np.ndarray
    local_vertical_displacement_m: np.ndarray
    local_vertical_velocity_mps: np.ndarray
    local_vertical_acceleration_mps2: np.ndarray
    local_draft_m: np.ndarray
    relative_entry_velocity_mps: np.ndarray
    relative_entry_acceleration_mps2: np.ndarray

    def __post_init__(self) -> None:
        time = np.asarray(self.time_s, dtype=float)
        x = np.asarray(self.station_x_from_transom_m, dtype=float)
        x_cg = np.asarray(self.station_x_from_cg_m, dtype=float)
        if time.ndim != 1 or x.ndim != 1 or x_cg.shape != x.shape:
            raise ValueError("time and station coordinates must be one-dimensional arrays.")
        if len(time) < 2 or len(x) < 2 or np.any(np.diff(time) <= 0.0) or np.any(np.diff(x) <= 0.0):
            raise ValueError("time and station coordinates must be strictly increasing.")
        one_d_names = (
            "heave_m",
            "heave_velocity_mps",
            "heave_acceleration_mps2",
            "pitch_rad",
            "pitch_rate_rad_s",
            "pitch_acceleration_rad_s2",
        )
        two_d_names = (
            "local_vertical_displacement_m",
            "local_vertical_velocity_mps",
            "local_vertical_acceleration_mps2",
            "local_draft_m",
            "relative_entry_velocity_mps",
            "relative_entry_acceleration_mps2",
        )
        for name in one_d_names:
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != time.shape or not np.isfinite(value).all():
                raise ValueError(f"{name} must be finite with shape (n_time,).")
            object.__setattr__(self, name, value)
        expected = (len(time), len(x))
        for name in two_d_names:
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != expected or not np.isfinite(value).all():
                raise ValueError(f"{name} must be finite with shape {expected}.")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "time_s", time)
        object.__setattr__(self, "station_x_from_transom_m", x)
        object.__setattr__(self, "station_x_from_cg_m", x_cg)


def prescribed_motion_kinematics(case: PrescribedMotion2DtCase) -> PrescribedMotionKinematics:
    """Evaluate Sun (2007), Eqs. (7.27)-(7.31), (7.43)-(7.44).

    Local displacement is positive upward. Local draft is positive downward,
    so an upward heave or a bow-up displacement at a forward station reduces
    immersion. The entry-velocity expressions retain the forward-speed pitch
    terms required by the 2D+t body condition.
    """

    time = case.time_s
    x = np.asarray([station.x_m for station in case.hull.stations], dtype=float)
    x_cg = x - float(case.hull.lcg_m)
    phase = float(case.omega_rad_s) * time
    eta = -float(case.motion_amplitude) * np.sin(phase)
    eta_dot = -float(case.motion_amplitude) * float(case.omega_rad_s) * np.cos(phase)
    eta_ddot = float(case.motion_amplitude) * float(case.omega_rad_s) ** 2 * np.sin(phase)
    zero = np.zeros_like(time)
    if case.motion_dof == "heave":
        heave, heave_dot, heave_ddot = eta, eta_dot, eta_ddot
        pitch, pitch_dot, pitch_ddot = zero, zero, zero
    else:
        heave, heave_dot, heave_ddot = zero, zero, zero
        pitch, pitch_dot, pitch_ddot = eta, eta_dot, eta_ddot

    local_displacement = heave[:, None] + pitch[:, None] * x_cg[None, :]
    local_velocity = heave_dot[:, None] + pitch_dot[:, None] * x_cg[None, :]
    local_acceleration = heave_ddot[:, None] + pitch_ddot[:, None] * x_cg[None, :]
    mean_draft = np.asarray([station.effective_draft_m() for station in case.hull.stations], dtype=float)
    local_draft = mean_draft[None, :] - local_displacement
    trim = float(case.mean_trim_rad)
    speed = float(case.speed_mps)
    relative_velocity = (
        speed * np.sin(trim)
        - local_velocity
        + speed * pitch[:, None] * np.cos(trim)
    )
    relative_acceleration = (
        -local_acceleration
        + 2.0 * speed * pitch_dot[:, None] * np.cos(trim)
    )
    return PrescribedMotionKinematics(
        time_s=time,
        station_x_from_transom_m=x,
        station_x_from_cg_m=x_cg,
        heave_m=heave,
        heave_velocity_mps=heave_dot,
        heave_acceleration_mps2=heave_ddot,
        pitch_rad=pitch,
        pitch_rate_rad_s=pitch_dot,
        pitch_acceleration_rad_s2=pitch_ddot,
        local_vertical_displacement_m=local_displacement,
        local_vertical_velocity_mps=local_velocity,
        local_vertical_acceleration_mps2=local_acceleration,
        local_draft_m=local_draft,
        relative_entry_velocity_mps=relative_velocity,
        relative_entry_acceleration_mps2=relative_acceleration,
    )


@dataclass(frozen=True)
class SectionalLoadHistory:
    """Sectional pressure-resultant history supplied by a 2D BEM kernel."""

    time_s: np.ndarray
    station_x_from_transom_m: np.ndarray
    vertical_force_per_length_n_m: np.ndarray
    potential_bvp_relative_residual: np.ndarray
    pressure_bvp_relative_residual: np.ndarray
    condition_number: np.ndarray
    generalized_correction_load: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        time = np.asarray(self.time_s, dtype=float)
        x = np.asarray(self.station_x_from_transom_m, dtype=float)
        expected = (len(time), len(x))
        if time.ndim != 1 or x.ndim != 1 or len(time) < 2 or len(x) < 2:
            raise ValueError("Sectional load history requires one-dimensional time and station grids.")
        if np.any(np.diff(time) <= 0.0) or np.any(np.diff(x) <= 0.0):
            raise ValueError("Sectional load history grids must be strictly increasing.")
        for name in (
            "vertical_force_per_length_n_m",
            "potential_bvp_relative_residual",
            "pressure_bvp_relative_residual",
            "condition_number",
        ):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != expected or not np.isfinite(value).all():
                raise ValueError(f"{name} must be finite with shape {expected}.")
            object.__setattr__(self, name, value)
        correction = self.generalized_correction_load
        if correction is None:
            correction_array = np.zeros((len(time), 2), dtype=float)
        else:
            correction_array = np.asarray(correction, dtype=float)
            if correction_array.shape != (len(time), 2) or not np.isfinite(correction_array).all():
                raise ValueError("generalized_correction_load must be finite with shape (n_time, 2).")
        object.__setattr__(self, "time_s", time)
        object.__setattr__(self, "station_x_from_transom_m", x)
        object.__setattr__(self, "generalized_correction_load", correction_array)
        object.__setattr__(self, "metadata", dict(self.metadata))


class PrescribedMotionSectionSolver(Protocol):
    """Protocol implemented by the nonlinear cross-plane BEM time marcher."""

    def solve(
        self,
        case: PrescribedMotion2DtCase,
        kinematics: PrescribedMotionKinematics,
    ) -> SectionalLoadHistory:
        ...


def integrate_sectional_generalized_load(
    history: SectionalLoadHistory,
    *,
    lcg_from_transom_m: float,
) -> np.ndarray:
    """Integrate sectional vertical load into heave force and bow-up moment."""

    x = history.station_x_from_transom_m
    lever = x - float(lcg_from_transom_m)
    force = np.trapezoid(history.vertical_force_per_length_n_m, x, axis=1)
    moment = np.trapezoid(history.vertical_force_per_length_n_m * lever[None, :], x, axis=1)
    generalized = np.column_stack((force, moment))
    return generalized + np.asarray(history.generalized_correction_load, dtype=float)


@dataclass(frozen=True)
class PrescribedMotion2DtResult:
    case: PrescribedMotion2DtCase
    kinematics: PrescribedMotionKinematics
    sectional_load_history: SectionalLoadHistory
    generalized_load: np.ndarray
    forced_motion_column: ForcedMotionColumn
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        loads = np.asarray(self.generalized_load, dtype=float)
        expected = (len(self.kinematics.time_s), 2)
        if loads.shape != expected or not np.isfinite(loads).all():
            raise ValueError(f"generalized_load must be finite with shape {expected}.")
        object.__setattr__(self, "generalized_load", loads)
        object.__setattr__(self, "metadata", dict(self.metadata))


def solve_prescribed_motion_case(
    case: PrescribedMotion2DtCase,
    section_solver: PrescribedMotionSectionSolver,
    *,
    restoring_column: np.ndarray,
    discard_cycles: float = 1.0,
    retained_cycles: float | None = None,
    fitted_harmonics: int = 3,
) -> PrescribedMotion2DtResult:
    """Run one prescribed-motion case and identify one hydrodynamic column."""

    kinematics = prescribed_motion_kinematics(case)
    history = section_solver.solve(case, kinematics)
    if not np.allclose(history.time_s, kinematics.time_s, rtol=0.0, atol=1e-12):
        raise ValueError("Section solver time grid does not match the prescribed-motion case.")
    if not np.allclose(
        history.station_x_from_transom_m,
        kinematics.station_x_from_transom_m,
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError("Section solver station grid does not match the prescribed-motion hull.")
    generalized = integrate_sectional_generalized_load(
        history,
        lcg_from_transom_m=case.hull.lcg_m,
    )
    column = extract_forced_motion_column(
        kinematics.time_s,
        generalized,
        motion_dof=case.motion_dof,
        omega_rad_s=case.omega_rad_s,
        motion_amplitude=case.motion_amplitude,
        restoring_column=np.asarray(restoring_column, dtype=float),
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=fitted_harmonics,
    )
    metadata = {
        "status": PRESCRIBED_MOTION_CONTRACT_STATUS,
        "source": "Sun_2007_Eq7.23_to_7.47",
        "coordinate_convention": "heave_up_pitch_bow_up_x_forward_from_transom",
        "load_order": "vertical_force_bow_up_pitch_moment",
        "section_solver": history.metadata.get("solver", "unspecified"),
        "response_calibration_used": False,
        **case.metadata,
    }
    return PrescribedMotion2DtResult(
        case=case,
        kinematics=kinematics,
        sectional_load_history=history,
        generalized_load=generalized,
        forced_motion_column=column,
        metadata=metadata,
    )
