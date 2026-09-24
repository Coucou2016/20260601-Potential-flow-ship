from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
import hashlib
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .config import BoatConfig
from .quadrature import clipped_piecewise_linear_integral
from .equilibrium import EquilibriumState, compute_geometry
from .longitudinal_response import LongitudinalFrequencyModel, faltinsen_head_sea_excitation
from .kernels.linear_2p5d import solve_station_hull_head_sea_excitation_matched_sweep
from .providers.linear_hydrodynamics import LinearFrequencyProvider
from .schema import Linear2p5DProviderConfig
from .section_bem import hard_chine_v_offsets, solve_wave_excitation
from .station_2p5d import (
    HardChineStation,
    RigidBody6DOF,
    StationHull,
    assemble_experimental_bem_6dof_matrices,
)
from .types import LongitudinalHydrodynamicMatrices


@dataclass(frozen=True)
class PlaningFrequencyCorrection:
    sample_omega_rad_s: np.ndarray
    high_frequency_reference_rad_s: float
    delta_added_mass: np.ndarray
    delta_radiation_damping: np.ndarray
    raw_added_mass: np.ndarray
    raw_radiation_damping: np.ndarray
    metadata: dict[str, Any]
    raw_restoring: np.ndarray | None = None
    excitation_per_wave_amplitude: np.ndarray | None = None
    excitation_components: dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        omega = np.asarray(self.sample_omega_rad_s, dtype=float)
        if omega.ndim != 1 or len(omega) < 3 or np.any(np.diff(omega) <= 0.0):
            raise ValueError("sample_omega_rad_s must be strictly increasing with at least three points.")
        for name in (
            "delta_added_mass",
            "delta_radiation_damping",
            "raw_added_mass",
            "raw_radiation_damping",
        ):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (len(omega), 2, 2) or not np.isfinite(value).all():
                raise ValueError(f"{name} must be finite with shape ({len(omega)}, 2, 2).")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "sample_omega_rad_s", omega)
        restoring = self.raw_restoring
        if restoring is not None:
            restoring_array = np.asarray(restoring, dtype=float)
            if restoring_array.shape == (2, 2):
                restoring_array = np.repeat(
                    restoring_array[None, :, :], len(omega), axis=0
                )
            if restoring_array.shape != (len(omega), 2, 2):
                raise ValueError(
                    "raw_restoring must have shape (2, 2) or "
                    f"({len(omega)}, 2, 2)."
                )
            if not np.isfinite(restoring_array).all():
                raise ValueError("raw_restoring must contain only finite values.")
            object.__setattr__(self, "raw_restoring", restoring_array)
        excitation = self.excitation_per_wave_amplitude
        if excitation is not None:
            excitation_array = np.asarray(excitation, dtype=complex)
            if excitation_array.shape != (len(omega), 2):
                raise ValueError(
                    "excitation_per_wave_amplitude must have shape "
                    f"({len(omega)}, 2)."
                )
            if not np.isfinite(excitation_array.real).all() or not np.isfinite(
                excitation_array.imag
            ).all():
                raise ValueError("excitation_per_wave_amplitude must be finite.")
            if np.any(np.linalg.norm(excitation_array, axis=1) <= 1.0e-12):
                raise ValueError("excitation_per_wave_amplitude must be non-zero.")
            object.__setattr__(self, "excitation_per_wave_amplitude", excitation_array)
        components: dict[str, np.ndarray] = {}
        for name, values in self.excitation_components.items():
            component = np.asarray(values, dtype=complex)
            if component.shape != (len(omega), 2):
                raise ValueError(
                    f"Excitation component {name!r} must have shape ({len(omega)}, 2)."
                )
            if not np.isfinite(component.real).all() or not np.isfinite(component.imag).all():
                raise ValueError(f"Excitation component {name!r} must be finite.")
            components[str(name)] = component
        object.__setattr__(self, "excitation_components", components)
        object.__setattr__(self, "metadata", dict(self.metadata))


_FORCED_MOTION_MATRIX_INDEX = {
    "A33": ("added", 0, 0),
    "A35": ("added", 0, 1),
    "A53": ("added", 1, 0),
    "A55": ("added", 1, 1),
    "B33": ("damping", 0, 0),
    "B35": ("damping", 0, 1),
    "B53": ("damping", 1, 0),
    "B55": ("damping", 1, 1),
}

_FORCED_MOTION_TARGET_CONTEXT_COLUMNS = (
    "target_identifier",
    "beam_m",
    "deadrise_deg",
    "trim_deg",
    "fn_b",
    "mean_wetted_length_over_b",
    "lcg_from_transom_m",
    "rho_water_kg_m3",
    "gravity_m_s2",
    "matrix_coordinate_contract",
)


def _csv_boolean(value: object) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"false", "0", "no"}:
        return False
    if normalized in {"true", "1", "yes"}:
        return True
    raise ValueError(f"CSV boolean value is not recognized: {value!r}.")


