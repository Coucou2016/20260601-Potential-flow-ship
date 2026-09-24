from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

from .coefficients import HydroMatrices, compute_hydro_matrices
from .config import BoatConfig, RunConfig, WaveConfig
from .equilibrium import (
    EquilibriumState,
    boat_with_prescribed_ratios,
    generalized_calm_force,
    make_prescribed_equilibrium,
    solve_equilibrium,
)
from .sixdof import make_sixdof_timeseries, rms_after
from .waves import WaveComponents, encounter_frequency, make_irregular_components, regular_periods, wavenumber_deep


@dataclass
class SpeedResult:
    equilibrium: EquilibriumState
    matrices: HydroMatrices
    rao: pd.DataFrame
    regular_timeseries: pd.DataFrame
    irregular_timeseries: pd.DataFrame | None
    summary: dict[str, float | str | bool]


def _bow_x_from_cg(config: RunConfig, boat: BoatConfig) -> float:
    if config.simulation.bow_x_from_cg_m is not None:
        return config.simulation.bow_x_from_cg_m
    return -(boat.length_m - boat.lcg_m)


def _resolve_boat_and_equilibrium(config: RunConfig, speed_mps: float) -> tuple[BoatConfig, EquilibriumState, str]:
    if config.prescribed_running_state.enabled:
        boat = boat_with_prescribed_ratios(config.boat, config.prescribed_running_state)
        eq = make_prescribed_equilibrium(boat, speed_mps, config.prescribed_running_state, config.environment)
        return boat, eq, "prescribed_running_state"
    boat = config.boat
    return boat, solve_equilibrium(boat, speed_mps, config.environment), "solved_savitsky_equilibrium"


def _response_diagnostics(df: pd.DataFrame, eq: EquilibriumState, g: float, prefix: str) -> dict[str, float | str | bool]:
    finite = bool(np.isfinite(df.select_dtypes(include=[np.number]).to_numpy()).all())
    heave_accel_g = float(df["heave_accel_mps2"].abs().max() / g)
    bow_accel_g = float(df["bow_vertical_accel_mps2"].abs().max() / g)
    transom_draft = max(eq.geometry.transom_draft_m, 1e-9)
    rel_motion = (df["heave_m"] - df["wave_elevation_m"]).abs()
    rel_motion_over_draft = float(rel_motion.max() / transom_draft)
    impact_accel_risk = bool(bow_accel_g > 3.0 or heave_accel_g > 3.0)
    dryout_risk = bool(rel_motion_over_draft > 1.2)
    jump_risk = dryout_risk
    if not finite:
        note = "model_failure_nonfinite_response"
    elif dryout_risk:
        note = "possible_jump_or_wetted_surface_loss_check_against_nonlinear_experiment"
    elif impact_accel_risk:
        note = "outside_linear_2p5d_comfort_zone_check_against_nonlinear_experiment"
    else:
        note = "no_jump_or_dryout_flag_from_simple_time_domain_diagnostics"
    return {
        f"{prefix}_finite_response": finite,
        f"{prefix}_max_cg_vertical_accel_g": heave_accel_g,
        f"{prefix}_max_bow_vertical_accel_g": bow_accel_g,
        f"{prefix}_max_relative_heave_over_transom_draft": rel_motion_over_draft,
        f"{prefix}_impact_accel_risk_flag": impact_accel_risk,
        f"{prefix}_jump_risk_flag": jump_risk,
        f"{prefix}_dryout_risk_flag": dryout_risk,
        f"{prefix}_model_limit_note": note,
    }


