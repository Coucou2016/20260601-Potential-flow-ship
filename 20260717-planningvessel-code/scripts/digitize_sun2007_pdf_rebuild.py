"""Independently digitize Sun (2007) Fig. 2.6 from the source-PDF crops.

The six input PNGs are the deterministic crops in ``pdf_rebuild_v1``.  This
utility fixes its calibration from the labelled axis ticks visible in those
crops, extracts only the blue dashed SIM. pixels, and uses the historical CSV
only after extraction for an audit.  In particular, the historical CSV does
not enter pixel selection, branch selection, or coordinate calibration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = (
    REPOSITORY_ROOT
    / "benchmarks"
    / "sun2007_fig2_6_wedge_similarity"
    / "pdf_rebuild_v1"
)
DEFAULT_OLD_CSV = (
    REPOSITORY_ROOT
    / "benchmarks"
    / "sun2007_fig2_6_wedge_similarity"
    / "fig2_6_zhao_faltinsen_similarity_curves.csv"
)

SOURCE_MANIFEST_NAME = "fig2_6_pdf_rebuild_manifest.json"
CURVE_CSV_NAME = "fig2_6_pdf_rebuild_similarity_curves.csv"
AUDIT_CSV_NAME = "fig2_6_pdf_rebuild_old_csv_audit.csv"
DIGITIZATION_MANIFEST_NAME = "fig2_6_pdf_rebuild_digitization_manifest.json"
AXIS_CALIBRATION_PERTURBATION_PX = 2.0
FREE_SURFACE_BACKTRACK_TOLERANCE_PX = 1.0

OUTPUT_COLUMNS = (
    "beta_deg",
    "quantity",
    "x_name",
    "x_nondimensional",
    "y_name",
    "y_nondimensional",
    "pixel_x",
    "pixel_y_median",
    "pixel_count_in_column",
    "selected_cluster_pixel_count",
    "cluster_count_in_column",
    "branch_policy",
    "curve_style",
    "source_image",
    "source_image_sha256",
)

AUDIT_COLUMNS = (
    "beta_deg",
    "quantity",
    "new_point_count",
    "old_point_count",
    "new_points_in_common_domain",
    "old_points_in_common_domain",
    "matched_observed_point_count",
    "common_x_min",
    "common_x_max",
    "matching_x_tolerance",
    "normalization_y_span",
    "nrmse",
    "max_abs_difference",
    "x_uncertainty_max_abs",
    "y_uncertainty_max_abs",
    "matching_method",
)


@dataclass
class Tick:
    """A labelled tick centre read directly from a source-PDF crop."""

    pixel: float
    value: float
    figure_label: str


@dataclass
class AxisCalibration:
    """A fixed linear coordinate map defined by labelled figure ticks."""

    name: str
    ticks: tuple[Tick, ...]
    anchor_indices: tuple[int, int]

    def parameters(self, anchor_pixel_shifts: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
        """Return ``value = slope * pixel + intercept`` for the selected ticks."""

        first_index, second_index = self.anchor_indices
        first = self.ticks[first_index]
        second = self.ticks[second_index]
        first_pixel = first.pixel + anchor_pixel_shifts[0]
        second_pixel = second.pixel + anchor_pixel_shifts[1]
        if first_pixel == second_pixel:
            raise ValueError(f"Calibration anchors for {self.name} have the same pixel coordinate")
        slope = (second.value - first.value) / (second_pixel - first_pixel)
        intercept = first.value - slope * first_pixel
        return slope, intercept

    def map(self, pixel: np.ndarray | float) -> np.ndarray:
        slope, intercept = self.parameters()
        return slope * np.asarray(pixel, dtype=float) + intercept

    def manifest_record(self) -> dict[str, Any]:
        slope, intercept = self.parameters()
        tick_pixels = np.asarray([tick.pixel for tick in self.ticks], dtype=float)
        tick_values = np.asarray([tick.value for tick in self.ticks], dtype=float)
        residuals = self.map(tick_pixels) - tick_values
        first_index, second_index = self.anchor_indices
        return {
            "axis_name": self.name,
            "coordinate_definition": "value = slope * crop_pixel + intercept",
            "tick_centres_from_figure": [
                {
                    "crop_pixel": tick.pixel,
                    "axis_value": tick.value,
                    "figure_label": tick.figure_label,
                }
                for tick in self.ticks
            ],
            "selected_anchor_tick_indices": [first_index, second_index],
            "selected_anchor_ticks": [
                {
                    "crop_pixel": self.ticks[index].pixel,
                    "axis_value": self.ticks[index].value,
                    "figure_label": self.ticks[index].figure_label,
                }
                for index in self.anchor_indices
            ],
            "slope": float(slope),
            "intercept": float(intercept),
            "max_abs_residual_at_other_labelled_ticks": float(np.max(np.abs(residuals))),
        }


@dataclass
class CurveSpec:
    panel: str
    beta_deg: float
    quantity: str
    image_name: str
    x_axis: AxisCalibration
    y_axis: AxisCalibration
    plot_roi: tuple[int, int, int, int]
    excluded_rectangles: tuple[tuple[int, int, int, int], ...]

    @property
    def x_name(self) -> str:
        return self.x_axis.name

    @property
    def y_name(self) -> str:
        return self.y_axis.name


def _axis(name: str, ticks: Iterable[tuple[float, float, str]]) -> AxisCalibration:
    tick_values = tuple(Tick(*tick) for tick in ticks)
    if len(tick_values) < 2:
        raise ValueError(f"At least two labelled ticks are needed for {name}")
    # The first and final listed ticks are the two explicit calibration
    # anchors.  Intermediate labelled ticks are retained for traceability and
    # residual checking, but no historical numeric curve is used here.
    return AxisCalibration(name=name, ticks=tick_values, anchor_indices=(0, len(tick_values) - 1))


# These centres are fixed in the cropped-PNG coordinate system.  They were
# read from the black strokes of the labelled axes in the six source-PDF
# crops.  The values and labels are the printed tick labels, not values fitted
# to the pre-existing CSV.
SPECS = (
    CurveSpec(
        panel="beta10_free_surface",
        beta_deg=10.0,
        quantity="free_surface",
        image_name="fig2_6_beta10_free_surface.png",
        x_axis=_axis(
            "y_over_Vt",
            ((125.0, 0.0, "0"), (283.0, 5.0, "5"), (441.0, 10.0, "10"), (599.0, 15.0, "15"), (757.0, 20.0, "20")),
        ),
        y_axis=_axis(
            "z_over_Vt",
            ((489.0, -2.0, "-2"), (372.0, -1.0, "-1"), (256.0, 0.0, "0"), (139.0, 1.0, "1"), (22.0, 2.0, "2")),
        ),
        plot_roi=(125, 22, 757, 489),
        excluded_rectangles=((148, 45, 330, 190),),
    ),
    CurveSpec(
        panel="beta10_pressure",
        beta_deg=10.0,
        quantity="pressure",
        image_name="fig2_6_beta10_pressure.png",
        x_axis=_axis(
            "z_over_Vt",
            ((135.0, -1.0, "-1,0"), (294.0, -0.5, "-0,5"), (452.0, 0.0, "0,0"), (611.0, 0.5, "0,5"), (769.0, 1.0, "1,0")),
        ),
        y_axis=_axis(
            "p_over_half_rho_V2",
            ((73.0, 80.0, "80"), (167.0, 60.0, "60"), (261.0, 40.0, "40"), (355.0, 20.0, "20"), (449.0, 0.0, "0")),
        ),
        plot_roi=(135, 26, 769, 496),
        excluded_rectangles=((172, 98, 356, 244),),
    ),
    CurveSpec(
        panel="beta20_free_surface",
        beta_deg=20.0,
        quantity="free_surface",
        image_name="fig2_6_beta20_free_surface.png",
        x_axis=_axis(
            "y_over_Vt",
            ((146.0, 0.0, "0,0"), (301.0, 2.5, "2,5"), (456.0, 5.0, "5,0"), (611.0, 7.5, "7,5"), (766.0, 10.0, "10,0")),
        ),
        y_axis=_axis(
            "z_over_Vt",
            ((484.0, -5.0, "-5,0"), (370.0, -2.5, "-2,5"), (256.0, 0.0, "0,0"), (142.0, 2.5, "2,5"), (28.0, 5.0, "5,0")),
        ),
        plot_roi=(146, 28, 766, 484),
        excluded_rectangles=((188, 54, 368, 196),),
    ),
    CurveSpec(
        panel="beta20_pressure",
        beta_deg=20.0,
        quantity="pressure",
        image_name="fig2_6_beta20_pressure.png",
        x_axis=_axis(
            "z_over_Vt",
            ((141.5, -1.0, "-1,0"), (297.5, -0.5, "-0,5"), (453.5, 0.0, "0,0"), (609.5, 0.5, "0,5"), (765.5, 1.0, "1,0")),
        ),
        y_axis=_axis(
            "p_over_half_rho_V2",
            ((22.0, 20.0, "20"), (137.0, 15.0, "15"), (253.0, 10.0, "10"), (368.0, 5.0, "5"), (483.0, 0.0, "0")),
        ),
        plot_roi=(141, 22, 766, 483),
        excluded_rectangles=((206, 54, 387, 198),),
    ),
    CurveSpec(
        panel="beta30_free_surface",
        beta_deg=30.0,
        quantity="free_surface",
        image_name="fig2_6_beta30_free_surface.png",
        x_axis=_axis(
            "y_over_Vt",
            ((126.0, 0.0, "0"), (339.0, 2.0, "2"), (552.0, 4.0, "4"), (764.0, 6.0, "6")),
        ),
        y_axis=_axis(
            "z_over_Vt",
            ((503.0, -3.0, "-3"), (423.0, -2.0, "-2"), (344.0, -1.0, "-1"), (264.0, 0.0, "0"), (185.0, 1.0, "1"), (105.0, 2.0, "2"), (26.0, 3.0, "3")),
        ),
        plot_roi=(126, 26, 764, 503),
        excluded_rectangles=((193, 54, 377, 203),),
    ),
    CurveSpec(
        panel="beta30_pressure",
        beta_deg=30.0,
        quantity="pressure",
        image_name="fig2_6_beta30_pressure.png",
        x_axis=_axis(
            "z_over_Vt",
            ((127.0, -1.0, "-1,0"), (284.5, -0.5, "-0,5"), (442.0, 0.0, "0,0"), (600.0, 0.5, "0,5"), (758.0, 1.0, "1,0")),
        ),
        y_axis=_axis(
            "p_over_half_rho_V2",
            ((26.0, 8.0, "8"), (142.0, 6.0, "6"), (259.0, 4.0, "4"), (376.0, 2.0, "2"), (492.0, 0.0, "0")),
        ),
        plot_roi=(127, 26, 758, 492),
        excluded_rectangles=((187, 38, 369, 184),),
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_rectangle(
    rectangle: tuple[int, int, int, int], image_size: tuple[int, int], *, name: str
) -> None:
    left, upper, right, lower = rectangle
    width, height = image_size
    if not (0 <= left <= right < width and 0 <= upper <= lower < height):
        raise ValueError(
            f"{name}={rectangle} is outside source image dimensions {width}x{height}"
        )


def _load_source_manifest(source_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate the six fixed input images against their supplied manifest."""

    manifest_path = source_dir / SOURCE_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    try:
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid source manifest {manifest_path}: {error}") from error

    outputs = source_manifest.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError(f"Source manifest {manifest_path} has no outputs list")
    by_filename: dict[str, dict[str, Any]] = {}
    for record in outputs:
        if not isinstance(record, dict) or not isinstance(record.get("filename"), str):
            raise ValueError(f"Source manifest {manifest_path} has an invalid output record")
        filename = record["filename"]
        if filename in by_filename:
            raise ValueError(f"Source manifest {manifest_path} repeats {filename!r}")
        by_filename[filename] = record

    expected_names = {spec.image_name for spec in SPECS}
    if set(by_filename) != expected_names:
        missing = sorted(expected_names - set(by_filename))
        unexpected = sorted(set(by_filename) - expected_names)
        raise ValueError(
            f"Source manifest must describe exactly the six Fig. 2.6 panels; "
            f"missing={missing}, unexpected={unexpected}"
        )

    source_records: list[dict[str, Any]] = []
    for spec in SPECS:
        record = by_filename[spec.image_name]
        if record.get("panel") != spec.panel:
            raise ValueError(
                f"Source manifest panel for {spec.image_name} is {record.get('panel')!r}, "
                f"expected {spec.panel!r}"
            )
        expected_hash = record.get("sha256")
        expected_size = record.get("size_px")
        if not isinstance(expected_hash, str) or not isinstance(expected_size, list) or len(expected_size) != 2:
            raise ValueError(f"Source manifest record for {spec.image_name} lacks sha256 or size_px")

        image_path = source_dir / spec.image_name
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        actual_hash = _sha256(image_path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"Source image hash mismatch for {image_path}: {actual_hash} != {expected_hash}"
            )
        with Image.open(image_path) as image:
            actual_size = list(image.size)
        if actual_size != expected_size:
            raise ValueError(
                f"Source image size mismatch for {image_path}: {actual_size} != {expected_size}"
            )
        source_records.append(
            {
                "panel": spec.panel,
                "filename": spec.image_name,
                "sha256": actual_hash,
                "size_px": actual_size,
                "verified_against_source_manifest": True,
            }
        )
    return source_manifest, source_records