def load_nonlinear_2dt_forced_motion_correction(
    path: str | Path | Sequence[str | Path],
    *,
    restoring_matrices_path: str | Path | None = None,
    component: str = "total",
    maximum_harmonic_fit_residual: float = 0.05,
    require_physical_restoring_subtraction: bool = True,
    require_target_context: bool = False,
) -> PlaningFrequencyCorrection:
    """Load an accepted Sun-style forced-motion matrix without response fitting.

    The CSV contract is the output of ``probe_sun2007_planing_forced_motion``:
    one dimensional value for each of A33, A35, A53, A55, B33, B35, B53,
    and B55 at every frequency.  Rows from zero-restoring diagnostics are
    intentionally rejected by default because their added masses are not
    physical production coefficients.
    """

    source_paths = (
        [Path(path).resolve()]
        if isinstance(path, (str, Path))
        else [Path(item).resolve() for item in path]
    )
    if not source_paths:
        raise ValueError("At least one forced-motion CSV path is required.")
    for source in source_paths:
        if not source.is_file():
            raise FileNotFoundError(source)
    if not math.isfinite(maximum_harmonic_fit_residual) or not (
        0.0 < maximum_harmonic_fit_residual <= 1.0
    ):
        raise ValueError("maximum_harmonic_fit_residual must lie in (0, 1].")
    rows: list[dict[str, str]] = []
    for source in source_paths:
        with open(str(source), "r", encoding="utf-8", newline="") as stream:
            rows.extend(
                row
                for row in csv.DictReader(stream)
                if str(row.get("component", "")).strip() == str(component)
            )
    if not rows:
        raise ValueError(f"No forced-motion rows found for component {component!r}.")

    required_columns = {
        "omega_rad_s",
        "coefficient",
        "value_dimensional",
        "harmonic_fit_residual_nrmse",
        "restoring_subtraction",
        "response_calibration_used",
    }
    for row_index, row in enumerate(rows):
        missing_columns = sorted(required_columns - set(row))
        if missing_columns:
            raise ValueError(
                f"Forced-motion CSV row {row_index} is missing columns: {missing_columns}."
            )
    if any(_csv_boolean(row["response_calibration_used"]) for row in rows):
        raise ValueError("Response-calibrated forced-motion coefficients are not admissible.")
    if "restoring_matrix_is_zero" in rows[0] and any(
        _csv_boolean(row["restoring_matrix_is_zero"]) for row in rows
    ):
        raise ValueError("Physical matrix loading rejects a zero restoring matrix.")

    restoring_labels = {str(row["restoring_subtraction"]).strip() for row in rows}
    if len(restoring_labels) != 1:
        raise ValueError("Every selected forced-motion row must use one restoring subtraction.")
    restoring_label = next(iter(restoring_labels))
    if require_physical_restoring_subtraction and (
        not restoring_label or "zero" in restoring_label.lower()
    ):
        raise ValueError(
            "Physical matrix loading rejects zero-restoring diagnostics; "
            "re-identify the same time series with a traceable restoring matrix."
        )
    restoring_hash = None
    if all("restoring_matrices_sha256" in row for row in rows):
        restoring_hashes = {
            str(row["restoring_matrices_sha256"]).strip() for row in rows
        }
        if len(restoring_hashes) != 1 or not next(iter(restoring_hashes)):
            raise ValueError(
                "Merged forced-motion columns must reference one restoring-matrix SHA-256."
            )
        restoring_hash = next(iter(restoring_hashes))

    target_context: dict[str, str | float] = {}
    for column in _FORCED_MOTION_TARGET_CONTEXT_COLUMNS:
        present = [column in row and str(row[column]).strip() != "" for row in rows]
        if require_target_context and not all(present):
            raise ValueError(f"Physical forced-motion matrix is missing target context: {column}.")
        if any(present) and not all(present):
            raise ValueError(f"Target-context column {column} is only partially populated.")
        if not all(present):
            continue
        values = {str(row[column]).strip() for row in rows}
        if len(values) != 1:
            raise ValueError(f"Merged forced-motion rows disagree on target context: {column}.")
        value = next(iter(values))
        if column in {"target_identifier", "matrix_coordinate_contract"}:
            target_context[column] = value
        else:
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"Target-context value {column} must be finite.")
            target_context[column] = numeric
    expected_contract = "heave_up_pitch_bow_up_force_and_moment_about_cg"
    if (
        "matrix_coordinate_contract" in target_context
        and target_context["matrix_coordinate_contract"] != expected_contract
    ):
        raise ValueError(
            "Forced-motion matrix coordinate contract must be "
            f"{expected_contract!r}."
        )

    frequencies = sorted({float(row["omega_rad_s"]) for row in rows})
    if len(frequencies) < 3 or any(
        not math.isfinite(value) or value <= 0.0 for value in frequencies
    ):
        raise ValueError("Forced-motion matrix loading needs at least three positive frequencies.")
    added = np.full((len(frequencies), 2, 2), np.nan, dtype=float)
    damping = np.full_like(added, np.nan)
    frequency_index = {value: index for index, value in enumerate(frequencies)}
    seen: set[tuple[float, str]] = set()
    maximum_residual = 0.0
    for row in rows:
        coefficient = str(row["coefficient"]).strip()
        if coefficient not in _FORCED_MOTION_MATRIX_INDEX:
            continue
        omega = float(row["omega_rad_s"])
        key = (omega, coefficient)
        if key in seen:
            raise ValueError(f"Duplicate forced-motion coefficient row: omega={omega}, {coefficient}.")
        seen.add(key)
        value = float(row["value_dimensional"])
        residual = float(row["harmonic_fit_residual_nrmse"])
        if not math.isfinite(value) or not math.isfinite(residual) or residual < 0.0:
            raise ValueError(f"Non-finite forced-motion value or residual at {key}.")
        if residual > maximum_harmonic_fit_residual:
            raise ValueError(
                f"Forced-motion harmonic residual {residual:.6g} exceeds "
                f"{maximum_harmonic_fit_residual:.6g} at {key}."
            )
        maximum_residual = max(maximum_residual, residual)
        matrix_name, matrix_row, matrix_column = _FORCED_MOTION_MATRIX_INDEX[coefficient]
        target = added if matrix_name == "added" else damping
        target[frequency_index[omega], matrix_row, matrix_column] = value
    expected = {
        (omega, coefficient)
        for omega in frequencies
        for coefficient in _FORCED_MOTION_MATRIX_INDEX
    }
    missing_rows = sorted(expected - seen)
    if missing_rows:
        preview = ", ".join(f"({omega:g}, {name})" for omega, name in missing_rows[:8])
        raise ValueError(f"Forced-motion matrix is incomplete; missing {preview}.")
    if not np.isfinite(added).all() or not np.isfinite(damping).all():
        raise ValueError("Forced-motion matrices must be finite and complete.")

    source_hashes: dict[str, str] = {}
    for source in source_paths:
        with open(str(source), "rb") as stream:
            source_hashes[str(source)] = hashlib.sha256(stream.read()).hexdigest()
    sample_omega = np.asarray(frequencies, dtype=float)
    raw_restoring = None
    restoring_source_path = None
    restoring_source_hash = None
    if restoring_matrices_path is not None:
        restoring_source_path = Path(restoring_matrices_path).resolve()
        if not restoring_source_path.is_file():
            raise FileNotFoundError(restoring_source_path)
        row_index = {"heave_force": 0, "pitch_moment": 1}
        column_index = {"heave": 0, "pitch": 1}
        restoring_values = np.full((2, 2), np.nan, dtype=float)
        with restoring_source_path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            restoring_rows = [
                row
                for row in csv.DictReader(stream)
                if str(row.get("component", "")).strip() == str(component)
            ]
        for row in restoring_rows:
            row_name = str(row.get("row", "")).strip()
            column_name = str(row.get("column", "")).strip()
            if row_name not in row_index or column_name not in column_index:
                continue
            restoring_values[row_index[row_name], column_index[column_name]] = float(
                row["value"]
            )
        if not np.isfinite(restoring_values).all():
            raise ValueError(
                "The forced-motion restoring CSV must contain one complete total 2x2 matrix."
            )
        raw_restoring = np.repeat(
            restoring_values[None, :, :], len(sample_omega), axis=0
        )
        with restoring_source_path.open("rb") as stream:
            restoring_source_hash = hashlib.sha256(stream.read()).hexdigest()
    return PlaningFrequencyCorrection(
        sample_omega_rad_s=sample_omega,
        high_frequency_reference_rad_s=float(sample_omega[-1]),
        delta_added_mass=added - added[-1][None, :, :],
        delta_radiation_damping=damping - damping[-1][None, :, :],
        raw_added_mass=added,
        raw_radiation_damping=damping,
        raw_restoring=raw_restoring,
        metadata={
            "source": "sun_nonlinear_2dt_forced_motion_precalculation",
            "source_csv": (
                str(source_paths[0])
                if len(source_paths) == 1
                else [str(source) for source in source_paths]
            ),
            "source_csv_sha256": (
                source_hashes[str(source_paths[0])]
                if len(source_paths) == 1
                else source_hashes
            ),
            "selected_component": str(component),
            "restoring_subtraction": restoring_label,
            "restoring_matrices_sha256": restoring_hash,
            "restoring_matrices_csv": (
                str(restoring_source_path) if restoring_source_path is not None else None
            ),
            "restoring_matrices_csv_sha256": restoring_source_hash,
            "target_context": target_context,
            "target_context_required": bool(require_target_context),
            "maximum_harmonic_fit_residual_nrmse": float(maximum_residual),
            "matrix_contract": expected_contract,
            "application_contract": "replace_with_matched_bie",
            "complete_matrix_contract": (
                "replace_A_B_C_together"
                if raw_restoring is not None
                else "replace_A_B_only"
            ),
            "response_calibration_used": False,
        },
    )


def matched_bie_matrix_to_bow_up(matrix: np.ndarray) -> np.ndarray:
    """Map matched-BIE heave/pitch matrices to the Gate 2 bow-up convention.

    The station kernel uses longitudinal position positive aft from the center
    of gravity, whereas the longitudinal response contract uses pitch positive
    bow up.  Generalized coordinates and forces therefore transform with
    ``T = diag(1, -1)``, giving ``K_bow_up = T K_kernel T``.
    """

    values = np.asarray(matrix)
    if values.shape[-2:] != (2, 2):
        raise ValueError("Matched-BIE heave/pitch matrices must end with shape (2, 2).")
    transform = np.diag([1.0, -1.0])
    return np.einsum("ij,...jk,kl->...il", transform, values, transform)


def matched_bie_excitation_to_bow_up(excitation: np.ndarray) -> np.ndarray:
    """Map matched-BIE generalized force vectors to heave-up/pitch-bow-up."""

    values = np.asarray(excitation, dtype=complex)
    if values.shape[-1:] != (2,):
        raise ValueError("Matched-BIE excitation vectors must end with shape (2,).")
    transform = np.diag([1.0, -1.0])
    return np.einsum("ij,...j->...i", transform, values)


def _transom_recovery_weight(
    x_from_transom_m: np.ndarray,
    recovery_length_m: float,
    recovery_profile: str,
) -> np.ndarray:
    """Return a dry-transom load recovery with no response-derived parameter.

    The square-root profile represents the local potential-flow asymptotic
    ``dp/dx=O(x**-1/2)`` at a ventilated transom edge, hence
    ``p-p_atm=O(sqrt(x))``.  The recovery length remains an independently
    specified physical input.
    """

    x = np.asarray(x_from_transom_m, dtype=float)
    length = float(recovery_length_m)
    profile = str(recovery_profile).strip().lower()
    if not math.isfinite(length) or length <= 0.0:
        raise ValueError("recovery_length_m must be finite and positive.")
    if profile == "hard_zero":
        return (x > length).astype(float)
    normalized = np.clip(x / length, 0.0, 1.0)
    if profile == "linear_ramp":
        return normalized
    if profile == "square_root_ramp":
        return np.sqrt(normalized)
    raise ValueError(
        "recovery_profile must be hard_zero, linear_ramp, or square_root_ramp."
    )


