from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
import math
from typing import Any, Callable, Literal

import numpy as np

from ...forced_motion_identification import (
    FirstHarmonicFit,
    ForcedMotionColumn,
    ForcedMotionMatrices,
    assemble_forced_motion_matrices,
    extract_forced_motion_column,
    fit_periodic_harmonics,
)
from .moving_wedge import (
    MovingWedgeConfig,
    MovingWedgeContactExitError,
    MovingWedgeState,
    RegularIncidentWave2D,
    VerticalMotionLaw,
    advance_moving_wedge_rk4,
    initialize_moving_wedge_state,
    moving_wedge_load,
    run_steady_planing_wedge_entry,
)


PLANING_FORCED_MOTION_2DT_STATUS = (
    "sun_2dt_ground_plane_forced_motion_with_explicit_source_transom_modes"
)


@dataclass(frozen=True)
class PlaningForcedMotionCase:
    speed_mps: float
    mean_trim_rad: float
    wetted_length_m: float
    lcg_from_transom_m: float
    motion_dof: str
    motion_amplitude: float
    omega_rad_s: float
    duration_s: float
    time_step_s: float
    initial_draft_m: float
    ground_plane_interval_s: float | None = None
    ground_plane_handoff_mode: Literal[
        "fixed_earth_grid",
        "fixed_earth_grid_scheduled_wagner",
        "constant_draft_event",
    ] = "fixed_earth_grid"
    rho_water_kg_m3: float = 1025.0
    gravity_m_s2: float = 9.80665
    front_added_mass_cm: float = 0.787
    front_pileup_factor: float = 1.5
    mean_wetted_length_beam_ratio: float | None = None
    transom_correction_enabled: bool = False
    transom_patch_length_beams: float = 0.1
    transom_fit_limit_beams: float = 3.0
    transom_keel_reduction_beams: float = 0.0
    incident_wave_amplitude_m: float = 0.0
    incident_wave_omega0_rad_s: float | None = None
    incident_wave_wavenumber_rad_m: float | None = None
    incident_wave_phase_at_cg_rad: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.motion_dof not in ("heave", "pitch", "fixed"):
            raise ValueError("motion_dof must be heave, pitch, or fixed.")
        positive = (
            self.speed_mps,
            self.mean_trim_rad,
            self.wetted_length_m,
            self.omega_rad_s,
            self.duration_s,
            self.time_step_s,
            self.initial_draft_m,
            self.rho_water_kg_m3,
            self.gravity_m_s2,
            self.front_added_mass_cm,
            self.front_pileup_factor,
            self.transom_patch_length_beams,
            self.transom_fit_limit_beams,
        )
        if any(not np.isfinite(float(value)) or float(value) <= 0.0 for value in positive):
            raise ValueError("Planing forced-motion positive inputs must be finite and positive.")
        if not np.isfinite(float(self.motion_amplitude)) or float(self.motion_amplitude) < 0.0:
            raise ValueError("motion_amplitude must be finite and non-negative.")
        if self.motion_dof == "fixed" and float(self.motion_amplitude) != 0.0:
            raise ValueError("fixed-hull incident-wave cases require motion_amplitude=0.")
        if self.motion_dof != "fixed" and float(self.motion_amplitude) <= 0.0:
            raise ValueError("Forced-heave and forced-pitch cases require positive motion_amplitude.")
        if not np.isfinite(float(self.lcg_from_transom_m)):
            raise ValueError("lcg_from_transom_m must be finite.")
        if (
            self.mean_wetted_length_beam_ratio is not None
            and (
                not np.isfinite(float(self.mean_wetted_length_beam_ratio))
                or float(self.mean_wetted_length_beam_ratio) <= 0.0
            )
        ):
            raise ValueError("mean_wetted_length_beam_ratio must be finite and positive when supplied.")
        if self.ground_plane_interval_s is not None:
            interval = float(self.ground_plane_interval_s)
            if not np.isfinite(interval) or interval <= 0.0:
                raise ValueError("ground_plane_interval_s must be finite and positive when supplied.")
            stride = int(round(interval / float(self.time_step_s)))
            if stride < 1 or not np.isclose(
                interval,
                stride * float(self.time_step_s),
                rtol=1e-10,
                atol=1e-14,
            ):
                raise ValueError(
                    "ground_plane_interval_s must be an integer multiple of time_step_s."
                )
        if self.ground_plane_handoff_mode not in (
            "fixed_earth_grid",
            "fixed_earth_grid_scheduled_wagner",
            "constant_draft_event",
        ):
            raise ValueError(
                "ground_plane_handoff_mode must be fixed_earth_grid, "
                "fixed_earth_grid_scheduled_wagner, or constant_draft_event."
            )
        period = 2.0 * np.pi / float(self.omega_rad_s)
        if self.duration_s < 2.0 * period or self.time_step_s > period / 16.0:
            raise ValueError("Planing forced motion needs at least two cycles and 16 time steps per cycle.")
        if self.initial_draft_m >= self.wetted_length_m * np.tan(self.mean_trim_rad):
            raise ValueError("initial_draft_m must be smaller than the transom draft implied by wetted length.")
        wave_amplitude = float(self.incident_wave_amplitude_m)
        if not np.isfinite(wave_amplitude) or wave_amplitude < 0.0:
            raise ValueError("incident_wave_amplitude_m must be finite and non-negative.")
        if wave_amplitude > 0.0:
            if self.incident_wave_omega0_rad_s is None or self.incident_wave_wavenumber_rad_m is None:
                raise ValueError(
                    "Incident-wave cases require omega0 and wavenumber."
                )
            if any(
                not np.isfinite(float(value)) or float(value) <= 0.0
                for value in (
                    self.incident_wave_omega0_rad_s,
                    self.incident_wave_wavenumber_rad_m,
                )
            ):
                raise ValueError("Incident-wave omega0 and wavenumber must be positive.")
            encounter = float(self.incident_wave_omega0_rad_s) + float(
                self.incident_wave_wavenumber_rad_m
            ) * float(self.speed_mps)
            if not np.isclose(encounter, self.omega_rad_s, rtol=1.0e-8, atol=1.0e-10):
                raise ValueError(
                    "omega_rad_s must equal omega0+kU for a head-sea incident wave."
                )
        elif self.motion_dof == "fixed":
            raise ValueError("fixed-hull cases require a non-zero incident wave.")
        if not np.isfinite(float(self.incident_wave_phase_at_cg_rad)):
            raise ValueError("incident_wave_phase_at_cg_rad must be finite.")
        keel_reduction = float(self.transom_keel_reduction_beams)
        if not np.isfinite(keel_reduction) or keel_reduction < 0.0:
            raise ValueError("transom_keel_reduction_beams must be finite and non-negative.")
        if self.transom_correction_enabled and keel_reduction > 0.0:
            raise ValueError(
                "The local analytical transom patch and keel-wetted-length reduction "
                "are distinct source corrections and cannot be enabled together."
            )
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def transom_correction_mode(self) -> str:
        if self.transom_keel_reduction_beams > 0.0:
            return "source_keel_wetted_length_reduction"
        if self.transom_correction_enabled:
            return "local_analytic_pressure_patch"
        return "none"

    @property
    def has_incident_wave(self) -> bool:
        return bool(self.incident_wave_amplitude_m > 0.0)

    @property
    def time_s(self) -> np.ndarray:
        step_count = int(np.ceil(self.duration_s / self.time_step_s))
        return np.linspace(0.0, step_count * self.time_step_s, step_count + 1)


@dataclass(frozen=True)
class GroundPlaneForcedMotionLaw(VerticalMotionLaw):
    case: PlaningForcedMotionCase
    reference_draft_m: float
    creation_time_s: float
    incident_wave_active: bool = False

    def _harmonics(self, time_s: float) -> tuple[float, float, float, float, float, float]:
        phase = self.case.omega_rad_s * float(time_s)
        eta = -self.case.motion_amplitude * np.sin(phase)
        eta_dot = -self.case.motion_amplitude * self.case.omega_rad_s * np.cos(phase)
        eta_ddot = self.case.motion_amplitude * self.case.omega_rad_s**2 * np.sin(phase)
        if self.case.motion_dof == "heave":
            return eta, eta_dot, eta_ddot, 0.0, 0.0, 0.0
        if self.case.motion_dof == "pitch":
            return 0.0, 0.0, 0.0, eta, eta_dot, eta_ddot
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    def age_s(self, time_s: float) -> float:
        return float(time_s) - float(self.creation_time_s)

    def longitudinal_coordinates(self, time_s: float) -> tuple[float, float, float]:
        leading_offset = self.case.initial_draft_m / np.tan(self.case.mean_trim_rad)
        from_leading = leading_offset + self.case.speed_mps * self.age_s(time_s)
        from_transom = self.case.wetted_length_m - from_leading
        from_cg = from_transom - self.case.lcg_from_transom_m
        return float(from_leading), float(from_transom), float(from_cg)

    def draft_m(self, time_s: float) -> float:
        from_leading, _, from_cg = self.longitudinal_coordinates(time_s)
        heave, _, _, pitch, _, _ = self._harmonics(time_s)
        return float(from_leading * np.tan(self.case.mean_trim_rad) - heave - from_cg * pitch)

    def displacement_m(self, time_s: float) -> float:
        return float(self.reference_draft_m - self.draft_m(time_s))

    def velocity_mps(self, time_s: float) -> float:
        _, _, from_cg = self.longitudinal_coordinates(time_s)
        _, heave_dot, _, pitch, pitch_dot, _ = self._harmonics(time_s)
        draft_rate = (
            self.case.speed_mps * np.tan(self.case.mean_trim_rad)
            - heave_dot
            + self.case.speed_mps * pitch
            - from_cg * pitch_dot
        )
        return float(-draft_rate)

    def acceleration_mps2(self, time_s: float) -> float:
        _, _, from_cg = self.longitudinal_coordinates(time_s)
        _, _, heave_ddot, _, pitch_dot, pitch_ddot = self._harmonics(time_s)
        draft_acceleration = -heave_ddot + 2.0 * self.case.speed_mps * pitch_dot - from_cg * pitch_ddot
        return float(-draft_acceleration)

    def incident_wave(self) -> RegularIncidentWave2D | None:
        if not self.incident_wave_active or not self.case.has_incident_wave:
            return None
        _, _, x_from_cg_at_zero = self.longitudinal_coordinates(0.0)
        return RegularIncidentWave2D(
            amplitude_m=float(self.case.incident_wave_amplitude_m),
            omega0_rad_s=float(self.case.incident_wave_omega0_rad_s),
            wavenumber_rad_m=float(self.case.incident_wave_wavenumber_rad_m),
            phase_at_time_zero_rad=(
                float(self.case.incident_wave_phase_at_cg_rad)
                + float(self.case.incident_wave_wavenumber_rad_m)
                * x_from_cg_at_zero
            ),
            gravity_m_s2=float(self.case.gravity_m_s2),
        )

    def submergence_m(self, time_s: float) -> float:
        wave = self.incident_wave()
        elevation = 0.0 if wave is None else wave.elevation_m(time_s)
        return float(self.draft_m(time_s) + elevation)


