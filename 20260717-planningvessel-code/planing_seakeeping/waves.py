from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .config import WaveConfig


@dataclass
class WaveComponents:
    omega0: np.ndarray
    omega_e: np.ndarray
    wavenumber: np.ndarray
    amplitude: np.ndarray
    phase: np.ndarray


def encounter_frequency(omega0: np.ndarray | float, speed_mps: float, heading_deg: float, g: float) -> np.ndarray | float:
    k = np.asarray(omega0) ** 2 / g
    mu = math.radians(heading_deg)
    return np.asarray(omega0) - k * speed_mps * math.cos(mu)


def wavenumber_deep(omega0: np.ndarray | float, g: float) -> np.ndarray | float:
    return np.asarray(omega0) ** 2 / g


def regular_periods(waves: WaveConfig) -> np.ndarray:
    return np.linspace(waves.period_min_s, waves.period_max_s, waves.period_count)


def spectrum_density(omega: np.ndarray, waves: WaveConfig, g: float) -> np.ndarray:
    omega = np.maximum(np.asarray(omega, dtype=float), 1e-6)
    hs = waves.significant_height_m
    wp = 2.0 * math.pi / waves.peak_period_s
    pm = 5.0 / 16.0 * hs**2 * wp**4 * omega**-5 * np.exp(-1.25 * (wp / omega) ** 4)
    if waves.spectrum.lower() == "pm":
        return pm
    sigma = np.where(omega <= wp, 0.07, 0.09)
    gamma_term = waves.gamma ** np.exp(-((omega / wp - 1.0) ** 2) / (2.0 * sigma**2))
    jonswap = pm * gamma_term
    # Renormalize numerically to preserve Hs approximately over the discretized band.
    return jonswap


def make_irregular_components(waves: WaveConfig, speed_mps: float, g: float) -> WaveComponents:
    omega_min = 2.0 * math.pi / max(waves.period_max_s, 1e-6)
    omega_max = 2.0 * math.pi / max(waves.period_min_s, 1e-6)
    omega = np.linspace(omega_min, omega_max, waves.component_count)
    dw = omega[1] - omega[0] if len(omega) > 1 else omega[0]
    s = spectrum_density(omega, waves, g)
    amp = np.sqrt(2.0 * s * dw)
    m0 = float(np.sum(s * dw))
    if m0 > 0:
        amp *= waves.significant_height_m / (4.0 * math.sqrt(m0))
    rng = np.random.default_rng(waves.seed)
    phase = rng.uniform(0.0, 2.0 * math.pi, size=omega.shape)
    return WaveComponents(
        omega0=omega,
        omega_e=np.asarray(encounter_frequency(omega, speed_mps, waves.heading_deg, g), dtype=float),
        wavenumber=np.asarray(wavenumber_deep(omega, g), dtype=float),
        amplitude=amp,
        phase=phase,
    )