def apply_transom_sectional_force_cutoff(
    *,
    station_x_m: np.ndarray,
    force_density_by_station: np.ndarray,
    end_force_matrices: np.ndarray,
    end_station_x_m: np.ndarray,
    cutoff_length_m: float,
    recovery_profile: str = "hard_zero",
    cutoff_quadrature: str = "nodal_mask",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, float]]:
    """Apply the Sun--Faltinsen dry-transom sectional-force correction.

    ``hard_zero`` reproduces the coarse correction used by Sun and Faltinsen:
    the sectional force is zero from the transom to ``cutoff_length_m``.
    ``linear_ramp`` enforces zero transom pressure and continuously recovers
    the two-dimensional force over the same source-fixed length.
    ``square_root_ramp`` additionally satisfies the local dry-transom
    square-root pressure-gradient asymptotic.  The cutoff is a physical model
    input and must not be inferred from a motion response.
    """

    x_rows = np.asarray(station_x_m, dtype=float)
    density = np.asarray(force_density_by_station, dtype=complex)
    end_force = np.asarray(end_force_matrices, dtype=complex)
    end_x = np.asarray(end_station_x_m, dtype=float)
    cutoff = float(cutoff_length_m)
    profile = str(recovery_profile).strip().lower()
    if cutoff_quadrature not in {"nodal_mask", "clipped_linear"}:
        raise ValueError("Unknown cutoff quadrature")
    if cutoff_quadrature == "clipped_linear" and profile != "hard_zero":
        raise ValueError("clipped_linear requires hard_zero recovery")
    if x_rows.ndim != 2 or density.shape != (*x_rows.shape, 2, 2):
        raise ValueError(
            "station_x_m and force_density_by_station must have shapes "
            "(n_frequency,n_station) and (n_frequency,n_station,2,2)."
        )
    if end_force.shape != (x_rows.shape[0], 2, 2) or end_x.shape != (x_rows.shape[0],):
        raise ValueError("End-force matrices and coordinates must match the frequency grid.")
    if not math.isfinite(cutoff) or cutoff <= 0.0:
        raise ValueError("cutoff_length_m must be finite and positive.")
    if profile not in {"hard_zero", "linear_ramp", "square_root_ramp"}:
        raise ValueError(
            "recovery_profile must be hard_zero, linear_ramp, or square_root_ramp."
        )
    if not np.isfinite(x_rows).all() or any(np.any(np.diff(row) <= 0.0) for row in x_rows):
        raise ValueError("Every station-coordinate row must be finite and strictly increasing.")
    if cutoff >= float(np.min(x_rows[:, -1])):
        raise ValueError("The transom cutoff must leave a non-empty forward loaded region.")

    retained = x_rows > cutoff
    recovery_weight = _transom_recovery_weight(x_rows, cutoff, profile)
    corrected_density = density * recovery_weight[:, :, None, None]
    corrected_end = end_force.copy()
    finite_end = np.isfinite(end_x)
    end_weight = np.ones_like(end_x)
    end_weight[finite_end] = _transom_recovery_weight(end_x[finite_end], cutoff, profile)
    corrected_end *= end_weight[:, None, None]
    station_dx = np.diff(x_rows, axis=1)
    corrected_total = np.sum(
        0.5
        * (corrected_density[:, 1:] + corrected_density[:, :-1])
        * station_dx[:, :, None, None],
        axis=1,
    ) + corrected_end
    if cutoff_quadrature == "clipped_linear":
        corrected_total = np.asarray([
            clipped_piecewise_linear_integral(x, values, cutoff)
            for x, values in zip(x_rows, density, strict=True)
        ]) + corrected_end
    if not np.isfinite(corrected_total.real).all() or not np.isfinite(
        corrected_total.imag
    ).all():
        raise RuntimeError("Transom-corrected sectional-force integration is non-finite.")
    retained_span = np.maximum(x_rows[:, -1] - cutoff, 0.0)
    total_span = x_rows[:, -1] - x_rows[:, 0]
    diagnostics = {
        "transom_force_cutoff_length_m": cutoff,
        "minimum_retained_station_count": float(np.min(np.sum(retained, axis=1))),
        "mean_retained_longitudinal_fraction": float(
            np.mean(retained_span / np.maximum(total_span, 1.0e-30))
        ),
        "end_force_zeroed_fraction": float(
            np.mean(finite_end & (end_x <= cutoff)) if profile == "hard_zero" else 0.0
        ),
        "minimum_recovery_weight": float(np.min(recovery_weight)),
        "mean_recovery_weight": float(np.mean(recovery_weight)),
    }
    return corrected_density, corrected_end, corrected_total, diagnostics


def assemble_section_bem_head_sea_excitation(
    *,
    hull: StationHull,
    encounter_omega_rad_s: np.ndarray,
    speed_mps: float,
    gravity_m_s2: float,
    rho_water_kg_m3: float,
    body_panel_count: int,
    free_surface_panel_count_per_side: int,
    transom_recovery_length_m: float = 0.0,
    transom_recovery_profile: str = "hard_zero",
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float]]:
    """Integrate direct 2D incident-plus-diffraction section pressures.

    The compact section BEM is solved at the absolute deep-water wave
    frequency, while forward speed enters the encounter-frequency inversion
    and longitudinal station phase.  This is an explicit diagnostic bridge to
    a direct diffraction calculation; it is not the still-missing matched-
    domain Ma-style diffraction march.
    """

    omega_e = np.asarray(encounter_omega_rad_s, dtype=float)
    wavenumber, omega_0 = head_sea_wavenumber_from_encounter_frequency(
        omega_e,
        speed_mps,
        gravity_m_s2,
    )
    station_x = np.asarray([station.x_m for station in hull.stations], dtype=float)
    if len(station_x) < 3 or np.any(np.diff(station_x) <= 0.0):
        raise ValueError("The section-BEM excitation requires at least three ordered stations.")
    if transom_recovery_length_m > 0.0:
        recovery_weight = _transom_recovery_weight(
            station_x,
            transom_recovery_length_m,
            transom_recovery_profile,
        )
    else:
        recovery_weight = np.ones_like(station_x)

    excitation = np.empty((len(omega_e), 2), dtype=complex)
    vertical_density = np.empty((len(omega_e), len(station_x)), dtype=complex)
    maximum_condition = 0.0
    maximum_residual = 0.0
    x_forward = station_x - float(hull.lcg_m)
    for frequency_index, (wave_number, wave_frequency) in enumerate(
        zip(wavenumber, omega_0)
    ):
        for station_index, station in enumerate(hull.stations):
            offsets = station.section_offsets()
            if offsets is None:
                offsets = hard_chine_v_offsets(
                    max(station.waterplane_beam_m(), 1.0e-8),
                    max(station.effective_draft_m(), 1.0e-8),
                )
            result = solve_wave_excitation(
                offsets,
                omega_rad_s=float(wave_frequency),
                wave_amplitude_m=1.0,
                wavenumber_rad_m=float(wave_number),
                transverse_wavenumber_rad_m=0.0,
                rho_water_kg_m3=float(rho_water_kg_m3),
                gravity_m_s2=float(gravity_m_s2),
                free_surface_panel_count_per_side=int(free_surface_panel_count_per_side),
                body_panel_count=int(body_panel_count),
            )
            vertical_density[frequency_index, station_index] = (
                result.complex_vertical_force_per_m * recovery_weight[station_index]
            )
            maximum_condition = max(maximum_condition, float(result.condition_number))
            maximum_residual = max(maximum_residual, float(result.residual_norm))
        phase = np.exp(1j * float(wave_number) * x_forward)
        phased_density = vertical_density[frequency_index] * phase
        excitation[frequency_index, 0] = np.trapezoid(phased_density, station_x)
        excitation[frequency_index, 1] = np.trapezoid(
            phased_density * x_forward,
            station_x,
        )
    if not np.isfinite(excitation.real).all() or not np.isfinite(excitation.imag).all():
        raise RuntimeError("Section-BEM head-sea excitation contains non-finite values.")
    return (
        excitation,
        {"section_bem_incident_plus_diffraction": excitation.copy()},
        {
            "section_bem_excitation_maximum_condition_number": maximum_condition,
            "section_bem_excitation_maximum_relative_residual": maximum_residual,
            "section_bem_excitation_mean_recovery_weight": float(np.mean(recovery_weight)),
        },
    )


def assemble_matched_domain_head_sea_excitation(
    *,
    hull: StationHull,
    encounter_omega_rad_s: np.ndarray,
    speed_mps: float,
    gravity_m_s2: float,
    rho_water_kg_m3: float,
    config: Linear2p5DProviderConfig,
    parametric_section_shape: str = "hard_chine_v",
    matched_sweep_options: dict[str, object] | None = None,
    transom_recovery_length_m: float = 0.0,
    transom_recovery_profile: str = "hard_zero",
    cutoff_quadrature: str = "nodal_mask",
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float]]:
    """Integrate A1 matched-domain Froude--Krylov plus diffraction loads."""

    omega_e = np.asarray(encounter_omega_rad_s, dtype=float)
    if omega_e.ndim != 1 or len(omega_e) < 1 or np.any(omega_e <= 0.0):
        raise ValueError("encounter_omega_rad_s must be a positive one-dimensional array.")
    recovery_length = float(transom_recovery_length_m)
    recovery_profile = str(transom_recovery_profile).strip().lower()
    if cutoff_quadrature not in {"nodal_mask", "clipped_linear"}:
        raise ValueError("Unknown cutoff quadrature")
    if cutoff_quadrature == "clipped_linear" and recovery_profile != "hard_zero":
        raise ValueError("clipped_linear requires hard_zero recovery")
    if not math.isfinite(recovery_length) or recovery_length < 0.0:
        raise ValueError("transom_recovery_length_m must be finite and non-negative.")
    if recovery_profile not in {"hard_zero", "linear_ramp", "square_root_ramp"}:
        raise ValueError(
            "transom_recovery_profile must be hard_zero, linear_ramp, or square_root_ramp."
        )

    froude_krylov_kernel: list[np.ndarray] = []
    diffraction_kernel: list[np.ndarray] = []
    total_kernel: list[np.ndarray] = []
    condition_numbers: list[float] = []
    system_residuals: list[float] = []
    body_condition_residuals: list[float] = []
    pressure_identity_residuals: list[float] = []
    force_integration_residuals: list[float] = []
    recovery_means: list[float] = []
    for frequency in omega_e:
        result = solve_station_hull_head_sea_excitation_matched_sweep(
            hull,
            float(frequency),
            speed_mps,
            config=config,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            parametric_section_shape=parametric_section_shape,
            matched_sweep_options=matched_sweep_options,
        )
        station_x = np.asarray(result.x_m, dtype=float)
        if recovery_length <= 0.0:
            recovery_weight = np.ones_like(station_x)
        else:
            recovery_weight = _transom_recovery_weight(
                station_x,
                recovery_length,
                recovery_profile,
            )
        fk_density = (
            np.asarray(result.froude_krylov_force_density_by_station, dtype=complex)
            * recovery_weight[:, None]
        )
        diffraction_density = (
            np.asarray(result.diffraction_force_density_by_station, dtype=complex)
            * recovery_weight[:, None]
        )
        fk_force = np.asarray(np.trapezoid(fk_density, station_x, axis=0), dtype=complex)
        diffraction_force = np.asarray(
            np.trapezoid(diffraction_density, station_x, axis=0),
            dtype=complex,
        )
        if cutoff_quadrature == "clipped_linear" and recovery_length > 0:
            fk_force = clipped_piecewise_linear_integral(
                station_x, result.froude_krylov_force_density_by_station, recovery_length)
            diffraction_force = clipped_piecewise_linear_integral(
                station_x, result.diffraction_force_density_by_station, recovery_length)
        froude_krylov_kernel.append(fk_force)
        diffraction_kernel.append(diffraction_force)
        total_kernel.append(fk_force + diffraction_force)
        condition_numbers.append(float(result.maximum_condition_number))
        system_residuals.append(float(result.maximum_linear_system_relative_residual))
        body_condition_residuals.append(float(result.body_condition_relative_residual))
        pressure_identity_residuals.append(
            float(result.equation30_incident_pressure_relative_residual)
        )
        force_integration_residuals.append(
            float(result.force_density_integration_relative_residual)
        )
        recovery_means.append(float(np.mean(recovery_weight)))

    # The kernel projects p onto N3=-normal_z. Body traction is -p*N3,
    # and the longitudinal response uses eta_CG=sin(w_e*t), not cosine.
    # Thus (-1) for traction times (-i) for wave phase gives +i here.
    fk_response = 1j * matched_bie_excitation_to_bow_up(
        np.asarray(froude_krylov_kernel, dtype=complex)
    )
    diffraction_response = 1j * matched_bie_excitation_to_bow_up(
        np.asarray(diffraction_kernel, dtype=complex)
    )
    excitation = 1j * matched_bie_excitation_to_bow_up(
        np.asarray(total_kernel, dtype=complex)
    )
    if not np.isfinite(excitation.real).all() or not np.isfinite(excitation.imag).all():
        raise RuntimeError("Matched-domain head-sea excitation contains non-finite values.")
    if np.any(np.linalg.norm(excitation, axis=1) <= 1.0e-12):
        raise RuntimeError("Matched-domain head-sea excitation contains a zero frequency row.")
    return (
        excitation,
        {
            "matched_domain_froude_krylov": fk_response,
            "matched_domain_diffraction": diffraction_response,
            "matched_domain_incident_plus_diffraction": excitation.copy(),
        },
        {
            "matched_domain_excitation_maximum_condition_number": float(max(condition_numbers)),
            "matched_domain_excitation_maximum_linear_system_relative_residual": float(
                max(system_residuals)
            ),
            "matched_domain_excitation_maximum_body_condition_relative_residual": float(
                max(body_condition_residuals)
            ),
            "matched_domain_excitation_maximum_incident_pressure_identity_relative_residual": float(
                max(pressure_identity_residuals)
            ),
            "matched_domain_excitation_maximum_force_integration_relative_residual": float(
                max(force_integration_residuals)
            ),
            "matched_domain_excitation_mean_recovery_weight": float(np.mean(recovery_means)),
            "matched_domain_pressure_projection_to_body_force_sign": -1.0,
            "matched_domain_cosine_to_sine_phase_shift_deg": -90.0,
        },
    )


