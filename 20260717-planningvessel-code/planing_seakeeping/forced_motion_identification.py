from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np


MotionDof = Literal["heave", "pitch"]


@dataclass(frozen=True)
class FirstHarmonicFit:
    mean: np.ndarray
    sine: np.ndarray
    cosine: np.ndarray
    residual_nrmse: np.ndarray
    retained_sample_count: int
    retained_cycle_count: float


@dataclass(frozen=True)
class ForcedMotionColumn:
    motion_dof: MotionDof
    omega_rad_s: float
    motion_amplitude: float
    added_mass_column: np.ndarray
    damping_column: np.ndarray
    harmonic_fit: FirstHarmonicFit
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ForcedMotionMatrices:
    omega_rad_s: float
    added_mass: np.ndarray
    damping: np.ndarray
    columns: tuple[ForcedMotionColumn, ForcedMotionColumn]
    metadata: dict[str, Any]


def fit_periodic_harmonics(
    time_s: np.ndarray,
    values: np.ndarray,
    omega_rad_s: float,
    *,
    discard_cycles: float = 1.0,
    retained_cycles: float | None = None,
    fitted_harmonics: int = 3,
) -> FirstHarmonicFit:
    """Fit Eq. (7.46) and return its first sine/cosine coefficients.

    The convention is ``f=b0+sum(a_n*sin(n*omega*t)+b_n*cos(n*omega*t))``.
    Higher harmonics are fitted so that nonlinear content does not leak into
    the first harmonic used for the linear hydrodynamic coefficients.
    """

    time = np.asarray(time_s, dtype=float)
    signal = np.asarray(values, dtype=float)
    if time.ndim != 1 or len(time) < 16 or np.any(np.diff(time) <= 0.0):
        raise ValueError("time_s must be strictly increasing with at least 16 samples.")
    if signal.shape[0] != len(time) or signal.ndim not in (1, 2):
        raise ValueError("values must have shape (sample,) or (sample, channel).")
    if not np.isfinite(time).all() or not np.isfinite(signal).all():
        raise ValueError("time_s and values must be finite.")
    if omega_rad_s <= 0.0 or discard_cycles < 0.0:
        raise ValueError("omega_rad_s must be positive and discard_cycles non-negative.")
    if retained_cycles is not None and retained_cycles <= 0.0:
        raise ValueError("retained_cycles must be positive when supplied.")
    if fitted_harmonics < 1:
        raise ValueError("fitted_harmonics must be at least one.")

    period = 2.0 * np.pi / float(omega_rad_s)
    start = float(time[0]) + discard_cycles * period
    end = float(time[-1])
    if retained_cycles is not None:
        end = min(end, start + retained_cycles * period)
    mask = (time >= start) & (time <= end)
    retained_time = time[mask]
    retained_values = signal[mask]
    cycle_count = (
        float(retained_time[-1] - retained_time[0]) / period if len(retained_time) >= 2 else 0.0
    )
    sampling_cycle_tolerance = 2.0 * float(np.max(np.diff(time))) / period + 1e-12
    if (
        len(retained_time) < max(16, 4 * fitted_harmonics + 1)
        or cycle_count + sampling_cycle_tolerance < 1.5
    ):
        raise ValueError("At least 1.5 retained cycles and sufficient samples are required.")

    columns = [np.ones_like(retained_time)]
    for harmonic in range(1, fitted_harmonics + 1):
        columns.extend(
            (
                np.sin(harmonic * omega_rad_s * retained_time),
                np.cos(harmonic * omega_rad_s * retained_time),
            )
        )
    design = np.column_stack(columns)
    coefficients, _, _, _ = np.linalg.lstsq(design, retained_values, rcond=None)
    fitted = design @ coefficients
    residual = retained_values - fitted
    if retained_values.ndim == 1:
        scale = max(float(np.ptp(retained_values)), np.finfo(float).eps)
        residual_nrmse = np.asarray([np.sqrt(np.mean(residual**2)) / scale])
        mean = np.asarray([coefficients[0]])
        sine = np.asarray([coefficients[1]])
        cosine = np.asarray([coefficients[2]])
    else:
        scale = np.maximum(np.ptp(retained_values, axis=0), np.finfo(float).eps)
        residual_nrmse = np.sqrt(np.mean(residual**2, axis=0)) / scale
        mean = coefficients[0]
        sine = coefficients[1]
        cosine = coefficients[2]
    return FirstHarmonicFit(
        mean=np.asarray(mean, dtype=float),
        sine=np.asarray(sine, dtype=float),
        cosine=np.asarray(cosine, dtype=float),
        residual_nrmse=np.asarray(residual_nrmse, dtype=float),
        retained_sample_count=int(len(retained_time)),
        retained_cycle_count=cycle_count,
    )


