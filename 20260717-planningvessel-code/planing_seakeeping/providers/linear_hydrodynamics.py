from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from ..schema import Linear2p5DProviderConfig
from ..station_2p5d import RigidBody6DOF, StationHull, assemble_forward_speed_2p5d_matrices
from ..types import FrequencyDomainHydrodynamics, ModelCapabilities, ValidityReport


LinearHydroSource = Literal["capytaine", "pdstrip", "linear_2p5d", "database", "legacy_station_prototype"]


@dataclass(frozen=True)
class LinearFrequencyProvider:
    """Unified frequency-domain hydrodynamics wrapper.

    The current `linear_2p5d` source routes through the existing station-based
    matched BIE sweep when `config.formulation == "matched_bie"`. The legacy
    station prototype remains available by selecting `legacy_station_prototype`.
    Both in-package paths remain explicitly unvalidated until the Ma 2005 gates
    pass.
    """

    source: LinearHydroSource = "linear_2p5d"
    production: bool = False
    rho_water_kg_m3: float = 1025.0
    gravity_m_s2: float = 9.80665
    config: Linear2p5DProviderConfig = field(default_factory=Linear2p5DProviderConfig)
    matched_options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.config.validate()
        if self.source not in {"linear_2p5d", "legacy_station_prototype"}:
            raise NotImplementedError(
                f"No verified adapter is implemented for source={self.source!r}; "
                "external backend names cannot select the local station prototype."
            )
        if (self.production or self.config.production) and self.source in {"linear_2p5d", "legacy_station_prototype"}:
            raise ValueError(
                "In-package linear 2.5D providers are not production-ready until the Ma 2005 gates pass."
            )

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            frequency_domain=True,
            six_dof=True,
            production=self.production and self.source in {"capytaine", "pdstrip", "database"},
            validated_benchmarks=(),
            status=(
                "validated_database_or_external_source"
                if self.production and self.source in {"capytaine", "pdstrip", "database"}
                else "linear_frequency_wrapper_not_validated"
            ),
            assumptions=(
                "Small-amplitude frequency-domain response.",
                "Provider source must carry its own benchmark provenance.",
            ),
        )

    def solve_station_hull(
        self,
        hull: StationHull,
        body: RigidBody6DOF,
        omega_rad_s: np.ndarray,
        speed_mps: float = 0.0,
    ) -> FrequencyDomainHydrodynamics:
        if self.source == "linear_2p5d" and self.config.formulation == "matched_bie":
            if speed_mps <= 0.0:
                raise ValueError("matched_bie linear 2.5D provider requires positive speed_mps.")
            from ..kernels.linear_2p5d.formulation import assemble_frequency_domain_from_matched_station_hull

            hydro = assemble_frequency_domain_from_matched_station_hull(
                hull,
                body,
                np.asarray(omega_rad_s, dtype=float),
                speed_mps,
                config=self.config,
                rho_water_kg_m3=self.rho_water_kg_m3,
                gravity_m_s2=self.gravity_m_s2,
                **self.matched_options,
            )
            return FrequencyDomainHydrodynamics(
                omega=hydro.omega,
                encounter_omega=hydro.encounter_omega,
                added_mass=hydro.added_mass,
                radiation_damping=hydro.radiation_damping,
                excitation=hydro.excitation,
                restoring=hydro.restoring,
                contribution_breakdown=hydro.contribution_breakdown,
                validity=ValidityReport(
                    status=hydro.validity.status,
                    model_assumptions=hydro.validity.model_assumptions,
                    violated_assumptions=hydro.validity.violated_assumptions,
                    extrapolation_distance=hydro.validity.extrapolation_distance,
                    reference_cases=hydro.validity.reference_cases,
                    notes=hydro.validity.notes
                    + (
                        "Routed through LinearFrequencyProvider(source='linear_2p5d', formulation='matched_bie').",
                    ),
                ),
                metadata={
                    **hydro.metadata,
                    "source": self.source,
                    "provider_formulation": self.config.formulation,
                    "provider_route": "matched_bie_station_sweep",
                },
            )
        if self.source == "linear_2p5d" and self.config.formulation == "transient_source":
            raise NotImplementedError(
                "linear_2p5d formulation='transient_source' is reserved for a future direct source formulation."
            )
        omega = np.asarray(omega_rad_s, dtype=float)
        added = np.zeros((omega.size, 6, 6))
        damping = np.zeros_like(added)
        restoring = np.zeros_like(added)
        excitation = np.zeros((omega.size, 6), dtype=complex)
        for index, omega_i in enumerate(omega):
            matrices = assemble_forward_speed_2p5d_matrices(
                hull,
                rho_water_kg_m3=self.rho_water_kg_m3,
                gravity_m_s2=self.gravity_m_s2,
                omega_rad_s=float(omega_i),
                speed_mps=speed_mps,
            )
            added[index] = matrices.added_mass
            damping[index] = matrices.damping
            restoring[index] = matrices.restoring
        return FrequencyDomainHydrodynamics(
            omega=omega,
            encounter_omega=omega,
            added_mass=added,
            radiation_damping=damping,
            excitation=excitation,
            restoring=restoring,
            validity=ValidityReport.unvalidated(
                "Frequency wrapper is active, but the routed station forward-speed assembly has not passed Ma 2005.",
                reference_cases=("ma2005_wigley_iii", "ma2005_sl7"),
            ),
            metadata={
                "source": self.source,
                "body_mass_kg": body.mass_kg,
                "speed_mps": speed_mps,
                "provider_formulation": self.config.formulation,
                "provider_route": "legacy_station_forward_speed_assembly",
            },
        )


def build_legacy_2p5d_provider() -> LinearFrequencyProvider:
    return LinearFrequencyProvider(
        source="legacy_station_prototype",
        production=False,
        config=Linear2p5DProviderConfig(formulation="legacy_station_prototype"),
    )
