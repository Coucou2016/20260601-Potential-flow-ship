from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


HullRole = Literal["main_hull", "port_demihull", "starboard_demihull", "port_outrigger", "starboard_outrigger"]
PlatformType = Literal["monohull", "catamaran", "trimaran", "hydrofoil"]


@dataclass(frozen=True)
class Linear2p5DProviderConfig:
    enabled: bool = False
    production: bool = False
    formulation: Literal["matched_bie", "transient_source", "legacy_station_prototype"] = "matched_bie"
    hull_stations: int = 41
    body_panels_per_section: int = 48
    free_surface_inner_panels: int = 64
    free_surface_outer_panels: int = 160
    # Ma et al. (2005), Section 3.3 recommends a control radius of three beams.
    control_surface_radius_beams: float = 3.0
    history_storage: Literal["full", "compressed", "state_space"] = "full"
    include_steady_perturbation: bool = True
    include_end_terms: bool = True

    def validate(self) -> None:
        if self.hull_stations < 3:
            raise ValueError("linear_2p5d.hull_stations must be at least 3.")
        if self.body_panels_per_section < 8:
            raise ValueError("linear_2p5d.body_panels_per_section must be at least 8.")
        if self.control_surface_radius_beams <= 1.0:
            raise ValueError("linear_2p5d.control_surface_radius_beams must be greater than one beam.")
        if self.production and self.formulation == "legacy_station_prototype":
            raise ValueError("legacy_station_prototype cannot be selected with production=true.")


@dataclass(frozen=True)
class Nonlinear2DtProviderConfig:
    enabled: bool = False
    production: bool = False
    section_planes: int = 60
    time_step_s: float = 0.001
    body_panels: int = 64
    free_surface_panels_near: int = 80
    free_surface_panels_far: int = 160
    initializer: Literal["wagner", "von_karman", "similarity"] = "wagner"
    jet_cut_ratio: float = 0.02
    spray_cut_enabled: bool = True
    chine_separation_enabled: bool = True
    curved_separation_enabled: bool = False
    damping_beach_length_beams: float = 8.0
    transom_correction_model: str = "sun_faltinsen_empirical"
    coupling_iterations: int = 2

    def validate(self) -> None:
        if self.section_planes < 3:
            raise ValueError("nonlinear_2dt.section_planes must be at least 3.")
        if self.time_step_s <= 0.0:
            raise ValueError("nonlinear_2dt.time_step_s must be positive.")
        if not 0.0 <= self.jet_cut_ratio <= 0.2:
            raise ValueError("nonlinear_2dt.jet_cut_ratio must lie in [0, 0.2].")
        if self.production:
            raise ValueError("NonlinearBEM2DtProvider is not production-ready until Sun-Faltinsen benchmarks pass.")


@dataclass(frozen=True)
class MultihullInteractionProviderConfig:
    enabled: bool = False
    production: bool = False
    model: Literal["independent_hulls", "coupled_section_bie", "external_3d_bem"] = "independent_hulls"
    include_cross_radiation: bool = False
    include_cross_diffraction: bool = False
    include_wetdeck_impact: bool = False
    include_connector_loads: bool = False

    def validate(self) -> None:
        if self.production and self.model == "independent_hulls":
            raise ValueError("independent_hulls cannot be used as a production multihull interaction model.")
        if self.model == "independent_hulls" and (self.include_cross_radiation or self.include_cross_diffraction):
            raise ValueError("Cross radiation/diffraction requires coupled_section_bie or external_3d_bem.")


@dataclass(frozen=True)
class HydrofoilProviderConfig:
    enabled: bool = False
    production: bool = False
    model: Literal["placeholder", "linear_finite_wing", "controlled_linear_finite_wing"] = "placeholder"
    include_actuator_dynamics: bool = True
    include_control_delay: bool = True

    def validate(self) -> None:
        if self.production and self.model == "placeholder":
            raise ValueError("Hydrofoil placeholder cannot be used with production=true.")


@dataclass(frozen=True)
class HullComponentConfig:
    name: str
    role: HullRole = "main_hull"
    stations_file: str | None = None
    origin_from_vessel_ap_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    geometry_source: str = "unspecified"


@dataclass(frozen=True)
class LiftingSurfaceConfig:
    name: str
    type: str = "t_foil"
    reference_point_body_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    span_m: float = 0.0
    chord_m: float = 0.0
    area_m2: float = 0.0
    aspect_ratio: float = 0.0
    flap_ratio: float = 0.0
    control_channel: str | None = None
    model: str = "placeholder"

    def validate(self) -> None:
        if self.area_m2 < 0.0 or self.span_m < 0.0 or self.chord_m < 0.0:
            raise ValueError(f"Lifting surface {self.name!r} has negative dimensions.")
        if self.model != "placeholder" and (self.area_m2 <= 0.0 or self.aspect_ratio <= 0.0):
            raise ValueError(f"Lifting surface {self.name!r} needs positive area and aspect ratio.")


@dataclass(frozen=True)
class VesselConfig:
    name: str
    platform_type: PlatformType = "monohull"
    mass_kg: float = 0.0
    cog_from_ap_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    radii_of_gyration_m: tuple[float, float, float] | None = None
    hull_components: tuple[HullComponentConfig, ...] = ()
    lifting_surfaces: tuple[LiftingSurfaceConfig, ...] = ()

    def validate(self) -> None:
        if self.mass_kg < 0.0:
            raise ValueError("vessel.mass_kg must be non-negative.")
        names = [component.name for component in self.hull_components]
        if len(names) != len(set(names)):
            raise ValueError("Hull component names must be unique.")
        roles = {component.role for component in self.hull_components}
        if self.platform_type == "catamaran" and not {"port_demihull", "starboard_demihull"} <= roles:
            raise ValueError("Catamaran configurations require port_demihull and starboard_demihull components.")
        if self.platform_type == "trimaran" and not {
            "main_hull",
            "port_outrigger",
            "starboard_outrigger",
        } <= roles:
            raise ValueError("Trimaran configurations require main_hull, port_outrigger, and starboard_outrigger.")
        for surface in self.lifting_surfaces:
            surface.validate()


@dataclass(frozen=True)
class ProviderSuiteConfig:
    linear_2p5d: Linear2p5DProviderConfig = field(default_factory=Linear2p5DProviderConfig)
    nonlinear_2dt: Nonlinear2DtProviderConfig = field(default_factory=Nonlinear2DtProviderConfig)
    multihull: MultihullInteractionProviderConfig = field(default_factory=MultihullInteractionProviderConfig)
    hydrofoil: HydrofoilProviderConfig = field(default_factory=HydrofoilProviderConfig)

    def validate(self) -> None:
        self.linear_2p5d.validate()
        self.nonlinear_2dt.validate()
        self.multihull.validate()
        self.hydrofoil.validate()