def extract_forced_motion_column(
    time_s: np.ndarray,
    generalized_load: np.ndarray,
    *,
    motion_dof: MotionDof,
    omega_rad_s: float,
    motion_amplitude: float,
    restoring_column: np.ndarray,
    discard_cycles: float = 1.0,
    retained_cycles: float | None = None,
    fitted_harmonics: int = 3,
) -> ForcedMotionColumn:
    """Extract one column of ``A`` and ``B`` using Sun (2007), Eqs. 7.46-7.47.

    Forced motion follows ``eta_j=-eta_ja*sin(omega*t)``.  The two load
    channels are vertical force and bow-up pitch moment in that order.
    """

    if motion_dof not in ("heave", "pitch"):
        raise ValueError("motion_dof must be heave or pitch.")
    if motion_amplitude <= 0.0:
        raise ValueError("motion_amplitude must be positive.")
    restoring = np.asarray(restoring_column, dtype=float)
    if restoring.shape != (2,) or not np.isfinite(restoring).all():
        raise ValueError("restoring_column must be a finite two-component vector.")
    loads = np.asarray(generalized_load, dtype=float)
    if loads.ndim != 2 or loads.shape[1] != 2:
        raise ValueError("generalized_load must have columns [vertical force, pitch moment].")
    fit = fit_periodic_harmonics(
        time_s,
        loads,
        omega_rad_s,
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=fitted_harmonics,
    )
    amplitude = float(motion_amplitude)
    omega = float(omega_rad_s)
    added = -(fit.sine - restoring * amplitude) / (omega**2 * amplitude)
    damping = fit.cosine / (omega * amplitude)
    return ForcedMotionColumn(
        motion_dof=motion_dof,
        omega_rad_s=omega,
        motion_amplitude=amplitude,
        added_mass_column=added,
        damping_column=damping,
        harmonic_fit=fit,
        metadata={
            "source": "Sun_2007_Eq7.46_to_7.47",
            "forced_motion_convention": "eta_j=-eta_ja*sin(omega*t)",
            "load_order": "vertical_force_bow_up_pitch_moment",
            "response_calibration_used": False,
        },
    )


def assemble_forced_motion_matrices(
    heave_column: ForcedMotionColumn,
    pitch_column: ForcedMotionColumn,
) -> ForcedMotionMatrices:
    """Assemble the two forced-motion columns into the Gate 2 matrix order."""

    if heave_column.motion_dof != "heave" or pitch_column.motion_dof != "pitch":
        raise ValueError("Columns must be supplied in forced-heave and forced-pitch order.")
    if not np.isclose(heave_column.omega_rad_s, pitch_column.omega_rad_s, rtol=1e-12):
        raise ValueError("Forced-heave and forced-pitch columns must use the same frequency.")
    added = np.column_stack(
        (heave_column.added_mass_column, pitch_column.added_mass_column)
    )
    damping = np.column_stack((heave_column.damping_column, pitch_column.damping_column))
    return ForcedMotionMatrices(
        omega_rad_s=heave_column.omega_rad_s,
        added_mass=added,
        damping=damping,
        columns=(heave_column, pitch_column),
        metadata={
            "matrix_order": "rows=[heave_force,pitch_moment]; columns=[heave,pitch]",
            "coordinate_convention": "heave_up_pitch_bow_up",
            "source": "Sun_2007_Eq7.46_to_7.47",
            "response_calibration_used": False,
        },
    )
