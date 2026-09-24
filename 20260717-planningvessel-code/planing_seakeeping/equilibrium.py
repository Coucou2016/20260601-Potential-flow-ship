from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import math
from typing import Iterable

import numpy as np
from scipy import optimize

from .config import BoatConfig, EnvironmentConfig, PrescribedRunningStateConfig


@dataclass
class GeometryState:
    keel_wetted_length_m: float
    chine_wetted_length_m: float
    side_chine_wetted_length_m: float
    lambda_w: float
    x_s_m: float
    z_max_ratio: float
    transom_draft_m: float
    alpha_deg: float
    chines_dry: bool


@dataclass
class ForceState:
    surge_force_n: float
    heave_force_n: float
    pitch_moment_nm: float
    lift_coefficient: float
    center_of_pressure_m: float


@dataclass
class EquilibriumState:
    speed_mps: float
    speed_through_water_mps: float
    trim_deg: float
    trim_rad: float
    z_wl_m: float
    fn_b: float
    geometry: GeometryState
    forces: ForceState
    residual: tuple[float, float]
    converged: bool
    message: str


def speed_through_water(speed_mps: float, env: EnvironmentConfig | None) -> float:
    if env is None or env.current_speed_mps == 0:
        return speed_mps
    projection = math.cos(math.radians(env.current_heading_deg - 180.0))
    return max(0.05, speed_mps + env.current_speed_mps * projection)


def zmax_ratio(deadrise_deg: float) -> float:
    beta = deadrise_deg
    return float(np.polyval([-2.100644618790201e-6, -6.815747611588763e-5, -1.130563334939335e-3, 5.754510457848798e-1], beta))


def compute_geometry(
    boat: BoatConfig,
    speed_mps: float,
    z_wl_m: float,
    trim_rad: float,
    eta3_m: float = 0.0,
    eta5_rad: float = 0.0,
) -> GeometryState:
    b = boat.beam_m
    beta = math.radians(boat.deadrise_deg)
    tau = max(trim_rad + eta5_rad, math.radians(0.05))
    tau_deg = math.degrees(tau)
    lk = boat.lcg_m + boat.vcg_m / math.tan(tau) - (z_wl_m + eta3_m) / math.sin(tau)
    lk = max(0.0, lk)
    zm = zmax_ratio(boat.deadrise_deg)

    if boat.wetted_lengths_type == 2:
        xs = b / math.pi * math.tan(beta) / math.tan(tau)
        zm = 0.5 * b * math.tan(beta) / max(xs * tau, 1e-12) - 1.0
        lc = lk - xs
        if lc < 0:
            lc = 0.0
            xs = lk
        lambda_w = (lk + lc) / (2.0 * b)
    elif boat.wetted_lengths_type == 3:
        w = (0.57 + boat.deadrise_deg / 1000.0) * (
            math.tan(beta) / (2.0 * math.tan(tau)) - boat.deadrise_deg / 167.0
        )
        lambda_k = lk / b
        lambda_c = (lambda_k - w) - 0.2 * math.exp(-(lambda_k - w) / 0.3)
        lc = max(0.0, lambda_c * b)
        xs = max(0.0, lk - lc)
        if xs > 0:
            zm = 0.5 * b * math.tan(beta) / max(xs * tau, 1e-12) - 1.0
        lambda_w = (lambda_k + max(lambda_c, 0.0)) / 2.0 + 0.03
    else:
        xs = 0.5 * b * math.tan(beta) / max((1.0 + zm) * tau, 1e-12)
        lc = lk - xs
        if lc < 0:
            lc = 0.0
            xs = lk
        lambda_w = (lk + lc) / (2.0 * b)

    lambda_w = max(lambda_w, 1e-6)
    alpha = math.degrees(math.atan2(b, 2.0 * max(xs, 1e-12)))
    fn_b = speed_mps / math.sqrt(boat.gravity_m_s2 * b)
    dry_metric = fn_b**2 - (lambda_w - 0.16 * math.tan(beta) / max(math.tan(tau), 1e-12)) / (
        3.0 * max(math.sin(tau), 1e-12)
    )
    if dry_metric >= 0:
        lc2 = 0.0
        chines_dry = True
    else:
        lc2 = max(0.0, lc - 3.0 * speed_mps**2 * math.sin(tau) / boat.gravity_m_s2)
        chines_dry = False
    return GeometryState(
        keel_wetted_length_m=lk,
        chine_wetted_length_m=lc,
        side_chine_wetted_length_m=lc2,
        lambda_w=lambda_w,
        x_s_m=xs,
        z_max_ratio=zm,
        transom_draft_m=lk * math.sin(tau),
        alpha_deg=alpha,
        chines_dry=chines_dry,
    )


