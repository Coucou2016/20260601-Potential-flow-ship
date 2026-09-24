from __future__ import annotations

"""Extract Sun (2007) Fig. 2.6 blue SIM paths from the native PDF stream.

The extractor intentionally derives curve geometry and axis calibration from the
PDF alone.  The raster redigitization and legacy CSV are opened only after the
six vector curves have been selected and calibrated, and are used solely for
post-extraction difference audits.
"""

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

from pypdf import PdfReader
from pypdf.generic import ContentStream


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmarks" / "sun2007_fig2_6_wedge_similarity"
DEFAULT_PDF = BENCHMARK_DIR / "sun2007_boundary_element_method.pdf"
DEFAULT_RASTER_CSV = (
    BENCHMARK_DIR
    / "pdf_redigitization_v1"
    / "fig2_6_pdf_rebuild_similarity_curves.csv"
)
DEFAULT_LEGACY_CSV = (
    BENCHMARK_DIR
    / "fig2_6_zhao_faltinsen_similarity_curves.csv"
)

FIGURE_PAGE_INDEX_ZERO_BASED = 39
EXPECTED_SOURCE_PDF_SHA256 = "0da387d3296a291e66efa080e1110eb00cad88af45bf9a3cdec642530c5f502d"

VECTOR_CSV_FILENAME = "sun2007_fig2_6_vector_similarity_curves.csv"
RASTER_AUDIT_FILENAME = "sun2007_fig2_6_vector_vs_pdf_redigitization_audit.csv"
LEGACY_AUDIT_FILENAME = "sun2007_fig2_6_vector_vs_legacy_audit.csv"
MANIFEST_FILENAME = "sun2007_fig2_6_vector_extraction_manifest.json"

VECTOR_FIELDS = (
    "beta_deg",
    "quantity",
    "branch_policy",
    "x_name",
    "x_nondimensional",
    "y_name",
    "y_nondimensional",
    "pdf_x",
    "pdf_y",
    "stroke_operation_index",
    "source_subpath_index",
    "visible_piece_index",
    "vertex_index",
    "clip_applied",
)
AUDIT_FIELDS = (
    "comparison_source",
    "beta_deg",
    "quantity",
    "matching_method",
    "vector_point_count",
    "reference_point_count",
    "compared_point_count",
    "common_x_min",
    "common_x_max",
    "max_abs_x_difference",
    "mean_signed_y_difference",
    "max_abs_y_difference",
    "rmse_y_difference",
    "reference_y_span",
    "nrmse_y_difference",
)

Point = tuple[float, float]
Rect = tuple[float, float, float, float]
Matrix = tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class PanelSpec:
    panel: str
    beta_deg: float
    quantity: str
    x_name: str
    y_name: str
    plot_box: Rect
    x_ticks: tuple[tuple[float, float], ...]
    y_ticks: tuple[tuple[float, float], ...]


# Tick locations are page-user-space centres of the labelled ticks visible on
# Fig. 2.6.  They were transcribed from the page's native vector axes, not from
# either CSV or a rendered/raster panel.
PANEL_SPECS = (
    PanelSpec(
        "beta10_free_surface",
        10.0,
        "free_surface",
        "y_over_Vt",
        "z_over_Vt",
        (81.42, 508.719, 239.46, 625.299),
        ((81.42, 0.0), (120.96, 5.0), (160.44, 10.0), (199.92, 15.0), (239.46, 20.0)),
        ((508.719, -2.0), (537.819, -1.0), (566.979, 0.0), (596.139, 1.0), (625.299, 2.0)),
    ),
    PanelSpec(
        "beta10_pressure",
        10.0,
        "pressure",
        "z_over_Vt",
        "p_over_half_rho_V2",
        (281.88, 506.979, 440.46, 624.279),
        ((281.88, -1.0), (321.54, -0.5), (361.20, 0.0), (400.80, 0.5), (440.46, 1.0)),
        ((506.979, 0.0), (530.439, 20.0), (553.899, 40.0), (577.359, 60.0), (600.819, 80.0)),
    ),
    PanelSpec(
        "beta20_free_surface",
        20.0,
        "free_surface",
        "y_over_Vt",
        "z_over_Vt",
        (86.64, 343.839, 241.74, 457.839),
        ((86.64, 0.0), (125.40, 2.5), (164.22, 5.0), (202.98, 7.5), (241.74, 10.0)),
        ((343.839, -5.0), (372.339, -2.5), (400.839, 0.0), (429.339, 2.5), (457.839, 5.0)),
    ),
    PanelSpec(
        "beta20_pressure",
        20.0,
        "pressure",
        "z_over_Vt",
        "p_over_half_rho_V2",
        (283.50, 344.139, 439.50, 459.399),
        ((283.50, -1.0), (322.50, -0.5), (361.50, 0.0), (400.50, 0.5), (439.50, 1.0)),
        ((344.139, 0.0), (372.939, 5.0), (401.739, 10.0), (430.539, 15.0), (459.399, 20.0)),
    ),
    PanelSpec(
        "beta30_free_surface",
        30.0,
        "free_surface",
        "y_over_Vt",
        "z_over_Vt",
        (81.72, 174.219, 241.20, 293.439),
        ((81.72, 0.0), (134.88, 2.0), (188.04, 4.0), (241.20, 6.0)),
        ((174.219, -3.0), (194.139, -2.0), (213.939, -1.0), (233.799, 0.0), (253.719, 1.0), (273.519, 2.0), (293.439, 3.0)),
    ),
    PanelSpec(
        "beta30_pressure",
        30.0,
        "pressure",
        "z_over_Vt",
        "p_over_half_rho_V2",
        (279.84, 176.859, 437.58, 293.439),
        ((279.84, -1.0), (319.26, -0.5), (358.68, 0.0), (398.10, 0.5), (437.58, 1.0)),
        ((176.859, 0.0), (205.959, 2.0), (235.119, 4.0), (264.279, 6.0), (293.439, 8.0)),
    ),
)


