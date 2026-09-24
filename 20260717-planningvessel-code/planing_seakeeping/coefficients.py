from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.special import gamma

from .config import BoatConfig
from .equilibrium import EquilibriumState, generalized_calm_force


@dataclass
class HydroMatrices:
    added_mass: np.ndarray
    rigid_mass: np.ndarray
    total_mass: np.ndarray
    damping: np.ndarray
    restoring: np.ndarray
    stability_eigenvalues: np.ndarray
    stable: bool


def wedge_added_mass_k(deadrise_deg: float) -> float:
    beta = math.radians(max(deadrise_deg, 0.1))
    beta_over_pi = beta / math.pi
    return (
        math.pi
        / math.sin(beta)
        * gamma(1.5 - beta_over_pi)
        / (gamma(1.0 - beta_over_pi) ** 2 * gamma(0.5 + beta_over_pi))
        - 1.0
    ) / math.tan(beta)


def savitsky_deadrise_lift_slope_per_rad(
    trim_rad: float,
    lambda_w: float,
    fn_b: float,
    deadrise_deg: float,
) -> float:
    """Return ``d C_L_beta / d tau`` from the full Savitsky lift law.

    The derivative retains both the high-speed ``0.012*sqrt(lambda)`` term and
    the finite-speed ``0.0055*lambda**2.5/Fn_B**2`` term used by the calm-water
    equilibrium model.  Omitting the latter systematically underestimates the
    planing-lift damping near resonance at finite beam Froude number.
    """

    tau = max(float(trim_rad), math.radians(0.05))
    lam = max(float(lambda_w), 1.0e-6)
    froude = max(float(fn_b), 1.0e-6)
    beta = max(float(deadrise_deg), 0.0)
    tau_deg = math.degrees(tau)
    speed_bracket = 0.012 * math.sqrt(lam) + 0.0055 * lam**2.5 / froude**2
    cl0 = tau_deg**1.1 * speed_bracket
    dcl0_dtau = 1.1 * (180.0 / math.pi) * tau_deg**0.1 * speed_bracket
    deadrise_derivative = 1.0 - 0.0039 * beta * max(cl0, 1.0e-12) ** -0.4
    return dcl0_dtau * deadrise_derivative


def _added_mass_matrix(boat: BoatConfig, eq: EquilibriumState) -> np.ndarray:
    rho = boat.rho_water_kg_m3
    b = boat.beam_m
    beta = math.radians(boat.deadrise_deg)
    geom = eq.geometry
    k_const = wedge_added_mass_k(boat.deadrise_deg)
    x_g = geom.keel_wetted_length_m - boat.lcg_m
    kappa = (1.0 + geom.z_max_ratio) * eq.trim_rad
    xs = geom.x_s_m
    lc = geom.chine_wetted_length_m
    lk = geom.keel_wetted_length_m

    a1_33 = rho * kappa**2 * k_const * xs**3 / 3.0
    a1_35 = a1_33 * (x_g - 0.75 * xs)
    a1_53 = a1_35
    a1_55 = a1_33 * (x_g**2 - 1.5 * x_g * xs + 0.6 * xs**2)

    if lc > 0:
        c1 = 2.0 * math.tan(beta) ** 2 / math.pi * k_const
        a2_33 = rho * b**3 * c1 * math.pi / 8.0 * lc / b
        a2_35 = rho * b**4 * (
            -c1 * math.pi / 16.0 * ((lk / b) ** 2 - (xs / b) ** 2)
            + (x_g / b) * a2_33 / (rho * b**3)
        )
        a2_53 = a2_35
        a2_55 = rho * b**5 * (
            c1 * math.pi / 24.0 * ((lk / b) ** 3 - (xs / b) ** 3)
            - c1 * math.pi / 8.0 * (x_g / b) * ((lk / b) ** 2 - (xs / b) ** 2)
            + (x_g / b) ** 2 * a2_33 / (rho * b**3)
        )
    else:
        a2_33 = a2_35 = a2_53 = a2_55 = 0.0

    return np.array(
        [[a1_33 + a2_33, a1_35 + a2_35], [a1_53 + a2_53, a1_55 + a2_55]],
        dtype=float,
    )


def _rigid_mass_matrix(boat: BoatConfig) -> np.ndarray:
    return np.array(
        [[boat.mass_kg, 0.0], [0.0, boat.mass_kg * boat.pitch_radius_gyration_m**2]],
        dtype=float,
    )