def planing_force(
    boat: BoatConfig,
    speed_mps: float,
    geometry: GeometryState,
    trim_rad: float,
    eta5_rad: float = 0.0,
) -> ForceState:
    b = boat.beam_m
    tau = max(trim_rad + eta5_rad, math.radians(0.05))
    tau_deg = math.degrees(tau)
    fn_b = speed_mps / math.sqrt(boat.gravity_m_s2 * b)
    lam = max(geometry.lambda_w, 1e-6)
    cl0 = tau_deg**1.1 * (0.012 * math.sqrt(lam) + 0.0055 * lam**2.5 / max(fn_b**2, 1e-12))
    clb = max(0.0, cl0 - 0.0065 * boat.deadrise_deg * cl0**0.6)
    fz = clb * 0.5 * boat.rho_water_kg_m3 * speed_mps**2 * b**2
    fx = fz * math.tan(tau)
    fn = fz / max(math.cos(tau), 1e-12)
    lcp = lam * b * (0.75 - 1.0 / (5.21 * (fn_b / lam) ** 2 + 2.39))
    moment = -fn * (boat.lcg_m - lcp)
    return ForceState(fx, fz, moment, clb, lcp)


def generalized_calm_force(
    boat: BoatConfig,
    speed_mps: float,
    z_wl_m: float,
    trim_rad: float,
    eta3_m: float = 0.0,
    eta5_rad: float = 0.0,
) -> tuple[np.ndarray, GeometryState, ForceState]:
    geom = compute_geometry(boat, speed_mps, z_wl_m, trim_rad, eta3_m, eta5_rad)
    force = planing_force(boat, speed_mps, geom, trim_rad, eta5_rad)
    weight = boat.mass_kg * boat.gravity_m_s2
    net = np.array([force.heave_force_n - weight, force.pitch_moment_nm], dtype=float)
    return net, geom, force


def boat_with_prescribed_ratios(boat: BoatConfig, state: PrescribedRunningStateConfig) -> BoatConfig:
    b = boat.beam_m
    values = {}
    if state.mass_over_rho_b3 is not None:
        values["mass_kg"] = state.mass_over_rho_b3 * boat.rho_water_kg_m3 * b**3
    if state.lcg_over_b is not None:
        values["lcg_m"] = state.lcg_over_b * b
    if state.vcg_over_b is not None:
        values["vcg_m"] = state.vcg_over_b * b
    if state.r55_over_b is not None:
        values["pitch_radius_gyration_m"] = state.r55_over_b * b
    if state.lambda_w is not None:
        values["wetted_lengths_type"] = 1
    return replace(boat, **values) if values else boat


def z_wl_for_lambda_w(boat: BoatConfig, lambda_w: float, trim_rad: float) -> float:
    b = boat.beam_m
    zm = zmax_ratio(boat.deadrise_deg)
    xs = 0.5 * b * math.tan(math.radians(boat.deadrise_deg)) / max((1.0 + zm) * trim_rad, 1e-12)
    keel_wetted_length = lambda_w * b + 0.5 * xs
    return math.sin(trim_rad) * (boat.lcg_m + boat.vcg_m / math.tan(trim_rad) - keel_wetted_length)