def instantaneous_handoff_creation_time_s(
    case: PlaningForcedMotionCase,
    time_s: float,
) -> float:
    """Choose the ground-plane coordinate so its local draft equals the BEM handoff draft."""

    phase = case.omega_rad_s * float(time_s)
    eta = -case.motion_amplitude * np.sin(phase)
    heave = eta if case.motion_dof == "heave" else 0.0
    pitch = eta if case.motion_dof == "pitch" else 0.0
    leading_offset = case.initial_draft_m / np.tan(case.mean_trim_rad)
    creation_from_cg = case.wetted_length_m - leading_offset - case.lcg_from_transom_m
    instantaneous_slope = np.tan(case.mean_trim_rad) + pitch
    if instantaneous_slope <= 0.0:
        raise ValueError("Instantaneous handoff requires a positive local bottom slope.")
    age = (heave + creation_from_cg * pitch) / (
        case.speed_mps * instantaneous_slope
    )
    return float(time_s) - float(age)


def fixed_ground_plane_activation_time_s(
    case: PlaningForcedMotionCase,
    motion: GroundPlaneForcedMotionLaw,
    *,
    interval_start_s: float,
    interval_end_s: float,
    minimum_draft_m: float,
    time_tolerance_s: float = 1.0e-12,
) -> float | None:
    """Locate a delayed fixed-plane BEM start without moving the Earth-fixed plane.

    Sun's new-plane rule delays Wagner initialization until the section is both
    inside the instantaneous wetted interval and sufficiently submerged.  The
    event is localized inside the current integration step so that its timing is
    not quantized by the internal BEM time step.
    """

    start = max(float(interval_start_s), float(motion.creation_time_s))
    end = float(interval_end_s)
    minimum_draft = float(minimum_draft_m)
    if not np.isfinite((start, end, minimum_draft)).all() or end < start:
        raise ValueError("Fixed-plane activation interval and draft must be finite and ordered.")
    if minimum_draft <= 0.0:
        raise ValueError("minimum_draft_m must be positive.")

    def supported(time_s: float) -> bool:
        _, x_from_transom, _ = motion.longitudinal_coordinates(time_s)
        wetted_length = planing_forced_motion_kinematics(
            case, time_s
        ).instantaneous_wetted_length_m
        return bool(
            -1.0e-9 <= x_from_transom <= wetted_length + 1.0e-9
            and motion.submergence_m(time_s) >= minimum_draft * (1.0 - 1.0e-9)
        )

    if supported(start):
        return start
    if not supported(end):
        return None

    lower = start
    upper = end
    for _ in range(64):
        if upper - lower <= time_tolerance_s:
            break
        middle = 0.5 * (lower + upper)
        if supported(middle):
            upper = middle
        else:
            lower = middle
    return upper


@dataclass(frozen=True)
class PlaningForcedMotionKinematics:
    heave_m: float
    heave_velocity_mps: float
    heave_acceleration_mps2: float
    pitch_rad: float
    pitch_velocity_rad_s: float
    pitch_acceleration_rad_s2: float
    instantaneous_wetted_length_m: float
    wetted_length_rate_mps: float


def incident_wave_phase_at_body_station_rad(
    case: PlaningForcedMotionCase,
    time_s: float,
    x_from_transom_m: float | np.ndarray,
) -> float | np.ndarray:
    """Return the head-sea phase on a body station.

    The code coordinate is positive from transom toward bow. Fixed Earth-plane
    phase advances with ``omega0``; evaluating the same wave on a translating
    body station gives ``omega_e=omega0+kU``.
    """

    if not case.has_incident_wave:
        result = np.zeros_like(np.asarray(x_from_transom_m, dtype=float))
    else:
        x_from_cg = np.asarray(x_from_transom_m, dtype=float) - float(
            case.lcg_from_transom_m
        )
        result = (
            float(case.omega_rad_s) * float(time_s)
            + float(case.incident_wave_wavenumber_rad_m) * x_from_cg
            + float(case.incident_wave_phase_at_cg_rad)
        )
    if np.ndim(x_from_transom_m) == 0:
        return float(result)
    return result


def incident_wave_elevation_at_body_station_m(
    case: PlaningForcedMotionCase,
    time_s: float,
    x_from_transom_m: float | np.ndarray,
) -> float | np.ndarray:
    if not case.has_incident_wave:
        result = np.zeros_like(np.asarray(x_from_transom_m, dtype=float))
    else:
        result = float(case.incident_wave_amplitude_m) * np.sin(
            incident_wave_phase_at_body_station_rad(
                case, time_s, x_from_transom_m
            )
        )
    if np.ndim(x_from_transom_m) == 0:
        return float(result)
    return result


def _wave_modified_wetted_length(
    case: PlaningForcedMotionCase,
    *,
    time_s: float,
    heave_m: float,
    heave_velocity_mps: float,
    pitch_rad: float,
    pitch_velocity_rad_s: float,
) -> tuple[float, float]:
    """Solve Sun Eq. (21) for the foremost zero-submergence station."""

    mean_trim = float(case.mean_trim_rad)
    alpha = mean_trim + float(pitch_rad)
    if alpha <= 0.0:
        raise ValueError("Instantaneous trim must remain positive.")
    if not case.has_incident_wave:
        numerator = (
            case.wetted_length_m * mean_trim
            - heave_m
            + case.lcg_from_transom_m * pitch_rad
        )
        numerator_rate = -heave_velocity_mps + case.lcg_from_transom_m * pitch_velocity_rad_s
        wetted_length = numerator / alpha
        wetted_length_rate = (
            numerator_rate * alpha - numerator * pitch_velocity_rad_s
        ) / alpha**2
        return float(wetted_length), float(wetted_length_rate)

    amplitude = float(case.incident_wave_amplitude_m)
    k = float(case.incident_wave_wavenumber_rad_m)

    def submergence(x_value: float) -> float:
        return float(
            (case.wetted_length_m - x_value) * mean_trim
            - heave_m
            - (x_value - case.lcg_from_transom_m) * pitch_rad
            + incident_wave_elevation_at_body_station_m(case, time_s, x_value)
        )

    upper = max(
        1.5 * float(case.wetted_length_m),
        float(case.wetted_length_m)
        + 2.0
        * (amplitude + abs(heave_m) + abs(pitch_rad) * case.wetted_length_m)
        / max(alpha, 1.0e-6),
    )
    grid = np.linspace(0.0, upper, 513)
    values = np.asarray([submergence(float(x)) for x in grid])
    crossings = np.flatnonzero(values[:-1] * values[1:] <= 0.0)
    if crossings.size == 0:
        raise RuntimeError(
            "Incident-wave wetted-length root was not bracketed inside the supported prismatic hull interval."
        )
    lower = float(grid[int(crossings[-1])])
    upper_root = float(grid[int(crossings[-1]) + 1])
    for _ in range(64):
        middle = 0.5 * (lower + upper_root)
        if submergence(lower) * submergence(middle) <= 0.0:
            upper_root = middle
        else:
            lower = middle
    wetted_length = 0.5 * (lower + upper_root)
    phase = float(
        incident_wave_phase_at_body_station_rad(
            case, time_s, wetted_length
        )
    )
    partial_time = (
        -heave_velocity_mps
        + (case.lcg_from_transom_m - wetted_length) * pitch_velocity_rad_s
        + amplitude * float(case.omega_rad_s) * np.cos(phase)
    )
    partial_x = -alpha + amplitude * k * np.cos(phase)
    if abs(partial_x) <= 1.0e-8:
        raise RuntimeError("Incident-wave wetted-length root is locally tangent and ill-conditioned.")
    return float(wetted_length), float(-partial_time / partial_x)


@dataclass(frozen=True)
class SunFrontLoadResult:
    generalized_load: np.ndarray
    front_length_m: float
    instantaneous_wetted_length_m: float
    maximum_sectional_force_abs_n_m: float


@dataclass(frozen=True)
class SunTransomPatchParameters:
    c1: float
    c2: float
    c3: float
    separation_speed_mps: float
    a_three_halves_m05_s: float
    instantaneous_trim_deg: float
    instantaneous_transom_draft_m: float


@dataclass(frozen=True)
class SunTransomLoadResult:
    generalized_load: np.ndarray
    patch_length_m: float
    parameters: SunTransomPatchParameters
    maximum_sectional_force_abs_n_m: float