@dataclass(frozen=True)
class AxisCalibration:
    slope: float
    intercept: float
    ticks: tuple[tuple[float, float], ...]
    max_abs_residual: float

    def value(self, coordinate: float) -> float:
        return self.slope * coordinate + self.intercept

    def manifest_record(self) -> dict[str, Any]:
        return {
            "coordinate_definition": "value = slope * pdf_page_user_space + intercept",
            "slope": self.slope,
            "intercept": self.intercept,
            "max_abs_residual_at_labelled_ticks": self.max_abs_residual,
            "labelled_ticks": [
                {"pdf_page_user_space": coordinate, "axis_value": value}
                for coordinate, value in self.ticks
            ],
        }


@dataclass(frozen=True)
class GraphicsState:
    ctm: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    stroke_color_space: str | None = None
    stroke_color: tuple[float, ...] | None = None
    line_width: float = 1.0
    dash: tuple[tuple[float, ...], float] = ((), 0.0)
    clip: Rect | None = None


@dataclass(frozen=True)
class Stroke:
    operation_index: int
    path_start_operation_index: int
    subpaths: tuple[tuple[Point, ...], ...]
    path_operators: tuple[str, ...]
    stroke_color_space: str | None
    stroke_color: tuple[float, ...] | None
    line_width: float
    dash: tuple[tuple[float, ...], float]
    ctm_at_paint: Matrix
    clip: Rect | None

    @property
    def point_count(self) -> int:
        return sum(len(path) for path in self.subpaths)

    @property
    def bbox(self) -> Rect:
        points = [point for path in self.subpaths for point in path]
        return _bbox(points)


@dataclass(frozen=True)
class VisibleSubpath:
    stroke_operation_index: int
    source_subpath_index: int
    visible_piece_index: int
    points: tuple[Point, ...]
    clip_applied: bool


@dataclass(frozen=True)
class CurveResult:
    spec: PanelSpec
    x_calibration: AxisCalibration
    y_calibration: AxisCalibration
    selected_strokes: tuple[Stroke, ...]
    rows: tuple[dict[str, Any], ...]
    fold: dict[str, Any] | None


@dataclass(frozen=True)
class PdfExtraction:
    source_pdf_sha256: str
    content_stream_sha256: str
    color_space_record: dict[str, Any]
    global_dash_record: dict[str, Any]
    blue_strokes: tuple[Stroke, ...]
    curves: tuple[CurveResult, ...]
    xobject_count: int


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _bbox(points: Iterable[Point]) -> Rect:
    values = tuple(points)
    if not values:
        raise ValueError("Cannot calculate a bounding box for an empty path.")
    return (
        min(x for x, _ in values),
        min(y for _, y in values),
        max(x for x, _ in values),
        max(y for _, y in values),
    )


def _intersection(first: Rect | None, second: Rect | None) -> Rect | None:
    if first is None:
        return second
    if second is None:
        return first
    return (
        max(first[0], second[0]),
        max(first[1], second[1]),
        min(first[2], second[2]),
        min(first[3], second[3]),
    )


def _rectangles_overlap(first: Rect, second: Rect) -> bool:
    return (
        min(first[2], second[2]) >= max(first[0], second[0])
        and min(first[3], second[3]) >= max(first[1], second[1])
    )


def _matrix_multiply(left: Matrix, right: Matrix) -> Matrix:
    """Return the PDF row-vector affine composition left then right."""

    a, b, c, d, e, f = left
    A, B, C, D, E, F = right
    return (
        a * A + b * C,
        a * B + b * D,
        c * A + d * C,
        c * B + d * D,
        e * A + f * C + E,
        e * B + f * D + F,
    )


def _transform_point(point: Point, matrix: Matrix) -> Point:
    x, y = point
    a, b, c, d, e, f = matrix
    return (a * x + c * y + e, b * x + d * y + f)


