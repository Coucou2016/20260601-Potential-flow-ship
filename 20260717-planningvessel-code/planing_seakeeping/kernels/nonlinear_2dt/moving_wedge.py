from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Protocol

import numpy as np
from scipy.interpolate import CubicSpline

from ...forced_motion_identification import FirstHarmonicFit, fit_periodic_harmonics
from .boundary_element import (
    ClosedBoundary2D,
    PressureAuxiliaryResult,
    boundary_velocity,
    boundary_node_velocity,
    build_mixed_boundary_operator,
    solve_linear_element_mixed_boundary_laplace,
    solve_pressure_auxiliary_bvp,
    solve_section_potential_bvp,
)


MOVING_WEDGE_BEM_STATUS = (
    "sun_ch2_moving_wedge_free_surface_bem_with_beach_remesh_jet_and_spray_topology_diagnostic_cut_pending_benchmark_pending"
)


class MovingWedgeContactExitError(ValueError):
    """The local contact has physically exited the supported wetted body interval."""


class VerticalMotionLaw(Protocol):
    def displacement_m(self, time_s: float) -> float:
        ...

    def velocity_mps(self, time_s: float) -> float:
        ...

    def acceleration_mps2(self, time_s: float) -> float:
        ...


@dataclass(frozen=True)
class RegularIncidentWave2D:
    """Incident-wave field in one Earth-fixed transverse plane.

    This is Eq. (3) of Sun and Faltinsen's planing-vessel-in-waves
    formulation. ``phase_at_time_zero_rad`` contains the longitudinal station
    phase, so the local field evolves with the intrinsic wave frequency while
    the assembled ship load evolves with encounter frequency.
    """

    amplitude_m: float
    omega0_rad_s: float
    wavenumber_rad_m: float
    phase_at_time_zero_rad: float
    gravity_m_s2: float = 9.80665

    def __post_init__(self) -> None:
        values = (
            self.amplitude_m,
            self.omega0_rad_s,
            self.wavenumber_rad_m,
            self.gravity_m_s2,
        )
        if any(not np.isfinite(float(value)) or float(value) <= 0.0 for value in values):
            raise ValueError("Regular incident-wave amplitude, frequency, wavenumber, and gravity must be positive.")
        if not np.isfinite(float(self.phase_at_time_zero_rad)):
            raise ValueError("phase_at_time_zero_rad must be finite.")

    def phase_rad(self, time_s: float) -> float:
        return float(self.omega0_rad_s * float(time_s) + self.phase_at_time_zero_rad)

    def _depth_factor(self, z_up_m: float | np.ndarray) -> np.ndarray:
        return np.exp(float(self.wavenumber_rad_m) * np.asarray(z_up_m, dtype=float))

    def elevation_m(self, time_s: float) -> float:
        return float(self.amplitude_m * np.sin(self.phase_rad(time_s)))

    def vertical_velocity_mps(
        self, time_s: float, z_up_m: float | np.ndarray
    ) -> np.ndarray:
        coefficient = (
            self.gravity_m_s2
            * self.amplitude_m
            * self.wavenumber_rad_m
            / self.omega0_rad_s
        )
        return coefficient * self._depth_factor(z_up_m) * np.cos(self.phase_rad(time_s))

    def vertical_acceleration_mps2(
        self, time_s: float, z_up_m: float | np.ndarray
    ) -> np.ndarray:
        coefficient = -(
            self.gravity_m_s2 * self.amplitude_m * self.wavenumber_rad_m
        )
        return coefficient * self._depth_factor(z_up_m) * np.sin(self.phase_rad(time_s))

    def potential_time_derivative_m2_s2(
        self, time_s: float, z_up_m: float | np.ndarray
    ) -> np.ndarray:
        coefficient = -(self.gravity_m_s2 * self.amplitude_m)
        return coefficient * self._depth_factor(z_up_m) * np.sin(self.phase_rad(time_s))


@dataclass(frozen=True)
class SinusoidalVerticalMotion:
    amplitude_m: float
    omega_rad_s: float
    mean_displacement_m: float = 0.0

    def __post_init__(self) -> None:
        if self.amplitude_m < 0.0 or self.omega_rad_s <= 0.0:
            raise ValueError("Sinusoidal motion needs non-negative amplitude and positive frequency.")

    def displacement_m(self, time_s: float) -> float:
        return float(self.mean_displacement_m - self.amplitude_m * np.sin(self.omega_rad_s * time_s))

    def velocity_mps(self, time_s: float) -> float:
        return float(-self.amplitude_m * self.omega_rad_s * np.cos(self.omega_rad_s * time_s))

    def acceleration_mps2(self, time_s: float) -> float:
        return float(self.amplitude_m * self.omega_rad_s**2 * np.sin(self.omega_rad_s * time_s))


@dataclass(frozen=True)
class ConstantVerticalMotion:
    displacement_value_m: float = 0.0

    def displacement_m(self, time_s: float) -> float:
        del time_s
        return float(self.displacement_value_m)

    def velocity_mps(self, time_s: float) -> float:
        del time_s
        return 0.0

    def acceleration_mps2(self, time_s: float) -> float:
        del time_s
        return 0.0


@dataclass(frozen=True)
class LinearDraftEntryMotion:
    """Constant-rate downward entry expressed as a z-up body displacement."""

    reference_draft_m: float
    initial_draft_m: float
    draft_rate_mps: float
    start_time_s: float = 0.0

    def __post_init__(self) -> None:
        if self.reference_draft_m <= 0.0 or self.initial_draft_m <= 0.0 or self.draft_rate_mps <= 0.0:
            raise ValueError("Linear draft entry parameters must be positive.")

    def draft_m(self, time_s: float) -> float:
        return float(self.initial_draft_m + self.draft_rate_mps * (float(time_s) - self.start_time_s))

    def displacement_m(self, time_s: float) -> float:
        return float(self.reference_draft_m - self.draft_m(time_s))

    def velocity_mps(self, time_s: float) -> float:
        del time_s
        return float(-self.draft_rate_mps)

    def acceleration_mps2(self, time_s: float) -> float:
        del time_s
        return 0.0


@dataclass(frozen=True)
class MovingWedgeConfig:
    deadrise_rad: float
    mean_draft_m: float
    chine_half_beam_m: float
    free_surface_extent_m: float
    water_depth_m: float
    body_panels_per_side: int = 20
    free_surface_panels_per_side: int = 28
    side_wall_panels: int = 6
    bottom_panels: int = 28
    gauss_order: int = 10
    element_interpolation: Literal["constant_panel", "linear_node"] = "constant_panel"
    pressure_interpolation: Literal["match_potential", "constant_panel"] = "constant_panel"
    damping_beach_length_m: float = 0.0
    damping_beach_beta0: float = 0.3
    initializer: Literal["flat", "wagner"] = "flat"
    free_surface_remesh_enabled: bool = True
    free_surface_remesh_interval_s: float | None = None
    free_surface_spacing_mode: Literal["uniform", "body_matched_geometric"] = "uniform"
    free_surface_smoothing_enabled: bool = True
    free_surface_smoothing_node_count: int = 7
    free_surface_smoothing_interval_s: float | None = None
    free_surface_uniform_near_body_panel_count: int = 6
    enforce_lateral_symmetry: bool = False
    use_symmetry_half_domain: bool = False
    chine_separation_enabled: bool = True
    knuckle_separation_model: Literal["clamped", "artificial_surface"] = "clamped"
    jet_cut_enabled: bool = False
    jet_cut_method: Literal["distance", "angle"] = "distance"
    jet_cut_distance_fraction: float = 0.25
    jet_cut_threshold_m: float | None = None
    jet_cut_search_node_count: int = 1
    # Legacy truncated-jet approximation: the free-surface array starts at
    # the spray tip and may initially walk inward along the upper jet branch.
    # This is not a generic coordinate-ordering or mesh-inversion detector.
    jet_cut_ordering_safeguard_enabled: bool = True
    jet_cut_angle_threshold_deg: float = 4.0
    jet_cut_angle_length_fraction: float = 0.1
    jet_cut_angle_hull_arc_length_m: float | None = None
    jet_cut_max_corrective_passes: int = 8

    def __post_init__(self) -> None:
        beta = float(self.deadrise_rad)
        if not 0.0 < beta < 0.5 * np.pi:
            raise ValueError("deadrise_rad must lie between zero and pi/2.")
        if self.mean_draft_m <= 0.0 or self.chine_half_beam_m <= 0.0:
            raise ValueError("mean_draft_m and chine_half_beam_m must be positive.")
        if self.free_surface_extent_m <= self.chine_half_beam_m:
            raise ValueError("free_surface_extent_m must exceed chine_half_beam_m.")
        if self.water_depth_m <= self.mean_draft_m:
            raise ValueError("water_depth_m must exceed mean_draft_m.")
        if (
            self.mean_draft_m / np.tan(beta) >= self.chine_half_beam_m
            and not self.chine_separation_enabled
        ):
            raise ValueError("Mean wedge waterline must lie inboard of the chine.")
        counts = (
            self.body_panels_per_side,
            self.free_surface_panels_per_side,
            self.side_wall_panels,
            self.bottom_panels,
        )
        if any(int(value) < 2 for value in counts) or int(self.gauss_order) < 4:
            raise ValueError("Moving-wedge panel counts and gauss_order are too small.")
        if not 0.0 <= float(self.damping_beach_length_m) < float(self.free_surface_extent_m):
            raise ValueError("damping_beach_length_m must lie in [0, free_surface_extent_m).")
        if float(self.damping_beach_beta0) < 0.0:
            raise ValueError("damping_beach_beta0 must be non-negative.")
        if self.initializer not in ("flat", "wagner"):
            raise ValueError("initializer must be flat or wagner.")
        if self.free_surface_remesh_interval_s is not None:
            interval = float(self.free_surface_remesh_interval_s)
            if not np.isfinite(interval) or interval <= 0.0:
                raise ValueError(
                    "free_surface_remesh_interval_s must be finite and positive when supplied."
                )
        if self.free_surface_spacing_mode not in ("uniform", "body_matched_geometric"):
            raise ValueError(
                "free_surface_spacing_mode must be uniform or body_matched_geometric."
            )
        if self.free_surface_smoothing_enabled and int(self.free_surface_smoothing_node_count) < 5:
            raise ValueError(
                "free_surface_smoothing_node_count must be at least five when smoothing is enabled."
            )
        if self.free_surface_smoothing_interval_s is not None:
            interval = float(self.free_surface_smoothing_interval_s)
            if not np.isfinite(interval) or interval <= 0.0:
                raise ValueError(
                    "free_surface_smoothing_interval_s must be finite and positive when supplied."
                )
        if int(self.free_surface_uniform_near_body_panel_count) < 1:
            raise ValueError(
                "free_surface_uniform_near_body_panel_count must be at least one."
            )
        if self.element_interpolation not in ("constant_panel", "linear_node"):
            raise ValueError("element_interpolation must be constant_panel or linear_node.")
        if self.pressure_interpolation not in ("match_potential", "constant_panel"):
            raise ValueError(
                "pressure_interpolation must be match_potential or constant_panel."
            )
        if self.element_interpolation == "linear_node" and not self.use_symmetry_half_domain:
            raise ValueError(
                "linear_node moving-wedge BEM currently requires the exact symmetry half-domain."
            )
        if self.knuckle_separation_model not in ("clamped", "artificial_surface"):
            raise ValueError("knuckle_separation_model must be clamped or artificial_surface.")
        if self.use_symmetry_half_domain and not self.enforce_lateral_symmetry:
            raise ValueError(
                "use_symmetry_half_domain requires enforce_lateral_symmetry=True."
            )
        if self.jet_cut_method not in ("distance", "angle"):
            raise ValueError("jet_cut_method must be distance or angle.")
        if self.jet_cut_method == "angle" and self.element_interpolation != "linear_node":
            raise ValueError(
                "The diagnostic angle jet-cut method requires linear_node interpolation."
            )
        if not 0.0 < float(self.jet_cut_distance_fraction) <= 1.0:
            raise ValueError("jet_cut_distance_fraction must lie in (0, 1].")
        if self.jet_cut_threshold_m is not None and float(self.jet_cut_threshold_m) <= 0.0:
            raise ValueError("jet_cut_threshold_m must be positive when supplied.")
        if int(self.jet_cut_search_node_count) < 1:
            raise ValueError("jet_cut_search_node_count must be at least one.")
        if not 0.0 < float(self.jet_cut_angle_threshold_deg) < 90.0:
            raise ValueError("jet_cut_angle_threshold_deg must lie in (0, 90).")
        if not 0.0 < float(self.jet_cut_angle_length_fraction) < 1.0:
            raise ValueError("jet_cut_angle_length_fraction must lie in (0, 1).")
        if (
            self.jet_cut_angle_hull_arc_length_m is not None
            and float(self.jet_cut_angle_hull_arc_length_m) <= 0.0
        ):
            raise ValueError(
                "jet_cut_angle_hull_arc_length_m must be positive when supplied."
            )
        if int(self.jet_cut_max_corrective_passes) < 1:
            raise ValueError("jet_cut_max_corrective_passes must be at least one.")


@dataclass(frozen=True)
class SprayGeometryDiagnostic:
    """Read-only precursor diagnostics for Sun's spray-sheet cut (Sec. 2.5)."""

    overturning_panel_count: int
    minimum_outward_tangent_cosine: float
    minimum_nonadjacent_distance_m: float | None
    minimum_nonadjacent_distance_ratio: float | None
    closest_nonadjacent_segment_indices: tuple[int, int] | None


def _point_segment_distance_2d(
    point: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
) -> float:
    segment = end - start
    length_squared = float(np.dot(segment, segment))
    if length_squared <= np.finfo(float).tiny:
        return float(np.linalg.norm(point - start))
    fraction = float(np.clip(np.dot(point - start, segment) / length_squared, 0.0, 1.0))
    return float(np.linalg.norm(point - (start + fraction * segment)))


def _segments_intersect_2d(
    first_start: np.ndarray,
    first_end: np.ndarray,
    second_start: np.ndarray,
    second_end: np.ndarray,
) -> bool:
    def cross(first: np.ndarray, second: np.ndarray) -> float:
        return float(first[0] * second[1] - first[1] * second[0])

    first_direction = first_end - first_start
    second_direction = second_end - second_start
    denominator = cross(first_direction, second_direction)
    offset = second_start - first_start
    scale = max(
        float(np.linalg.norm(first_direction)),
        float(np.linalg.norm(second_direction)),
        1.0,
    )
    tolerance = 64.0 * np.finfo(float).eps * scale * scale
    if abs(denominator) <= tolerance:
        if abs(cross(offset, first_direction)) > tolerance:
            return False
        axis = int(np.argmax(np.abs(first_direction)))
        first_interval = sorted((float(first_start[axis]), float(first_end[axis])))
        second_interval = sorted((float(second_start[axis]), float(second_end[axis])))
        return max(first_interval[0], second_interval[0]) <= min(
            first_interval[1], second_interval[1]
        ) + tolerance
    first_fraction = cross(offset, second_direction) / denominator
    second_fraction = cross(offset, first_direction) / denominator
    return (
        -tolerance <= first_fraction <= 1.0 + tolerance
        and -tolerance <= second_fraction <= 1.0 + tolerance
    )


def _segment_distance_2d(
    first_start: np.ndarray,
    first_end: np.ndarray,
    second_start: np.ndarray,
    second_end: np.ndarray,
) -> float:
    if _segments_intersect_2d(first_start, first_end, second_start, second_end):
        return 0.0
    return min(
        _point_segment_distance_2d(first_start, second_start, second_end),
        _point_segment_distance_2d(first_end, second_start, second_end),
        _point_segment_distance_2d(second_start, first_start, first_end),
        _point_segment_distance_2d(second_end, first_start, first_end),
    )


