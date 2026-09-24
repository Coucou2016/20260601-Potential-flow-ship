from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from .moving_wedge import MovingWedgeConfig, run_steady_planing_wedge_entry
from .planing_forced_motion import (
    PlaningForcedMotionCase,
    _integrate_station_interval,
    _longitudinal_bem_bin_definition,
    _remove_aft_station_interval,
)


PLANING_RESTORING_STATUS = "sun_2007_eq7_17_eq7_18_quasistatic_restoring"


@dataclass(frozen=True)
class PlaningSteadyGeometry:
    heave_m: float
    pitch_rad: float
    trim_rad: float
    average_wetted_length_m: float
    chine_wetting_x_from_leading_m: float
    keel_wetted_length_m: float
    transom_draft_m: float


@dataclass(frozen=True)
class PlaningSteadyLoadResult:
    geometry: PlaningSteadyGeometry
    generalized_load: np.ndarray
    raw_bem_generalized_load: np.ndarray
    bem_generalized_load: np.ndarray
    front_generalized_load: np.ndarray
    transom_generalized_load: np.ndarray
    longitudinal_bem_bin_generalized_load: dict[str, np.ndarray]
    station_count: int
    max_potential_bvp_relative_residual: float
    max_pressure_bvp_relative_residual: float
    max_contact_constraint_abs_m: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PlaningRestoringMatrixResult:
    restoring_matrix: np.ndarray
    coarse_matrix: np.ndarray
    refined_matrix: np.ndarray
    relative_step_change: np.ndarray
    component_restoring_matrices: dict[str, np.ndarray]
    coarse_component_restoring_matrices: dict[str, np.ndarray]
    refined_component_restoring_matrices: dict[str, np.ndarray]
    heave_step_m: float
    pitch_step_rad: float
    load_cases: tuple[PlaningSteadyLoadResult, ...]
    metadata: dict[str, Any]


def steady_average_wetted_length_eq_7_17(
    *,
    mean_average_wetted_length_m: float,
    lcg_from_transom_m: float,
    vcg_m: float,
    mean_trim_rad: float,
    heave_m: float,
    pitch_rad: float,
) -> float:
    """Evaluate Sun (2007), Eq. 7.17, using heave-up and bow-up signs."""

    values = (
        mean_average_wetted_length_m,
        lcg_from_transom_m,
        vcg_m,
        mean_trim_rad,
        heave_m,
        pitch_rad,
    )
    if not np.isfinite(values).all():
        raise ValueError("Steady wetted-length inputs must be finite.")
    if mean_average_wetted_length_m <= 0.0 or vcg_m <= 0.0 or mean_trim_rad <= 0.0:
        raise ValueError("Mean wetted length, VCG, and trim must be positive.")
    trim = float(mean_trim_rad + pitch_rad)
    if not 0.0 < trim < 0.5 * np.pi:
        raise ValueError("Instantaneous trim must lie between zero and pi/2.")
    numerator = (
        vcg_m * np.cos(mean_trim_rad)
        - (mean_average_wetted_length_m - lcg_from_transom_m) * np.sin(mean_trim_rad)
        + heave_m
    )
    length = lcg_from_transom_m + vcg_m / np.tan(trim) - numerator / np.sin(trim)
    if length <= 0.0:
        raise ValueError("Eq. 7.17 produced a non-positive average wetted length.")
    return float(length)


def _integrate_generalized_load(
    x_from_transom_m: np.ndarray,
    force_density_n_m: np.ndarray,
    lcg_from_transom_m: float,
) -> np.ndarray:
    return _integrate_station_interval(
        np.asarray(x_from_transom_m, dtype=float),
        np.asarray(force_density_n_m, dtype=float),
        lower_m=float(x_from_transom_m[0]),
        upper_m=float(x_from_transom_m[-1]),
        lcg_from_transom_m=float(lcg_from_transom_m),
    )


def _static_front_load(
    wedge_config: MovingWedgeConfig,
    case: PlaningForcedMotionCase,
    geometry: PlaningSteadyGeometry,
    *,
    foremost_bem_x_from_transom_m: float,
    gauss_order: int = 8,
) -> np.ndarray:
    x_start = float(foremost_bem_x_from_transom_m)
    x_end = geometry.keel_wetted_length_m
    length = max(x_end - x_start, 0.0)
    if length == 0.0:
        return np.zeros(2, dtype=float)
    nodes, weights = np.polynomial.legendre.leggauss(int(gauss_order))
    x = 0.5 * (x_start + x_end) + 0.5 * length * nodes
    draft = (x_end - x) * geometry.trim_rad
    entry_speed = case.speed_mps * geometry.trim_rad
    added_mass_k = (
        case.front_added_mass_cm
        * case.rho_water_kg_m3
        * np.pi
        * case.front_pileup_factor**2
        / (2.0 * np.tan(wedge_config.deadrise_rad) ** 2)
    )
    force_density = 2.0 * added_mass_k * draft * entry_speed**2
    jacobian = 0.5 * length
    force = jacobian * np.sum(weights * force_density)
    moment = jacobian * np.sum(
        weights * force_density * (x - case.lcg_from_transom_m)
    )
    return np.asarray([force, moment], dtype=float)


