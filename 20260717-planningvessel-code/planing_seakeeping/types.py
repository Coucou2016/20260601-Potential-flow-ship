from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ModelCapabilities:
    """Capability declaration for a hydrodynamic provider or kernel."""

    frequency_domain: bool = False
    time_domain: bool = False
    six_dof: bool = False
    nonlinear_free_surface: bool = False
    instantaneous_wetted_surface: bool = False
    multihull_interaction: bool = False
    hydrofoil_control: bool = False
    production: bool = False
    validated_benchmarks: tuple[str, ...] = ()
    status: str = "not_validated"
    assumptions: tuple[str, ...] = ()

    def require_production_ready(self) -> None:
        if not self.production:
            raise ValueError(
                f"Provider status is {self.status!r}; production=true is only allowed after benchmark validation."
            )


@dataclass(frozen=True)
class ValidityReport:
    """Traceable validity metadata attached to numerical results."""

    status: str
    model_assumptions: tuple[str, ...] = ()
    violated_assumptions: tuple[str, ...] = ()
    extrapolation_distance: dict[str, float] = field(default_factory=dict)
    reference_cases: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def is_validated(self) -> bool:
        return self.status == "validated" and not self.violated_assumptions

    @classmethod
    def unvalidated(cls, *notes: str, reference_cases: tuple[str, ...] = ()) -> "ValidityReport":
        return cls(status="not_validated", reference_cases=reference_cases, notes=tuple(notes))


@dataclass(frozen=True)
class HydroLoadResult:
    """Generalized hydrodynamic load with component-level provenance."""

    tau: np.ndarray
    components: dict[str, np.ndarray] = field(default_factory=dict)
    validity: ValidityReport = field(default_factory=lambda: ValidityReport.unvalidated("No validity metadata supplied."))

    def __post_init__(self) -> None:
        tau = np.asarray(self.tau, dtype=float)
        if tau.shape != (6,):
            raise ValueError("HydroLoadResult.tau must be a six-component vector.")
        object.__setattr__(self, "tau", tau)
        converted = {name: np.asarray(value, dtype=float) for name, value in self.components.items()}
        for name, value in converted.items():
            if value.shape != (6,):
                raise ValueError(f"Hydro load component {name!r} must be a six-component vector.")
        object.__setattr__(self, "components", converted)

    @classmethod
    def zeros(cls, note: str = "Zero-load placeholder.") -> "HydroLoadResult":
        return cls(tau=np.zeros(6), validity=ValidityReport.unvalidated(note))


@dataclass(frozen=True)
class LongitudinalHydrodynamicMatrices:
    """Frozen heave--pitch radiation matrix contract.

    Rows and columns are ordered as ``(heave, pitch)``. The solver-frequency
    convention is ``F = omega**2 A - 1j * omega B``.
    """

    solver_omega_rad_s: np.ndarray
    encounter_omega_rad_s: np.ndarray
    added_mass: np.ndarray
    radiation_damping: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)
    row_dofs: tuple[str, str] = ("heave", "pitch")
    col_dofs: tuple[str, str] = ("heave", "pitch")
    source_dof_indices: tuple[int, int] = (2, 4)
    added_mass_units: tuple[tuple[str, str], tuple[str, str]] = (
        ("kg", "kg*m"),
        ("kg*m", "kg*m^2"),
    )
    radiation_damping_units: tuple[tuple[str, str], tuple[str, str]] = (
        ("kg/s", "kg*m/s"),
        ("kg*m/s", "kg*m^2/s"),
    )

    def __post_init__(self) -> None:
        omega = np.asarray(self.solver_omega_rad_s, dtype=float)
        encounter = np.asarray(self.encounter_omega_rad_s, dtype=float)
        added = np.asarray(self.added_mass, dtype=float)
        damping = np.asarray(self.radiation_damping, dtype=float)
        if omega.ndim != 1 or omega.size == 0:
            raise ValueError("solver_omega_rad_s must be a non-empty one-dimensional array.")
        if encounter.shape != omega.shape:
            raise ValueError("encounter_omega_rad_s must have the same shape as solver_omega_rad_s.")
        expected_shape = (omega.size, 2, 2)
        if added.shape != expected_shape:
            raise ValueError(f"added_mass must have shape {expected_shape}.")
        if damping.shape != expected_shape:
            raise ValueError(f"radiation_damping must have shape {expected_shape}.")
        if not np.isfinite(omega).all() or not np.isfinite(encounter).all():
            raise ValueError("Frequency arrays must contain only finite values.")
        if not np.isfinite(added).all() or not np.isfinite(damping).all():
            raise ValueError("Hydrodynamic matrices must contain only finite values.")
        if self.row_dofs != ("heave", "pitch") or self.col_dofs != ("heave", "pitch"):
            raise ValueError("The longitudinal matrix order is frozen as (heave, pitch).")
        if self.source_dof_indices != (2, 4):
            raise ValueError("The source 6DOF indices are frozen as (2, 4).")
        object.__setattr__(self, "solver_omega_rad_s", omega)
        object.__setattr__(self, "encounter_omega_rad_s", encounter)
        object.__setattr__(self, "added_mass", added)
        object.__setattr__(self, "radiation_damping", damping)
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def complex_force_matrix(self) -> np.ndarray:
        omega = self.solver_omega_rad_s[:, None, None]
        return omega**2 * self.added_mass - 1j * omega * self.radiation_damping

    def reconstruction_relative_residual(self, reference_force: np.ndarray) -> float:
        reference = np.asarray(reference_force, dtype=complex)
        if reference.shape != self.complex_force_matrix.shape:
            raise ValueError(
                f"reference_force must have shape {self.complex_force_matrix.shape}, got {reference.shape}."
            )
        residual = self.complex_force_matrix - reference
        return float(np.linalg.norm(residual) / max(np.linalg.norm(reference), 1.0e-12))