def wave_excitation_coefficients(
    boat: BoatConfig,
    eq: EquilibriumState,
    matrices: HydroMatrices,
    omega0: float,
    omega_e: float,
    k: float,
) -> np.ndarray:
    a = matrices.added_mass
    b = matrices.damping
    c = matrices.restoring
    u = eq.speed_through_water_mps
    b33d = b[0, 0]
    b53d = b[1, 0]
    b35d = b[0, 1] + u * a[0, 0]
    b55d = b[1, 1] + u * a[0, 1]
    f3s = c[0, 0] - a[0, 0] * omega0 * omega_e - b35d * omega0 * k
    f3c = c[0, 1] * k - a[0, 1] * omega0 * omega_e * k + b33d * omega0
    f5s = c[1, 0] - a[1, 0] * omega0 * omega_e - b55d * omega0 * k
    f5c = c[1, 1] * k - a[1, 1] * omega0 * omega_e * k + b53d * omega0
    return np.array([[f3s, f3c], [f5s, f5c]], dtype=float)


def solve_rao(
    boat: BoatConfig,
    waves: WaveConfig,
    eq: EquilibriumState,
    matrices: HydroMatrices,
    bow_x_from_cg_m: float,
) -> pd.DataFrame:
    rows = []
    for period in regular_periods(waves):
        omega0 = 2.0 * math.pi / period
        k = float(wavenumber_deep(omega0, boat.gravity_m_s2))
        omega_e = float(encounter_frequency(omega0, eq.speed_through_water_mps, waves.heading_deg, boat.gravity_m_s2))
        f = wave_excitation_coefficients(boat, eq, matrices, omega0, omega_e, k)
        rhs_per_m = np.array([f[0, 1] - 1j * f[0, 0], f[1, 1] - 1j * f[1, 0]], dtype=complex)
        dyn = -omega_e**2 * matrices.total_mass + 1j * omega_e * matrices.damping + matrices.restoring
        try:
            eta_per_m = np.linalg.solve(dyn.astype(complex), rhs_per_m)
        except np.linalg.LinAlgError:
            eta_per_m = np.array([np.nan + 0j, np.nan + 0j])
        bow_per_m = eta_per_m[0] - bow_x_from_cg_m * eta_per_m[1]
        rows.append(
            {
                "speed_mps": eq.speed_mps,
                "fn_b": eq.fn_b,
                "wave_period_s": period,
                "omega0_rad_s": omega0,
                "omega_e_rad_s": omega_e,
                "wavenumber_rad_m": k,
                "heave_rao_m_per_m": abs(eta_per_m[0]),
                "pitch_rao_rad_per_m": abs(eta_per_m[1]),
                "pitch_rao_rad_per_wave_slope": abs(eta_per_m[1]) / max(abs(k), 1e-12),
                "bow_vertical_rao_m_per_m": abs(bow_per_m),
                "heave_accel_rao_mps2_per_m": omega_e**2 * abs(eta_per_m[0]),
                "bow_accel_rao_mps2_per_m": omega_e**2 * abs(bow_per_m),
                "heave_phase_rad": float(np.angle(eta_per_m[0])),
                "pitch_phase_rad": float(np.angle(eta_per_m[1])),
            }
        )
    return pd.DataFrame(rows)