def _static_transom_load(
    wedge_config: MovingWedgeConfig,
    case: PlaningForcedMotionCase,
    geometry: PlaningSteadyGeometry,
    *,
    gauss_order: int = 8,
) -> np.ndarray:
    if not case.transom_correction_enabled:
        return np.zeros(2, dtype=float)
    beam = 2.0 * wedge_config.chine_half_beam_m
    fn_b = case.speed_mps / np.sqrt(case.gravity_m_s2 * beam)
    lambda_w = geometry.average_wetted_length_m / beam
    trim_deg = float(np.degrees(geometry.trim_rad))
    common = trim_deg**0.7 / fn_b**0.6
    c1 = 0.02064 * common**2
    c2 = 0.00448 * common**2.44
    c3 = 0.0108 * lambda_w * trim_deg**0.34
    separation_speed = np.sqrt(
        case.speed_mps**2 + 2.0 * case.gravity_m_s2 * geometry.transom_draft_m
    )
    alpha = case.transom_fit_limit_beams
    integral = (
        c1 * alpha**4.5 / 4.5
        - c2 * alpha**4.94 / 4.94
        + c3 * alpha**3.5 / 3.5
    )
    a_three_halves = 4.0 * separation_speed * integral / (alpha**4 * np.sqrt(beam))
    patch_length = case.transom_patch_length_beams * beam
    nodes, weights = np.polynomial.legendre.leggauss(int(gauss_order))
    x = 0.5 * patch_length * (nodes + 1.0)
    force_density = (
        1.5
        * case.rho_water_kg_m3
        * separation_speed
        * a_three_halves
        * np.sqrt(x)
        * beam
    )
    jacobian = 0.5 * patch_length
    force = jacobian * np.sum(weights * force_density)
    moment = jacobian * np.sum(
        weights * force_density * (x - case.lcg_from_transom_m)
    )
    return np.asarray([force, moment], dtype=float)


