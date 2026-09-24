from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ComponentLoad:
    name: str
    force_n: np.ndarray
    moment_nm: np.ndarray
    origin_from_vessel_ap_m: tuple[float, float, float]

    def __post_init__(self) -> None:
        force = np.asarray(self.force_n, dtype=float)
        moment = np.asarray(self.moment_nm, dtype=float)
        if force.shape != (3,) or moment.shape != (3,):
            raise ValueError("ComponentLoad force and moment must be three-component vectors.")
        object.__setattr__(self, "force_n", force)
        object.__setattr__(self, "moment_nm", moment)


def assemble_component_loads(loads: tuple[ComponentLoad, ...], cog_from_ap_m: tuple[float, float, float]) -> np.ndarray:
    """Assemble component forces/moments into vessel generalized load."""

    cog = np.asarray(cog_from_ap_m, dtype=float)
    total_force = np.zeros(3)
    total_moment = np.zeros(3)
    for load in loads:
        arm = np.asarray(load.origin_from_vessel_ap_m, dtype=float) - cog
        total_force += load.force_n
        total_moment += load.moment_nm + np.cross(arm, load.force_n)
    return np.r_[total_force, total_moment]


def coupling_completeness_report(
    *,
    include_cross_radiation: bool,
    include_cross_diffraction: bool,
    include_wetdeck_impact: bool,
    include_connector_loads: bool,
) -> dict[str, object]:
    missing = []
    if not include_cross_radiation:
        missing.append("cross_radiation")
    if not include_cross_diffraction:
        missing.append("cross_diffraction")
    if not include_wetdeck_impact:
        missing.append("wetdeck_impact")
    if not include_connector_loads:
        missing.append("connector_loads")
    return {
        "production_ready": len(missing) == 0,
        "missing_terms": tuple(missing),
        "note": "Independent-hull summation is only a lower-bound diagnostic when any coupling term is missing.",
    }
