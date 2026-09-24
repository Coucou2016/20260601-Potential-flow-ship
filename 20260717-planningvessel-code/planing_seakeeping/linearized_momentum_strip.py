from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from .config import BoatConfig
from .equilibrium import EquilibriumState
from .longitudinal_response import (
    LongitudinalFrequencyModel,
    faltinsen_head_sea_excitation,
    finite_length_strip_factors,
    planing_target_context,
)
from .types import LongitudinalHydrodynamicMatrices


@dataclass(frozen=True)
class MomentumStripOptions:
    station_count: int = 401
    wagner_pileup_factor: float = math.pi / 2.0
    wedge_added_mass_coefficient: float = 1.0
    buoyancy_force_factor: float = 0.5
    buoyancy_moment_factor: float = 0.25
    crossflow_drag_coefficient: float | None = None
    momentum_rate_formulation: str = "relative_velocity_squared"

    def validate(self) -> None:
        if self.station_count < 101 or self.station_count % 2 == 0:
            raise ValueError("station_count must be an odd integer >=101.")
        if self.wagner_pileup_factor <= 0.0:
            raise ValueError("wagner_pileup_factor must be positive.")
        if self.wedge_added_mass_coefficient <= 0.0:
            raise ValueError("wedge_added_mass_coefficient must be positive.")
        if self.buoyancy_force_factor < 0.0 or self.buoyancy_moment_factor < 0.0:
            raise ValueError("buoyancy factors must be non-negative.")
        if self.crossflow_drag_coefficient is not None and self.crossflow_drag_coefficient < 0.0:
            raise ValueError("crossflow_drag_coefficient must be non-negative when supplied.")
        if self.momentum_rate_formulation not in {
            "relative_velocity_squared",
            "sun_faltinsen_2007_eq7_36_to_7_45",
        }:
            raise ValueError(
                "momentum_rate_formulation must be relative_velocity_squared or "
                "sun_faltinsen_2007_eq7_36_to_7_45."
            )


@dataclass(frozen=True)
class MomentumStripLinearization:
    added_mass: np.ndarray
    damping: np.ndarray
    restoring: np.ndarray
    base_generalized_load: np.ndarray
    station_x_from_transom_m: np.ndarray
    base_penetration_m: np.ndarray
    metadata: dict[str, Any]


def _station_grid(equilibrium: EquilibriumState, options: MomentumStripOptions) -> np.ndarray:
    wetted_length = float(equilibrium.geometry.keel_wetted_length_m)
    if wetted_length <= 0.0:
        raise ValueError("The momentum-strip model requires positive keel wetted length.")
    # Midpoint stations avoid evaluating the nonsmooth leading-edge endpoint.
    edges = np.linspace(0.0, wetted_length, options.station_count + 1)
    return 0.5 * (edges[:-1] + edges[1:])