def make_prescribed_equilibrium(
    boat: BoatConfig,
    speed_mps: float,
    state: PrescribedRunningStateConfig,
    env: EnvironmentConfig | None = None,
) -> EquilibriumState:
    state.validate()
    speed_water = speed_through_water(speed_mps, env)
    trim_deg = float(state.trim_deg)
    trim_rad = math.radians(trim_deg)
    z_wl = float(state.z_wl_m) if state.z_wl_m is not None else z_wl_for_lambda_w(boat, float(state.lambda_w), trim_rad)
    geom = compute_geometry(boat, speed_water, z_wl, trim_rad)
    force = planing_force(boat, speed_water, geom, trim_rad)
    net, _, _ = generalized_calm_force(boat, speed_water, z_wl, trim_rad)
    weight = boat.mass_kg * boat.gravity_m_s2
    scale = np.array([weight, max(weight * boat.beam_m, 1.0)])
    residual = net / scale
    return EquilibriumState(
        speed_mps=speed_mps,
        speed_through_water_mps=speed_water,
        trim_deg=trim_deg,
        trim_rad=trim_rad,
        z_wl_m=z_wl,
        fn_b=speed_water / math.sqrt(boat.gravity_m_s2 * boat.beam_m),
        geometry=geom,
        forces=force,
        residual=(float(residual[0]), float(residual[1])),
        converged=bool(np.linalg.norm(residual) < 5e-4),
        message="Prescribed running state; residual reports consistency with the current calm-water force model.",
    )


def solve_equilibrium(
    boat: BoatConfig,
    speed_mps: float,
    env: EnvironmentConfig | None = None,
    seeds: Iterable[tuple[float, float]] | None = None,
) -> EquilibriumState:
    speed_water = speed_through_water(speed_mps, env)
    weight = boat.mass_kg * boat.gravity_m_s2
    scale = np.array([weight, max(weight * boat.beam_m, 1.0)])

    def residual(x: np.ndarray) -> np.ndarray:
        z_wl, trim_deg = float(x[0]), float(x[1])
        net, _, _ = generalized_calm_force(boat, speed_water, z_wl, math.radians(trim_deg))
        return net / scale

    lo_trim, hi_trim = boat.trim_bounds_deg
    if seeds is None:
        seeds = [
            (boat.initial_z_wl_m, boat.initial_trim_deg),
            (0.0, 3.0),
            (0.0, 5.0),
            (0.2 * boat.beam_m, 4.0),
            (-0.2 * boat.beam_m, 6.0),
        ]
    best = None
    for seed in seeds:
        try:
            res = optimize.least_squares(
                residual,
                x0=np.array(seed, dtype=float),
                bounds=([-5.0 * boat.beam_m, lo_trim], [5.0 * boat.beam_m, hi_trim]),
                xtol=1e-11,
                ftol=1e-11,
                gtol=1e-11,
                max_nfev=250,
            )
        except Exception as exc:  # pragma: no cover - defensive path
            if best is None:
                best = (np.inf, seed, False, str(exc))
            continue
        norm = float(np.linalg.norm(res.fun))
        if best is None or norm < best[0]:
            best = (norm, res.x, bool(res.success), res.message)
    if best is None:
        raise RuntimeError("Equilibrium search failed before any iterate was evaluated.")

    _, x, ok, message = best
    z_wl, trim_deg = float(x[0]), float(x[1])
    net, geom, force = generalized_calm_force(boat, speed_water, z_wl, math.radians(trim_deg))
    return EquilibriumState(
        speed_mps=speed_mps,
        speed_through_water_mps=speed_water,
        trim_deg=trim_deg,
        trim_rad=math.radians(trim_deg),
        z_wl_m=z_wl,
        fn_b=speed_water / math.sqrt(boat.gravity_m_s2 * boat.beam_m),
        geometry=geom,
        forces=force,
        residual=(float(net[0] / scale[0]), float(net[1] / scale[1])),
        converged=ok and np.linalg.norm(net / scale) < 5e-4,
        message=str(message),
    )