def head_sea_wavenumber_from_encounter_frequency(
    encounter_omega_rad_s: np.ndarray,
    speed_mps: float,
    gravity_m_s2: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Invert ``omega_e=sqrt(g*k)+U*k`` for deep-water head seas."""

    omega_e = np.asarray(encounter_omega_rad_s, dtype=float)
    speed = float(speed_mps)
    gravity = float(gravity_m_s2)
    if omega_e.ndim != 1 or np.any(omega_e <= 0.0):
        raise ValueError("encounter_omega_rad_s must be a positive one-dimensional array.")
    if not math.isfinite(speed) or speed < 0.0:
        raise ValueError("speed_mps must be finite and non-negative.")
    if not math.isfinite(gravity) or gravity <= 0.0:
        raise ValueError("gravity_m_s2 must be finite and positive.")
    if speed <= 1.0e-12:
        wavenumber = omega_e**2 / gravity
    else:
        sqrt_k = (np.sqrt(gravity + 4.0 * speed * omega_e) - math.sqrt(gravity)) / (
            2.0 * speed
        )
        wavenumber = sqrt_k**2
    wave_omega = np.sqrt(gravity * wavenumber)
    closure = wave_omega + speed * wavenumber
    if not np.allclose(closure, omega_e, rtol=1.0e-12, atol=1.0e-12):
        raise RuntimeError("Head-sea encounter-frequency inversion failed to close.")
    return wavenumber, wave_omega


def _moment_matched_restoring_density(
    station_x_forward_m: np.ndarray,
    station_weight: np.ndarray,
    restoring_matrix: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Reconstruct a local vertical-load density from both restoring columns.

    A local vertical displacement is ``eta3+x*eta5``.  The density is therefore
    constrained so its zeroth and first longitudinal moments reproduce the
    heave and pitch columns of the supplied whole-craft restoring matrix.  A
    wetted-beam weight keeps the reconstruction on the physical loaded region;
    no response measurement enters the calculation.
    """

    x = np.asarray(station_x_forward_m, dtype=float)
    weight = np.asarray(station_weight, dtype=float)
    restoring = np.asarray(restoring_matrix, dtype=float)
    if x.ndim != 1 or weight.shape != x.shape or len(x) < 3:
        raise ValueError("Station coordinates and weights must be matching arrays with >=3 points.")
    if np.any(np.diff(x) <= 0.0) or np.any(weight < 0.0) or not np.any(weight > 0.0):
        raise ValueError("Station coordinates must increase and restoring weights must be non-negative.")
    if restoring.shape != (2, 2) or not np.isfinite(restoring).all():
        raise ValueError("restoring_matrix must be a finite 2x2 matrix.")
    basis = np.column_stack((np.ones_like(x), x))
    gram = np.empty((2, 2), dtype=float)
    for row in range(2):
        for column in range(2):
            gram[row, column] = float(
                np.trapezoid(weight * basis[:, row] * basis[:, column], x)
            )
    if not np.isfinite(gram).all() or np.linalg.cond(gram) > 1.0e12:
        raise ValueError("The wetted-station restoring moment system is singular or ill-conditioned.")
    density = np.empty((len(x), 2), dtype=float)
    for generalized_row in range(2):
        coefficients = np.linalg.solve(gram, restoring[generalized_row])
        density[:, generalized_row] = weight * (basis @ coefficients)
    reconstructed = np.column_stack(
        (
            np.trapezoid(density, x, axis=0),
            np.trapezoid(density * x[:, None], x, axis=0),
        )
    )
    residual = float(
        np.linalg.norm(reconstructed - restoring)
        / max(np.linalg.norm(restoring), 1.0e-30)
    )
    if residual > 1.0e-10:
        raise RuntimeError(
            f"Restoring-density moment reconstruction residual {residual:.3e} exceeds 1e-10."
        )
    return density, residual


def assemble_phase_resolved_head_sea_excitation(
    *,
    station_x_m: np.ndarray,
    total_force_density_by_station: np.ndarray,
    total_force_matrices: np.ndarray,
    end_force_matrices: np.ndarray,
    end_station_x_m: np.ndarray,
    station_waterplane_beam_m: np.ndarray,
    restoring_matrix: np.ndarray,
    encounter_omega_rad_s: np.ndarray,
    speed_mps: float,
    gravity_m_s2: float,
    lcg_from_transom_m: float,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float]]:
    """Assemble phased Froude--Krylov and diffraction excitation.

    The diffraction boundary condition is represented by the equivalent local
    heave displacement

    ``q_D(x)=i*omega_0/omega_e*exp(i*k*x)``.

    Multiplying the radiation complex-force density by ``q_D`` gives the
    Faltinsen Chapter 9 long-wave limit ``B*omega_0+i*A*omega_0*omega_e``.
    The incident-elevation phasor is ``-i*exp(i*k*x)``.  Its restoring-density
    integral gives ``-i*C[:,0]+k*C[:,1]`` as ``k`` tends to zero.  Finite wave
    length is retained station by station rather than through a fitted response
    multiplier.
    """

    omega_e = np.asarray(encounter_omega_rad_s, dtype=float)
    x_rows = np.asarray(station_x_m, dtype=float)
    density_rows = np.asarray(total_force_density_by_station, dtype=complex)
    total_force_rows = np.asarray(total_force_matrices, dtype=complex)
    end_rows = np.asarray(end_force_matrices, dtype=complex)
    end_x = np.asarray(end_station_x_m, dtype=float)
    beam_rows = np.asarray(station_waterplane_beam_m, dtype=float)
    restoring = np.asarray(restoring_matrix, dtype=float)
    n_frequency = len(omega_e)
    if x_rows.shape[0] != n_frequency or x_rows.ndim != 2:
        raise ValueError("station_x_m must have shape (n_frequency, n_station).")
    expected_density_shape = (n_frequency, x_rows.shape[1], 2, 2)
    if density_rows.shape != expected_density_shape:
        raise ValueError(
            "total_force_density_by_station must have shape "
            f"{expected_density_shape}."
        )
    if total_force_rows.shape != (n_frequency, 2, 2):
        raise ValueError("total_force_matrices must have shape (n_frequency,2,2).")
    if end_rows.shape != (n_frequency, 2, 2) or end_x.shape != (n_frequency,):
        raise ValueError("End-force matrices and coordinates must match the frequency grid.")
    if beam_rows.shape != x_rows.shape:
        raise ValueError("station_waterplane_beam_m must match station_x_m.")
    if restoring.shape == (2, 2):
        restoring = np.repeat(restoring[None, :, :], n_frequency, axis=0)
    if restoring.shape != (n_frequency, 2, 2):
        raise ValueError("restoring_matrix must have shape (2,2) or (n_frequency,2,2).")
    if not np.isfinite(x_rows).all() or not np.isfinite(beam_rows).all():
        raise ValueError("Station geometry used for excitation must be finite.")

    wavenumber, wave_omega = head_sea_wavenumber_from_encounter_frequency(
        omega_e,
        speed_mps,
        gravity_m_s2,
    )
    froude_krylov = np.empty((n_frequency, 2), dtype=complex)
    diffraction_body = np.empty_like(froude_krylov)
    diffraction_end = np.zeros_like(froude_krylov)
    restoring_residuals: list[float] = []
    radiation_uniform_residuals: list[float] = []
    for index in range(n_frequency):
        x = x_rows[index]
        x_forward = x - float(lcg_from_transom_m)
        if np.any(np.diff(x) <= 0.0):
            raise ValueError("Every station row must be strictly increasing.")
        restoring_density, restoring_residual = _moment_matched_restoring_density(
            x_forward,
            beam_rows[index],
            restoring[index],
        )
        restoring_residuals.append(restoring_residual)
        wave_phase = np.exp(1j * wavenumber[index] * x_forward)
        elevation_phasor = -1j * wave_phase
        froude_krylov[index] = np.trapezoid(
            restoring_density * elevation_phasor[:, None],
            x,
            axis=0,
        )

        equivalent_heave = (
            1j * wave_omega[index] / omega_e[index] * wave_phase
        )
        heave_column_density = density_rows[index, :, :, 0]
        diffraction_body[index] = np.trapezoid(
            heave_column_density * equivalent_heave[:, None],
            x,
            axis=0,
        )
        integrated_heave_column = np.trapezoid(heave_column_density, x, axis=0)
        end_column = end_rows[index, :, 0]
        if np.isfinite(end_x[index]):
            end_phase = np.exp(
                1j
                * wavenumber[index]
                * (end_x[index] - float(lcg_from_transom_m))
            )
            end_equivalent_heave = (
                1j * wave_omega[index] / omega_e[index] * end_phase
            )
            diffraction_end[index] = end_column * end_equivalent_heave
        elif np.linalg.norm(end_column) > 1.0e-12:
            raise ValueError("A non-zero end force requires a finite endpoint coordinate.")
        uniform_from_density = integrated_heave_column + end_column
        uniform_from_total = total_force_rows[index, :, 0]
        radiation_uniform_residuals.append(
            float(
                np.linalg.norm(uniform_from_density - uniform_from_total)
                / max(np.linalg.norm(uniform_from_total), 1.0e-30)
            )
        )
    diffraction = diffraction_body + diffraction_end
    total = froude_krylov + diffraction
    if not np.isfinite(total.real).all() or not np.isfinite(total.imag).all():
        raise RuntimeError("Phase-resolved head-sea excitation contains non-finite values.")
    diagnostics = {
        "maximum_restoring_moment_residual": float(max(restoring_residuals, default=0.0)),
        "maximum_uniform_radiation_reconstruction_residual": float(
            max(radiation_uniform_residuals, default=0.0)
        ),
    }
    return (
        total,
        {
            "froude_krylov": froude_krylov,
            "diffraction_body": diffraction_body,
            "diffraction_end": diffraction_end,
            "diffraction_total": diffraction,
        },
        diagnostics,
    )