def planing_forced_motion_kinematics(
    case: PlaningForcedMotionCase,
    time_s: float,
) -> PlaningForcedMotionKinematics:
    """Return the small-angle kinematics used in Sun (2007), Eqs. 7.41-7.45."""

    phase = case.omega_rad_s * float(time_s)
    eta = -case.motion_amplitude * np.sin(phase)
    eta_dot = -case.motion_amplitude * case.omega_rad_s * np.cos(phase)
    eta_ddot = case.motion_amplitude * case.omega_rad_s**2 * np.sin(phase)
    if case.motion_dof == "heave":
        heave, heave_dot, heave_ddot = eta, eta_dot, eta_ddot
        pitch = pitch_dot = pitch_ddot = 0.0
    elif case.motion_dof == "pitch":
        heave = heave_dot = heave_ddot = 0.0
        pitch, pitch_dot, pitch_ddot = eta, eta_dot, eta_ddot
    else:
        heave = heave_dot = heave_ddot = 0.0
        pitch = pitch_dot = pitch_ddot = 0.0

    wetted_length, wetted_length_rate = _wave_modified_wetted_length(
        case,
        time_s=float(time_s),
        heave_m=float(heave),
        heave_velocity_mps=float(heave_dot),
        pitch_rad=float(pitch),
        pitch_velocity_rad_s=float(pitch_dot),
    )
    return PlaningForcedMotionKinematics(
        heave_m=float(heave),
        heave_velocity_mps=float(heave_dot),
        heave_acceleration_mps2=float(heave_ddot),
        pitch_rad=float(pitch),
        pitch_velocity_rad_s=float(pitch_dot),
        pitch_acceleration_rad_s2=float(pitch_ddot),
        instantaneous_wetted_length_m=float(wetted_length),
        wetted_length_rate_mps=float(wetted_length_rate),
    )


def sun_front_sectional_force_density(
    case: PlaningForcedMotionCase,
    *,
    deadrise_rad: float,
    time_s: float,
    x_from_transom_m: float | np.ndarray,
) -> float | np.ndarray:
    """Evaluate the gravity-free foremost sectional force in Sun (2007), Eq. 7.45."""

    beta = float(deadrise_rad)
    if not np.isfinite(beta) or beta <= 0.0 or beta >= 0.5 * np.pi:
        raise ValueError("deadrise_rad must lie between zero and pi/2.")
    x_forward = np.asarray(x_from_transom_m, dtype=float)
    if not np.isfinite(x_forward).all():
        raise ValueError("x_from_transom_m must be finite.")

    motion = planing_forced_motion_kinematics(case, time_s)
    alpha = case.mean_trim_rad + motion.pitch_rad
    distance_from_leading = motion.instantaneous_wetted_length_m - x_forward
    incident_elevation = np.asarray(
        incident_wave_elevation_at_body_station_m(
            case,
            time_s,
            x_forward,
        ),
        dtype=float,
    )
    local_draft = (
        (case.wetted_length_m - x_forward) * case.mean_trim_rad
        - motion.heave_m
        - (x_forward - case.lcg_from_transom_m) * motion.pitch_rad
        + incident_elevation
    )
    if case.has_incident_wave:
        phase = np.asarray(
            incident_wave_phase_at_body_station_rad(
                case,
                time_s,
                x_forward,
            ),
            dtype=float,
        )
        incident_vertical_velocity = (
            case.gravity_m_s2
            * case.incident_wave_amplitude_m
            * case.incident_wave_wavenumber_rad_m
            / case.incident_wave_omega0_rad_s
        ) * np.cos(phase)
        incident_vertical_acceleration = -(
            case.gravity_m_s2
            * case.incident_wave_amplitude_m
            * case.incident_wave_wavenumber_rad_m
        ) * np.sin(phase)
    else:
        incident_vertical_velocity = np.zeros_like(x_forward)
        incident_vertical_acceleration = np.zeros_like(x_forward)
    draft_material_rate = (
        (motion.wetted_length_rate_mps + case.speed_mps) * alpha
        + distance_from_leading * motion.pitch_velocity_rad_s
        + incident_vertical_velocity
    )
    x_aft_from_cg = case.lcg_from_transom_m - x_forward
    entry_speed = (
        case.speed_mps * alpha
        - motion.heave_velocity_mps
        + x_aft_from_cg * motion.pitch_velocity_rad_s
        + incident_vertical_velocity
    )
    entry_acceleration = (
        2.0 * case.speed_mps * motion.pitch_velocity_rad_s
        - motion.heave_acceleration_mps2
        + x_aft_from_cg * motion.pitch_acceleration_rad_s2
        + incident_vertical_acceleration
    )
    added_mass_k = (
        case.front_added_mass_cm
        * case.rho_water_kg_m3
        * np.pi
        * case.front_pileup_factor**2
        / (2.0 * np.tan(beta) ** 2)
    )
    sectional_force = (
        2.0 * added_mass_k * local_draft * draft_material_rate * entry_speed
        + added_mass_k * local_draft**2 * entry_acceleration
    )
    if case.has_incident_wave:
        submerged_area = np.maximum(local_draft, 0.0) ** 2 / np.tan(beta)
        sectional_force += case.rho_water_kg_m3 * case.gravity_m_s2 * submerged_area
    sectional_force = np.where(distance_from_leading >= 0.0, sectional_force, 0.0)
    if np.ndim(x_from_transom_m) == 0:
        return float(sectional_force)
    return sectional_force


def integrate_sun_front_generalized_load(
    case: PlaningForcedMotionCase,
    *,
    deadrise_rad: float,
    time_s: float,
    foremost_bem_x_from_transom_m: float,
    gauss_order: int = 8,
) -> SunFrontLoadResult:
    """Integrate Eq. 7.45 only over the gap ahead of the foremost BEM plane."""

    if gauss_order < 3:
        raise ValueError("gauss_order must be at least three.")
    motion = planing_forced_motion_kinematics(case, time_s)
    x_start = float(foremost_bem_x_from_transom_m)
    x_end = float(motion.instantaneous_wetted_length_m)
    front_length = max(x_end - x_start, 0.0)
    if front_length == 0.0:
        return SunFrontLoadResult(
            generalized_load=np.zeros(2, dtype=float),
            front_length_m=0.0,
            instantaneous_wetted_length_m=x_end,
            maximum_sectional_force_abs_n_m=0.0,
        )

    nodes, weights = np.polynomial.legendre.leggauss(int(gauss_order))
    x = 0.5 * (x_end + x_start) + 0.5 * front_length * nodes
    force_density = np.asarray(
        sun_front_sectional_force_density(
            case,
            deadrise_rad=deadrise_rad,
            time_s=time_s,
            x_from_transom_m=x,
        ),
        dtype=float,
    )
    jacobian = 0.5 * front_length
    vertical_force = jacobian * np.sum(weights * force_density)
    pitch_moment = jacobian * np.sum(
        weights * force_density * (x - case.lcg_from_transom_m)
    )
    return SunFrontLoadResult(
        generalized_load=np.asarray([vertical_force, pitch_moment], dtype=float),
        front_length_m=front_length,
        instantaneous_wetted_length_m=x_end,
        maximum_sectional_force_abs_n_m=float(np.max(np.abs(force_density))),
    )


def sun_transom_patch_parameters(
    case: PlaningForcedMotionCase,
    *,
    beam_m: float,
    mean_transom_draft_m: float,
    time_s: float,
) -> SunTransomPatchParameters:
    """Evaluate Sun (2007), Eqs. 3.30 and 7.19-7.20, for one instant."""

    beam = float(beam_m)
    if beam <= 0.0 or mean_transom_draft_m <= 0.0:
        raise ValueError("beam_m and mean_transom_draft_m must be positive.")
    motion = planing_forced_motion_kinematics(case, time_s)
    trim = case.mean_trim_rad + motion.pitch_rad
    trim_deg = float(np.degrees(trim))
    if trim_deg <= 0.0:
        raise ValueError("Instantaneous trim must remain positive for the transom patch.")
    transom_draft = (
        float(mean_transom_draft_m)
        - motion.heave_m
        + case.lcg_from_transom_m * motion.pitch_rad
    )
    if transom_draft <= 0.0:
        raise ValueError("Instantaneous transom draft must remain positive for the transom patch.")
    fn_b = case.speed_mps / np.sqrt(case.gravity_m_s2 * beam)
    lambda_w = (
        case.wetted_length_m / beam
        if case.mean_wetted_length_beam_ratio is None
        else float(case.mean_wetted_length_beam_ratio)
    )
    common = trim_deg**0.7 / fn_b**0.6
    c1 = 0.02064 * common**2
    c2 = 0.00448 * common**2.44
    c3 = 0.0108 * lambda_w * trim_deg**0.34
    separation_speed = np.sqrt(
        case.speed_mps**2 + 2.0 * case.gravity_m_s2 * transom_draft
    )
    alpha = case.transom_fit_limit_beams
    integral = (
        c1 * alpha**4.5 / 4.5
        - c2 * alpha**4.94 / 4.94
        + c3 * alpha**3.5 / 3.5
    )
    a_three_halves = 4.0 * separation_speed * integral / (alpha**4 * np.sqrt(beam))
    return SunTransomPatchParameters(
        c1=float(c1),
        c2=float(c2),
        c3=float(c3),
        separation_speed_mps=float(separation_speed),
        a_three_halves_m05_s=float(a_three_halves),
        instantaneous_trim_deg=trim_deg,
        instantaneous_transom_draft_m=float(transom_draft),
    )


def sun_transom_sectional_force_density(
    case: PlaningForcedMotionCase,
    *,
    beam_m: float,
    mean_transom_draft_m: float,
    time_s: float,
    x_from_transom_m: float | np.ndarray,
) -> float | np.ndarray:
    """Return the local separated-flow force from Sun Eqs. 3.33 and 7.22."""

    beam = float(beam_m)
    x = np.asarray(x_from_transom_m, dtype=float)
    if not np.isfinite(x).all() or np.any(x < 0.0):
        raise ValueError("x_from_transom_m must be finite and non-negative.")
    parameters = sun_transom_patch_parameters(
        case,
        beam_m=beam,
        mean_transom_draft_m=mean_transom_draft_m,
        time_s=time_s,
    )
    force = (
        1.5
        * case.rho_water_kg_m3
        * parameters.separation_speed_mps
        * parameters.a_three_halves_m05_s
        * np.sqrt(x)
        * beam
    )
    if np.ndim(x_from_transom_m) == 0:
        return float(force)
    return force


