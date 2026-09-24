from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

from .coefficients import HydroMatrices
from .config import BoatConfig
from .equilibrium import EquilibriumState
from .types import LongitudinalHydrodynamicMatrices


def _as_float_array(value: np.ndarray | float, size: int, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        array = np.full(size, float(array), dtype=float)
    if array.shape != (size,):
        raise ValueError(f"{name} must have shape ({size},).")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values.")
    return array


def wrap_phase_deg(value: np.ndarray | float) -> np.ndarray:
    """Wrap an angle to [-180, 180) degrees."""

    angle = np.asarray(value, dtype=float)
    return (angle + 180.0) % 360.0 - 180.0


def circular_difference_deg(first: np.ndarray | float, second: np.ndarray | float) -> np.ndarray:
    return wrap_phase_deg(np.asarray(first, dtype=float) - np.asarray(second, dtype=float))


def planing_target_context(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
) -> dict[str, float | str]:
    """Return the physical state that a frequency-dependent matrix must match."""

    return {
        "beam_m": float(boat.beam_m),
        "deadrise_deg": float(boat.deadrise_deg),
        "trim_deg": float(equilibrium.trim_deg),
        "fn_b": float(equilibrium.fn_b),
        "mean_wetted_length_over_b": float(equilibrium.geometry.lambda_w),
        "lcg_from_transom_m": float(boat.lcg_m),
        "rho_water_kg_m3": float(boat.rho_water_kg_m3),
        "gravity_m_s2": float(boat.gravity_m_s2),
        "matrix_coordinate_contract": (
            "heave_up_pitch_bow_up_force_and_moment_about_cg"
        ),
    }


def finite_length_strip_factors(wavenumber_rad_m: np.ndarray, phase_length_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Return Faltinsen Eq. 9.95-9.98 finite-length phasing factors.

    The factors are the exact constant-section strip integrals divided by the
    long-wave heave-force and pitch-moment approximations. They tend to one as
    ``k L`` tends to zero and contain no empirical calibration.
    """

    if phase_length_m <= 0.0:
        raise ValueError("phase_length_m must be positive.")
    k = np.asarray(wavenumber_rad_m, dtype=float)
    s = k * float(phase_length_m)
    heave = np.ones_like(s)
    pitch = np.ones_like(s)
    regular = np.abs(s) > 1.0e-5
    sr = s[regular]
    heave[regular] = 2.0 * np.sin(0.5 * sr) / sr
    pitch[regular] = 12.0 * (-sr * np.cos(0.5 * sr) + 2.0 * np.sin(0.5 * sr)) / sr**3
    if np.any(~regular):
        ss = s[~regular]
        heave[~regular] = 1.0 - ss**2 / 24.0 + ss**4 / 1920.0
        pitch[~regular] = 1.0 - ss**2 / 40.0 + ss**4 / 4480.0
    return heave, pitch


def faltinsen_head_sea_excitation(
    added_mass: np.ndarray,
    radiation_damping: np.ndarray,
    restoring: np.ndarray,
    omega0_rad_s: np.ndarray,
    encounter_omega_rad_s: np.ndarray,
    wavenumber_rad_m: np.ndarray,
    speed_mps: float,
    *,
    heave_finite_length_factor: np.ndarray | float = 1.0,
    pitch_finite_length_factor: np.ndarray | float = 1.0,
) -> np.ndarray:
    """Assemble Faltinsen Eq. 9.110-9.117 head-sea excitation per wave amplitude.

    The returned phasor follows ``F_hat = F_c - i F_s`` under the package
    convention ``Re(F_hat exp(i omega_e t))``. The incident wave at the center
    of gravity is ``zeta_a sin(omega_e t)`` and therefore has phasor ``-i zeta_a``.
    """

    a = np.asarray(added_mass, dtype=float)
    b = np.asarray(radiation_damping, dtype=float)
    c = np.asarray(restoring, dtype=float)
    if a.ndim != 3 or a.shape[1:] != (2, 2):
        raise ValueError("added_mass must have shape (n_frequency, 2, 2).")
    n = a.shape[0]
    if b.shape != a.shape or c.shape != a.shape:
        raise ValueError("radiation_damping and restoring must match added_mass shape.")
    omega0 = _as_float_array(omega0_rad_s, n, "omega0_rad_s")
    omega_e = _as_float_array(encounter_omega_rad_s, n, "encounter_omega_rad_s")
    k = _as_float_array(wavenumber_rad_m, n, "wavenumber_rad_m")
    r3 = _as_float_array(heave_finite_length_factor, n, "heave_finite_length_factor")
    r5 = _as_float_array(pitch_finite_length_factor, n, "pitch_finite_length_factor")

    b33d = b[:, 0, 0]
    b53d = b[:, 1, 0]
    b35d = b[:, 0, 1] + float(speed_mps) * a[:, 0, 0]
    b55d = b[:, 1, 1] + float(speed_mps) * a[:, 0, 1]

    f3s = c[:, 0, 0] - a[:, 0, 0] * omega0 * omega_e - b35d * omega0 * k
    f3c = c[:, 0, 1] * k - a[:, 0, 1] * omega0 * omega_e * k + b33d * omega0
    f5s = c[:, 1, 0] - a[:, 1, 0] * omega0 * omega_e - b55d * omega0 * k
    f5c = c[:, 1, 1] * k - a[:, 1, 1] * omega0 * omega_e * k + b53d * omega0

    excitation = np.empty((n, 2), dtype=complex)
    excitation[:, 0] = r3 * (f3c - 1j * f3s)
    excitation[:, 1] = r5 * (f5c - 1j * f5s)
    return excitation


@dataclass(frozen=True)
class LongitudinalFrequencyModel:
    """Complete small-amplitude heave-pitch frequency-domain problem."""

    hydrodynamics: LongitudinalHydrodynamicMatrices
    rigid_mass: np.ndarray
    restoring: np.ndarray
    excitation_per_wave_amplitude: np.ndarray
    omega0_rad_s: np.ndarray
    wavenumber_rad_m: np.ndarray
    wavelength_m: np.ndarray
    wave_amplitude_m: np.ndarray
    point_x_forward_m: float
    heave_finite_length_factor: np.ndarray
    pitch_finite_length_factor: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = self.hydrodynamics.solver_omega_rad_s.size
        rigid = np.asarray(self.rigid_mass, dtype=float)
        restoring = np.asarray(self.restoring, dtype=float)
        excitation = np.asarray(self.excitation_per_wave_amplitude, dtype=complex)
        if rigid.shape != (2, 2):
            raise ValueError("rigid_mass must have shape (2, 2).")
        if restoring.shape != (n, 2, 2):
            raise ValueError(f"restoring must have shape ({n}, 2, 2).")
        if excitation.shape != (n, 2):
            raise ValueError(f"excitation_per_wave_amplitude must have shape ({n}, 2).")
        if not np.isfinite(rigid).all() or not np.isfinite(restoring).all():
            raise ValueError("Mass and restoring matrices must contain only finite values.")
        if not np.isfinite(excitation.real).all() or not np.isfinite(excitation.imag).all():
            raise ValueError("Excitation must contain only finite values.")
        if np.any(np.linalg.norm(excitation, axis=1) <= 1.0e-12):
            raise ValueError("Wave excitation must be non-zero at every solved frequency.")
        object.__setattr__(self, "rigid_mass", rigid)
        object.__setattr__(self, "restoring", restoring)
        object.__setattr__(self, "excitation_per_wave_amplitude", excitation)
        for name in (
            "omega0_rad_s",
            "wavenumber_rad_m",
            "wavelength_m",
            "wave_amplitude_m",
            "heave_finite_length_factor",
            "pitch_finite_length_factor",
        ):
            object.__setattr__(self, name, _as_float_array(getattr(self, name), n, name))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def dynamic_stiffness(self) -> np.ndarray:
        omega = self.hydrodynamics.solver_omega_rad_s[:, None, None]
        total_mass = self.rigid_mass[None, :, :] + self.hydrodynamics.added_mass
        return -(omega**2) * total_mass + 1j * omega * self.hydrodynamics.radiation_damping + self.restoring


def build_faltinsen_planing_model(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    matrices: HydroMatrices,
    wavelength_m: np.ndarray,
    wave_amplitude_m: np.ndarray | float,
    *,
    point_x_forward_m: float,
    phase_length_m: float,
    apply_finite_length_correction: bool = True,
    metadata: dict[str, Any] | None = None,
) -> LongitudinalFrequencyModel:
    """Adapt the Chapter 9 reduced-order coefficients to the frozen Gate 1 contract."""

    wavelength = np.asarray(wavelength_m, dtype=float)
    if wavelength.ndim != 1 or wavelength.size == 0 or np.any(wavelength <= 0.0):
        raise ValueError("wavelength_m must be a non-empty positive one-dimensional array.")
    n = wavelength.size
    k = 2.0 * np.pi / wavelength
    omega0 = np.sqrt(boat.gravity_m_s2 * k)
    omega_e = omega0 + k * equilibrium.speed_through_water_mps
    added = np.repeat(np.asarray(matrices.added_mass, dtype=float)[None, :, :], n, axis=0)
    damping = np.repeat(np.asarray(matrices.damping, dtype=float)[None, :, :], n, axis=0)
    restoring = np.repeat(np.asarray(matrices.restoring, dtype=float)[None, :, :], n, axis=0)
    if apply_finite_length_correction:
        r3, r5 = finite_length_strip_factors(k, phase_length_m)
    else:
        r3 = np.ones(n)
        r5 = np.ones(n)
    hydro = LongitudinalHydrodynamicMatrices(
        solver_omega_rad_s=omega_e,
        encounter_omega_rad_s=omega_e,
        added_mass=added,
        radiation_damping=damping,
        metadata={
            "matrix_contract": "heave_pitch_2x2_v1",
            "row_dofs": ("heave", "pitch"),
            "col_dofs": ("heave", "pitch"),
            "source_dof_indices": (2, 4),
            "provider_route": "faltinsen_ch9_reduced_order_planing",
            "gate1_contract_dependency": "ma2005_wigley_iii_gate1_passed",
            "coefficient_frequency_dependence": "constant_about_prescribed_running_state",
            "force_harmonic_convention": "F=omega_e^2*A-i*omega_e*B",
        },
    )
    excitation = faltinsen_head_sea_excitation(
        added,
        damping,
        restoring,
        omega0,
        omega_e,
        k,
        equilibrium.speed_through_water_mps,
        heave_finite_length_factor=r3,
        pitch_finite_length_factor=r5,
    )
    rigid = np.diag([boat.mass_kg, boat.mass_kg * boat.pitch_radius_gyration_m**2]).astype(float)
    return LongitudinalFrequencyModel(
        hydrodynamics=hydro,
        rigid_mass=rigid,
        restoring=restoring,
        excitation_per_wave_amplitude=excitation,
        omega0_rad_s=omega0,
        wavenumber_rad_m=k,
        wavelength_m=wavelength,
        wave_amplitude_m=wave_amplitude_m,
        point_x_forward_m=float(point_x_forward_m),
        heave_finite_length_factor=r3,
        pitch_finite_length_factor=r5,
        metadata={
            "equation_of_motion": "[-omega_e^2(M+A)+i*omega_e*B+C]xi=F_exc",
            "excitation_formulation": "faltinsen_eq9_110_to_9_117",
            "finite_length_formulation": (
                "faltinsen_eq9_95_to_9_98_constant_section"
                if apply_finite_length_correction
                else "long_wave_limit"
            ),
            "phase_length_m": float(phase_length_m),
            "heave_positive": "up",
            "pitch_positive": "bow_up",
            "longitudinal_point_axis": "positive_forward_from_cg",
            "wave_at_cg": "zeta_a*sin(omega_e*t)",
            **(metadata or {}),
            "target_context": planing_target_context(boat, equilibrium),
        },
    )


def _solve_index(model: LongitudinalFrequencyModel, index: int) -> tuple[np.ndarray, float, float]:
    dynamic = model.dynamic_stiffness[index]
    excitation = model.excitation_per_wave_amplitude[index]
    response = np.linalg.solve(dynamic, excitation)
    residual = dynamic @ response - excitation
    relative_residual = float(np.linalg.norm(residual) / max(np.linalg.norm(excitation), 1.0e-12))
    condition_number = float(np.linalg.cond(dynamic))
    return response, relative_residual, condition_number


def solve_longitudinal_frequency_response(model: LongitudinalFrequencyModel) -> pd.DataFrame:
    """Solve the complete two-DOF complex equation at every frequency."""

    rows: list[dict[str, Any]] = []
    for index in range(model.hydrodynamics.solver_omega_rad_s.size):
        response, residual, condition = _solve_index(model, index)
        omega_e = float(model.hydrodynamics.solver_omega_rad_s[index])
        heave = response[0]
        pitch = response[1]
        point = heave + model.point_x_forward_m * pitch
        lead_phase = wrap_phase_deg(np.angle(response / (-1j), deg=True))
        point_lead_phase = float(wrap_phase_deg(np.angle(point / (-1j), deg=True)))
        amplitude = float(model.wave_amplitude_m[index])
        rows.append(
            {
                "frequency_index": index,
                "omega0_rad_s": float(model.omega0_rad_s[index]),
                "omega_e_rad_s": omega_e,
                "wavenumber_rad_m": float(model.wavenumber_rad_m[index]),
                "wavelength_m": float(model.wavelength_m[index]),
                "wave_amplitude_m": amplitude,
                "heave_response_real_m_per_m": float(heave.real),
                "heave_response_imag_m_per_m": float(heave.imag),
                "pitch_response_real_rad_per_m": float(pitch.real),
                "pitch_response_imag_rad_per_m": float(pitch.imag),
                "heave_rao_m_per_m": float(abs(heave)),
                "pitch_rao_rad_per_m": float(abs(pitch)),
                "pitch_rao_rad_per_wave_slope": float(abs(pitch) / model.wavenumber_rad_m[index]),
                "point_vertical_rao_m_per_m": float(abs(point)),
                "heave_phase_lead_deg": float(lead_phase[0]),
                "pitch_phase_lead_deg": float(lead_phase[1]),
                "point_phase_lead_deg": point_lead_phase,
                "fridsma_heave_phase_lag_deg": float(-lead_phase[0]),
                "fridsma_pitch_phase_lead_deg": float(lead_phase[1]),
                "cg_accel_rao_mps2_per_m": float(omega_e**2 * abs(heave)),
                "point_accel_rao_mps2_per_m": float(omega_e**2 * abs(point)),
                "cg_accel_g": float(omega_e**2 * amplitude * abs(heave) / 9.80665),
                "point_accel_g": float(omega_e**2 * amplitude * abs(point) / 9.80665),
                "dynamic_condition_number": condition,
                "equation_relative_residual": residual,
                "heave_finite_length_factor": float(model.heave_finite_length_factor[index]),
                "pitch_finite_length_factor": float(model.pitch_finite_length_factor[index]),
                "provider_route": model.hydrodynamics.metadata.get("provider_route", "unknown"),
                "matrix_contract": model.hydrodynamics.metadata.get("matrix_contract", "unknown"),
            }
        )
    return pd.DataFrame(rows)


def simulate_regular_wave_ivp(
    model: LongitudinalFrequencyModel,
    frequency_index: int,
    *,
    wave_amplitude_m: float | None = None,
    cycles: int = 8,
    samples_per_cycle: int = 96,
) -> pd.DataFrame:
    """Re-solve one harmonic case in time with the exact steady-state initial condition."""

    if cycles < 2 or samples_per_cycle < 24:
        raise ValueError("cycles must be >=2 and samples_per_cycle must be >=24.")
    response_per_m, _, _ = _solve_index(model, frequency_index)
    omega = float(model.hydrodynamics.solver_omega_rad_s[frequency_index])
    amplitude = float(model.wave_amplitude_m[frequency_index]) if wave_amplitude_m is None else float(wave_amplitude_m)
    if amplitude <= 0.0:
        raise ValueError("wave_amplitude_m must be positive.")
    total_mass = model.rigid_mass + model.hydrodynamics.added_mass[frequency_index]
    damping = model.hydrodynamics.radiation_damping[frequency_index]
    restoring = model.restoring[frequency_index]
    force_hat = amplitude * model.excitation_per_wave_amplitude[frequency_index]
    response_hat = amplitude * response_per_m
    velocity_hat = 1j * omega * response_hat
    mass_inverse = np.linalg.inv(total_mass)

    def rhs(time_s: float, state: np.ndarray) -> np.ndarray:
        position = state[:2]
        velocity = state[2:]
        force = np.real(force_hat * np.exp(1j * omega * time_s))
        acceleration = mass_inverse @ (force - damping @ velocity - restoring @ position)
        return np.concatenate((velocity, acceleration))

    period = 2.0 * np.pi / omega
    duration = cycles * period
    sample_count = cycles * samples_per_cycle + 1
    time = np.linspace(0.0, duration, sample_count)
    initial = np.concatenate((np.real(response_hat), np.real(velocity_hat)))
    solution = solve_ivp(
        rhs,
        (0.0, duration),
        initial,
        t_eval=time,
        method="DOP853",
        rtol=1.0e-10,
        atol=1.0e-12,
        max_step=period / samples_per_cycle,
    )
    if not solution.success:
        raise RuntimeError(f"Regular-wave time-domain integration failed: {solution.message}")
    accelerations = np.asarray([rhs(t, state)[2:] for t, state in zip(solution.t, solution.y.T)])
    point = solution.y[0] + model.point_x_forward_m * solution.y[1]
    point_accel = accelerations[:, 0] + model.point_x_forward_m * accelerations[:, 1]
    return pd.DataFrame(
        {
            "time_s": solution.t,
            "wave_elevation_m": amplitude * np.sin(omega * solution.t),
            "heave_m": solution.y[0],
            "pitch_rad": solution.y[1],
            "heave_velocity_mps": solution.y[2],
            "pitch_rate_rad_s": solution.y[3],
            "heave_accel_mps2": accelerations[:, 0],
            "pitch_accel_rad_s2": accelerations[:, 1],
            "point_vertical_m": point,
            "point_vertical_accel_mps2": point_accel,
        }
    )


def harmonic_phasor(time_s: np.ndarray, values: np.ndarray, omega_rad_s: float) -> complex:
    """Least-squares harmonic phasor for ``Re(Q exp(i omega t))``."""

    time = np.asarray(time_s, dtype=float)
    signal = np.asarray(values, dtype=float)
    design = np.column_stack((np.cos(omega_rad_s * time), np.sin(omega_rad_s * time), np.ones_like(time)))
    coefficients = np.linalg.lstsq(design, signal, rcond=None)[0]
    return complex(coefficients[0], -coefficients[1])


def frequency_time_consistency(
    model: LongitudinalFrequencyModel,
    frequency_index: int,
    *,
    wave_amplitude_m: float | None = None,
) -> dict[str, float]:
    response_per_m, _, _ = _solve_index(model, frequency_index)
    amplitude = float(model.wave_amplitude_m[frequency_index]) if wave_amplitude_m is None else float(wave_amplitude_m)
    timeseries = simulate_regular_wave_ivp(model, frequency_index, wave_amplitude_m=amplitude)
    omega = float(model.hydrodynamics.solver_omega_rad_s[frequency_index])
    heave_time = harmonic_phasor(timeseries["time_s"], timeseries["heave_m"], omega) / amplitude
    pitch_time = harmonic_phasor(timeseries["time_s"], timeseries["pitch_rad"], omega) / amplitude
    expected = response_per_m
    amplitude_errors = np.abs(np.abs(np.asarray([heave_time, pitch_time])) - np.abs(expected)) / np.maximum(
        np.abs(expected), 1.0e-12
    )
    phase_errors = np.abs(
        circular_difference_deg(
            np.angle(np.asarray([heave_time, pitch_time]), deg=True),
            np.angle(expected, deg=True),
        )
    )
    kinematic = timeseries["heave_accel_mps2"].to_numpy() + model.point_x_forward_m * timeseries[
        "pitch_accel_rad_s2"
    ].to_numpy()
    kinematic_residual = float(
        np.linalg.norm(kinematic - timeseries["point_vertical_accel_mps2"].to_numpy())
        / max(np.linalg.norm(kinematic), 1.0e-12)
    )
    return {
        "heave_amplitude_relative_error": float(amplitude_errors[0]),
        "pitch_amplitude_relative_error": float(amplitude_errors[1]),
        "heave_phase_circular_error_deg": float(phase_errors[0]),
        "pitch_phase_circular_error_deg": float(phase_errors[1]),
        "point_acceleration_kinematic_relative_residual": kinematic_residual,
    }


def wave_amplitude_linearity(
    model: LongitudinalFrequencyModel,
    frequency_index: int,
    base_wave_amplitude_m: float,
) -> dict[str, float]:
    phasors: list[np.ndarray] = []
    for amplitude in (base_wave_amplitude_m, 2.0 * base_wave_amplitude_m):
        series = simulate_regular_wave_ivp(model, frequency_index, wave_amplitude_m=amplitude)
        omega = float(model.hydrodynamics.solver_omega_rad_s[frequency_index])
        phasors.append(
            np.asarray(
                [
                    harmonic_phasor(series["time_s"], series["heave_m"], omega),
                    harmonic_phasor(series["time_s"], series["pitch_rad"], omega),
                    harmonic_phasor(series["time_s"], series["point_vertical_accel_mps2"], omega),
                ],
                dtype=complex,
            )
        )
    ratio = np.abs(phasors[1]) / np.maximum(np.abs(phasors[0]), 1.0e-12)
    return {
        "heave_amplitude_ratio": float(ratio[0]),
        "pitch_amplitude_ratio": float(ratio[1]),
        "point_acceleration_amplitude_ratio": float(ratio[2]),
    }
