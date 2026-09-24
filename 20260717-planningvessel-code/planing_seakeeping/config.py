from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any

import yaml


@dataclass
class BoatConfig:
    length_m: float
    beam_m: float
    deadrise_deg: float
    mass_kg: float
    lcg_m: float
    vcg_m: float
    pitch_radius_gyration_m: float
    rho_water_kg_m3: float = 1025.0
    nu_water_m2_s: float = 1.19e-6
    gravity_m_s2: float = 9.80665
    wetted_lengths_type: int = 1
    initial_trim_deg: float = 4.0
    initial_z_wl_m: float = 0.0
    trim_bounds_deg: tuple[float, float] = (0.5, 18.0)


@dataclass
class WaveConfig:
    heading_deg: float = 180.0
    regular_height_m: float = 0.5
    regular_period_s: float = 4.0
    period_min_s: float = 2.0
    period_max_s: float = 8.0
    period_count: int = 80
    spectrum: str = "jonswap"
    significant_height_m: float = 0.6
    peak_period_s: float = 4.0
    gamma: float = 3.3
    component_count: int = 80
    seed: int = 20260717


@dataclass
class EnvironmentConfig:
    # Positive head current increases speed through water; heading 180 deg means head current.
    current_speed_mps: float = 0.0
    current_heading_deg: float = 180.0
    wind_speed_mps: float = 0.0
    wind_heading_deg: float = 180.0


@dataclass
class SimulationConfig:
    speeds_mps: list[float] = field(default_factory=list)
    speeds_fn_b: list[float] = field(default_factory=list)
    time_step_s: float = 0.02
    duration_s: float = 80.0
    discard_initial_s: float = 20.0
    bow_x_from_cg_m: float | None = None
    use_irregular_wave: bool = True
    allow_linear_fallback: bool = False


@dataclass
class PrescribedRunningStateConfig:
    enabled: bool = False
    trim_deg: float | None = None
    lambda_w: float | None = None
    fn_b: float | None = None
    mass_over_rho_b3: float | None = None
    lcg_over_b: float | None = None
    vcg_over_b: float | None = None
    r55_over_b: float | None = None
    z_wl_m: float | None = None

    def validate(self) -> None:
        if not self.enabled:
            return
        if self.trim_deg is None:
            raise ValueError("prescribed_running_state.trim_deg is required when enabled.")
        if self.lambda_w is None and self.z_wl_m is None:
            raise ValueError("prescribed_running_state.lambda_w or z_wl_m is required when enabled.")
        if self.lambda_w is not None and self.lambda_w <= 0.0:
            raise ValueError("prescribed_running_state.lambda_w must be positive.")
        if self.fn_b is not None and self.fn_b <= 0.0:
            raise ValueError("prescribed_running_state.fn_b must be positive.")


@dataclass
class RunConfig:
    boat: BoatConfig
    waves: WaveConfig = field(default_factory=WaveConfig)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    prescribed_running_state: PrescribedRunningStateConfig = field(default_factory=PrescribedRunningStateConfig)

    def speeds(self) -> list[float]:
        speeds = list(self.simulation.speeds_mps)
        if self.simulation.speeds_fn_b:
            scale = (self.boat.gravity_m_s2 * self.boat.beam_m) ** 0.5
            speeds.extend(fn * scale for fn in self.simulation.speeds_fn_b)
        if not speeds and self.prescribed_running_state.enabled and self.prescribed_running_state.fn_b is not None:
            scale = (self.boat.gravity_m_s2 * self.boat.beam_m) ** 0.5
            speeds.append(self.prescribed_running_state.fn_b * scale)
        if not speeds:
            raise ValueError(
                "No speeds configured. Provide simulation.speeds_mps, speeds_fn_b, "
                "or prescribed_running_state.fn_b."
            )
        return speeds

    def bow_x_from_cg(self) -> float:
        if self.simulation.bow_x_from_cg_m is not None:
            return self.simulation.bow_x_from_cg_m
        # Coordinate convention follows Faltinsen Ch. 9: x positive aft from COG.
        return -(self.boat.length_m - self.boat.lcg_m)


def _tuple2(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if value is None:
        return default
    if len(value) != 2:
        raise ValueError("Expected a two-value sequence.")
    return float(value[0]), float(value[1])


def _boat(data: dict[str, Any]) -> BoatConfig:
    defaults = BoatConfig(
        length_m=1.0,
        beam_m=1.0,
        deadrise_deg=20.0,
        mass_kg=1.0,
        lcg_m=1.0,
        vcg_m=0.2,
        pitch_radius_gyration_m=1.0,
    )
    merged = {**defaults.__dict__, **data}
    merged["trim_bounds_deg"] = _tuple2(merged.get("trim_bounds_deg"), defaults.trim_bounds_deg)
    return BoatConfig(**merged)


def _waves(data: dict[str, Any]) -> WaveConfig:
    return WaveConfig(**{**WaveConfig().__dict__, **data})


def _environment(data: dict[str, Any]) -> EnvironmentConfig:
    return EnvironmentConfig(**{**EnvironmentConfig().__dict__, **data})


def _simulation(data: dict[str, Any]) -> SimulationConfig:
    return SimulationConfig(**{**SimulationConfig().__dict__, **data})


def _prescribed_running_state(data: dict[str, Any]) -> PrescribedRunningStateConfig:
    state = PrescribedRunningStateConfig(**{**PrescribedRunningStateConfig().__dict__, **data})
    state.validate()
    return state


def load_config(path: str | Path) -> RunConfig:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        raw = json.loads(text)
    else:
        raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError(f"{path} did not contain a mapping.")
    return RunConfig(
        boat=_boat(raw.get("boat", {})),
        waves=_waves(raw.get("waves", {})),
        environment=_environment(raw.get("environment", {})),
        simulation=_simulation(raw.get("simulation", {})),
        prescribed_running_state=_prescribed_running_state(raw.get("prescribed_running_state", {})),
    )