def _append_cubic(
    subpath: list[Point],
    control_one: Point,
    control_two: Point,
    end: Point,
    *,
    subdivisions: int = 16,
) -> None:
    start = subpath[-1]
    for index in range(1, subdivisions + 1):
        t = index / subdivisions
        one_minus_t = 1.0 - t
        x = (
            one_minus_t**3 * start[0]
            + 3.0 * one_minus_t**2 * t * control_one[0]
            + 3.0 * one_minus_t * t**2 * control_two[0]
            + t**3 * end[0]
        )
        y = (
            one_minus_t**3 * start[1]
            + 3.0 * one_minus_t**2 * t * control_one[1]
            + 3.0 * one_minus_t * t**2 * control_two[1]
            + t**3 * end[1]
        )
        subpath.append((x, y))


def _rect_from_clip_path(subpaths: Sequence[Sequence[Point]]) -> Rect:
    if len(subpaths) != 1 or len(subpaths[0]) < 4:
        raise ValueError("The source page uses a non-rectangular clipping path.")
    points = tuple(subpaths[0])
    left, bottom, right, top = _bbox(points)
    if not left < right or not bottom < top:
        raise ValueError("The source page uses a degenerate clipping rectangle.")
    allowed = {
        (left, bottom),
        (left, top),
        (right, bottom),
        (right, top),
    }
    if any(point not in allowed for point in points):
        raise ValueError("The source page uses a non-axis-aligned clipping path.")
    return (left, bottom, right, top)


def _clip_segment_to_rect(start: Point, end: Point, rect: Rect) -> tuple[Point, Point] | None:
    left, bottom, right, top = rect
    if left > right or bottom > top:
        return None
    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    enter = 0.0
    leave = 1.0
    for p, q in ((-dx, x0 - left), (dx, right - x0), (-dy, y0 - bottom), (dy, top - y0)):
        if math.isclose(p, 0.0, abs_tol=1e-15):
            if q < 0.0:
                return None
            continue
        ratio = q / p
        if p < 0.0:
            if ratio > leave:
                return None
            enter = max(enter, ratio)
        else:
            if ratio < enter:
                return None
            leave = min(leave, ratio)
    if enter > leave:
        return None
    return ((x0 + enter * dx, y0 + enter * dy), (x0 + leave * dx, y0 + leave * dy))


def _clip_polyline(points: Sequence[Point], rect: Rect | None) -> list[tuple[Point, ...]]:
    if len(points) < 2:
        return []
    if rect is None:
        return [tuple(points)]
    pieces: list[list[Point]] = []
    active: list[Point] | None = None
    for start, end in zip(points, points[1:]):
        clipped = _clip_segment_to_rect(start, end, rect)
        if clipped is None:
            active = None
            continue
        clipped_start, clipped_end = clipped
        if active is None or active[-1] != clipped_start:
            active = [clipped_start, clipped_end]
            pieces.append(active)
        else:
            active.append(clipped_end)
    return [tuple(piece) for piece in pieces if len(piece) >= 2]


def _fit_axis(ticks: Sequence[tuple[float, float]]) -> AxisCalibration:
    if len(ticks) < 2:
        raise ValueError("At least two labelled ticks are required for calibration.")
    coordinates = [coordinate for coordinate, _ in ticks]
    values = [value for _, value in ticks]
    coordinate_mean = sum(coordinates) / len(coordinates)
    value_mean = sum(values) / len(values)
    denominator = sum((coordinate - coordinate_mean) ** 2 for coordinate in coordinates)
    if math.isclose(denominator, 0.0):
        raise ValueError("Labelled tick coordinates are degenerate.")
    slope = sum(
        (coordinate - coordinate_mean) * (value - value_mean)
        for coordinate, value in ticks
    ) / denominator
    intercept = value_mean - slope * coordinate_mean
    max_abs_residual = max(abs(slope * coordinate + intercept - value) for coordinate, value in ticks)
    return AxisCalibration(
        slope=slope,
        intercept=intercept,
        ticks=tuple(ticks),
        max_abs_residual=max_abs_residual,
    )


def _finish_path(
    current_path: list[list[Point]],
    pending_clip: Rect | None,
    state: GraphicsState,
) -> tuple[list[list[Point]], GraphicsState, Rect | None]:
    if pending_clip is not None:
        state = replace(state, clip=_intersection(state.clip, pending_clip))
    return [], state, None