def build_planing_wetted_station_hull(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    *,
    station_count: int = 21,
    wagner_pileup_factor: float = 1.0,
) -> StationHull:
    """Build the equilibrium mean wetted contour used by a linear free-surface BIE.

    The longitudinal distance between keel and chine wetting is taken from the
    supplied equilibrium state.  It already contains the selected
    Faltinsen/Savitsky steady spray-root relation and must not be replaced by a
    flat-water geometric intersection.  ``wagner_pileup_factor`` is retained
    as a dimensionless sensitivity multiplier around that frozen mean contour;
    its production default is one.
    """
    if station_count < 9:
        raise ValueError("station_count must be at least 9.")
    if not math.isfinite(wagner_pileup_factor) or wagner_pileup_factor <= 0.0:
        raise ValueError("wagner_pileup_factor must be finite and positive.")
    wetted_length = float(equilibrium.geometry.keel_wetted_length_m)
    if not 0.0 < wetted_length <= boat.length_m:
        raise ValueError("Keel wetted length must lie within the physical hull length.")
    beta = math.radians(boat.deadrise_deg)
    chine_draft = 0.5 * boat.beam_m * math.tan(beta)
    chine_wetting_offset = float(equilibrium.geometry.x_s_m)
    if not 0.0 < chine_wetting_offset <= wetted_length:
        raise ValueError(
            "The equilibrium chine-wetting offset must lie inside the keel-wetted length."
        )
    effective_transition_length = chine_wetting_offset / wagner_pileup_factor
    epsilon = max(1.0e-5 * wetted_length, 1.0e-6)
    x_values = np.linspace(epsilon, wetted_length - epsilon, station_count)
    stations = []
    for x_m in x_values:
        mean_wetted_fraction = (wetted_length - x_m) / effective_transition_length
        draft = min(max(chine_draft * mean_wetted_fraction, epsilon), chine_draft)
        waterplane_beam = min(boat.beam_m, 2.0 * draft / max(math.tan(beta), 1.0e-12))
        area = 0.5 * waterplane_beam * draft
        stations.append(
            HardChineStation(
                x_m=float(x_m),
                beam_m=max(float(waterplane_beam), epsilon),
                draft_m=float(draft),
                deadrise_deg=boat.deadrise_deg,
                waterplane_beam_override_m=float(waterplane_beam),
                submerged_area_override_m2=float(area),
                centroid_z_override_m=float(draft / 3.0),
            )
        )
    return StationHull(
        length_m=boat.length_m,
        lcg_from_transom_m=boat.lcg_m,
        stations=tuple(stations),
    )


def assemble_planing_wetted_hydrostatic_restoring(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    *,
    station_count: int = 401,
    wagner_pileup_factor: float = 1.0,
) -> np.ndarray:
    """Linearize buoyancy of the reconstructed mean-wetted planing surface.

    The reduced Chapter 9 planing load is differentiated separately in
    :mod:`planing_seakeeping.coefficients`.  This routine supplies the
    hydrostatic part that becomes important as a craft approaches the
    semi-planing range.  At every perturbation it rebuilds the prescribed
    keel/chine intersection, integrates submerged sectional area, and places
    the vertical buoyancy resultant at the longitudinal center of buoyancy.

    Coordinates follow the longitudinal response contract: heave is positive
    upward and pitch is positive bow-up.  No response or experimental motion
    value enters the calculation.
    """

    if station_count < 9:
        raise ValueError("station_count must be at least 9.")
    heave_step = max(1.0e-5 * boat.beam_m, 1.0e-6)
    pitch_step = 1.0e-5

    def buoyancy_load(eta3_m: float, eta5_rad: float) -> np.ndarray:
        geometry = compute_geometry(
            boat,
            equilibrium.speed_through_water_mps,
            equilibrium.z_wl_m,
            equilibrium.trim_rad,
            eta3_m=eta3_m,
            eta5_rad=eta5_rad,
        )
        perturbed = replace(equilibrium, geometry=geometry)
        hull = build_planing_wetted_station_hull(
            boat,
            perturbed,
            station_count=station_count,
            wagner_pileup_factor=wagner_pileup_factor,
        )
        hydrostatics = hull.hydrostatics()
        buoyancy_n = (
            boat.rho_water_kg_m3
            * boat.gravity_m_s2
            * hydrostatics.displacement_volume_m3
        )
        lever_forward_m = hydrostatics.center_of_buoyancy_x_m - boat.lcg_m
        return np.array(
            [buoyancy_n, buoyancy_n * lever_forward_m],
            dtype=float,
        )

    derivative_heave = (
        buoyancy_load(heave_step, 0.0) - buoyancy_load(-heave_step, 0.0)
    ) / (2.0 * heave_step)
    derivative_pitch = (
        buoyancy_load(0.0, pitch_step) - buoyancy_load(0.0, -pitch_step)
    ) / (2.0 * pitch_step)
    restoring = -np.column_stack((derivative_heave, derivative_pitch))
    if restoring.shape != (2, 2) or not np.isfinite(restoring).all():
        raise RuntimeError("Mean-wetted hydrostatic restoring matrix is not finite 2x2 data.")
    return restoring