def _blue_pixel_mask(rgb: np.ndarray) -> np.ndarray:
    """Select anti-aliased blue dashed pixels without using curve coordinates."""

    red, green, blue = np.moveaxis(np.asarray(rgb, dtype=np.int16), -1, 0)
    return (blue >= 115) & ((blue - red) >= 25) & ((blue - green) >= 12)


def _contiguous_pixel_runs(pixel_rows: np.ndarray) -> list[np.ndarray]:
    rows = np.unique(np.asarray(pixel_rows, dtype=int))
    if rows.size == 0:
        return []
    return list(np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1))


def _select_lower_outer_free_surface_clusters(
    pixel_x: np.ndarray,
    pixel_y: np.ndarray,
    *,
    backtrack_tolerance_px: float = FREE_SURFACE_BACKTRACK_TOLERANCE_PX,
) -> dict[int, tuple[float, int, int]]:
    """Retain only observed lower outer free-surface branch pixels.

    Image rows increase downward.  The outer, decaying free-surface branch is
    therefore the bottommost pixel cluster after the spray-root fold.  A
    dashed gap can expose only an upper spray pixel; it is skipped rather than
    used to bridge or interpolate the outer branch.
    """

    selected: dict[int, tuple[float, int, int]] = {}
    running_lower_row: float | None = None
    for x_value in np.unique(pixel_x):
        column_rows = pixel_y[pixel_x == x_value]
        clusters = _contiguous_pixel_runs(column_rows)
        if not clusters:
            continue
        lower_cluster = max(clusters, key=lambda values: float(np.median(values)))
        representative = float(np.median(lower_cluster))
        if (
            running_lower_row is not None
            and representative < running_lower_row - backtrack_tolerance_px
        ):
            # This is an observed upper-only spray dash, not an unobserved
            # outer-branch point.  Do not invent a point for the gap.
            continue
        selected[int(x_value)] = (representative, int(lower_cluster.size), len(clusters))
        running_lower_row = (
            representative
            if running_lower_row is None
            else max(running_lower_row, representative)
        )
    return selected