def diagnose_free_surface_spray_geometry(
    outward_coordinate_m: np.ndarray,
    z_up_m: np.ndarray,
    *,
    minimum_segment_index_gap: int = 3,
) -> SprayGeometryDiagnostic:
    """Measure necessary geometric precursors without modifying the free surface.

    The nodes must be ordered from the body contact toward the outer boundary and
    ``outward_coordinate_m`` must increase away from the hull. Sun's Fig. 2.3
    spray loop necessarily contains an inward-pointing panel before its upper and
    lower branches can approach each other. Nonadjacent distances are therefore
    reported as a topology diagnostic, not as a spray-cut trigger or fit parameter.
    """

    outward = np.asarray(outward_coordinate_m, dtype=float)
    vertical = np.asarray(z_up_m, dtype=float)
    if (
        outward.ndim != 1
        or vertical.shape != outward.shape
        or len(outward) < 4
        or not np.isfinite(outward).all()
        or not np.isfinite(vertical).all()
    ):
        raise ValueError("Spray geometry needs at least four finite free-surface nodes.")
    if int(minimum_segment_index_gap) < 2:
        raise ValueError("minimum_segment_index_gap must be at least two.")

    points = np.column_stack((outward, vertical))
    panel_vectors = np.diff(points, axis=0)
    panel_lengths = np.linalg.norm(panel_vectors, axis=1)
    if np.any(panel_lengths <= np.finfo(float).tiny):
        raise ValueError("Spray geometry contains a zero-length free-surface panel.")
    outward_cosines = panel_vectors[:, 0] / panel_lengths
    cosine_tolerance = 64.0 * np.finfo(float).eps
    overturning_count = int(np.count_nonzero(outward_cosines < -cosine_tolerance))

    minimum_distance: float | None = None
    minimum_ratio: float | None = None
    closest_pair: tuple[int, int] | None = None
    gap = int(minimum_segment_index_gap)
    for first_index in range(len(panel_lengths)):
        for second_index in range(first_index + gap, len(panel_lengths)):
            distance = _segment_distance_2d(
                points[first_index],
                points[first_index + 1],
                points[second_index],
                points[second_index + 1],
            )
            local_length = 0.5 * (
                float(panel_lengths[first_index]) + float(panel_lengths[second_index])
            )
            ratio = distance / local_length
            if minimum_ratio is None or ratio < minimum_ratio:
                minimum_distance = float(distance)
                minimum_ratio = float(ratio)
                closest_pair = (first_index, second_index)

    return SprayGeometryDiagnostic(
        overturning_panel_count=overturning_count,
        minimum_outward_tangent_cosine=float(np.min(outward_cosines)),
        minimum_nonadjacent_distance_m=minimum_distance,
        minimum_nonadjacent_distance_ratio=minimum_ratio,
        closest_nonadjacent_segment_indices=closest_pair,
    )


@dataclass(frozen=True)
class MovingWedgeState:
    right_free_y_m: np.ndarray
    right_free_z_up_m: np.ndarray
    left_free_y_m: np.ndarray
    left_free_z_up_m: np.ndarray
    right_free_potential_m2_s: np.ndarray
    left_free_potential_m2_s: np.ndarray
    time_s: float = 0.0
    status: str = MOVING_WEDGE_BEM_STATUS
    jet_cut_count: int = 0
    minimum_jet_normal_distance_ratio: float | None = None
    minimum_jet_projection_ratio: float | None = None
    maximum_jet_projection_ratio: float | None = None
    maximum_spray_overturning_panel_count: int = 0
    minimum_spray_outward_tangent_cosine: float | None = None
    minimum_spray_nonadjacent_distance_ratio: float | None = None

    def __post_init__(self) -> None:
        ry = np.asarray(self.right_free_y_m, dtype=float)
        rz = np.asarray(self.right_free_z_up_m, dtype=float)
        ly = np.asarray(self.left_free_y_m, dtype=float)
        lz = np.asarray(self.left_free_z_up_m, dtype=float)
        rp = np.asarray(self.right_free_potential_m2_s, dtype=float)
        lp = np.asarray(self.left_free_potential_m2_s, dtype=float)
        if ry.ndim != 1 or rz.shape != ry.shape or ly.ndim != 1 or lz.shape != ly.shape:
            raise ValueError("Moving-wedge free-surface nodes require matching one-dimensional coordinates.")
        panel_values = rp.shape == (len(ry) - 1,) and lp.shape == (len(ly) - 1,)
        node_values = rp.shape == (len(ry),) and lp.shape == (len(ly),)
        if len(ry) < 3 or len(ly) < 3 or not (panel_values or node_values):
            raise ValueError(
                "Moving-wedge potentials require matching panel-centred or nodal arrays."
            )
        if panel_values != (rp.shape != (len(ry),)):
            raise ValueError("Left and right free-surface potentials must use the same location.")
        arrays = (ry, rz, ly, lz, rp, lp)
        if any(not np.isfinite(value).all() for value in arrays) or not np.isfinite(float(self.time_s)):
            raise ValueError("Moving-wedge state must be finite.")
        if int(self.jet_cut_count) != self.jet_cut_count or int(self.jet_cut_count) < 0:
            raise ValueError("jet_cut_count must be a non-negative integer.")
        if (
            int(self.maximum_spray_overturning_panel_count)
            != self.maximum_spray_overturning_panel_count
            or int(self.maximum_spray_overturning_panel_count) < 0
        ):
            raise ValueError("maximum_spray_overturning_panel_count must be non-negative.")
        for name in (
            "minimum_jet_normal_distance_ratio",
            "minimum_jet_projection_ratio",
            "maximum_jet_projection_ratio",
            "minimum_spray_outward_tangent_cosine",
            "minimum_spray_nonadjacent_distance_ratio",
        ):
            value = getattr(self, name)
            if value is not None and not np.isfinite(float(value)):
                raise ValueError(f"{name} must be finite when supplied.")
        for name, value in (
            ("right_free_y_m", ry),
            ("right_free_z_up_m", rz),
            ("left_free_y_m", ly),
            ("left_free_z_up_m", lz),
            ("right_free_potential_m2_s", rp),
            ("left_free_potential_m2_s", lp),
        ):
            object.__setattr__(self, name, value)


def _state_with_updated_spray_diagnostics(state: MovingWedgeState) -> MovingWedgeState:
    right = diagnose_free_surface_spray_geometry(
        state.right_free_y_m,
        state.right_free_z_up_m,
    )
    left = diagnose_free_surface_spray_geometry(
        -state.left_free_y_m[::-1],
        state.left_free_z_up_m[::-1],
    )
    current_overturning_count = max(
        right.overturning_panel_count,
        left.overturning_panel_count,
    )
    current_minimum_cosine = min(
        right.minimum_outward_tangent_cosine,
        left.minimum_outward_tangent_cosine,
    )
    current_distance_ratios = [
        value
        for value in (
            right.minimum_nonadjacent_distance_ratio,
            left.minimum_nonadjacent_distance_ratio,
        )
        if value is not None
    ]
    current_minimum_distance_ratio = (
        None if not current_distance_ratios else min(current_distance_ratios)
    )
    historical_cosine = state.minimum_spray_outward_tangent_cosine
    historical_distance_ratio = state.minimum_spray_nonadjacent_distance_ratio
    return replace(
        state,
        maximum_spray_overturning_panel_count=max(
            int(state.maximum_spray_overturning_panel_count),
            current_overturning_count,
        ),
        minimum_spray_outward_tangent_cosine=(
            current_minimum_cosine
            if historical_cosine is None
            else min(float(historical_cosine), current_minimum_cosine)
        ),
        minimum_spray_nonadjacent_distance_ratio=(
            historical_distance_ratio
            if current_minimum_distance_ratio is None
            else current_minimum_distance_ratio
            if historical_distance_ratio is None
            else min(float(historical_distance_ratio), current_minimum_distance_ratio)
        ),
    )


@dataclass(frozen=True)
class MovingWedgeRhs:
    right_node_velocity_mps: np.ndarray
    left_node_velocity_mps: np.ndarray
    right_potential_rate_m2_s2: np.ndarray
    left_potential_rate_m2_s2: np.ndarray
    potential_relative_residual: float
    potential_condition_number: float


@dataclass(frozen=True)
class MovingWedgeStepResult:
    state: MovingWedgeState
    max_potential_relative_residual: float
    max_potential_condition_number: float
    separation_event_time_s: float | None = None
    jet_cut_event_time_s: float | None = None


@dataclass(frozen=True)
class MovingWedgeLoadResult:
    pressure: PressureAuxiliaryResult
    boundary: ClosedBoundary2D
    contact_constraint_max_abs_m: float
    potential_bvp_relative_residual: float
    potential_bvp_condition_number: float


@dataclass(frozen=True)
class MovingWedgeTimeHistory:
    time_s: np.ndarray
    vertical_force_per_length_n_m: np.ndarray
    potential_bvp_relative_residual: np.ndarray
    pressure_bvp_relative_residual: np.ndarray
    free_surface_pressure_max_abs_pa: np.ndarray
    contact_constraint_max_abs_m: np.ndarray
    final_state: MovingWedgeState


@dataclass(frozen=True)
class MovingWedgeHeaveCoefficients:
    omega_rad_s: float
    motion_amplitude_m: float
    added_mass_per_length_kg_m: float
    damping_per_length_kg_m_s: float
    restoring_per_length_n_m2: float
    harmonic_fit: FirstHarmonicFit
    status: str = MOVING_WEDGE_BEM_STATUS


@dataclass(frozen=True)
class SteadyPlaningWedgeEntryResult:
    time_s: np.ndarray
    x_from_leading_edge_m: np.ndarray
    draft_m: np.ndarray
    vertical_force_per_length_n_m: np.ndarray
    states: tuple[MovingWedgeState, ...]
    reference_draft_m: float
    final_jet_cut_count: int
    separated_state_count: int
    separation_event_count: int
    first_separation_time_s: float | None
    first_separation_x_from_leading_m: float | None
    minimum_jet_normal_distance_ratio: float | None
    minimum_jet_projection_ratio: float | None
    maximum_jet_projection_ratio: float | None
    max_potential_bvp_relative_residual: float
    max_pressure_bvp_relative_residual: float
    max_contact_constraint_abs_m: float
    status: str = "sun_2dt_steady_planing_wedge_entry_wagner_initializer_pending"


def initialize_moving_wedge_state(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    *,
    time_s: float = 0.0,
    incident_wave: RegularIncidentWave2D | None = None,
) -> MovingWedgeState:
    apex_z = -float(config.mean_draft_m) + float(motion.displacement_m(time_s))
    undisturbed_elevation = (
        0.0 if incident_wave is None else incident_wave.elevation_m(time_s)
    )
    submergence = undisturbed_elevation - apex_z
    geometric_contact = submergence / np.tan(float(config.deadrise_rad))
    wagner_contact = 0.5 * np.pi * geometric_contact
    candidate_contact = wagner_contact if config.initializer == "wagner" else geometric_contact
    separated = bool(
        config.chine_separation_enabled and candidate_contact >= float(config.chine_half_beam_m)
    )
    contact_half_beam = (
        float(config.chine_half_beam_m) if separated else candidate_contact
    )
    contact_z = (
        apex_z + contact_half_beam * np.tan(float(config.deadrise_rad))
        if separated
        else undisturbed_elevation
    )
    if not 0.0 < contact_half_beam <= float(config.chine_half_beam_m):
        raise ValueError("Initial wedge contact lies outside the supported pre-chine interval.")
    count = int(config.free_surface_panels_per_side)
    extent = float(config.free_surface_extent_m)
    if config.free_surface_spacing_mode == "body_matched_geometric":
        first_panel_length = contact_half_beam / (
            int(config.body_panels_per_side) * np.cos(float(config.deadrise_rad))
        )
        right_y = contact_half_beam + _geometric_node_arclengths(
            extent - contact_half_beam,
            count,
            first_panel_length,
            uniform_panel_count=int(config.free_surface_uniform_near_body_panel_count),
        )
    else:
        right_y = np.linspace(contact_half_beam, extent, count + 1)
    left_y = -right_y[::-1]
    if config.initializer == "wagner" and not separated:
        right_z = (
            right_y
            * submergence
            / contact_half_beam
            * np.arcsin(np.clip(contact_half_beam / right_y, 0.0, 1.0))
            - submergence
            + undisturbed_elevation
        )
        left_z = right_z[::-1]
    else:
        right_z = np.linspace(contact_z, undisturbed_elevation, count + 1)
        left_z = np.linspace(undisturbed_elevation, contact_z, count + 1)
    return _state_with_updated_spray_diagnostics(
        MovingWedgeState(
            right_free_y_m=right_y,
            right_free_z_up_m=right_z,
            left_free_y_m=left_y,
            left_free_z_up_m=left_z,
            right_free_potential_m2_s=np.zeros(
                count + 1 if config.element_interpolation == "linear_node" else count
            ),
            left_free_potential_m2_s=np.zeros(
                count + 1 if config.element_interpolation == "linear_node" else count
            ),
            time_s=float(time_s),
        )
    )


