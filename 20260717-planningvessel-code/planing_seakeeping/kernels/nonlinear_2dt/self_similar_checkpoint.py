from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq

from .self_similar_wedge import (
    SelfSimilarCoupledPseudoTimeResult,
    SelfSimilarShallowJetCoupledResult,
    SelfSimilarWedgeConfig,
    _build_coupled_solution_from_outer_nodes,
    _outer_panel_fractions,
    _regrid_coupled_outer_nodes,
    build_residual_curvature_monitor_fractions,
    derive_shallow_water_jet_root_state_from_coupled,
)


CHECKPOINT_SCHEMA_VERSION = 1
CONTINUATION_OVERRIDE_FIELDS = frozenset(
    {
        "pseudo_cfl",
        "coupled_jet_bie_panel_count",
        "coupled_root_inner_tolerance",
        "coupled_pseudo_time_preconditioner",
        "coupled_pseudo_time_preconditioner_max_ratio",
    }
)
HISTORY_COLUMNS = (
    "iteration",
    "pseudo_time",
    "kinematic_rms",
    "dipole_coefficient",
    "root_thickness",
    "root_s_lambda",
    "root_measured_s_lambda",
    "root_relative_mismatch",
    "root_body_eta",
    "root_resolution_ratio",
    "bem_condition_number",
    "accepted_time_step",
    "maximum_displacement_ratio",
)
OPTIONAL_HISTORY_COLUMNS = (
    "kinematic_integral",
    "kinematic_convergence_integral",
    "provisional_matching_surface_shift_panels",
    "final_matching_surface_shift_panels",
    "provisional_matching_surface_root_displacement_ratio",
    "final_matching_surface_root_displacement_ratio",
    "provisional_matching_surface_trigger_code",
    "final_matching_surface_trigger_code",
    "rk2_rejected_attempt_count",
    "jet_point_count",
    "shallow_jet_panel_count_per_side",
    "boundary_panel_count",
    "jet_tip_thickness",
    "jet_tip_s_lambda",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def coupled_pseudo_time_history_frame(
    result: SelfSimilarCoupledPseudoTimeResult,
) -> pd.DataFrame:
    count = len(result.pseudo_time_history)
    data: dict[str, np.ndarray] = {
            "iteration": np.arange(count, dtype=int),
            "pseudo_time": result.pseudo_time_history,
            "kinematic_rms": result.kinematic_rms_history,
            "dipole_coefficient": result.dipole_coefficient_history,
            "root_thickness": result.root_thickness_history,
            "root_s_lambda": result.root_s_lambda_history,
            "root_measured_s_lambda": result.root_measured_s_lambda_history,
            "root_relative_mismatch": result.root_relative_mismatch_history,
            "root_body_eta": result.root_body_eta_history,
            "root_resolution_ratio": result.root_resolution_ratio_history,
            "bem_condition_number": result.bem_condition_number_history,
            "accepted_time_step": np.concatenate(
                ([np.nan], result.time_step_history)
            ),
            "maximum_displacement_ratio": np.concatenate(
                ([np.nan], result.maximum_displacement_ratio_history)
            ),
    }
    integral = getattr(result, "kinematic_integral_history", None)
    if integral is not None:
        data["kinematic_integral"] = np.asarray(integral, dtype=float)
    convergence_integral = getattr(
        result,
        "kinematic_convergence_integral_history",
        None,
    )
    if convergence_integral is not None:
        data["kinematic_convergence_integral"] = np.asarray(
            convergence_integral,
            dtype=float,
        )
    transition_histories = {
        "provisional_matching_surface_shift_panels": (
            "provisional_matching_surface_shift_history"
        ),
        "final_matching_surface_shift_panels": (
            "final_matching_surface_shift_history"
        ),
        "provisional_matching_surface_root_displacement_ratio": (
            "provisional_matching_surface_root_displacement_history"
        ),
        "final_matching_surface_root_displacement_ratio": (
            "final_matching_surface_root_displacement_history"
        ),
        "provisional_matching_surface_trigger_code": (
            "provisional_matching_surface_trigger_history"
        ),
        "final_matching_surface_trigger_code": (
            "final_matching_surface_trigger_history"
        ),
        "rk2_rejected_attempt_count": "rk2_rejected_attempt_count_history",
    }
    for column, attribute in transition_histories.items():
        values = getattr(result, attribute, None)
        if values is not None:
            data[column] = np.concatenate(([np.nan], np.asarray(values, dtype=float)))
    state_histories = {
        "jet_point_count": "jet_point_count_history",
        "shallow_jet_panel_count_per_side": (
            "shallow_jet_panel_count_per_side_history"
        ),
        "boundary_panel_count": "boundary_panel_count_history",
        "jet_tip_thickness": "jet_tip_thickness_history",
        "jet_tip_s_lambda": "jet_tip_s_lambda_history",
    }
    for column, attribute in state_histories.items():
        values = getattr(result, attribute, None)
        if values is not None:
            data[column] = np.asarray(values, dtype=float)
    return pd.DataFrame(data)


def _validated_history(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [name for name in HISTORY_COLUMNS if name not in frame.columns]
    if missing:
        raise ValueError(f"Checkpoint history is missing columns: {missing}.")
    optional = [name for name in OPTIONAL_HISTORY_COLUMNS if name in frame.columns]
    history = frame.loc[:, (*HISTORY_COLUMNS, *optional)].copy()
    for name in HISTORY_COLUMNS:
        history[name] = pd.to_numeric(history[name], errors="raise")
    if history.empty:
        raise ValueError("A resumable checkpoint requires an initial state row.")
    iteration = history["iteration"].to_numpy(dtype=int)
    if not np.array_equal(iteration, np.arange(len(history), dtype=int)):
        raise ValueError("Checkpoint iterations must be contiguous and zero based.")
    pseudo_time = history["pseudo_time"].to_numpy(dtype=float)
    if pseudo_time[0] != 0.0 or np.any(np.diff(pseudo_time) <= 0.0):
        raise ValueError("Checkpoint pseudo-time must start at zero and increase.")
    step = history["accepted_time_step"].to_numpy(dtype=float)
    displacement = history["maximum_displacement_ratio"].to_numpy(dtype=float)
    if not np.isnan(step[0]) or not np.isnan(displacement[0]):
        raise ValueError("The initial checkpoint row must not contain an accepted step.")
    if not np.isfinite(step[1:]).all() or np.any(step[1:] <= 0.0):
        raise ValueError("Accepted checkpoint time steps must be finite and positive.")
    if not np.isfinite(displacement[1:]).all() or np.any(displacement[1:] < 0.0):
        raise ValueError("Checkpoint displacement ratios must be finite and non-negative.")
    if not np.allclose(np.diff(pseudo_time), step[1:], rtol=1.0e-10, atol=1.0e-13):
        raise ValueError("Checkpoint pseudo-time increments disagree with accepted steps.")
    state = history.loc[:, HISTORY_COLUMNS[2:-2]].to_numpy(dtype=float)
    if not np.isfinite(state).all():
        raise ValueError("Checkpoint state histories must be finite.")
    if np.any(history["kinematic_rms"] < 0.0):
        raise ValueError("Checkpoint kinematic residuals must be non-negative.")
    if np.any(history["root_thickness"] <= 0.0):
        raise ValueError("Checkpoint root thicknesses must be positive.")
    if np.any(history["root_resolution_ratio"] <= 0.0):
        raise ValueError("Checkpoint root resolution ratios must be positive.")
    if np.any(history["bem_condition_number"] <= 0.0):
        raise ValueError("Checkpoint BEM condition numbers must be positive.")
    for name in optional:
        values = pd.to_numeric(history[name], errors="raise").to_numpy(dtype=float)
        finite = np.isfinite(values)
        if finite.any():
            first = int(np.flatnonzero(finite)[0])
            if not finite[first:].all() or np.any(values[first:] < 0.0):
                raise ValueError(
                    f"Optional checkpoint history {name} must have only a NaN prefix "
                    "followed by finite non-negative values."
                )
    return history


@dataclass(frozen=True)
class SelfSimilarMatchingSurfacePhase:
    phase_index: int
    modal_cycle_length: int
    reset_count: int
    reset_iterations: tuple[int, ...]
    minimum_relative_jump: float
    period_interval_count: int


def infer_matching_surface_phase(
    history: pd.DataFrame,
    *,
    minimum_relative_jump: float = 0.05,
    recent_reset_interval_count: int = 40,
) -> SelfSimilarMatchingSurfacePhase:
    """Infer a periodic reset phase or a proven no-reset smooth phase.

    A reset is counted only when both the root thickness and root resolution
    ratio jump by the declared amount. This prevents ordinary smooth root
    evolution from being mistaken for a matching-surface reconstruction.
    """

    if not 0.0 < float(minimum_relative_jump) < 1.0:
        raise ValueError("minimum_relative_jump must lie between zero and one.")
    if int(recent_reset_interval_count) < 3:
        raise ValueError("recent_reset_interval_count must be at least three.")
    required = ("iteration", "root_thickness", "root_resolution_ratio")
    missing = [name for name in required if name not in history.columns]
    if missing:
        raise ValueError(
            f"Matching-surface phase history is missing columns: {missing}."
        )
    iteration = pd.to_numeric(history["iteration"], errors="raise").to_numpy(
        dtype=int
    )
    thickness = pd.to_numeric(
        history["root_thickness"], errors="raise"
    ).to_numpy(dtype=float)
    resolution = pd.to_numeric(
        history["root_resolution_ratio"], errors="raise"
    ).to_numpy(dtype=float)
    if len(iteration) < 2:
        raise ValueError("Matching-surface phase inference requires two states.")
    if not np.isfinite(thickness).all() or not np.isfinite(resolution).all():
        raise ValueError("Matching-surface phase state must be finite.")
    if np.any(thickness <= 0.0) or np.any(resolution <= 0.0):
        raise ValueError("Matching-surface phase state must be positive.")
    if np.any(np.diff(iteration) != 1):
        raise ValueError("Matching-surface phase iterations must be contiguous.")

    threshold = 1.0 + float(minimum_relative_jump)
    reset_mask = (thickness[1:] / thickness[:-1] >= threshold) & (
        resolution[1:] / resolution[:-1] >= threshold
    )
    reset_positions = np.flatnonzero(reset_mask) + 1
    if len(reset_positions) < 3:
        explicit_columns = (
            "provisional_matching_surface_shift_panels",
            "final_matching_surface_shift_panels",
            "boundary_panel_count",
        )
        if len(history) >= 8 and all(
            name in history.columns for name in explicit_columns
        ):
            tail_start = len(history) - 8
            tail = history.iloc[tail_start:]
            tail_has_reset = bool(
                np.any(reset_positions >= tail_start + 1)
            )
            provisional = pd.to_numeric(
                tail[explicit_columns[0]], errors="raise"
            ).to_numpy(dtype=float)
            final = pd.to_numeric(
                tail[explicit_columns[1]], errors="raise"
            ).to_numpy(dtype=float)
            boundary_count = pd.to_numeric(
                tail[explicit_columns[2]], errors="raise"
            ).to_numpy(dtype=float)
            tail_thickness = thickness[tail_start:]
            tail_resolution = resolution[tail_start:]
            transition = np.isfinite(provisional) & np.isfinite(final)
            state = np.isfinite(boundary_count)
            finite_provisional = provisional[transition]
            finite_final = final[transition]
            finite_boundary_count = boundary_count[state]
            relative_thickness_step = (
                np.abs(np.diff(tail_thickness)) / tail_thickness[:-1]
            )
            relative_resolution_step = (
                np.abs(np.diff(tail_resolution)) / tail_resolution[:-1]
            )
            enough_explicit_history = (
                np.count_nonzero(transition) >= 7
                and np.count_nonzero(state) >= 8
            )
            matching_is_zero = not tail_has_reset and enough_explicit_history and (
                np.allclose(finite_provisional, 0.0, atol=1.0e-14)
                and np.allclose(finite_final, 0.0, atol=1.0e-14)
                and np.allclose(
                    finite_boundary_count,
                    finite_boundary_count[0],
                    rtol=0.0,
                    atol=1.0e-12,
                )
            )
            matching_is_smooth = not tail_has_reset and enough_explicit_history and (
                np.all(finite_provisional >= 0.0)
                and np.all(finite_final >= 0.0)
                and np.max(finite_provisional) <= 0.25
                and np.max(finite_final) <= 0.25
                and np.max(np.abs(finite_provisional - finite_final)) <= 0.05
                and (
                    len(finite_provisional) < 2
                    or np.max(np.abs(np.diff(finite_provisional))) <= 0.05
                )
                and (
                    len(finite_final) < 2
                    or np.max(np.abs(np.diff(finite_final))) <= 0.05
                )
                and np.max(relative_thickness_step) < float(minimum_relative_jump)
                and np.max(relative_resolution_step) < float(minimum_relative_jump)
                and np.all(np.diff(finite_boundary_count) >= 0.0)
                and np.all(np.diff(finite_boundary_count) <= 2.0)
            )
            if matching_is_zero or matching_is_smooth:
                return SelfSimilarMatchingSurfacePhase(
                    phase_index=0,
                    modal_cycle_length=1,
                    reset_count=len(reset_positions),
                    reset_iterations=tuple(
                        int(iteration[index]) for index in reset_positions
                    ),
                    minimum_relative_jump=float(minimum_relative_jump),
                    period_interval_count=len(tail) - 1,
                )
        raise ValueError(
            "At least three matching-surface resets, or eight states with explicit "
            "zero/smooth shifts and non-jumping topology, are required to infer a "
            "phase."
        )
    periods = np.diff(reset_positions)[-int(recent_reset_interval_count) :]
    values, counts = np.unique(periods, return_counts=True)
    modal_cycle_length = int(values[counts == counts.max()][0])
    phase_index = int(len(history) - 1 - reset_positions[-1])
    if phase_index >= modal_cycle_length:
        raise ValueError(
            "The final matching-surface phase lies outside the inferred modal "
            f"cycle: phase={phase_index}, period={modal_cycle_length}."
        )
    return SelfSimilarMatchingSurfacePhase(
        phase_index=phase_index,
        modal_cycle_length=modal_cycle_length,
        reset_count=len(reset_positions),
        reset_iterations=tuple(int(iteration[index]) for index in reset_positions),
        minimum_relative_jump=float(minimum_relative_jump),
        period_interval_count=len(periods),
    )


def _state_metrics(coupled: SelfSimilarShallowJetCoupledResult) -> dict[str, float]:
    root = coupled.jet_interface.root_state
    measured = derive_shallow_water_jet_root_state_from_coupled(coupled)
    metrics = {
        "kinematic_rms": coupled.kinematic_rms,
        "kinematic_integral": coupled.kinematic_integral,
        "kinematic_length_weighted_rms": coupled.kinematic_length_weighted_rms,
        "solved_dipole_coefficient": coupled.dipole_coefficient,
        "bem_condition_number": coupled.solution.condition_number,
        "body_pressure_min": float(np.min(coupled.body_pressure_coefficient)),
        "body_pressure_max": float(np.max(coupled.body_pressure_coefficient)),
        "body_vertical_force_coefficient": coupled.body_vertical_force_coefficient,
        "interface_s_lambda": root.s_lambda,
        "measured_s_lambda": measured.s_lambda,
        "root_thickness": root.thickness,
        "root_xi": float(coupled.outer_free_surface.node_xi[0]),
        "root_eta": float(coupled.outer_free_surface.node_eta[0]),
    }
    exact_integral = getattr(coupled, "kinematic_integral_linear_exact", None)
    if exact_integral is not None:
        metrics["kinematic_integral_linear_exact"] = exact_integral
    return metrics


@dataclass(frozen=True)
class SelfSimilarCoupledCheckpoint:
    source_directory: Path
    source_kind: str
    config: SelfSimilarWedgeConfig
    coupled: SelfSimilarShallowJetCoupledResult
    history: pd.DataFrame
    outer_shape_dipole_coefficient: float
    completed_iterations: int
    cumulative_pseudo_time: float
    source_hashes: dict[str, str]
    reconstruction_relative_errors: dict[str, float]
    continuation_config_overrides: dict[str, Any]


@dataclass(frozen=True)
class SelfSimilarCheckpointRegridResult:
    coupled: SelfSimilarShallowJetCoupledResult
    source_panel_count: int
    target_panel_count: int
    source_panel_growth: float
    target_panel_growth: float
    source_far_radius: float
    target_far_radius: float
    source_grid_mode: str
    target_grid_mode: str
    target_root_spacing_ratio: float
    target_far_spacing_ratio: float
    target_endpoint_decay: float
    monitor_used: bool
    monitor_residual_weight: float | None
    monitor_curvature_weight: float | None
    monitor_growth_weight: float | None
    monitor_smoothing_passes: int | None
    monitor_maximum_node_shift_panels: float | None
    target_jet_bie_panel_count: int | None
    source_jet_terminal_closure: str
    target_jet_terminal_closure: str
    target_far_field_panels: int
    target_symmetry_panels: int
    asymptotic_extension_used: bool
    source_linear_gradient_recovery: str
    target_linear_gradient_recovery: str
    source_linear_corner_treatment: str
    target_linear_corner_treatment: str
    source_linear_far_corner_treatment: str
    target_linear_far_corner_treatment: str
    source_linear_cusp_velocity_recovery: str
    target_linear_cusp_velocity_recovery: str
    source_free_surface_update: str
    target_free_surface_update: str
    source_root_state_recovery: str
    target_root_state_recovery: str
    production_maintenance_maximum_midpoint_displacement_ratio: float
    production_maintenance_maximum_node_displacement: float
    post_maintenance_maximum_midpoint_displacement_ratio: float
    post_maintenance_maximum_node_displacement: float
    geometry_relative_l2: float
    geometry_maximum_absolute_error: float
    state_relative_changes: dict[str, float]


@dataclass(frozen=True)
class SelfSimilarCheckpointAccelerationResult:
    coupled: SelfSimilarShallowJetCoupledResult
    time_interval_ratio: float
    vector_convergence_factor: float
    raw_extrapolation_factor: float
    extrapolation_factor: float
    extrapolation_was_clipped: bool
    maximum_node_displacement_ratio: float
    residual_ratio: float
    legacy_unweighted_rms_ratio: float
    condition_number_ratio: float
    source_pseudo_times: tuple[float, float, float]
    source_pseudo_time_basis: str
    source_matching_surface_phases: tuple[int, int, int]
    source_modal_cycle_lengths: tuple[int, int, int]
    source_matching_surface_reset_counts: tuple[int, int, int]


def _outer_nodes_from_legacy_boundary(
    path: Path,
    *,
    far_radius: float,
) -> np.ndarray:
    frame = pd.read_csv(path)
    if not {"xi", "eta"}.issubset(frame.columns):
        raise ValueError("Legacy coupled boundary nodes require xi and eta columns.")
    coordinates = frame.loc[:, ["xi", "eta"]].to_numpy(dtype=float)
    if not np.isfinite(coordinates).all():
        raise ValueError("Legacy coupled boundary nodes must be finite.")
    radius = np.linalg.norm(coordinates, axis=1)
    far = np.flatnonzero(
        np.isclose(radius, float(far_radius), rtol=0.0, atol=1.0e-9)
    )
    if len(far) == 0:
        raise ValueError("The outer free-surface endpoint was not found on the far circle.")
    outer = coordinates[: int(far[0]) + 1]
    if len(outer) < 5:
        raise ValueError("A checkpoint requires at least five outer free-surface nodes.")
    return outer


def _verification_errors(
    actual: dict[str, float],
    expected: dict[str, float],
) -> dict[str, float]:
    errors: dict[str, float] = {}
    for name, expected_value in expected.items():
        if name not in actual:
            continue
        scale = max(abs(float(expected_value)), 1.0)
        errors[name] = abs(actual[name] - float(expected_value)) / scale
    return errors


def load_coupled_self_similar_checkpoint(
    directory: str | Path,
    *,
    verification_tolerance: float = 1.0e-6,
    continuation_config_overrides: Mapping[str, Any] | None = None,
) -> SelfSimilarCoupledCheckpoint:
    source = Path(directory).resolve()
    formal = source / "coupled_checkpoint.json"
    source_hashes: dict[str, str]
    if formal.exists():
        metadata = json.loads(formal.read_text(encoding="utf-8"))
        if int(metadata.get("schema_version", -1)) != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("Unsupported coupled checkpoint schema version.")
        files = metadata["files"]
        outer_path = source / files["outer_nodes"]["name"]
        history_path = source / files["history"]["name"]
        for name, path in (("outer_nodes", outer_path), ("history", history_path)):
            expected_hash = files[name]["sha256"]
            if _sha256(path) != expected_hash:
                raise ValueError(f"Checkpoint {name} SHA-256 does not match metadata.")
        outer_frame = pd.read_csv(outer_path, float_precision="round_trip")
        if not {"xi", "eta"}.issubset(outer_frame.columns):
            raise ValueError("Checkpoint outer nodes require xi and eta columns.")
        outer_nodes = outer_frame.loc[:, ["xi", "eta"]].to_numpy(dtype=float)
        config_data = dict(metadata["config"])
        outer_shape_dipole = float(metadata["outer_shape_dipole_coefficient"])
        interface_s_lambda = float(metadata["expected_state"]["interface_s_lambda"])
        expected_state = {
            key: float(value) for key, value in metadata["expected_state"].items()
        }
        source_hashes = {
            "coupled_checkpoint.json": _sha256(formal),
            outer_path.name: _sha256(outer_path),
            history_path.name: _sha256(history_path),
        }
        source_kind = "formal_v1"
    else:
        summary_path = source / "summary.json"
        boundary_path = source / "coupled_boundary_nodes.csv"
        history_path = source / "coupled_pseudo_time_history.csv"
        for path in (summary_path, boundary_path, history_path):
            if not path.exists():
                raise ValueError(f"Missing legacy checkpoint file: {path.name}.")
        metadata = json.loads(summary_path.read_text(encoding="utf-8"))
        config_data = dict(metadata["config"])
        outer_nodes = _outer_nodes_from_legacy_boundary(
            boundary_path,
            far_radius=float(config_data["far_radius"]),
        )
        coupling = metadata["shallow_water_coupling"]
        expected_state = {
            "kinematic_rms": float(coupling["augmented_bie"]["outer_kinematic_rms"]),
            "solved_dipole_coefficient": float(
                coupling["augmented_bie"]["dipole_coefficient"]
            ),
            "bem_condition_number": float(
                coupling["augmented_bie"]["condition_number"]
            ),
            "body_pressure_min": float(coupling["augmented_bie"]["body_pressure_min"]),
            "body_pressure_max": float(coupling["augmented_bie"]["body_pressure_max"]),
            "body_vertical_force_coefficient": float(
                coupling["augmented_bie"]["body_vertical_force_coefficient"]
            ),
            "interface_s_lambda": float(coupling["final_root_state"]["s_lambda"]),
            "measured_s_lambda": float(
                coupling["final_measured_root_state"]["s_lambda"]
            ),
            "root_thickness": float(coupling["final_root_state"]["thickness"]),
            "root_xi": float(coupling["final_root_state"]["free_root_xi"]),
            "root_eta": float(coupling["final_root_state"]["free_root_eta"]),
        }
        interface_s_lambda = expected_state["interface_s_lambda"]
        source_hashes = {
            summary_path.name: _sha256(summary_path),
            boundary_path.name: _sha256(boundary_path),
            history_path.name: _sha256(history_path),
        }
        source_kind = "legacy_probe_output"

    history = _validated_history(pd.read_csv(history_path))
    if source_kind == "legacy_probe_output":
        outer_shape_dipole = float(history.iloc[-2]["dipole_coefficient"])
    overrides = dict(continuation_config_overrides or {})
    unsupported = sorted(set(overrides) - CONTINUATION_OVERRIDE_FIELDS)
    if unsupported:
        raise ValueError(
            "Checkpoint continuation may only override "
            f"{sorted(CONTINUATION_OVERRIDE_FIELDS)}; received {unsupported}."
        )
    config_data.update(overrides)
    config = SelfSimilarWedgeConfig(**config_data)
    coupled_config = replace(config, jet_closure="truncated_control")
    coupled = _build_coupled_solution_from_outer_nodes(
        coupled_config,
        outer_nodes,
        outer_shape_dipole,
        root_inner_iterations=0,
        s_lambda_seed=interface_s_lambda,
    )
    actual_state = _state_metrics(coupled)
    errors = _verification_errors(actual_state, expected_state)
    if not errors or max(errors.values()) > float(verification_tolerance):
        raise ValueError(
            "Checkpoint reconstruction did not reproduce the frozen state: "
            f"max relative error={max(errors.values(), default=np.inf):.6g}."
        )
    last = history.iloc[-1]
    history_errors = {
        "history_kinematic_rms": abs(
            float(last["kinematic_rms"]) - coupled.kinematic_rms
        )
        / max(abs(coupled.kinematic_rms), 1.0),
        "history_solved_dipole": abs(
            float(last["dipole_coefficient"]) - coupled.dipole_coefficient
        )
        / max(abs(coupled.dipole_coefficient), 1.0),
        "history_interface_s_lambda": abs(
            float(last["root_s_lambda"])
            - coupled.jet_interface.root_state.s_lambda
        )
        / max(abs(coupled.jet_interface.root_state.s_lambda), 1.0),
    }
    if max(history_errors.values()) > float(verification_tolerance):
        raise ValueError("Checkpoint history final row disagrees with reconstructed state.")
    errors.update(history_errors)
    return SelfSimilarCoupledCheckpoint(
        source_directory=source,
        source_kind=source_kind,
        config=coupled_config,
        coupled=coupled,
        history=history,
        outer_shape_dipole_coefficient=outer_shape_dipole,
        completed_iterations=int(last["iteration"]),
        cumulative_pseudo_time=float(last["pseudo_time"]),
        source_hashes=source_hashes,
        reconstruction_relative_errors=errors,
        continuation_config_overrides=overrides,
    )


def _extend_outer_free_surface_to_radius(
    source_nodes: np.ndarray,
    *,
    source_radius: float,
    target_radius: float,
    dipole_coefficient: float,
) -> tuple[np.ndarray, bool]:
    """Append a C1 tail that relaxes smoothly toward Iafrati Eq. (51)."""

    source = np.asarray(source_nodes, dtype=float)
    if target_radius < source_radius - 1.0e-10 * source_radius:
        raise ValueError("target_far_radius cannot be smaller than the source radius.")
    if np.isclose(target_radius, source_radius, rtol=0.0, atol=1.0e-10):
        return source.copy(), False
    coefficient = float(dipole_coefficient)
    if not np.isfinite(coefficient) or coefficient <= 0.0:
        raise ValueError("Far-domain extension requires a positive dipole coefficient.")
    x0, y0 = (float(value) for value in source[-1])
    if x0 <= 0.0 or np.any(np.diff(source[:, 0]) <= 0.0):
        raise ValueError("Far-domain extension requires outward-monotone xi nodes.")

    def asymptotic_eta(xi: float) -> float:
        return coefficient / (3.0 * xi**2)

    tail_count = min(8, len(source))
    source_slope = float(
        CubicSpline(
            source[-tail_count:, 0],
            source[-tail_count:, 1],
            bc_type="natural",
        )(x0, 1)
    )
    asymptotic_y0 = asymptotic_eta(x0)
    asymptotic_slope0 = float(-2.0 * coefficient / (3.0 * x0**3))
    amplitude = y0 - asymptotic_y0
    decay_length = max(0.5 * source_radius, target_radius - source_radius)
    slope_amplitude = source_slope - asymptotic_slope0 + amplitude / decay_length

    def transition_eta(xi: float | np.ndarray) -> float | np.ndarray:
        distance = np.asarray(xi) - x0
        correction = np.exp(-distance / decay_length) * (
            amplitude + slope_amplitude * distance
        )
        return coefficient / (3.0 * np.square(xi)) + correction

    def circle_residual(xi: float) -> float:
        return xi**2 + float(transition_eta(xi)) ** 2 - target_radius**2

    x1 = float(
        brentq(
            circle_residual,
            max(x0, np.sqrt(np.finfo(float).eps)),
            target_radius,
            xtol=1.0e-13,
            rtol=1.0e-13,
        )
    )
    y1 = float(transition_eta(x1))
    source_panel = np.linalg.norm(np.diff(source, axis=0), axis=1)
    tail_panel = source_panel[-min(8, len(source_panel)) :]
    target_step = max(float(np.median(tail_panel)), 0.05)
    extension_panels = max(16, int(np.ceil((x1 - x0) / target_step)))
    extension_x = np.linspace(x0, x1, extension_panels + 1)[1:]
    extension = np.column_stack((extension_x, transition_eta(extension_x)))
    extension[-1] = np.asarray([x1, y1])
    return np.vstack((source, extension)), True


def _maximum_midpoint_displacement_ratio(
    source_nodes: np.ndarray,
    candidate_nodes: np.ndarray,
) -> float:
    """Return the largest panel-midpoint shift in source-panel lengths."""

    source = np.asarray(source_nodes, dtype=float)
    candidate = np.asarray(candidate_nodes, dtype=float)
    if (
        source.ndim != 2
        or candidate.ndim != 2
        or source.shape[1:] != (2,)
        or candidate.shape[1:] != (2,)
        or len(source) < 2
        or len(candidate) < 2
    ):
        raise ValueError("Displacement ratio requires two planar node arrays.")
    panel_length = np.linalg.norm(np.diff(source, axis=0), axis=1)
    if np.any(panel_length <= np.finfo(float).eps):
        raise ValueError("Displacement ratio requires positive source panel lengths.")
    aligned_candidate = _align_candidate_to_source_nodes(source, candidate)
    source_midpoint = 0.5 * (source[:-1] + source[1:])
    candidate_midpoint = 0.5 * (
        aligned_candidate[:-1] + aligned_candidate[1:]
    )
    return float(
        np.max(
            np.linalg.norm(candidate_midpoint - source_midpoint, axis=1)
            / panel_length
        )
    )


def _align_candidate_to_source_nodes(
    source_nodes: np.ndarray,
    candidate_nodes: np.ndarray,
) -> np.ndarray:
    """Represent a candidate curve at the source normalized arc coordinates."""

    source = np.asarray(source_nodes, dtype=float)
    candidate = np.asarray(candidate_nodes, dtype=float)
    if source.shape == candidate.shape:
        return candidate
    source_length = np.linalg.norm(np.diff(source, axis=0), axis=1)
    candidate_length = np.linalg.norm(np.diff(candidate, axis=0), axis=1)
    if (
        np.any(source_length <= np.finfo(float).eps)
        or np.any(candidate_length <= np.finfo(float).eps)
    ):
        raise ValueError("Curve alignment requires positive panel lengths.")
    source_fraction = np.concatenate(([0.0], np.cumsum(source_length)))
    source_fraction /= source_fraction[-1]
    candidate_fraction = np.concatenate(([0.0], np.cumsum(candidate_length)))
    candidate_fraction /= candidate_fraction[-1]
    return np.column_stack(
        (
            CubicSpline(candidate_fraction, candidate[:, 0], bc_type="natural")(
                source_fraction
            ),
            CubicSpline(candidate_fraction, candidate[:, 1], bc_type="natural")(
                source_fraction
            ),
        )
    )


def regrid_coupled_self_similar_checkpoint(
    checkpoint: SelfSimilarCoupledCheckpoint,
    target_panel_count: int,
    *,
    root_inner_iterations: int = 0,
    root_state_recovery: str | None = None,
    target_far_radius: float | None = None,
    grid_mode: str | None = None,
    root_spacing_ratio: float | None = None,
    far_spacing_ratio: float | None = None,
    endpoint_decay: float | None = None,
    far_field_panels: int | None = None,
    symmetry_panels: int | None = None,
    linear_gradient_recovery: str | None = None,
    linear_corner_treatment: str | None = None,
    linear_far_corner_treatment: str | None = None,
    linear_cusp_velocity_recovery: str | None = None,
    free_surface_update: str | None = None,
    monitor_residual_weight: float | None = None,
    monitor_curvature_weight: float = 0.25,
    monitor_growth_weight: float = 0.15,
    monitor_smoothing_passes: int = 2,
    monitor_maximum_node_shift_panels: float = 2.0,
    jet_bie_panel_count: int | None = None,
    jet_terminal_closure: str | None = None,
) -> SelfSimilarCheckpointRegridResult:
    """Rebuild a frozen state with independent endpoint and domain controls.

    A larger far circle is initialized by a slope-continuous transition to
    Iafrati Eq. (51). The transformed curve is then passed through the same
    geometry-maintenance operator used by production pseudo-time marching so
    the rebuilt checkpoint is a production-consistent state. This declared
    transformation never reads benchmark values and is not an exact resume.
    """

    target_count = int(target_panel_count)
    if target_count < 12:
        raise ValueError("A regridded outer free surface requires at least 12 panels.")
    if int(root_inner_iterations) < 0:
        raise ValueError("root_inner_iterations must be non-negative.")
    source_nodes = np.column_stack(
        (
            checkpoint.coupled.outer_free_surface.node_xi,
            checkpoint.coupled.outer_free_surface.node_eta,
        )
    )
    source_count = len(source_nodes) - 1
    segment = np.linalg.norm(np.diff(source_nodes, axis=0), axis=1)
    if np.any(segment <= 1.0e-12):
        raise ValueError("The frozen outer free surface contains a zero-length panel.")
    source_arc = np.concatenate(([0.0], np.cumsum(segment)))
    source_growth = float(checkpoint.config.free_surface_panel_growth)
    target_growth = source_growth ** (source_count / target_count)
    source_radius = float(checkpoint.config.far_radius)
    target_radius = source_radius if target_far_radius is None else float(target_far_radius)
    if target_radius <= 8.0:
        raise ValueError("target_far_radius must exceed eight similarity lengths.")
    target_mode = checkpoint.config.coupled_outer_grid_mode if grid_mode is None else str(grid_mode)
    if grid_mode is None and any(
        value is not None
        for value in (root_spacing_ratio, far_spacing_ratio, endpoint_decay)
    ):
        target_mode = "double_ended"
    target_root_ratio = float(
        checkpoint.config.coupled_outer_root_spacing_ratio
        if root_spacing_ratio is None
        else root_spacing_ratio
    )
    target_far_ratio = float(
        checkpoint.config.coupled_outer_far_spacing_ratio
        if far_spacing_ratio is None
        else far_spacing_ratio
    )
    target_decay = float(
        checkpoint.config.coupled_outer_endpoint_decay
        if endpoint_decay is None
        else endpoint_decay
    )
    radius_ratio = target_radius / source_radius
    target_far_panels = int(
        max(8, round(checkpoint.config.far_field_panels * radius_ratio))
        if far_field_panels is None
        else far_field_panels
    )
    target_symmetry_panels = int(
        max(4, round(checkpoint.config.symmetry_panels * radius_ratio))
        if symmetry_panels is None
        else symmetry_panels
    )
    target_monitor_fractions: tuple[float, ...] | None = None
    if monitor_residual_weight is not None:
        target_mode = "frozen_monitor"
        target_monitor_fractions = tuple(
            float(value)
            for value in build_residual_curvature_monitor_fractions(
                checkpoint.coupled,
                target_count,
                root_spacing_ratio=target_root_ratio,
                far_spacing_ratio=target_far_ratio,
                endpoint_decay=target_decay,
                residual_weight=float(monitor_residual_weight),
                curvature_weight=float(monitor_curvature_weight),
                growth_weight=float(monitor_growth_weight),
                smoothing_passes=int(monitor_smoothing_passes),
                maximum_node_shift_panels=float(
                    monitor_maximum_node_shift_panels
                ),
            )
        )
    elif target_mode == "frozen_monitor":
        source_monitor = checkpoint.config.coupled_outer_monitor_fractions
        if source_monitor is None or len(source_monitor) != target_count + 1:
            raise ValueError(
                "frozen_monitor regridding requires monitor weights when the "
                "source fractions cannot be reused."
            )
        target_monitor_fractions = tuple(source_monitor)

    target_jet_bie_panel_count = (
        checkpoint.config.coupled_jet_bie_panel_count
        if jet_bie_panel_count is None
        else int(jet_bie_panel_count)
    )
    if target_jet_bie_panel_count is not None and target_jet_bie_panel_count < 2:
        raise ValueError("jet_bie_panel_count must be at least two when set.")
    if target_mode == "frozen_monitor" and target_jet_bie_panel_count is None:
        source_labels = np.asarray(
            checkpoint.coupled.boundary.panel_labels,
            dtype=object,
        )
        target_jet_bie_panel_count = int(
            np.count_nonzero(source_labels == "shallow_jet_body")
        )
        if target_jet_bie_panel_count < 2:
            raise ValueError(
                "A monitored regrid could not infer a resolved source jet topology."
            )

    target_config = replace(
        checkpoint.config,
        far_radius=target_radius,
        free_surface_panels=target_count,
        free_surface_panel_growth=target_growth,
        far_field_panels=target_far_panels,
        symmetry_panels=target_symmetry_panels,
        coupled_outer_grid_mode=target_mode,
        coupled_outer_root_spacing_ratio=target_root_ratio,
        coupled_outer_far_spacing_ratio=target_far_ratio,
        coupled_outer_endpoint_decay=target_decay,
        coupled_outer_monitor_fractions=target_monitor_fractions,
        coupled_jet_bie_panel_count=target_jet_bie_panel_count,
        coupled_jet_terminal_closure=(
            checkpoint.config.coupled_jet_terminal_closure
            if jet_terminal_closure is None
            else str(jet_terminal_closure)
        ),
        coupled_linear_gradient_recovery=(
            checkpoint.config.coupled_linear_gradient_recovery
            if linear_gradient_recovery is None
            else linear_gradient_recovery
        ),
        coupled_linear_corner_treatment=(
            checkpoint.config.coupled_linear_corner_treatment
            if linear_corner_treatment is None
            else linear_corner_treatment
        ),
        coupled_linear_far_corner_treatment=(
            checkpoint.config.coupled_linear_far_corner_treatment
            if linear_far_corner_treatment is None
            else linear_far_corner_treatment
        ),
        coupled_linear_cusp_velocity_recovery=(
            checkpoint.config.coupled_linear_cusp_velocity_recovery
            if linear_cusp_velocity_recovery is None
            else linear_cusp_velocity_recovery
        ),
        coupled_free_surface_update=(
            checkpoint.config.coupled_free_surface_update
            if free_surface_update is None
            else free_surface_update
        ),
        coupled_root_state_recovery=(
            checkpoint.config.coupled_root_state_recovery
            if root_state_recovery is None
            else root_state_recovery
        ),
    )
    working_nodes, extension_used = _extend_outer_free_surface_to_radius(
        source_nodes,
        source_radius=source_radius,
        target_radius=target_radius,
        dipole_coefficient=checkpoint.outer_shape_dipole_coefficient,
    )
    working_segment = np.linalg.norm(np.diff(working_nodes, axis=0), axis=1)
    working_arc = np.concatenate(([0.0], np.cumsum(working_segment)))
    unchanged_grid = (
        target_count == source_count
        and not extension_used
        and target_mode == checkpoint.config.coupled_outer_grid_mode
        and np.isclose(target_root_ratio, checkpoint.config.coupled_outer_root_spacing_ratio)
        and np.isclose(target_far_ratio, checkpoint.config.coupled_outer_far_spacing_ratio)
        and np.isclose(target_decay, checkpoint.config.coupled_outer_endpoint_decay)
        and target_monitor_fractions
        == checkpoint.config.coupled_outer_monitor_fractions
    )
    if unchanged_grid:
        target_arc = source_arc.copy()
        target_nodes = source_nodes.copy()
    else:
        target_arc = working_arc[-1] * _outer_panel_fractions(target_config)
        target_nodes = np.column_stack(
            (
                CubicSpline(working_arc, working_nodes[:, 0], bc_type="natural")(
                    target_arc
                ),
                CubicSpline(working_arc, working_nodes[:, 1], bc_type="natural")(
                    target_arc
                ),
            )
        )
        target_nodes[[0, -1]] = working_nodes[[0, -1]]

    pre_maintenance_nodes = target_nodes.copy()
    target_nodes = _regrid_coupled_outer_nodes(target_config, target_nodes)
    production_maintenance_ratio = _maximum_midpoint_displacement_ratio(
        pre_maintenance_nodes,
        target_nodes,
    )
    aligned_target_nodes = _align_candidate_to_source_nodes(
        pre_maintenance_nodes,
        target_nodes,
    )
    production_maintenance_maximum_node_displacement = float(
        np.max(
            np.linalg.norm(
                aligned_target_nodes - pre_maintenance_nodes,
                axis=1,
            )
        )
    )
    post_maintenance_nodes = _regrid_coupled_outer_nodes(target_config, target_nodes)
    post_maintenance_ratio = _maximum_midpoint_displacement_ratio(
        target_nodes,
        post_maintenance_nodes,
    )
    aligned_post_maintenance_nodes = _align_candidate_to_source_nodes(
        target_nodes,
        post_maintenance_nodes,
    )
    post_maintenance_maximum_node_displacement = float(
        np.max(
            np.linalg.norm(
                aligned_post_maintenance_nodes - target_nodes,
                axis=1,
            )
        )
    )

    target_segment = np.linalg.norm(np.diff(target_nodes, axis=0), axis=1)
    target_arc = np.concatenate(([0.0], np.cumsum(target_segment)))
    represented_source = np.column_stack(
        (
            np.interp(source_arc, target_arc, target_nodes[:, 0]),
            np.interp(source_arc, target_arc, target_nodes[:, 1]),
        )
    )
    difference = represented_source - source_nodes
    geometry_relative_l2 = float(
        np.linalg.norm(difference)
        / max(np.linalg.norm(source_nodes), np.finfo(float).eps)
    )
    geometry_maximum_absolute_error = float(
        np.max(np.linalg.norm(difference, axis=1))
    )
    rebuilt = _build_coupled_solution_from_outer_nodes(
        target_config,
        target_nodes,
        checkpoint.outer_shape_dipole_coefficient,
        root_inner_iterations=int(root_inner_iterations),
        s_lambda_seed=checkpoint.coupled.jet_interface.root_state.s_lambda,
    )
    source_state = _state_metrics(checkpoint.coupled)
    rebuilt_state = _state_metrics(rebuilt)
    state_relative_changes = {
        name: abs(rebuilt_state[name] - source_state[name])
        / max(abs(source_state[name]), 1.0)
        for name in source_state
    }
    return SelfSimilarCheckpointRegridResult(
        coupled=rebuilt,
        source_panel_count=source_count,
        target_panel_count=target_count,
        source_panel_growth=source_growth,
        target_panel_growth=target_growth,
        source_far_radius=source_radius,
        target_far_radius=target_radius,
        source_grid_mode=checkpoint.config.coupled_outer_grid_mode,
        target_grid_mode=target_mode,
        target_root_spacing_ratio=target_root_ratio,
        target_far_spacing_ratio=target_far_ratio,
        target_endpoint_decay=target_decay,
        monitor_used=target_mode == "frozen_monitor",
        monitor_residual_weight=(
            None
            if monitor_residual_weight is None
            else float(monitor_residual_weight)
        ),
        monitor_curvature_weight=(
            None
            if monitor_residual_weight is None
            else float(monitor_curvature_weight)
        ),
        monitor_growth_weight=(
            None
            if monitor_residual_weight is None
            else float(monitor_growth_weight)
        ),
        monitor_smoothing_passes=(
            None
            if monitor_residual_weight is None
            else int(monitor_smoothing_passes)
        ),
        monitor_maximum_node_shift_panels=(
            None
            if monitor_residual_weight is None
            else float(monitor_maximum_node_shift_panels)
        ),
        target_jet_bie_panel_count=target_jet_bie_panel_count,
        source_jet_terminal_closure=(
            checkpoint.config.coupled_jet_terminal_closure
        ),
        target_jet_terminal_closure=target_config.coupled_jet_terminal_closure,
        target_far_field_panels=target_far_panels,
        target_symmetry_panels=target_symmetry_panels,
        asymptotic_extension_used=extension_used,
        source_linear_gradient_recovery=(
            checkpoint.config.coupled_linear_gradient_recovery
        ),
        target_linear_gradient_recovery=(
            target_config.coupled_linear_gradient_recovery
        ),
        source_linear_corner_treatment=(
            checkpoint.config.coupled_linear_corner_treatment
        ),
        target_linear_corner_treatment=(
            target_config.coupled_linear_corner_treatment
        ),
        source_linear_far_corner_treatment=(
            checkpoint.config.coupled_linear_far_corner_treatment
        ),
        target_linear_far_corner_treatment=(
            target_config.coupled_linear_far_corner_treatment
        ),
        source_linear_cusp_velocity_recovery=(
            checkpoint.config.coupled_linear_cusp_velocity_recovery
        ),
        target_linear_cusp_velocity_recovery=(
            target_config.coupled_linear_cusp_velocity_recovery
        ),
        source_free_surface_update=(
            checkpoint.config.coupled_free_surface_update
        ),
        target_free_surface_update=target_config.coupled_free_surface_update,
        source_root_state_recovery=checkpoint.config.coupled_root_state_recovery,
        target_root_state_recovery=target_config.coupled_root_state_recovery,
        production_maintenance_maximum_midpoint_displacement_ratio=(
            production_maintenance_ratio
        ),
        production_maintenance_maximum_node_displacement=(
            production_maintenance_maximum_node_displacement
        ),
        post_maintenance_maximum_midpoint_displacement_ratio=(
            post_maintenance_ratio
        ),
        post_maintenance_maximum_node_displacement=(
            post_maintenance_maximum_node_displacement
        ),
        geometry_relative_l2=geometry_relative_l2,
        geometry_maximum_absolute_error=geometry_maximum_absolute_error,
        state_relative_changes=state_relative_changes,
    )


def _acceleration_source_pseudo_times(
    checkpoints: tuple[
        SelfSimilarCoupledCheckpoint,
        SelfSimilarCoupledCheckpoint,
        SelfSimilarCoupledCheckpoint,
    ],
) -> tuple[tuple[float, float, float], str]:
    """Recover comparable source times from global or parent-linked local histories."""

    reported = tuple(float(item.cumulative_pseudo_time) for item in checkpoints)
    source_directories = [
        Path(item.source_directory).resolve()
        if getattr(item, "source_directory", None) is not None
        else None
        for item in checkpoints
    ]
    direct_parent_chain = all(path is not None for path in source_directories)
    if direct_parent_chain:
        for index in (1, 2):
            metadata_path = source_directories[index] / "coupled_checkpoint.json"
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                parent_path = Path(metadata["parent_checkpoint"]["path"]).resolve()
            except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
                direct_parent_chain = False
                break
            if parent_path != source_directories[index - 1]:
                direct_parent_chain = False
                break

    completed = (
        tuple(int(item.completed_iterations) for item in checkpoints)
        if direct_parent_chain
        else ()
    )
    if direct_parent_chain and not (completed[0] < completed[1] < completed[2]):
        first_interval = reported[1]
        second_interval = reported[2]
        if first_interval <= 0.0 or second_interval <= 0.0:
            raise ValueError(
                "Parent-linked Aitken segment durations must be strictly positive."
            )
        return (
            (0.0, first_interval, first_interval + second_interval),
            "direct_parent_local_segment_durations",
        )
    return reported, "reported_cumulative_pseudo_time"


def accelerate_coupled_self_similar_checkpoints(
    checkpoints: tuple[
        SelfSimilarCoupledCheckpoint,
        SelfSimilarCoupledCheckpoint,
        SelfSimilarCoupledCheckpoint,
    ],
    *,
    maximum_convergence_factor: float = 0.9,
    maximum_interval_ratio: float = 1.25,
    maximum_displacement_ratio: float = 4.0,
    maximum_residual_ratio: float = 0.9,
    maximum_condition_ratio: float = 5.0,
    clip_extrapolation_to_displacement_limit: bool = False,
) -> SelfSimilarCheckpointAccelerationResult:
    """Apply a qualified vector Aitken extrapolation to three frozen states.

    Only the evolving outer free surface, previous shape dipole, and supplied
    jet-root state are extrapolated. Reference curves are not read. The
    candidate must rebuild a physical augmented BIE and reduce its kinematic
    residual before it is returned.
    """

    if len(checkpoints) != 3:
        raise ValueError("Vector Aitken acceleration requires three checkpoints.")
    configurations = []
    for checkpoint in checkpoints:
        data = asdict(checkpoint.config)
        data.pop("pseudo_cfl", None)
        configurations.append(data)
    if configurations[1:] != configurations[:-1]:
        raise ValueError(
            "Aitken source checkpoints must share grid and physical configuration."
        )
    matching_phases = tuple(
        infer_matching_surface_phase(checkpoint.history)
        for checkpoint in checkpoints
    )
    source_phase_indices = tuple(item.phase_index for item in matching_phases)
    source_modal_periods = tuple(
        item.modal_cycle_length for item in matching_phases
    )
    if len(set(source_modal_periods)) != 1 or len(set(source_phase_indices)) != 1:
        raise ValueError(
            "Aitken source checkpoints are not matching-surface phase aligned: "
            f"phases={list(source_phase_indices)}, "
            f"modal_periods={list(source_modal_periods)}."
        )
    times, time_basis = _acceleration_source_pseudo_times(checkpoints)
    intervals = np.diff(np.asarray(times, dtype=float))
    if np.any(intervals <= 0.0):
        raise ValueError("Aitken source pseudo-times must increase strictly.")
    interval_ratio = float(max(intervals) / min(intervals))
    if interval_ratio > float(maximum_interval_ratio):
        raise ValueError(
            "Aitken source pseudo-time intervals are not sufficiently matched: "
            f"ratio={interval_ratio:.6g}."
        )
    nodes = [
        np.column_stack(
            (
                item.coupled.outer_free_surface.node_xi,
                item.coupled.outer_free_surface.node_eta,
            )
        )
        for item in checkpoints
    ]
    if nodes[0].shape != nodes[1].shape or nodes[1].shape != nodes[2].shape:
        raise ValueError("Aitken source checkpoints must share outer-node topology.")
    previous_increment = (nodes[1] - nodes[0]) * (intervals[1] / intervals[0])
    latest_increment = nodes[2] - nodes[1]
    denominator = float(np.sum(np.square(previous_increment)))
    if denominator <= np.finfo(float).eps:
        raise ValueError("Aitken source states do not contain a finite prior increment.")
    convergence_factor = float(
        np.sum(previous_increment * latest_increment) / denominator
    )
    if not 0.0 < convergence_factor <= float(maximum_convergence_factor):
        raise ValueError(
            "Aitken vector convergence factor is outside the qualified interval: "
            f"q={convergence_factor:.6g}."
        )
    raw_factor = convergence_factor / (1.0 - convergence_factor)
    panel_length = np.linalg.norm(np.diff(nodes[2], axis=0), axis=1)
    node_scale = np.concatenate(
        (
            [panel_length[0]],
            np.minimum(panel_length[:-1], panel_length[1:]),
            [panel_length[-1]],
        )
    )
    raw_node_displacement = raw_factor * latest_increment
    raw_node_displacement[-1] = 0.0
    raw_displacement_ratio = float(
        np.max(
            np.linalg.norm(raw_node_displacement, axis=1)
            / np.maximum(node_scale, np.finfo(float).eps)
        )
    )
    factor = raw_factor
    extrapolation_was_clipped = False
    if raw_displacement_ratio > float(maximum_displacement_ratio):
        if not bool(clip_extrapolation_to_displacement_limit):
            raise ValueError(
                "Aitken candidate exceeds the declared node-displacement limit: "
                f"ratio={raw_displacement_ratio:.6g}."
            )
        factor *= float(maximum_displacement_ratio) / raw_displacement_ratio
        extrapolation_was_clipped = True
    candidate_nodes = nodes[2] + factor * latest_increment
    candidate_nodes[-1] = nodes[2][-1]
    displacement_ratio = float(
        np.max(
            np.linalg.norm(candidate_nodes - nodes[2], axis=1)
            / np.maximum(node_scale, np.finfo(float).eps)
        )
    )
    shape_dipoles = np.asarray(
        [item.outer_shape_dipole_coefficient for item in checkpoints],
        dtype=float,
    )
    candidate_shape_dipole = float(
        shape_dipoles[2] + factor * (shape_dipoles[2] - shape_dipoles[1])
    )
    root_states = np.asarray(
        [item.coupled.jet_interface.root_state.s_lambda for item in checkpoints],
        dtype=float,
    )
    candidate_root = float(
        root_states[2] + factor * (root_states[2] - root_states[1])
    )
    if candidate_shape_dipole <= 0.0 or candidate_root <= 0.0:
        raise ValueError("Aitken extrapolation produced a non-positive physical state.")
    latest = checkpoints[2]
    accelerated = _build_coupled_solution_from_outer_nodes(
        latest.config,
        candidate_nodes,
        candidate_shape_dipole,
        root_inner_iterations=0,
        s_lambda_seed=candidate_root,
    )
    residual_ratio = (
        accelerated.kinematic_integral / latest.coupled.kinematic_integral
    )
    legacy_unweighted_rms_ratio = (
        accelerated.kinematic_rms / latest.coupled.kinematic_rms
    )
    condition_ratio = (
        accelerated.solution.condition_number
        / latest.coupled.solution.condition_number
    )
    if residual_ratio > float(maximum_residual_ratio):
        raise ValueError(
            "Aitken candidate did not reduce Iafrati Eq. (52) kinematic "
            "integral sufficiently: "
            f"ratio={residual_ratio:.6g}."
        )
    if condition_ratio > float(maximum_condition_ratio):
        raise ValueError(
            "Aitken candidate exceeded the condition-number limit: "
            f"ratio={condition_ratio:.6g}."
        )
    return SelfSimilarCheckpointAccelerationResult(
        coupled=accelerated,
        time_interval_ratio=interval_ratio,
        vector_convergence_factor=convergence_factor,
        raw_extrapolation_factor=raw_factor,
        extrapolation_factor=factor,
        extrapolation_was_clipped=extrapolation_was_clipped,
        maximum_node_displacement_ratio=displacement_ratio,
        residual_ratio=float(residual_ratio),
        legacy_unweighted_rms_ratio=float(legacy_unweighted_rms_ratio),
        condition_number_ratio=float(condition_ratio),
        source_pseudo_times=times,
        source_pseudo_time_basis=time_basis,
        source_matching_surface_phases=source_phase_indices,
        source_modal_cycle_lengths=source_modal_periods,
        source_matching_surface_reset_counts=tuple(
            item.reset_count for item in matching_phases
        ),
    )


def merge_coupled_checkpoint_history(
    checkpoint: SelfSimilarCoupledCheckpoint,
    continuation: SelfSimilarCoupledPseudoTimeResult,
) -> pd.DataFrame:
    child = coupled_pseudo_time_history_frame(continuation)
    parent_last = checkpoint.history.iloc[-1]
    child_first = child.iloc[0]
    for name in (
        "kinematic_rms",
        "dipole_coefficient",
        "root_thickness",
        "root_s_lambda",
        "root_measured_s_lambda",
        "root_relative_mismatch",
        "root_body_eta",
        "root_resolution_ratio",
        "bem_condition_number",
    ):
        if not np.isclose(
            float(parent_last[name]),
            float(child_first[name]),
            rtol=1.0e-8,
            atol=1.0e-10,
        ):
            raise ValueError(f"Continuation initial state disagrees in {name}.")
    appended = child.iloc[1:].copy()
    appended["iteration"] += checkpoint.completed_iterations
    appended["pseudo_time"] += checkpoint.cumulative_pseudo_time
    merged = pd.concat((checkpoint.history, appended), ignore_index=True)
    return _validated_history(merged)


def write_coupled_self_similar_checkpoint(
    directory: str | Path,
    coupled: SelfSimilarShallowJetCoupledResult,
    history: pd.DataFrame,
    *,
    parent: SelfSimilarCoupledCheckpoint | None = None,
    transformation: Mapping[str, Any] | None = None,
) -> Path:
    output = Path(directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    checked = _validated_history(history)
    if len(checked) == 1 and (parent is None or transformation is None):
        raise ValueError(
            "A zero-step checkpoint requires a parent checkpoint and an explicit "
            "state transformation."
        )
    outer_path = output / "coupled_checkpoint_outer_nodes.csv"
    history_path = output / "coupled_pseudo_time_history.csv"
    pd.DataFrame(
        {
            "xi": coupled.outer_free_surface.node_xi,
            "eta": coupled.outer_free_surface.node_eta,
        }
    ).to_csv(outer_path, index=False)
    checked.to_csv(history_path, index=False)
    if len(checked) >= 2:
        outer_shape_dipole = float(checked.iloc[-2]["dipole_coefficient"])
    elif transformation is not None and "outer_shape_dipole_coefficient" in transformation:
        outer_shape_dipole = float(transformation["outer_shape_dipole_coefficient"])
        if not np.isfinite(outer_shape_dipole) or outer_shape_dipole <= 0.0:
            raise ValueError(
                "Explicit transformed outer-shape dipole coefficient must be "
                "finite and positive."
            )
    else:
        outer_shape_dipole = float(parent.outer_shape_dipole_coefficient)
    metadata: dict[str, Any] = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "status": "self_similar_coupled_checkpoint_unvalidated",
        "config": asdict(coupled.config),
        "completed_iterations": int(checked.iloc[-1]["iteration"]),
        "cumulative_pseudo_time": float(checked.iloc[-1]["pseudo_time"]),
        "outer_shape_dipole_coefficient": outer_shape_dipole,
        "expected_state": _state_metrics(coupled),
        "files": {
            "outer_nodes": {
                "name": outer_path.name,
                "sha256": _sha256(outer_path),
            },
            "history": {
                "name": history_path.name,
                "sha256": _sha256(history_path),
            },
        },
        "reference_used_during_solve": False,
    }
    if parent is not None:
        metadata["parent_checkpoint"] = {
            "path": str(parent.source_directory),
            "kind": parent.source_kind,
            "completed_iterations": parent.completed_iterations,
            "source_hashes": parent.source_hashes,
            "continuation_config_overrides": (
                parent.continuation_config_overrides
            ),
        }
    if transformation is not None:
        metadata["state_transformation"] = dict(transformation)
    metadata_path = output / "coupled_checkpoint.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return metadata_path