def integrate_sun_transom_generalized_load(
    case: PlaningForcedMotionCase,
    *,
    beam_m: float,
    mean_transom_draft_m: float,
    time_s: float,
    gauss_order: int = 8,
) -> SunTransomLoadResult:
    """Integrate the separated-flow patch over the source interval 0-0.1B."""

    if gauss_order < 3:
        raise ValueError("gauss_order must be at least three.")
    parameters = sun_transom_patch_parameters(
        case,
        beam_m=beam_m,
        mean_transom_draft_m=mean_transom_draft_m,
        time_s=time_s,
    )
    patch_length = case.transom_patch_length_beams * float(beam_m)
    nodes, weights = np.polynomial.legendre.leggauss(int(gauss_order))
    x = 0.5 * patch_length * (nodes + 1.0)
    force_density = np.asarray(
        sun_transom_sectional_force_density(
            case,
            beam_m=beam_m,
            mean_transom_draft_m=mean_transom_draft_m,
            time_s=time_s,
            x_from_transom_m=x,
        ),
        dtype=float,
    )
    jacobian = 0.5 * patch_length
    vertical_force = jacobian * np.sum(weights * force_density)
    pitch_moment = jacobian * np.sum(
        weights * force_density * (x - case.lcg_from_transom_m)
    )
    return SunTransomLoadResult(
        generalized_load=np.asarray([vertical_force, pitch_moment], dtype=float),
        patch_length_m=patch_length,
        parameters=parameters,
        maximum_sectional_force_abs_n_m=float(np.max(np.abs(force_density))),
    )


@dataclass(frozen=True)
class ActiveGroundPlane:
    creation_time_s: float
    state: MovingWedgeState
    incident_wave_active: bool = False


def _evaluate_ground_plane_load_job(job):
    config, case, plane, current_time, reference_draft, x_from_transom = job
    motion = GroundPlaneForcedMotionLaw(
        case=case,
        reference_draft_m=reference_draft,
        creation_time_s=plane.creation_time_s,
        incident_wave_active=plane.incident_wave_active,
    )
    load = moving_wedge_load(
        config,
        motion,
        plane.state,
        rho_water_kg_m3=case.rho_water_kg_m3,
        gravity_m_s2=case.gravity_m_s2,
        incident_wave=motion.incident_wave(),
    )
    return (
        float(x_from_transom),
        load.pressure.body_vertical_force_per_length_n_m,
        float(plane.creation_time_s),
        float(plane.state.right_free_y_m[0]),
        int(plane.state.jet_cut_count),
        load.potential_bvp_relative_residual,
        load.potential_bvp_condition_number,
        load.pressure.auxiliary_solution.relative_residual,
        load.pressure.auxiliary_solution.condition_number,
        load.pressure.free_surface_pressure_max_abs_pa,
        load.contact_constraint_max_abs_m,
    )


def _advance_ground_plane_job(job):
    (
        config,
        case,
        plane,
        next_time,
        reference_draft,
        next_x_from_transom,
        next_draft,
        time_step_s,
    ) = job
    motion = GroundPlaneForcedMotionLaw(
        case=case,
        reference_draft_m=reference_draft,
        creation_time_s=plane.creation_time_s,
        incident_wave_active=plane.incident_wave_active,
    )
    try:
        step = advance_moving_wedge_rk4(
            config,
            motion,
            plane.state,
            time_step_s=time_step_s,
            gravity_m_s2=case.gravity_m_s2,
            incident_wave=motion.incident_wave(),
        )
    except MovingWedgeContactExitError as exc:
        if next_draft <= case.initial_draft_m * (1.0 + 1.0e-6):
            return plane, None
        raise RuntimeError(
            "A moving-wedge contact exited at a draft above the frozen BEM "
            "handoff threshold: "
            f"global_time={next_time:.9g} s, draft={next_draft:.9g} m, "
            f"threshold={case.initial_draft_m:.9g} m."
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            "Ground-plane BEM advance failed inside the event-managed wetted interval: "
            f"global_time={next_time:.9g} s, creation_parameter={plane.creation_time_s:.9g} s, "
            f"age={next_time - plane.creation_time_s:.9g} s, "
            f"x_from_transom={next_x_from_transom:.9g} m, draft={next_draft:.9g} m."
        ) from exc
    return plane, step


@dataclass(frozen=True)
class PlaningForcedMotion2DtResult:
    time_s: np.ndarray
    generalized_load: np.ndarray
    raw_bem_generalized_load: np.ndarray
    resolved_station_generalized_load: np.ndarray
    transom_extrapolation_generalized_load: np.ndarray
    longitudinal_bem_bin_generalized_load: np.ndarray
    pre_chine_bem_generalized_load: np.ndarray
    post_chine_bem_generalized_load: np.ndarray
    bem_generalized_load: np.ndarray
    front_generalized_load: np.ndarray
    transom_generalized_load: np.ndarray
    front_approximation_length_m: np.ndarray
    transom_correction_length_m: np.ndarray
    active_plane_count: np.ndarray
    max_potential_bvp_relative_residual: np.ndarray
    max_potential_bvp_condition_number: np.ndarray
    max_pressure_bvp_relative_residual: np.ndarray
    max_pressure_bvp_condition_number: np.ndarray
    max_free_surface_pressure_abs_pa: np.ndarray
    max_contact_constraint_abs_m: np.ndarray
    aftmost_resolved_station_x_m: np.ndarray
    foremost_resolved_station_x_m: np.ndarray
    transom_coverage_gap_m: np.ndarray
    station_x_from_transom_m: np.ndarray
    station_force_density_n_m: np.ndarray
    station_creation_parameter_s: np.ndarray
    station_age_parameter_s: np.ndarray
    station_contact_half_beam_m: np.ndarray
    station_jet_cut_count: np.ndarray
    minimum_matrix_station_count: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IdentifiedPlaningForcedMotionColumn:
    simulation: PlaningForcedMotion2DtResult
    column: ForcedMotionColumn


@dataclass(frozen=True)
class IdentifiedPlaningIncidentWaveExcitation:
    simulation: PlaningForcedMotion2DtResult
    harmonic_fit: FirstHarmonicFit
    excitation_per_wave_amplitude: np.ndarray
    component_excitation_per_wave_amplitude: dict[str, np.ndarray]
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        excitation = np.asarray(self.excitation_per_wave_amplitude, dtype=complex)
        if excitation.shape != (2,) or not np.isfinite(excitation).all():
            raise ValueError("Incident-wave excitation must be a finite two-component complex vector.")
        components = {
            str(name): np.asarray(value, dtype=complex)
            for name, value in self.component_excitation_per_wave_amplitude.items()
        }
        if any(value.shape != (2,) or not np.isfinite(value).all() for value in components.values()):
            raise ValueError("Every incident-wave excitation component must contain two finite values.")
        object.__setattr__(self, "excitation_per_wave_amplitude", excitation)
        object.__setattr__(self, "component_excitation_per_wave_amplitude", components)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class PlaningForcedMotionFrequencyResult:
    heave: IdentifiedPlaningForcedMotionColumn
    pitch: IdentifiedPlaningForcedMotionColumn
    matrices: ForcedMotionMatrices


def _state_at_global_time(state: MovingWedgeState, global_time_s: float) -> MovingWedgeState:
    return MovingWedgeState(
        right_free_y_m=state.right_free_y_m,
        right_free_z_up_m=state.right_free_z_up_m,
        left_free_y_m=state.left_free_y_m,
        left_free_z_up_m=state.left_free_z_up_m,
        right_free_potential_m2_s=state.right_free_potential_m2_s,
        left_free_potential_m2_s=state.left_free_potential_m2_s,
        time_s=float(global_time_s),
        jet_cut_count=state.jet_cut_count,
        minimum_jet_normal_distance_ratio=state.minimum_jet_normal_distance_ratio,
        minimum_jet_projection_ratio=state.minimum_jet_projection_ratio,
        maximum_jet_projection_ratio=state.maximum_jet_projection_ratio,
        maximum_spray_overturning_panel_count=(
            state.maximum_spray_overturning_panel_count
        ),
        minimum_spray_outward_tangent_cosine=(
            state.minimum_spray_outward_tangent_cosine
        ),
        minimum_spray_nonadjacent_distance_ratio=(
            state.minimum_spray_nonadjacent_distance_ratio
        ),
    )


def _integrate_station_interval(
    x_from_transom_m: np.ndarray,
    force_density_n_m: np.ndarray,
    *,
    lower_m: float,
    upper_m: float,
    lcg_from_transom_m: float,
) -> np.ndarray:
    lower = max(float(lower_m), float(x_from_transom_m[0]))
    upper = min(float(upper_m), float(x_from_transom_m[-1]))
    if upper <= lower:
        return np.zeros(2, dtype=float)
    interior = (x_from_transom_m > lower) & (x_from_transom_m < upper)
    x = np.concatenate(([lower], x_from_transom_m[interior], [upper]))
    force = np.interp(x, x_from_transom_m, force_density_n_m)
    panel_length = np.diff(x)
    force_left = force[:-1]
    force_right = force[1:]
    x_left = x[:-1]
    x_right = x[1:]
    vertical = np.sum(0.5 * panel_length * (force_left + force_right))
    first_moment = np.sum(
        panel_length
        * (
            force_left * (2.0 * x_left + x_right)
            + force_right * (x_left + 2.0 * x_right)
        )
        / 6.0
    )
    moment = first_moment - lcg_from_transom_m * vertical
    return np.asarray([vertical, moment], dtype=float)