def _damping_matrix(
    boat: BoatConfig,
    eq: EquilibriumState,
    added_mass: np.ndarray,
    *,
    lift_slope_model: str = "faltinsen_eq9_76_high_frequency",
) -> np.ndarray:
    rho = boat.rho_water_kg_m3
    b = boat.beam_m
    beta = math.radians(boat.deadrise_deg)
    geom = eq.geometry
    k_const = wedge_added_mass_k(boat.deadrise_deg)
    if geom.chine_wetted_length_m > 0:
        section_draft = 0.5 * b * math.tan(beta)
    else:
        section_draft = (1.0 + geom.z_max_ratio) * eq.trim_rad * geom.keel_wetted_length_m
    a33_2d = rho * section_draft**2 * k_const
    lam = max(geom.lambda_w, 1e-6)
    slope_model = str(lift_slope_model).strip().lower()
    if slope_model == "faltinsen_eq9_76_high_frequency":
        tau_deg = max(eq.trim_deg, 0.05)
        cl0_inf = tau_deg**1.1 * 0.012 * math.sqrt(lam)
        dcl0_dtau = (
            (180.0 / math.pi) ** 1.1
            * 0.0132
            * eq.trim_rad**0.1
            * math.sqrt(lam)
        )
        dclb_dtau = dcl0_dtau * (
            1.0 - 0.0039 * boat.deadrise_deg * max(cl0_inf, 1.0e-12) ** -0.4
        )
    elif slope_model == "finite_speed_savitsky_diagnostic":
        dclb_dtau = savitsky_deadrise_lift_slope_per_rad(
            eq.trim_rad,
            lam,
            eq.fn_b,
            boat.deadrise_deg,
        )
    else:
        raise ValueError(
            "lift_slope_model must be faltinsen_eq9_76_high_frequency or "
            "finite_speed_savitsky_diagnostic."
        )
    u = eq.speed_through_water_mps
    b33 = rho / 2.0 * u * b**2 * dclb_dtau
    b35 = -u * (added_mass[0, 0] + boat.lcg_m * a33_2d)
    b53 = b33 * (0.75 * lam * b - boat.lcg_m)
    b55 = u * boat.lcg_m**2 * a33_2d
    return np.array([[b33, b35], [b53, b55]], dtype=float)


def _restoring_matrix(boat: BoatConfig, eq: EquilibriumState) -> np.ndarray:
    h3 = max(1e-5 * boat.beam_m, 1e-6)
    h5 = 1e-5

    def force(eta3: float, eta5: float) -> np.ndarray:
        net, _, _ = generalized_calm_force(
            boat,
            eq.speed_through_water_mps,
            eq.z_wl_m,
            eq.trim_rad,
            eta3_m=eta3,
            eta5_rad=eta5,
        )
        return net

    base = force(0.0, 0.0)
    c33 = -((force(h3, 0.0) - force(-h3, 0.0)) / (2.0 * h3))[0]
    c53 = -((force(h3, 0.0) - force(-h3, 0.0)) / (2.0 * h3))[1]
    c35 = -((force(0.0, h5) - force(0.0, -h5)) / (2.0 * h5))[0]
    c55 = -((force(0.0, h5) - force(0.0, -h5)) / (2.0 * h5))[1]
    c = np.array([[c33, c35], [c53, c55]], dtype=float)
    if np.linalg.norm(base) > boat.mass_kg * boat.gravity_m_s2 * 1e-2:
        # The equilibrium residual is reported elsewhere; keep the derivative usable.
        pass
    return c


def _stability_eigenvalues(total_mass: np.ndarray, damping: np.ndarray, restoring: np.ndarray) -> np.ndarray:
    zero = np.zeros((2, 2))
    ident = np.eye(2)
    minv = np.linalg.inv(total_mass)
    state = np.block([[zero, ident], [-minv @ restoring, -minv @ damping]])
    return np.linalg.eigvals(state)


def compute_hydro_matrices(
    boat: BoatConfig,
    eq: EquilibriumState,
    *,
    damping_lift_slope_model: str = "faltinsen_eq9_76_high_frequency",
) -> HydroMatrices:
    added = _added_mass_matrix(boat, eq)
    rigid = _rigid_mass_matrix(boat)
    total = rigid + added
    damping = _damping_matrix(
        boat,
        eq,
        added,
        lift_slope_model=damping_lift_slope_model,
    )
    restoring = _restoring_matrix(boat, eq)
    eig = _stability_eigenvalues(total, damping, restoring)
    return HydroMatrices(
        added_mass=added,
        rigid_mass=rigid,
        total_mass=total,
        damping=damping,
        restoring=restoring,
        stability_eigenvalues=eig,
        stable=bool(np.all(np.real(eig) < 0.0)),
    )