def compute_matched_bie_frequency_correction(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    sample_omega_rad_s: np.ndarray,
    *,
    high_frequency_reference_rad_s: float,
    station_count: int = 21,
    body_panels_per_section: int = 30,
    free_surface_inner_panels: int = 20,
    free_surface_outer_panels: int = 40,
    force_component_route: str = "total_eq32_stokes_body_plus_end",
    wagner_pileup_factor: float = 1.0,
    restoring_matrix: np.ndarray | None = None,
    transom_force_cutoff_length_beams: float = 0.0,
    transom_force_recovery_profile: str = "hard_zero",
    head_sea_excitation_formulation: str = "equivalent_radiation",
    history_steps: int = 40,
    history_quadrature_count: int = 32,
    history_k_max: float = 25.0,
    cutoff_quadrature: str = "nodal_mask",
    free_surface_substeps_per_station: int = 1,
    waterline_grading_exponent: float = 1.0,
) -> PlaningFrequencyCorrection:
    if not math.isfinite(waterline_grading_exponent) or not 1. <= waterline_grading_exponent <= 2.:
        raise ValueError('waterline_grading_exponent must be finite and between 1 and 2')
    omega = np.asarray(sample_omega_rad_s, dtype=float)
    if omega.ndim != 1 or len(omega) < 2 or np.any(omega <= 0.0):
        raise ValueError("sample_omega_rad_s must contain at least two positive frequencies.")
    if high_frequency_reference_rad_s <= float(omega.max()):
        raise ValueError("high_frequency_reference_rad_s must exceed every sampled response frequency.")
    cutoff_beams = float(transom_force_cutoff_length_beams)
    recovery_profile = str(transom_force_recovery_profile).strip().lower()
    excitation_formulation = str(head_sea_excitation_formulation).strip().lower()
    if cutoff_quadrature not in {"nodal_mask", "clipped_linear"}:
        raise ValueError("Unknown cutoff quadrature")
    if cutoff_quadrature == "clipped_linear" and (
        recovery_profile != "hard_zero" or
        (restoring_matrix is not None and excitation_formulation != "matched_domain_incident_diffraction")
    ):
        raise ValueError("clipped_linear requires hard_zero and direct matched excitation")
    if not math.isfinite(cutoff_beams) or cutoff_beams < 0.0:
        raise ValueError("transom_force_cutoff_length_beams must be finite and non-negative.")
    if recovery_profile not in {"hard_zero", "linear_ramp", "square_root_ramp"}:
        raise ValueError(
            "transom_force_recovery_profile must be hard_zero, linear_ramp, or "
            "square_root_ramp."
        )
    if excitation_formulation not in {
        "equivalent_radiation",
        "section_bem_incident_diffraction",
        "matched_domain_incident_diffraction",
    }:
        raise ValueError(
            "head_sea_excitation_formulation must be equivalent_radiation or "
            "section_bem_incident_diffraction or matched_domain_incident_diffraction."
        )
    solve_omega = np.unique(np.concatenate((omega, [float(high_frequency_reference_rad_s)])))
    hull = build_planing_wetted_station_hull(
        boat,
        equilibrium,
        station_count=station_count,
        wagner_pileup_factor=wagner_pileup_factor,
    )
    body = RigidBody6DOF.from_radii(
        mass_kg=boat.mass_kg,
        roll_radius_gyration_m=max(0.35 * boat.beam_m, 1.0e-6),
        pitch_radius_gyration_m=boat.pitch_radius_gyration_m,
        yaw_radius_gyration_m=max(boat.pitch_radius_gyration_m, 1.0e-6),
    )
    config = Linear2p5DProviderConfig(
        enabled=True,
        production=False,
        formulation="matched_bie",
        hull_stations=station_count,
        body_panels_per_section=body_panels_per_section,
        free_surface_inner_panels=free_surface_inner_panels,
        free_surface_outer_panels=free_surface_outer_panels,
        control_surface_radius_beams=3.0,
        include_steady_perturbation=False,
        include_end_terms=True,
    )
    provider = LinearFrequencyProvider(
        source="linear_2p5d",
        production=False,
        rho_water_kg_m3=boat.rho_water_kg_m3,
        gravity_m_s2=boat.gravity_m_s2,
        config=config,
        matched_options={
            "parametric_section_shape": "hard_chine_v",
            "force_assembly_route": "eq32_stokes_body_plus_end",
            "history_steps": history_steps,
            "history_quadrature_count": history_quadrature_count,
            "history_k_max": history_k_max,
            "free_surface_substeps_per_station": free_surface_substeps_per_station,
            "waterline_grading_exponent": waterline_grading_exponent,
        },
    )
    full = provider.solve_station_hull(
        hull,
        body,
        solve_omega,
        speed_mps=equilibrium.speed_through_water_mps,
    )
    route = str(force_component_route).strip().lower()
    route_aliases = {
        "total": "total_eq32_stokes_body_plus_end",
        "total_eq32_stokes_body_plus_end": "total_eq32_stokes_body_plus_end",
        "time": "time_derivative_only",
        "time_derivative_only": "time_derivative_only",
        "stokes": "stokes_body_forward_speed_only",
        "stokes_body_forward_speed_only": "stokes_body_forward_speed_only",
        "end": "end_term_only",
        "end_term_only": "end_term_only",
        "time_plus_stokes": "time_plus_stokes_body_forward_speed",
        "time_plus_stokes_body_forward_speed": "time_plus_stokes_body_forward_speed",
        "time_plus_end": "time_plus_end_term",
        "time_plus_end_term": "time_plus_end_term",
    }
    if route not in route_aliases:
        raise ValueError(
            "force_component_route must select total, time derivative, Stokes body forward-speed, "
            "end term, time plus Stokes, or time plus end."
        )
    route = route_aliases[route]
    breakdown = full.contribution_breakdown
    total_force = np.asarray(breakdown["heave_pitch_complex_force_matrices"], dtype=complex)
    time_force = np.asarray(
        breakdown["heave_pitch_time_derivative_force_matrices"], dtype=complex
    )
    stokes_force = np.asarray(
        breakdown["heave_pitch_stokes_body_forward_speed_force_matrices"], dtype=complex
    )
    end_force = np.asarray(breakdown["heave_pitch_end_term_force_matrices"], dtype=complex)
    component_force_kernel_convention = {
        "total_eq32_stokes_body_plus_end": total_force,
        "time_derivative_only": time_force,
        "stokes_body_forward_speed_only": stokes_force,
        "end_term_only": end_force,
        "time_plus_stokes_body_forward_speed": time_force + stokes_force,
        "time_plus_end_term": time_force + end_force,
    }[route]
    transom_diagnostics: dict[str, float] = {}
    corrected_total_density_kernel: np.ndarray | None = None
    corrected_end_force_kernel: np.ndarray | None = None
    if cutoff_beams > 0.0:
        if route != "total_eq32_stokes_body_plus_end":
            raise ValueError(
                "The transom sectional-force correction requires the complete Eq.32 route."
            )
        station_x = np.asarray(breakdown["station_x_m"], dtype=float)
        time_density = np.asarray(
            breakdown["heave_pitch_time_derivative_force_density_by_station"],
            dtype=complex,
        )
        stokes_density = np.asarray(
            breakdown[
                "heave_pitch_stokes_body_forward_speed_force_density_by_station"
            ],
            dtype=complex,
        )
        end_x_over_l = np.asarray(breakdown["end_term_station_x_over_l"], dtype=float)
        (
            corrected_total_density_kernel,
            corrected_end_force_kernel,
            component_force_kernel_convention,
            transom_diagnostics,
        ) = apply_transom_sectional_force_cutoff(
            station_x_m=station_x,
            force_density_by_station=time_density + stokes_density,
            end_force_matrices=end_force,
            end_station_x_m=end_x_over_l * boat.length_m,
            cutoff_length_m=cutoff_beams * boat.beam_m,
            recovery_profile=recovery_profile,
            cutoff_quadrature=cutoff_quadrature,
        )
    component_force = matched_bie_matrix_to_bow_up(component_force_kernel_convention)
    expected_shape = (len(solve_omega), 2, 2)
    if component_force.shape != expected_shape or not np.isfinite(component_force).all():
        raise RuntimeError(
            f"Matched-BIE force component {route!r} must be finite with shape {expected_shape}."
        )
    raw_added = np.real(component_force) / solve_omega[:, None, None] ** 2
    raw_damping = -np.imag(component_force) / solve_omega[:, None, None]
    high_index = int(np.argmax(solve_omega))
    high_added = raw_added[high_index]
    high_damping = raw_damping[high_index]
    delta_added = raw_added - high_added[None, :, :]
    delta_damping = raw_damping - high_damping[None, :, :]
    excitation: np.ndarray | None = None
    excitation_components: dict[str, np.ndarray] = {}
    excitation_diagnostics: dict[str, float] = {}
    if restoring_matrix is not None:
        if route != "total_eq32_stokes_body_plus_end":
            raise ValueError(
                "Phase-resolved excitation requires the complete Eq.32 force component route."
            )
        station_x = np.asarray(breakdown["station_x_m"], dtype=float)
        station_beam = np.asarray(breakdown["station_waterplane_beams"], dtype=float)
        time_density = np.asarray(
            breakdown["heave_pitch_time_derivative_force_density_by_station"],
            dtype=complex,
        )
        stokes_density = np.asarray(
            breakdown[
                "heave_pitch_stokes_body_forward_speed_force_density_by_station"
            ],
            dtype=complex,
        )
        total_density = matched_bie_matrix_to_bow_up(
            time_density + stokes_density
            if corrected_total_density_kernel is None
            else corrected_total_density_kernel
        )
        end_force = matched_bie_matrix_to_bow_up(
            np.asarray(breakdown["heave_pitch_end_term_force_matrices"], dtype=complex)
            if corrected_end_force_kernel is None
            else corrected_end_force_kernel
        )
        end_x_over_l = np.asarray(
            breakdown["end_term_station_x_over_l"],
            dtype=float,
        )
        if excitation_formulation == "equivalent_radiation":
            excitation, excitation_components, excitation_diagnostics = (
                assemble_phase_resolved_head_sea_excitation(
                    station_x_m=station_x,
                    total_force_density_by_station=total_density,
                    total_force_matrices=component_force,
                    end_force_matrices=end_force,
                    end_station_x_m=end_x_over_l * boat.length_m,
                    station_waterplane_beam_m=station_beam,
                    restoring_matrix=np.asarray(restoring_matrix, dtype=float),
                    encounter_omega_rad_s=solve_omega,
                    speed_mps=equilibrium.speed_through_water_mps,
                    gravity_m_s2=boat.gravity_m_s2,
                    lcg_from_transom_m=boat.lcg_m,
                )
            )
            if (
                excitation_diagnostics[
                    "maximum_uniform_radiation_reconstruction_residual"
                ]
                > 1.0e-8
            ):
                raise RuntimeError(
                    "Eq.32 station force density and whole-craft radiation matrix do not close: "
                    f"relative residual={excitation_diagnostics['maximum_uniform_radiation_reconstruction_residual']:.3e}."
                )
        elif excitation_formulation == "section_bem_incident_diffraction":
            excitation, excitation_components, excitation_diagnostics = (
                assemble_section_bem_head_sea_excitation(
                    hull=hull,
                    encounter_omega_rad_s=solve_omega,
                    speed_mps=equilibrium.speed_through_water_mps,
                    gravity_m_s2=boat.gravity_m_s2,
                    rho_water_kg_m3=boat.rho_water_kg_m3,
                    body_panel_count=body_panels_per_section,
                    free_surface_panel_count_per_side=free_surface_inner_panels,
                    transom_recovery_length_m=cutoff_beams * boat.beam_m,
                    transom_recovery_profile=recovery_profile,
                )
            )
        else:
            excitation, excitation_components, excitation_diagnostics = (
                assemble_matched_domain_head_sea_excitation(
                    hull=hull,
                    encounter_omega_rad_s=solve_omega,
                    speed_mps=equilibrium.speed_through_water_mps,
                    gravity_m_s2=boat.gravity_m_s2,
                    rho_water_kg_m3=boat.rho_water_kg_m3,
                    config=config,
                    parametric_section_shape="hard_chine_v",
                    matched_sweep_options={
                        "history_steps": history_steps,
                        "history_quadrature_count": history_quadrature_count,
                        "history_k_max": history_k_max,
                        "free_surface_substeps_per_station": free_surface_substeps_per_station,
                        "waterline_grading_exponent": waterline_grading_exponent,
                    },
                    cutoff_quadrature=cutoff_quadrature,
                    transom_recovery_length_m=cutoff_beams * boat.beam_m,
                    transom_recovery_profile=recovery_profile,
                )
            )
    return PlaningFrequencyCorrection(
        sample_omega_rad_s=solve_omega,
        high_frequency_reference_rad_s=float(high_frequency_reference_rad_s),
        delta_added_mass=delta_added,
        delta_radiation_damping=delta_damping,
        raw_added_mass=raw_added,
        raw_radiation_damping=raw_damping,
        metadata={
            "source": "ma2005_matched_bie_dynamic_minus_high_frequency_limit",
            "steady_perturbation_potential_solved": False,
            "forward_speed_body_condition": "A1_eq6_uniform_flow_m5_equals_Nz_not_solved_steady_planing_flow",
            "waterline_grading_exponent": waterline_grading_exponent,
            "provider_route": full.metadata.get("provider_route", "unknown"),
            "force_assembly_route": "eq32_stokes_body_plus_end",
            "base_load_source": "supplied_by_longitudinal_frequency_model",
            "double_counting_control": "subtract_same_geometry_matched_bie_high_frequency_matrix",
            "kernel_coordinate_convention": "heave_up_x_positive_aft_pitch_kernel",
            "response_coordinate_convention": "heave_up_pitch_bow_up",
            "coordinate_transform": "T=diag(1,-1); K_response=T*K_kernel*T",
            "force_component_route": route,
            "station_count": station_count,
            "body_panels_per_section": body_panels_per_section,
            "free_surface_inner_panels": free_surface_inner_panels,
            "free_surface_outer_panels": free_surface_outer_panels,
            "wagner_pileup_factor": wagner_pileup_factor,
            "matched_bie_wetted_geometry_source": (
                "equilibrium_mean_keel_and_chine_wetted_contour"
                if abs(float(wagner_pileup_factor) - 1.0) <= 1.0e-12
                else "diagnostic_scale_about_equilibrium_mean_wetted_contour"
            ),
            "transom_force_cutoff_length_beams": cutoff_beams,
            "cutoff_quadrature": cutoff_quadrature,
            "free_surface_substeps_per_station": free_surface_substeps_per_station,
            "transom_force_recovery_profile": recovery_profile,
            "transom_force_cutoff_source": (
                (
                    "Sun_Faltinsen_planing_2Dt_empirical_3D_stern_length_"
                    + {
                        "hard_zero": "hard_zero",
                        "linear_ramp": "linear_pressure_recovery",
                        "square_root_ramp": "local_square_root_pressure_recovery",
                    }[recovery_profile]
                )
                if cutoff_beams > 0.0
                else "disabled"
            ),
            "response_calibration_used": False,
            "validity_status": full.validity.status,
            "head_sea_excitation_available": excitation is not None,
            "head_sea_excitation_formulation": (
                (
                    "station_phase_moment_matched_fk_plus_radiation_equivalent_diffraction"
                    if excitation_formulation == "equivalent_radiation"
                    else (
                        "section_bem_direct_incident_plus_diffraction_absolute_frequency"
                        if excitation_formulation == "section_bem_incident_diffraction"
                        else "ma2005_matched_domain_eq3_eq4_eq30_incident_plus_diffraction"
                    )
                )
                if excitation is not None
                else "not_computed"
            ),
            **excitation_diagnostics,
            **transom_diagnostics,
        },
        excitation_per_wave_amplitude=excitation,
        excitation_components=excitation_components,
    )


