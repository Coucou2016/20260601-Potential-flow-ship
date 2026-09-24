from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .types import HydroLoadResult, ValidityReport


def smoothstep(q: float, q0: float, q1: float) -> float:
    """Cubic smoothstep used for regime transitions."""

    if q1 <= q0:
        raise ValueError("smoothstep requires q1 > q0.")
    if q <= q0:
        return 0.0
    if q >= q1:
        return 1.0
    r = (q - q0) / (q1 - q0)
    return float(3.0 * r**2 - 2.0 * r**3)


@dataclass(frozen=True)
class RegimeObservables:
    fn_l: float
    fn_b: float
    buoyancy_fraction: float
    planing_lift_fraction: float
    wetted_length_over_beam: float
    transom_dry: bool = False
    chine_wetted_fraction: float = 1.0
    pressure_center_over_length: float | None = None
    dry_station_fraction: float = 0.0


@dataclass(frozen=True)
class RegimeReport:
    displacement: float
    semi_displacement: float
    planing: float
    observables: RegimeObservables
    notes: tuple[str, ...] = ()

    def as_array(self) -> np.ndarray:
        return np.asarray([self.displacement, self.semi_displacement, self.planing], dtype=float)


@dataclass(frozen=True)
class LoadOwnership:
    hydrostatic: str = "hydrostatic"
    radiation: str = "semi_displacement"
    diffraction: str = "semi_displacement"
    planing: str = "planing"
    slamming: str = "planing"
    viscous: str = "always"
    multihull: str = "always"
    hydrofoil: str = "always"

    def weight_for(self, component: str, regime: RegimeReport) -> float:
        owner = getattr(self, component, "always")
        if owner == "hydrostatic" or owner == "always":
            return 1.0
        if owner == "displacement":
            return regime.displacement
        if owner == "semi_displacement":
            return regime.semi_displacement
        if owner == "planing":
            return regime.planing
        raise ValueError(f"Unknown load ownership value {owner!r} for component {component!r}.")


class LoadArbiter:
    """Component-level displacement/semi-displacement/planing load arbiter."""

    def weights(self, observables: RegimeObservables) -> RegimeReport:
        planing_from_speed = smoothstep(observables.fn_b, 1.1, 1.8)
        planing_from_lift = smoothstep(observables.planing_lift_fraction, 0.25, 0.70)
        planing_from_transom = 1.0 if observables.transom_dry else 0.0
        planing = 0.55 * planing_from_speed + 0.35 * planing_from_lift + 0.10 * planing_from_transom
        displacement = (1.0 - smoothstep(observables.fn_l, 0.45, 0.90)) * smoothstep(
            observables.buoyancy_fraction, 0.35, 0.85
        )
        planing = float(np.clip(planing, 0.0, 1.0))
        displacement = float(np.clip(displacement, 0.0, 1.0 - planing))
        semi = max(0.0, 1.0 - displacement - planing)
        total = displacement + semi + planing
        if total <= 0.0:
            displacement, semi, planing = 0.0, 1.0, 0.0
        else:
            displacement, semi, planing = displacement / total, semi / total, planing / total
        notes = (
            "Weights are applied at load-component level; hydrodynamic matrices are not blended directly.",
        )
        return RegimeReport(displacement, semi, planing, observables, notes)

    def combine_components(
        self,
        reports: dict[str, HydroLoadResult],
        ownership: LoadOwnership,
        regime: RegimeReport,
    ) -> HydroLoadResult:
        total = np.zeros(6)
        components: dict[str, np.ndarray] = {}
        notes = list(regime.notes)
        for name, report in reports.items():
            weight = ownership.weight_for(name, regime)
            contribution = weight * report.tau
            components[name] = contribution
            total += contribution
            notes.append(f"{name}: ownership weight {weight:.3f}.")
        return HydroLoadResult(
            tau=total,
            components=components,
            validity=ValidityReport.unvalidated(
                "Combined load assembled with regime weights; final validation depends on each provider.",
                *notes,
            ),
        )