def moving_wedge_boundary(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
) -> ClosedBoundary2D:
    extent = float(config.free_surface_extent_m)
    depth = float(config.water_depth_m)
    apex_z = -float(config.mean_draft_m) + float(motion.displacement_m(state.time_s))
    right_separated = bool(
        config.knuckle_separation_model == "artificial_surface"
        and state.right_free_y_m[0] > float(config.chine_half_beam_m) * (1.0 + 1e-10)
    )
    left_separated = bool(
        config.knuckle_separation_model == "artificial_surface"
        and -state.left_free_y_m[-1] > float(config.chine_half_beam_m) * (1.0 + 1e-10)
    )
    nodes: list[tuple[float, float]] = [
        (float(state.right_free_y_m[0]), float(state.right_free_z_up_m[0]))
    ]
    labels: list[str] = []

    def append_given(y: np.ndarray, z: np.ndarray, label: str) -> None:
        nodes.extend((float(yi), float(zi)) for yi, zi in zip(y[1:], z[1:]))
        labels.extend([label] * (len(y) - 1))

    def append_linear(end_y: float, end_z: float, panel_count: int, label: str) -> None:
        start_y, start_z = nodes[-1]
        y = np.linspace(start_y, float(end_y), int(panel_count) + 1)
        z = np.linspace(start_z, float(end_z), int(panel_count) + 1)
        append_given(y, z, label)

    chine = float(config.chine_half_beam_m)
    chine_z = apex_z + chine * np.tan(float(config.deadrise_rad))
    append_given(state.right_free_y_m, state.right_free_z_up_m, "free_surface")
    append_linear(extent, -depth, int(config.side_wall_panels), "wall")
    if config.use_symmetry_half_domain:
        append_linear(
            0.0,
            -depth,
            max(int(config.bottom_panels) // 2, 2),
            "bottom",
        )
        symmetry_length = apex_z + depth
        symmetry_count = max(
            int(config.body_panels_per_side),
            int(config.side_wall_panels),
        )
        body_contact_length = max(
            float(state.right_free_y_m[0]),
            np.finfo(float).eps,
        ) / (
            int(config.body_panels_per_side) * np.cos(float(config.deadrise_rad))
        )
        symmetry_from_apex = _geometric_node_arclengths(
            symmetry_length,
            symmetry_count,
            body_contact_length,
        )
        symmetry_z = apex_z - symmetry_from_apex[::-1]
        append_given(
            np.zeros(symmetry_count + 1),
            symmetry_z,
            "symmetry",
        )
        if right_separated:
            append_linear(chine, chine_z, int(config.body_panels_per_side), "body")
            append_linear(
                float(state.right_free_y_m[0]),
                float(state.right_free_z_up_m[0]),
                1,
                "artificial_body",
            )
        else:
            append_linear(
                float(state.right_free_y_m[0]),
                float(state.right_free_z_up_m[0]),
                int(config.body_panels_per_side),
                "body",
            )
        coordinates = np.asarray(nodes, dtype=float)
        return ClosedBoundary2D(coordinates[:, 0], coordinates[:, 1], tuple(labels))

    append_linear(-extent, -depth, int(config.bottom_panels), "bottom")
    append_linear(
        -extent,
        float(state.left_free_z_up_m[0]),
        int(config.side_wall_panels),
        "wall",
    )
    append_given(state.left_free_y_m, state.left_free_z_up_m, "free_surface")
    if left_separated:
        append_linear(-chine, chine_z, 1, "artificial_body")
    append_linear(0.0, apex_z, int(config.body_panels_per_side), "body")
    if right_separated:
        append_linear(chine, chine_z, int(config.body_panels_per_side), "body")
        append_linear(
            float(state.right_free_y_m[0]),
            float(state.right_free_z_up_m[0]),
            1,
            "artificial_body",
        )
    else:
        append_linear(
            float(state.right_free_y_m[0]),
            float(state.right_free_z_up_m[0]),
            int(config.body_panels_per_side),
            "body",
        )
    coordinates = np.asarray(nodes, dtype=float)
    return ClosedBoundary2D(coordinates[:, 0], coordinates[:, 1], tuple(labels))


def _contact_velocity(
    candidate: np.ndarray,
    *,
    side: str,
    deadrise_rad: float,
    apex_velocity_mps: float,
) -> np.ndarray:
    tan_beta = np.tan(float(deadrise_rad))
    constraint_normal = np.asarray((-tan_beta, 1.0) if side == "right" else (tan_beta, 1.0))
    correction = (
        float(apex_velocity_mps) - float(np.dot(constraint_normal, candidate))
    ) / float(np.dot(constraint_normal, constraint_normal))
    return np.asarray(candidate, dtype=float) + correction * constraint_normal


def _linear_neumann_endpoint_values(
    boundary: ClosedBoundary2D,
    *,
    body_vertical_value: float,
    incident_endpoint_values: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(boundary.panel_labels, dtype=object)
    dirichlet_panels = labels == "free_surface"
    q_endpoints = np.zeros((boundary.panel_count, 2), dtype=float)
    body_panels = (labels == "body") | (labels == "artificial_body")
    if incident_endpoint_values is None:
        q_endpoints[body_panels, :] = (
            boundary.panel_normal[body_panels, 1] * float(body_vertical_value)
        )[:, None]
        return dirichlet_panels, q_endpoints
    incident = (
        np.asarray(incident_endpoint_values, dtype=float)
    )
    if incident.shape != (boundary.panel_count, 2) or not np.isfinite(incident).all():
        raise ValueError("incident_endpoint_values must be finite with shape (n_panel, 2).")
    q_endpoints[body_panels, :] = boundary.panel_normal[
        body_panels, 1, None
    ] * (float(body_vertical_value) - incident[body_panels, :])
    return dirichlet_panels, q_endpoints


def _incident_endpoint_values(
    boundary: ClosedBoundary2D,
    incident_wave: RegularIncidentWave2D | None,
    *,
    time_s: float,
    derivative: Literal["velocity", "acceleration"],
) -> np.ndarray:
    if incident_wave is None:
        return np.zeros((boundary.panel_count, 2), dtype=float)
    left_z = boundary.node_z_up_m[:-1]
    right_z = boundary.node_z_up_m[1:]
    evaluator = (
        incident_wave.vertical_velocity_mps
        if derivative == "velocity"
        else incident_wave.vertical_acceleration_mps2
    )
    return np.column_stack(
        (
            evaluator(time_s, left_z),
            evaluator(time_s, right_z),
        )
    )


def _linear_free_surface_node_velocity(
    boundary: ClosedBoundary2D,
    solution,
    free_panel_count: int,
) -> np.ndarray:
    return _linear_free_surface_node_velocity_from_values(
        boundary,
        solution.potential_m2_s[: int(free_panel_count) + 1],
        solution.normal_derivative_m_s[: int(free_panel_count) + 1],
        free_panel_count,
    )


def _linear_free_surface_node_velocity_from_values(
    boundary: ClosedBoundary2D,
    potential_m2_s: np.ndarray,
    normal_derivative_m_s: np.ndarray,
    free_panel_count: int,
) -> np.ndarray:
    """Reconstruct free-surface velocity using Sun (2007), Eqs. 2.27-2.28."""

    count = int(free_panel_count)
    phi = np.asarray(potential_m2_s, dtype=float)
    q = np.asarray(normal_derivative_m_s, dtype=float)
    if phi.shape != (count + 1,) or q.shape != (count + 1,):
        raise MovingWedgeContactExitError(
            "Linear free-surface potential and normal derivative need one value per node."
        )
    panel_length = boundary.panel_length_m[:count]
    panel_tangent = boundary.panel_tangent[:count]
    panel_normal = boundary.panel_normal[:count]
    tangent = np.empty((count + 1, 2), dtype=float)
    normal = np.empty((count + 1, 2), dtype=float)
    tangent[0], tangent[-1] = panel_tangent[0], panel_tangent[-1]
    normal[0], normal[-1] = panel_normal[0], panel_normal[-1]
    if count > 1:
        tangent[1:-1] = (
            panel_length[:-1, None] * panel_tangent[:-1]
            + panel_length[1:, None] * panel_tangent[1:]
        )
        normal[1:-1] = (
            panel_length[:-1, None] * panel_normal[:-1]
            + panel_length[1:, None] * panel_normal[1:]
        )
        tangent[1:-1] /= np.maximum(
            np.linalg.norm(tangent[1:-1], axis=1)[:, None],
            np.finfo(float).eps,
        )
        normal[1:-1] /= np.maximum(
            np.linalg.norm(normal[1:-1], axis=1)[:, None],
            np.finfo(float).eps,
        )
    tangential = np.empty(count + 1, dtype=float)
    if count == 1:
        tangential[:] = (phi[1] - phi[0]) / panel_length[0]
    else:
        h1 = panel_length[0]
        h2 = panel_length[1]
        tangential[0] = (
            -(h2**2 + 2.0 * h1 * h2) * phi[0]
            + (h1 + h2) ** 2 * phi[1]
            - h1**2 * phi[2]
        ) / (h1 * h2 * (h1 + h2))
        previous = panel_length[:-1]
        following = panel_length[1:]
        tangential[1:-1] = (
            -(following**2) * phi[:-2]
            + (following**2 - previous**2) * phi[1:-1]
            + previous**2 * phi[2:]
        ) / (following * previous * (following + previous))
        h_previous = panel_length[-2]
        h_last = panel_length[-1]
        tangential[-1] = (
            h_last**2 * phi[-3]
            - (h_previous + h_last) ** 2 * phi[-2]
            + (h_previous**2 + 2.0 * h_previous * h_last) * phi[-1]
        ) / (h_previous * h_last * (h_previous + h_last))
    return tangential[:, None] * tangent + q[:, None] * normal


def _solve_linear_free_surface_normal_derivative(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
    incident_wave: RegularIncidentWave2D | None = None,
):
    boundary = moving_wedge_boundary(config, motion, state)
    labels = np.asarray(boundary.panel_labels, dtype=object)
    free_panel_count = int(np.count_nonzero(labels == "free_surface"))
    dirichlet_panels, q_endpoints = _linear_neumann_endpoint_values(
        boundary,
        body_vertical_value=float(motion.velocity_mps(state.time_s)),
        incident_endpoint_values=(
            None
            if incident_wave is None
            else _incident_endpoint_values(
                boundary,
                incident_wave,
                time_s=state.time_s,
                derivative="velocity",
            )
        ),
    )
    phi_known = np.zeros(boundary.panel_count, dtype=float)
    phi_known[: free_panel_count + 1] = state.right_free_potential_m2_s
    solution = solve_linear_element_mixed_boundary_laplace(
        boundary,
        dirichlet_panel_mask=dirichlet_panels,
        dirichlet_node_values=phi_known,
        neumann_endpoint_values=q_endpoints,
        gauss_order=int(config.gauss_order),
    )
    return boundary, free_panel_count, solution


def _evaluate_linear_moving_wedge_rhs_with_frozen_normal(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
    normal_derivative_m_s: np.ndarray,
    *,
    potential_relative_residual: float,
    potential_condition_number: float,
    gravity_m_s2: float,
    separation_velocity_mps: np.ndarray | None = None,
    incident_wave: RegularIncidentWave2D | None = None,
) -> MovingWedgeRhs:
    boundary = moving_wedge_boundary(config, motion, state)
    labels = np.asarray(boundary.panel_labels, dtype=object)
    free_panel_count = int(np.count_nonzero(labels == "free_surface"))
    right_node_velocity = _linear_free_surface_node_velocity_from_values(
        boundary,
        state.right_free_potential_m2_s,
        normal_derivative_m_s,
        free_panel_count,
    )
    incident_vertical_nodes = None
    if incident_wave is not None:
        incident_vertical_nodes = incident_wave.vertical_velocity_mps(
            state.time_s,
            boundary.node_z_up_m[: free_panel_count + 1],
        )
        right_node_velocity = right_node_velocity.copy()
        right_node_velocity[:, 1] += incident_vertical_nodes
    body_velocity_z = float(motion.velocity_mps(state.time_s))
    right_separated = bool(
        config.chine_separation_enabled
        and state.right_free_y_m[0]
        >= float(config.chine_half_beam_m) * (1.0 - 1e-10)
    )
    contact_candidate = right_node_velocity[0]
    if (
        right_separated
        and config.knuckle_separation_model == "artificial_surface"
        and separation_velocity_mps is not None
    ):
        contact_candidate = np.asarray(separation_velocity_mps, dtype=float)
    if right_separated and config.knuckle_separation_model == "clamped":
        right_node_velocity[0] = np.asarray((0.0, body_velocity_z))
    elif right_separated and config.knuckle_separation_model == "artificial_surface":
        right_node_velocity[0] = _contact_velocity(
            contact_candidate,
            side="right",
            deadrise_rad=config.deadrise_rad,
            apex_velocity_mps=body_velocity_z,
        )
    # Before separation the spray root is not a material point fixed to the
    # body. Sun Sec. 2.3 advances the free-surface endpoint with the solved
    # free-side velocity and then projects it normally onto the new body.
    # Constraining an extrapolated velocity to the wedge here suppresses the
    # Wagner contact speed by more than an order of magnitude.
    right_node_velocity[-1, 0] = 0.0
    left_node_velocity = right_node_velocity[::-1] * np.asarray((-1.0, 1.0))
    free_z = boundary.node_z_up_m[: free_panel_count + 1]
    if incident_wave is None:
        potential_rate = (
            0.5 * np.sum(right_node_velocity**2, axis=1)
            - float(gravity_m_s2) * free_z
        )
    else:
        right_disturbance_velocity = right_node_velocity.copy()
        right_disturbance_velocity[:, 1] -= incident_vertical_nodes
        potential_rate = 0.5 * np.sum(right_disturbance_velocity**2, axis=1)
        potential_rate -= float(gravity_m_s2) * free_z
        potential_rate -= incident_wave.potential_time_derivative_m2_s2(
            state.time_s,
            free_z,
        )
    beach_length = float(config.damping_beach_length_m)
    if beach_length > 0.0:
        free_y = boundary.node_y_m[: free_panel_count + 1]
        beach_start = float(config.free_surface_extent_m) - beach_length
        coordinate = np.clip((np.abs(free_y) - beach_start) / beach_length, 0.0, 1.0)
        ramp = -2.0 * coordinate**3 + 3.0 * coordinate**2
        mean_waterline_beam = 2.0 * float(config.mean_draft_m) / np.tan(
            float(config.deadrise_rad)
        )
        nu0 = float(config.damping_beach_beta0) * np.sqrt(
            0.5 * float(gravity_m_s2) * mean_waterline_beam
        )
        potential_rate -= nu0 * ramp * np.asarray(normal_derivative_m_s, dtype=float)
    return MovingWedgeRhs(
        right_node_velocity_mps=right_node_velocity,
        left_node_velocity_mps=left_node_velocity,
        right_potential_rate_m2_s2=potential_rate,
        left_potential_rate_m2_s2=potential_rate[::-1],
        potential_relative_residual=float(potential_relative_residual),
        potential_condition_number=float(potential_condition_number),
    )


def _linear_physical_knuckle_velocity(
    boundary: ClosedBoundary2D,
    potential_solution,
    *,
    body_velocity_z: float,
    incident_vertical_velocity_mps: float = 0.0,
) -> np.ndarray:
    """Return disturbance velocity next to Sun's separation point S.

    The solved potential is the disturbance potential.  Its body-normal
    derivative is therefore ``n_z * (V_BO - phi_I,z)`` (Sun--Faltinsen
    Eq. 15), while the tangential derivative comes directly from the nodal
    potential.  Add the incident velocity only when a total fluid velocity is
    needed to advect a free-surface point.
    """

    labels = np.asarray(boundary.panel_labels, dtype=object)
    physical = np.flatnonzero(
        (labels == "body") & (boundary.panel_mid_y_m >= -1e-12)
    )
    if physical.size < 1:
        raise ValueError("Knuckle separation needs at least one physical body panel.")
    ordered = physical[np.argsort(boundary.panel_mid_y_m[physical])]
    knuckle_panel = int(ordered[-1])
    knuckle_node = (knuckle_panel + 1) % boundary.panel_count
    separation_speed = float(
        (
            potential_solution.potential_m2_s[knuckle_node]
            - potential_solution.potential_m2_s[knuckle_panel]
        )
        / boundary.panel_length_m[knuckle_panel]
    )
    tangent = boundary.panel_tangent[knuckle_panel]
    normal = boundary.panel_normal[knuckle_panel]
    return (
        separation_speed * tangent
        + normal
        * normal[1]
        * (float(body_velocity_z) - float(incident_vertical_velocity_mps))
    )


def _linear_physical_knuckle_potential(
    boundary: ClosedBoundary2D,
    potential_solution,
) -> float:
    labels = np.asarray(boundary.panel_labels, dtype=object)
    physical = np.flatnonzero(
        (labels == "body") & (boundary.panel_mid_y_m >= -1e-12)
    )
    if physical.size == 0:
        raise ValueError("Knuckle potential needs a physical starboard body panel.")
    knuckle_panel = int(physical[np.argmax(boundary.panel_mid_y_m[physical])])
    knuckle_node = (knuckle_panel + 1) % boundary.panel_count
    return float(potential_solution.potential_m2_s[knuckle_node])


def evaluate_moving_wedge_rhs(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
    *,
    gravity_m_s2: float = 9.80665,
    incident_wave: RegularIncidentWave2D | None = None,
) -> MovingWedgeRhs:
    boundary = moving_wedge_boundary(config, motion, state)
    labels = np.asarray(boundary.panel_labels, dtype=object)
    body_mask = (labels == "body") | (labels == "artificial_body")
    free_mask = labels == "free_surface"
    body_velocity_z = float(motion.velocity_mps(state.time_s))
    if config.element_interpolation == "linear_node":
        linear_boundary, free_panel_count, potential = _solve_linear_free_surface_normal_derivative(
            config,
            motion,
            state,
            incident_wave,
        )
        separation_velocity = None
        separation_disturbance_velocity = None
        if (
            config.knuckle_separation_model == "artificial_surface"
            and state.right_free_y_m[0]
            >= float(config.chine_half_beam_m) * (1.0 - 1e-10)
        ):
            incident_knuckle_velocity = (
                0.0
                if incident_wave is None
                else float(
                    incident_wave.vertical_velocity_mps(
                        state.time_s,
                        linear_boundary.node_z_up_m[free_panel_count],
                    )
                )
            )
            separation_velocity = _linear_physical_knuckle_velocity(
                linear_boundary,
                potential,
                body_velocity_z=body_velocity_z,
                incident_vertical_velocity_mps=incident_knuckle_velocity,
            )
            if incident_wave is not None:
                separation_velocity[1] += incident_knuckle_velocity
        return _evaluate_linear_moving_wedge_rhs_with_frozen_normal(
            config,
            motion,
            state,
            potential.normal_derivative_m_s[: free_panel_count + 1],
            potential_relative_residual=potential.relative_residual,
            potential_condition_number=potential.condition_number,
            gravity_m_s2=float(gravity_m_s2),
            separation_velocity_mps=separation_velocity,
            incident_wave=incident_wave,
        )

    incident_body_velocity = (
        np.zeros(int(np.count_nonzero(body_mask)), dtype=float)
        if incident_wave is None
        else incident_wave.vertical_velocity_mps(
            state.time_s,
            boundary.panel_mid_z_up_m[body_mask],
        )
    )
    body_normal_velocity = boundary.panel_normal[body_mask, 1] * (
        body_velocity_z - incident_body_velocity
    )
    free_potential = (
        state.right_free_potential_m2_s
        if config.use_symmetry_half_domain
        else np.concatenate(
            (state.right_free_potential_m2_s, state.left_free_potential_m2_s)
        )
    )
    potential = solve_section_potential_bvp(
        boundary,
        free_surface_potential_m2_s=free_potential,
        body_normal_velocity_mps=body_normal_velocity,
        gauss_order=int(config.gauss_order),
    )
    velocity = boundary_velocity(boundary, potential)
    free_velocity = velocity[free_mask]
    right_count = len(state.right_free_potential_m2_s)
    right_panel_velocity = free_velocity[:right_count]
    if config.use_symmetry_half_domain:
        left_panel_velocity = right_panel_velocity[::-1] * np.asarray((-1.0, 1.0))
    else:
        left_panel_velocity = free_velocity[right_count:]

    def panel_to_node(panel_velocity: np.ndarray) -> np.ndarray:
        node_velocity = np.zeros((len(panel_velocity) + 1, 2), dtype=float)
        node_velocity[0] = panel_velocity[0]
        node_velocity[-1] = panel_velocity[-1]
        if len(panel_velocity) > 1:
            node_velocity[1:-1] = 0.5 * (panel_velocity[:-1] + panel_velocity[1:])
        return node_velocity

    right_node_velocity = panel_to_node(right_panel_velocity)
    left_node_velocity = panel_to_node(left_panel_velocity)
    if incident_wave is not None:
        right_node_velocity[:, 1] += incident_wave.vertical_velocity_mps(
            state.time_s, state.right_free_z_up_m
        )
        left_node_velocity[:, 1] += incident_wave.vertical_velocity_mps(
            state.time_s, state.left_free_z_up_m
        )
    right_separated = bool(
        config.chine_separation_enabled
        and state.right_free_y_m[0] >= float(config.chine_half_beam_m) * (1.0 - 1e-10)
    )
    left_separated = bool(
        config.chine_separation_enabled
        and -state.left_free_y_m[-1] >= float(config.chine_half_beam_m) * (1.0 - 1e-10)
    )
    right_candidate = right_node_velocity[0]
    left_candidate = left_node_velocity[-1]
    if config.knuckle_separation_model == "artificial_surface" and right_separated:
        physical = np.flatnonzero(labels == "body")
        right_panel = physical[np.argmax(boundary.panel_mid_y_m[physical])]
        right_candidate = velocity[right_panel].copy()
        if incident_wave is not None:
            right_candidate[1] += float(
                incident_wave.vertical_velocity_mps(
                    state.time_s,
                    boundary.panel_mid_z_up_m[right_panel],
                )
            )
    if config.knuckle_separation_model == "artificial_surface" and left_separated:
        physical = np.flatnonzero(labels == "body")
        left_panel = physical[np.argmin(boundary.panel_mid_y_m[physical])]
        left_candidate = velocity[left_panel].copy()
        if incident_wave is not None:
            left_candidate[1] += float(
                incident_wave.vertical_velocity_mps(
                    state.time_s,
                    boundary.panel_mid_z_up_m[left_panel],
                )
            )
    right_node_velocity[0] = (
        np.asarray((0.0, body_velocity_z))
        if right_separated and config.knuckle_separation_model == "clamped"
        else _contact_velocity(
            right_candidate,
            side="right",
            deadrise_rad=config.deadrise_rad,
            apex_velocity_mps=body_velocity_z,
        )
    )
    right_node_velocity[-1, 0] = 0.0
    left_node_velocity[0, 0] = 0.0
    left_node_velocity[-1] = (
        np.asarray((0.0, body_velocity_z))
        if left_separated and config.knuckle_separation_model == "clamped"
        else _contact_velocity(
            left_candidate,
            side="left",
            deadrise_rad=config.deadrise_rad,
            apex_velocity_mps=body_velocity_z,
        )
    )
    free_z = boundary.panel_mid_z_up_m[free_mask]
    potential_rate = 0.5 * np.sum(free_velocity**2, axis=1) - float(gravity_m_s2) * free_z
    if incident_wave is not None:
        potential_rate -= incident_wave.potential_time_derivative_m2_s2(
            state.time_s,
            free_z,
        )
    beach_length = float(config.damping_beach_length_m)
    if beach_length > 0.0:
        free_y = boundary.panel_mid_y_m[free_mask]
        beach_start = float(config.free_surface_extent_m) - beach_length
        coordinate = np.clip((np.abs(free_y) - beach_start) / beach_length, 0.0, 1.0)
        ramp = -2.0 * coordinate**3 + 3.0 * coordinate**2
        mean_waterline_beam = 2.0 * float(config.mean_draft_m) / np.tan(float(config.deadrise_rad))
        nu0 = float(config.damping_beach_beta0) * np.sqrt(
            0.5 * float(gravity_m_s2) * mean_waterline_beam
        )
        potential_rate -= nu0 * ramp * potential.normal_derivative_m_s[free_mask]
    right_potential_rate = potential_rate[:right_count]
    left_potential_rate = (
        right_potential_rate[::-1]
        if config.use_symmetry_half_domain
        else potential_rate[right_count:]
    )
    return MovingWedgeRhs(
        right_node_velocity_mps=right_node_velocity,
        left_node_velocity_mps=left_node_velocity,
        right_potential_rate_m2_s2=right_potential_rate,
        left_potential_rate_m2_s2=left_potential_rate,
        potential_relative_residual=potential.relative_residual,
        potential_condition_number=potential.condition_number,
    )


def _increment_moving_wedge_state(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
    rhs: MovingWedgeRhs,
    scale_s: float,
) -> MovingWedgeState:
    scale = float(scale_s)
    new_time = float(state.time_s + scale)
    right_y = state.right_free_y_m + scale * rhs.right_node_velocity_mps[:, 0]
    right_z = state.right_free_z_up_m + scale * rhs.right_node_velocity_mps[:, 1]
    left_y = state.left_free_y_m + scale * rhs.left_node_velocity_mps[:, 0]
    left_z = state.left_free_z_up_m + scale * rhs.left_node_velocity_mps[:, 1]
    right_y[-1] = float(config.free_surface_extent_m)
    left_y[0] = -float(config.free_surface_extent_m)
    apex_z = -float(config.mean_draft_m) + float(motion.displacement_m(new_time))
    tan_beta = np.tan(float(config.deadrise_rad))
    chine = float(config.chine_half_beam_m)
    right_was_separated = bool(state.right_free_y_m[0] >= chine * (1.0 - 1e-10))
    left_was_separated = bool(-state.left_free_y_m[-1] >= chine * (1.0 - 1e-10))
    if not right_was_separated:
        tangent = np.asarray(
            (np.cos(float(config.deadrise_rad)), np.sin(float(config.deadrise_rad))),
            dtype=float,
        )
        provisional = np.asarray((right_y[0], right_z[0] - apex_z), dtype=float)
        arclength = float(np.dot(provisional, tangent))
        right_y[0] = arclength * tangent[0]
        right_z[0] = apex_z + arclength * tangent[1]
    if not left_was_separated:
        tangent = np.asarray(
            (-np.cos(float(config.deadrise_rad)), np.sin(float(config.deadrise_rad))),
            dtype=float,
        )
        provisional = np.asarray((left_y[-1], left_z[-1] - apex_z), dtype=float)
        arclength = float(np.dot(provisional, tangent))
        left_y[-1] = arclength * tangent[0]
        left_z[-1] = apex_z + arclength * tangent[1]
    if (
        config.chine_separation_enabled
        and config.knuckle_separation_model == "clamped"
        and right_y[0] >= float(config.chine_half_beam_m)
    ):
        right_y[0] = float(config.chine_half_beam_m)
    if (
        config.chine_separation_enabled
        and config.knuckle_separation_model == "clamped"
        and -left_y[-1] >= float(config.chine_half_beam_m)
    ):
        left_y[-1] = -float(config.chine_half_beam_m)
    if (
        config.chine_separation_enabled
        and config.knuckle_separation_model == "artificial_surface"
        and right_was_separated
        and right_y[0] < chine
    ):
        right_y[0] = chine
    if (
        config.chine_separation_enabled
        and config.knuckle_separation_model == "artificial_surface"
        and left_was_separated
        and -left_y[-1] < chine
    ):
        left_y[-1] = -chine
    if config.enforce_lateral_symmetry:
        symmetric_y = 0.5 * (right_y - left_y[::-1])
        symmetric_z = 0.5 * (right_z + left_z[::-1])
        right_y = symmetric_y
        left_y = -symmetric_y[::-1]
        right_z = symmetric_z
        left_z = symmetric_z[::-1]
    right_z[0] = apex_z + right_y[0] * tan_beta
    left_z[-1] = apex_z - left_y[-1] * tan_beta
    maximum_contact = (
        config.chine_half_beam_m
        if config.knuckle_separation_model == "clamped"
        else config.free_surface_extent_m
    )
    if right_y[0] <= 0.0 or right_y[0] > maximum_contact * (1.0 + 1e-12):
        raise MovingWedgeContactExitError(
            "Right moving-wedge contact left the supported interval: "
            f"contact={right_y[0]:.9g} m, limit={maximum_contact:.9g} m, "
            f"time={new_time:.9g} s."
        )
    if left_y[-1] >= 0.0 or -left_y[-1] > maximum_contact * (1.0 + 1e-12):
        raise ValueError(
            "Left moving-wedge contact left the supported interval: "
            f"contact={left_y[-1]:.9g} m, limit={maximum_contact:.9g} m, "
            f"time={new_time:.9g} s."
        )
    right_potential = state.right_free_potential_m2_s + scale * rhs.right_potential_rate_m2_s2
    left_potential = state.left_free_potential_m2_s + scale * rhs.left_potential_rate_m2_s2
    if config.enforce_lateral_symmetry:
        symmetric_potential = 0.5 * (right_potential + left_potential[::-1])
        right_potential = symmetric_potential
        left_potential = symmetric_potential[::-1]
    return MovingWedgeState(
        right_free_y_m=right_y,
        right_free_z_up_m=right_z,
        left_free_y_m=left_y,
        left_free_z_up_m=left_z,
        right_free_potential_m2_s=right_potential,
        left_free_potential_m2_s=left_potential,
        time_s=new_time,
        jet_cut_count=state.jet_cut_count,
        minimum_jet_normal_distance_ratio=state.minimum_jet_normal_distance_ratio,
        minimum_jet_projection_ratio=state.minimum_jet_projection_ratio,
        maximum_jet_projection_ratio=state.maximum_jet_projection_ratio,
        maximum_spray_overturning_panel_count=(
            state.maximum_spray_overturning_panel_count
        ),
        minimum_spray_outward_tangent_cosine=(
            state.minimum_spray_outward_tangent_cosine
        ),
        minimum_spray_nonadjacent_distance_ratio=(
            state.minimum_spray_nonadjacent_distance_ratio
        ),
    )


def _geometric_node_arclengths(
    total_length_m: float,
    panel_count: int,
    first_panel_length_m: float,
    *,
    uniform_panel_count: int = 1,
) -> np.ndarray:
    """Return uniform near-body panels followed by geometric far-field growth."""

    total = float(total_length_m)
    count = int(panel_count)
    first = float(first_panel_length_m)
    uniform = min(max(int(uniform_panel_count), 1), count)
    if total <= 0.0 or count < 1 or first <= 0.0:
        raise ValueError("Geometric spacing needs positive length, panel count, and first panel.")
    if first * count >= total * (1.0 - 1e-12):
        return np.linspace(0.0, total, count + 1)

    remaining = count - uniform
    if remaining == 0:
        return np.linspace(0.0, total, count + 1)

    def series_sum(ratio: float) -> float:
        far = first * ratio * (ratio**remaining - 1.0) / (ratio - 1.0)
        return first * uniform + far

    lower = 1.0
    upper = 1.1
    while series_sum(upper) < total:
        upper *= 1.5
    for _ in range(80):
        middle = 0.5 * (lower + upper)
        if series_sum(middle) < total:
            lower = middle
        else:
            upper = middle
    ratio = 0.5 * (lower + upper)
    panel_lengths = np.concatenate(
        (
            np.full(uniform, first, dtype=float),
            first * ratio ** np.arange(1, remaining + 1, dtype=float),
        )
    )
    panel_lengths[-1] += total - float(np.sum(panel_lengths))
    return np.concatenate(([0.0], np.cumsum(panel_lengths)))


def _sun_five_point_third_order_smooth(values: np.ndarray) -> np.ndarray:
    """Apply Sun (2007), Eqs. 2.21a-e, to one node sequence."""

    original = np.asarray(values, dtype=float)
    if original.ndim != 1 or len(original) < 5 or not np.isfinite(original).all():
        raise ValueError("Five-point smoothing needs at least five finite scalar values.")
    smoothed = original.copy()
    smoothed[0] = (
        69.0 * original[0]
        + 4.0 * original[1]
        - 6.0 * original[2]
        + 4.0 * original[3]
        - original[4]
    ) / 70.0
    smoothed[1] = (
        2.0 * original[0]
        + 27.0 * original[1]
        + 12.0 * original[2]
        - 8.0 * original[3]
        + 2.0 * original[4]
    ) / 35.0
    smoothed[2:-2] = (
        -3.0 * original[:-4]
        + 12.0 * original[1:-3]
        + 17.0 * original[2:-2]
        + 12.0 * original[3:-1]
        - 3.0 * original[4:]
    ) / 35.0
    smoothed[-2] = (
        2.0 * original[-5]
        - 8.0 * original[-4]
        + 12.0 * original[-3]
        + 27.0 * original[-2]
        + 2.0 * original[-1]
    ) / 35.0
    smoothed[-1] = (
        -original[-5]
        + 4.0 * original[-4]
        - 6.0 * original[-3]
        + 4.0 * original[-2]
        + 69.0 * original[-1]
    ) / 70.0
    return smoothed


def _smooth_free_surface_near_contact(
    y_m: np.ndarray,
    z_up_m: np.ndarray,
    potential_m2_s: np.ndarray,
    *,
    node_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Smooth near-body nodes while preserving the intersection exactly."""

    y = np.asarray(y_m, dtype=float).copy()
    z = np.asarray(z_up_m, dtype=float).copy()
    potential = np.asarray(potential_m2_s, dtype=float).copy()
    count = min(int(node_count), len(y) - 1)
    if count < 5:
        return y, z, potential
    contact_y = float(y[0])
    contact_z = float(z[0])
    contact_potential = float(potential[0]) if potential.shape == y.shape else None
    y[:count] = _sun_five_point_third_order_smooth(y[:count])
    z[:count] = _sun_five_point_third_order_smooth(z[:count])
    y[0] = contact_y
    z[0] = contact_z
    if potential.shape == y.shape:
        potential[:count] = _sun_five_point_third_order_smooth(potential[:count])
        potential[0] = contact_potential
    return y, z, potential


def _remesh_free_surface_segment(
    y_m: np.ndarray,
    z_up_m: np.ndarray,
    potential_m2_s: np.ndarray,
    *,
    target_node_count: int | None = None,
    first_panel_length_m: float | None = None,
    uniform_panel_count: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dy = np.diff(y_m)
    dz = np.diff(z_up_m)
    panel_length = np.hypot(dy, dz)
    total = float(np.sum(panel_length))
    if total <= 1e-12:
        raise ValueError("Cannot remesh a near-zero-length free-surface segment.")
    node_s = np.concatenate(([0.0], np.cumsum(panel_length))) / total
    target_count = len(node_s) if target_node_count is None else int(target_node_count)
    if target_count < 3:
        raise ValueError("Free-surface remeshing needs at least three target nodes.")
    if first_panel_length_m is None:
        new_node_s = np.linspace(0.0, 1.0, target_count)
    else:
        new_node_s = _geometric_node_arclengths(
            total,
            target_count - 1,
            first_panel_length_m,
            uniform_panel_count=uniform_panel_count,
        ) / total
    if len(node_s) >= 4:
        new_y = CubicSpline(node_s, y_m, bc_type="natural")(new_node_s)
        new_z = CubicSpline(node_s, z_up_m, bc_type="natural")(new_node_s)
    else:
        new_y = np.interp(new_node_s, node_s, y_m)
        new_z = np.interp(new_node_s, node_s, z_up_m)
    potential = np.asarray(potential_m2_s, dtype=float)
    if len(potential) == len(node_s):
        if len(potential) >= 4:
            new_potential = CubicSpline(
                node_s,
                potential,
                bc_type="natural",
                extrapolate=True,
            )(new_node_s)
        else:
            new_potential = np.interp(new_node_s, node_s, potential)
    else:
        old_panel_s = 0.5 * (node_s[:-1] + node_s[1:])
        new_panel_s = 0.5 * (new_node_s[:-1] + new_node_s[1:])
        if len(potential) >= 4:
            new_potential = CubicSpline(
                old_panel_s,
                potential,
                bc_type="natural",
                extrapolate=True,
            )(new_panel_s)
        else:
            new_potential = np.interp(new_panel_s, old_panel_s, potential)
    new_y[0], new_y[-1] = y_m[0], y_m[-1]
    new_z[0], new_z[-1] = z_up_m[0], z_up_m[-1]
    return np.asarray(new_y), np.asarray(new_z), np.asarray(new_potential)


def _jet_cut_threshold_m(
    config: MovingWedgeConfig,
    *,
    contact_half_beam_m: float | None = None,
) -> float:
    if config.jet_cut_threshold_m is not None:
        return float(config.jet_cut_threshold_m)
    wetted_half_beam = (
        float(config.chine_half_beam_m)
        if contact_half_beam_m is None
        else min(abs(float(contact_half_beam_m)), float(config.chine_half_beam_m))
    )
    body_panel_length = wetted_half_beam / (
        max(int(config.body_panels_per_side), 1)
        * np.cos(float(config.deadrise_rad))
    )
    return float(config.jet_cut_distance_fraction) * body_panel_length


@dataclass(frozen=True)
class _AngleJetCutCandidate:
    """Geometric construction for the source-backed angle jet cut.

    The construction follows the published ``theta_0=4 deg``,
    ``lambda_0=0.1 L``, ``lambda_1=0.8 lambda_0`` and
    ``lambda_2=0.1 lambda_0`` definition.  It remains diagnostic until the
    wedge-entry pressure benchmark passes without response fitting.
    """

    margin_m: float
    lambda0_m: float
    e_arclength_m: float
    b_arclength_m: float | None
    c_arclength_m: float | None
    projection_d_m: np.ndarray
    point_c_m: np.ndarray | None
    first_retained_node_index: int | None
    potential_d_m2_s: float | None
    potential_c_m2_s: float | None

    @property
    def eligible(self) -> bool:
        return bool(
            self.margin_m <= 64.0 * np.finfo(float).eps * max(self.lambda0_m, 1.0)
            and self.point_c_m is not None
            and self.first_retained_node_index is not None
            and self.potential_d_m2_s is not None
            and self.potential_c_m2_s is not None
        )


def _right_angle_jet_cut_candidate(
    config: MovingWedgeConfig,
    *,
    apex_z_up_m: float,
    free_y_m: np.ndarray,
    free_z_up_m: np.ndarray,
    free_potential_m2_s: np.ndarray,
) -> _AngleJetCutCandidate:
    """Locate points E, B, C and D of the published angle-cut construction."""

    y = np.asarray(free_y_m, dtype=float)
    z = np.asarray(free_z_up_m, dtype=float)
    potential = np.asarray(free_potential_m2_s, dtype=float)
    if y.shape != z.shape or potential.shape != y.shape or len(y) < 4:
        raise ValueError(
            "Angle jet cutting needs at least four free-surface nodes with nodal potential."
        )
    points = np.column_stack((y, z))
    panel_vector = np.diff(points, axis=0)
    panel_length = np.linalg.norm(panel_vector, axis=1)
    if np.any(panel_length <= np.finfo(float).eps):
        raise ValueError("Angle jet cutting found a zero-length free-surface panel.")
    panel_tangent = panel_vector / panel_length[:, None]
    body_tangent = np.asarray(
        (np.cos(float(config.deadrise_rad)), np.sin(float(config.deadrise_rad))),
        dtype=float,
    )
    node_tangent = np.empty_like(points)
    # The inviscid spray root leaves the body tangentially.  Enforce that
    # contact condition exactly instead of allowing the first coarse panel to
    # define a spurious non-zero angle at A.
    node_tangent[0] = body_tangent
    node_tangent[-1] = panel_tangent[-1]
    for index in range(1, len(points) - 1):
        previous = panel_tangent[index - 1]
        following = panel_tangent[index]
        if float(np.dot(previous, following)) < 0.0:
            following = -following
        combined = previous + following
        norm = float(np.linalg.norm(combined))
        node_tangent[index] = previous if norm <= np.finfo(float).eps else combined / norm

    acute_cosine = np.clip(np.abs(node_tangent @ body_tangent), 0.0, 1.0)
    tangent_angle = np.arccos(acute_cosine)
    threshold_angle = np.radians(float(config.jet_cut_angle_threshold_deg))
    cumulative_s = np.concatenate(([0.0], np.cumsum(panel_length)))
    crossing = np.flatnonzero(tangent_angle > threshold_angle)
    if len(crossing) == 0:
        e_arclength = 0.0
    else:
        crossing_index = int(crossing[0])
        if crossing_index == 0:
            e_arclength = 0.0
        else:
            angle_before = float(tangent_angle[crossing_index - 1])
            angle_after = float(tangent_angle[crossing_index])
            denominator = angle_after - angle_before
            fraction = (
                1.0
                if denominator <= np.finfo(float).eps
                else np.clip(
                    (threshold_angle - angle_before) / denominator,
                    0.0,
                    1.0,
                )
            )
            e_arclength = float(
                cumulative_s[crossing_index - 1]
                + fraction
                * (cumulative_s[crossing_index] - cumulative_s[crossing_index - 1])
            )

    hull_arc_length = (
        float(config.jet_cut_angle_hull_arc_length_m)
        if config.jet_cut_angle_hull_arc_length_m is not None
        else float(config.chine_half_beam_m) / np.cos(float(config.deadrise_rad))
    )
    lambda0 = float(config.jet_cut_angle_length_fraction) * hull_arc_length
    margin = lambda0 - e_arclength
    contact = points[0]
    empty = _AngleJetCutCandidate(
        margin_m=float(margin),
        lambda0_m=float(lambda0),
        e_arclength_m=float(e_arclength),
        b_arclength_m=None,
        c_arclength_m=None,
        projection_d_m=np.asarray(contact, dtype=float),
        point_c_m=None,
        first_retained_node_index=None,
        potential_d_m2_s=None,
        potential_c_m2_s=None,
    )
    if margin > 64.0 * np.finfo(float).eps * max(lambda0, 1.0):
        return empty

    lambda1 = 0.8 * lambda0
    lambda2 = 0.1 * lambda0
    b_arclength = e_arclength - lambda1
    c_arclength = b_arclength + lambda2
    if b_arclength <= 0.0 or c_arclength >= cumulative_s[-1]:
        return empty
    point_b = np.asarray(
        (
            np.interp(b_arclength, cumulative_s, y),
            np.interp(b_arclength, cumulative_s, z),
        ),
        dtype=float,
    )
    point_c = np.asarray(
        (
            np.interp(c_arclength, cumulative_s, y),
            np.interp(c_arclength, cumulative_s, z),
        ),
        dtype=float,
    )
    apex = np.asarray((0.0, float(apex_z_up_m)), dtype=float)
    projection_scalar = float(np.dot(point_b - apex, body_tangent))
    projection = apex + projection_scalar * body_tangent
    if not 0.0 < float(projection[0]) < float(contact[0]) * (1.0 - 1e-10):
        return empty

    potential_b = float(np.interp(b_arclength, cumulative_s, potential))
    potential_c = float(np.interp(c_arclength, cumulative_s, potential))
    smoothing_length = max(c_arclength - b_arclength, np.finfo(float).eps)
    projection_length = float(np.linalg.norm(point_c - projection))
    potential_d = potential_c + projection_length / smoothing_length * (
        potential_b - potential_c
    )
    retained_index = int(np.searchsorted(cumulative_s, c_arclength, side="right"))
    return _AngleJetCutCandidate(
        margin_m=float(margin),
        lambda0_m=float(lambda0),
        e_arclength_m=float(e_arclength),
        b_arclength_m=float(b_arclength),
        c_arclength_m=float(c_arclength),
        projection_d_m=np.asarray(projection, dtype=float),
        point_c_m=np.asarray(point_c, dtype=float),
        first_retained_node_index=retained_index,
        potential_d_m2_s=float(potential_d),
        potential_c_m2_s=float(potential_c),
    )


def _apply_right_angle_jet_cut(
    config: MovingWedgeConfig,
    *,
    apex_z_up_m: float,
    free_y_m: np.ndarray,
    free_z_up_m: np.ndarray,
    free_potential_m2_s: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, _AngleJetCutCandidate, bool]:
    candidate = _right_angle_jet_cut_candidate(
        config,
        apex_z_up_m=apex_z_up_m,
        free_y_m=free_y_m,
        free_z_up_m=free_z_up_m,
        free_potential_m2_s=free_potential_m2_s,
    )
    if not candidate.eligible:
        return (
            np.asarray(free_y_m, dtype=float),
            np.asarray(free_z_up_m, dtype=float),
            np.asarray(free_potential_m2_s, dtype=float),
            candidate,
            False,
        )
    point_c = np.asarray(candidate.point_c_m, dtype=float)
    retained = int(candidate.first_retained_node_index)
    y = np.concatenate(
        (
            [candidate.projection_d_m[0], point_c[0]],
            np.asarray(free_y_m, dtype=float)[retained:],
        )
    )
    z = np.concatenate(
        (
            [candidate.projection_d_m[1], point_c[1]],
            np.asarray(free_z_up_m, dtype=float)[retained:],
        )
    )
    potential = np.concatenate(
        (
            [candidate.potential_d_m2_s, candidate.potential_c_m2_s],
            np.asarray(free_potential_m2_s, dtype=float)[retained:],
        )
    )
    return y, z, potential, candidate, True


def _right_jet_cut_scan(
    config: MovingWedgeConfig,
    *,
    apex_z_up_m: float,
    free_y_m: np.ndarray,
    free_z_up_m: np.ndarray,
) -> tuple[float, int, np.ndarray, float, float]:
    """Find Sun's outermost thin-jet node B, scanning back toward jet tip A."""

    y = np.asarray(free_y_m, dtype=float)
    z = np.asarray(free_z_up_m, dtype=float)
    if y.shape != z.shape or len(y) < 3:
        raise ValueError("Jet-cut scanning needs at least three free-surface nodes.")
    search_count = min(
        len(y) - 2,
        max(int(config.jet_cut_search_node_count), 1),
    )
    tangent = np.asarray(
        (np.cos(float(config.deadrise_rad)), np.sin(float(config.deadrise_rad))),
        dtype=float,
    )
    relative = np.column_stack((y[1 : search_count + 1], z[1 : search_count + 1]))
    relative -= np.asarray((0.0, float(apex_z_up_m)), dtype=float)
    signed_distance = tangent[0] * relative[:, 1] - tangent[1] * relative[:, 0]
    projection_scalar = relative @ tangent
    projection_y = projection_scalar * tangent[0]
    threshold = _jet_cut_threshold_m(
        config,
        contact_half_beam_m=float(y[0]),
    )
    margins = -signed_distance - threshold
    valid_projection = (
        (projection_y > 0.0)
        & (projection_y < float(y[0]) * (1.0 - 1e-10))
    )
    eligible = np.flatnonzero(
        valid_projection & (margins <= threshold * 1e-10)
    )
    if len(eligible):
        # Search from the outer free surface toward A: retain the outermost B
        # that bounds the contiguous low-pressure thin-jet region.
        local_index = int(eligible[-1])
    else:
        valid_indices = np.flatnonzero(valid_projection)
        local_index = (
            int(valid_indices[np.argmin(margins[valid_indices])])
            if len(valid_indices)
            else 0
        )
    node_index = local_index + 1
    projection = np.asarray((0.0, float(apex_z_up_m))) + float(
        projection_scalar[local_index]
    ) * tangent
    return (
        float(margins[local_index]),
        node_index,
        projection,
        abs(float(signed_distance[local_index])),
        float(threshold),
    )


def _free_surface_smoothing_due(
    config: MovingWedgeConfig,
    *,
    start_time_s: float,
    end_time_s: float,
) -> bool:
    """Return whether a physical-time smoothing boundary was crossed."""

    if not config.free_surface_smoothing_enabled:
        return False
    interval = config.free_surface_smoothing_interval_s
    if interval is None:
        return True
    start = float(start_time_s)
    end = float(end_time_s)
    if end <= start:
        return False
    interval = float(interval)
    scale = max(abs(start), abs(end), interval, 1.0)
    tolerance = 64.0 * np.finfo(float).eps * scale
    start_index = int(np.floor((start + tolerance) / interval))
    end_index = int(np.floor((end + tolerance) / interval))
    return end_index > start_index


def _free_surface_remesh_due(
    config: MovingWedgeConfig,
    *,
    start_time_s: float,
    end_time_s: float,
) -> bool:
    if not config.free_surface_remesh_enabled:
        return False
    interval = config.free_surface_remesh_interval_s
    if interval is None:
        return True
    start = float(start_time_s)
    end = float(end_time_s)
    if end <= start:
        return False
    interval = float(interval)
    scale = max(abs(start), abs(end), interval, 1.0)
    tolerance = 64.0 * np.finfo(float).eps * scale
    start_index = int(np.floor((start + tolerance) / interval))
    end_index = int(np.floor((end + tolerance) / interval))
    return end_index > start_index


def remesh_moving_wedge_free_surface(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
    *,
    artificial_conversion_right: tuple[float, float, float] | None = None,
    artificial_conversion_left: tuple[float, float, float] | None = None,
    apply_smoothing: bool | None = None,
    _postcheck_depth: int = 0,
) -> MovingWedgeState:
    """Cubic-spline equal-arclength remeshing with fixed wall/body contacts."""

    state = _state_with_updated_spray_diagnostics(state)
    apex_z = -float(config.mean_draft_m) + float(motion.displacement_m(state.time_s))
    tan_beta = np.tan(float(config.deadrise_rad))
    chine = float(config.chine_half_beam_m)
    right_input_y = state.right_free_y_m
    right_input_z = state.right_free_z_up_m
    right_input_phi = state.right_free_potential_m2_s
    left_input_y = state.left_free_y_m
    left_input_z = state.left_free_z_up_m
    left_input_phi = state.left_free_potential_m2_s
    target_right_count = len(right_input_y)
    target_left_count = len(left_input_y)
    jet_cut_count = int(state.jet_cut_count)
    minimum_distance_ratio = state.minimum_jet_normal_distance_ratio
    minimum_projection_ratio = state.minimum_jet_projection_ratio
    maximum_projection_ratio = state.maximum_jet_projection_ratio

    def record_jet_geometry(normal_distance: float, threshold: float, projection_ratio: float) -> None:
        nonlocal minimum_distance_ratio, minimum_projection_ratio, maximum_projection_ratio
        distance_ratio = normal_distance / threshold
        minimum_distance_ratio = (
            distance_ratio
            if minimum_distance_ratio is None
            else min(minimum_distance_ratio, distance_ratio)
        )
        minimum_projection_ratio = (
            projection_ratio
            if minimum_projection_ratio is None
            else min(minimum_projection_ratio, projection_ratio)
        )
        maximum_projection_ratio = (
            projection_ratio
            if maximum_projection_ratio is None
            else max(maximum_projection_ratio, projection_ratio)
        )

    if (
        config.jet_cut_enabled
        and config.jet_cut_method == "angle"
        and right_input_y[0] < chine * (1.0 - 1e-10)
    ):
        (
            right_input_y,
            right_input_z,
            right_input_phi,
            _,
            right_cut,
        ) = _apply_right_angle_jet_cut(
            config,
            apex_z_up_m=apex_z,
            free_y_m=right_input_y,
            free_z_up_m=right_input_z,
            free_potential_m2_s=right_input_phi,
        )
        if right_cut:
            jet_cut_count += 1
    elif config.jet_cut_enabled and right_input_y[0] < chine * (1.0 - 1e-10):
        (
            right_margin,
            right_b_index,
            projection,
            normal_distance,
            right_threshold,
        ) = _right_jet_cut_scan(
            config,
            apex_z_up_m=apex_z,
            free_y_m=right_input_y,
            free_z_up_m=right_input_z,
        )
        projection_ratio = float(projection[0] / right_input_y[0])
        record_jet_geometry(normal_distance, right_threshold, projection_ratio)
        if (
            (
                right_margin <= right_threshold * 1e-10
                or (
                    config.jet_cut_ordering_safeguard_enabled
                    and right_input_y[1] <= right_input_y[0]
                )
            )
            and 0.0 < projection[0] < config.free_surface_extent_m
        ):
            right_input_y = np.concatenate(
                ([projection[0]], right_input_y[right_b_index + 1 :])
            )
            right_input_z = np.concatenate(
                ([projection[1]], right_input_z[right_b_index + 1 :])
            )
            right_input_phi = right_input_phi[right_b_index:]
            jet_cut_count += 1
    if (
        config.jet_cut_enabled
        and config.jet_cut_method == "angle"
        and -left_input_y[-1] < chine * (1.0 - 1e-10)
    ):
        (
            mirrored_y,
            mirrored_z,
            mirrored_phi,
            _,
            left_cut,
        ) = _apply_right_angle_jet_cut(
            config,
            apex_z_up_m=apex_z,
            free_y_m=-left_input_y[::-1],
            free_z_up_m=left_input_z[::-1],
            free_potential_m2_s=left_input_phi[::-1],
        )
        if left_cut:
            left_input_y = -mirrored_y[::-1]
            left_input_z = mirrored_z[::-1]
            left_input_phi = mirrored_phi[::-1]
            jet_cut_count += 1
    elif config.jet_cut_enabled and -left_input_y[-1] < chine * (1.0 - 1e-10):
        mirrored_left_y = -left_input_y[::-1]
        mirrored_left_z = left_input_z[::-1]
        (
            left_margin,
            left_b_offset,
            mirrored_projection,
            normal_distance,
            left_threshold,
        ) = _right_jet_cut_scan(
            config,
            apex_z_up_m=apex_z,
            free_y_m=mirrored_left_y,
            free_z_up_m=mirrored_left_z,
        )
        projection = np.asarray((-mirrored_projection[0], mirrored_projection[1]))
        left_b_index = len(left_input_y) - 1 - left_b_offset
        projection_ratio = float(-projection[0] / -left_input_y[-1])
        record_jet_geometry(normal_distance, left_threshold, projection_ratio)
        if (
            (
                left_margin <= left_threshold * 1e-10
                or (
                    config.jet_cut_ordering_safeguard_enabled
                    and left_input_y[-2] >= left_input_y[-1]
                )
            )
            and -config.free_surface_extent_m < projection[0] < 0.0
        ):
            left_input_y = np.concatenate(
                (left_input_y[:left_b_index], [projection[0]])
            )
            left_input_z = np.concatenate(
                (left_input_z[:left_b_index], [projection[1]])
            )
            if left_input_phi.shape == state.left_free_y_m.shape:
                left_input_phi = left_input_phi[: left_b_index + 1]
            else:
                left_input_phi = left_input_phi[:left_b_index]
            jet_cut_count += 1
    if (
        config.knuckle_separation_model == "artificial_surface"
        and right_input_y[0] > chine * (1.0 + 1e-10)
    ):
        conversion = artificial_conversion_right
        if (
            conversion is not None
            and chine < float(conversion[0]) < float(right_input_y[0])
        ):
            new_y, new_z, new_phi = (float(value) for value in conversion)
        else:
            old_extension = float(right_input_y[0] - chine)
            nominal_extension = chine / max(int(config.body_panels_per_side), 1)
            new_extension = min(nominal_extension, 0.5 * old_extension)
            new_y = chine + new_extension
            new_z = apex_z + new_y * tan_beta
            new_phi = float(right_input_phi[0])
        right_input_y = np.concatenate(([new_y], right_input_y))
        right_input_z = np.concatenate(([new_z], right_input_z))
        right_input_phi = np.concatenate(([new_phi], right_input_phi))
    if (
        config.knuckle_separation_model == "artificial_surface"
        and -left_input_y[-1] > chine * (1.0 + 1e-10)
    ):
        conversion = artificial_conversion_left
        if (
            conversion is not None
            and float(left_input_y[-1]) < float(conversion[0]) < -chine
        ):
            new_y, new_z, new_phi = (float(value) for value in conversion)
        else:
            old_extension = float(-left_input_y[-1] - chine)
            nominal_extension = chine / max(int(config.body_panels_per_side), 1)
            new_extension = min(nominal_extension, 0.5 * old_extension)
            new_y = -(chine + new_extension)
            new_z = apex_z - new_y * tan_beta
            new_phi = float(left_input_phi[-1])
        left_input_y = np.concatenate((left_input_y, [new_y]))
        left_input_z = np.concatenate((left_input_z, [new_z]))
        left_input_phi = np.concatenate((left_input_phi, [new_phi]))
    smoothing_enabled = (
        config.free_surface_smoothing_enabled
        if apply_smoothing is None
        else bool(apply_smoothing) and config.free_surface_smoothing_enabled
    )
    if smoothing_enabled:
        smoothing_count = int(config.free_surface_smoothing_node_count)
        right_input_y, right_input_z, right_input_phi = _smooth_free_surface_near_contact(
            right_input_y,
            right_input_z,
            right_input_phi,
            node_count=smoothing_count,
        )
        left_y_reversed, left_z_reversed, left_phi_reversed = (
            _smooth_free_surface_near_contact(
                left_input_y[::-1],
                left_input_z[::-1],
                left_input_phi[::-1],
                node_count=smoothing_count,
            )
        )
        left_input_y = left_y_reversed[::-1]
        left_input_z = left_z_reversed[::-1]
        left_input_phi = left_phi_reversed[::-1]
    right_first_panel_length = None
    left_first_panel_length = None
    if config.free_surface_spacing_mode == "body_matched_geometric":
        cosine = np.cos(float(config.deadrise_rad))
        panel_count = max(int(config.body_panels_per_side), 1)
        right_first_panel_length = min(abs(float(right_input_y[0])), chine) / (
            panel_count * cosine
        )
        left_first_panel_length = min(abs(float(left_input_y[-1])), chine) / (
            panel_count * cosine
        )
    right_y, right_z, right_phi = _remesh_free_surface_segment(
        right_input_y,
        right_input_z,
        right_input_phi,
        target_node_count=target_right_count,
        first_panel_length_m=right_first_panel_length,
        uniform_panel_count=int(config.free_surface_uniform_near_body_panel_count),
    )
    left_y_reversed, left_z_reversed, left_phi_reversed = _remesh_free_surface_segment(
        left_input_y[::-1],
        left_input_z[::-1],
        left_input_phi[::-1],
        target_node_count=target_left_count,
        first_panel_length_m=left_first_panel_length,
        uniform_panel_count=int(config.free_surface_uniform_near_body_panel_count),
    )
    left_y = left_y_reversed[::-1]
    left_z = left_z_reversed[::-1]
    left_phi = left_phi_reversed[::-1]
    right_y[-1] = float(config.free_surface_extent_m)
    left_y[0] = -float(config.free_surface_extent_m)
    if (
        config.chine_separation_enabled
        and config.knuckle_separation_model == "clamped"
        and right_y[0] >= chine
    ):
        right_y[0] = float(config.chine_half_beam_m)
    if (
        config.chine_separation_enabled
        and config.knuckle_separation_model == "clamped"
        and -left_y[-1] >= chine
    ):
        left_y[-1] = -float(config.chine_half_beam_m)
    if config.enforce_lateral_symmetry:
        symmetric_y = 0.5 * (right_y - left_y[::-1])
        symmetric_z = 0.5 * (right_z + left_z[::-1])
        symmetric_potential = 0.5 * (right_phi + left_phi[::-1])
        right_y = symmetric_y
        left_y = -symmetric_y[::-1]
        right_z = symmetric_z
        left_z = symmetric_z[::-1]
        right_phi = symmetric_potential
        left_phi = symmetric_potential[::-1]
    if (
        config.chine_separation_enabled
        and config.knuckle_separation_model == "clamped"
        and right_y[0] >= chine * (1.0 - 1e-10)
        and len(right_y) >= 3
    ):
        chine_z = apex_z + chine * tan_beta
        right_y[0] = chine
        right_z[0] = chine_z
        nominal_length = chine / (
            max(int(config.body_panels_per_side), 1) * np.cos(float(config.deadrise_rad))
        )
        distance_to_second = float(
            np.hypot(right_y[2] - chine, right_z[2] - chine_z)
        )
        local_length = min(nominal_length, 0.45 * distance_to_second)
        right_y[1] = chine + local_length * np.cos(float(config.deadrise_rad))
        right_z[1] = chine_z + local_length * np.sin(float(config.deadrise_rad))
        if right_phi.shape == right_y.shape:
            interpolation_fraction = min(
                local_length / max(distance_to_second, np.finfo(float).eps),
                1.0,
            )
            right_phi[1] = right_phi[0] + interpolation_fraction * (
                right_phi[2] - right_phi[0]
            )
        if config.enforce_lateral_symmetry:
            left_y = -right_y[::-1]
            left_z = right_z[::-1]
            left_phi = right_phi[::-1]
    right_z[0] = apex_z + right_y[0] * tan_beta
    left_z[-1] = apex_z - left_y[-1] * tan_beta
    result = MovingWedgeState(
        right_free_y_m=right_y,
        right_free_z_up_m=right_z,
        left_free_y_m=left_y,
        left_free_z_up_m=left_z,
        right_free_potential_m2_s=right_phi,
        left_free_potential_m2_s=left_phi,
        time_s=state.time_s,
        jet_cut_count=jet_cut_count,
        minimum_jet_normal_distance_ratio=minimum_distance_ratio,
        minimum_jet_projection_ratio=minimum_projection_ratio,
        maximum_jet_projection_ratio=maximum_projection_ratio,
        maximum_spray_overturning_panel_count=(
            state.maximum_spray_overturning_panel_count
        ),
        minimum_spray_outward_tangent_cosine=(
            state.minimum_spray_outward_tangent_cosine
        ),
        minimum_spray_nonadjacent_distance_ratio=(
            state.minimum_spray_nonadjacent_distance_ratio
        ),
    )
    if (
        config.jet_cut_enabled
        and config.jet_cut_method == "distance"
        and result.right_free_y_m[0] < chine * (1.0 - 1e-10)
    ):
        right_tangent = np.asarray(
            (np.cos(config.deadrise_rad), np.sin(config.deadrise_rad)),
            dtype=float,
        )
        right_relative = np.asarray(
            (result.right_free_y_m[1], result.right_free_z_up_m[1]),
            dtype=float,
        ) - np.asarray((0.0, apex_z), dtype=float)
        right_signed_distance = float(
            right_tangent[0] * right_relative[1]
            - right_tangent[1] * right_relative[0]
        )
        if right_signed_distance > 0.0 or (
            config.jet_cut_ordering_safeguard_enabled
            and result.right_free_y_m[1] <= result.right_free_y_m[0]
        ):
            if int(_postcheck_depth) >= int(config.jet_cut_max_corrective_passes):
                raise ValueError(
                    "Thin-jet remeshing left a free-surface node inside the body after "
                    f"{int(config.jet_cut_max_corrective_passes)} corrective cuts."
                )
            return remesh_moving_wedge_free_surface(
                config,
                motion,
                result,
                # Smoothing belongs to the physical time step and must not be
                # repeated by topology-only corrective cuts.
                apply_smoothing=False,
                _postcheck_depth=int(_postcheck_depth) + 1,
            )
    return result


def _advance_moving_wedge_rk4_single_step(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
    *,
    time_step_s: float,
    gravity_m_s2: float = 9.80665,
    remesh_enabled: bool = True,
    incident_wave: RegularIncidentWave2D | None = None,
) -> MovingWedgeStepResult:
    dt = float(time_step_s)
    if dt <= 0.0:
        raise ValueError("time_step_s must be positive.")
    if config.element_interpolation == "linear_node":
        linear_boundary, free_panel_count, potential = _solve_linear_free_surface_normal_derivative(
            config,
            motion,
            state,
            incident_wave,
        )
        frozen_normal = potential.normal_derivative_m_s[: free_panel_count + 1]
        separation_velocity = None
        if (
            config.knuckle_separation_model == "artificial_surface"
            and state.right_free_y_m[0]
            >= float(config.chine_half_beam_m) * (1.0 - 1e-10)
        ):
            incident_knuckle_velocity = (
                0.0
                if incident_wave is None
                else float(
                    incident_wave.vertical_velocity_mps(
                        state.time_s,
                        linear_boundary.node_z_up_m[free_panel_count],
                    )
                )
            )
            separation_disturbance_velocity = _linear_physical_knuckle_velocity(
                linear_boundary,
                potential,
                body_velocity_z=float(motion.velocity_mps(state.time_s)),
                incident_vertical_velocity_mps=incident_knuckle_velocity,
            )
            separation_velocity = separation_disturbance_velocity.copy()
            if incident_wave is not None:
                separation_velocity[1] += incident_knuckle_velocity

        def evaluate_stage(stage_state: MovingWedgeState) -> MovingWedgeRhs:
            return _evaluate_linear_moving_wedge_rhs_with_frozen_normal(
                config,
                motion,
                stage_state,
                frozen_normal,
                potential_relative_residual=potential.relative_residual,
                potential_condition_number=potential.condition_number,
                gravity_m_s2=float(gravity_m_s2),
                separation_velocity_mps=separation_velocity,
                incident_wave=incident_wave,
            )

        # Sun (2007), Eq. 2.29: phi_n is frozen during one RK4 interval.
        k1 = evaluate_stage(state)
        k2 = evaluate_stage(
            _increment_moving_wedge_state(config, motion, state, k1, 0.5 * dt)
        )
        k3 = evaluate_stage(
            _increment_moving_wedge_state(config, motion, state, k2, 0.5 * dt)
        )
        k4 = evaluate_stage(
            _increment_moving_wedge_state(config, motion, state, k3, dt)
        )
    else:
        k1 = evaluate_moving_wedge_rhs(
            config,
            motion,
            state,
            gravity_m_s2=gravity_m_s2,
            incident_wave=incident_wave,
        )
        k2 = evaluate_moving_wedge_rhs(
            config,
            motion,
            _increment_moving_wedge_state(config, motion, state, k1, 0.5 * dt),
            gravity_m_s2=gravity_m_s2,
            incident_wave=incident_wave,
        )
        k3 = evaluate_moving_wedge_rhs(
            config,
            motion,
            _increment_moving_wedge_state(config, motion, state, k2, 0.5 * dt),
            gravity_m_s2=gravity_m_s2,
            incident_wave=incident_wave,
        )
        k4 = evaluate_moving_wedge_rhs(
            config,
            motion,
            _increment_moving_wedge_state(config, motion, state, k3, dt),
            gravity_m_s2=gravity_m_s2,
            incident_wave=incident_wave,
        )
    combined = MovingWedgeRhs(
        right_node_velocity_mps=(k1.right_node_velocity_mps + 2 * k2.right_node_velocity_mps + 2 * k3.right_node_velocity_mps + k4.right_node_velocity_mps) / 6.0,
        left_node_velocity_mps=(k1.left_node_velocity_mps + 2 * k2.left_node_velocity_mps + 2 * k3.left_node_velocity_mps + k4.left_node_velocity_mps) / 6.0,
        right_potential_rate_m2_s2=(k1.right_potential_rate_m2_s2 + 2 * k2.right_potential_rate_m2_s2 + 2 * k3.right_potential_rate_m2_s2 + k4.right_potential_rate_m2_s2) / 6.0,
        left_potential_rate_m2_s2=(k1.left_potential_rate_m2_s2 + 2 * k2.left_potential_rate_m2_s2 + 2 * k3.left_potential_rate_m2_s2 + k4.left_potential_rate_m2_s2) / 6.0,
        potential_relative_residual=max(k1.potential_relative_residual, k2.potential_relative_residual, k3.potential_relative_residual, k4.potential_relative_residual),
        potential_condition_number=max(k1.potential_condition_number, k2.potential_condition_number, k3.potential_condition_number, k4.potential_condition_number),
    )
    advanced_state = _state_with_updated_spray_diagnostics(
        _increment_moving_wedge_state(config, motion, state, combined, dt)
    )
    artificial_conversion_right = None
    artificial_conversion_left = None
    if (
        config.element_interpolation == "linear_node"
        and config.knuckle_separation_model == "artificial_surface"
        and separation_velocity is not None
        and state.right_free_y_m[0]
        >= float(config.chine_half_beam_m) * (1.0 - 1e-10)
    ):
        knuckle_potential = _linear_physical_knuckle_potential(
            linear_boundary,
            potential,
        )
        apex_z = -float(config.mean_draft_m) + float(
            motion.displacement_m(state.time_s)
        )
        chine_point = np.asarray(
            (
                float(config.chine_half_beam_m),
                apex_z
                + float(config.chine_half_beam_m)
                * np.tan(float(config.deadrise_rad)),
            ),
            dtype=float,
        )
        converted_point = chine_point + np.asarray(separation_velocity) * dt
        if incident_wave is None:
            converted_potential = knuckle_potential + dt * (
                0.5 * float(np.dot(separation_velocity, separation_velocity))
                - float(gravity_m_s2) * float(chine_point[1])
            )
        else:
            incident_potential_time_derivative = float(
                incident_wave.potential_time_derivative_m2_s2(
                    state.time_s,
                    chine_point[1],
                )
            )
            converted_potential = knuckle_potential + dt * (
                0.5
                * float(
                    np.dot(
                        separation_disturbance_velocity,
                        separation_disturbance_velocity,
                    )
                )
                - incident_potential_time_derivative
                - float(gravity_m_s2) * float(chine_point[1])
            )
        artificial_conversion_right = (
            float(converted_point[0]),
            float(converted_point[1]),
            float(converted_potential),
        )
        artificial_conversion_left = (
            -float(converted_point[0]),
            float(converted_point[1]),
            float(converted_potential),
        )
    remesh_due = bool(
        remesh_enabled
        and _free_surface_remesh_due(
            config,
            start_time_s=state.time_s,
            end_time_s=advanced_state.time_s,
        )
    )
    if remesh_due:
        smoothing_due = _free_surface_smoothing_due(
            config,
            start_time_s=state.time_s,
            end_time_s=advanced_state.time_s,
        )
        advanced_state = remesh_moving_wedge_free_surface(
            config,
            motion,
            advanced_state,
            artificial_conversion_right=artificial_conversion_right,
            artificial_conversion_left=artificial_conversion_left,
            apply_smoothing=smoothing_due,
        )
    return MovingWedgeStepResult(
        state=advanced_state,
        max_potential_relative_residual=combined.potential_relative_residual,
        max_potential_condition_number=combined.potential_condition_number,
    )


def _snap_moving_wedge_contact_to_chine(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
) -> MovingWedgeState:
    """Place the first separated state exactly at the physical knuckle."""

    chine = float(config.chine_half_beam_m)
    apex_z = -float(config.mean_draft_m) + float(motion.displacement_m(state.time_s))
    chine_z = apex_z + chine * np.tan(float(config.deadrise_rad))
    right_y = np.asarray(state.right_free_y_m, dtype=float).copy()
    right_z = np.asarray(state.right_free_z_up_m, dtype=float).copy()
    left_y = np.asarray(state.left_free_y_m, dtype=float).copy()
    left_z = np.asarray(state.left_free_z_up_m, dtype=float).copy()
    right_y[0] = chine
    right_z[0] = chine_z
    left_y[-1] = -chine
    left_z[-1] = chine_z
    return replace(
        state,
        right_free_y_m=right_y,
        right_free_z_up_m=right_z,
        left_free_y_m=left_y,
        left_free_z_up_m=left_z,
    )


def _right_jet_cut_event_geometry(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
) -> tuple[float, float]:
    """Return jet-cut margin and the body projection of the next free node."""

    apex_z = -float(config.mean_draft_m) + float(motion.displacement_m(state.time_s))
    chine = float(config.chine_half_beam_m)
    if config.jet_cut_method == "angle":
        candidate = _right_angle_jet_cut_candidate(
            config,
            apex_z_up_m=apex_z,
            free_y_m=state.right_free_y_m,
            free_z_up_m=state.right_free_z_up_m,
            free_potential_m2_s=state.right_free_potential_m2_s,
        )
        margin = float(candidate.margin_m)
        projection = np.asarray(candidate.projection_d_m, dtype=float)
    else:
        margin, _, projection, _, _ = _right_jet_cut_scan(
            config,
            apex_z_up_m=apex_z,
            free_y_m=state.right_free_y_m,
            free_z_up_m=state.right_free_z_up_m,
        )
    if config.jet_cut_ordering_safeguard_enabled:
        # Negative first-edge dy is physically possible when the boundary
        # starts at the spray tip and follows the upper jet toward its root.
        # The legacy production route treats that topology as an immediate
        # request to replace the unresolved jet by a truncated control panel.
        margin = min(
            margin,
            float(state.right_free_y_m[1] - state.right_free_y_m[0]),
        )
    return float(margin), float(projection[0])


def advance_moving_wedge_rk4(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
    *,
    time_step_s: float,
    gravity_m_s2: float = 9.80665,
    incident_wave: RegularIncidentWave2D | None = None,
) -> MovingWedgeStepResult:
    """Advance one step and localize topology changes inside the RK4 interval."""

    dt = float(time_step_s)
    if dt <= 0.0:
        raise ValueError("time_step_s must be positive.")
    chine = float(config.chine_half_beam_m)
    separation_event_eligible = bool(
        config.element_interpolation == "linear_node"
        and config.knuckle_separation_model == "artificial_surface"
        and state.right_free_y_m[0] < chine * (1.0 - 1e-10)
    )
    jet_cut_event_eligible = bool(
        config.element_interpolation == "linear_node"
        and config.jet_cut_enabled
        and config.free_surface_remesh_enabled
        and state.right_free_y_m[0] < chine * (1.0 - 1e-10)
        and len(state.right_free_y_m) >= 2
    )
    if separation_event_eligible or jet_cut_event_eligible:
        trial = _advance_moving_wedge_rk4_single_step(
            config,
            motion,
            state,
            time_step_s=dt,
            gravity_m_s2=gravity_m_s2,
            remesh_enabled=False,
            incident_wave=incident_wave,
        )
        start_contact = float(state.right_free_y_m[0])
        end_contact = float(trial.state.right_free_y_m[0])
        event_fraction: float | None = None
        event_kind: Literal["separation", "jet_cut"] | None = None
        if separation_event_eligible and end_contact > chine:
            fraction = (chine - start_contact) / (end_contact - start_contact)
            event_fraction = float(np.clip(fraction, 1e-8, 1.0 - 1e-8))
            event_kind = "separation"
        elif separation_event_eligible and config.jet_cut_enabled:
            start_margin, start_projection = _right_jet_cut_event_geometry(
                config,
                motion,
                state,
            )
            end_margin, end_projection = _right_jet_cut_event_geometry(
                config,
                motion,
                trial.state,
            )
            if end_margin <= 0.0 and end_projection > chine:
                if start_margin > 0.0 and end_margin < start_margin:
                    fraction = start_margin / (start_margin - end_margin)
                elif start_projection < chine and end_projection > start_projection:
                    fraction = (chine - start_projection) / (
                        end_projection - start_projection
                    )
                else:
                    fraction = 0.5
                event_fraction = float(np.clip(fraction, 1e-8, 1.0 - 1e-8))
                event_kind = "separation"
        if event_kind is None and jet_cut_event_eligible:
            start_margin, _ = _right_jet_cut_event_geometry(config, motion, state)
            end_margin, end_projection = _right_jet_cut_event_geometry(
                config,
                motion,
                trial.state,
            )
            if (
                start_margin > 0.0
                and end_margin <= 0.0
                and 0.0 < end_projection < float(config.free_surface_extent_m)
            ):
                low_fraction = 0.0
                high_fraction = 1.0
                event_step = trial
                # The jet node can cross the body between two saved states.  Use
                # the first non-positive bracket so remeshing occurs at the
                # prescribed thin-jet distance, rather than one full step late.
                for _ in range(12):
                    mid_fraction = 0.5 * (low_fraction + high_fraction)
                    mid_step = _advance_moving_wedge_rk4_single_step(
                        config,
                        motion,
                        state,
                        time_step_s=mid_fraction * dt,
                        gravity_m_s2=gravity_m_s2,
                        remesh_enabled=False,
                        incident_wave=incident_wave,
                    )
                    mid_margin, _ = _right_jet_cut_event_geometry(
                        config,
                        motion,
                        mid_step.state,
                    )
                    if mid_margin <= 0.0:
                        high_fraction = mid_fraction
                        event_step = mid_step
                    else:
                        low_fraction = mid_fraction
                event_fraction = float(high_fraction)
                event_kind = "jet_cut"
        if event_fraction is not None:
            event_dt = event_fraction * dt
            if event_kind != "jet_cut":
                event_step = _advance_moving_wedge_rk4_single_step(
                    config,
                    motion,
                    state,
                    time_step_s=event_dt,
                    gravity_m_s2=gravity_m_s2,
                    remesh_enabled=False,
                    incident_wave=incident_wave,
                )
            event_state = event_step.state
            if event_kind == "separation":
                event_state = _snap_moving_wedge_contact_to_chine(
                    config,
                    motion,
                    event_state,
                )
            if config.free_surface_remesh_enabled:
                smoothing_due = _free_surface_smoothing_due(
                    config,
                    start_time_s=state.time_s,
                    end_time_s=event_state.time_s,
                )
                event_state = remesh_moving_wedge_free_surface(
                    config,
                    motion,
                    event_state,
                    apply_smoothing=smoothing_due,
                )
            remaining_dt = dt - event_dt
            if remaining_dt > 64.0 * np.finfo(float).eps * max(dt, 1.0):
                remainder = _advance_moving_wedge_rk4_single_step(
                    config,
                    motion,
                    event_state,
                    time_step_s=remaining_dt,
                    gravity_m_s2=gravity_m_s2,
                    incident_wave=incident_wave,
                )
            else:
                remainder = MovingWedgeStepResult(
                    state=event_state,
                    max_potential_relative_residual=(
                        event_step.max_potential_relative_residual
                    ),
                    max_potential_condition_number=(
                        event_step.max_potential_condition_number
                    ),
                )
            return MovingWedgeStepResult(
                state=remainder.state,
                max_potential_relative_residual=max(
                    event_step.max_potential_relative_residual,
                    remainder.max_potential_relative_residual,
                ),
                max_potential_condition_number=max(
                    event_step.max_potential_condition_number,
                    remainder.max_potential_condition_number,
                ),
                separation_event_time_s=(
                    float(event_state.time_s)
                    if event_kind == "separation"
                    else None
                ),
                jet_cut_event_time_s=(
                    float(event_state.time_s) if event_kind == "jet_cut" else None
                ),
            )
    return _advance_moving_wedge_rk4_single_step(
        config,
        motion,
        state,
        time_step_s=dt,
        gravity_m_s2=gravity_m_s2,
        incident_wave=incident_wave,
    )


def _linear_body_node_velocity(
    boundary: ClosedBoundary2D,
    potential_solution,
    *,
    body_velocity_z: float,
    free_panel_count: int,
    incident_wave: RegularIncidentWave2D | None = None,
    time_s: float = 0.0,
) -> np.ndarray:
    velocity = boundary_node_velocity(boundary, potential_solution)
    labels = np.asarray(boundary.panel_labels, dtype=object)
    body_panels = np.flatnonzero((labels == "body") | (labels == "artificial_body"))
    accumulated = np.zeros_like(velocity)
    weight = np.zeros(boundary.panel_count, dtype=float)
    phi = np.asarray(potential_solution.potential_m2_s, dtype=float)
    for panel in body_panels:
        right = (panel + 1) % boundary.panel_count
        tangent = boundary.panel_tangent[panel]
        normal = boundary.panel_normal[panel]
        derivative = (phi[right] - phi[panel]) / boundary.panel_length_m[panel]
        incident_vertical = (
            0.0
            if incident_wave is None
            else float(
                incident_wave.vertical_velocity_mps(
                    time_s,
                    boundary.panel_mid_z_up_m[panel],
                )
            )
        )
        panel_velocity = (
            derivative * tangent
            + normal * normal[1] * (float(body_velocity_z) - incident_vertical)
        )
        for node in (panel, right):
            accumulated[node] += boundary.panel_length_m[panel] * panel_velocity
            weight[node] += boundary.panel_length_m[panel]
    body_nodes = weight > 0.0
    velocity[body_nodes] = accumulated[body_nodes] / weight[body_nodes, None]
    free_velocity = _linear_free_surface_node_velocity(
        boundary,
        potential_solution,
        free_panel_count,
    )
    velocity[: free_panel_count + 1] = free_velocity
    return velocity


def moving_wedge_load(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    state: MovingWedgeState,
    *,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    incident_wave: RegularIncidentWave2D | None = None,
) -> MovingWedgeLoadResult:
    if (
        config.element_interpolation == "linear_node"
        and config.pressure_interpolation == "constant_panel"
    ):
        panel_state = replace(
            state,
            right_free_potential_m2_s=0.5
            * (
                state.right_free_potential_m2_s[:-1]
                + state.right_free_potential_m2_s[1:]
            ),
            left_free_potential_m2_s=0.5
            * (
                state.left_free_potential_m2_s[:-1]
                + state.left_free_potential_m2_s[1:]
            ),
        )
        panel_result = moving_wedge_load(
            replace(
                config,
                element_interpolation="constant_panel",
                pressure_interpolation="match_potential",
            ),
            motion,
            panel_state,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            incident_wave=incident_wave,
        )
        return replace(
            panel_result,
            pressure=replace(
                panel_result.pressure,
                status="sun_ch2_linear_free_surface_constant_panel_pressure_bvp",
            ),
        )
    boundary = moving_wedge_boundary(config, motion, state)
    labels = np.asarray(boundary.panel_labels, dtype=object)
    body_mask = (labels == "body") | (labels == "artificial_body")
    free_mask = labels == "free_surface"
    velocity_z = float(motion.velocity_mps(state.time_s))
    acceleration_z = float(motion.acceleration_mps2(state.time_s))
    if config.element_interpolation == "linear_node":
        free_panel_count = int(np.count_nonzero(free_mask))
        dirichlet_panels, q_endpoints = _linear_neumann_endpoint_values(
            boundary,
            body_vertical_value=velocity_z,
            incident_endpoint_values=(
                None
                if incident_wave is None
                else _incident_endpoint_values(
                    boundary,
                    incident_wave,
                    time_s=state.time_s,
                    derivative="velocity",
                )
            ),
        )
        phi_known = np.zeros(boundary.panel_count, dtype=float)
        phi_known[: free_panel_count + 1] = state.right_free_potential_m2_s
        potential = solve_linear_element_mixed_boundary_laplace(
            boundary,
            dirichlet_panel_mask=dirichlet_panels,
            dirichlet_node_values=phi_known,
            neumann_endpoint_values=q_endpoints,
            gauss_order=int(config.gauss_order),
        )
        velocity = _linear_body_node_velocity(
            boundary,
            potential,
            body_velocity_z=velocity_z,
            free_panel_count=free_panel_count,
            incident_wave=incident_wave,
            time_s=state.time_s,
        )
        right_separated = bool(
            config.chine_separation_enabled
            and state.right_free_y_m[0]
            >= float(config.chine_half_beam_m) * (1.0 - 1e-10)
        )
        if right_separated and config.knuckle_separation_model == "clamped":
            velocity[0] = np.asarray((0.0, velocity_z))
        elif right_separated and config.knuckle_separation_model == "artificial_surface":
            incident_knuckle_velocity = (
                0.0
                if incident_wave is None
                else float(
                    incident_wave.vertical_velocity_mps(
                        state.time_s,
                        boundary.node_z_up_m[free_panel_count],
                    )
                )
            )
            velocity[0] = _linear_physical_knuckle_velocity(
                boundary,
                potential,
                body_velocity_z=velocity_z,
                incident_vertical_velocity_mps=incident_knuckle_velocity,
            )
        speed_squared = np.sum(velocity**2, axis=1)
        body_advection = velocity[:, 1] * velocity_z
        psi_known = np.zeros(boundary.panel_count, dtype=float)
        incident_vertical_nodes = (
            np.zeros(boundary.panel_count, dtype=float)
            if incident_wave is None
            else incident_wave.vertical_velocity_mps(
                state.time_s,
                boundary.node_z_up_m[:-1],
            )
        )
        incident_potential_time_nodes = (
            np.zeros(boundary.panel_count, dtype=float)
            if incident_wave is None
            else incident_wave.potential_time_derivative_m2_s2(
                state.time_s,
                boundary.node_z_up_m[:-1],
            )
        )
        psi_known[: free_panel_count + 1] = (
            body_advection[: free_panel_count + 1]
            - incident_vertical_nodes[: free_panel_count + 1]
            * velocity[: free_panel_count + 1, 1]
            - 0.5 * speed_squared[: free_panel_count + 1]
            - incident_potential_time_nodes[: free_panel_count + 1]
            - float(gravity_m_s2) * boundary.node_z_up_m[: free_panel_count + 1]
        )
        _, acceleration_endpoints = _linear_neumann_endpoint_values(
            boundary,
            body_vertical_value=acceleration_z,
            incident_endpoint_values=(
                None
                if incident_wave is None
                else _incident_endpoint_values(
                    boundary,
                    incident_wave,
                    time_s=state.time_s,
                    derivative="acceleration",
                )
            ),
        )
        auxiliary = solve_linear_element_mixed_boundary_laplace(
            boundary,
            dirichlet_panel_mask=dirichlet_panels,
            dirichlet_node_values=psi_known,
            neumann_endpoint_values=acceleration_endpoints,
            gauss_order=int(config.gauss_order),
        )
        phi_t = auxiliary.potential_m2_s - body_advection
        pressure_nodes = -float(rho_water_kg_m3) * (
            float(gravity_m_s2) * boundary.node_z_up_m[:-1]
            + phi_t
            + 0.5 * speed_squared
            + incident_vertical_nodes * velocity[:, 1]
            + incident_potential_time_nodes
        )
        physical_body = np.flatnonzero(labels == "body")
        vertical_force_half = 0.0
        for panel in physical_body:
            right = (panel + 1) % boundary.panel_count
            vertical_force_half += (
                0.5
                * (pressure_nodes[panel] + pressure_nodes[right])
                * boundary.panel_normal[panel, 1]
                * boundary.panel_length_m[panel]
            )
        free_pressure = pressure_nodes[: free_panel_count + 1]
        pressure = PressureAuxiliaryResult(
            auxiliary_solution=auxiliary,
            velocity_mps=velocity,
            potential_time_derivative_m2_s2=phi_t,
            gauge_pressure_pa=pressure_nodes,
            free_surface_pressure_max_abs_pa=float(np.max(np.abs(free_pressure))),
            body_vertical_force_per_length_n_m=2.0 * float(vertical_force_half),
            body_panel_count=2 * int(len(physical_body)),
            status="sun_ch2_linear_node_auxiliary_pressure_bvp",
        )
        apex_z = -float(config.mean_draft_m) + float(
            motion.displacement_m(state.time_s)
        )
        tan_beta = np.tan(float(config.deadrise_rad))
        right_constraint = (
            state.right_free_z_up_m[0]
            - apex_z
            - state.right_free_y_m[0] * tan_beta
        )
        left_constraint = (
            state.left_free_z_up_m[-1]
            - apex_z
            + state.left_free_y_m[-1] * tan_beta
        )
        return MovingWedgeLoadResult(
            pressure=pressure,
            boundary=boundary,
            contact_constraint_max_abs_m=float(
                max(abs(right_constraint), abs(left_constraint))
            ),
            potential_bvp_relative_residual=potential.relative_residual,
            potential_bvp_condition_number=potential.condition_number,
        )

    free_potential = (
        state.right_free_potential_m2_s
        if config.use_symmetry_half_domain
        else np.concatenate(
            (state.right_free_potential_m2_s, state.left_free_potential_m2_s)
        )
    )
    operator = build_mixed_boundary_operator(
        boundary,
        dirichlet_mask=free_mask,
        gauss_order=int(config.gauss_order),
    )
    incident_vertical_panels = (
        np.zeros(boundary.panel_count, dtype=float)
        if incident_wave is None
        else incident_wave.vertical_velocity_mps(
            state.time_s,
            boundary.panel_mid_z_up_m,
        )
    )
    incident_vertical_acceleration_panels = (
        np.zeros(boundary.panel_count, dtype=float)
        if incident_wave is None
        else incident_wave.vertical_acceleration_mps2(
            state.time_s,
            boundary.panel_mid_z_up_m,
        )
    )
    incident_potential_time_panels = (
        np.zeros(boundary.panel_count, dtype=float)
        if incident_wave is None
        else incident_wave.potential_time_derivative_m2_s2(
            state.time_s,
            boundary.panel_mid_z_up_m,
        )
    )
    potential = solve_section_potential_bvp(
        boundary,
        free_surface_potential_m2_s=free_potential,
        body_normal_velocity_mps=boundary.panel_normal[body_mask, 1]
        * (velocity_z - incident_vertical_panels[body_mask]),
        gauss_order=int(config.gauss_order),
        operator=operator,
    )
    pressure = solve_pressure_auxiliary_bvp(
        boundary,
        potential,
        body_velocity_yz_mps=(0.0, velocity_z),
        body_acceleration_normal_mps2=boundary.panel_normal[body_mask, 1]
        * (acceleration_z - incident_vertical_acceleration_panels[body_mask]),
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        gauss_order=int(config.gauss_order),
        operator=operator,
        incident_vertical_velocity_mps=incident_vertical_panels,
        incident_potential_time_derivative_m2_s2=(
            incident_potential_time_panels
        ),
    )
    if config.use_symmetry_half_domain:
        pressure = replace(
            pressure,
            body_vertical_force_per_length_n_m=(
                2.0 * pressure.body_vertical_force_per_length_n_m
            ),
            body_panel_count=2 * pressure.body_panel_count,
        )
    apex_z = -float(config.mean_draft_m) + float(motion.displacement_m(state.time_s))
    tan_beta = np.tan(float(config.deadrise_rad))
    right_constraint = state.right_free_z_up_m[0] - apex_z - state.right_free_y_m[0] * tan_beta
    left_constraint = state.left_free_z_up_m[-1] - apex_z + state.left_free_y_m[-1] * tan_beta
    return MovingWedgeLoadResult(
        pressure=pressure,
        boundary=boundary,
        contact_constraint_max_abs_m=float(max(abs(right_constraint), abs(left_constraint))),
        potential_bvp_relative_residual=potential.relative_residual,
        potential_bvp_condition_number=potential.condition_number,
    )


def run_moving_wedge_time_history(
    config: MovingWedgeConfig,
    motion: VerticalMotionLaw,
    time_s: np.ndarray,
    *,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> MovingWedgeTimeHistory:
    """Run a prescribed moving-wedge history and retain BVP diagnostics."""

    time = np.asarray(time_s, dtype=float)
    if time.ndim != 1 or len(time) < 2 or np.any(np.diff(time) <= 0.0):
        raise ValueError("time_s must be a strictly increasing one-dimensional array.")
    steps = np.diff(time)
    if not np.allclose(steps, steps[0], rtol=1e-10, atol=1e-12):
        raise ValueError("Moving-wedge RK4 history currently requires a uniform time grid.")
    state = initialize_moving_wedge_state(config, motion, time_s=float(time[0]))
    force = np.zeros(len(time), dtype=float)
    potential_residual = np.zeros(len(time), dtype=float)
    pressure_residual = np.zeros(len(time), dtype=float)
    free_pressure = np.zeros(len(time), dtype=float)
    contact_residual = np.zeros(len(time), dtype=float)
    for index, target_time in enumerate(time):
        if abs(state.time_s - target_time) > 1e-10:
            raise RuntimeError("Moving-wedge state time lost alignment with the requested grid.")
        load = moving_wedge_load(
            config,
            motion,
            state,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
        )
        force[index] = load.pressure.body_vertical_force_per_length_n_m
        potential_residual[index] = load.potential_bvp_relative_residual
        pressure_residual[index] = load.pressure.auxiliary_solution.relative_residual
        free_pressure[index] = load.pressure.free_surface_pressure_max_abs_pa
        contact_residual[index] = load.contact_constraint_max_abs_m
        if index + 1 < len(time):
            step = advance_moving_wedge_rk4(
                config,
                motion,
                state,
                time_step_s=float(steps[index]),
                gravity_m_s2=gravity_m_s2,
            )
            potential_residual[index] = max(
                potential_residual[index], step.max_potential_relative_residual
            )
            state = step.state
    return MovingWedgeTimeHistory(
        time_s=time,
        vertical_force_per_length_n_m=force,
        potential_bvp_relative_residual=potential_residual,
        pressure_bvp_relative_residual=pressure_residual,
        free_surface_pressure_max_abs_pa=free_pressure,
        contact_constraint_max_abs_m=contact_residual,
        final_state=state,
    )


def identify_moving_wedge_heave_coefficients(
    config: MovingWedgeConfig,
    motion: SinusoidalVerticalMotion,
    history: MovingWedgeTimeHistory,
    *,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    discard_cycles: float = 1.0,
    retained_cycles: float | None = None,
    fitted_harmonics: int = 3,
) -> MovingWedgeHeaveCoefficients:
    """Identify sectional ``A33`` and ``B33`` using Sun Eqs. (6.6)-(6.8)."""

    if motion.amplitude_m <= 0.0:
        raise ValueError("Coefficient identification requires a positive heave amplitude.")
    fit = fit_periodic_harmonics(
        history.time_s,
        history.vertical_force_per_length_n_m,
        motion.omega_rad_s,
        discard_cycles=discard_cycles,
        retained_cycles=retained_cycles,
        fitted_harmonics=fitted_harmonics,
    )
    waterline_beam = 2.0 * float(config.mean_draft_m) / np.tan(float(config.deadrise_rad))
    restoring = float(rho_water_kg_m3) * float(gravity_m_s2) * waterline_beam
    sine = float(fit.sine[0])
    cosine = float(fit.cosine[0])
    amplitude = float(motion.amplitude_m)
    omega = float(motion.omega_rad_s)
    added = -(sine - restoring * amplitude) / (omega**2 * amplitude)
    damping = cosine / (omega * amplitude)
    return MovingWedgeHeaveCoefficients(
        omega_rad_s=omega,
        motion_amplitude_m=amplitude,
        added_mass_per_length_kg_m=float(added),
        damping_per_length_kg_m_s=float(damping),
        restoring_per_length_n_m2=restoring,
        harmonic_fit=fit,
    )


def run_steady_planing_wedge_entry(
    config: MovingWedgeConfig,
    *,
    speed_mps: float,
    trim_rad: float,
    wetted_length_m: float,
    time_step_s: float,
    initial_draft_m: float,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> SteadyPlaningWedgeEntryResult:
    """March one ground-fixed plane through a steady prismatic planing hull.

    The local draft grows as ``d=d0+U*tan(trim)*t``. This is the steady
    2D+t base-flow history needed before a forced oscillation is superposed.
    ``initializer='wagner'`` uses Sun (2007), Eqs. 2.14-2.15, at the finite
    starting draft; ``flat`` retains the simpler diagnostic initializer.
    """

    speed = float(speed_mps)
    trim = float(trim_rad)
    length = float(wetted_length_m)
    dt = float(time_step_s)
    initial_draft = float(initial_draft_m)
    if speed <= 0.0 or not 0.0 < trim < 0.5 * np.pi or length <= 0.0 or dt <= 0.0:
        raise ValueError("Steady planing entry requires positive speed, trim, length, and time step.")
    draft_rate = speed * np.tan(trim)
    target_duration = max((length * np.tan(trim) - initial_draft) / draft_rate, 0.0)
    step_count = max(int(np.ceil(target_duration / dt)), 1)
    time = np.linspace(0.0, step_count * dt, step_count + 1)
    # Size the numerical domain from the exact physical endpoint plus one fixed
    # step of margin. Using time[-1] here makes the whole mesh jump whenever
    # ceil(target_duration / dt) changes, which contaminates restoring-force
    # derivatives with a non-physical station-count discontinuity.
    target_draft = initial_draft + draft_rate * target_duration
    reference_draft = max(
        float(config.mean_draft_m),
        target_draft + draft_rate * dt,
    )
    motion = LinearDraftEntryMotion(
        reference_draft_m=reference_draft,
        initial_draft_m=initial_draft,
        draft_rate_mps=draft_rate,
    )
    working_config = MovingWedgeConfig(
        **{
            **config.__dict__,
            "mean_draft_m": reference_draft,
        }
    )
    state = initialize_moving_wedge_state(working_config, motion)
    states: list[MovingWedgeState] = []
    force = np.zeros(len(time))
    potential_residual = np.zeros(len(time))
    pressure_residual = np.zeros(len(time))
    contact_residual = np.zeros(len(time))
    separation_event_times: list[float] = []
    for index in range(len(time)):
        states.append(state)
        load = moving_wedge_load(
            working_config,
            motion,
            state,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
        )
        force[index] = load.pressure.body_vertical_force_per_length_n_m
        potential_residual[index] = load.potential_bvp_relative_residual
        pressure_residual[index] = load.pressure.auxiliary_solution.relative_residual
        contact_residual[index] = load.contact_constraint_max_abs_m
        if index + 1 < len(time):
            step = advance_moving_wedge_rk4(
                working_config,
                motion,
                state,
                time_step_s=dt,
                gravity_m_s2=gravity_m_s2,
            )
            potential_residual[index] = max(
                potential_residual[index], step.max_potential_relative_residual
            )
            if step.separation_event_time_s is not None:
                separation_event_times.append(float(step.separation_event_time_s))
            state = step.state
    draft = np.asarray([motion.draft_m(value) for value in time], dtype=float)
    separated_indices = [
        index
        for index, candidate in enumerate(states)
        if candidate.right_free_y_m[0]
        > float(config.chine_half_beam_m) * (1.0 + 1e-10)
    ]

    def finite_state_extreme(name: str, reducer) -> float | None:
        values = [
            float(value)
            for candidate in states
            if (value := getattr(candidate, name)) is not None
        ]
        return None if not values else float(reducer(values))

    return SteadyPlaningWedgeEntryResult(
        time_s=time,
        x_from_leading_edge_m=speed * time,
        draft_m=draft,
        vertical_force_per_length_n_m=force,
        states=tuple(states),
        reference_draft_m=float(reference_draft),
        final_jet_cut_count=int(states[-1].jet_cut_count),
        separated_state_count=len(separated_indices),
        separation_event_count=len(separation_event_times),
        first_separation_time_s=(
            None if not separation_event_times else float(separation_event_times[0])
        ),
        first_separation_x_from_leading_m=(
            float(speed * separation_event_times[0])
            if separation_event_times
            else (
                None
                if not separated_indices
                else float(speed * time[separated_indices[0]])
            )
        ),
        minimum_jet_normal_distance_ratio=finite_state_extreme(
            "minimum_jet_normal_distance_ratio", min
        ),
        minimum_jet_projection_ratio=finite_state_extreme(
            "minimum_jet_projection_ratio", min
        ),
        maximum_jet_projection_ratio=finite_state_extreme(
            "maximum_jet_projection_ratio", max
        ),
        max_potential_bvp_relative_residual=float(np.max(potential_residual)),
        max_pressure_bvp_relative_residual=float(np.max(pressure_residual)),
        max_contact_constraint_abs_m=float(np.max(contact_residual)),
        status=(
            "sun_2dt_steady_planing_wedge_entry_wagner_initialized"
            if config.initializer == "wagner"
            else "sun_2dt_steady_planing_wedge_entry_wagner_initializer_pending"
        ),
    )