def compute_section_bem_frequency_correction(
    boat: BoatConfig,
    equilibrium: EquilibriumState,
    sample_omega_rad_s: np.ndarray,
    *,
    high_frequency_reference_rad_s: float,
    station_count: int = 21,
    body_panels_per_section: int = 30,
    free_surface_panels_per_side: int = 20,
    section_solver: str = "pdstrip_style",
    wagner_pileup_factor: float = 1.0,
) -> PlaningFrequencyCorrection:
    """Build a diagnostic classical 2D-section radiation correction.

    Each wetted section is solved independently at the encounter frequency and
    integrated over the measured running wetted geometry.  This is a diagnostic
    control route for the matched 2.5D kernel, not a replacement for Gate 1.
    """

    omega = np.asarray(sample_omega_rad_s, dtype=float)
    if omega.ndim != 1 or len(omega) < 2 or np.any(omega <= 0.0):
        raise ValueError("sample_omega_rad_s must contain at least two positive frequencies.")
    if high_frequency_reference_rad_s <= float(omega.max()):
        raise ValueError("high_frequency_reference_rad_s must exceed every sampled response frequency.")
    solve_omega = np.unique(np.concatenate((omega, [float(high_frequency_reference_rad_s)])))
    hull = build_planing_wetted_station_hull(
        boat,
        equilibrium,
        station_count=station_count,
        wagner_pileup_factor=wagner_pileup_factor,
    )
    raw_added = np.empty((len(solve_omega), 2, 2), dtype=float)
    raw_damping = np.empty_like(raw_added)
    for index, omega_i in enumerate(solve_omega):
        matrices = assemble_experimental_bem_6dof_matrices(
            hull,
            rho_water_kg_m3=boat.rho_water_kg_m3,
            gravity_m_s2=boat.gravity_m_s2,
            omega_rad_s=float(omega_i),
            free_surface_panel_count_per_side=free_surface_panels_per_side,
            body_panel_count=body_panels_per_section,
            speed_mps=equilibrium.speed_through_water_mps,
            section_solver=section_solver,
        )
        longitudinal = np.ix_((2, 4), (2, 4))
        raw_added[index] = matched_bie_matrix_to_bow_up(matrices.added_mass[longitudinal])
        raw_damping[index] = matched_bie_matrix_to_bow_up(matrices.damping[longitudinal])
    if not np.isfinite(raw_added).all() or not np.isfinite(raw_damping).all():
        raise RuntimeError("Section-BEM radiation matrices must be finite.")
    high_added = raw_added[-1]
    high_damping = raw_damping[-1]
    return PlaningFrequencyCorrection(
        sample_omega_rad_s=solve_omega,
        high_frequency_reference_rad_s=float(high_frequency_reference_rad_s),
        delta_added_mass=raw_added - high_added[None, :, :],
        delta_radiation_damping=raw_damping - high_damping[None, :, :],
        raw_added_mass=raw_added,
        raw_radiation_damping=raw_damping,
        metadata={
            "source": "classical_independent_section_bem_radiation_diagnostic",
            "base_load_source": "supplied_by_longitudinal_frequency_model",
            "section_solver": section_solver,
            "station_count": station_count,
            "body_panels_per_section": body_panels_per_section,
            "free_surface_panels_per_side": free_surface_panels_per_side,
            "wagner_pileup_factor": wagner_pileup_factor,
            "kernel_coordinate_convention": "heave_up_x_positive_aft_pitch_kernel",
            "response_coordinate_convention": "heave_up_pitch_bow_up",
            "coordinate_transform": "T=diag(1,-1); K_response=T*K_kernel*T",
            "response_calibration_used": False,
            "validity_status": "diagnostic_control_not_gate1_replacement",
        },
    )


def _interpolate_matrix(
    target_omega: np.ndarray, sample_omega: np.ndarray, values: np.ndarray
) -> np.ndarray:
    target = np.asarray(target_omega, dtype=float)
    result = np.empty((len(target), 2, 2), dtype=float)
    for row in range(2):
        for column in range(2):
            result[:, row, column] = np.interp(
                target,
                sample_omega,
                values[:, row, column],
                left=values[0, row, column],
                right=values[-1, row, column],
            )
    return result


def _interpolate_complex_vector(
    target_omega: np.ndarray,
    sample_omega: np.ndarray,
    values: np.ndarray,
) -> np.ndarray:
    target = np.asarray(target_omega, dtype=float)
    source = np.asarray(values, dtype=complex)
    if source.shape != (len(sample_omega), 2):
        raise ValueError("Complex vector interpolation requires shape (n_frequency,2).")
    result = np.empty((len(target), 2), dtype=complex)
    for column in range(2):
        result[:, column] = np.interp(
            target,
            sample_omega,
            source[:, column].real,
            left=source[0, column].real,
            right=source[-1, column].real,
        ) + 1j * np.interp(
            target,
            sample_omega,
            source[:, column].imag,
            left=source[0, column].imag,
            right=source[-1, column].imag,
        )
    return result