def _parse_strokes(page: Any, reader: PdfReader) -> tuple[list[Stroke], bytes, list[dict[str, Any]]]:
    contents = page.get_contents()
    raw_content = contents.get_data()
    content = ContentStream(contents, reader)
    state = GraphicsState()
    stack: list[GraphicsState] = []
    current_path: list[list[Point]] = []
    current_subpath: list[Point] | None = None
    path_operators: list[str] = []
    path_start_operation_index: int | None = None
    pending_clip: Rect | None = None
    strokes: list[Stroke] = []
    dash_operators: list[dict[str, Any]] = []

    def begin_path_operator(index: int, operator: str) -> None:
        nonlocal path_start_operation_index
        if path_start_operation_index is None:
            path_start_operation_index = index
        path_operators.append(operator)

    for index, (operands, raw_operator) in enumerate(content.operations):
        operator = raw_operator.decode("latin-1")
        if operator == "q":
            stack.append(state)
            continue
        if operator == "Q":
            if not stack:
                raise ValueError("Unbalanced Q operator in the source page.")
            state = stack.pop()
            continue
        if operator == "cm":
            matrix = tuple(float(value) for value in operands)
            if len(matrix) != 6:
                raise ValueError("Malformed cm operator in the source page.")
            state = replace(state, ctm=_matrix_multiply(matrix, state.ctm))
            continue
        if operator == "CS":
            state = replace(state, stroke_color_space=str(operands[0]))
            continue
        if operator in {"SC", "SCN"}:
            state = replace(state, stroke_color=tuple(float(value) for value in operands))
            continue
        if operator == "G":
            state = replace(
                state,
                stroke_color_space="/DeviceGray",
                stroke_color=(float(operands[0]),),
            )
            continue
        if operator == "RG":
            state = replace(
                state,
                stroke_color_space="/DeviceRGB",
                stroke_color=tuple(float(value) for value in operands),
            )
            continue
        if operator == "K":
            state = replace(
                state,
                stroke_color_space="/DeviceCMYK",
                stroke_color=tuple(float(value) for value in operands),
            )
            continue
        if operator == "w":
            state = replace(state, line_width=float(operands[0]))
            continue
        if operator == "d":
            dash = (tuple(float(value) for value in operands[0]), float(operands[1]))
            state = replace(state, dash=dash)
            dash_operators.append(
                {"operation_index": index, "array": list(dash[0]), "phase": dash[1]}
            )
            continue
        if operator == "m":
            begin_path_operator(index, operator)
            current_subpath = [_transform_point((float(operands[0]), float(operands[1])), state.ctm)]
            current_path.append(current_subpath)
            continue
        if operator == "l":
            if current_subpath is None:
                raise ValueError("Line-to without a current subpath in the source page.")
            begin_path_operator(index, operator)
            current_subpath.append(
                _transform_point((float(operands[0]), float(operands[1])), state.ctm)
            )
            continue
        if operator == "re":
            begin_path_operator(index, operator)
            x, y, width, height = (float(value) for value in operands)
            raw_points = ((x, y), (x + width, y), (x + width, y + height), (x, y + height), (x, y))
            current_subpath = [_transform_point(point, state.ctm) for point in raw_points]
            current_path.append(current_subpath)
            continue
        if operator in {"c", "v", "y"}:
            if current_subpath is None:
                raise ValueError("Bezier operator without a current subpath in the source page.")
            begin_path_operator(index, operator)
            if operator == "c":
                raw_control_one = (float(operands[0]), float(operands[1]))
                raw_control_two = (float(operands[2]), float(operands[3]))
                raw_end = (float(operands[4]), float(operands[5]))
                control_one = _transform_point(raw_control_one, state.ctm)
                control_two = _transform_point(raw_control_two, state.ctm)
                end = _transform_point(raw_end, state.ctm)
            elif operator == "v":
                control_one = current_subpath[-1]
                control_two = _transform_point((float(operands[0]), float(operands[1])), state.ctm)
                end = _transform_point((float(operands[2]), float(operands[3])), state.ctm)
            else:
                control_one = _transform_point((float(operands[0]), float(operands[1])), state.ctm)
                end = _transform_point((float(operands[2]), float(operands[3])), state.ctm)
                control_two = end
            _append_cubic(current_subpath, control_one, control_two, end)
            continue
        if operator == "h":
            if current_subpath is None:
                raise ValueError("Close-path without a current subpath in the source page.")
            begin_path_operator(index, operator)
            if current_subpath[-1] != current_subpath[0]:
                current_subpath.append(current_subpath[0])
            continue
        if operator in {"W", "W*"}:
            pending_clip = _rect_from_clip_path(current_path)
            continue
        if operator in {"s", "b", "b*"} and current_subpath is not None:
            if current_subpath[-1] != current_subpath[0]:
                current_subpath.append(current_subpath[0])
            path_operators.append("h")
        if operator in {"S", "s", "B", "B*", "b", "b*", "f", "F", "f*", "n"}:
            if pending_clip is not None:
                state = replace(state, clip=_intersection(state.clip, pending_clip))
                pending_clip = None
            if operator in {"S", "s", "B", "B*", "b", "b*"} and current_path:
                strokes.append(
                    Stroke(
                        operation_index=index,
                        path_start_operation_index=path_start_operation_index
                        if path_start_operation_index is not None
                        else index,
                        subpaths=tuple(tuple(path) for path in current_path),
                        path_operators=tuple(sorted(set(path_operators))),
                        stroke_color_space=state.stroke_color_space,
                        stroke_color=state.stroke_color,
                        line_width=state.line_width,
                        dash=state.dash,
                        ctm_at_paint=state.ctm,
                        clip=state.clip,
                    )
                )
            current_path = []
            current_subpath = None
            path_operators = []
            path_start_operation_index = None
            continue

    if stack:
        raise ValueError("Unbalanced q operator in the source page.")
    return strokes, raw_content, dash_operators