def run_steady_planing_offset(
    wedge_config: MovingWedgeConfig,
    case: PlaningForcedMotionCase,
    *,
    vcg_m: float,
    heave_m: float = 0.0,
    pitch_rad: float = 0.0,
) -> PlaningSteadyLoadResult:
    """Compute one constant-heave/pitch load for Sun Eqs. 7.17-7.18."""

    beam = 2.0 * float(wedge_config.chine_half_beam_m)
    if case.mean_wetted_length_beam_ratio is None:
        raise ValueError("mean_wetted_length_beam_ratio is required for Eq. 7.17.")
    mean_average_length = float(case.mean_wetted_length_beam_ratio) * beam
    average_length = steady_average_wetted_length_eq_7_17(
        mean_average_wetted_length_m=mean_average_length,
        lcg_from_transom_m=case.lcg_from_transom_m,
        vcg_m=vcg_m,
        mean_trim_rad=case.mean_trim_rad,
        heave_m=heave_m,
        pitch_rad=pitch_rad,
    )
    trim = float(case.mean_trim_rad + pitch_rad)
    mean_chine_wetting_x = 2.0 * (case.wetted_length_m - mean_average_length)
    if mean_chine_wetting_x <= 0.0:
        raise ValueError(
            "Keel wetted length must exceed mean wetted length so Eq. 7.3 defines x_s."
        )
    x_s = mean_chine_wetting_x * np.tan(case.mean_trim_rad) / np.tan(trim)
    keel_length = average_length + 0.5 * x_s
    transom_draft = keel_length * np.tan(trim)
    geometry = PlaningSteadyGeometry(
        heave_m=float(heave_m),
        pitch_rad=float(pitch_rad),
        trim_rad=trim,
        average_wetted_length_m=average_length,
        chine_wetting_x_from_leading_m=x_s,
        keel_wetted_length_m=float(keel_length),
        transom_draft_m=float(transom_draft),
    )
    steady = run_steady_planing_wedge_entry(
        wedge_config,
        speed_mps=case.speed_mps,
        trim_rad=trim,
        wetted_length_m=keel_length,
        time_step_s=case.time_step_s,
        initial_draft_m=case.initial_draft_m,
        rho_water_kg_m3=case.rho_water_kg_m3,
        gravity_m_s2=case.gravity_m_s2,
    )
    initial_offset = case.initial_draft_m / np.tan(trim)
    x_all = keel_length - (initial_offset + steady.x_from_leading_edge_m)
    force_all = np.asarray(steady.vertical_force_per_length_n_m, dtype=float)
    order = np.argsort(x_all)
    x_all = np.asarray(x_all[order], dtype=float)
    force_all = force_all[order]
    if x_all[0] > 0.0 or x_all[-1] < 0.0:
        raise RuntimeError("Steady entry history does not bracket the transom x=0 endpoint.")
    force_at_transom = float(np.interp(0.0, x_all, force_all))
    positive = x_all > 1e-12
    x = np.concatenate(([0.0], x_all[positive]))
    force_density = np.concatenate(([force_at_transom], force_all[positive]))
    if len(x) < 2 or np.any(np.diff(x) <= 0.0):
        raise RuntimeError("Steady offset produced an invalid longitudinal station grid.")
    raw_bem = _integrate_generalized_load(x, force_density, case.lcg_from_transom_m)
    longitudinal_bin_edges, longitudinal_bin_labels = _longitudinal_bem_bin_definition(
        case,
        wedge_config,
    )
    longitudinal_bin_loads = {
        label: _integrate_station_interval(
            x,
            force_density,
            lower_m=float(longitudinal_bin_edges[index]),
            upper_m=float(longitudinal_bin_edges[index + 1]),
            lcg_from_transom_m=case.lcg_from_transom_m,
        )
        for index, label in enumerate(longitudinal_bin_labels)
    }
    bem = raw_bem.copy()
    removed_length = 0.0
    if case.transom_keel_reduction_beams > 0.0:
        removed_length = case.transom_keel_reduction_beams * beam
        interior_x, interior_force = _remove_aft_station_interval(
            x,
            force_density,
            removed_length_m=removed_length,
        )
        bem = _integrate_generalized_load(
            interior_x,
            interior_force,
            case.lcg_from_transom_m,
        )
    elif case.transom_correction_enabled:
        removed_length = case.transom_patch_length_beams * beam
        interior_x, interior_force = _remove_aft_station_interval(
            x,
            force_density,
            removed_length_m=removed_length,
        )
        bem = _integrate_generalized_load(
            interior_x,
            interior_force,
            case.lcg_from_transom_m,
        )
    front = _static_front_load(
        wedge_config,
        case,
        geometry,
        foremost_bem_x_from_transom_m=float(x[-1]),
    )
    transom = _static_transom_load(wedge_config, case, geometry)
    total = bem + front + transom
    return PlaningSteadyLoadResult(
        geometry=geometry,
        generalized_load=total,
        raw_bem_generalized_load=raw_bem,
        bem_generalized_load=bem,
        front_generalized_load=front,
        transom_generalized_load=transom,
        longitudinal_bem_bin_generalized_load=longitudinal_bin_loads,
        station_count=int(len(x)),
        max_potential_bvp_relative_residual=steady.max_potential_bvp_relative_residual,
        max_pressure_bvp_relative_residual=steady.max_pressure_bvp_relative_residual,
        max_contact_constraint_abs_m=steady.max_contact_constraint_abs_m,
        metadata={
            "status": PLANING_RESTORING_STATUS,
            "wetted_length_equation": "Sun_2007_Eq7.17",
            "restoring_equation": "Sun_2007_Eq7.18",
            "transom_3d_correction_mode": case.transom_correction_mode,
            "transom_removed_length_m": removed_length,
            "chine_wetting_position": "Eq7.3_base_xs_scaled_by_tan(mean_trim)/tan(trim)",
            "load_decomposition": "interior_BEM_plus_front_Eq7.36_7.45_plus_transom_Eq7.19_7.22",
            "steady_entry_reference_draft_m": steady.reference_draft_m,
            "steady_entry_final_jet_cut_count": steady.final_jet_cut_count,
            "steady_entry_separated_state_count": steady.separated_state_count,
            "steady_entry_separation_event_count": steady.separation_event_count,
            "steady_entry_first_separation_time_s": steady.first_separation_time_s,
            "steady_entry_first_separation_x_from_leading_m": (
                steady.first_separation_x_from_leading_m
            ),
            "steady_entry_minimum_jet_normal_distance_ratio": (
                steady.minimum_jet_normal_distance_ratio
            ),
            "steady_entry_minimum_jet_projection_ratio": (
                steady.minimum_jet_projection_ratio
            ),
            "steady_entry_maximum_jet_projection_ratio": (
                steady.maximum_jet_projection_ratio
            ),
            "longitudinal_bem_bin_labels": list(longitudinal_bin_labels),
            "longitudinal_bem_bin_edges_m": longitudinal_bin_edges.tolist(),
            "response_calibration_used": False,
        },
    )