@dataclass(frozen=True)
class FrequencyDomainHydrodynamics:
    """Frequency-domain hydrodynamic matrices and excitation.

    Matrix arrays use shape (n_omega, 6, 6); excitation uses shape
    (n_omega, 6). This keeps Ma-style station assembly, PDSTRIP diagnostics,
    database RAOs, and later Capytaine results behind one data contract.
    """

    omega: np.ndarray
    encounter_omega: np.ndarray
    added_mass: np.ndarray
    radiation_damping: np.ndarray
    excitation: np.ndarray
    restoring: np.ndarray
    contribution_breakdown: dict[str, np.ndarray] = field(default_factory=dict)
    validity: ValidityReport = field(default_factory=lambda: ValidityReport.unvalidated("No validity metadata supplied."))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        omega = np.asarray(self.omega, dtype=float)
        encounter = np.asarray(self.encounter_omega, dtype=float)
        if omega.ndim != 1:
            raise ValueError("omega must be a one-dimensional array.")
        if encounter.shape != omega.shape:
            raise ValueError("encounter_omega must have the same shape as omega.")
        n = omega.size
        for name in ("added_mass", "radiation_damping", "restoring"):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (n, 6, 6):
                raise ValueError(f"{name} must have shape (n_omega, 6, 6).")
            object.__setattr__(self, name, value)
        excitation = np.asarray(self.excitation, dtype=complex)
        if excitation.shape != (n, 6):
            raise ValueError("excitation must have shape (n_omega, 6).")
        object.__setattr__(self, "omega", omega)
        object.__setattr__(self, "encounter_omega", encounter)
        object.__setattr__(self, "excitation", excitation)

    def longitudinal_heave_pitch_matrices(self) -> LongitudinalHydrodynamicMatrices:
        """Return the frozen ``(heave, pitch)`` 2x2 radiation block."""

        indices = np.asarray((2, 4), dtype=int)
        added = self.added_mass[:, indices][:, :, indices]
        damping = self.radiation_damping[:, indices][:, :, indices]
        metadata = {
            **self.metadata,
            "matrix_contract": "heave_pitch_2x2_v1",
            "row_dofs": ("heave", "pitch"),
            "col_dofs": ("heave", "pitch"),
            "source_dof_indices": (2, 4),
            "force_harmonic_convention": "F=omega^2*A-i*omega*B",
        }
        return LongitudinalHydrodynamicMatrices(
            solver_omega_rad_s=self.omega,
            encounter_omega_rad_s=self.encounter_omega,
            added_mass=added,
            radiation_damping=damping,
            metadata=metadata,
        )

    @classmethod
    def zeros(
        cls,
        omega: np.ndarray,
        encounter_omega: np.ndarray | None = None,
        validity: ValidityReport | None = None,
    ) -> "FrequencyDomainHydrodynamics":
        omega_array = np.asarray(omega, dtype=float)
        encounter = omega_array if encounter_omega is None else np.asarray(encounter_omega, dtype=float)
        n = omega_array.size
        return cls(
            omega=omega_array,
            encounter_omega=encounter,
            added_mass=np.zeros((n, 6, 6)),
            radiation_damping=np.zeros((n, 6, 6)),
            excitation=np.zeros((n, 6), dtype=complex),
            restoring=np.zeros((n, 6, 6)),
            validity=validity or ValidityReport.unvalidated("Allocated zero frequency-domain hydrodynamics."),
        )