def _is_source_blue(stroke: Stroke) -> bool:
    return (
        stroke.stroke_color_space == "/Cs6"
        and stroke.stroke_color is not None
        and len(stroke.stroke_color) == 3
        and all(math.isclose(component, expected, abs_tol=1e-12) for component, expected in zip(stroke.stroke_color, (0.0, 0.0, 1.0)))
    )


def _stroke_matches_panel(stroke: Stroke, spec: PanelSpec) -> bool:
    return _rectangles_overlap(stroke.bbox, spec.plot_box)


def _select_strokes_for_panel(blue_strokes: Sequence[Stroke], spec: PanelSpec) -> tuple[Stroke, ...]:
    main_candidates = [
        stroke
        for stroke in blue_strokes
        if len(stroke.subpaths) >= 20 and _stroke_matches_panel(stroke, spec)
    ]
    if len(main_candidates) != 1:
        candidates = [stroke.operation_index for stroke in main_candidates]
        raise ValueError(f"Expected one main blue dashed path for {spec.panel}; got {candidates}.")
    main = main_candidates[0]
    main_index = blue_strokes.index(main)
    selected = [main]

    # The source uses individual short blue subpaths rather than a PDF dash
    # pattern.  Boundary-crossing dash fragments are emitted in neighbouring
    # q/re/W/n blocks, immediately before or after the main stroke.  A legend
    # dash is the first neighbouring unclipped blue stroke and terminates this
    # local association.
    for direction in (-1, 1):
        cursor = main_index + direction
        adjacent: list[Stroke] = []
        while 0 <= cursor < len(blue_strokes):
            candidate = blue_strokes[cursor]
            if candidate.clip is None:
                break
            if _stroke_matches_panel(candidate, spec):
                adjacent.append(candidate)
            cursor += direction
        selected.extend(adjacent)
    return tuple(sorted(set(selected), key=lambda stroke: stroke.operation_index))


def _visible_subpaths(strokes: Sequence[Stroke]) -> list[VisibleSubpath]:
    visible: list[VisibleSubpath] = []
    for stroke in strokes:
        for source_subpath_index, source_subpath in enumerate(stroke.subpaths):
            for visible_piece_index, piece in enumerate(_clip_polyline(source_subpath, stroke.clip)):
                visible.append(
                    VisibleSubpath(
                        stroke_operation_index=stroke.operation_index,
                        source_subpath_index=source_subpath_index,
                        visible_piece_index=visible_piece_index,
                        points=piece,
                        clip_applied=stroke.clip is not None,
                    )
                )
    return visible


def _outer_free_surface_subpaths(
    visible_subpaths: Sequence[VisibleSubpath],
) -> tuple[list[VisibleSubpath], dict[str, Any]]:
    if not visible_subpaths:
        raise ValueError("No visible blue path segments were available for free-surface selection.")
    fold_subpath_index = -1
    fold_vertex_index = -1
    fold_point: Point | None = None
    for subpath_index, subpath in enumerate(visible_subpaths):
        for vertex_index, point in enumerate(subpath.points):
            if fold_point is None or point[0] < fold_point[0]:
                fold_subpath_index = subpath_index
                fold_vertex_index = vertex_index
                fold_point = point
    assert fold_point is not None

    selected: list[VisibleSubpath] = []
    fold_subpath = visible_subpaths[fold_subpath_index]
    folded_points = fold_subpath.points[fold_vertex_index:]
    if len(folded_points) >= 2:
        selected.append(replace(fold_subpath, points=folded_points))
    selected.extend(visible_subpaths[fold_subpath_index + 1 :])
    if not selected:
        raise ValueError("The outward free-surface branch has no visible line segment.")
    return selected, {
        "selection": "content_stream_global_minimum_pdf_x_fold_then_follow_render_order",
        "fold_stroke_operation_index": fold_subpath.stroke_operation_index,
        "fold_source_subpath_index": fold_subpath.source_subpath_index,
        "fold_visible_piece_index": fold_subpath.visible_piece_index,
        "fold_vertex_index": fold_vertex_index,
        "fold_pdf_x": fold_point[0],
        "fold_pdf_y": fold_point[1],
    }


def _curve_rows(
    spec: PanelSpec,
    x_calibration: AxisCalibration,
    y_calibration: AxisCalibration,
    subpaths: Sequence[VisibleSubpath],
) -> list[dict[str, Any]]:
    branch_policy = (
        "content_stream_fold_to_outward_branch"
        if spec.quantity == "free_surface"
        else "all_visible_content_stream_dashed_segments"
    )
    rows: list[dict[str, Any]] = []
    for subpath in subpaths:
        for vertex_index, (pdf_x, pdf_y) in enumerate(subpath.points):
            rows.append(
                {
                    "beta_deg": spec.beta_deg,
                    "quantity": spec.quantity,
                    "branch_policy": branch_policy,
                    "x_name": spec.x_name,
                    "x_nondimensional": x_calibration.value(pdf_x),
                    "y_name": spec.y_name,
                    "y_nondimensional": y_calibration.value(pdf_y),
                    "pdf_x": pdf_x,
                    "pdf_y": pdf_y,
                    "stroke_operation_index": subpath.stroke_operation_index,
                    "source_subpath_index": subpath.source_subpath_index,
                    "visible_piece_index": subpath.visible_piece_index,
                    "vertex_index": vertex_index,
                    "clip_applied": int(subpath.clip_applied),
                }
            )
    return rows