def estimate_planing_restoring_matrix(
    wedge_config: MovingWedgeConfig,
    case: PlaningForcedMotionCase,
    *,
    vcg_m: float,
    heave_step_m: float,
    pitch_step_rad: float,
    richardson_extrapolation: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> PlaningRestoringMatrixResult:
    """Estimate ``C_ij=-dF_i/deta_j`` with centered finite differences."""

    if heave_step_m <= 0.0 or pitch_step_rad <= 0.0:
        raise ValueError("Restoring finite-difference steps must be positive.")
    loads: list[PlaningSteadyLoadResult] = []

    component_attributes = {
        "raw_bem": "raw_bem_generalized_load",
        "bem": "bem_generalized_load",
        "front": "front_generalized_load",
        "transom": "transom_generalized_load",
        "total": "generalized_load",
    }
    _, longitudinal_bin_labels = _longitudinal_bem_bin_definition(case, wedge_config)
    longitudinal_component_names = tuple(
        f"longitudinal_bin_{label}" for label in longitudinal_bin_labels
    )

    def component_load(load: PlaningSteadyLoadResult, name: str) -> np.ndarray:
        if name.startswith("longitudinal_bin_"):
            label = name.removeprefix("longitudinal_bin_")
            return np.asarray(load.longitudinal_bem_bin_generalized_load[label], dtype=float)
        return np.asarray(getattr(load, component_attributes[name]), dtype=float)

    def matrix_for_steps(
        h_step: float,
        p_step: float,
        stage: str,
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        matrix = np.zeros((2, 2), dtype=float)
        components = {
            name: np.zeros((2, 2), dtype=float)
            for name in (*component_attributes, *longitudinal_component_names)
        }
        for column, (dof, h_plus, p_plus, step) in enumerate(
            (("heave", h_step, 0.0, h_step), ("pitch", 0.0, p_step, p_step))
        ):
            if progress_callback is not None:
                progress_callback(f"{stage}:{dof}:plus")
            plus = run_steady_planing_offset(
                wedge_config,
                case,
                vcg_m=vcg_m,
                heave_m=h_plus,
                pitch_rad=p_plus,
            )
            if progress_callback is not None:
                progress_callback(f"{stage}:{dof}:minus")
            minus = run_steady_planing_offset(
                wedge_config,
                case,
                vcg_m=vcg_m,
                heave_m=-h_plus,
                pitch_rad=-p_plus,
            )
            loads.extend((plus, minus))
            matrix[:, column] = -(plus.generalized_load - minus.generalized_load) / (2.0 * step)
            for name in components:
                plus_load = component_load(plus, name)
                minus_load = component_load(minus, name)
                components[name][:, column] = -(plus_load - minus_load) / (2.0 * step)
        return matrix, components

    coarse, coarse_components = matrix_for_steps(
        float(heave_step_m),
        float(pitch_step_rad),
        "coarse",
    )
    if richardson_extrapolation:
        refined, refined_components = matrix_for_steps(
            0.5 * float(heave_step_m),
            0.5 * float(pitch_step_rad),
            "refined",
        )
        restoring = (4.0 * refined - coarse) / 3.0
        component_restoring = {
            name: (4.0 * refined_components[name] - coarse_components[name]) / 3.0
            for name in coarse_components
        }
    else:
        refined = coarse.copy()
        refined_components = {
            name: value.copy() for name, value in coarse_components.items()
        }
        restoring = coarse.copy()
        component_restoring = {name: value.copy() for name, value in coarse_components.items()}
    scale = np.maximum(np.abs(restoring), np.finfo(float).eps)
    relative_change = np.abs(refined - coarse) / scale
    return PlaningRestoringMatrixResult(
        restoring_matrix=restoring,
        coarse_matrix=coarse,
        refined_matrix=refined,
        relative_step_change=relative_change,
        component_restoring_matrices=component_restoring,
        coarse_component_restoring_matrices={
            name: value.copy() for name, value in coarse_components.items()
        },
        refined_component_restoring_matrices={
            name: value.copy() for name, value in refined_components.items()
        },
        heave_step_m=float(heave_step_m),
        pitch_step_rad=float(pitch_step_rad),
        load_cases=tuple(loads),
        metadata={
            "status": PLANING_RESTORING_STATUS,
            "source": "Sun_2007_Eq7.17_and_Eq7.18",
            "finite_difference": "centered_with_Richardson" if richardson_extrapolation else "centered",
            "step_convergence_evaluated": bool(richardson_extrapolation),
            "response_calibration_used": False,
        },
    )