def _remove_aft_station_interval(
    x_from_transom_m: np.ndarray,
    force_density_n_m: np.ndarray,
    *,
    removed_length_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Remove a source-prescribed aft interval while preserving its boundary value.

    Sun (2007), Sec. 7.3.1, represents the transom suction correction by reducing
    the effective keel wetted length by ``0.5B``.  The source coordinate starts at
    the wetted bow and ends at the transom; in this code's transom-positive-forward
    coordinate the same operation removes ``0 <= x < removed_length_m``.
    """

    x = np.asarray(x_from_transom_m, dtype=float)
    force = np.asarray(force_density_n_m, dtype=float)
    removed = float(removed_length_m)
    if (
        x.ndim != 1
        or force.shape != x.shape
        or len(x) < 2
        or not np.isfinite(x).all()
        or not np.isfinite(force).all()
        or np.any(np.diff(x) <= 0.0)
    ):
        raise ValueError("Station coordinates and force density must be finite ordered vectors.")
    if not np.isfinite(removed) or removed <= 0.0:
        raise ValueError("removed_length_m must be finite and positive.")
    if removed >= float(x[-1]):
        raise RuntimeError("The aft correction removes the complete resolved station interval.")
    boundary_force = float(np.interp(removed, x, force))
    retained = x > removed
    corrected_x = np.concatenate(([removed], x[retained]))
    corrected_force = np.concatenate(([boundary_force], force[retained]))
    return corrected_x, corrected_force


def _extend_station_load_to_transom(
    x_from_transom_m: np.ndarray,
    force_density_n_m: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Close the uncorrected 2D+t station integral at the physical transom x=0."""

    x = np.asarray(x_from_transom_m, dtype=float)
    force = np.asarray(force_density_n_m, dtype=float)
    if x.ndim != 1 or force.shape != x.shape or len(x) < 2 or np.any(np.diff(x) <= 0.0):
        raise ValueError("Transom extension requires two or more sorted station loads.")
    gap = max(float(x[0]), 0.0)
    if gap <= 1e-12:
        closed_x = x.copy()
        closed_x[0] = 0.0
        return closed_x, force.copy(), gap
    slope = (force[1] - force[0]) / (x[1] - x[0])
    transom_force = force[0] - slope * x[0]
    return (
        np.concatenate(([0.0], x)),
        np.concatenate(([transom_force], force)),
        gap,
    )


def _longitudinal_bem_bin_definition(
    case: PlaningForcedMotionCase,
    config: MovingWedgeConfig,
) -> tuple[np.ndarray, tuple[str, ...]]:
    """Split the BEM load into three post-chine bands and one pre-chine band."""

    if case.mean_wetted_length_beam_ratio is not None:
        beam = 2.0 * config.chine_half_beam_m
        mean_average_wetted_length = case.mean_wetted_length_beam_ratio * beam
        mean_chine_wetting_from_leading = 2.0 * (
            case.wetted_length_m - mean_average_wetted_length
        )
        split_from_transom = case.wetted_length_m - mean_chine_wetting_from_leading
    else:
        split_from_transom = 0.75 * case.wetted_length_m
    split_from_transom = float(
        np.clip(split_from_transom, 0.0, case.wetted_length_m)
    )
    edges = np.asarray(
        [
            0.0,
            split_from_transom / 3.0,
            2.0 * split_from_transom / 3.0,
            split_from_transom,
            case.wetted_length_m,
        ],
        dtype=float,
    )
    labels = (
        "aft_post_chine",
        "middle_post_chine",
        "forward_post_chine",
        "pre_chine",
    )
    return edges, labels


def _pad_station_history(
    history: list[np.ndarray],
    *,
    width: int,
    fill_value: float,
    dtype: Any = float,
) -> np.ndarray:
    result = np.full((len(history), int(width)), fill_value, dtype=dtype)
    for index, values in enumerate(history):
        row = np.asarray(values, dtype=dtype)
        result[index, : len(row)] = row
    return result


def run_planing_forced_motion_2dt(
    wedge_config: MovingWedgeConfig,
    case: PlaningForcedMotionCase,
    *,
    progress_callback: Callable[[int, int, float], None] | None = None,
    parallel_workers: int = 1,
) -> PlaningForcedMotion2DtResult:
    """Run the ground-fixed plane queue in Sun (2007), Fig. 7.12."""

    workers = int(parallel_workers)
    if workers != parallel_workers or workers < 1:
        raise ValueError("parallel_workers must be a positive integer.")
    executor = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None

    time = case.time_s
    dt = float(case.time_step_s)
    plane_interval = (
        dt
        if case.ground_plane_interval_s is None
        else float(case.ground_plane_interval_s)
    )
    plane_creation_stride = int(round(plane_interval / dt))
    scheduled_wagner = (
        case.ground_plane_handoff_mode == "fixed_earth_grid_scheduled_wagner"
    )
    leading_offset = case.initial_draft_m / np.tan(case.mean_trim_rad)
    base = run_steady_planing_wedge_entry(
        wedge_config,
        speed_mps=case.speed_mps,
        trim_rad=case.mean_trim_rad,
        wetted_length_m=case.wetted_length_m,
        time_step_s=dt,
        initial_draft_m=case.initial_draft_m,
        rho_water_kg_m3=case.rho_water_kg_m3,
        gravity_m_s2=case.gravity_m_s2,
    )
    reference_draft = max(float(wedge_config.mean_draft_m), float(np.max(base.draft_m)))
    config = MovingWedgeConfig(**{**wedge_config.__dict__, "mean_draft_m": reference_draft})
    active_duration = (case.wetted_length_m - leading_offset) / case.speed_mps
    active: list[ActiveGroundPlane] = []
    for base_index, (base_time, base_state) in enumerate(zip(base.time_s, base.states)):
        if base_index % plane_creation_stride != 0:
            continue
        if base_time <= active_duration + 1e-12:
            active.append(
                ActiveGroundPlane(
                    creation_time_s=-float(base_time),
                    state=_state_at_global_time(base_state, 0.0),
                    incident_wave_active=False,
                )
            )
    maximum_jet_cut_count_per_plane = max((plane.state.jet_cut_count for plane in active), default=0)
    jet_distance_ratios = [
        plane.state.minimum_jet_normal_distance_ratio
        for plane in active
        if plane.state.minimum_jet_normal_distance_ratio is not None
    ]
    jet_projection_minima = [
        plane.state.minimum_jet_projection_ratio
        for plane in active
        if plane.state.minimum_jet_projection_ratio is not None
    ]
    jet_projection_maxima = [
        plane.state.maximum_jet_projection_ratio
        for plane in active
        if plane.state.maximum_jet_projection_ratio is not None
    ]
    maximum_spray_overturning_panel_count = max(
        (plane.state.maximum_spray_overturning_panel_count for plane in active),
        default=0,
    )
    spray_outward_tangent_cosines = [
        plane.state.minimum_spray_outward_tangent_cosine
        for plane in active
        if plane.state.minimum_spray_outward_tangent_cosine is not None
    ]
    spray_nonadjacent_distance_ratios = [
        plane.state.minimum_spray_nonadjacent_distance_ratio
        for plane in active
        if plane.state.minimum_spray_nonadjacent_distance_ratio is not None
    ]
    if len(active) < 2:
        raise ValueError("Ground-plane queue needs at least two active planes; reduce time_step_s.")

    loads = np.zeros((len(time), 2), dtype=float)
    raw_bem_loads = np.zeros((len(time), 2), dtype=float)
    resolved_station_loads = np.zeros((len(time), 2), dtype=float)
    transom_extrapolation_loads = np.zeros((len(time), 2), dtype=float)
    longitudinal_bin_edges, longitudinal_bin_labels = _longitudinal_bem_bin_definition(
        case, config
    )
    longitudinal_bem_bin_loads = np.zeros(
        (len(time), len(longitudinal_bin_labels), 2), dtype=float
    )
    pre_chine_bem_loads = np.zeros((len(time), 2), dtype=float)
    post_chine_bem_loads = np.zeros((len(time), 2), dtype=float)
    bem_loads = np.zeros((len(time), 2), dtype=float)
    front_loads = np.zeros((len(time), 2), dtype=float)
    transom_loads = np.zeros((len(time), 2), dtype=float)
    front_lengths = np.zeros(len(time), dtype=float)
    transom_lengths = np.zeros(len(time), dtype=float)
    counts = np.zeros(len(time), dtype=int)
    potential_residual = np.zeros(len(time))
    potential_condition = np.zeros(len(time))
    pressure_residual = np.zeros(len(time))
    pressure_condition = np.zeros(len(time))
    free_pressure = np.zeros(len(time))
    contact_residual = np.zeros(len(time))
    transom_coverage_gap = np.zeros(len(time))
    aftmost_resolved_station_x = np.zeros(len(time))
    foremost_resolved_station_x = np.zeros(len(time))
    wet_plane_removal_count = 0
    contact_exit_removal_count = 0
    transom_exit_removal_count = 0
    forward_interval_exit_removal_count = 0
    below_handoff_draft_removal_count = 0
    fixed_plane_deferred_creation_count = 0
    fixed_plane_expired_before_activation_count = 0
    pending_fixed_creation_parameters: list[float] = []
    creation_draft_errors: list[float] = []
    creation_drafts: list[float] = []
    creation_spacing_errors: list[float] = []
    fixed_plane_localized_activation_count = 0
    fixed_plane_maximum_removed_time_quantization_s = 0.0
    station_x_history: list[np.ndarray] = []
    station_force_history: list[np.ndarray] = []
    station_creation_history: list[np.ndarray] = []
    station_age_history: list[np.ndarray] = []
    station_contact_history: list[np.ndarray] = []
    station_jet_cut_history: list[np.ndarray] = []
    for time_index, current_time in enumerate(time):
        if progress_callback is not None:
            progress_callback(time_index, len(time), float(current_time))
        instantaneous_wetted_length = planing_forced_motion_kinematics(
            case, float(current_time)
        ).instantaneous_wetted_length_m
        station_rows: list[tuple[float, float, float, float, int]] = []
        load_jobs: list[tuple[Any, ...]] = []
        for plane in active:
            motion = GroundPlaneForcedMotionLaw(
                case=case,
                reference_draft_m=reference_draft,
                creation_time_s=plane.creation_time_s,
                incident_wave_active=plane.incident_wave_active,
            )
            _, x_from_transom, _ = motion.longitudinal_coordinates(current_time)
            if x_from_transom < -1e-9 or x_from_transom > instantaneous_wetted_length + 1e-9:
                continue
            load_jobs.append(
                (
                    config,
                    case,
                    plane,
                    float(current_time),
                    reference_draft,
                    float(x_from_transom),
                )
            )

        load_results = (
            map(_evaluate_ground_plane_load_job, load_jobs)
            if executor is None
            else executor.map(_evaluate_ground_plane_load_job, load_jobs)
        )
        for (
            x_from_transom,
            force_density,
            creation_time,
            contact,
            jet_cut_count,
            load_potential_residual,
            load_potential_condition,
            load_pressure_residual,
            load_pressure_condition,
            load_free_pressure,
            load_contact_residual,
        ) in load_results:
            station_rows.append(
                (
                    float(x_from_transom),
                    force_density,
                    creation_time,
                    contact,
                    jet_cut_count,
                )
            )
            potential_residual[time_index] = max(
                potential_residual[time_index], load_potential_residual
            )
            potential_condition[time_index] = max(
                potential_condition[time_index], load_potential_condition
            )
            pressure_residual[time_index] = max(
                pressure_residual[time_index], load_pressure_residual
            )
            pressure_condition[time_index] = max(
                pressure_condition[time_index], load_pressure_condition
            )
            free_pressure[time_index] = max(
                free_pressure[time_index], load_free_pressure
            )
            contact_residual[time_index] = max(
                contact_residual[time_index], load_contact_residual
            )
        station_rows.sort(key=lambda item: item[0])
        counts[time_index] = len(station_rows)
        if len(station_rows) < 2:
            raise RuntimeError("Fewer than two active ground planes remain in the wetted interval.")
        resolved_x = np.asarray([row[0] for row in station_rows])
        resolved_force_density = np.asarray([row[1] for row in station_rows])
        station_x_history.append(resolved_x.copy())
        station_force_history.append(resolved_force_density.copy())
        station_creation_history.append(
            np.asarray([row[2] for row in station_rows], dtype=float)
        )
        station_age_history.append(
            float(current_time) - station_creation_history[-1]
        )
        station_contact_history.append(
            np.asarray([row[3] for row in station_rows], dtype=float)
        )
        station_jet_cut_history.append(
            np.asarray([row[4] for row in station_rows], dtype=int)
        )
        aftmost_resolved_station_x[time_index] = float(resolved_x[0])
        foremost_resolved_station_x[time_index] = float(resolved_x[-1])
        resolved_station_loads[time_index] = _integrate_station_interval(
            resolved_x,
            resolved_force_density,
            lower_m=float(resolved_x[0]),
            upper_m=float(resolved_x[-1]),
            lcg_from_transom_m=case.lcg_from_transom_m,
        )
        x, force_density, transom_coverage_gap[time_index] = _extend_station_load_to_transom(
            resolved_x, resolved_force_density
        )
        raw_bem_loads[time_index] = _integrate_station_interval(
            x,
            force_density,
            lower_m=float(x[0]),
            upper_m=float(x[-1]),
            lcg_from_transom_m=case.lcg_from_transom_m,
        )
        transom_extrapolation_loads[time_index] = (
            raw_bem_loads[time_index] - resolved_station_loads[time_index]
        )
        for bin_index, (lower, upper) in enumerate(
            zip(longitudinal_bin_edges[:-1], longitudinal_bin_edges[1:])
        ):
            longitudinal_bem_bin_loads[time_index, bin_index] = (
                _integrate_station_interval(
                    x,
                    force_density,
                    lower_m=float(lower),
                    upper_m=float(upper),
                    lcg_from_transom_m=case.lcg_from_transom_m,
                )
            )
        if case.mean_wetted_length_beam_ratio is not None:
            beam = 2.0 * config.chine_half_beam_m
            mean_average_wetted_length = case.mean_wetted_length_beam_ratio * beam
            mean_chine_wetting_from_leading = 2.0 * (
                case.wetted_length_m - mean_average_wetted_length
            )
            split_from_transom = (
                case.wetted_length_m - mean_chine_wetting_from_leading
            )
            post_chine_bem_loads[time_index] = _integrate_station_interval(
                x,
                force_density,
                lower_m=float(x[0]),
                upper_m=split_from_transom,
                lcg_from_transom_m=case.lcg_from_transom_m,
            )
            pre_chine_bem_loads[time_index] = _integrate_station_interval(
                x,
                force_density,
                lower_m=split_from_transom,
                upper_m=float(x[-1]),
                lcg_from_transom_m=case.lcg_from_transom_m,
            )
        else:
            pre_chine_bem_loads[time_index] = raw_bem_loads[time_index]
        if case.transom_keel_reduction_beams > 0.0:
            beam = 2.0 * config.chine_half_beam_m
            removed_length = case.transom_keel_reduction_beams * beam
            interior_x, interior_force = _remove_aft_station_interval(
                x,
                force_density,
                removed_length_m=removed_length,
            )
            bem_loads[time_index] = _integrate_station_interval(
                interior_x,
                interior_force,
                lower_m=float(interior_x[0]),
                upper_m=float(interior_x[-1]),
                lcg_from_transom_m=case.lcg_from_transom_m,
            )
            transom_lengths[time_index] = removed_length
        elif case.transom_correction_enabled:
            beam = 2.0 * config.chine_half_beam_m
            patch_length = case.transom_patch_length_beams * beam
            interior_x, interior_force = _remove_aft_station_interval(
                x,
                force_density,
                removed_length_m=patch_length,
            )
            bem_loads[time_index] = _integrate_station_interval(
                interior_x,
                interior_force,
                lower_m=float(interior_x[0]),
                upper_m=float(interior_x[-1]),
                lcg_from_transom_m=case.lcg_from_transom_m,
            )
            transom = integrate_sun_transom_generalized_load(
                case,
                beam_m=beam,
                mean_transom_draft_m=wedge_config.mean_draft_m,
                time_s=float(current_time),
            )
            transom_loads[time_index] = transom.generalized_load
            transom_lengths[time_index] = transom.patch_length_m
        else:
            bem_loads[time_index] = raw_bem_loads[time_index]
        front = integrate_sun_front_generalized_load(
            case,
            deadrise_rad=config.deadrise_rad,
            time_s=float(current_time),
            foremost_bem_x_from_transom_m=float(x[-1]),
        )
        front_loads[time_index] = front.generalized_load
        front_lengths[time_index] = front.front_length_m
        loads[time_index] = (
            bem_loads[time_index]
            + transom_loads[time_index]
            + front_loads[time_index]
        )

        if time_index + 1 == len(time):
            continue
        next_time = float(time[time_index + 1])
        advanced: list[ActiveGroundPlane] = []
        advance_jobs: list[tuple[Any, ...]] = []
        next_wetted_length = planing_forced_motion_kinematics(
            case, next_time
        ).instantaneous_wetted_length_m
        for plane in active:
            motion = GroundPlaneForcedMotionLaw(
                case=case,
                reference_draft_m=reference_draft,
                creation_time_s=plane.creation_time_s,
                incident_wave_active=plane.incident_wave_active,
            )
            _, next_x_from_transom, _ = motion.longitudinal_coordinates(next_time)
            next_draft = motion.submergence_m(next_time)
            minimum_supported_draft = (
                case.initial_draft_m * 1.0e-9
                if scheduled_wagner
                else case.initial_draft_m * (1.0 - 1e-9)
            )
            remains_wet = (
                -1e-9 <= next_x_from_transom <= next_wetted_length + 1e-9
                and next_draft >= minimum_supported_draft
            )
            if remains_wet:
                advance_jobs.append(
                    (
                        config,
                        case,
                        plane,
                        next_time,
                        reference_draft,
                        float(next_x_from_transom),
                        float(next_draft),
                        dt,
                    )
                )
            else:
                wet_plane_removal_count += 1
                if next_x_from_transom < -1.0e-9:
                    transom_exit_removal_count += 1
                elif next_x_from_transom > next_wetted_length + 1.0e-9:
                    forward_interval_exit_removal_count += 1
                else:
                    below_handoff_draft_removal_count += 1

        advance_results = (
            map(_advance_ground_plane_job, advance_jobs)
            if executor is None
            else executor.map(_advance_ground_plane_job, advance_jobs)
        )
        for plane, step in advance_results:
            if step is None:
                wet_plane_removal_count += 1
                contact_exit_removal_count += 1
                continue
            potential_residual[time_index] = max(
                potential_residual[time_index], step.max_potential_relative_residual
            )
            maximum_jet_cut_count_per_plane = max(
                maximum_jet_cut_count_per_plane, step.state.jet_cut_count
            )
            if step.state.minimum_jet_normal_distance_ratio is not None:
                jet_distance_ratios.append(step.state.minimum_jet_normal_distance_ratio)
            if step.state.minimum_jet_projection_ratio is not None:
                jet_projection_minima.append(step.state.minimum_jet_projection_ratio)
            if step.state.maximum_jet_projection_ratio is not None:
                jet_projection_maxima.append(step.state.maximum_jet_projection_ratio)
            maximum_spray_overturning_panel_count = max(
                maximum_spray_overturning_panel_count,
                step.state.maximum_spray_overturning_panel_count,
            )
            if step.state.minimum_spray_outward_tangent_cosine is not None:
                spray_outward_tangent_cosines.append(
                    step.state.minimum_spray_outward_tangent_cosine
                )
            if step.state.minimum_spray_nonadjacent_distance_ratio is not None:
                spray_nonadjacent_distance_ratios.append(
                    step.state.minimum_spray_nonadjacent_distance_ratio
                )
            advanced.append(
                ActiveGroundPlane(
                    plane.creation_time_s,
                    step.state,
                    plane.incident_wave_active,
                )
            )
        creation_candidates: list[tuple[float, float]] = []
        if (time_index + 1) % plane_creation_stride == 0:
            if case.ground_plane_handoff_mode == "fixed_earth_grid":
                pending_fixed_creation_parameters.append(next_time)
            elif scheduled_wagner:
                creation_candidates.append((next_time, next_time))
            else:
                creation_candidates.append(
                    (instantaneous_handoff_creation_time_s(case, next_time), next_time)
                )
        if case.ground_plane_handoff_mode == "fixed_earth_grid":
            still_pending: list[float] = []
            for creation_parameter in pending_fixed_creation_parameters:
                pending_motion = GroundPlaneForcedMotionLaw(
                    case=case,
                    reference_draft_m=reference_draft,
                    creation_time_s=creation_parameter,
                    incident_wave_active=case.has_incident_wave,
                )
                _, pending_x, _ = pending_motion.longitudinal_coordinates(next_time)
                if pending_x < -1.0e-9:
                    fixed_plane_expired_before_activation_count += 1
                    continue
                activation_time = fixed_ground_plane_activation_time_s(
                    case,
                    pending_motion,
                    interval_start_s=float(current_time),
                    interval_end_s=next_time,
                    minimum_draft_m=case.initial_draft_m,
                )
                if activation_time is None:
                    if math.isclose(
                        creation_parameter,
                        next_time,
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    ):
                        fixed_plane_deferred_creation_count += 1
                    still_pending.append(creation_parameter)
                    continue
                creation_candidates.append((creation_parameter, activation_time))
            pending_fixed_creation_parameters = still_pending
        for creation_parameter, activation_time in creation_candidates:
            new_motion = GroundPlaneForcedMotionLaw(
                case=case,
                reference_draft_m=reference_draft,
                creation_time_s=creation_parameter,
                incident_wave_active=case.has_incident_wave,
            )
            creation_draft = new_motion.submergence_m(activation_time)
            if creation_draft <= 0.0:
                raise RuntimeError("A BEM ground plane cannot be initialized at non-positive draft.")
            new_state = initialize_moving_wedge_state(
                config,
                new_motion,
                time_s=activation_time,
                incident_wave=new_motion.incident_wave(),
            )
            remaining_step = next_time - activation_time
            if remaining_step > 1.0e-12:
                activation_step = advance_moving_wedge_rk4(
                    config,
                    new_motion,
                    new_state,
                    time_step_s=remaining_step,
                    gravity_m_s2=case.gravity_m_s2,
                    incident_wave=new_motion.incident_wave(),
                )
                new_state = activation_step.state
                potential_residual[time_index + 1] = max(
                    potential_residual[time_index + 1],
                    activation_step.max_potential_relative_residual,
                )
                fixed_plane_localized_activation_count += 1
                fixed_plane_maximum_removed_time_quantization_s = max(
                    fixed_plane_maximum_removed_time_quantization_s,
                    remaining_step,
                )
            creation_drafts.append(float(creation_draft))
            creation_draft_errors.append(abs(creation_draft - case.initial_draft_m))
            if advanced:
                existing_foremost_x = max(
                    GroundPlaneForcedMotionLaw(
                        case=case,
                        reference_draft_m=reference_draft,
                        creation_time_s=plane.creation_time_s,
                        incident_wave_active=plane.incident_wave_active,
                    ).longitudinal_coordinates(next_time)[1]
                    for plane in advanced
                )
                new_x = new_motion.longitudinal_coordinates(next_time)[1]
                expected_spacing = case.speed_mps * plane_interval
                creation_spacing_errors.append(
                    abs((new_x - existing_foremost_x) - expected_spacing)
                )
            advanced.append(
                ActiveGroundPlane(
                    creation_parameter,
                    new_state,
                    case.has_incident_wave,
                )
            )
        active = advanced

    if executor is not None:
        executor.shutdown(wait=True)
    if progress_callback is not None:
        progress_callback(len(time), len(time), float(time[-1]))

    maximum_station_count = max(len(values) for values in station_x_history)
    station_x = _pad_station_history(
        station_x_history,
        width=maximum_station_count,
        fill_value=np.nan,
    )
    station_force = _pad_station_history(
        station_force_history,
        width=maximum_station_count,
        fill_value=np.nan,
    )
    station_creation = _pad_station_history(
        station_creation_history,
        width=maximum_station_count,
        fill_value=np.nan,
    )
    station_age = _pad_station_history(
        station_age_history,
        width=maximum_station_count,
        fill_value=np.nan,
    )
    station_contact = _pad_station_history(
        station_contact_history,
        width=maximum_station_count,
        fill_value=np.nan,
    )
    station_jet_cut = _pad_station_history(
        station_jet_cut_history,
        width=maximum_station_count,
        fill_value=-1,
        dtype=int,
    )

    return PlaningForcedMotion2DtResult(
        time_s=time,
        generalized_load=loads,
        raw_bem_generalized_load=raw_bem_loads,
        resolved_station_generalized_load=resolved_station_loads,
        transom_extrapolation_generalized_load=transom_extrapolation_loads,
        longitudinal_bem_bin_generalized_load=longitudinal_bem_bin_loads,
        pre_chine_bem_generalized_load=pre_chine_bem_loads,
        post_chine_bem_generalized_load=post_chine_bem_loads,
        bem_generalized_load=bem_loads,
        front_generalized_load=front_loads,
        transom_generalized_load=transom_loads,
        front_approximation_length_m=front_lengths,
        transom_correction_length_m=transom_lengths,
        active_plane_count=counts,
        max_potential_bvp_relative_residual=potential_residual,
        max_potential_bvp_condition_number=potential_condition,
        max_pressure_bvp_relative_residual=pressure_residual,
        max_pressure_bvp_condition_number=pressure_condition,
        max_free_surface_pressure_abs_pa=free_pressure,
        max_contact_constraint_abs_m=contact_residual,
        aftmost_resolved_station_x_m=aftmost_resolved_station_x,
        foremost_resolved_station_x_m=foremost_resolved_station_x,
        transom_coverage_gap_m=transom_coverage_gap,
        station_x_from_transom_m=station_x,
        station_force_density_n_m=station_force,
        station_creation_parameter_s=station_creation,
        station_age_parameter_s=station_age,
        station_contact_half_beam_m=station_contact,
        station_jet_cut_count=station_jet_cut,
        minimum_matrix_station_count=int(np.min(counts)),
        metadata={
            "status": PLANING_FORCED_MOTION_2DT_STATUS,
            "source": "Sun_2007_Eq7.23_to_7.45_and_Fig7.12",
            "incident_wave_included": case.has_incident_wave,
            "incident_wave_formulation": (
                "Sun_Faltinsen_Eq3_11_to_18_21_to_22_direct_cross_plane"
                if case.has_incident_wave
                else "none"
            ),
            "incident_wave_amplitude_m": case.incident_wave_amplitude_m,
            "incident_wave_omega0_rad_s": case.incident_wave_omega0_rad_s,
            "incident_wave_encounter_omega_rad_s": (
                case.omega_rad_s if case.has_incident_wave else None
            ),
            "incident_wave_wavenumber_rad_m": case.incident_wave_wavenumber_rad_m,
            "incident_wave_phase_at_cg_rad": case.incident_wave_phase_at_cg_rad,
            "incident_wave_activation_rule": (
                "initial_Nx_planes_calm_then_each_new_bow_plane_uses_full_incident_wave"
                if case.has_incident_wave
                else "not_applicable"
            ),
            "front_approximation_included": True,
            "front_approximation_equations": "Sun_2007_Eq7.36_to_7.45",
            "front_added_mass_cm": case.front_added_mass_cm,
            "front_pileup_factor": case.front_pileup_factor,
            "front_similarity_reference_deadrise_deg": 20.0,
            "transom_3d_correction_included": case.transom_correction_mode != "none",
            "transom_3d_correction_mode": case.transom_correction_mode,
            "transom_3d_correction_equations": (
                "Sun_2007_Sec7.3.1_effective_keel_wetted_length_reduction"
                if case.transom_keel_reduction_beams > 0.0
                else "Sun_2007_Eq3.30_to_3.33_and_Eq7.19_to_7.22"
                if case.transom_correction_enabled
                else "none"
            ),
            "transom_patch_length_beams": case.transom_patch_length_beams,
            "transom_fit_limit_beams": case.transom_fit_limit_beams,
            "transom_keel_reduction_beams": case.transom_keel_reduction_beams,
            "wagner_initializer_included": config.initializer == "wagner",
            "element_interpolation": config.element_interpolation,
            "pressure_interpolation": config.pressure_interpolation,
            "free_surface_spacing_mode": config.free_surface_spacing_mode,
            "free_surface_remesh_included": config.free_surface_remesh_enabled,
            "free_surface_remesh_interval_s": config.free_surface_remesh_interval_s,
            "free_surface_smoothing_included": config.free_surface_smoothing_enabled,
            "free_surface_smoothing_node_count": config.free_surface_smoothing_node_count,
            "free_surface_smoothing_interval_s": (
                config.free_surface_smoothing_interval_s
            ),
            "free_surface_uniform_near_body_panel_count": (
                config.free_surface_uniform_near_body_panel_count
            ),
            "lateral_symmetry_enforced": config.enforce_lateral_symmetry,
            "knuckle_separation_model": config.knuckle_separation_model,
            "jet_cut_included": config.jet_cut_enabled,
            "jet_cut_method": config.jet_cut_method,
            "jet_cut_distance_fraction": config.jet_cut_distance_fraction,
            "jet_cut_search_node_count": config.jet_cut_search_node_count,
            "jet_cut_ordering_safeguard_enabled": (
                config.jet_cut_ordering_safeguard_enabled
            ),
            "jet_cut_angle_threshold_deg": config.jet_cut_angle_threshold_deg,
            "jet_cut_angle_length_fraction": config.jet_cut_angle_length_fraction,
            "jet_cut_angle_hull_arc_length_m": (
                config.jet_cut_angle_hull_arc_length_m
            ),
            "jet_cut_max_corrective_passes": config.jet_cut_max_corrective_passes,
            "maximum_jet_cut_count_per_plane": maximum_jet_cut_count_per_plane,
            "minimum_jet_normal_distance_ratio": (
                min(jet_distance_ratios) if jet_distance_ratios else None
            ),
            "minimum_jet_projection_ratio": (
                min(jet_projection_minima) if jet_projection_minima else None
            ),
            "maximum_jet_projection_ratio": (
                max(jet_projection_maxima) if jet_projection_maxima else None
            ),
            "spray_cut_included": False,
            "spray_topology_diagnostic_source": "Sun_2007_Sec2.5_Fig2.3_precursor_only",
            "maximum_spray_overturning_panel_count": (
                maximum_spray_overturning_panel_count
            ),
            "minimum_spray_outward_tangent_cosine": (
                min(spray_outward_tangent_cosines)
                if spray_outward_tangent_cosines
                else None
            ),
            "minimum_spray_nonadjacent_distance_ratio": (
                min(spray_nonadjacent_distance_ratios)
                if spray_nonadjacent_distance_ratios
                else None
            ),
            "ground_plane_handoff_mode": case.ground_plane_handoff_mode,
            "parallel_workers": workers,
            "bem_internal_time_step_s": dt,
            "maximum_matrix_station_count": maximum_station_count,
            "ground_plane_interval_s": plane_interval,
            "bem_substeps_per_ground_plane_interval": plane_creation_stride,
            "maximum_creation_draft_error_m": (
                max(creation_draft_errors) if creation_draft_errors else 0.0
            ),
            "maximum_creation_draft_deviation_from_steady_handoff_m": (
                max(creation_draft_errors) if creation_draft_errors else 0.0
            ),
            "creation_draft_interpretation": (
                "actual_section_submergence_at_fixed_grid_introduction; "
                "deviation_from_steady_handoff_is_physical_in_forced_motion"
            ),
            "minimum_creation_draft_m": (
                min(creation_drafts) if creation_drafts else case.initial_draft_m
            ),
            "maximum_creation_draft_m": (
                max(creation_drafts) if creation_drafts else case.initial_draft_m
            ),
            "maximum_ground_plane_spacing_error_m": (
                max(creation_spacing_errors) if creation_spacing_errors else 0.0
            ),
            "wet_plane_removal_count": wet_plane_removal_count,
            "contact_exit_removal_count": contact_exit_removal_count,
            "transom_exit_removal_count": transom_exit_removal_count,
            "forward_interval_exit_removal_count": (
                forward_interval_exit_removal_count
            ),
            "below_handoff_draft_removal_count": (
                below_handoff_draft_removal_count
            ),
            "fixed_plane_deferred_creation_count": fixed_plane_deferred_creation_count,
            "fixed_plane_expired_before_activation_count": (
                fixed_plane_expired_before_activation_count
            ),
            "fixed_plane_pending_count_at_end": len(pending_fixed_creation_parameters),
            "fixed_plane_localized_activation_count": (
                fixed_plane_localized_activation_count
            ),
            "fixed_plane_maximum_removed_time_quantization_s": (
                fixed_plane_maximum_removed_time_quantization_s
            ),
            "fixed_plane_activation_rule": (
                "Earth-fixed equal-spacing plane initialized by Wagner at its "
                "scheduled introduction time using the actual positive section draft"
                if scheduled_wagner
                else "Earth-fixed plane retained; Wagner initialization localized when "
                "actual section draft first reaches the BEM handoff threshold"
            ),
            "maximum_raw_transom_coverage_gap_m": float(np.max(transom_coverage_gap)),
            "longitudinal_bem_bin_labels": longitudinal_bin_labels,
            "longitudinal_bem_bin_edges_m": longitudinal_bin_edges.tolist(),
            "longitudinal_bem_bin_rule": (
                "three_equal_post_chine_intervals_plus_one_pre_chine_interval"
            ),
            "transom_endpoint_rule": "linear_extrapolation_from_two_aftmost_ground_planes",
            "chine_region_decomposition": "Eq7.3_mean_split_when_mean_wetted_length_is_supplied",
            "response_calibration_used": False,
            **case.metadata,
        },
    )


def identify_planing_forced_motion_column(
    simulation: PlaningForcedMotion2DtResult,
    case: PlaningForcedMotionCase,
    *,
    restoring_column: np.ndarray,
    discard_cycles: float = 1.0,
    retained_cycles: float | None = None,
    fitted_harmonics: int = 3,
) -> IdentifiedPlaningForcedMotionColumn:
    if not np.allclose(simulation.time_s, case.time_s, rtol=0.0, atol=1e-12):
        raise ValueError("Planing forced-motion simulation and case time grids differ.")
    column = extract_forced_motion_column(
        simulation.time_s,
        simulation.generalized_load,
        motion_dof=case.motion_dof,  # type: ignore[arg-type]
        omega_rad_s=case.omega_rad_s,
        motion_amplitude=case.motion_amplitude,
        restoring_column=np.asarray(restoring_column, dtype=float),
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=fitted_harmonics,
    )
    return IdentifiedPlaningForcedMotionColumn(simulation=simulation, column=column)


def identify_planing_incident_wave_excitation(
    simulation: PlaningForcedMotion2DtResult,
    case: PlaningForcedMotionCase,
    *,
    discard_cycles: float = 1.0,
    retained_cycles: float | None = None,
    fitted_harmonics: int = 3,
) -> IdentifiedPlaningIncidentWaveExcitation:
    """Identify direct 2D+t wave excitation using the encounter harmonic.

    Loads are represented as ``Re(F_hat*exp(i*omega_e*t))``. With the shared
    harmonic fitter convention ``s*sin+c*cos``, the complex amplitude is
    therefore ``c-i*s``. No response or experimental result enters this
    identification.
    """

    if not case.has_incident_wave or case.incident_wave_amplitude_m <= 0.0:
        raise ValueError("A non-zero incident wave is required for excitation identification.")
    if case.motion_dof != "fixed":
        raise ValueError("Direct incident-wave excitation must be identified on a fixed hull.")
    if not np.allclose(simulation.time_s, case.time_s, rtol=0.0, atol=1e-12):
        raise ValueError("Incident-wave simulation and case time grids differ.")

    component_histories = {
        "total": simulation.generalized_load,
        "bem": simulation.bem_generalized_load,
        "front": simulation.front_generalized_load,
        "transom": simulation.transom_generalized_load,
        "raw_bem": simulation.raw_bem_generalized_load,
        "resolved_station": simulation.resolved_station_generalized_load,
        "transom_extrapolation": simulation.transom_extrapolation_generalized_load,
        "pre_chine_bem": simulation.pre_chine_bem_generalized_load,
        "post_chine_bem": simulation.post_chine_bem_generalized_load,
    }
    fits = {
        name: fit_periodic_harmonics(
            simulation.time_s,
            values,
            case.omega_rad_s,
            discard_cycles=discard_cycles,
            retained_cycles=retained_cycles,
            fitted_harmonics=fitted_harmonics,
        )
        for name, values in component_histories.items()
    }
    amplitude = float(case.incident_wave_amplitude_m)
    components = {
        name: (fit.cosine - 1j * fit.sine) / amplitude
        for name, fit in fits.items()
    }
    total_fit = fits["total"]
    return IdentifiedPlaningIncidentWaveExcitation(
        simulation=simulation,
        harmonic_fit=total_fit,
        excitation_per_wave_amplitude=components["total"],
        component_excitation_per_wave_amplitude=components,
        metadata={
            "source": "Sun_Faltinsen_incident_wave_Eq3_11_to_18_21_to_22",
            "complex_load_convention": "Re(F_hat*exp(i*omega_e*t)); F_hat=cosine-i*sine",
            "load_order": "vertical_force_bow_up_pitch_moment",
            "omega0_rad_s": case.incident_wave_omega0_rad_s,
            "omega_e_rad_s": case.omega_rad_s,
            "wavenumber_rad_m": case.incident_wave_wavenumber_rad_m,
            "wave_amplitude_m": case.incident_wave_amplitude_m,
            "maximum_total_harmonic_residual_nrmse": float(
                np.max(total_fit.residual_nrmse)
            ),
            "response_calibration_used": False,
        },
    )


def run_planing_forced_motion_frequency(
    wedge_config: MovingWedgeConfig,
    heave_case: PlaningForcedMotionCase,
    pitch_case: PlaningForcedMotionCase,
    *,
    restoring_matrix: np.ndarray,
    discard_cycles: float = 1.0,
    retained_cycles: float | None = None,
    fitted_harmonics: int = 3,
) -> PlaningForcedMotionFrequencyResult:
    """Run both prescribed columns and assemble one frequency-dependent matrix."""

    if heave_case.motion_dof != "heave" or pitch_case.motion_dof != "pitch":
        raise ValueError("Cases must be supplied in forced-heave then forced-pitch order.")
    shared_names = (
        "speed_mps",
        "mean_trim_rad",
        "wetted_length_m",
        "lcg_from_transom_m",
        "omega_rad_s",
        "duration_s",
        "time_step_s",
        "ground_plane_interval_s",
        "initial_draft_m",
        "rho_water_kg_m3",
        "gravity_m_s2",
        "front_added_mass_cm",
        "front_pileup_factor",
        "mean_wetted_length_beam_ratio",
        "transom_correction_enabled",
        "transom_patch_length_beams",
        "transom_fit_limit_beams",
    )
    def shared_value_matches(name: str) -> bool:
        heave_value = getattr(heave_case, name)
        pitch_value = getattr(pitch_case, name)
        if heave_value is None or pitch_value is None:
            return heave_value is None and pitch_value is None
        return bool(np.isclose(heave_value, pitch_value, rtol=1e-12, atol=1e-14))

    if any(not shared_value_matches(name) for name in shared_names):
        raise ValueError("Forced-heave and forced-pitch cases must share the same physical condition.")
    restoring = np.asarray(restoring_matrix, dtype=float)
    if restoring.shape != (2, 2) or not np.isfinite(restoring).all():
        raise ValueError("restoring_matrix must be finite with shape (2, 2).")
    heave_simulation = run_planing_forced_motion_2dt(wedge_config, heave_case)
    pitch_simulation = run_planing_forced_motion_2dt(wedge_config, pitch_case)
    heave = identify_planing_forced_motion_column(
        heave_simulation,
        heave_case,
        restoring_column=restoring[:, 0],
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=fitted_harmonics,
    )
    pitch = identify_planing_forced_motion_column(
        pitch_simulation,
        pitch_case,
        restoring_column=restoring[:, 1],
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=fitted_harmonics,
    )
    return PlaningForcedMotionFrequencyResult(
        heave=heave,
        pitch=pitch,
        matrices=assemble_forced_motion_matrices(heave.column, pitch.column),
    )