def _color_space_record(page: Any) -> dict[str, Any]:
    resources = page["/Resources"].get_object()
    color_spaces = resources["/ColorSpace"].get_object()
    source_blue_space = color_spaces["/Cs6"].get_object()
    if str(source_blue_space[0]) != "/ICCBased":
        raise ValueError("Expected /Cs6 to be ICCBased in the source page.")
    profile = source_blue_space[1].get_object()
    if int(profile["/N"]) != 3 or str(profile["/Alternate"]) != "/DeviceRGB":
        raise ValueError("Expected /Cs6 to use a three-component DeviceRGB alternate.")
    return {
        "resource_name": "/Cs6",
        "kind": "/ICCBased",
        "component_count": int(profile["/N"]),
        "alternate": str(profile["/Alternate"]),
        "blue_stroke_components": [0.0, 0.0, 1.0],
    }


def extract_vector_rows(pdf_path: Path = DEFAULT_PDF) -> PdfExtraction:
    """Extract and calibrate the six curves using only the source PDF."""

    pdf_path = Path(pdf_path)
    source_pdf_sha256 = _sha256_file(pdf_path)
    if source_pdf_sha256 != EXPECTED_SOURCE_PDF_SHA256:
        raise ValueError(
            "Unexpected source PDF hash; the fixed Fig. 2.6 tick map and operator layout must not be applied to a different PDF."
        )
    reader = PdfReader(pdf_path)
    if FIGURE_PAGE_INDEX_ZERO_BASED >= len(reader.pages):
        raise ValueError("Fig. 2.6 page index is out of bounds for the source PDF.")
    page = reader.pages[FIGURE_PAGE_INDEX_ZERO_BASED]
    resources = page["/Resources"].get_object()
    xobjects = resources.get("/XObject")
    xobject_count = len(xobjects.get_object()) if xobjects is not None else 0
    if xobject_count:
        raise ValueError("The source page unexpectedly contains XObjects; native path extraction is no longer assured.")
    color_space_record = _color_space_record(page)
    strokes, raw_content, dash_operators = _parse_strokes(page, reader)
    blue_strokes = tuple(stroke for stroke in strokes if _is_source_blue(stroke))
    if not blue_strokes:
        raise ValueError("No /Cs6 [0 0 1] blue stroke paths were found on the source page.")
    if not dash_operators or dash_operators != [{"operation_index": 19, "array": [], "phase": 0.0}]:
        raise ValueError("The source page's dash-operator evidence differs from the expected manual-dash layout.")

    curves: list[CurveResult] = []
    for spec in PANEL_SPECS:
        x_calibration = _fit_axis(spec.x_ticks)
        y_calibration = _fit_axis(spec.y_ticks)
        selected_strokes = _select_strokes_for_panel(blue_strokes, spec)
        visible_subpaths = _visible_subpaths(selected_strokes)
        fold: dict[str, Any] | None = None
        if spec.quantity == "free_surface":
            visible_subpaths, fold = _outer_free_surface_subpaths(visible_subpaths)
        rows = _curve_rows(spec, x_calibration, y_calibration, visible_subpaths)
        if not rows:
            raise ValueError(f"No output vertices remained for {spec.panel}.")
        curves.append(
            CurveResult(
                spec=spec,
                x_calibration=x_calibration,
                y_calibration=y_calibration,
                selected_strokes=selected_strokes,
                rows=tuple(rows),
                fold=fold,
            )
        )
    return PdfExtraction(
        source_pdf_sha256=source_pdf_sha256,
        content_stream_sha256=_sha256_bytes(raw_content),
        color_space_record=color_space_record,
        global_dash_record=dash_operators[0],
        blue_strokes=blue_strokes,
        curves=tuple(curves),
        xobject_count=xobject_count,
    )


def _read_reference_rows(path: Path) -> list[dict[str, float | str]]:
    required = {"beta_deg", "quantity", "x_nondimensional", "y_nondimensional"}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Reference CSV {path} is missing required curve columns.")
        return [
            {
                "beta_deg": float(row["beta_deg"]),
                "quantity": row["quantity"],
                "x_nondimensional": float(row["x_nondimensional"]),
                "y_nondimensional": float(row["y_nondimensional"]),
            }
            for row in reader
        ]