def _precompute_component_residuals(
    boat: BoatConfig,
    eq: EquilibriumState,
    matrices: HydroMatrices,
    comp: WaveComponents,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    c = matrices.restoring
    f3_s = []
    f3_c = []
    f5_s = []
    f5_c = []
    for omega0, omega_e, k in zip(comp.omega0, comp.omega_e, comp.wavenumber):
        coeff = wave_excitation_coefficients(boat, eq, matrices, float(omega0), float(omega_e), float(k))
        f3_s.append(coeff[0, 0] - c[0, 0])
        f3_c.append(coeff[0, 1] - c[0, 1] * k)
        f5_s.append(coeff[1, 0] - c[1, 0])
        f5_c.append(coeff[1, 1] - c[1, 1] * k)
    return np.asarray(f3_s), np.asarray(f3_c), np.asarray(f5_s), np.asarray(f5_c)


def _component_residual_forces(
    comp: WaveComponents,
    residual_coeffs: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    t: float,
) -> tuple[float, float, float, float]:
    f3_s, f3_c, f5_s, f5_c = residual_coeffs
    arg = comp.omega_e * t + comp.phase
    s = np.sin(arg)
    co = np.cos(arg)
    weighted_s = comp.amplitude * s
    weighted_c = comp.amplitude * co
    wave_eta = 0.0
    wave_slope = 0.0
    f3_res = 0.0
    f5_res = 0.0
    wave_eta = float(np.sum(weighted_s))
    wave_slope = float(np.sum(comp.wavenumber * weighted_c))
    f3_res = float(np.sum(f3_s * weighted_s + f3_c * weighted_c))
    f5_res = float(np.sum(f5_s * weighted_s + f5_c * weighted_c))
    return wave_eta, wave_slope, f3_res, f5_res


def _regular_components(waves: WaveConfig, eq: EquilibriumState, g: float) -> WaveComponents:
    omega0 = np.array([2.0 * math.pi / waves.regular_period_s])
    return WaveComponents(
        omega0=omega0,
        omega_e=np.asarray(encounter_frequency(omega0, eq.speed_through_water_mps, waves.heading_deg, g), dtype=float),
        wavenumber=np.asarray(wavenumber_deep(omega0, g), dtype=float),
        amplitude=np.array([0.5 * waves.regular_height_m], dtype=float),
        phase=np.array([0.0], dtype=float),
    )


def _time_eval_grid(duration_s: float, time_step_s: float) -> np.ndarray:
    t_eval = np.arange(0.0, duration_s + 0.5 * time_step_s, time_step_s)
    t_eval = t_eval[t_eval <= duration_s]
    if len(t_eval) == 0 or t_eval[-1] < duration_s - 1e-12:
        t_eval = np.append(t_eval, duration_s)
    return t_eval


def _nonlinear_rhs_function(
    boat: BoatConfig,
    eq: EquilibriumState,
    matrices: HydroMatrices,
    components: WaveComponents,
) -> tuple[Callable[[float, np.ndarray], np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    baseline, _, _ = generalized_calm_force(
        boat, eq.speed_through_water_mps, eq.z_wl_m, eq.trim_rad, eta3_m=0.0, eta5_rad=0.0
    )
    minv = np.linalg.inv(matrices.total_mass)
    residual_coeffs = _precompute_component_residuals(boat, eq, matrices, components)

    def rhs(t: float, y: np.ndarray) -> np.ndarray:
        eta3, eta5, u3, u5 = y
        wave_eta, wave_slope, f3_res, f5_res = _component_residual_forces(components, residual_coeffs, t)
        quasi, _, _ = generalized_calm_force(
            boat,
            eq.speed_through_water_mps,
            eq.z_wl_m,
            eq.trim_rad,
            eta3_m=eta3 - wave_eta,
            eta5_rad=eta5 - wave_slope,
        )
        force = quasi - baseline + np.array([f3_res, f5_res]) - matrices.damping @ np.array([u3, u5])
        acc = minv @ force
        return np.array([u3, u5, acc[0], acc[1]], dtype=float)

    return rhs, residual_coeffs


def _sixdof_from_nonlinear_states(
    t_eval: np.ndarray,
    states: np.ndarray,
    rhs: Callable[[float, np.ndarray], np.ndarray],
    residual_coeffs: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    components: WaveComponents,
    bow_x_from_cg_m: float,
) -> pd.DataFrame:
    acc = np.zeros((2, states.shape[1]))
    wave_eta_series = np.zeros(states.shape[1])
    for idx, (t, state) in enumerate(zip(t_eval, states.T)):
        dydt = rhs(float(t), state)
        acc[:, idx] = dydt[2:4]
        wave_eta_series[idx] = _component_residual_forces(components, residual_coeffs, float(t))[0]
    return make_sixdof_timeseries(
        t_eval,
        states[0],
        states[1],
        states[2],
        states[3],
        acc[0],
        acc[1],
        bow_x_from_cg_m,
        wave_eta_series,
    )


def simulate_time_domain(
    boat: BoatConfig,
    waves: WaveConfig,
    eq: EquilibriumState,
    matrices: HydroMatrices,
    components: WaveComponents,
    duration_s: float,
    time_step_s: float,
    bow_x_from_cg_m: float,
) -> pd.DataFrame:
    rhs, residual_coeffs = _nonlinear_rhs_function(boat, eq, matrices, components)
    t_eval = _time_eval_grid(duration_s, time_step_s)
    sol = solve_ivp(
        rhs,
        (0.0, duration_s),
        y0=np.zeros(4),
        t_eval=t_eval,
        method="RK45",
        rtol=1e-7,
        atol=1e-9,
        max_step=max(time_step_s, 1e-3),
    )
    if not sol.success:
        raise RuntimeError(f"Time-domain integration failed: {sol.message}")

    return _sixdof_from_nonlinear_states(sol.t, sol.y, rhs, residual_coeffs, components, bow_x_from_cg_m)


def simulate_time_domain_rk4(
    boat: BoatConfig,
    waves: WaveConfig,
    eq: EquilibriumState,
    matrices: HydroMatrices,
    components: WaveComponents,
    duration_s: float,
    time_step_s: float,
    bow_x_from_cg_m: float,
) -> pd.DataFrame:
    """Fixed-step nonlinear diagnostic integrator for benchmark sweeps.

    The default `simulate_time_domain` path remains the adaptive solve_ivp
    solver. This RK4 path is useful for coarse validation probes that need many
    short regular-wave nonlinear runs with deterministic sampling cost.
    """
    rhs, residual_coeffs = _nonlinear_rhs_function(boat, eq, matrices, components)
    t_eval = _time_eval_grid(duration_s, time_step_s)
    states = np.zeros((4, len(t_eval)), dtype=float)
    for idx in range(len(t_eval) - 1):
        t = float(t_eval[idx])
        h = float(t_eval[idx + 1] - t_eval[idx])
        y = states[:, idx]
        k1 = rhs(t, y)
        k2 = rhs(t + 0.5 * h, y + 0.5 * h * k1)
        k3 = rhs(t + 0.5 * h, y + 0.5 * h * k2)
        k4 = rhs(t + h, y + h * k3)
        states[:, idx + 1] = y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        if not np.isfinite(states[:, idx + 1]).all():
            raise RuntimeError("Fixed-step nonlinear time-domain integration produced non-finite state values.")
    return _sixdof_from_nonlinear_states(t_eval, states, rhs, residual_coeffs, components, bow_x_from_cg_m)


def simulate_linear_response(
    boat: BoatConfig,
    eq: EquilibriumState,
    matrices: HydroMatrices,
    components: WaveComponents,
    duration_s: float,
    time_step_s: float,
    bow_x_from_cg_m: float,
) -> pd.DataFrame:
    t = np.arange(0.0, duration_s + 0.5 * time_step_s, time_step_s)
    heave = np.zeros_like(t)
    pitch = np.zeros_like(t)
    heave_vel = np.zeros_like(t)
    pitch_rate = np.zeros_like(t)
    heave_acc = np.zeros_like(t)
    pitch_acc = np.zeros_like(t)
    wave_eta = np.zeros_like(t)
    for omega0, omega_e, k, amp, phase in zip(
        components.omega0,
        components.omega_e,
        components.wavenumber,
        components.amplitude,
        components.phase,
    ):
        f = wave_excitation_coefficients(boat, eq, matrices, float(omega0), float(omega_e), float(k))
        rhs_per_m = np.array([f[0, 1] - 1j * f[0, 0], f[1, 1] - 1j * f[1, 0]], dtype=complex)
        dyn = -omega_e**2 * matrices.total_mass + 1j * omega_e * matrices.damping + matrices.restoring
        eta_per_m = np.linalg.solve(dyn.astype(complex), rhs_per_m)
        exp_arg = np.exp(1j * (omega_e * t + phase))
        heave_complex = amp * eta_per_m[0] * exp_arg
        pitch_complex = amp * eta_per_m[1] * exp_arg
        heave += np.real(heave_complex)
        pitch += np.real(pitch_complex)
        heave_vel += np.real(1j * omega_e * heave_complex)
        pitch_rate += np.real(1j * omega_e * pitch_complex)
        heave_acc += np.real(-(omega_e**2) * heave_complex)
        pitch_acc += np.real(-(omega_e**2) * pitch_complex)
        wave_eta += amp * np.sin(omega_e * t + phase)
    return make_sixdof_timeseries(
        t,
        heave,
        pitch,
        heave_vel,
        pitch_rate,
        heave_acc,
        pitch_acc,
        bow_x_from_cg_m,
        wave_eta,
    )


def analyze_speed(config: RunConfig, speed_mps: float) -> SpeedResult:
    boat, eq, equilibrium_source = _resolve_boat_and_equilibrium(config, speed_mps)
    matrices = compute_hydro_matrices(boat, eq)
    bow_x = _bow_x_from_cg(config, boat)
    rao = solve_rao(boat, config.waves, eq, matrices, bow_x)
    regular_ts = simulate_time_domain(
        boat,
        config.waves,
        eq,
        matrices,
        _regular_components(config.waves, eq, boat.gravity_m_s2),
        config.simulation.duration_s,
        config.simulation.time_step_s,
        bow_x,
    )
    irregular_ts = None
    irregular_method = "none"
    fallback_reason = ""
    if config.simulation.use_irregular_wave:
        irregular_components = make_irregular_components(config.waves, eq.speed_through_water_mps, boat.gravity_m_s2)
        try:
            irregular_ts = simulate_time_domain(
                boat,
                config.waves,
                eq,
                matrices,
                irregular_components,
                config.simulation.duration_s,
                config.simulation.time_step_s,
                bow_x,
            )
            irregular_method = "nonlinear_time_domain"
        except RuntimeError as error:
            if not config.simulation.allow_linear_fallback:
                raise
            fallback_reason = str(error)
            irregular_ts = simulate_linear_response(
                boat,
                eq,
                matrices,
                irregular_components,
                config.simulation.duration_s,
                config.simulation.time_step_s,
                bow_x,
            )
            irregular_method = "linear_rao_superposition_fallback"
    rms_source = irregular_ts if irregular_ts is not None else regular_ts
    rms = rms_after(rms_source, config.simulation.discard_initial_s)
    response_diagnostics = _response_diagnostics(regular_ts, eq, boat.gravity_m_s2, "regular")
    if irregular_ts is not None:
        response_diagnostics.update(_response_diagnostics(irregular_ts, eq, boat.gravity_m_s2, "irregular"))
    eig = matrices.stability_eigenvalues
    summary = {
        "speed_mps": eq.speed_mps,
        "speed_kn": eq.speed_mps * 1.943844,
        "speed_through_water_mps": eq.speed_through_water_mps,
        "fn_b": eq.fn_b,
        "trim_deg": eq.trim_deg,
        "z_wl_m": eq.z_wl_m,
        "keel_wetted_length_m": eq.geometry.keel_wetted_length_m,
        "chine_wetted_length_m": eq.geometry.chine_wetted_length_m,
        "lambda_w": eq.geometry.lambda_w,
        "equilibrium_source": equilibrium_source,
        "equilibrium_converged": eq.converged,
        "heave_force_residual_weight_fraction": eq.residual[0],
        "pitch_moment_residual_weight_beam_fraction": eq.residual[1],
        "stable_linear_hp": matrices.stable,
        "max_eigen_real": float(np.max(np.real(eig))),
        "irregular_method": irregular_method,
        "fallback_reason": fallback_reason,
        **rms,
        **response_diagnostics,
        "sixdof_note": "Heave/pitch solved; surge constrained by prescribed speed; sway/roll/yaw constrained by head-sea symmetry, not independently predicted.",
    }
    return SpeedResult(eq, matrices, rao, regular_ts, irregular_ts, summary)
