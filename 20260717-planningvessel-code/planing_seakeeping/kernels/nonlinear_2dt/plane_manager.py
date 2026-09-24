from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionPlane:
    x_ground_m: float
    age_s: float = 0.0
    bem_started: bool = False
    inherited_from_x_m: float | None = None


@dataclass(frozen=True)
class SectionPlaneManager:
    """Ground-fixed moving-section manager for Sun-Faltinsen 2D+t simulations."""

    planes: tuple[SectionPlane, ...]
    spacing_m: float
    active_length_m: float

    @classmethod
    def initialize(cls, bow_x_m: float, length_m: float, section_count: int) -> "SectionPlaneManager":
        if section_count < 2:
            raise ValueError("section_count must be at least 2.")
        spacing = length_m / (section_count - 1)
        planes = tuple(SectionPlane(bow_x_m - index * spacing) for index in range(section_count))
        return cls(planes=planes, spacing_m=spacing, active_length_m=length_m)

    def advance(self, bow_x_m: float, dt_s: float) -> "SectionPlaneManager":
        if dt_s < 0.0:
            raise ValueError("dt_s must be non-negative.")
        stern_limit = bow_x_m - self.active_length_m
        active = [
            SectionPlane(
                x_ground_m=plane.x_ground_m,
                age_s=plane.age_s + dt_s,
                bem_started=plane.bem_started,
                inherited_from_x_m=plane.inherited_from_x_m,
            )
            for plane in self.planes
            if stern_limit - 1e-9 <= plane.x_ground_m <= bow_x_m + 1e-9
        ]
        if not active:
            active.append(SectionPlane(bow_x_m))
        while max(plane.x_ground_m for plane in active) < bow_x_m - 0.5 * self.spacing_m:
            nearest = max(active, key=lambda plane: plane.x_ground_m)
            active.append(SectionPlane(bow_x_m, inherited_from_x_m=nearest.x_ground_m))
        active = sorted(active, key=lambda plane: plane.x_ground_m, reverse=True)
        return SectionPlaneManager(tuple(active), self.spacing_m, self.active_length_m)

    def active_planes(self) -> tuple[SectionPlane, ...]:
        return self.planes