def _masked_blue_pixels(spec: CurveSpec, image_path: Path) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(image_path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    mask = _blue_pixel_mask(rgb)
    _require_rectangle(spec.plot_roi, (rgb.shape[1], rgb.shape[0]), name=f"plot_roi for {spec.panel}")
    left, upper, right, lower = spec.plot_roi
    roi_mask = np.zeros(mask.shape, dtype=bool)
    roi_mask[upper : lower + 1, left : right + 1] = True
    mask &= roi_mask
    for rectangle in spec.excluded_rectangles:
        _require_rectangle(
            rectangle,
            (rgb.shape[1], rgb.shape[0]),
            name=f"excluded rectangle for {spec.panel}",
        )
        x0, y0, x1, y1 = rectangle
        mask[y0 : y1 + 1, x0 : x1 + 1] = False
    pixel_y, pixel_x = np.where(mask)
    if pixel_x.size < 20:
        raise RuntimeError(
            f"Too few blue data pixels in {image_path} after applying the fixed ROI and legend exclusion: "
            f"{pixel_x.size}"
        )
    return pixel_x, pixel_y


def _extract_curve(
    spec: CurveSpec,
    source_dir: Path,
    source_sha256: str,
) -> list[dict[str, Any]]:
    pixel_x, pixel_y = _masked_blue_pixels(spec, source_dir / spec.image_name)
    if spec.quantity == "free_surface":
        selected_columns = _select_lower_outer_free_surface_clusters(pixel_x, pixel_y)
        branch_policy = "bottommost_contiguous_cluster_monotone_outer_branch"
    else:
        selected_columns = {
            int(x_value): (
                float(np.median(pixel_y[pixel_x == x_value])),
                int(np.count_nonzero(pixel_x == x_value)),
                len(_contiguous_pixel_runs(pixel_y[pixel_x == x_value])),
            )
            for x_value in np.unique(pixel_x)
        }
        branch_policy = "blue_pixel_column_median"

    rows: list[dict[str, Any]] = []
    for x_value, (y_value, selected_count, cluster_count) in selected_columns.items():
        all_column_pixels = int(np.count_nonzero(pixel_x == x_value))
        rows.append(
            {
                "beta_deg": spec.beta_deg,
                "quantity": spec.quantity,
                "x_name": spec.x_name,
                "x_nondimensional": float(spec.x_axis.map(float(x_value))),
                "y_name": spec.y_name,
                "y_nondimensional": float(spec.y_axis.map(y_value)),
                "pixel_x": int(x_value),
                "pixel_y_median": float(y_value),
                "pixel_count_in_column": all_column_pixels,
                "selected_cluster_pixel_count": selected_count,
                "cluster_count_in_column": cluster_count,
                "branch_policy": branch_policy,
                "curve_style": "blue_dashed_SIM_from_source_pdf_crop",
                "source_image": spec.image_name,
                "source_image_sha256": source_sha256,
            }
        )
    if not rows:
        raise RuntimeError(f"No curve columns were selected from {source_dir / spec.image_name}")
    return rows


def _read_old_csv(old_csv: Path) -> dict[tuple[float, str], list[dict[str, Any]]]:
    """Read the old artifact only for a post-digitization difference audit."""

    if not old_csv.is_file():
        raise FileNotFoundError(old_csv)
    with old_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"beta_deg", "quantity", "x_nondimensional", "y_nondimensional"} - set(
            reader.fieldnames or ()
        )
        if missing:
            raise ValueError(f"Old CSV {old_csv} is missing required columns: {sorted(missing)}")
        grouped: dict[tuple[float, str], list[dict[str, Any]]] = {}
        for raw_row in reader:
            try:
                beta_deg = float(raw_row["beta_deg"])
                quantity = str(raw_row["quantity"])
                x_value = float(raw_row["x_nondimensional"])
                y_value = float(raw_row["y_nondimensional"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Old CSV {old_csv} contains a non-numeric curve row") from error
            if not all(math.isfinite(value) for value in (beta_deg, x_value, y_value)):
                raise ValueError(f"Old CSV {old_csv} contains non-finite curve coordinates")
            grouped.setdefault((beta_deg, quantity), []).append(
                {"x_nondimensional": x_value, "y_nondimensional": y_value}
            )
    expected_keys = {(spec.beta_deg, spec.quantity) for spec in SPECS}
    if set(grouped) != expected_keys:
        missing = sorted(expected_keys - set(grouped))
        unexpected = sorted(set(grouped) - expected_keys)
        raise ValueError(
            f"Old CSV must contain exactly the six Fig. 2.6 curves; missing={missing}, "
            f"unexpected={unexpected}"
        )
    return grouped


def _curve_arrays(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    x_values = np.asarray([float(row["x_nondimensional"]) for row in rows], dtype=float)
    y_values = np.asarray([float(row["y_nondimensional"]) for row in rows], dtype=float)
    order = np.argsort(x_values, kind="stable")
    return x_values[order], y_values[order]


def _nominal_x_spacing(x_values: np.ndarray) -> float:
    positive_steps = np.diff(np.unique(np.sort(x_values)))
    positive_steps = positive_steps[positive_steps > 0.0]
    if positive_steps.size == 0:
        raise ValueError("At least two distinct x coordinates are required for the audit")
    return float(np.median(positive_steps))


def _match_observed_x_points(
    new_x: np.ndarray,
    old_x: np.ndarray,
) -> tuple[list[tuple[int, int]], float, np.ndarray, np.ndarray]:
    """One-to-one nearest matching of observed points, with no interpolation."""

    common_min = max(float(np.min(new_x)), float(np.min(old_x)))
    common_max = min(float(np.max(new_x)), float(np.max(old_x)))
    if common_min > common_max:
        raise ValueError("New and old curves have no common x domain")
    new_indices = np.flatnonzero((new_x >= common_min) & (new_x <= common_max))
    old_indices = np.flatnonzero((old_x >= common_min) & (old_x <= common_max))
    if new_indices.size == 0 or old_indices.size == 0:
        raise ValueError("New and old curves have no observed points in their common x domain")

    # The tolerance is based only on the observed x sampling density.  It
    # permits a coarser raster's neighbouring pixel centre to match, while
    # keeping each old point paired at most once.  It never fills dashed gaps.
    tolerance = 1.5 * max(
        _nominal_x_spacing(new_x[new_indices]),
        _nominal_x_spacing(old_x[old_indices]),
    )
    chosen_for_old: dict[int, tuple[float, int]] = {}
    old_x_common = old_x[old_indices]
    for new_index in new_indices:
        insertion = int(np.searchsorted(old_x_common, new_x[new_index], side="left"))
        candidate_positions = [position for position in (insertion - 1, insertion) if 0 <= position < old_indices.size]
        if not candidate_positions:
            continue
        position = min(
            candidate_positions,
            key=lambda candidate: (abs(float(old_x_common[candidate] - new_x[new_index])), candidate),
        )
        old_index = int(old_indices[position])
        distance = abs(float(old_x[old_index] - new_x[new_index]))
        if distance > tolerance:
            continue
        previous = chosen_for_old.get(old_index)
        if previous is None or (distance, int(new_index)) < previous:
            chosen_for_old[old_index] = (distance, int(new_index))
    pairs = sorted(
        ((new_index, old_index) for old_index, (_, new_index) in chosen_for_old.items()),
        key=lambda pair: pair[0],
    )
    if len(pairs) < 2:
        raise ValueError("Fewer than two observed point pairs are available for the audit")
    return pairs, float(tolerance), new_indices, old_indices


def _axis_sensitivity(axis: AxisCalibration, pixels: np.ndarray) -> dict[str, Any]:
    nominal = axis.map(pixels)
    maxima: list[float] = []
    rms_values: list[float] = []
    variants: list[dict[str, Any]] = []
    for first_shift, second_shift in product(
        (-AXIS_CALIBRATION_PERTURBATION_PX, AXIS_CALIBRATION_PERTURBATION_PX),
        repeat=2,
    ):
        slope, intercept = axis.parameters((first_shift, second_shift))
        change = slope * pixels + intercept - nominal
        maxima.append(float(np.max(np.abs(change))))
        rms_values.append(float(np.sqrt(np.mean(np.square(change)))))
        variants.append(
            {
                "anchor_pixel_shifts": [first_shift, second_shift],
                "max_abs_coordinate_change": maxima[-1],
                "rms_coordinate_change": rms_values[-1],
            }
        )
    return {
        "axis_name": axis.name,
        "anchor_uncertainty_px": AXIS_CALIBRATION_PERTURBATION_PX,
        "anchor_perturbation_variants": variants,
        "max_abs_coordinate_change_over_variants": max(maxima),
        "max_rms_coordinate_change_over_variants": max(rms_values),
    }


def _curve_sensitivity(spec: CurveSpec, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "method": (
            "Hold the observed selected blue pixels fixed; perturb each of the two "
            "labelled axis-anchor centres independently by plus or minus 2 crop pixels. "
            "No pixel selection, branch selection, or gap interpolation is changed."
        ),
        "x_axis": _axis_sensitivity(
            spec.x_axis,
            np.asarray([float(row["pixel_x"]) for row in rows], dtype=float),
        ),
        "y_axis": _axis_sensitivity(
            spec.y_axis,
            np.asarray([float(row["pixel_y_median"]) for row in rows], dtype=float),
        ),
    }


def _audit_curves(
    new_by_key: dict[tuple[float, str], list[dict[str, Any]]],
    old_by_key: dict[tuple[float, str], list[dict[str, Any]]],
    sensitivity_by_key: dict[tuple[float, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for spec in SPECS:
        key = (spec.beta_deg, spec.quantity)
        new_rows = new_by_key[key]
        old_rows = old_by_key[key]
        new_x, new_y = _curve_arrays(new_rows)
        old_x, old_y = _curve_arrays(old_rows)
        pairs, tolerance, new_indices, old_indices = _match_observed_x_points(new_x, old_x)
        pair_new_indices = np.asarray([pair[0] for pair in pairs], dtype=int)
        pair_old_indices = np.asarray([pair[1] for pair in pairs], dtype=int)
        differences = new_y[pair_new_indices] - old_y[pair_old_indices]
        normalization_y_span = float(np.ptp(old_y[pair_old_indices]))
        if normalization_y_span <= 0.0:
            raise ValueError(f"Old {key} curve has zero y span at its matched observed points")
        sensitivity = sensitivity_by_key[key]
        audit_rows.append(
            {
                "beta_deg": spec.beta_deg,
                "quantity": spec.quantity,
                "new_point_count": len(new_rows),
                "old_point_count": len(old_rows),
                "new_points_in_common_domain": int(new_indices.size),
                "old_points_in_common_domain": int(old_indices.size),
                "matched_observed_point_count": len(pairs),
                "common_x_min": max(float(np.min(new_x)), float(np.min(old_x))),
                "common_x_max": min(float(np.max(new_x)), float(np.max(old_x))),
                "matching_x_tolerance": tolerance,
                "normalization_y_span": normalization_y_span,
                "nrmse": float(np.sqrt(np.mean(np.square(differences))) / normalization_y_span),
                "max_abs_difference": float(np.max(np.abs(differences))),
                "x_uncertainty_max_abs": sensitivity["x_axis"][
                    "max_abs_coordinate_change_over_variants"
                ],
                "y_uncertainty_max_abs": sensitivity["y_axis"][
                    "max_abs_coordinate_change_over_variants"
                ],
                "matching_method": (
                    "one_to_one_nearest_observed_x_no_interpolation_across_dashed_gaps"
                ),
            }
        )
    return audit_rows


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def digitize_pdf_rebuild(
    source_dir: Path | str,
    old_csv: Path | str,
    out_dir: Path | str,
) -> dict[str, Path]:
    """Digitize the six supplied PDF crops and write independent audit artifacts.

    The old CSV is intentionally read only after all image-derived rows and
    coordinate sensitivities have been computed.  It is not a fitting target.
    """

    source = Path(source_dir)
    old = Path(old_csv)
    out = Path(out_dir)

    source_manifest, source_records = _load_source_manifest(source)
    source_hash_by_filename = {record["filename"]: record["sha256"] for record in source_records}

    all_rows: list[dict[str, Any]] = []
    new_by_key: dict[tuple[float, str], list[dict[str, Any]]] = {}
    sensitivity_by_key: dict[tuple[float, str], dict[str, Any]] = {}
    for spec in SPECS:
        rows = _extract_curve(spec, source, source_hash_by_filename[spec.image_name])
        key = (spec.beta_deg, spec.quantity)
        new_by_key[key] = rows
        sensitivity_by_key[key] = _curve_sensitivity(spec, rows)
        all_rows.extend(rows)

    # The old artifact enters only here, after pixels, branches, calibrations,
    # and uncertainty calculations are already fixed.
    old_by_key = _read_old_csv(old)
    audit_rows = _audit_curves(new_by_key, old_by_key, sensitivity_by_key)

    out.mkdir(parents=True, exist_ok=True)
    curve_csv_path = out / CURVE_CSV_NAME
    audit_csv_path = out / AUDIT_CSV_NAME
    manifest_path = out / DIGITIZATION_MANIFEST_NAME
    _write_csv(curve_csv_path, OUTPUT_COLUMNS, all_rows)
    _write_csv(audit_csv_path, AUDIT_COLUMNS, audit_rows)

    source_manifest_path = source / SOURCE_MANIFEST_NAME
    curve_records = []
    for spec in SPECS:
        key = (spec.beta_deg, spec.quantity)
        source_record = next(record for record in source_records if record["filename"] == spec.image_name)
        curve_records.append(
            {
                "panel": spec.panel,
                "beta_deg": spec.beta_deg,
                "quantity": spec.quantity,
                "source_image": source_record,
                "point_count": len(new_by_key[key]),
                "plot_roi": list(spec.plot_roi),
                "excluded_rectangles": [list(rectangle) for rectangle in spec.excluded_rectangles],
                "calibration": {
                    "axis_value_source": "labelled tick centres visible in this source-PDF crop",
                    "x_axis": spec.x_axis.manifest_record(),
                    "y_axis": spec.y_axis.manifest_record(),
                },
                "uncertainty_sensitivity": sensitivity_by_key[key],
            }
        )

    manifest = {
        "artifact": "Sun 2007 Fig. 2.6 independent digitization from source-PDF panel crops",
        "scope": (
            "Blue dashed SIM. curves are re-digitized from the six supplied source-PDF PNG crops. "
            "The historical CSV is retained solely for a post-digitization difference audit."
        ),
        "source_input": {
            "source_directory_name": source.name,
            "crop_manifest_filename": SOURCE_MANIFEST_NAME,
            "crop_manifest_sha256": _sha256(source_manifest_path),
            "source_pdf_sha256_as_recorded_by_crop_manifest": source_manifest.get("source_pdf", {}).get("sha256"),
            "images": source_records,
        },
        "pixel_coordinate_convention": (
            "PNG crop coordinates use an upper-left origin; x increases rightward and y increases downward. "
            "ROIs and exclusions are inclusive [left, upper, right, lower] pixel rectangles."
        ),
        "blue_pixel_selection": {
            "rule": "blue >= 115 and blue-red >= 25 and blue-green >= 12",
            "legend_handling": "fixed panel-specific legend rectangles are excluded",
        },
        "free_surface_branch_policy": {
            "rule": "bottommost contiguous cluster with 1 px monotonic-backtrack tolerance",
            "meaning": "lower outward-decaying branch after the spray-root fold",
            "gap_handling": "upper-only dashed-gap columns are omitted; no curve points are interpolated",
        },
        "reference_data_participates_in_solution": False,
        "reference_curve_used_for_digitization": False,
        "reference_curve_used_for_solution": False,
        "response_calibration_used": False,
        "old_csv_used_for_calibration": False,
        "old_csv_used_for_pixel_selection": False,
        "old_csv_used_for_branch_selection": False,
        "old_csv_role": "post_digitization_audit_only",
        "axis_calibration_uncertainty_px": AXIS_CALIBRATION_PERTURBATION_PX,
        "curves": curve_records,
        "curve_csv": {
            "filename": curve_csv_path.name,
            "sha256": _sha256(curve_csv_path),
            "row_count": len(all_rows),
        },
        "old_csv_audit": {
            "old_csv_filename": old.name,
            "old_csv_sha256": _sha256(old),
            "audit_filename": audit_csv_path.name,
            "audit_sha256": _sha256(audit_csv_path),
            "matching_policy": (
                "Within the overlapping x domain, pair only one-to-one nearest observed x locations; "
                "the audit does not interpolate a curve across dashed gaps."
            ),
            "rows": audit_rows,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "curve_csv": curve_csv_path,
        "audit_csv": audit_csv_path,
        "manifest": manifest_path,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently digitize Sun 2007 Fig. 2.6 source-PDF panel crops."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing the six PNG crops and their supplied manifest.",
    )
    parser.add_argument(
        "--old-csv",
        type=Path,
        default=DEFAULT_OLD_CSV,
        help="Historical CSV used only for post-digitization auditing.",
    )
    parser.add_argument("--out", type=Path, required=True, help="Directory for the three generated artifacts.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    outputs = digitize_pdf_rebuild(args.source_dir, args.old_csv, args.out)
    print(
        json.dumps(
            {name: str(path) for name, path in outputs.items()},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