def _section_properties(
    penetration_m: np.ndarray,
    boat: BoatConfig,
    options: MomentumStripOptions,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    penetration = np.maximum(np.asarray(penetration_m, dtype=float), 0.0)
    beta = math.radians(boat.deadrise_deg)
    tan_beta = max(math.tan(beta), 1.0e-10)
    chine_half_beam = 0.5 * boat.beam_m
    uncapped_half_beam = options.wagner_pileup_factor * penetration / tan_beta
    half_beam = np.minimum(chine_half_beam, uncapped_half_beam)
    half_beam_derivative = np.where(
        uncapped_half_beam < chine_half_beam,
        options.wagner_pileup_factor / tan_beta,
        0.0,
    )
    half_beam_derivative = np.where(penetration > 0.0, half_beam_derivative, 0.0)

    added_mass = (
        options.wedge_added_mass_coefficient
        * 0.5
        * math.pi
        * boat.rho_water_kg_m3
        * half_beam**2
    )
    added_mass_derivative = (
        options.wedge_added_mass_coefficient
        * math.pi
        * boat.rho_water_kg_m3
        * half_beam
        * half_beam_derivative
    )

    chine_penetration = chine_half_beam * tan_beta / options.wagner_pileup_factor
    wedge_area = penetration**2 / tan_beta
    chine_area = chine_penetration**2 / tan_beta
    full_beam_area = chine_area + boat.beam_m * np.maximum(penetration - chine_penetration, 0.0)
    immersed_area = np.where(penetration <= chine_penetration, wedge_area, full_beam_area)
    return half_beam, added_mass, added_mass_derivative, immersed_area


def _generalized_load(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    options: MomentumStripOptions,
    station_x_from_transom_m: np.ndarray,
    *,
    displacement: np.ndarray | None = None,
    velocity: np.ndarray | None = None,
    acceleration: np.ndarray | None = None,
    wave_amplitude_m: float = 0.0,
    wave_number_rad_m: float = 0.0,
    wave_omega_rad_s: float = 0.0,
    encounter_omega_rad_s: float = 0.0,
    time_s: float = 0.0,
) -> np.ndarray:
    displacement = np.zeros(2) if displacement is None else np.asarray(displacement, dtype=float)
    velocity = np.zeros(2) if velocity is None else np.asarray(velocity, dtype=float)
    acceleration = np.zeros(2) if acceleration is None else np.asarray(acceleration, dtype=float)
    if displacement.shape != (2,) or velocity.shape != (2,) or acceleration.shape != (2,):
        raise ValueError("displacement, velocity and acceleration must have shape (2,).")

    x_from_cg = station_x_from_transom_m - boat.lcg_m
    trim = float(equilibrium.trim_rad)
    speed = float(equilibrium.speed_through_water_mps)
    base_penetration = np.maximum(
        (equilibrium.geometry.keel_wetted_length_m - station_x_from_transom_m) * math.sin(trim),
        0.0,
    )

    phase = encounter_omega_rad_s * float(time_s) + wave_number_rad_m * x_from_cg
    wave_elevation = float(wave_amplitude_m) * np.sin(phase)
    wave_normal_velocity = (
        float(wave_amplitude_m) * float(wave_omega_rad_s) * np.cos(phase)
    )
    # At a body-fixed station the incident-wave vertical velocity oscillates
    # at the encounter frequency.  Therefore d(w)/dt carries omega_0*omega_e,
    # as in Faltinsen (2006), Eqs. 9.100--9.113, rather than omega_0**2.
    wave_normal_acceleration = -(
        float(wave_amplitude_m)
        * float(wave_omega_rad_s)
        * float(encounter_omega_rad_s)
        * np.sin(phase)
    )

    local_displacement = displacement[0] + x_from_cg * displacement[1]
    local_velocity = velocity[0] + x_from_cg * velocity[1]
    local_acceleration = acceleration[0] + x_from_cg * acceleration[1]
    penetration = base_penetration - local_displacement + wave_elevation
    half_beam, added_mass, added_mass_derivative, immersed_area = _section_properties(
        penetration, boat, options
    )

    # D/Dt = partial/partial_t - U partial/partial_x for a water plane moving
    # from the leading edge toward the transom in the body-fixed system.
    normal_velocity = (
        speed * math.sin(trim)
        - local_velocity
        + speed * displacement[1] * math.cos(trim)
        + wave_normal_velocity
    )
    normal_acceleration = (
        -local_acceleration
        + 2.0 * speed * velocity[1] * math.cos(trim)
        + wave_normal_acceleration
    )
    if options.momentum_rate_formulation == "sun_faltinsen_2007_eq7_36_to_7_45":
        distance_aft_of_leading_edge = (
            equilibrium.geometry.keel_wetted_length_m - station_x_from_transom_m
        )
        # Sun (2007), Eqs. 7.42--7.45: Dd/Dt controls DA/Dt and is
        # distinct from the relative entry velocity V during forced motion.
        added_mass_material_velocity = (
            speed * math.sin(trim)
            + speed * displacement[1] * math.cos(trim)
            + distance_aft_of_leading_edge * velocity[1]
            + wave_normal_velocity
        )
    else:
        added_mass_material_velocity = normal_velocity
    momentum_rate = (
        added_mass * normal_acceleration
        + added_mass_derivative * added_mass_material_velocity * normal_velocity
    )
    crossflow_drag_coefficient = (
        math.cos(math.radians(boat.deadrise_deg))
        if options.crossflow_drag_coefficient is None
        else options.crossflow_drag_coefficient
    )
    crossflow_drag = (
        0.5
        * boat.rho_water_kg_m3
        * crossflow_drag_coefficient
        * half_beam
        * normal_velocity
        * np.abs(normal_velocity)
    )
    normal_force_per_m = momentum_rate + crossflow_drag
    vertical_dynamic_per_m = normal_force_per_m * math.cos(trim)
    buoyancy_per_m = (
        options.buoyancy_force_factor
        * boat.rho_water_kg_m3
        * boat.gravity_m_s2
        * immersed_area
    )

    heave_load = np.trapezoid(vertical_dynamic_per_m + buoyancy_per_m, station_x_from_transom_m)
    pitch_load = np.trapezoid(
        vertical_dynamic_per_m * x_from_cg
        + (options.buoyancy_moment_factor / max(options.buoyancy_force_factor, 1.0e-12))
        * buoyancy_per_m
        * x_from_cg,
        station_x_from_transom_m,
    )
    return np.asarray([heave_load, pitch_load], dtype=float)


def linearize_momentum_strip(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    options: MomentumStripOptions | None = None,
) -> MomentumStripLinearization:
    options = options or MomentumStripOptions()
    options.validate()
    x = _station_grid(equilibrium, options)
    base = _generalized_load(boat, equilibrium, options, x)
    added_mass = np.zeros((2, 2), dtype=float)
    damping = np.zeros((2, 2), dtype=float)
    restoring = np.zeros((2, 2), dtype=float)
    displacement_steps = np.asarray([max(1.0e-6, 1.0e-5 * boat.beam_m), 1.0e-6])
    velocity_steps = np.asarray([max(1.0e-6, 1.0e-5 * equilibrium.speed_through_water_mps), 1.0e-5])
    acceleration_steps = np.asarray(
        [max(1.0e-5, 1.0e-5 * boat.gravity_m_s2), max(1.0e-5, 1.0e-5 * boat.gravity_m_s2 / boat.length_m)]
    )
    for column in range(2):
        unit = np.zeros(2)
        unit[column] = displacement_steps[column]
        restoring[:, column] = -(
            _generalized_load(boat, equilibrium, options, x, displacement=unit)
            - _generalized_load(boat, equilibrium, options, x, displacement=-unit)
        ) / (2.0 * displacement_steps[column])

        unit = np.zeros(2)
        unit[column] = velocity_steps[column]
        damping[:, column] = -(
            _generalized_load(boat, equilibrium, options, x, velocity=unit)
            - _generalized_load(boat, equilibrium, options, x, velocity=-unit)
        ) / (2.0 * velocity_steps[column])

        unit = np.zeros(2)
        unit[column] = acceleration_steps[column]
        added_mass[:, column] = -(
            _generalized_load(boat, equilibrium, options, x, acceleration=unit)
            - _generalized_load(boat, equilibrium, options, x, acceleration=-unit)
        ) / (2.0 * acceleration_steps[column])

    base_penetration = np.maximum(
        (equilibrium.geometry.keel_wetted_length_m - x) * math.sin(equilibrium.trim_rad), 0.0
    )
    crossflow_drag_coefficient = (
        math.cos(math.radians(boat.deadrise_deg))
        if options.crossflow_drag_coefficient is None
        else options.crossflow_drag_coefficient
    )
    source = (
        "Sun_2007_Eq7.36_to_7.45_forced_motion_linearization"
        if options.momentum_rate_formulation == "sun_faltinsen_2007_eq7_36_to_7_45"
        else "Zarnick_1978_relative_entry_velocity_momentum_linearization"
    )
    return MomentumStripLinearization(
        added_mass=added_mass,
        damping=damping,
        restoring=restoring,
        base_generalized_load=base,
        station_x_from_transom_m=x,
        base_penetration_m=base_penetration,
        metadata={
            "source": source,
            "station_count": options.station_count,
            "wagner_pileup_factor": options.wagner_pileup_factor,
            "wedge_added_mass_coefficient": options.wedge_added_mass_coefficient,
            "crossflow_drag_coefficient": crossflow_drag_coefficient,
            "buoyancy_force_factor": options.buoyancy_force_factor,
            "buoyancy_moment_factor": options.buoyancy_moment_factor,
            "momentum_rate_formulation": options.momentum_rate_formulation,
            "added_mass_material_velocity_distinct_from_relative_entry_velocity": (
                options.momentum_rate_formulation
                == "sun_faltinsen_2007_eq7_36_to_7_45"
            ),
            "response_calibration_used": False,
        },
    )


def momentum_strip_wave_excitation_per_amplitude(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    options: MomentumStripOptions,
    x: np.ndarray,
    wavenumber_rad_m: np.ndarray,
    wave_omega_rad_s: np.ndarray,
    encounter_omega_rad_s: np.ndarray,
) -> np.ndarray:
    """Linear wave excitation from the same local planing-strip load law.

    The incident elevation and vertical velocity retain their station phase;
    the body-fixed vertical acceleration uses ``omega_0 * omega_e``.  The
    central wave-amplitude derivative keeps the result independent of any
    measured motion response.
    """

    wavenumber_rad_m = np.asarray(wavenumber_rad_m, dtype=float)
    wave_omega_rad_s = np.asarray(wave_omega_rad_s, dtype=float)
    encounter_omega_rad_s = np.asarray(encounter_omega_rad_s, dtype=float)
    if (
        wavenumber_rad_m.ndim != 1
        or wave_omega_rad_s.shape != wavenumber_rad_m.shape
        or encounter_omega_rad_s.shape != wavenumber_rad_m.shape
        or np.any(wavenumber_rad_m <= 0.0)
        or np.any(wave_omega_rad_s <= 0.0)
        or np.any(encounter_omega_rad_s <= 0.0)
    ):
        raise ValueError("Wave numbers, wave frequencies and encounter frequencies must be matching positive arrays.")
    excitation = np.empty((len(wavenumber_rad_m), 2), dtype=complex)
    perturbation = max(1.0e-7, 1.0e-5 * boat.beam_m)
    for index, (k, omega0, omega_e) in enumerate(
        zip(wavenumber_rad_m, wave_omega_rad_s, encounter_omega_rad_s)
    ):
        values = []
        for time_s in (0.0, 0.5 * math.pi / float(omega_e)):
            positive = _generalized_load(
                boat,
                equilibrium,
                options,
                x,
                wave_amplitude_m=perturbation,
                wave_number_rad_m=float(k),
                wave_omega_rad_s=float(omega0),
                encounter_omega_rad_s=float(omega_e),
                time_s=time_s,
            )
            negative = _generalized_load(
                boat,
                equilibrium,
                options,
                x,
                wave_amplitude_m=-perturbation,
                wave_number_rad_m=float(k),
                wave_omega_rad_s=float(omega0),
                encounter_omega_rad_s=float(omega_e),
                time_s=time_s,
            )
            values.append((positive - negative) / (2.0 * perturbation))
        excitation[index] = values[0] - 1j * values[1]
    return excitation


def build_linearized_momentum_strip_model(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    wavelength_m: np.ndarray,
    wave_amplitude_m: np.ndarray | float,
    *,
    point_x_forward_m: float,
    options: MomentumStripOptions | None = None,
    quasi_static_restoring: np.ndarray | None = None,
    quasi_static_restoring_source: str = "zarnick1978_strip_load_derivative",
    excitation_formulation: str = "zarnick1978_same_strip_wave_derivative",
    excitation_phase_length_m: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> LongitudinalFrequencyModel:
    options = options or MomentumStripOptions()
    linearization = linearize_momentum_strip(boat, equilibrium, options)
    wavelength = np.asarray(wavelength_m, dtype=float)
    if wavelength.ndim != 1 or len(wavelength) == 0 or np.any(wavelength <= 0.0):
        raise ValueError("wavelength_m must be a non-empty positive one-dimensional array.")
    wavenumber = 2.0 * math.pi / wavelength
    omega0 = np.sqrt(boat.gravity_m_s2 * wavenumber)
    omega_e = omega0 + wavenumber * equilibrium.speed_through_water_mps
    n = len(wavelength)
    added = np.repeat(linearization.added_mass[None, :, :], n, axis=0)
    damping = np.repeat(linearization.damping[None, :, :], n, axis=0)
    if quasi_static_restoring is None:
        restoring_matrix = linearization.restoring
    else:
        restoring_matrix = np.asarray(quasi_static_restoring, dtype=float)
        if restoring_matrix.shape != (2, 2) or not np.isfinite(restoring_matrix).all():
            raise ValueError("quasi_static_restoring must be a finite 2x2 matrix.")
    restoring = np.repeat(restoring_matrix[None, :, :], n, axis=0)
    if excitation_formulation == "zarnick1978_same_strip_wave_derivative":
        excitation = momentum_strip_wave_excitation_per_amplitude(
            boat,
            equilibrium,
            options,
            linearization.station_x_from_transom_m,
            wavenumber,
            omega0,
            omega_e,
        )
        heave_phase_factor = np.ones(n)
        pitch_phase_factor = np.ones(n)
    elif excitation_formulation == "faltinsen_eq9_110_to_9_117":
        phase_length = boat.length_m if excitation_phase_length_m is None else float(
            excitation_phase_length_m
        )
        heave_phase_factor, pitch_phase_factor = finite_length_strip_factors(
            wavenumber, phase_length
        )
        excitation = faltinsen_head_sea_excitation(
            added,
            damping,
            restoring,
            omega0,
            omega_e,
            wavenumber,
            equilibrium.speed_through_water_mps,
            heave_finite_length_factor=heave_phase_factor,
            pitch_finite_length_factor=pitch_phase_factor,
        )
    else:
        raise ValueError(f"Unsupported excitation_formulation: {excitation_formulation}")
    hydro = LongitudinalHydrodynamicMatrices(
        solver_omega_rad_s=omega_e,
        encounter_omega_rad_s=omega_e,
        added_mass=added,
        radiation_damping=damping,
        metadata={
            "matrix_contract": "heave_pitch_2x2_v1",
            "provider_route": "zarnick1978_linearized_momentum_strip",
            "coefficient_frequency_dependence": "quasi_steady_constant_with_frequency_dependent_wave_excitation",
            "force_harmonic_convention": "Re(F_hat*exp(i*omega_e*t))",
            **linearization.metadata,
        },
    )
    rigid_mass = np.diag(
        [boat.mass_kg, boat.mass_kg * boat.pitch_radius_gyration_m**2]
    ).astype(float)
    return LongitudinalFrequencyModel(
        hydrodynamics=hydro,
        rigid_mass=rigid_mass,
        restoring=restoring,
        excitation_per_wave_amplitude=excitation,
        omega0_rad_s=omega0,
        wavenumber_rad_m=wavenumber,
        wavelength_m=wavelength,
        wave_amplitude_m=wave_amplitude_m,
        point_x_forward_m=float(point_x_forward_m),
        heave_finite_length_factor=heave_phase_factor,
        pitch_finite_length_factor=pitch_phase_factor,
        metadata={
            "equation_of_motion": "[-omega_e^2(M+A)+i*omega_e*B+C]xi=F_exc",
            "excitation_formulation": excitation_formulation,
            "heave_positive": "up",
            "pitch_positive": "bow_up",
            "longitudinal_point_axis": "positive_forward_from_cg",
            "wave_at_cg": "zeta_a*sin(omega_e*t)",
            "response_calibration_used": False,
            "quasi_static_restoring_source": quasi_static_restoring_source,
            **(metadata or {}),
            "target_context": planing_target_context(boat, equilibrium),
        },
    )