def _audit_against_reference(
    curves: Sequence[CurveResult],
    reference_rows: Sequence[dict[str, float | str]],
    comparison_source: str,
) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for curve in curves:
        vector = list(curve.rows)
        reference = [
            row
            for row in reference_rows
            if float(row["beta_deg"]) == curve.spec.beta_deg
            and str(row["quantity"]) == curve.spec.quantity
        ]
        if not reference:
            raise ValueError(f"Reference CSV lacks {curve.spec.panel}.")
        vector_x = [float(row["x_nondimensional"]) for row in vector]
        common_x_min = max(min(vector_x), min(float(row["x_nondimensional"]) for row in reference))
        common_x_max = min(max(vector_x), max(float(row["x_nondimensional"]) for row in reference))
        compared = [
            row
            for row in reference
            if common_x_min <= float(row["x_nondimensional"]) <= common_x_max
        ]
        if not compared:
            raise ValueError(f"No common x-domain remains for {comparison_source} {curve.spec.panel}.")
        x_differences: list[float] = []
        y_differences: list[float] = []
        for observed in compared:
            observed_x = float(observed["x_nondimensional"])
            nearest = min(
                vector,
                key=lambda candidate: abs(float(candidate["x_nondimensional"]) - observed_x),
            )
            x_differences.append(float(nearest["x_nondimensional"]) - observed_x)
            y_differences.append(float(nearest["y_nondimensional"]) - float(observed["y_nondimensional"]))
        reference_values = [float(row["y_nondimensional"]) for row in compared]
        reference_span = max(reference_values) - min(reference_values)
        rmse = math.sqrt(sum(difference * difference for difference in y_differences) / len(y_differences))
        audit_rows.append(
            {
                "comparison_source": comparison_source,
                "beta_deg": curve.spec.beta_deg,
                "quantity": curve.spec.quantity,
                "matching_method": "post_extraction_nearest_vector_x_no_interpolation_across_dash_gaps",
                "vector_point_count": len(vector),
                "reference_point_count": len(reference),
                "compared_point_count": len(compared),
                "common_x_min": common_x_min,
                "common_x_max": common_x_max,
                "max_abs_x_difference": max(abs(difference) for difference in x_differences),
                "mean_signed_y_difference": sum(y_differences) / len(y_differences),
                "max_abs_y_difference": max(abs(difference) for difference in y_differences),
                "rmse_y_difference": rmse,
                "reference_y_span": reference_span,
                "nrmse_y_difference": rmse / reference_span if reference_span else None,
            }
        )
    return audit_rows


def _format_csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return format(value, ".15g")
    if value is None:
        return ""
    return value


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_csv_value(row[field]) for field in fieldnames})


def _curve_row_hash(rows: Sequence[dict[str, Any]]) -> str:
    return _sha256_bytes(
        json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    )


def _stroke_record(stroke: Stroke) -> dict[str, Any]:
    return {
        "stroke_operator_index": stroke.operation_index,
        "path_start_operator_index": stroke.path_start_operation_index,
        "path_operators": list(stroke.path_operators),
        "subpath_count": len(stroke.subpaths),
        "point_count": stroke.point_count,
        "line_width": stroke.line_width,
        "dash": {"array": list(stroke.dash[0]), "phase": stroke.dash[1]},
        "ctm_at_paint": list(stroke.ctm_at_paint),
        "clip_box_pdf_user_space": list(stroke.clip) if stroke.clip is not None else None,
    }