def _verify_target_context_match(
    base_model: LongitudinalFrequencyModel,
    correction: PlaningFrequencyCorrection,
) -> None:
    correction_context = correction.metadata.get("target_context")
    if not correction_context:
        return
    model_context = base_model.metadata.get("target_context")
    if not isinstance(model_context, dict):
        raise ValueError(
            "A target-bound forced-motion matrix requires target_context in the response model."
        )
    for name, correction_value in correction_context.items():
        if name == "target_identifier":
            continue
        if name not in model_context:
            raise ValueError(f"Response model target context is missing {name}.")
        model_value = model_context[name]
        if isinstance(correction_value, str):
            matches = str(model_value) == correction_value
        else:
            relative_tolerance = 1.0e-4 if name == "fn_b" else 1.0e-8
            matches = math.isclose(
                float(model_value),
                float(correction_value),
                rel_tol=relative_tolerance,
                abs_tol=1.0e-10,
            )
        if not matches:
            raise ValueError(
                "Forced-motion matrix target mismatch for "
                f"{name}: matrix={correction_value!r}, model={model_value!r}."
            )


def apply_frequency_correction(
    base_model: LongitudinalFrequencyModel,
    correction: PlaningFrequencyCorrection,
    *,
    include_added_mass: bool = True,
    include_radiation_damping: bool = True,
    application_mode: str = "delta_from_high_frequency",
    recompute_faltinsen_excitation: bool = False,
    use_phase_resolved_excitation: bool = False,
) -> LongitudinalFrequencyModel:
    if not include_added_mass and not include_radiation_damping:
        raise ValueError("At least one frequency-correction component must be enabled.")
    _verify_target_context_match(base_model, correction)
    omega = base_model.hydrodynamics.solver_omega_rad_s
    if correction.metadata.get("application_contract") == "replace_with_matched_bie":
        lower = float(correction.sample_omega_rad_s[0])
        upper = float(correction.sample_omega_rad_s[-1])
        tolerance = 1.0e-10 * max(1.0, abs(lower), abs(upper))
        if float(np.min(omega)) < lower - tolerance or float(np.max(omega)) > upper + tolerance:
            raise ValueError(
                "Target-bound forced-motion matrices may only be interpolated inside their "
                f"computed frequency range [{lower:.9g}, {upper:.9g}] rad/s; response range is "
                f"[{float(np.min(omega)):.9g}, {float(np.max(omega)):.9g}] rad/s."
            )
    mode = str(application_mode).strip().lower()
    if mode not in {
        "delta_from_high_frequency",
        "replace_with_matched_bie",
        "planing_base_plus_matched_radiation",
        "planing_high_frequency_added_plus_matched_damping",
    }:
        raise ValueError(
            "application_mode must be delta_from_high_frequency, replace_with_matched_bie, "
            "planing_base_plus_matched_radiation, or "
            "planing_high_frequency_added_plus_matched_damping."
        )
    if correction.raw_restoring is not None and (
        mode != "replace_with_matched_bie"
        or not include_added_mass
        or not include_radiation_damping
    ):
        raise ValueError(
            "A target 2D+t restoring matrix requires complete A/B/C replacement together."
        )
    if mode == "delta_from_high_frequency":
        delta_added = _interpolate_matrix(
            omega, correction.sample_omega_rad_s, correction.delta_added_mass
        )
        delta_damping = _interpolate_matrix(
            omega, correction.sample_omega_rad_s, correction.delta_radiation_damping
        )
        added = base_model.hydrodynamics.added_mass + (
            delta_added if include_added_mass else np.zeros_like(delta_added)
        )
        damping = base_model.hydrodynamics.radiation_damping + (
            delta_damping if include_radiation_damping else np.zeros_like(delta_damping)
        )
    elif mode == "replace_with_matched_bie":
        matched_added = _interpolate_matrix(
            omega, correction.sample_omega_rad_s, correction.raw_added_mass
        )
        matched_damping = _interpolate_matrix(
            omega, correction.sample_omega_rad_s, correction.raw_radiation_damping
        )
        added = matched_added if include_added_mass else base_model.hydrodynamics.added_mass
        damping = (
            matched_damping
            if include_radiation_damping
            else base_model.hydrodynamics.radiation_damping
        )
    elif mode == "planing_base_plus_matched_radiation":
        if not include_added_mass or not include_radiation_damping:
            raise ValueError(
                "planing_base_plus_matched_radiation is one physical formulation and requires "
                "both added-mass and damping components."
            )
        delta_added = _interpolate_matrix(
            omega,
            correction.sample_omega_rad_s,
            correction.delta_added_mass,
        )
        matched_damping = _interpolate_matrix(
            omega,
            correction.sample_omega_rad_s,
            correction.raw_radiation_damping,
        )
        added = base_model.hydrodynamics.added_mass + delta_added
        damping = base_model.hydrodynamics.radiation_damping + matched_damping
    else:
        if not include_added_mass or not include_radiation_damping:
            raise ValueError(
                "planing_high_frequency_added_plus_matched_damping is one physical formulation "
                "and requires both added-mass and damping components."
            )
        delta_added = _interpolate_matrix(
            omega,
            correction.sample_omega_rad_s,
            correction.delta_added_mass,
        )
        matched_damping = _interpolate_matrix(
            omega,
            correction.sample_omega_rad_s,
            correction.raw_radiation_damping,
        )
        # The Chapter 9 base supplies the high-frequency planing added mass.
        # Eq. 32 matched damping already contains its forward-speed transport
        # terms, so replacing damping avoids counting those terms twice.
        added = base_model.hydrodynamics.added_mass + delta_added
        damping = matched_damping
    restoring = base_model.restoring
    if correction.raw_restoring is not None:
        restoring = _interpolate_matrix(
            omega,
            correction.sample_omega_rad_s,
            correction.raw_restoring,
        )
    if recompute_faltinsen_excitation and use_phase_resolved_excitation:
        raise ValueError(
            "recompute_faltinsen_excitation and use_phase_resolved_excitation are mutually exclusive."
        )
    excitation = base_model.excitation_per_wave_amplitude
    if use_phase_resolved_excitation:
        if correction.excitation_per_wave_amplitude is None:
            raise ValueError("The frequency correction does not contain phase-resolved excitation.")
        excitation = _interpolate_complex_vector(
            omega,
            correction.sample_omega_rad_s,
            correction.excitation_per_wave_amplitude,
        )
    if recompute_faltinsen_excitation:
        speed_samples = (
            base_model.hydrodynamics.encounter_omega_rad_s - base_model.omega0_rad_s
        ) / base_model.wavenumber_rad_m
        speed = float(np.mean(speed_samples))
        if not np.allclose(speed_samples, speed, rtol=1.0e-9, atol=1.0e-10):
            raise ValueError("The response grid does not imply one constant forward speed.")
        excitation = faltinsen_head_sea_excitation(
            added,
            damping,
            restoring,
            base_model.omega0_rad_s,
            base_model.hydrodynamics.encounter_omega_rad_s,
            base_model.wavenumber_rad_m,
            speed,
            heave_finite_length_factor=base_model.heave_finite_length_factor,
            pitch_finite_length_factor=base_model.pitch_finite_length_factor,
        )
    hydro = LongitudinalHydrodynamicMatrices(
        solver_omega_rad_s=omega,
        encounter_omega_rad_s=base_model.hydrodynamics.encounter_omega_rad_s,
        added_mass=added,
        radiation_damping=damping,
        metadata={
            **base_model.hydrodynamics.metadata,
            **correction.metadata,
            "provider_route": (
                f"{base_model.hydrodynamics.metadata.get('provider_route', 'base')}"
                f"_plus_matched_bie_{mode}"
            ),
            "coefficient_frequency_dependence": f"matched_bie_{mode}",
            "frequency_correction_added_mass_enabled": include_added_mass,
            "frequency_correction_radiation_damping_enabled": include_radiation_damping,
            "frequency_correction_application_mode": mode,
            "excitation_recomputed_from_final_matrices": recompute_faltinsen_excitation,
            "phase_resolved_excitation_enabled": use_phase_resolved_excitation,
        },
    )
    return LongitudinalFrequencyModel(
        hydrodynamics=hydro,
        rigid_mass=base_model.rigid_mass,
        restoring=restoring,
        excitation_per_wave_amplitude=excitation,
        omega0_rad_s=base_model.omega0_rad_s,
        wavenumber_rad_m=base_model.wavenumber_rad_m,
        wavelength_m=base_model.wavelength_m,
        wave_amplitude_m=base_model.wave_amplitude_m,
        point_x_forward_m=base_model.point_x_forward_m,
        heave_finite_length_factor=base_model.heave_finite_length_factor,
        pitch_finite_length_factor=base_model.pitch_finite_length_factor,
        metadata={
            **base_model.metadata,
            "frequency_correction_source": correction.metadata["source"],
            "frequency_correction_high_reference_rad_s": correction.high_frequency_reference_rad_s,
            "response_calibration_used": False,
            "frequency_correction_added_mass_enabled": include_added_mass,
            "frequency_correction_radiation_damping_enabled": include_radiation_damping,
            "frequency_correction_application_mode": mode,
            "frequency_correction_restoring_replaced": correction.raw_restoring is not None,
            "excitation_recomputed_from_final_matrices": recompute_faltinsen_excitation,
            "phase_resolved_excitation_enabled": use_phase_resolved_excitation,
            "excitation_formulation": (
                correction.metadata.get("head_sea_excitation_formulation", "unknown")
                if use_phase_resolved_excitation
                else base_model.metadata.get("excitation_formulation", "unknown")
            ),
        },
    )
