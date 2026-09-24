from __future__ import annotations

from dataclasses import dataclass

from ..types import HydroLoadResult, ModelCapabilities


@dataclass(frozen=True)
class MultihullInteractionPlaceholderProvider:
    production: bool = False

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            six_dof=True,
            multihull_interaction=False,
            production=False,
            status="multihull_placeholder_zero_load",
            assumptions=("No cross-radiation, cross-diffraction, wet-deck impact, or connector loads are computed.",),
        )

    def load(self) -> HydroLoadResult:
        if self.production:
            self.capabilities.require_production_ready()
        return HydroLoadResult.zeros("Multihull placeholder returns zero interaction load.")


@dataclass(frozen=True)
class HydrofoilPlaceholderProvider:
    production: bool = False

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            six_dof=True,
            hydrofoil_control=False,
            production=False,
            status="hydrofoil_placeholder_zero_load",
            assumptions=("No foil lift, actuator, free-surface, ventilation, or cavitation model is computed.",),
        )

    def load(self) -> HydroLoadResult:
        if self.production:
            self.capabilities.require_production_ready()
        return HydroLoadResult.zeros("Hydrofoil placeholder returns zero foil load.")