def _manifest(
    extraction: PdfExtraction,
    raster_csv: Path,
    legacy_csv: Path,
    raster_rows: Sequence[dict[str, Any]],
    legacy_rows: Sequence[dict[str, Any]],
    output_hashes: dict[str, str],
) -> dict[str, Any]:
    curves = []
    for curve in extraction.curves:
        curves.append(
            {
                "panel": curve.spec.panel,
                "beta_deg": curve.spec.beta_deg,
                "quantity": curve.spec.quantity,
                "plot_box_pdf_user_space": list(curve.spec.plot_box),
                "calibration_source": "labelled vector tick centres on Fig. 2.6; no raster or legacy input",
                "x_axis": {"name": curve.spec.x_name, **curve.x_calibration.manifest_record()},
                "y_axis": {"name": curve.spec.y_name, **curve.y_calibration.manifest_record()},
                "branch_policy": (
                    "content_stream_fold_to_outward_branch"
                    if curve.spec.quantity == "free_surface"
                    else "all_visible_content_stream_dashed_segments"
                ),
                "fold": curve.fold,
                "selected_blue_strokes": [_stroke_record(stroke) for stroke in curve.selected_strokes],
                "point_count": len(curve.rows),
                "vector_row_sha256": _curve_row_hash(curve.rows),
            }
        )
    return {
        "artifact": "Sun 2007 Fig. 2.6 native-PDF blue SIM vector extraction",
        "source": {
            "pdf_filename": DEFAULT_PDF.name,
            "pdf_sha256": extraction.source_pdf_sha256,
            "page_index_zero_based": FIGURE_PAGE_INDEX_ZERO_BASED,
            "page_content_stream_sha256": extraction.content_stream_sha256,
            "xobject_count": extraction.xobject_count,
        },
        "blue_stroke_evidence": {
            "color_space": extraction.color_space_record,
            "color_operator_sequence": ["CS /Cs6", "SCN 0 0 1", "m/l", "S"],
            "global_dash_operator": extraction.global_dash_record,
            "dash_representation": "manual disconnected m/l subpaths; the page-level d operator is [] 0",
            "blue_stroke_count_on_page": len(extraction.blue_strokes),
        },
        "extraction_order": [
            "parse source PDF paths, transformations, and clipping",
            "select blue curve paths and calibrate from labelled PDF ticks",
            "write vector curve rows",
            "read raster and legacy CSVs only for separate post-extraction audits",
        ],
        "reference_use": {
            "raster_used_for_path_selection": False,
            "raster_used_for_axis_calibration": False,
            "legacy_used_for_path_selection": False,
            "legacy_used_for_axis_calibration": False,
        },
        "curves": curves,
        "post_extraction_audits": {
            "pdf_redigitization": {
                "source_csv_filename": raster_csv.name,
                "source_csv_sha256": _sha256_file(raster_csv),
                "row_count": len(raster_rows),
                "audit_filename": RASTER_AUDIT_FILENAME,
                "audit_sha256": output_hashes[RASTER_AUDIT_FILENAME],
            },
            "frozen_legacy_jpeg_digitization": {
                "source_csv_filename": legacy_csv.name,
                "source_csv_sha256": _sha256_file(legacy_csv),
                "row_count": len(legacy_rows),
                "audit_filename": LEGACY_AUDIT_FILENAME,
                "audit_sha256": output_hashes[LEGACY_AUDIT_FILENAME],
            },
        },
        "artifacts": {
            "vector_csv": {
                "filename": VECTOR_CSV_FILENAME,
                "sha256": output_hashes[VECTOR_CSV_FILENAME],
                "row_count": sum(len(curve.rows) for curve in extraction.curves),
            },
            "raster_audit_csv": {
                "filename": RASTER_AUDIT_FILENAME,
                "sha256": output_hashes[RASTER_AUDIT_FILENAME],
                "row_count": len(extraction.curves),
            },
            "legacy_audit_csv": {
                "filename": LEGACY_AUDIT_FILENAME,
                "sha256": output_hashes[LEGACY_AUDIT_FILENAME],
                "row_count": len(extraction.curves),
            },
        },
    }


def extract_sun2007_fig2_6_vector(
    pdf_path: Path,
    output_dir: Path,
    *,
    raster_csv: Path = DEFAULT_RASTER_CSV,
    legacy_csv: Path = DEFAULT_LEGACY_CSV,
) -> Path:
    """Write vector curves, provenance manifest, and two post-extraction audits."""

    extraction = extract_vector_rows(Path(pdf_path))
    vector_rows = [row for curve in extraction.curves for row in curve.rows]

    # These reference inputs are deliberately read only after PDF-only
    # extraction above.  They cannot affect path selection or calibration.
    raster_csv = Path(raster_csv)
    legacy_csv = Path(legacy_csv)
    raster_reference_rows = _read_reference_rows(raster_csv)
    legacy_reference_rows = _read_reference_rows(legacy_csv)
    raster_audit = _audit_against_reference(
        extraction.curves, raster_reference_rows, "pdf_redigitization_v1"
    )
    legacy_audit = _audit_against_reference(
        extraction.curves,
        legacy_reference_rows,
        "frozen_legacy_jpeg_digitization",
    )

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to write into an existing directory: {output_dir}")
    output_dir.mkdir(parents=True)
    vector_path = output_dir / VECTOR_CSV_FILENAME
    raster_audit_path = output_dir / RASTER_AUDIT_FILENAME
    legacy_audit_path = output_dir / LEGACY_AUDIT_FILENAME
    _write_csv(vector_path, VECTOR_FIELDS, vector_rows)
    _write_csv(raster_audit_path, AUDIT_FIELDS, raster_audit)
    _write_csv(legacy_audit_path, AUDIT_FIELDS, legacy_audit)
    output_hashes = {
        VECTOR_CSV_FILENAME: _sha256_file(vector_path),
        RASTER_AUDIT_FILENAME: _sha256_file(raster_audit_path),
        LEGACY_AUDIT_FILENAME: _sha256_file(legacy_audit_path),
    }
    manifest = _manifest(
        extraction,
        raster_csv,
        legacy_csv,
        raster_reference_rows,
        legacy_reference_rows,
        output_hashes,
    )
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--raster-csv", type=Path, default=DEFAULT_RASTER_CSV)
    parser.add_argument("--legacy-csv", type=Path, default=DEFAULT_LEGACY_CSV)
    arguments = parser.parse_args()
    manifest_path = extract_sun2007_fig2_6_vector(
        arguments.pdf,
        arguments.output_dir,
        raster_csv=arguments.raster_csv,
        legacy_csv=arguments.legacy_csv,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = {
        "manifest": str(manifest_path),
        "manifest_sha256": _sha256_file(manifest_path),
        "curves": [
            {
                "panel": curve["panel"],
                "point_count": curve["point_count"],
                "vector_row_sha256": curve["vector_row_sha256"],
            }
            for curve in manifest["curves"]
        ],
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
