from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from planing_seakeeping.forced_motion_identification import (
    ForcedMotionMatrices,
    assemble_forced_motion_matrices,
    extract_forced_motion_column,
)
from planing_seakeeping.forced_motion_validation import (
    compare_sun2007_troesch,
    nondimensionalize_forced_motion_matrices,
)
from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import MovingWedgeConfig
from planing_seakeeping.kernels.nonlinear_2dt.planing_forced_motion import (
    PlaningForcedMotion2DtResult,
    PlaningForcedMotionCase,
    run_planing_forced_motion_2dt,
)
from planing_seakeeping.kernels.nonlinear_2dt.planing_restoring import (
    estimate_planing_restoring_matrix,
)


COEFFICIENT_INDEX = {
    "A33": ("added_mass", 0, 0),
    "A35": ("added_mass", 0, 1),
    "A53": ("added_mass", 1, 0),
    "A55": ("added_mass", 1, 1),
    "B33": ("damping", 0, 0),
    "B35": ("damping", 0, 1),
    "B53": ("damping", 1, 0),
    "B55": ("damping", 1, 1),
}

LONGITUDINAL_BIN_COMPONENTS = (
    "longitudinal_bin_aft_post_chine",
    "longitudinal_bin_middle_post_chine",
    "longitudinal_bin_forward_post_chine",
    "longitudinal_bin_pre_chine",
)
LOAD_COMPONENTS = (
    "raw_bem",
    "resolved_station_bem",
    "transom_extrapolation",
    "pre_chine_bem",
    "post_chine_bem",
    *LONGITUDINAL_BIN_COMPONENTS,
    "bem",
    "front",
    "transom",
    "total",
)


GROUND_PLANE_EVENT_METADATA_KEYS = (
    "contact_exit_removal_count",
    "transom_exit_removal_count",
    "forward_interval_exit_removal_count",
    "below_handoff_draft_removal_count",
    "fixed_plane_deferred_creation_count",
    "fixed_plane_expired_before_activation_count",
    "fixed_plane_pending_count_at_end",
    "fixed_plane_localized_activation_count",
    "fixed_plane_maximum_removed_time_quantization_s",
    "fixed_plane_activation_rule",
)


def _ground_plane_event_diagnostics(
    prefix: str,
    result: PlaningForcedMotion2DtResult,
) -> dict[str, object]:
    return {
        f"{prefix}_{key}": result.metadata[key]
        for key in GROUND_PLANE_EVENT_METADATA_KEYS
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_external_restoring_matrices(path: Path) -> dict[str, np.ndarray]:
    row_index = {"heave_force": 0, "pitch_moment": 1}
    column_index = {"heave": 0, "pitch": 1}
    matrices: dict[str, np.ndarray] = {}
    populated: dict[str, set[tuple[int, int]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"component", "row", "column", "value"}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(
                "External restoring matrix is missing columns: "
                + ", ".join(sorted(missing))
            )
        for source_row in reader:
            component = str(source_row["component"]).strip()
            if component not in LOAD_COMPONENTS:
                raise ValueError(f"Unknown restoring-matrix component: {component!r}.")
            row_label = str(source_row["row"]).strip()
            column_label = str(source_row["column"]).strip()
            if row_label not in row_index or column_label not in column_index:
                raise ValueError(
                    "Unknown restoring-matrix coordinate: "
                    f"row={row_label!r}, column={column_label!r}."
                )
            index = (row_index[row_label], column_index[column_label])
            component_cells = populated.setdefault(component, set())
            if index in component_cells:
                raise ValueError(
                    f"Duplicate restoring-matrix cell for {component}: "
                    f"{row_label}/{column_label}."
                )
            value = float(source_row["value"])
            if not math.isfinite(value):
                raise ValueError("External restoring-matrix values must be finite.")
            matrices.setdefault(component, np.zeros((2, 2), dtype=float))[index] = value
            component_cells.add(index)
    if not matrices:
        raise ValueError("External restoring matrix is empty.")
    incomplete = {
        component: sorted(set(np.ndindex(2, 2)).difference(cells))
        for component, cells in populated.items()
        if len(cells) != 4
    }
    if incomplete:
        raise ValueError(
            "Each listed restoring-matrix component must define all four cells: "
            f"{incomplete}."
        )
    if "total" not in matrices:
        raise ValueError("External restoring matrix must define the total component.")
    return matrices


def _jsonable_argument_snapshot(args: argparse.Namespace) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for name, value in vars(args).items():
        if isinstance(value, Path):
            snapshot[name] = str(value)
        else:
            snapshot[name] = value
    return snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute planing forced-motion coefficients with separated BEM/front loads. "
            "Defaults reproduce the Sun (2007) Troesch benchmark target."
        )
    )
    parser.add_argument(
        "--target-identifier",
        default="sun2007_troesch_prismatic_planing_hull",
    )
    parser.add_argument("--beam-m", type=float, default=0.318)
    parser.add_argument("--rho-water-kg-m3", type=float, default=1000.0)
    parser.add_argument("--gravity-m-s2", type=float, default=9.80665)
    parser.add_argument("--deadrise-deg", type=float, default=20.0)
    parser.add_argument("--trim-deg", type=float, default=4.0)
    parser.add_argument("--fn-b", type=float, default=2.5)
    parser.add_argument("--mean-wetted-length-over-beam", type=float, default=3.0)
    parser.add_argument("--chine-wetting-offset-over-beam", type=float, default=1.6)
    parser.add_argument("--keel-wetted-length-over-beam", type=float, default=None)
    parser.add_argument("--lcg-over-beam", type=float, default=1.47)
    parser.add_argument("--vcg-over-beam", type=float, default=0.65)
    parser.add_argument("--mean-draft-over-beam", type=float, default=0.266)
    parser.add_argument("--heave-amplitude-over-beam", type=float, default=0.036)
    parser.add_argument("--pitch-amplitude-deg", type=float, default=0.43)
    parser.add_argument("--sigmas", type=float, nargs="+", default=[1.4])
    parser.add_argument("--out", type=Path, default=Path("outputs/sun2007_forced_motion_probe"))
    parser.add_argument("--cycles", type=float, default=2.75)
    parser.add_argument("--discard-cycles", type=float, default=0.75)
    parser.add_argument("--retained-cycles", type=float, default=2.0)
    parser.add_argument("--section-planes", type=int, default=11)
    parser.add_argument("--bem-substeps-per-plane", type=int, default=8)
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=1,
        help="Parallelize independent Earth-fixed plane BVP solves within each time step.",
    )
    parser.add_argument(
        "--ground-plane-handoff-mode",
        choices=(
            "fixed_earth_grid",
            "fixed_earth_grid_scheduled_wagner",
            "constant_draft_event",
        ),
        default="fixed_earth_grid",
        help=(
            "Earth-fixed equal-spacing follows Sun Fig. 7.12. The scheduled_wagner "
            "variant starts each plane at the fixed introduction time with its actual "
            "positive draft; constant_draft_event is diagnostic only."
        ),
    )
    parser.add_argument(
        "--ground-plane-spacing-rule",
        choices=("keel_over_nx", "bem_interval_over_nx_minus_one"),
        default="keel_over_nx",
        help=(
            "keel_over_nx preserves the frozen production baseline. "
            "bem_interval_over_nx_minus_one places NX planes from the explicit "
            "Wagner/BEM handoff through the transom, matching Sun Fig. 7.10/7.12."
        ),
    )
    parser.add_argument("--body-panels", type=int, default=12)
    parser.add_argument("--free-surface-panels", type=int, default=15)
    parser.add_argument("--side-panels", type=int, default=6)
    parser.add_argument("--bottom-panels", type=int, default=18)
    parser.add_argument("--gauss-order", type=int, default=8)
    parser.add_argument(
        "--element-interpolation",
        choices=("constant_panel", "linear_node"),
        default="linear_node",
    )
    parser.add_argument(
        "--pressure-interpolation",
        choices=("match_potential", "constant_panel"),
        default="constant_panel",
    )
    parser.add_argument(
        "--symmetry-half-domain",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    transom_group = parser.add_mutually_exclusive_group()
    transom_group.add_argument(
        "--transom-correction",
        action="store_true",
        help="Use the local 0.1B analytical pressure patch from Sun Eqs. 7.19-7.22.",
    )
    transom_group.add_argument(
        "--transom-keel-reduction",
        action="store_true",
        help=(
            "Use Sun Sec. 7.3.1's fixed 0.5B effective keel-wetted-length "
            "reduction for the stern suction correction."
        ),
    )
    parser.add_argument(
        "--initial-leading-offset-beams",
        type=float,
        default=None,
        help=(
            "Wagner-to-BEM handoff distance from the wetted leading edge. "
            "Default: one Sun Fig. 7.12 ground-plane spacing, Lk/(B*NX). "
            "Its relation to plane spacing is selected explicitly by "
            "--ground-plane-spacing-rule."
        ),
    )
    motion_group = parser.add_mutually_exclusive_group()
    motion_group.add_argument("--heave-only", action="store_true")
    motion_group.add_argument("--pitch-only", action="store_true")
    parser.add_argument(
        "--write-station-timeseries",
        action="store_true",
        help=(
            "Write a long-form checkpoint of every resolved ground-plane load. "
            "This is intended for convergence diagnosis and does not alter the solver."
        ),
    )
    parser.add_argument(
        "--knuckle-separation-model",
        choices=("clamped", "artificial_surface"),
        default="artificial_surface",
        help=(
            "Sun Chapter 3/7 non-viscous separated artificial surface is the "
            "benchmark default; clamped is retained for explicit sensitivity tests."
        ),
    )
    parser.add_argument(
        "--jet-cut",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--jet-cut-distance-fraction", type=float, default=0.25)
    parser.add_argument(
        "--jet-cut-threshold-over-beam",
        type=float,
        default=None,
        help=(
            "Optional fixed physical jet-cut distance divided by beam. "
            "Use this for panel convergence so mesh refinement does not change the cut criterion."
        ),
    )
    parser.add_argument("--jet-cut-max-corrective-passes", type=int, default=8)
    parser.add_argument(
        "--free-surface-spacing-mode",
        choices=("uniform", "body_matched_geometric"),
        default="body_matched_geometric",
    )
    parser.add_argument(
        "--free-surface-remesh-updates-per-plane",
        type=int,
        default=0,
        help=(
            "Fix equal-arclength remeshing updates per ground-plane interval during "
            "time-step convergence. Zero retains remeshing every BEM step."
        ),
    )
    parser.add_argument(
        "--free-surface-smoothing",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--free-surface-smoothing-node-count", type=int, default=7)
    parser.add_argument(
        "--free-surface-smoothing-updates-per-plane",
        type=int,
        default=0,
        help=(
            "Fix the number of smoothing updates per ground-plane interval during "
            "time-step convergence. Zero retains the source-style every-BEM-step behavior."
        ),
    )
    parser.add_argument("--uniform-near-body-panels", type=int, default=6)
    parser.add_argument(
        "--restoring-mode",
        choices=("quasistatic", "zero", "external"),
        default="quasistatic",
    )
    parser.add_argument(
        "--restoring-matrix-file",
        type=Path,
        default=None,
        help=(
            "CSV with component,row,column,value fields. Required for external "
            "mode; the source path and SHA-256 are recorded in diagnostics."
        ),
    )
    parser.add_argument(
        "--restoring-richardson",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--restoring-heave-step-over-beam", type=float, default=0.01)
    parser.add_argument("--restoring-pitch-step-deg", type=float, default=0.1)
    parser.add_argument("--restoring-only", action="store_true")
    return parser


def _component_result(
    result: PlaningForcedMotion2DtResult,
    component: str,
) -> PlaningForcedMotion2DtResult:
    if component == "total":
        return result
    if component == "raw_bem":
        load = result.raw_bem_generalized_load
    elif component == "resolved_station_bem":
        load = result.resolved_station_generalized_load
    elif component == "transom_extrapolation":
        load = result.transom_extrapolation_generalized_load
    elif component == "pre_chine_bem":
        load = result.pre_chine_bem_generalized_load
    elif component == "post_chine_bem":
        load = result.post_chine_bem_generalized_load
    elif component == "bem":
        load = result.bem_generalized_load
    elif component == "front":
        load = result.front_generalized_load
    elif component == "transom":
        load = result.transom_generalized_load
    elif component.startswith("longitudinal_bin_"):
        label = component.removeprefix("longitudinal_bin_")
        labels = tuple(result.metadata["longitudinal_bem_bin_labels"])
        try:
            bin_index = labels.index(label)
        except ValueError as exc:
            raise ValueError(f"Unknown longitudinal load bin {label!r}.") from exc
        load = result.longitudinal_bem_bin_generalized_load[:, bin_index, :]
    else:
        raise ValueError(f"Unknown component {component!r}.")
    return replace(result, generalized_load=np.asarray(load, dtype=float))


def _write_timeseries_checkpoint(
    output: Path,
    *,
    sigma: float,
    motion_dof: str,
    result: PlaningForcedMotion2DtResult,
) -> Path:
    """Persist the expensive flow solution before harmonic post-processing."""

    sigma_label = f"{float(sigma):.6g}".replace(".", "p")
    path = output / f"timeseries_sigma_{sigma_label}_{motion_dof}.csv"
    component_arrays = {
        "total": result.generalized_load,
        "raw_bem": result.raw_bem_generalized_load,
        "resolved_station_bem": result.resolved_station_generalized_load,
        "transom_extrapolation": result.transom_extrapolation_generalized_load,
        "pre_chine_bem": result.pre_chine_bem_generalized_load,
        "post_chine_bem": result.post_chine_bem_generalized_load,
        "bem": result.bem_generalized_load,
        "front": result.front_generalized_load,
        "transom": result.transom_generalized_load,
    }
    for bin_index, label in enumerate(result.metadata["longitudinal_bem_bin_labels"]):
        component_arrays[f"longitudinal_bin_{label}"] = (
            result.longitudinal_bem_bin_generalized_load[:, bin_index, :]
        )
    fieldnames = ["time_s"]
    for component in component_arrays:
        fieldnames.extend((f"{component}_vertical_force_n", f"{component}_pitch_moment_nm"))
    fieldnames.extend(
        (
            "active_plane_count",
            "potential_bvp_relative_residual",
            "potential_bvp_condition_number",
            "pressure_bvp_relative_residual",
            "pressure_bvp_condition_number",
            "free_surface_pressure_max_abs_pa",
            "contact_constraint_max_abs_m",
            "aftmost_resolved_station_x_m",
            "foremost_resolved_station_x_m",
            "transom_coverage_gap_m",
        )
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, time_s in enumerate(result.time_s):
            row: dict[str, object] = {"time_s": float(time_s)}
            for component, values in component_arrays.items():
                row[f"{component}_vertical_force_n"] = float(values[index, 0])
                row[f"{component}_pitch_moment_nm"] = float(values[index, 1])
            row.update(
                {
                    "active_plane_count": int(result.active_plane_count[index]),
                    "potential_bvp_relative_residual": float(
                        result.max_potential_bvp_relative_residual[index]
                    ),
                    "potential_bvp_condition_number": float(
                        result.max_potential_bvp_condition_number[index]
                    ),
                    "pressure_bvp_relative_residual": float(
                        result.max_pressure_bvp_relative_residual[index]
                    ),
                    "pressure_bvp_condition_number": float(
                        result.max_pressure_bvp_condition_number[index]
                    ),
                    "free_surface_pressure_max_abs_pa": float(
                        result.max_free_surface_pressure_abs_pa[index]
                    ),
                    "contact_constraint_max_abs_m": float(
                        result.max_contact_constraint_abs_m[index]
                    ),
                    "aftmost_resolved_station_x_m": float(
                        result.aftmost_resolved_station_x_m[index]
                    ),
                    "foremost_resolved_station_x_m": float(
                        result.foremost_resolved_station_x_m[index]
                    ),
                    "transom_coverage_gap_m": float(
                        result.transom_coverage_gap_m[index]
                    ),
                }
            )
            writer.writerow(row)
    return path


def _write_station_timeseries_checkpoint(
    output: Path,
    *,
    sigma: float,
    motion_dof: str,
    result: PlaningForcedMotion2DtResult,
) -> Path:
    """Persist the resolved sectional load distribution in long form."""

    sigma_label = f"{float(sigma):.6g}".replace(".", "p")
    path = output / f"station_timeseries_sigma_{sigma_label}_{motion_dof}.csv"
    fieldnames = (
        "time_index",
        "time_s",
        "station_index_aft_to_forward",
        "x_from_transom_m",
        "force_density_n_m",
        "creation_parameter_s",
        "age_parameter_s",
        "contact_half_beam_m",
        "jet_cut_count",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for time_index, time_s in enumerate(result.time_s):
            count = int(result.active_plane_count[time_index])
            for station_index in range(count):
                writer.writerow(
                    {
                        "time_index": time_index,
                        "time_s": float(time_s),
                        "station_index_aft_to_forward": station_index,
                        "x_from_transom_m": float(
                            result.station_x_from_transom_m[time_index, station_index]
                        ),
                        "force_density_n_m": float(
                            result.station_force_density_n_m[time_index, station_index]
                        ),
                        "creation_parameter_s": float(
                            result.station_creation_parameter_s[time_index, station_index]
                        ),
                        "age_parameter_s": float(
                            result.station_age_parameter_s[time_index, station_index]
                        ),
                        "contact_half_beam_m": float(
                            result.station_contact_half_beam_m[time_index, station_index]
                        ),
                        "jet_cut_count": int(
                            result.station_jet_cut_count[time_index, station_index]
                        ),
                    }
                )
    return path


def _identify(
    heave_result: PlaningForcedMotion2DtResult,
    pitch_result: PlaningForcedMotion2DtResult,
    heave_case: PlaningForcedMotionCase,
    pitch_case: PlaningForcedMotionCase,
    component: str,
    *,
    restoring_matrix: np.ndarray,
    discard_cycles: float,
    retained_cycles: float,
) -> ForcedMotionMatrices:
    heave = extract_forced_motion_column(
        heave_case.time_s,
        _component_result(heave_result, component).generalized_load,
        motion_dof="heave",
        omega_rad_s=heave_case.omega_rad_s,
        motion_amplitude=heave_case.motion_amplitude,
        restoring_column=np.asarray(restoring_matrix, dtype=float)[:, 0],
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=3,
    )
    pitch = extract_forced_motion_column(
        pitch_case.time_s,
        _component_result(pitch_result, component).generalized_load,
        motion_dof="pitch",
        omega_rad_s=pitch_case.omega_rad_s,
        motion_amplitude=pitch_case.motion_amplitude,
        restoring_column=np.asarray(restoring_matrix, dtype=float)[:, 1],
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=3,
    )
    return assemble_forced_motion_matrices(heave, pitch)


def _identify_heave_column(
    result: PlaningForcedMotion2DtResult,
    case: PlaningForcedMotionCase,
    component: str,
    *,
    restoring_matrix: np.ndarray,
    discard_cycles: float,
    retained_cycles: float,
):
    return extract_forced_motion_column(
        case.time_s,
        _component_result(result, component).generalized_load,
        motion_dof="heave",
        omega_rad_s=case.omega_rad_s,
        motion_amplitude=case.motion_amplitude,
        restoring_column=np.asarray(restoring_matrix, dtype=float)[:, 0],
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=3,
    )


def _identify_pitch_column(
    result: PlaningForcedMotion2DtResult,
    case: PlaningForcedMotionCase,
    component: str,
    *,
    restoring_matrix: np.ndarray,
    discard_cycles: float,
    retained_cycles: float,
):
    return extract_forced_motion_column(
        case.time_s,
        _component_result(result, component).generalized_load,
        motion_dof="pitch",
        omega_rad_s=case.omega_rad_s,
        motion_amplitude=case.motion_amplitude,
        restoring_column=np.asarray(restoring_matrix, dtype=float)[:, 1],
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=3,
    )


def _coefficient_scale(coefficient: str, *, beam: float, rho: float, gravity: float) -> float:
    if coefficient in ("A33", "B33"):
        length_power = 3
    elif coefficient in ("A35", "A53", "B35", "B53"):
        length_power = 4
    elif coefficient in ("A55", "B55"):
        length_power = 5
    else:
        raise ValueError(f"Unsupported forced-motion coefficient: {coefficient}.")
    scale = rho * beam**length_power
    if coefficient.startswith("B"):
        scale *= math.sqrt(gravity / beam)
    return float(scale)


def _ground_plane_spacing_m(
    *,
    wetted_length_m: float,
    initial_leading_offset_m: float,
    section_planes: int,
    rule: str,
) -> float:
    wetted = float(wetted_length_m)
    offset = float(initial_leading_offset_m)
    count = int(section_planes)
    if count != section_planes or count < 3:
        raise ValueError("section_planes must be an integer of at least three.")
    if not 0.0 < offset < wetted:
        raise ValueError("The BEM handoff must lie inside the keel-wetted interval.")
    if rule == "keel_over_nx":
        return wetted / count
    if rule == "bem_interval_over_nx_minus_one":
        return (wetted - offset) / (count - 1)
    raise ValueError(f"Unsupported ground-plane spacing rule: {rule}.")


def _load_center_row(
    *,
    component: str,
    sigma: float,
    added_mass_column: np.ndarray,
    damping_column: np.ndarray,
    lcg_from_transom_m: float,
    beam_m: float,
    restoring_subtraction: str,
) -> dict[str, object]:
    added = np.asarray(added_mass_column, dtype=float)
    damping = np.asarray(damping_column, dtype=float)

    def center(column: np.ndarray) -> tuple[float, float]:
        if abs(float(column[0])) <= 1e-14:
            return float("nan"), float("nan")
        from_cg = float(column[1] / column[0])
        return from_cg, float(lcg_from_transom_m + from_cg)

    in_phase_from_cg, in_phase_from_transom = center(added)
    damping_from_cg, damping_from_transom = center(damping)
    return {
        "component": component,
        "sigma": float(sigma),
        "in_phase_center_from_cg_m": in_phase_from_cg,
        "in_phase_center_from_transom_m": in_phase_from_transom,
        "in_phase_center_from_transom_over_beam": in_phase_from_transom / beam_m,
        "damping_center_from_cg_m": damping_from_cg,
        "damping_center_from_transom_m": damping_from_transom,
        "damping_center_from_transom_over_beam": damping_from_transom / beam_m,
        "restoring_subtraction": restoring_subtraction,
        "response_calibration_used": False,
    }


def _progress_printer(label: str):
    last_bucket = -1

    def report(index: int, count: int, time_s: float) -> None:
        nonlocal last_bucket
        denominator = max(int(count) - 1, 1)
        percent = min(100, int(np.floor(100.0 * min(index, denominator) / denominator)))
        bucket = min(100, 5 * (percent // 5))
        if bucket > last_bucket or index >= count:
            last_bucket = bucket
            print(f"{label}: {bucket:3d}% t={time_s:.6g}s", flush=True)

    return report


def _result_diagnostic_fields(
    prefix: str,
    result: PlaningForcedMotion2DtResult,
) -> dict[str, object]:
    return {
        f"{prefix}_minimum_active_planes": result.minimum_matrix_station_count,
        f"{prefix}_max_potential_residual": float(
            np.max(result.max_potential_bvp_relative_residual)
        ),
        f"{prefix}_max_potential_condition_number": float(
            np.max(result.max_potential_bvp_condition_number)
        ),
        f"{prefix}_max_pressure_residual": float(
            np.max(result.max_pressure_bvp_relative_residual)
        ),
        f"{prefix}_max_pressure_condition_number": float(
            np.max(result.max_pressure_bvp_condition_number)
        ),
        f"{prefix}_max_front_length_m": float(
            np.max(result.front_approximation_length_m)
        ),
        f"{prefix}_maximum_jet_cut_count_per_plane": result.metadata[
            "maximum_jet_cut_count_per_plane"
        ],
        f"{prefix}_minimum_jet_normal_distance_ratio": result.metadata[
            "minimum_jet_normal_distance_ratio"
        ],
        f"{prefix}_minimum_jet_projection_ratio": result.metadata[
            "minimum_jet_projection_ratio"
        ],
        f"{prefix}_maximum_jet_projection_ratio": result.metadata[
            "maximum_jet_projection_ratio"
        ],
        f"{prefix}_maximum_spray_overturning_panel_count": result.metadata[
            "maximum_spray_overturning_panel_count"
        ],
        f"{prefix}_minimum_spray_outward_tangent_cosine": result.metadata[
            "minimum_spray_outward_tangent_cosine"
        ],
        f"{prefix}_minimum_spray_nonadjacent_distance_ratio": result.metadata[
            "minimum_spray_nonadjacent_distance_ratio"
        ],
        f"{prefix}_spray_cut_included": result.metadata["spray_cut_included"],
        f"{prefix}_maximum_creation_draft_error_m": result.metadata[
            "maximum_creation_draft_error_m"
        ],
        f"{prefix}_ground_plane_handoff_mode": result.metadata[
            "ground_plane_handoff_mode"
        ],
        f"{prefix}_minimum_creation_draft_m": result.metadata[
            "minimum_creation_draft_m"
        ],
        f"{prefix}_maximum_creation_draft_m": result.metadata[
            "maximum_creation_draft_m"
        ],
        f"{prefix}_maximum_ground_plane_spacing_error_m": result.metadata[
            "maximum_ground_plane_spacing_error_m"
        ],
        f"{prefix}_wet_plane_removal_count": result.metadata[
            "wet_plane_removal_count"
        ],
        **_ground_plane_event_diagnostics(prefix, result),
        f"{prefix}_maximum_raw_transom_coverage_gap_m": result.metadata[
            "maximum_raw_transom_coverage_gap_m"
        ],
    }


def main() -> int:
    args = _parser().parse_args()
    if args.restoring_mode == "external" and args.restoring_matrix_file is None:
        raise ValueError("--restoring-matrix-file is required for external restoring mode.")
    if args.restoring_mode != "external" and args.restoring_matrix_file is not None:
        raise ValueError(
            "--restoring-matrix-file can only be used with --restoring-mode external."
        )
    if args.section_planes < 3:
        raise ValueError("section-planes must be at least three.")
    if args.bem_substeps_per_plane < 1:
        raise ValueError("bem-substeps-per-plane must be at least one.")
    if args.parallel_workers < 1:
        raise ValueError("parallel-workers must be at least one.")
    root = Path(__file__).resolve().parents[1]
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)

    beam = float(args.beam_m)
    gravity = float(args.gravity_m_s2)
    rho = float(args.rho_water_kg_m3)
    trim = math.radians(float(args.trim_deg))
    deadrise = math.radians(float(args.deadrise_deg))
    speed = float(args.fn_b) * math.sqrt(gravity * beam)
    mean_wetted_length_beam_ratio = float(args.mean_wetted_length_over_beam)
    chine_wetting_offset_beams = float(args.chine_wetting_offset_over_beam)
    derived_keel_wetted_length_beams = (
        mean_wetted_length_beam_ratio + 0.5 * chine_wetting_offset_beams
    )
    if args.keel_wetted_length_over_beam is not None and not math.isclose(
        float(args.keel_wetted_length_over_beam),
        derived_keel_wetted_length_beams,
        rel_tol=0.0,
        abs_tol=1.0e-8,
    ):
        raise ValueError(
            "keel-wetted-length-over-beam must equal mean-wetted-length-over-beam "
            "+ 0.5*chine-wetting-offset-over-beam."
        )
    keel_wetted_length_beams = (
        derived_keel_wetted_length_beams
        if args.keel_wetted_length_over_beam is None
        else float(args.keel_wetted_length_over_beam)
    )
    wetted_length = keel_wetted_length_beams * beam
    lcg = float(args.lcg_over_beam) * beam
    vcg = float(args.vcg_over_beam) * beam
    positive_inputs = {
        "beam-m": beam,
        "rho-water-kg-m3": rho,
        "gravity-m-s2": gravity,
        "fn-b": float(args.fn_b),
        "mean-wetted-length-over-beam": mean_wetted_length_beam_ratio,
        "keel-wetted-length-over-beam": keel_wetted_length_beams,
        "mean-draft-over-beam": float(args.mean_draft_over_beam),
        "heave-amplitude-over-beam": float(args.heave_amplitude_over_beam),
        "pitch-amplitude-deg": float(args.pitch_amplitude_deg),
    }
    invalid = [name for name, value in positive_inputs.items() if not math.isfinite(value) or value <= 0.0]
    if invalid:
        raise ValueError(f"Target inputs must be finite and positive: {invalid}.")
    target_context = {
        "target_identifier": str(args.target_identifier),
        "beam_m": beam,
        "deadrise_deg": math.degrees(deadrise),
        "trim_deg": math.degrees(trim),
        "fn_b": speed / math.sqrt(gravity * beam),
        "mean_wetted_length_over_b": mean_wetted_length_beam_ratio,
        "lcg_from_transom_m": lcg,
        "rho_water_kg_m3": rho,
        "gravity_m_s2": gravity,
        "matrix_coordinate_contract": (
            "heave_up_pitch_bow_up_force_and_moment_about_cg"
        ),
    }
    initial_leading_offset_beams = (
        wetted_length / (beam * float(args.section_planes))
        if args.initial_leading_offset_beams is None
        else float(args.initial_leading_offset_beams)
    )
    if not 0.0 < initial_leading_offset_beams < wetted_length / beam:
        raise ValueError(
            "initial-leading-offset-beams must lie between zero and the keel wetted length."
        )
    initial_draft = initial_leading_offset_beams * beam * math.tan(trim)
    active_duration = (wetted_length - initial_draft / math.tan(trim)) / speed
    plane_spacing = _ground_plane_spacing_m(
        wetted_length_m=wetted_length,
        initial_leading_offset_m=initial_leading_offset_beams * beam,
        section_planes=args.section_planes,
        rule=args.ground_plane_spacing_rule,
    )
    plane_step = plane_spacing / speed
    remesh_updates_per_plane = int(args.free_surface_remesh_updates_per_plane)
    if remesh_updates_per_plane < 0:
        raise ValueError("free-surface-remesh-updates-per-plane must be non-negative.")
    remesh_interval_s = (
        None
        if remesh_updates_per_plane == 0
        else plane_step / float(remesh_updates_per_plane)
    )
    smoothing_updates_per_plane = int(args.free_surface_smoothing_updates_per_plane)
    if smoothing_updates_per_plane < 0:
        raise ValueError("free-surface-smoothing-updates-per-plane must be non-negative.")
    smoothing_interval_s = (
        None
        if smoothing_updates_per_plane == 0
        else plane_step / float(smoothing_updates_per_plane)
    )
    config = MovingWedgeConfig(
        deadrise_rad=deadrise,
        mean_draft_m=float(args.mean_draft_over_beam) * beam,
        chine_half_beam_m=0.5 * beam,
        free_surface_extent_m=3.0 * beam,
        water_depth_m=2.5 * beam,
        body_panels_per_side=args.body_panels,
        free_surface_panels_per_side=args.free_surface_panels,
        side_wall_panels=args.side_panels,
        bottom_panels=args.bottom_panels,
        gauss_order=args.gauss_order,
        element_interpolation=args.element_interpolation,
        pressure_interpolation=args.pressure_interpolation,
        damping_beach_length_m=beam,
        initializer="wagner",
        free_surface_remesh_interval_s=remesh_interval_s,
        free_surface_spacing_mode=args.free_surface_spacing_mode,
        free_surface_smoothing_enabled=args.free_surface_smoothing,
        free_surface_smoothing_node_count=args.free_surface_smoothing_node_count,
        free_surface_smoothing_interval_s=smoothing_interval_s,
        free_surface_uniform_near_body_panel_count=args.uniform_near_body_panels,
        enforce_lateral_symmetry=True,
        use_symmetry_half_domain=args.symmetry_half_domain,
        knuckle_separation_model=args.knuckle_separation_model,
        jet_cut_enabled=args.jet_cut,
        jet_cut_distance_fraction=args.jet_cut_distance_fraction,
        jet_cut_threshold_m=(
            None
            if args.jet_cut_threshold_over_beam is None
            else float(args.jet_cut_threshold_over_beam) * beam
        ),
        jet_cut_max_corrective_passes=args.jet_cut_max_corrective_passes,
    )
    script_path = Path(__file__).resolve()
    input_snapshot = {
        "schema": "planing_forced_motion_2dt_input_snapshot_v1",
        "script": str(script_path),
        "script_sha256": _sha256(script_path),
        "argv": [str(value) for value in sys.argv],
        "arguments": _jsonable_argument_snapshot(args),
        "derived_target_context": target_context,
        "derived_inputs": {
            "speed_mps": speed,
            "keel_wetted_length_over_beam": keel_wetted_length_beams,
            "keel_wetted_length_m": wetted_length,
            "initial_leading_offset_over_beam": initial_leading_offset_beams,
            "initial_draft_m": initial_draft,
            "active_bem_duration_s": active_duration,
            "ground_plane_interval_s": plane_step,
            "ground_plane_spacing_over_beam": plane_spacing / beam,
            "ground_plane_spacing_rule": args.ground_plane_spacing_rule,
            "free_surface_remesh_updates_per_ground_plane_interval": (
                remesh_updates_per_plane
            ),
            "free_surface_remesh_interval_s": remesh_interval_s,
            "free_surface_smoothing_updates_per_ground_plane_interval": (
                smoothing_updates_per_plane
            ),
            "free_surface_smoothing_interval_s": smoothing_interval_s,
            "lcg_from_transom_m": lcg,
            "vcg_m": vcg,
        },
        "moving_wedge_config": {
            name: value
            for name, value in config.__dict__.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        },
        "response_calibration_used": False,
    }
    (output / "run_input_snapshot.json").write_text(
        json.dumps(input_snapshot, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    restoring_label = "zero_diagnostic_only"
    restoring_matrices = {
        name: np.zeros((2, 2), dtype=float) for name in LOAD_COMPONENTS
    }
    restoring_diagnostics: dict[str, object] = {
        "mode": args.restoring_mode,
        "response_calibration_used": False,
        "numerical_configuration": {
            "body_panels_per_side": args.body_panels,
            "free_surface_panels_per_side": args.free_surface_panels,
            "bem_substeps_per_plane": args.bem_substeps_per_plane,
            "parallel_workers": args.parallel_workers,
            "element_interpolation": args.element_interpolation,
            "pressure_interpolation": args.pressure_interpolation,
            "knuckle_separation_model": args.knuckle_separation_model,
            "jet_cut_enabled": args.jet_cut,
            "jet_cut_distance_fraction": args.jet_cut_distance_fraction,
            "jet_cut_threshold_over_beam": args.jet_cut_threshold_over_beam,
            "jet_cut_threshold_m": config.jet_cut_threshold_m,
            "free_surface_remesh_updates_per_ground_plane_interval": (
                remesh_updates_per_plane
            ),
            "free_surface_remesh_interval_s": remesh_interval_s,
            "free_surface_smoothing_enabled": args.free_surface_smoothing,
            "free_surface_smoothing_node_count": args.free_surface_smoothing_node_count,
            "free_surface_smoothing_updates_per_ground_plane_interval": (
                smoothing_updates_per_plane
            ),
            "free_surface_smoothing_interval_s": smoothing_interval_s,
            "uniform_near_body_panels": args.uniform_near_body_panels,
        },
    }
    if args.restoring_mode == "external":
        restoring_path = Path(args.restoring_matrix_file).resolve()
        loaded_matrices = _read_external_restoring_matrices(restoring_path)
        restoring_matrices.update(loaded_matrices)
        restoring_label = f"external:{restoring_path.parent.name}/{restoring_path.name}"
        restoring_diagnostics.update(
            {
                "source": "external_response_independent_restoring_matrix",
                "source_path": str(restoring_path),
                "source_sha256": _sha256(restoring_path),
                "restoring_matrix": restoring_matrices["total"].tolist(),
                "step_convergence_evaluated": False,
            }
        )
    elif args.restoring_mode == "quasistatic":
        reference_sigma = float(args.sigmas[0])
        reference_omega = reference_sigma * math.sqrt(gravity / beam)
        reference_period = 2.0 * math.pi / reference_omega
        reference_plane_interval = plane_step
        reference_time_step = reference_plane_interval / float(
            args.bem_substeps_per_plane
        )
        static_case = PlaningForcedMotionCase(
            speed_mps=speed,
            mean_trim_rad=trim,
            wetted_length_m=wetted_length,
            lcg_from_transom_m=lcg,
            motion_dof="heave",
            motion_amplitude=float(args.heave_amplitude_over_beam) * beam,
            omega_rad_s=reference_omega,
            duration_s=2.0 * reference_period,
            time_step_s=reference_time_step,
            initial_draft_m=initial_draft,
            ground_plane_interval_s=reference_plane_interval,
            ground_plane_handoff_mode=args.ground_plane_handoff_mode,
            rho_water_kg_m3=rho,
            gravity_m_s2=gravity,
            mean_wetted_length_beam_ratio=mean_wetted_length_beam_ratio,
            transom_correction_enabled=args.transom_correction,
            transom_keel_reduction_beams=(0.5 if args.transom_keel_reduction else 0.0),
            metadata={
                "target_identifier": str(args.target_identifier),
                "calculation_role": "quasistatic_restoring_derivative",
            },
        )
        restoring_result = estimate_planing_restoring_matrix(
            config,
            static_case,
            vcg_m=vcg,
            heave_step_m=float(args.restoring_heave_step_over_beam) * beam,
            pitch_step_rad=math.radians(float(args.restoring_pitch_step_deg)),
            richardson_extrapolation=args.restoring_richardson,
            progress_callback=lambda stage: print(f"restoring:{stage}", flush=True),
        )
        restoring_matrices = restoring_result.component_restoring_matrices
        for component in LOAD_COMPONENTS:
            restoring_matrices.setdefault(component, np.zeros((2, 2), dtype=float))
        restoring_label = "nonlinear_2dt_quasistatic_target_state"
        restoring_diagnostics.update(
            {
                "restoring_matrix": restoring_result.restoring_matrix.tolist(),
                "coarse_matrix": restoring_result.coarse_matrix.tolist(),
                "refined_matrix": restoring_result.refined_matrix.tolist(),
                "relative_step_change": restoring_result.relative_step_change.tolist(),
                "heave_step_m": restoring_result.heave_step_m,
                "pitch_step_rad": restoring_result.pitch_step_rad,
                "richardson_extrapolation": args.restoring_richardson,
                "step_convergence_evaluated": bool(args.restoring_richardson),
                "max_potential_bvp_relative_residual": max(
                    load.max_potential_bvp_relative_residual
                    for load in restoring_result.load_cases
                ),
                "max_pressure_bvp_relative_residual": max(
                    load.max_pressure_bvp_relative_residual
                    for load in restoring_result.load_cases
                ),
                "source": "nonlinear_2dt_quasistatic_load_derivatives",
                "load_cases": [
                    {
                        "stage_and_motion": label,
                        "heave_m": load.geometry.heave_m,
                        "pitch_rad": load.geometry.pitch_rad,
                        "trim_rad": load.geometry.trim_rad,
                        "average_wetted_length_m": load.geometry.average_wetted_length_m,
                        "chine_wetting_x_from_leading_m": (
                            load.geometry.chine_wetting_x_from_leading_m
                        ),
                        "keel_wetted_length_m": load.geometry.keel_wetted_length_m,
                        "transom_draft_m": load.geometry.transom_draft_m,
                        "station_count": load.station_count,
                        "final_jet_cut_count": load.metadata[
                            "steady_entry_final_jet_cut_count"
                        ],
                        "separated_state_count": load.metadata[
                            "steady_entry_separated_state_count"
                        ],
                        "separation_event_count": load.metadata[
                            "steady_entry_separation_event_count"
                        ],
                        "first_separation_time_s": load.metadata[
                            "steady_entry_first_separation_time_s"
                        ],
                        "first_separation_x_from_leading_m": load.metadata[
                            "steady_entry_first_separation_x_from_leading_m"
                        ],
                        "minimum_jet_normal_distance_ratio": load.metadata[
                            "steady_entry_minimum_jet_normal_distance_ratio"
                        ],
                        "minimum_jet_projection_ratio": load.metadata[
                            "steady_entry_minimum_jet_projection_ratio"
                        ],
                        "maximum_jet_projection_ratio": load.metadata[
                            "steady_entry_maximum_jet_projection_ratio"
                        ],
                        "total_vertical_force_n": float(load.generalized_load[0]),
                        "total_pitch_moment_nm": float(load.generalized_load[1]),
                        "bem_vertical_force_n": float(load.bem_generalized_load[0]),
                        "bem_pitch_moment_nm": float(load.bem_generalized_load[1]),
                        "front_vertical_force_n": float(load.front_generalized_load[0]),
                        "front_pitch_moment_nm": float(load.front_generalized_load[1]),
                        "longitudinal_bem_bins": {
                            label: {
                                "vertical_force_n": float(component_load[0]),
                                "pitch_moment_nm": float(component_load[1]),
                            }
                            for label, component_load in (
                                load.longitudinal_bem_bin_generalized_load.items()
                            )
                        },
                    }
                    for label, load in zip(
                        (
                            "coarse_heave_plus",
                            "coarse_heave_minus",
                            "coarse_pitch_plus",
                            "coarse_pitch_minus",
                            "refined_heave_plus",
                            "refined_heave_minus",
                            "refined_pitch_plus",
                            "refined_pitch_minus",
                        )[: len(restoring_result.load_cases)],
                        restoring_result.load_cases,
                    )
                ],
            }
        )

    restoring_rows: list[dict[str, object]] = []
    for component, matrix in restoring_matrices.items():
        for row in range(2):
            for column in range(2):
                restoring_rows.append(
                    {
                        "component": component,
                        "row": ("heave_force", "pitch_moment")[row],
                        "column": ("heave", "pitch")[column],
                        "value": float(matrix[row, column]),
                        "units": (("N/m", "N/rad"), ("N", "N m/rad"))[row][column],
                    }
                )
    with (output / "restoring_matrices.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(restoring_rows[0]))
        writer.writeheader()
        writer.writerows(restoring_rows)
    component_convergence_rows: list[dict[str, object]] = []
    for component, matrix in restoring_matrices.items():
        component_has_static_decomposition = bool(
            args.restoring_mode == "quasistatic"
            and component in restoring_result.coarse_component_restoring_matrices
        )
        coarse_matrix = (
            restoring_result.coarse_component_restoring_matrices[component]
            if component_has_static_decomposition
            else matrix
        )
        refined_matrix = (
            restoring_result.refined_component_restoring_matrices[component]
            if component_has_static_decomposition
            else matrix
        )
        for row in range(2):
            for column in range(2):
                extrapolated = float(matrix[row, column])
                relative_change = (
                    abs(float(refined_matrix[row, column] - coarse_matrix[row, column]))
                    / max(abs(extrapolated), np.finfo(float).eps)
                    if component_has_static_decomposition and args.restoring_richardson
                    else None
                )
                component_convergence_rows.append(
                    {
                        "component": component,
                        "row": ("heave_force", "pitch_moment")[row],
                        "column": ("heave", "pitch")[column],
                        "coarse_value": float(coarse_matrix[row, column]),
                        "refined_value": float(refined_matrix[row, column]),
                        "extrapolated_value": extrapolated,
                        "relative_step_change": relative_change,
                        "step_convergence_evaluated": bool(
                            component_has_static_decomposition and args.restoring_richardson
                        ),
                    }
                )
    with (output / "restoring_component_convergence.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(component_convergence_rows[0]))
        writer.writeheader()
        writer.writerows(component_convergence_rows)
    (output / "restoring_diagnostics.json").write_text(
        json.dumps(restoring_diagnostics, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    if args.restoring_only:
        print(output)
        return 0

    rows: list[dict[str, object]] = []
    load_center_rows: list[dict[str, object]] = []
    matrices_by_component: dict[str, list[ForcedMotionMatrices]] = {
        component: [] for component in LOAD_COMPONENTS
    }
    run_diagnostics: list[dict[str, object]] = []
    for sigma in args.sigmas:
        omega = float(sigma) * math.sqrt(gravity / beam)
        period = 2.0 * math.pi / omega
        minimum_substeps = max(
            int(args.bem_substeps_per_plane),
            int(math.ceil(24.0 * plane_step / period)),
        )
        time_step = plane_step / float(minimum_substeps)
        duration = args.cycles * period
        shared = dict(
            speed_mps=speed,
            mean_trim_rad=trim,
            wetted_length_m=wetted_length,
            lcg_from_transom_m=lcg,
            omega_rad_s=omega,
            duration_s=duration,
            time_step_s=time_step,
            initial_draft_m=initial_draft,
            ground_plane_interval_s=plane_step,
            ground_plane_handoff_mode=args.ground_plane_handoff_mode,
            rho_water_kg_m3=rho,
            gravity_m_s2=gravity,
            mean_wetted_length_beam_ratio=mean_wetted_length_beam_ratio,
            transom_correction_enabled=args.transom_correction,
            transom_keel_reduction_beams=(0.5 if args.transom_keel_reduction else 0.0),
            metadata={
                "benchmark": str(args.target_identifier),
                "keel_wetted_length_over_beam": keel_wetted_length_beams,
                "mean_wetted_length_over_beam": mean_wetted_length_beam_ratio,
                "chine_wetting_offset_over_beam": chine_wetting_offset_beams,
                "initial_leading_offset_over_beam": initial_leading_offset_beams,
                "initial_handoff_rule": (
                    "default_one_ground_plane_spacing"
                    if args.initial_leading_offset_beams is None
                    else "explicit_user_value"
                ),
                "ground_plane_spacing_rule": (
                    args.ground_plane_spacing_rule
                ),
                "ground_plane_handoff_mode": args.ground_plane_handoff_mode,
                "knuckle_separation_model": args.knuckle_separation_model,
                "jet_cut_enabled": args.jet_cut,
                "jet_cut_distance_fraction": args.jet_cut_distance_fraction,
                "jet_cut_max_corrective_passes": args.jet_cut_max_corrective_passes,
                "free_surface_spacing_mode": args.free_surface_spacing_mode,
                "element_interpolation": args.element_interpolation,
                "pressure_interpolation": args.pressure_interpolation,
                "free_surface_smoothing_enabled": args.free_surface_smoothing,
                "uniform_near_body_panel_count": args.uniform_near_body_panels,
                "symmetry_half_domain": args.symmetry_half_domain,
                "bem_substeps_per_ground_plane_interval": minimum_substeps,
                "restoring_subtraction": restoring_label,
                "transom_correction_enabled": args.transom_correction,
                "transom_keel_reduction_beams": (
                    0.5 if args.transom_keel_reduction else 0.0
                ),
            },
        )
        heave_case = PlaningForcedMotionCase(
            motion_dof="heave",
            motion_amplitude=float(args.heave_amplitude_over_beam) * beam,
            **shared,
        )
        pitch_case = PlaningForcedMotionCase(
            motion_dof="pitch",
            motion_amplitude=math.radians(float(args.pitch_amplitude_deg)),
            **shared,
        )
        heave_result = (
            None
            if args.pitch_only
            else run_planing_forced_motion_2dt(
                config,
                heave_case,
                progress_callback=_progress_printer(
                    f"sigma={float(sigma):.6g} heave"
                ),
                parallel_workers=args.parallel_workers,
            )
        )
        if heave_result is not None:
            _write_timeseries_checkpoint(
                output,
                sigma=float(sigma),
                motion_dof="heave",
                result=heave_result,
            )
            if args.write_station_timeseries:
                _write_station_timeseries_checkpoint(
                    output,
                    sigma=float(sigma),
                    motion_dof="heave",
                    result=heave_result,
                )
        pitch_result = (
            None
            if args.heave_only
            else run_planing_forced_motion_2dt(
                config,
                pitch_case,
                progress_callback=_progress_printer(f"sigma={float(sigma):.6g} pitch"),
                parallel_workers=args.parallel_workers,
            )
        )
        if pitch_result is not None:
            _write_timeseries_checkpoint(
                output,
                sigma=float(sigma),
                motion_dof="pitch",
                result=pitch_result,
            )
            if args.write_station_timeseries:
                _write_station_timeseries_checkpoint(
                    output,
                    sigma=float(sigma),
                    motion_dof="pitch",
                    result=pitch_result,
                )
        diagnostic = {
                "sigma": sigma,
                "omega_rad_s": omega,
                "time_step_s": time_step,
                "ground_plane_interval_s": plane_step,
                "ground_plane_spacing_over_beam": plane_spacing / beam,
                "ground_plane_spacing_rule": args.ground_plane_spacing_rule,
                "bem_substeps_per_ground_plane_interval": minimum_substeps,
                "parallel_workers": args.parallel_workers,
                "free_surface_remesh_updates_per_ground_plane_interval": (
                    remesh_updates_per_plane
                ),
                "free_surface_remesh_interval_s": remesh_interval_s,
                "free_surface_smoothing_updates_per_ground_plane_interval": (
                    smoothing_updates_per_plane
                ),
                "free_surface_smoothing_interval_s": smoothing_interval_s,
                "station_timeseries_written": bool(args.write_station_timeseries),
                "initial_leading_offset_over_beam": initial_leading_offset_beams,
                **target_context,
            }
        if heave_result is not None:
            diagnostic.update(_result_diagnostic_fields("heave", heave_result))
            diagnostic.update(
                {
                    "longitudinal_bem_bin_labels": heave_result.metadata[
                        "longitudinal_bem_bin_labels"
                    ],
                    "longitudinal_bem_bin_edges_m": heave_result.metadata[
                        "longitudinal_bem_bin_edges_m"
                    ],
                }
            )
        if pitch_result is not None:
            diagnostic.update(_result_diagnostic_fields("pitch", pitch_result))
            if "longitudinal_bem_bin_labels" not in diagnostic:
                diagnostic.update(
                    {
                        "longitudinal_bem_bin_labels": pitch_result.metadata[
                            "longitudinal_bem_bin_labels"
                        ],
                        "longitudinal_bem_bin_edges_m": pitch_result.metadata[
                            "longitudinal_bem_bin_edges_m"
                        ],
                    }
                )
        run_diagnostics.append(diagnostic)
        for component in LOAD_COMPONENTS:
            if args.heave_only:
                assert heave_result is not None
                column_result = _identify_heave_column(
                    heave_result,
                    heave_case,
                    component,
                    restoring_matrix=restoring_matrices[component],
                    discard_cycles=args.discard_cycles,
                    retained_cycles=args.retained_cycles,
                )
                load_center_rows.append(
                    _load_center_row(
                        component=component,
                        sigma=float(sigma),
                        added_mass_column=column_result.added_mass_column,
                        damping_column=column_result.damping_column,
                        lcg_from_transom_m=lcg,
                        beam_m=beam,
                        restoring_subtraction=restoring_label,
                    )
                )
                for coefficient, matrix_name, row in (
                    ("A33", "added_mass_column", 0),
                    ("A53", "added_mass_column", 1),
                    ("B33", "damping_column", 0),
                    ("B53", "damping_column", 1),
                ):
                    dimensional = float(getattr(column_result, matrix_name)[row])
                    rows.append(
                        {
                            "component": component,
                            "sigma": sigma,
                            "omega_rad_s": omega,
                            "coefficient": coefficient,
                            "value_dimensional": dimensional,
                            "value_nondimensional": dimensional
                            / _coefficient_scale(
                                coefficient,
                                beam=beam,
                                rho=rho,
                                gravity=gravity,
                            ),
                            "harmonic_fit_residual_nrmse": float(
                                column_result.harmonic_fit.residual_nrmse[row]
                            ),
                            "restoring_subtraction": restoring_label,
                            "diagnostic_zero_restoring_component": bool(
                                not np.any(restoring_matrices[component])
                                and args.restoring_mode == "quasistatic"
                                and component != "total"
                            ),
                            **target_context,
                            "response_calibration_used": False,
                        }
                    )
                continue
            if args.pitch_only:
                assert pitch_result is not None
                column_result = _identify_pitch_column(
                    pitch_result,
                    pitch_case,
                    component,
                    restoring_matrix=restoring_matrices[component],
                    discard_cycles=args.discard_cycles,
                    retained_cycles=args.retained_cycles,
                )
                load_center_rows.append(
                    _load_center_row(
                        component=component,
                        sigma=float(sigma),
                        added_mass_column=column_result.added_mass_column,
                        damping_column=column_result.damping_column,
                        lcg_from_transom_m=lcg,
                        beam_m=beam,
                        restoring_subtraction=restoring_label,
                    )
                )
                for coefficient, matrix_name, row in (
                    ("A35", "added_mass_column", 0),
                    ("A55", "added_mass_column", 1),
                    ("B35", "damping_column", 0),
                    ("B55", "damping_column", 1),
                ):
                    dimensional = float(getattr(column_result, matrix_name)[row])
                    rows.append(
                        {
                            "component": component,
                            "sigma": sigma,
                            "omega_rad_s": omega,
                            "coefficient": coefficient,
                            "value_dimensional": dimensional,
                            "value_nondimensional": dimensional
                            / _coefficient_scale(
                                coefficient,
                                beam=beam,
                                rho=rho,
                                gravity=gravity,
                            ),
                            "harmonic_fit_residual_nrmse": float(
                                column_result.harmonic_fit.residual_nrmse[row]
                            ),
                            "restoring_subtraction": restoring_label,
                            "diagnostic_zero_restoring_component": bool(
                                not np.any(restoring_matrices[component])
                                and args.restoring_mode == "quasistatic"
                                and component != "total"
                            ),
                            **target_context,
                            "response_calibration_used": False,
                        }
                    )
                continue
            assert heave_result is not None
            assert pitch_result is not None
            matrices = _identify(
                heave_result,
                pitch_result,
                heave_case,
                pitch_case,
                component,
                restoring_matrix=restoring_matrices[component],
                discard_cycles=args.discard_cycles,
                retained_cycles=args.retained_cycles,
            )
            matrices_by_component[component].append(matrices)
            load_center_rows.append(
                _load_center_row(
                    component=component,
                    sigma=float(sigma),
                    added_mass_column=matrices.added_mass[:, 0],
                    damping_column=matrices.damping[:, 0],
                    lcg_from_transom_m=lcg,
                    beam_m=beam,
                    restoring_subtraction=restoring_label,
                )
            )
            nondimensional = nondimensionalize_forced_motion_matrices(
                [matrices],
                beam_m=beam,
                rho_water_kg_m3=rho,
                gravity_m_s2=gravity,
            )
            matched_sigma = next(iter({key[0] for key in nondimensional}))
            for coefficient, (matrix_name, row, column) in COEFFICIENT_INDEX.items():
                matrix = getattr(matrices, matrix_name)
                rows.append(
                    {
                        "component": component,
                        "sigma": sigma,
                        "omega_rad_s": omega,
                        "coefficient": coefficient,
                        "value_dimensional": float(matrix[row, column]),
                        "value_nondimensional": float(
                            nondimensional[(matched_sigma, coefficient)]
                        ),
                        "harmonic_fit_residual_nrmse": float(
                            matrices.columns[column].harmonic_fit.residual_nrmse[row]
                        ),
                        "restoring_subtraction": restoring_label,
                        "diagnostic_zero_restoring_component": bool(
                            not np.any(restoring_matrices[component])
                            and args.restoring_mode == "quasistatic"
                            and component != "total"
                        ),
                        **target_context,
                        "response_calibration_used": False,
                    }
                )

    with (output / "identified_coefficients.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (output / "identified_load_centers.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(load_center_rows[0]))
        writer.writeheader()
        writer.writerows(load_center_rows)
    (output / "run_diagnostics.json").write_text(
        json.dumps(run_diagnostics, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    acceptance: dict[str, object] = {
        "status": "not_evaluated_requires_all_five_frequencies",
        "restoring_subtraction": restoring_label,
    }
    expected_sigmas = np.asarray([0.85, 1.13, 1.4, 1.7, 1.95])
    is_sun_reference_target = (
        str(args.target_identifier) == "sun2007_troesch_prismatic_planing_hull"
        and math.isclose(beam, 0.318)
        and math.isclose(math.degrees(deadrise), 20.0)
        and math.isclose(math.degrees(trim), 4.0)
        and math.isclose(float(args.fn_b), 2.5)
        and math.isclose(mean_wetted_length_beam_ratio, 3.0)
        and math.isclose(chine_wetting_offset_beams, 1.6)
        and math.isclose(float(args.lcg_over_beam), 1.47)
    )
    if (
        is_sun_reference_target
        and not args.heave_only
        and not args.pitch_only
        and len(args.sigmas) == 5
        and np.allclose(sorted(args.sigmas), expected_sigmas)
    ):
        comparison = compare_sun2007_troesch(
            matrices_by_component["total"],
            benchmark_csv_path=root / "benchmarks" / "sun2007_troesch_forced_motion_coefficients.csv",
            model_variant=(
                "sun_2dt_with_stern_3d_correction"
                if args.transom_correction or args.transom_keel_reduction
                else "sun_2dt_without_stern_3d_correction"
            ),
            beam_m=beam,
            rho_water_kg_m3=rho,
            gravity_m_s2=gravity,
            frequency_match_tolerance=5e-3,
        )
        acceptance = {
            "status": "diagnostic_comparison_complete",
            "passed": comparison.passed,
            "restoring_subtraction": restoring_label,
            "a35_monotonic_decrease": comparison.a35_monotonic_decrease,
            "a35_a53_nonreciprocal": comparison.a35_a53_nonreciprocal,
            "metrics": [metric.__dict__ for metric in comparison.metrics],
        }
    (output / "diagnostic_acceptance.json").write_text(
        json.dumps(acceptance, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
