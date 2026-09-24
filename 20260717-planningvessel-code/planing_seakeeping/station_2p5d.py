from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import json
import math
from typing import Any

import numpy as np
import yaml

from .section_bem import (
    PDSTRIP_STYLE_STATUS,
    SECTION_BEM_STATUS,
    SectionOffsets,
    hard_chine_v_offsets,
    section_bem_multimode_radiation_diagnostics,
    section_bem_pressure_transfer_diagnostics,
    solve_pressure_transfer,
    solve_heave_radiation,
    solve_heave_radiation_pdstrip_style,
    solve_wave_excitation,
    wigley_section_offsets,
)


STATION_2P5D_STATUS = "frequency_forward_speed_prototype_not_validated"
STATION_2P5D_VALIDATED = False
STRIP_2P5D_FORWARD_STATUS = "experimental_pdstrip_like_forward_speed_assembly_not_validated"
STRIP_2P5D_PDSTRIP_STEP_STATUS = "experimental_pdstrip_step_forward_speed_assembly_not_validated"
PDSTRIP_EXTERNAL_SECTIONS_STATUS = "external_pdstrip_section_radiation_zero_speed_assembly_not_validated"
PDSTRIP_EXTERNAL_FORWARD_STATUS = "external_pdstrip_section_forward_speed_assembly_not_validated"
PDSTRIP_EXTERNAL_PDSTRIP_STEP_STATUS = "external_pdstrip_section_pdstrip_step_forward_speed_assembly_not_validated"
HYBRID_FORWARD_COUPLING_STATUS = "diagnostic_prototype_diagonal_forward_coupling_not_validated"
HYBRID_PRESSURE_DAMPING_COUPLING_STATUS = (
    "diagnostic_prototype_diagonal_forward_added_pressure_damping_coupling_not_validated"
)
PRESSURE_TRANSFER_FORWARD_STATUS = "experimental_pressure_transfer_forward_speed_diagnostic_not_validated"
PRESSURE_TRANSFER_GRADIENT_STATUS = "experimental_pressure_transfer_gradient_end_term_diagnostic_not_validated"
PRESSURE_TRANSFER_FORWARD_ASSEMBLY_STATUS = "experimental_pressure_transfer_forward_speed_assembly_not_validated"
PRESSURE_TRANSFER_PDSTRIP_STEP_ASSEMBLY_STATUS = (
    "experimental_pressure_transfer_pdstrip_step_forward_speed_assembly_not_validated"
)
PRESSURE_TRANSFER_PDSTRIP_DAMPING_FORWARD_ASSEMBLY_STATUS = (
    "diagnostic_pressure_transfer_added_pdstrip_style_damping_forward_speed_assembly_not_validated"
)
PRESSURE_TRANSFER_PDSTRIP_DAMPING_PDSTRIP_STEP_ASSEMBLY_STATUS = (
    "diagnostic_pressure_transfer_added_pdstrip_style_damping_pdstrip_step_forward_speed_assembly_not_validated"
)
DOF_LABELS = ("surge", "sway", "heave", "roll", "pitch", "yaw")
LONGITUDINAL_DOF_INDICES = (2, 4)


@dataclass(frozen=True)
class HardChineStation:
    """Station section at one longitudinal station.

    x_m is measured forward from the transom. The strip assembly converts this
    to the package's longitudinal convention, x positive aft from CG. A station
    can be described either by beam/draft/deadrise or by explicit wetted offsets.
    """

    x_m: float
    beam_m: float
    draft_m: float
    deadrise_deg: float
    waterplane_beam_override_m: float | None = None
    submerged_area_override_m2: float | None = None
    centroid_z_override_m: float | None = None
    offset_points_m: tuple[tuple[float, float], ...] | None = None

    def section_offsets(self) -> SectionOffsets | None:
        if self.offset_points_m is None:
            return None
        points = np.asarray(self.offset_points_m, dtype=float)
        return SectionOffsets(y_m=points[:, 0], z_down_m=points[:, 1])

    def effective_draft_m(self) -> float:
        offsets = self.section_offsets()
        if offsets is not None:
            return offsets.draft_m
        return self.draft_m

    def _offset_area_centroid(self) -> tuple[float, float]:
        offsets = self.section_offsets()
        if offsets is None:
            return 0.0, 0.0
        y = offsets.y_m
        z = offsets.z_down_m
        y_next = np.roll(y, -1)
        z_next = np.roll(z, -1)
        cross = y * z_next - y_next * z
        signed_area = 0.5 * float(np.sum(cross))
        if abs(signed_area) <= 1e-12:
            raise ValueError("Station offsets define a near-zero submerged section area.")
        centroid_z = float(np.sum((z + z_next) * cross) / (6.0 * signed_area))
        return abs(signed_area), max(centroid_z, 0.0)

    def waterline_half_breadth_m(self) -> float:
        if self.waterplane_beam_override_m is not None:
            return 0.5 * max(float(self.waterplane_beam_override_m), 0.0)
        offsets = self.section_offsets()
        if offsets is not None:
            return 0.5 * offsets.beam_m
        beta = math.radians(max(self.deadrise_deg, 1e-6))
        return float(min(0.5 * self.beam_m, self.draft_m / math.tan(beta)))

    def waterplane_beam_m(self) -> float:
        return 2.0 * self.waterline_half_breadth_m()

    def submerged_area_m2(self) -> float:
        if self.submerged_area_override_m2 is not None:
            return max(float(self.submerged_area_override_m2), 0.0)
        if self.offset_points_m is not None:
            area, _ = self._offset_area_centroid()
            return area
        return self.waterline_half_breadth_m() * self.draft_m

    def centroid_z_below_waterline_m(self) -> float:
        if self.centroid_z_override_m is not None:
            return max(float(self.centroid_z_override_m), 0.0)
        if self.offset_points_m is not None:
            _, centroid_z = self._offset_area_centroid()
            return centroid_z
        return self.draft_m / 3.0


@dataclass(frozen=True)
class SectionHydrostatics:
    displacement_volume_m3: float
    waterplane_area_m2: float
    center_of_buoyancy_x_m: float
    center_of_buoyancy_z_below_waterline_m: float
    waterplane_second_moment_roll_m4: float
    waterplane_second_moment_pitch_m4: float


@dataclass(frozen=True)
class StationMatrices:
    added_mass: np.ndarray
    damping: np.ndarray
    restoring: np.ndarray
    hydrostatics: SectionHydrostatics
    status: str = STATION_2P5D_STATUS


@dataclass(frozen=True)
class Station6DOFMatrices:
    added_mass: np.ndarray
    damping: np.ndarray
    restoring: np.ndarray
    hydrostatics: SectionHydrostatics
    dof_labels: tuple[str, ...] = DOF_LABELS
    status: str = STATION_2P5D_STATUS

    def longitudinal_matrices(self) -> StationMatrices:
        idx = np.ix_(LONGITUDINAL_DOF_INDICES, LONGITUDINAL_DOF_INDICES)
        return StationMatrices(
            added_mass=self.added_mass[idx],
            damping=self.damping[idx],
            restoring=self.restoring[idx],
            hydrostatics=self.hydrostatics,
            status=self.status,
        )


@dataclass(frozen=True)
class RigidBody6DOF:
    mass_kg: float
    roll_inertia_kg_m2: float
    pitch_inertia_kg_m2: float
    yaw_inertia_kg_m2: float

    @classmethod
    def from_radii(
        cls,
        mass_kg: float,
        roll_radius_gyration_m: float,
        pitch_radius_gyration_m: float,
        yaw_radius_gyration_m: float,
    ) -> "RigidBody6DOF":
        return cls(
            mass_kg=float(mass_kg),
            roll_inertia_kg_m2=float(mass_kg) * float(roll_radius_gyration_m) ** 2,
            pitch_inertia_kg_m2=float(mass_kg) * float(pitch_radius_gyration_m) ** 2,
            yaw_inertia_kg_m2=float(mass_kg) * float(yaw_radius_gyration_m) ** 2,
        )

    def matrix(self) -> np.ndarray:
        return np.diag(
            [
                self.mass_kg,
                self.mass_kg,
                self.mass_kg,
                self.roll_inertia_kg_m2,
                self.pitch_inertia_kg_m2,
                self.yaw_inertia_kg_m2,
            ]
        )


@dataclass(frozen=True)
class StationHull:
    length_m: float
    stations: tuple[HardChineStation, ...]
    lcg_from_transom_m: float | None = None

    def __post_init__(self) -> None:
        if self.length_m <= 0.0:
            raise ValueError("StationHull.length_m must be positive.")
        if len(self.stations) < 2:
            raise ValueError("At least two stations are required.")
        stations = tuple(sorted(self.stations, key=lambda item: item.x_m))
        for station in stations:
            if station.beam_m <= 0.0 or station.effective_draft_m() <= 0.0:
                raise ValueError("Station beam and draft must be positive.")
            if station.x_m < -1e-9 or station.x_m > self.length_m + 1e-9:
                raise ValueError("Station x_m must lie between transom and bow.")
        object.__setattr__(self, "stations", stations)

    @property
    def lcg_m(self) -> float:
        return 0.5 * self.length_m if self.lcg_from_transom_m is None else float(self.lcg_from_transom_m)

    def arrays(self) -> dict[str, np.ndarray]:
        return {
            "x": np.asarray([station.x_m for station in self.stations], dtype=float),
            "area": np.asarray([station.submerged_area_m2() for station in self.stations], dtype=float),
            "beam": np.asarray([station.waterplane_beam_m() for station in self.stations], dtype=float),
            "draft": np.asarray([station.effective_draft_m() for station in self.stations], dtype=float),
            "z_cb": np.asarray([station.centroid_z_below_waterline_m() for station in self.stations], dtype=float),
        }

    def hydrostatics(self) -> SectionHydrostatics:
        data = self.arrays()
        x = data["x"]
        area = data["area"]
        beam = data["beam"]
        z_cb = data["z_cb"]
        volume = float(np.trapezoid(area, x))
        if volume <= 0.0:
            raise ValueError("Integrated submerged volume must be positive.")
        waterplane_area = float(np.trapezoid(beam, x))
        xb = float(np.trapezoid(area * x, x) / volume)
        zb = float(np.trapezoid(area * z_cb, x) / volume)
        x_rel = self.lcg_m - x
        i_roll = float(np.trapezoid(beam**3 / 12.0, x))
        i_pitch = float(np.trapezoid(beam * x_rel**2, x))
        return SectionHydrostatics(
            displacement_volume_m3=volume,
            waterplane_area_m2=waterplane_area,
            center_of_buoyancy_x_m=xb,
            center_of_buoyancy_z_below_waterline_m=zb,
            waterplane_second_moment_roll_m4=i_roll,
            waterplane_second_moment_pitch_m4=i_pitch,
        )


def _offset_points_from_mapping(data: dict[str, Any]) -> tuple[tuple[float, float], ...] | None:
    raw = data.get("offsets_m", data.get("offsets"))
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError("Station offsets must be a list with at least three [y_m, z_down_m] points.")
    points: list[tuple[float, float]] = []
    for item in raw:
        if isinstance(item, dict):
            y_value = item.get("y_m")
            z_value = item.get("z_down_m", item.get("z_m"))
            if y_value is None or z_value is None:
                raise ValueError("Offset dictionaries must contain y_m and z_down_m.")
            points.append((float(y_value), float(z_value)))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            points.append((float(item[0]), float(item[1])))
        else:
            raise ValueError("Each station offset must be [y_m, z_down_m] or a mapping with y_m/z_down_m.")
    SectionOffsets(
        y_m=np.asarray([point[0] for point in points], dtype=float),
        z_down_m=np.asarray([point[1] for point in points], dtype=float),
    )
    return tuple(points)


def _offset_default_beam_draft(offset_points: tuple[tuple[float, float], ...] | None) -> tuple[float | None, float | None]:
    if offset_points is None:
        return None, None
    points = np.asarray(offset_points, dtype=float)
    return float(np.max(points[:, 0]) - np.min(points[:, 0])), float(np.max(points[:, 1]))


def _station_from_mapping(data: dict[str, Any]) -> HardChineStation:
    offset_points = _offset_points_from_mapping(data)
    default_beam, default_draft = _offset_default_beam_draft(offset_points)
    beam_value = data.get("beam_m", default_beam)
    draft_value = data.get("draft_m", default_draft)
    if beam_value is None:
        raise ValueError("Station mapping must contain beam_m unless explicit offsets are provided.")
    if draft_value is None:
        raise ValueError("Station mapping must contain draft_m unless explicit offsets are provided.")
    return HardChineStation(
        x_m=float(data["x_m"]),
        beam_m=float(beam_value),
        draft_m=float(draft_value),
        deadrise_deg=float(data.get("deadrise_deg", 90.0)),
        waterplane_beam_override_m=None
        if data.get("waterplane_beam_m") is None
        else float(data["waterplane_beam_m"]),
        submerged_area_override_m2=None
        if data.get("submerged_area_m2") is None
        else float(data["submerged_area_m2"]),
        centroid_z_override_m=None
        if data.get("centroid_z_below_waterline_m") is None
        else float(data["centroid_z_below_waterline_m"]),
        offset_points_m=offset_points,
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return float(text)


def _first_optional_float(rows: list[dict[str, str]], field: str) -> float | None:
    for row in rows:
        if field in row:
            value = _optional_float(row.get(field))
            if value is not None:
                return value
    return None


def load_station_offsets_csv(path: str | Path) -> tuple[HardChineStation, ...]:
    """Load station offsets from a long-form CSV table.

    Required columns are `x_m`, `y_m`, and `z_down_m`. Optional columns include
    `station_id`, `point_order`, `beam_m`, `draft_m`, `deadrise_deg`,
    `waterplane_beam_m`, `submerged_area_m2`, and
    `centroid_z_below_waterline_m`.
    """

    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Station offsets CSV not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Station offsets CSV must have a header row.")
        fields = {field.strip() for field in reader.fieldnames}
        missing = {"x_m", "y_m", "z_down_m"} - fields
        if missing:
            raise ValueError(f"Station offsets CSV is missing required columns: {sorted(missing)}")
        grouped: dict[str, list[dict[str, str]]] = {}
        order: list[str] = []
        for row_index, row in enumerate(reader):
            key = str(row.get("station_id") or row.get("x_m") or "").strip()
            if key == "":
                raise ValueError(f"Station offsets CSV row {row_index + 2} has no station_id or x_m.")
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            row["_row_order"] = str(row_index)
            grouped[key].append(row)

    stations: list[HardChineStation] = []
    for key in order:
        rows = grouped[key]
        rows_sorted = sorted(
            rows,
            key=lambda row: (
                float(row["point_order"]) if row.get("point_order", "").strip() else float(row["_row_order"])
            ),
        )
        points = tuple((float(row["y_m"]), float(row["z_down_m"])) for row in rows_sorted)
        default_beam, default_draft = _offset_default_beam_draft(points)
        beam = _first_optional_float(rows, "beam_m")
        draft = _first_optional_float(rows, "draft_m")
        station = HardChineStation(
            x_m=float(rows[0]["x_m"]),
            beam_m=float(default_beam if beam is None else beam),
            draft_m=float(default_draft if draft is None else draft),
            deadrise_deg=float(_first_optional_float(rows, "deadrise_deg") or 90.0),
            waterplane_beam_override_m=_first_optional_float(rows, "waterplane_beam_m"),
            submerged_area_override_m2=_first_optional_float(rows, "submerged_area_m2"),
            centroid_z_override_m=_first_optional_float(rows, "centroid_z_below_waterline_m"),
            offset_points_m=points,
        )
        stations.append(station)
    return tuple(stations)


def station_hull_from_mapping(data: dict[str, Any], base_dir: Path | None = None) -> StationHull:
    stations: list[HardChineStation] = []
    if data.get("offsets_file") is not None:
        offsets_path = Path(str(data["offsets_file"]))
        if not offsets_path.is_absolute() and base_dir is not None:
            offsets_path = base_dir / offsets_path
        stations.extend(load_station_offsets_csv(offsets_path))
    if "stations" in data and data["stations"] is not None:
        stations.extend(_station_from_mapping(item) for item in data["stations"])
    if not stations:
        raise ValueError("Station hull mapping must contain a stations list or offsets_file.")
    return StationHull(
        length_m=float(data["length_m"]),
        lcg_from_transom_m=None if data.get("lcg_from_transom_m") is None else float(data["lcg_from_transom_m"]),
        stations=tuple(stations),
    )


def load_station_hull(path: str | Path) -> StationHull:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a mapping.")
    return station_hull_from_mapping(data, base_dir=path.parent)


def _offset_signed_area(offsets: SectionOffsets) -> float:
    y = offsets.y_m
    z = offsets.z_down_m
    return 0.5 * float(np.sum(y * np.roll(z, -1) - np.roll(y, -1) * z))


def station_geometry_audit(hull: StationHull) -> list[dict[str, float | str]]:
    """Return station-by-station geometry diagnostics before hydrodynamic use."""

    rows: list[dict[str, float | str]] = []
    previous_x: float | None = None
    for idx, station in enumerate(hull.stations):
        offsets = station.section_offsets()
        waterplane_beam = station.waterplane_beam_m()
        draft = station.effective_draft_m()
        area = station.submerged_area_m2()
        centroid_z = station.centroid_z_below_waterline_m()
        notes: list[str] = []
        status = "PASS"
        if previous_x is not None and station.x_m <= previous_x:
            status = "FAIL"
            notes.append("station x_m is not strictly increasing")
        if waterplane_beam <= 0.0:
            status = "FAIL"
            notes.append("nonpositive waterplane beam")
        if draft <= 0.0:
            status = "FAIL"
            notes.append("nonpositive draft")
        if area <= 0.0:
            status = "FAIL"
            notes.append("nonpositive submerged area")
        if centroid_z < -1e-9 or centroid_z > draft + 1e-9:
            status = "FAIL"
            notes.append("centroid outside section draft")

        offset_point_count = 0
        signed_area: float | str = ""
        waterline_endpoint_z_max_abs: float | str = ""
        orientation = ""
        if offsets is not None:
            offset_point_count = len(offsets.y_m)
            signed_area_value = _offset_signed_area(offsets)
            signed_area = signed_area_value
            orientation = "positive" if signed_area_value > 0.0 else "negative" if signed_area_value < 0.0 else "zero"
            waterline_endpoint_z_max_abs_value = max(abs(float(offsets.z_down_m[0])), abs(float(offsets.z_down_m[-1])))
            waterline_endpoint_z_max_abs = waterline_endpoint_z_max_abs_value
            if offset_point_count < 3:
                status = "FAIL"
                notes.append("fewer than three offset points")
            if abs(signed_area_value) <= 1e-12:
                status = "FAIL"
                notes.append("near-zero signed offset area")
            if waterline_endpoint_z_max_abs_value > 1e-6:
                status = "WARN" if status == "PASS" else status
                notes.append("offset endpoints are not on the calm-water free surface")
        else:
            orientation = "parametric"

        rows.append(
            {
                "station_index": idx,
                "x_m": float(station.x_m),
                "geometry_source": "offsets" if offsets is not None else "parametric",
                "offset_point_count": offset_point_count,
                "waterplane_beam_m": float(waterplane_beam),
                "draft_m": float(draft),
                "submerged_area_m2": float(area),
                "centroid_z_below_waterline_m": float(centroid_z),
                "offset_signed_area_m2": signed_area,
                "offset_orientation": orientation,
                "waterline_endpoint_z_max_abs_m": waterline_endpoint_z_max_abs,
                "status": status,
                "note": "; ".join(notes),
            }
        )
        previous_x = station.x_m
    return rows


def make_wigley_iii_hull(
    length_m: float = 1.0,
    beam_m: float = 0.1,
    draft_m: float = 0.0625,
    station_count: int = 41,
    lcg_from_transom_m: float | None = None,
) -> StationHull:
    """Generate the Journee/Ma Wigley III parabolic station model.

    The section uses
    ``2 y / B = (1 - (z/T)^2) * (1 - xi^2) * (1 + 0.2 xi^2)``,
    where ``xi = 2 x / L - 1`` and ``z`` is measured downward from the still
    waterline.  The final longitudinal factor distinguishes Wigley III from the
    basic Wigley hull and gives the Ma 2005 Table 1 displacement ``0.078 m3``
    for ``L=3 m``, ``B=0.3 m`` and ``T=0.1875 m``. End stations use zero-area
    overrides but retain tiny positive geometric dimensions for validation.
    """

    if station_count < 3:
        raise ValueError("station_count must be at least 3.")
    length = float(length_m)
    beam = float(beam_m)
    draft = float(draft_m)
    eps = 1e-9
    stations = []
    for x in np.linspace(0.0, length, int(station_count)):
        xi = 2.0 * x / length - 1.0
        fx = max(0.0, (1.0 - xi**2) * (1.0 + 0.2 * xi**2))
        waterplane_beam = beam * fx
        area = (2.0 / 3.0) * beam * draft * fx
        stations.append(
            HardChineStation(
                x_m=float(x),
                beam_m=max(waterplane_beam, eps),
                draft_m=max(draft, eps),
                deadrise_deg=90.0,
                waterplane_beam_override_m=waterplane_beam,
                submerged_area_override_m2=area,
                centroid_z_override_m=0.375 * draft,
            )
        )
    return StationHull(
        length_m=length,
        lcg_from_transom_m=0.5 * length if lcg_from_transom_m is None else float(lcg_from_transom_m),
        stations=tuple(stations),
    )


def make_sl7_surrogate_hull(
    length_m: float = 1.0,
    beam_m: float = 0.138,
    draft_m: float = 0.045,
    station_count: int = 41,
    lcg_from_transom_m: float | None = None,
) -> StationHull:
    """Generate a documented SL-7-like surrogate until offsets are digitized."""

    if station_count < 3:
        raise ValueError("station_count must be at least 3.")
    length = float(length_m)
    beam = float(beam_m)
    draft = float(draft_m)
    eps = 1e-9
    stations = []
    for x in np.linspace(0.0, length, int(station_count)):
        s = x / length
        entrance = math.sin(math.pi * s) ** 0.55
        fullness = 0.78 + 0.22 * math.sin(math.pi * s) ** 2
        waterplane_beam = beam * entrance
        local_draft = draft * (0.75 + 0.25 * math.sin(math.pi * s))
        area = fullness * waterplane_beam * local_draft
        stations.append(
            HardChineStation(
                x_m=float(x),
                beam_m=max(waterplane_beam, eps),
                draft_m=max(local_draft, eps),
                deadrise_deg=60.0,
                waterplane_beam_override_m=waterplane_beam,
                submerged_area_override_m2=area,
                centroid_z_override_m=0.45 * local_draft,
            )
        )
    return StationHull(
        length_m=length,
        lcg_from_transom_m=0.5 * length if lcg_from_transom_m is None else float(lcg_from_transom_m),
        stations=tuple(stations),
    )


def assemble_prototype_strip_matrices(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    radiation_damping_ratio: float = 0.08,
    speed_mps: float = 0.0,
) -> StationMatrices:
    """Assemble a heave/pitch strip-matrix prototype.

    This is not a validated boundary-integral 2.5D method. It provides a stable
    station-based API and first-order checks while the real sectional radiation
    and diffraction solver is added and benchmarked against Ma 2005.
    """

    return assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega_rad_s,
        radiation_damping_ratio=radiation_damping_ratio,
        speed_mps=speed_mps,
    ).longitudinal_matrices()


def _radiation_kernels(omega_rad_s: float, length_m: float, gravity_m_s2: float) -> dict[str, float]:
    """Smooth development kernels for frequency-dependent section radiation.

    These kernels move the station API away from constant added mass and
    Rayleigh-style damping while the matched boundary-integral solver is being
    implemented. They are deliberately marked as unvalidated and should not be
    used to claim Ma 2005 acceptance.
    """

    omega_hat = max(float(omega_rad_s) * math.sqrt(float(length_m) / float(gravity_m_s2)), 1e-6)
    heave_added = 0.31 + 0.69 / (1.0 + omega_hat**3)
    heave_damping = 1.55 * (omega_hat / 2.2) * math.exp(max(-40.0, 1.0 - omega_hat / 2.2))
    pitch_added = 0.42 + 1.56 / (1.0 + omega_hat**2)
    pitch_damping = 1.05 * (omega_hat / 2.8) * math.exp(max(-40.0, 1.0 - omega_hat / 2.8))
    coupling_added = 0.95 / (1.0 + omega_hat**2)
    coupling_damping = 0.85 * (omega_hat / 2.8) / (1.0 + (omega_hat / 5.5) ** 2)
    return {
        "omega_hat": omega_hat,
        "heave_added": heave_added,
        "heave_damping": heave_damping,
        "pitch_added": pitch_added,
        "pitch_damping": pitch_damping,
        "coupling_added": coupling_added,
        "coupling_damping": coupling_damping,
    }


def assemble_prototype_6dof_matrices(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    radiation_damping_ratio: float = 0.08,
    surge_added_mass_fraction: float = 0.02,
    speed_mps: float = 0.0,
) -> Station6DOFMatrices:
    """Assemble a 6DOF strip-matrix prototype.

    The matrix layout follows [surge, sway, heave, roll, pitch, yaw]. The
    longitudinal terms include a frequency-dependent development kernel and the
    forward-speed heave/pitch coupling suggested by the 2.5D body condition
    i*omega*N_j + U*m_j. This is still not the boundary-integral solver required
    for final Ma 2005 validation.
    """

    data = hull.arrays()
    x = data["x"]
    beam = data["beam"]
    draft = data["draft"]
    area = data["area"]
    x_rel = hull.lcg_m - x
    hydro = hull.hydrostatics()

    vertical_added_mass = rho_water_kg_m3 * math.pi * (0.5 * beam) ** 2
    lateral_added_mass = rho_water_kg_m3 * math.pi * draft**2
    surge_added_mass = surge_added_mass_fraction * rho_water_kg_m3 * area
    kernels = _radiation_kernels(omega_rad_s, hull.length_m, gravity_m_s2)
    speed_fn_l = max(float(speed_mps), 0.0) / math.sqrt(gravity_m_s2 * hull.length_m)
    radiation_frequency = math.sqrt(gravity_m_s2 / hull.length_m)

    added_mass = np.zeros((6, 6), dtype=float)
    added_mass[0, 0] = float(np.trapezoid(surge_added_mass, x))
    added_mass[1, 1] = float(np.trapezoid(lateral_added_mass, x))
    added_mass[1, 5] = added_mass[5, 1] = float(np.trapezoid(lateral_added_mass * x_rel, x))
    added_mass[5, 5] = float(np.trapezoid(lateral_added_mass * x_rel**2, x))
    vertical_added_mass_inf = vertical_added_mass
    added_mass[2, 2] = float(np.trapezoid(vertical_added_mass_inf * kernels["heave_added"], x))
    added_mass[2, 4] = added_mass[4, 2] = float(np.trapezoid(vertical_added_mass_inf * kernels["heave_added"] * x_rel, x))
    added_mass[4, 4] = float(np.trapezoid(vertical_added_mass_inf * kernels["pitch_added"] * x_rel**2, x))
    added_mass[3, 3] = float(np.trapezoid(vertical_added_mass * (beam**2 + draft**2) / 12.0, x))

    damping = np.zeros((6, 6), dtype=float)
    damping[0, 0] = max(float(omega_rad_s), 0.0) * radiation_damping_ratio * added_mass[0, 0]
    damping[1, 1] = max(float(omega_rad_s), 0.0) * radiation_damping_ratio * added_mass[1, 1]
    damping[1, 5] = damping[5, 1] = max(float(omega_rad_s), 0.0) * radiation_damping_ratio * added_mass[1, 5]
    damping[5, 5] = max(float(omega_rad_s), 0.0) * radiation_damping_ratio * added_mass[5, 5]
    damping[2, 2] = float(np.trapezoid(vertical_added_mass_inf * kernels["heave_damping"] * radiation_frequency, x))
    damping[2, 4] = damping[4, 2] = float(
        np.trapezoid(vertical_added_mass_inf * kernels["heave_damping"] * radiation_frequency * x_rel, x)
    )
    damping[4, 4] = float(
        np.trapezoid(vertical_added_mass_inf * kernels["pitch_damping"] * radiation_frequency * x_rel**2, x)
    )
    damping[3, 3] = max(float(omega_rad_s), 0.0) * radiation_damping_ratio * added_mass[3, 3]

    if speed_fn_l > 0.0:
        total_vertical_mass_inf = float(np.trapezoid(vertical_added_mass_inf, x))
        added_coupling = speed_fn_l * total_vertical_mass_inf * hull.length_m * kernels["coupling_added"]
        damping_coupling = speed_fn_l * total_vertical_mass_inf * radiation_frequency * hull.length_m * kernels[
            "coupling_damping"
        ]
        added_mass[2, 4] -= added_coupling
        added_mass[4, 2] += added_coupling
        damping[2, 4] += damping_coupling
        damping[4, 2] -= damping_coupling

    restoring = np.zeros((6, 6), dtype=float)
    restoring[2, 2] = rho_water_kg_m3 * gravity_m_s2 * hydro.waterplane_area_m2
    restoring[2, 4] = restoring[4, 2] = rho_water_kg_m3 * gravity_m_s2 * float(np.trapezoid(beam * x_rel, x))
    restoring[3, 3] = rho_water_kg_m3 * gravity_m_s2 * hydro.waterplane_second_moment_roll_m4
    restoring[4, 4] = rho_water_kg_m3 * gravity_m_s2 * hydro.waterplane_second_moment_pitch_m4
    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=restoring,
        hydrostatics=hydro,
    )


def _station_offsets_for_bem(station: HardChineStation):
    offsets = station.section_offsets()
    if offsets is not None:
        return offsets
    beam = max(station.waterplane_beam_m(), 1e-8)
    draft = max(station.effective_draft_m(), 1e-8)
    if station.deadrise_deg >= 89.0:
        return wigley_section_offsets(beam, draft)
    return hard_chine_v_offsets(beam, draft)


def section_bem_station_diagnostics(
    hull: StationHull,
    omega_rad_s: float | np.ndarray,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    section_solver: str = "collocation",
) -> list[dict[str, float | str]]:
    """Return station-by-station experimental section-BEM heave diagnostics."""

    solver = section_solver.strip().lower()
    if solver not in {"collocation", "pdstrip_style"}:
        raise ValueError("section_solver must be 'collocation' or 'pdstrip_style'.")
    data = hull.arrays()
    omegas = np.atleast_1d(np.asarray(omega_rad_s, dtype=float))
    rows: list[dict[str, float | str]] = []
    for omega in omegas:
        for idx, station in enumerate(hull.stations):
            beam = float(data["beam"][idx])
            draft = float(data["draft"][idx])
            if beam <= 1e-7 or draft <= 1e-7:
                rows.append(
                    {
                        "station_index": idx,
                        "x_m": float(station.x_m),
                        "omega_rad_s": float(omega),
                        "waterplane_beam_m": beam,
                        "draft_m": draft,
                        "added_mass_per_m": 0.0,
                        "damping_per_m": 0.0,
                        "condition_number": "",
                        "residual_norm": "",
                        "body_panel_count": 0,
                        "free_surface_panel_count": 0,
                        "section_solver": solver,
                        "status": "skipped_tiny_section",
                    }
                )
                continue
            section_offsets = _station_offsets_for_bem(station)
            if solver == "pdstrip_style":
                result = solve_heave_radiation_pdstrip_style(
                    section_offsets,
                    omega_rad_s=float(omega),
                    rho_water_kg_m3=rho_water_kg_m3,
                    gravity_m_s2=gravity_m_s2,
                    free_surface_panel_count_per_side=free_surface_panel_count_per_side,
                    body_panel_count=body_panel_count,
                )
            else:
                result = solve_heave_radiation(
                    section_offsets,
                    omega_rad_s=float(omega),
                    rho_water_kg_m3=rho_water_kg_m3,
                    gravity_m_s2=gravity_m_s2,
                    free_surface_panel_count_per_side=free_surface_panel_count_per_side,
                    body_panel_count=body_panel_count,
                )
            rows.append(
                {
                    "station_index": idx,
                    "x_m": float(station.x_m),
                    "omega_rad_s": float(omega),
                    "waterplane_beam_m": beam,
                    "draft_m": draft,
                    "added_mass_per_m": result.added_mass_per_m,
                    "damping_per_m": result.damping_per_m,
                    "condition_number": result.condition_number,
                    "residual_norm": result.residual_norm,
                    "body_panel_count": result.panel_count,
                    "free_surface_panel_count": result.free_surface_panel_count,
                    "section_solver": solver,
                    "status": result.status,
                }
            )
    return rows


def section_bem_multimode_station_diagnostics(
    hull: StationHull,
    omega_rad_s: float | np.ndarray,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
) -> list[dict[str, float | str]]:
    """Return station-by-station sway/heave/roll section-radiation diagnostics."""

    data = hull.arrays()
    omegas = np.atleast_1d(np.asarray(omega_rad_s, dtype=float))
    rows: list[dict[str, float | str]] = []
    for omega in omegas:
        for idx, station in enumerate(hull.stations):
            beam = float(data["beam"][idx])
            draft = float(data["draft"][idx])
            if beam <= 1e-7 or draft <= 1e-7:
                rows.append(
                    {
                        "station_index": idx,
                        "x_m": float(station.x_m),
                        "omega_rad_s": float(omega),
                        "waterplane_beam_m": beam,
                        "draft_m": draft,
                        "response_mode": "",
                        "excitation_mode": "",
                        "added_mass_per_m": 0.0,
                        "damping_per_m": 0.0,
                        "condition_number": "",
                        "residual_norm": "",
                        "body_panel_count": 0,
                        "free_surface_panel_count": 0,
                        "status": "skipped_tiny_section",
                    }
                )
                continue
            section_rows = section_bem_multimode_radiation_diagnostics(
                _station_offsets_for_bem(station),
                omega_rad_s=float(omega),
                rho_water_kg_m3=rho_water_kg_m3,
                gravity_m_s2=gravity_m_s2,
                free_surface_panel_count_per_side=free_surface_panel_count_per_side,
                body_panel_count=body_panel_count,
            )
            for row in section_rows:
                enriched = {
                    "station_index": idx,
                    "x_m": float(station.x_m),
                    "waterplane_beam_m": beam,
                    "draft_m": draft,
                }
                enriched.update(row)
                rows.append(enriched)
    return rows


def section_bem_excitation_diagnostics(
    hull: StationHull,
    omega_rad_s: float | np.ndarray,
    wave_amplitude_m: float,
    wavenumber_rad_m: float | np.ndarray,
    heading_deg: float = 180.0,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
) -> list[dict[str, float | str]]:
    """Return station-by-station experimental section-BEM wave-excitation diagnostics."""

    data = hull.arrays()
    omegas = np.atleast_1d(np.asarray(omega_rad_s, dtype=float))
    wavenumbers = np.atleast_1d(np.asarray(wavenumber_rad_m, dtype=float))
    if len(wavenumbers) == 1 and len(omegas) > 1:
        wavenumbers = np.full_like(omegas, float(wavenumbers[0]))
    if len(wavenumbers) != len(omegas):
        raise ValueError("wavenumber_rad_m must be scalar or have the same length as omega_rad_s.")
    heading = math.radians(float(heading_deg) - 180.0)
    lateral = math.sin(heading)
    rows: list[dict[str, float | str]] = []
    for omega, wavenumber in zip(omegas, wavenumbers):
        transverse_wavenumber = float(wavenumber) * lateral
        for idx, station in enumerate(hull.stations):
            beam = float(data["beam"][idx])
            draft = float(data["draft"][idx])
            if beam <= 1e-7 or draft <= 1e-7:
                rows.append(
                    {
                        "station_index": idx,
                        "x_m": float(station.x_m),
                        "omega_rad_s": float(omega),
                        "wavenumber_rad_m": float(wavenumber),
                        "transverse_wavenumber_rad_m": transverse_wavenumber,
                        "waterplane_beam_m": beam,
                        "draft_m": draft,
                        "vertical_force_abs_per_m": 0.0,
                        "lateral_force_abs_per_m": 0.0,
                        "roll_moment_abs_per_m": 0.0,
                        "condition_number": "",
                        "residual_norm": "",
                        "body_panel_count": 0,
                        "free_surface_panel_count": 0,
                        "status": "skipped_tiny_section",
                    }
                )
                continue
            result = solve_wave_excitation(
                _station_offsets_for_bem(station),
                omega_rad_s=float(omega),
                wave_amplitude_m=wave_amplitude_m,
                wavenumber_rad_m=float(wavenumber),
                transverse_wavenumber_rad_m=transverse_wavenumber,
                rho_water_kg_m3=rho_water_kg_m3,
                gravity_m_s2=gravity_m_s2,
                free_surface_panel_count_per_side=free_surface_panel_count_per_side,
                body_panel_count=body_panel_count,
            )
            rows.append(
                {
                    "station_index": idx,
                    "x_m": float(station.x_m),
                    "omega_rad_s": float(omega),
                    "wavenumber_rad_m": float(wavenumber),
                    "transverse_wavenumber_rad_m": transverse_wavenumber,
                    "waterplane_beam_m": beam,
                    "draft_m": draft,
                    "vertical_force_abs_per_m": abs(result.complex_vertical_force_per_m),
                    "lateral_force_abs_per_m": abs(result.complex_lateral_force_per_m),
                    "roll_moment_abs_per_m": abs(result.complex_roll_moment_per_m),
                    "condition_number": result.condition_number,
                    "residual_norm": result.residual_norm,
                    "body_panel_count": result.panel_count,
                    "free_surface_panel_count": result.free_surface_panel_count,
                    "status": result.status,
                }
            )
    return rows


def section_bem_pressure_transfer_station_diagnostics(
    hull: StationHull,
    omega_rad_s: float | np.ndarray,
    wave_amplitude_m: float,
    wavenumber_rad_m: float | np.ndarray,
    heading_deg: float = 180.0,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
) -> list[dict[str, float | str]]:
    """Return station-by-station body-panel pressure-transfer diagnostics."""

    data = hull.arrays()
    omegas = np.atleast_1d(np.asarray(omega_rad_s, dtype=float))
    wavenumbers = np.atleast_1d(np.asarray(wavenumber_rad_m, dtype=float))
    if len(wavenumbers) == 1 and len(omegas) > 1:
        wavenumbers = np.full_like(omegas, float(wavenumbers[0]))
    if len(wavenumbers) != len(omegas):
        raise ValueError("wavenumber_rad_m must be scalar or have the same length as omega_rad_s.")
    heading = math.radians(float(heading_deg) - 180.0)
    lateral = math.sin(heading)
    rows: list[dict[str, float | str]] = []
    for omega, wavenumber in zip(omegas, wavenumbers):
        transverse_wavenumber = float(wavenumber) * lateral
        for idx, station in enumerate(hull.stations):
            beam = float(data["beam"][idx])
            draft = float(data["draft"][idx])
            if beam <= 1e-7 or draft <= 1e-7:
                rows.append(
                    {
                        "station_index": idx,
                        "x_m": float(station.x_m),
                        "omega_rad_s": float(omega),
                        "wavenumber_rad_m": float(wavenumber),
                        "transverse_wavenumber_rad_m": transverse_wavenumber,
                        "waterplane_beam_m": beam,
                        "draft_m": draft,
                        "panel_index": "",
                        "pressure_kind": "",
                        "radiation_mode": "",
                        "pressure_abs_pa": 0.0,
                        "condition_number": "",
                        "residual_norm": "",
                        "body_panel_count": 0,
                        "free_surface_panel_count": 0,
                        "status": "skipped_tiny_section",
                    }
                )
                continue
            section_rows = section_bem_pressure_transfer_diagnostics(
                _station_offsets_for_bem(station),
                omega_rad_s=float(omega),
                wave_amplitude_m=wave_amplitude_m,
                wavenumber_rad_m=float(wavenumber),
                transverse_wavenumber_rad_m=transverse_wavenumber,
                rho_water_kg_m3=rho_water_kg_m3,
                gravity_m_s2=gravity_m_s2,
                free_surface_panel_count_per_side=free_surface_panel_count_per_side,
                body_panel_count=body_panel_count,
            )
            for row in section_rows:
                enriched = {
                    "station_index": idx,
                    "x_m": float(station.x_m),
                    "waterplane_beam_m": beam,
                    "draft_m": draft,
                }
                enriched.update(row)
                rows.append(enriched)
    return rows


def _section_heave_pressure_transfer_arrays(
    hull: StationHull,
    omega_rad_s: float,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
    free_surface_panel_count_per_side: int,
    body_panel_count: int | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[dict[str, float | str]]]:
    omega = max(abs(float(omega_rad_s)), 1e-9)
    data = hull.arrays()
    raw_added = np.zeros_like(data["x"], dtype=float)
    raw_damping = np.zeros_like(data["x"], dtype=float)
    clipped_added = np.zeros_like(data["x"], dtype=float)
    clipped_damping = np.zeros_like(data["x"], dtype=float)
    diagnostics: list[dict[str, float | str]] = []
    for idx, station in enumerate(hull.stations):
        beam = float(data["beam"][idx])
        draft = float(data["draft"][idx])
        if beam <= 1e-7 or draft <= 1e-7:
            diagnostics.append(
                {
                    "station_index": idx,
                    "x_m": float(station.x_m),
                    "raw_added_mass_per_m": 0.0,
                    "raw_damping_per_m": 0.0,
                    "clipped_added_mass_per_m": 0.0,
                    "clipped_damping_per_m": 0.0,
                    "was_clipped": False,
                    "condition_number": "",
                    "residual_norm": "",
                    "status": "skipped_tiny_section",
                }
            )
            continue
        pressure = solve_pressure_transfer(
            _station_offsets_for_bem(station),
            omega_rad_s=omega,
            wave_amplitude_m=1.0,
            wavenumber_rad_m=omega**2 / gravity_m_s2,
            transverse_wavenumber_rad_m=0.0,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            free_surface_panel_count_per_side=free_surface_panel_count_per_side,
            body_panel_count=body_panel_count,
        )
        heave_index = pressure.modes.index("heave")
        heave_force = pressure.radiation_force_matrix_per_m[heave_index, heave_index]
        raw_added[idx] = float(np.real(heave_force) / omega**2)
        raw_damping[idx] = float(-np.imag(heave_force) / omega)
        clipped_added[idx] = max(raw_added[idx], 0.0)
        clipped_damping[idx] = max(raw_damping[idx], 0.0)
        was_clipped = not (
            np.isclose(raw_added[idx], clipped_added[idx], rtol=0.0, atol=1e-12)
            and np.isclose(raw_damping[idx], clipped_damping[idx], rtol=0.0, atol=1e-12)
        )
        diagnostics.append(
            {
                "station_index": idx,
                "x_m": float(station.x_m),
                "raw_added_mass_per_m": raw_added[idx],
                "raw_damping_per_m": raw_damping[idx],
                "clipped_added_mass_per_m": clipped_added[idx],
                "clipped_damping_per_m": clipped_damping[idx],
                "was_clipped": bool(was_clipped),
                "condition_number": pressure.condition_number,
                "residual_norm": max(
                    [pressure.diffraction_residual_norm] + list(pressure.radiation_residual_norm_by_mode.values())
                ),
                "status": pressure.status,
            }
        )
    return raw_added, raw_damping, clipped_added, clipped_damping, diagnostics


def _section_heave_radiation_arrays(
    hull: StationHull,
    omega_rad_s: float,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
    free_surface_panel_count_per_side: int,
    body_panel_count: int | None,
    section_solver: str,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, float | str]]]:
    data = hull.arrays()
    section_added = np.zeros_like(data["x"], dtype=float)
    section_damping = np.zeros_like(data["x"], dtype=float)
    diagnostics = section_bem_station_diagnostics(
        hull,
        omega_rad_s=omega_rad_s,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        section_solver=section_solver,
    )
    for row in diagnostics:
        idx = int(row["station_index"])
        if row["status"] == "skipped_tiny_section":
            continue
        section_added[idx] = max(float(row["added_mass_per_m"]), 0.0)
        section_damping[idx] = max(float(row["damping_per_m"]), 0.0)
    return section_added, section_damping, diagnostics


def _forward_speed_2p5d_operator_parts_from_sections(
    hull: StationHull,
    omega_rad_s: float,
    speed_mps: float,
    section_added: np.ndarray,
    section_damping: np.ndarray,
    projection_pitch_sign: float = 1.0,
    velocity_pitch_sign: float = 1.0,
    speed_term_sign: float = 1.0,
    gradient_sign: float = -1.0,
    include_gradient: bool = True,
) -> tuple[dict[str, np.ndarray], float, float]:
    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    data = hull.arrays()
    x = data["x"]
    x_rel = hull.lcg_m - x
    complex_added = np.asarray(section_added, dtype=float) - 1j * np.asarray(section_damping, dtype=float) / omega
    projection = np.column_stack([np.ones_like(x), float(projection_pitch_sign) * x_rel])
    section_velocity_map = np.column_stack(
        [
            1j * omega * np.ones_like(x),
            1j * omega * float(velocity_pitch_sign) * x_rel + float(speed_term_sign) * speed * np.ones_like(x),
        ]
    )
    main_density = projection[:, :, None] * (
        1j * omega * complex_added[:, None, None] * section_velocity_map[:, None, :]
    )
    main_operator = np.trapezoid(main_density, x, axis=0)
    if include_gradient and speed > 0.0:
        edge_order = 2 if len(x) >= 3 else 1
        complex_aw_gradient = np.gradient(
            complex_added[:, None] * section_velocity_map,
            x,
            axis=0,
            edge_order=edge_order,
        )
        forward_gradient_density = (
            float(gradient_sign) * speed * projection[:, :, None] * complex_aw_gradient[:, None, :]
        )
        forward_gradient_operator = np.trapezoid(forward_gradient_density, x, axis=0)
    else:
        forward_gradient_operator = np.zeros((2, 2), dtype=complex)
    return (
        {
            "main_radiation": main_operator,
            "forward_gradient": forward_gradient_operator,
            "total": main_operator + forward_gradient_operator,
        },
        omega,
        speed,
    )


def _forward_speed_2p5d_station_operator_contributions_from_sections(
    hull: StationHull,
    omega_rad_s: float,
    speed_mps: float,
    section_added: np.ndarray,
    section_damping: np.ndarray,
    assembly_method: str = "continuous_gradient",
) -> list[dict[str, float | int | str | np.ndarray]]:
    """Return per-station heave/pitch operator contributions.

    This is a diagnostic decomposition of the existing station assembly. The
    station contributions sum to the same longitudinal operator used by the
    current development models; no extra hydrodynamic assumption is introduced.
    """

    method = assembly_method.strip().lower()
    if method not in {"continuous_gradient", "pdstrip_step"}:
        raise ValueError("assembly_method must be 'continuous_gradient' or 'pdstrip_step'.")
    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    data = hull.arrays()
    x = data["x"]
    x_rel = hull.lcg_m - x
    weights = _strip_weights(x)
    complex_added = np.asarray(section_added, dtype=float) - 1j * np.asarray(section_damping, dtype=float) / omega
    projection = np.column_stack([np.ones_like(x), x_rel])
    section_velocity_map = np.column_stack(
        [
            1j * omega * np.ones_like(x),
            1j * omega * x_rel + speed * np.ones_like(x),
        ]
    )
    main_density = projection[:, :, None] * (
        1j * omega * complex_added[:, None, None] * section_velocity_map[:, None, :]
    )
    main_contrib = weights[:, None, None] * main_density

    if method == "pdstrip_step":
        gradient_contrib = np.zeros_like(main_contrib)
        aw = complex_added[:, None] * section_velocity_map
        aw_previous_forward = np.zeros(2, dtype=complex)
        for idx in range(len(x) - 1, -1, -1):
            lever = 0.5 * (x_rel[idx] + x_rel[idx + 1]) if idx < len(x) - 1 else x_rel[idx]
            step_projection = np.asarray([1.0, lever], dtype=float)
            gradient_contrib[idx] = speed * step_projection[:, None] * (
                aw[idx, None, :] - aw_previous_forward[None, :]
            )
            aw_previous_forward = aw[idx]
        gradient_name = "forward_gradient_pdstrip_step"
    elif speed > 0.0:
        edge_order = 2 if len(x) >= 3 else 1
        complex_aw_gradient = np.gradient(
            complex_added[:, None] * section_velocity_map,
            x,
            axis=0,
            edge_order=edge_order,
        )
        gradient_density = -speed * projection[:, :, None] * complex_aw_gradient[:, None, :]
        gradient_contrib = weights[:, None, None] * gradient_density
        gradient_name = "forward_gradient"
    else:
        gradient_contrib = np.zeros_like(main_contrib)
        gradient_name = "forward_gradient"

    parts = (
        ("main_radiation", main_contrib),
        (gradient_name, gradient_contrib),
        ("total", main_contrib + gradient_contrib),
    )
    rows: list[dict[str, float | int | str | np.ndarray]] = []
    for idx in range(len(x)):
        for operator_part, contributions in parts:
            rows.append(
                {
                    "station_index": int(idx),
                    "x_m": float(x[idx]),
                    "x_rel_from_cg_m": float(x_rel[idx]),
                    "strip_weight_m": float(weights[idx]),
                    "operator_part": operator_part,
                    "assembly_method": method,
                    "operator": contributions[idx],
                }
            )
    return rows


def _strip_weights(x: np.ndarray) -> np.ndarray:
    if len(x) < 2:
        raise ValueError("At least two stations are required for strip integration.")
    weights = np.zeros_like(x, dtype=float)
    weights[0] = 0.5 * (x[1] - x[0])
    weights[-1] = 0.5 * (x[-1] - x[-2])
    if len(x) > 2:
        weights[1:-1] = 0.5 * (x[2:] - x[:-2])
    return weights


def _external_pdstrip_active_stations(hull: StationHull, section_count: int) -> tuple[HardChineStation, ...]:
    stations = tuple(hull.stations)
    if int(section_count) == len(stations):
        return stations
    areas = np.asarray([station.submerged_area_m2() for station in stations], dtype=float)
    beams = np.asarray([station.waterplane_beam_m() for station in stations], dtype=float)
    drafts = np.asarray([station.effective_draft_m() for station in stations], dtype=float)
    max_area = max(float(np.max(areas)), 0.0)
    max_beam = max(float(np.max(beams)), 0.0)
    max_draft = max(float(np.max(drafts)), 0.0)
    active = tuple(
        station
        for station, area, beam, draft in zip(stations, areas, beams, drafts)
        if area > max(max_area * 1e-10, 1e-14)
        and beam > max(max_beam * 1e-8, 1e-10)
        and draft > max(max_draft * 1e-8, 1e-10)
    )
    if int(section_count) == len(active):
        return active
    raise ValueError(
        f"External PDSTRIP section count ({section_count}) must match hull station count ({len(stations)}) "
        f"or non-degenerate active station count ({len(active)})."
    )


def _interpolate_pdstrip_section_complex_added(sectionresults: Any, station_index: int, omega_rad_s: float) -> np.ndarray:
    blocks = sorted(
        (block for block in sectionresults.blocks if int(block.station_index) == int(station_index)),
        key=lambda block: float(block.omega_rad_s),
    )
    if not blocks:
        raise ValueError(f"No external PDSTRIP sectionresults blocks for station_index={station_index}.")
    frequencies = np.asarray([float(block.omega_rad_s) for block in blocks], dtype=float)
    omega = float(np.clip(float(omega_rad_s), frequencies[0], frequencies[-1]))
    matrices = np.asarray([block.complex_added_mass_matrix_per_m.T for block in blocks], dtype=complex)
    real = np.empty((3, 3), dtype=float)
    imag = np.empty((3, 3), dtype=float)
    for row in range(3):
        for col in range(3):
            real[row, col] = float(np.interp(omega, frequencies, np.real(matrices[:, row, col])))
            imag[row, col] = float(np.interp(omega, frequencies, np.imag(matrices[:, row, col])))
    return real + 1j * imag


def assemble_external_pdstrip_section_6dof_matrices(
    hull: StationHull,
    sectionresults: Any,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    damping_sign_convention: str = "section_bem",
    symmetrize: bool = True,
) -> Station6DOFMatrices:
    """Assemble zero-speed 6DOF matrices from external PDSTRIP section data.

    The external ``sectionresults`` file supplies 3x3 sway/heave/roll section
    radiation matrices. This diagnostic adapter integrates them with the same
    strip weights and lever arms used elsewhere in the station API. It is a
    bridge toward Ma 2005 coefficient mapping, not a validated complete 2.5D
    forward-speed assembly.
    """

    active_stations = _external_pdstrip_active_stations(hull, int(sectionresults.section_count))
    convention = damping_sign_convention.strip().lower()
    if convention not in {"section_bem", "pdstrip"}:
        raise ValueError("damping_sign_convention must be 'section_bem' or 'pdstrip'.")
    omega = max(abs(float(omega_rad_s)), 1e-9)
    full_weights = _strip_weights(np.asarray([station.x_m for station in hull.stations], dtype=float))
    active_index_by_id = {id(station): idx for idx, station in enumerate(hull.stations)}
    added_mass = np.zeros((6, 6), dtype=float)
    damping = np.zeros((6, 6), dtype=float)

    for station_offset, station in enumerate(active_stations):
        full_index = active_index_by_id[id(station)]
        station_index = station_offset + 1
        x_rel = hull.lcg_m - float(station.x_m)
        complex_added = _interpolate_pdstrip_section_complex_added(sectionresults, station_index, omega)
        section_added = np.real(complex_added)
        section_damping = omega * np.imag(complex_added)
        if convention == "section_bem":
            section_damping = -section_damping
        transform = np.zeros((3, 6), dtype=float)
        transform[0, 1] = 1.0
        transform[0, 5] = x_rel
        transform[1, 2] = 1.0
        transform[1, 4] = x_rel
        transform[2, 3] = 1.0
        weight = float(full_weights[full_index])
        added_mass += weight * (transform.T @ section_added @ transform)
        damping += weight * (transform.T @ section_damping @ transform)

    if symmetrize:
        added_mass = 0.5 * (added_mass + added_mass.T)
        damping = 0.5 * (damping + damping.T)

    prototype = assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega,
        speed_mps=0.0,
    )
    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=prototype.restoring,
        hydrostatics=prototype.hydrostatics,
        status=PDSTRIP_EXTERNAL_SECTIONS_STATUS,
    )


def assemble_external_pdstrip_forward_speed_matrices(
    hull: StationHull,
    sectionresults: Any,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    speed_mps: float = 0.0,
    damping_sign_convention: str = "section_bem",
    assembly_method: str = "continuous_gradient",
) -> Station6DOFMatrices:
    """Assemble a forward-speed heave/pitch diagnostic from external PDSTRIP sections.

    This uses external PDSTRIP section radiation data only; diffraction and
    pressure-gradient validation are still missing. It is therefore a triage
    model for Ma 2005, not a validated 2.5D solver.
    """

    method = assembly_method.strip().lower()
    if method not in {"continuous_gradient", "pdstrip_step"}:
        raise ValueError("assembly_method must be 'continuous_gradient' or 'pdstrip_step'.")
    convention = damping_sign_convention.strip().lower()
    if convention not in {"section_bem", "pdstrip"}:
        raise ValueError("damping_sign_convention must be 'section_bem' or 'pdstrip'.")

    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    active_stations = _external_pdstrip_active_stations(hull, int(sectionresults.section_count))
    active_index_by_id = {id(station): idx for idx, station in enumerate(hull.stations)}
    section_added = np.zeros(len(hull.stations), dtype=float)
    section_damping = np.zeros(len(hull.stations), dtype=float)
    for station_offset, station in enumerate(active_stations):
        full_index = active_index_by_id[id(station)]
        station_index = station_offset + 1
        complex_added = _interpolate_pdstrip_section_complex_added(sectionresults, station_index, omega)
        heave_complex_added = complex_added[1, 1]
        damping = omega * float(np.imag(heave_complex_added))
        if convention == "section_bem":
            damping = -damping
        section_added[full_index] = float(np.real(heave_complex_added))
        section_damping[full_index] = damping

    if method == "pdstrip_step":
        operator_parts, omega, _ = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
            hull,
            omega_rad_s=omega,
            speed_mps=speed,
            section_added=section_added,
            section_damping=section_damping,
        )
    else:
        operator_parts, omega, _ = _forward_speed_2p5d_operator_parts_from_sections(
            hull,
            omega_rad_s=omega,
            speed_mps=speed,
            section_added=section_added,
            section_damping=section_damping,
        )
    dynamic_operator = operator_parts["total"]
    longitudinal_added = -np.real(dynamic_operator) / omega**2
    longitudinal_damping = np.imag(dynamic_operator) / omega

    matrices = assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega,
        speed_mps=0.0,
    )
    added_mass = np.array(matrices.added_mass, copy=True)
    damping = np.array(matrices.damping, copy=True)
    for local_i, dof_i in enumerate(LONGITUDINAL_DOF_INDICES):
        for local_j, dof_j in enumerate(LONGITUDINAL_DOF_INDICES):
            added_mass[dof_i, dof_j] = float(longitudinal_added[local_i, local_j])
            damping[dof_i, dof_j] = float(longitudinal_damping[local_i, local_j])

    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=matrices.restoring,
        hydrostatics=matrices.hydrostatics,
        status=PDSTRIP_EXTERNAL_PDSTRIP_STEP_STATUS if method == "pdstrip_step" else PDSTRIP_EXTERNAL_FORWARD_STATUS,
    )


def external_pdstrip_heave_section_diagnostics(
    hull: StationHull,
    sectionresults: Any,
    omega_rad_s: float = 1.0,
    damping_sign_convention: str = "section_bem",
) -> list[dict[str, float | str]]:
    """Return per-station heave radiation rows from external PDSTRIP sections."""

    convention = damping_sign_convention.strip().lower()
    if convention not in {"section_bem", "pdstrip"}:
        raise ValueError("damping_sign_convention must be 'section_bem' or 'pdstrip'.")
    omega = max(abs(float(omega_rad_s)), 1e-9)
    active_stations = _external_pdstrip_active_stations(hull, int(sectionresults.section_count))
    active_index_by_id = {id(station): idx for idx, station in enumerate(hull.stations)}
    active_x = np.asarray([station.x_m for station in active_stations], dtype=float)
    active_weights = _strip_weights(active_x)
    full_weights = _strip_weights(np.asarray([station.x_m for station in hull.stations], dtype=float))
    rows: list[dict[str, float | str]] = []
    for pdstrip_offset, station in enumerate(active_stations):
        full_index = active_index_by_id[id(station)]
        pdstrip_station_index = pdstrip_offset + 1
        x_rel = hull.lcg_m - float(station.x_m)
        complex_added = _interpolate_pdstrip_section_complex_added(sectionresults, pdstrip_station_index, omega)
        heave_complex_added = complex_added[1, 1]
        damping = omega * float(np.imag(heave_complex_added))
        if convention == "section_bem":
            damping = -damping
        weight = float(full_weights[full_index])
        active_only_weight = float(active_weights[pdstrip_offset])
        added = float(np.real(heave_complex_added))
        rows.append(
            {
                "station_index": int(full_index),
                "pdstrip_station_index": int(pdstrip_station_index),
                "x_m": float(station.x_m),
                "x_rel_from_cg_m": float(x_rel),
                "beam_m": float(station.waterplane_beam_m()),
                "draft_m": float(station.effective_draft_m()),
                "submerged_area_m2": float(station.submerged_area_m2()),
                "strip_weight_m": weight,
                "active_only_strip_weight_m": active_only_weight,
                "endpoint_closure_weight_delta_m": float(weight - active_only_weight),
                "external_added_mass_per_m": added,
                "external_damping_per_m": float(damping),
                "a33_contribution": float(weight * added),
                "a35_contribution": float(weight * added * x_rel),
                "a55_contribution": float(weight * added * x_rel**2),
                "b33_contribution": float(weight * damping),
                "b35_contribution": float(weight * damping * x_rel),
                "b55_contribution": float(weight * damping * x_rel**2),
                "status": PDSTRIP_EXTERNAL_SECTIONS_STATUS,
            }
        )
    return rows


def _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
    hull: StationHull,
    omega_rad_s: float,
    speed_mps: float,
    section_added: np.ndarray,
    section_damping: np.ndarray,
    projection_pitch_sign: float = 1.0,
    velocity_pitch_sign: float = 1.0,
    speed_term_sign: float = 1.0,
    derivative_dynamic_sign: float = 1.0,
) -> tuple[dict[str, np.ndarray], float, float]:
    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    data = hull.arrays()
    x = data["x"]
    x_rel = hull.lcg_m - x
    weights = _strip_weights(x)
    complex_added = np.asarray(section_added, dtype=float) - 1j * np.asarray(section_damping, dtype=float) / omega
    projection = np.column_stack([np.ones_like(x), float(projection_pitch_sign) * x_rel])
    section_velocity_map = np.column_stack(
        [
            1j * omega * np.ones_like(x),
            1j * omega * float(velocity_pitch_sign) * x_rel + float(speed_term_sign) * speed * np.ones_like(x),
        ]
    )
    aw = complex_added[:, None] * section_velocity_map
    main_operator = np.zeros((2, 2), dtype=complex)
    for idx in range(len(x)):
        main_operator += weights[idx] * projection[idx, :, None] * (1j * omega * aw[idx, None, :])

    step_operator = np.zeros((2, 2), dtype=complex)
    aw_previous_forward = np.zeros(2, dtype=complex)
    for idx in range(len(x) - 1, -1, -1):
        if idx < len(x) - 1:
            lever = 0.5 * (x_rel[idx] + x_rel[idx + 1])
        else:
            lever = x_rel[idx]
        step_projection = np.asarray([1.0, float(projection_pitch_sign) * lever], dtype=float)
        step_operator += (
            float(derivative_dynamic_sign)
            * speed
            * step_projection[:, None]
            * (aw[idx, None, :] - aw_previous_forward[None, :])
        )
        aw_previous_forward = aw[idx]
    return (
        {
            "main_radiation": main_operator,
            "forward_gradient": step_operator,
            "total": main_operator + step_operator,
        },
        omega,
        speed,
    )


def assemble_experimental_bem_6dof_matrices(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
    section_solver: str = "collocation",
) -> Station6DOFMatrices:
    """Assemble a 6DOF matrix using experimental 2D section BEM heave terms.

    The current BEM path solves heave radiation on each transverse station and
    integrates it into heave/pitch terms. Lateral terms, excitation, and 2.5D
    matched free-surface stepping are still development work, so this function
    must remain diagnostic until it passes Ma 2005.
    """

    data = hull.arrays()
    x = data["x"]
    x_rel = hull.lcg_m - x
    hydro = hull.hydrostatics()

    section_added, section_damping, _ = _section_heave_radiation_arrays(
        hull,
        omega_rad_s=omega_rad_s,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        section_solver=section_solver,
    )

    matrices = assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega_rad_s,
        speed_mps=speed_mps,
    )
    added_mass = np.array(matrices.added_mass, copy=True)
    damping = np.array(matrices.damping, copy=True)
    added_mass[2, 2] = float(np.trapezoid(section_added, x))
    added_mass[2, 4] = added_mass[4, 2] = float(np.trapezoid(section_added * x_rel, x))
    added_mass[4, 4] = float(np.trapezoid(section_added * x_rel**2, x))
    damping[2, 2] = float(np.trapezoid(section_damping, x))
    damping[2, 4] = damping[4, 2] = float(np.trapezoid(section_damping * x_rel, x))
    damping[4, 4] = float(np.trapezoid(section_damping * x_rel**2, x))

    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=matrices.restoring,
        hydrostatics=hydro,
        status=PDSTRIP_STYLE_STATUS if section_solver.strip().lower() == "pdstrip_style" else SECTION_BEM_STATUS,
    )


def _forward_speed_2p5d_operator_parts(
    hull: StationHull,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
    omega_rad_s: float,
    free_surface_panel_count_per_side: int,
    body_panel_count: int | None,
    speed_mps: float,
    section_solver: str,
) -> tuple[dict[str, np.ndarray], SectionHydrostatics, float, float]:
    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    hydro = hull.hydrostatics()
    section_added, section_damping, _ = _section_heave_radiation_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        section_solver=section_solver,
    )
    operator_parts, omega, speed = _forward_speed_2p5d_operator_parts_from_sections(
        hull,
        omega_rad_s=omega,
        speed_mps=speed,
        section_added=section_added,
        section_damping=section_damping,
    )
    return operator_parts, hydro, omega, speed


def assemble_forward_speed_2p5d_matrices(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
    section_solver: str = "pdstrip_style",
    assembly_method: str = "continuous_gradient",
) -> Station6DOFMatrices:
    """Assemble a diagnostic PDSTRIP-like forward-speed heave/pitch model.

    The compact ``section_bem`` path integrates section added mass and damping as
    symmetric strip terms. This diagnostic branch instead builds the complex
    frequency-domain hydrodynamic operator from each section's
    ``a - i b / omega`` value, a forward-speed vertical-velocity mapping, and a
    finite-difference longitudinal gradient term inspired by PDSTRIP's ``W`` and
    ``U*d(AW)/dx`` assembly. It remains experimental until it passes Ma 2005.
    """

    method = assembly_method.strip().lower()
    if method not in {"continuous_gradient", "pdstrip_step"}:
        raise ValueError("assembly_method must be 'continuous_gradient' or 'pdstrip_step'.")
    if method == "pdstrip_step":
        omega = max(abs(float(omega_rad_s)), 1e-9)
        speed = max(float(speed_mps), 0.0)
        hydro = hull.hydrostatics()
        section_added, section_damping, _ = _section_heave_radiation_arrays(
            hull,
            omega_rad_s=omega,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            free_surface_panel_count_per_side=free_surface_panel_count_per_side,
            body_panel_count=body_panel_count,
            section_solver=section_solver,
        )
        operator_parts, omega, _ = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
            hull,
            omega_rad_s=omega,
            speed_mps=speed,
            section_added=section_added,
            section_damping=section_damping,
        )
    else:
        operator_parts, hydro, omega, _ = _forward_speed_2p5d_operator_parts(
            hull,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            omega_rad_s=omega_rad_s,
            free_surface_panel_count_per_side=free_surface_panel_count_per_side,
            body_panel_count=body_panel_count,
            speed_mps=speed_mps,
            section_solver=section_solver,
        )
    dynamic_operator = operator_parts["total"]

    longitudinal_added = -np.real(dynamic_operator) / omega**2
    longitudinal_damping = np.imag(dynamic_operator) / omega

    matrices = assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega,
        speed_mps=0.0,
    )
    added_mass = np.array(matrices.added_mass, copy=True)
    damping = np.array(matrices.damping, copy=True)
    for local_i, dof_i in enumerate(LONGITUDINAL_DOF_INDICES):
        for local_j, dof_j in enumerate(LONGITUDINAL_DOF_INDICES):
            added_mass[dof_i, dof_j] = float(longitudinal_added[local_i, local_j])
            damping[dof_i, dof_j] = float(longitudinal_damping[local_i, local_j])

    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=matrices.restoring,
        hydrostatics=hydro,
        status=STRIP_2P5D_PDSTRIP_STEP_STATUS if method == "pdstrip_step" else STRIP_2P5D_FORWARD_STATUS,
    )


def assemble_pressure_transfer_forward_speed_matrices(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
    assembly_method: str = "continuous_gradient",
    clip_negative_section_terms: bool = True,
) -> Station6DOFMatrices:
    """Assemble a pressure-transfer forward-speed heave/pitch diagnostic.

    The scalar section-BEM path integrates section force coefficients. This
    branch derives the same per-metre heave radiation coefficients from the
    body-panel pressure-transfer solve, then routes them through the current
    forward-speed station operator. It is a development bridge toward the
    pressure-based 2.5D formulation, not a validated acceptance model.
    """

    method = assembly_method.strip().lower()
    if method not in {"continuous_gradient", "pdstrip_step"}:
        raise ValueError("assembly_method must be 'continuous_gradient' or 'pdstrip_step'.")
    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    raw_added, raw_damping, clipped_added, clipped_damping, _ = _section_heave_pressure_transfer_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
    )
    section_added = clipped_added if clip_negative_section_terms else raw_added
    section_damping = clipped_damping if clip_negative_section_terms else raw_damping
    if method == "pdstrip_step":
        operator_parts, omega, _ = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
            hull,
            omega_rad_s=omega,
            speed_mps=speed,
            section_added=section_added,
            section_damping=section_damping,
        )
    else:
        operator_parts, omega, _ = _forward_speed_2p5d_operator_parts_from_sections(
            hull,
            omega_rad_s=omega,
            speed_mps=speed,
            section_added=section_added,
            section_damping=section_damping,
        )
    dynamic_operator = operator_parts["total"]
    longitudinal_added = -np.real(dynamic_operator) / omega**2
    longitudinal_damping = np.imag(dynamic_operator) / omega

    matrices = assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega,
        speed_mps=0.0,
    )
    added_mass = np.array(matrices.added_mass, copy=True)
    damping = np.array(matrices.damping, copy=True)
    for local_i, dof_i in enumerate(LONGITUDINAL_DOF_INDICES):
        for local_j, dof_j in enumerate(LONGITUDINAL_DOF_INDICES):
            added_mass[dof_i, dof_j] = float(longitudinal_added[local_i, local_j])
            damping[dof_i, dof_j] = float(longitudinal_damping[local_i, local_j])

    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=matrices.restoring,
        hydrostatics=matrices.hydrostatics,
        status=(
            PRESSURE_TRANSFER_PDSTRIP_STEP_ASSEMBLY_STATUS
            if method == "pdstrip_step"
            else PRESSURE_TRANSFER_FORWARD_ASSEMBLY_STATUS
        ),
    )


def assemble_pressure_transfer_pdstrip_damping_forward_speed_matrices(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
    assembly_method: str = "continuous_gradient",
    clip_negative_section_terms: bool = True,
) -> Station6DOFMatrices:
    """Pressure-transfer diagnostic with PDSTRIP-style sectional damping.

    This candidate keeps the pressure-transfer sectional added-mass channel but
    replaces sectional damping with the local PDSTRIP-style radiation solver.
    It tests whether Ma 2005 B35/B53 misses are controlled by sectional damping
    frequency shape. It is deliberately diagnostic and must not be treated as a
    validated pressure-transfer formulation.
    """

    method = assembly_method.strip().lower()
    if method not in {"continuous_gradient", "pdstrip_step"}:
        raise ValueError("assembly_method must be 'continuous_gradient' or 'pdstrip_step'.")
    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    raw_added, _, clipped_added, _, _ = _section_heave_pressure_transfer_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
    )
    _, pdstrip_style_damping, _ = _section_heave_radiation_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        section_solver="pdstrip_style",
    )
    section_added = clipped_added if clip_negative_section_terms else raw_added
    section_damping = pdstrip_style_damping
    if method == "pdstrip_step":
        operator_parts, omega, _ = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
            hull,
            omega_rad_s=omega,
            speed_mps=speed,
            section_added=section_added,
            section_damping=section_damping,
        )
    else:
        operator_parts, omega, _ = _forward_speed_2p5d_operator_parts_from_sections(
            hull,
            omega_rad_s=omega,
            speed_mps=speed,
            section_added=section_added,
            section_damping=section_damping,
        )
    dynamic_operator = operator_parts["total"]
    longitudinal_added = -np.real(dynamic_operator) / omega**2
    longitudinal_damping = np.imag(dynamic_operator) / omega

    matrices = assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega,
        speed_mps=0.0,
    )
    added_mass = np.array(matrices.added_mass, copy=True)
    damping = np.array(matrices.damping, copy=True)
    for local_i, dof_i in enumerate(LONGITUDINAL_DOF_INDICES):
        for local_j, dof_j in enumerate(LONGITUDINAL_DOF_INDICES):
            added_mass[dof_i, dof_j] = float(longitudinal_added[local_i, local_j])
            damping[dof_i, dof_j] = float(longitudinal_damping[local_i, local_j])

    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=matrices.restoring,
        hydrostatics=matrices.hydrostatics,
        status=(
            PRESSURE_TRANSFER_PDSTRIP_DAMPING_PDSTRIP_STEP_ASSEMBLY_STATUS
            if method == "pdstrip_step"
            else PRESSURE_TRANSFER_PDSTRIP_DAMPING_FORWARD_ASSEMBLY_STATUS
        ),
    )


def assemble_hybrid_forward_coupling_matrices(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
) -> Station6DOFMatrices:
    """Return a diagnostic matrix with prototype diagonals and forward couplings.

    This is an error-isolation model for Ma 2005 triage: the prototype path has
    acceptable diagonal trends, while ``strip_2p5d_forward`` gives a more
    physics-based forward-speed coupling channel. Keeping them separated helps
    decide whether remaining error is diagonal section radiation or coupling
    assembly. It is not a production hydrodynamic model.
    """

    prototype = assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega_rad_s,
        speed_mps=speed_mps,
    )
    forward = assemble_forward_speed_2p5d_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega_rad_s,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        speed_mps=speed_mps,
        section_solver="pdstrip_style",
    )
    added_mass = np.array(prototype.added_mass, copy=True)
    damping = np.array(prototype.damping, copy=True)
    for row_idx, col_idx in ((2, 4), (4, 2)):
        added_mass[row_idx, col_idx] = forward.added_mass[row_idx, col_idx]
        damping[row_idx, col_idx] = forward.damping[row_idx, col_idx]
    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=prototype.restoring,
        hydrostatics=prototype.hydrostatics,
        status=HYBRID_FORWARD_COUPLING_STATUS,
    )


def assemble_hybrid_pressure_damping_coupling_matrices(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
) -> Station6DOFMatrices:
    """Return a diagnostic hybrid focused on Ma 2005 damping couplings.

    Prototype diagonal terms are kept as a stable baseline. Added-mass
    heave/pitch couplings come from the existing forward-speed assembly, while
    damping couplings come from the pressure-transfer PDSTRIP-step path. This
    isolates whether the pressure path reduces the current B35/B53 blockers; it
    is diagnostic, not a validated production model.
    """

    prototype = assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega_rad_s,
        speed_mps=speed_mps,
    )
    forward = assemble_forward_speed_2p5d_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega_rad_s,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        speed_mps=speed_mps,
        section_solver="pdstrip_style",
    )
    pressure = assemble_pressure_transfer_forward_speed_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega_rad_s,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        speed_mps=speed_mps,
        assembly_method="pdstrip_step",
    )
    added_mass = np.array(prototype.added_mass, copy=True)
    damping = np.array(prototype.damping, copy=True)
    for row_idx, col_idx in ((2, 4), (4, 2)):
        added_mass[row_idx, col_idx] = forward.added_mass[row_idx, col_idx]
        damping[row_idx, col_idx] = pressure.damping[row_idx, col_idx]
    return Station6DOFMatrices(
        added_mass=added_mass,
        damping=damping,
        restoring=prototype.restoring,
        hydrostatics=prototype.hydrostatics,
        status=HYBRID_PRESSURE_DAMPING_COUPLING_STATUS,
    )


def forward_speed_2p5d_component_diagnostics(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
    section_solver: str = "pdstrip_style",
    assembly_method: str = "continuous_gradient",
) -> list[dict[str, float | str]]:
    """Return component-level A/B diagnostics for the forward-speed assembly."""

    method = assembly_method.strip().lower()
    if method not in {"continuous_gradient", "pdstrip_step"}:
        raise ValueError("assembly_method must be 'continuous_gradient' or 'pdstrip_step'.")
    if method == "pdstrip_step":
        omega = max(abs(float(omega_rad_s)), 1e-9)
        speed = max(float(speed_mps), 0.0)
        section_added, section_damping, _ = _section_heave_radiation_arrays(
            hull,
            omega_rad_s=omega,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            free_surface_panel_count_per_side=free_surface_panel_count_per_side,
            body_panel_count=body_panel_count,
            section_solver=section_solver,
        )
        operator_parts, omega, speed = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
            hull,
            omega_rad_s=omega,
            speed_mps=speed,
            section_added=section_added,
            section_damping=section_damping,
        )
    else:
        operator_parts, _, omega, speed = _forward_speed_2p5d_operator_parts(
            hull,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            omega_rad_s=omega_rad_s,
            free_surface_panel_count_per_side=free_surface_panel_count_per_side,
            body_panel_count=body_panel_count,
            speed_mps=speed_mps,
            section_solver=section_solver,
        )
    dofs = [("3", "heave", 2), ("5", "pitch", 4)]
    rows: list[dict[str, float | str]] = []
    for component, operator in operator_parts.items():
        added = -np.real(operator) / omega**2
        damping = np.imag(operator) / omega
        for local_i, (row_number, row_label, row_index) in enumerate(dofs):
            for local_j, (col_number, col_label, col_index) in enumerate(dofs):
                rows.append(
                    {
                        "component": component,
                        "omega_rad_s": float(omega),
                        "speed_mps": float(speed),
                        "row_dof": row_label,
                        "col_dof": col_label,
                        "row_index": row_index,
                        "col_index": col_index,
                        "added_mass_coefficient": f"A{row_number}{col_number}",
                        "damping_coefficient": f"B{row_number}{col_number}",
                        "added_mass_value": float(added[local_i, local_j]),
                        "damping_value": float(damping[local_i, local_j]),
                        "dynamic_operator_real": float(np.real(operator[local_i, local_j])),
                        "dynamic_operator_imag": float(np.imag(operator[local_i, local_j])),
                        "assembly_method": method,
                        "section_solver": section_solver.strip().lower(),
                        "status": STRIP_2P5D_PDSTRIP_STEP_STATUS if method == "pdstrip_step" else STRIP_2P5D_FORWARD_STATUS,
                    }
                )
    return rows


def forward_speed_pressure_transfer_diagnostics(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
) -> list[dict[str, float | str]]:
    """Reconstruct the forward-speed main operator from body-panel pressures.

    This audit uses the compact section-BEM pressure transfer functions to build
    the heave/pitch main-radiation operator from panel pressure contributions.
    It is a diagnostic bridge toward pressure-based 2.5D assembly; it does not
    replace the Ma 2005 coefficient gate.
    """

    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    data = hull.arrays()
    x = data["x"]
    x_rel = hull.lcg_m - x
    weights = _strip_weights(x)
    pressure_operator_raw = np.zeros((2, 2), dtype=complex)
    pressure_operator_clipped = np.zeros((2, 2), dtype=complex)
    active_station_count = 0
    clipped_station_count = 0
    max_pressure_abs = 0.0
    max_residual_norm = 0.0
    max_condition_number = 0.0

    for idx, station in enumerate(hull.stations):
        beam = float(data["beam"][idx])
        draft = float(data["draft"][idx])
        if beam <= 1e-7 or draft <= 1e-7:
            continue
        pressure = solve_pressure_transfer(
            _station_offsets_for_bem(station),
            omega_rad_s=omega,
            wave_amplitude_m=1.0,
            wavenumber_rad_m=omega**2 / gravity_m_s2,
            transverse_wavenumber_rad_m=0.0,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            free_surface_panel_count_per_side=free_surface_panel_count_per_side,
            body_panel_count=body_panel_count,
        )
        heave_index = pressure.modes.index("heave")
        heave_pressure = pressure.radiation_pressure_pa[:, heave_index]
        panel_force_per_displacement = heave_pressure * (-pressure.panel_normal_z) * pressure.panel_length_m
        force_per_displacement = complex(np.sum(panel_force_per_displacement))
        added_per_m = max(float(np.real(force_per_displacement) / omega**2), 0.0)
        damping_per_m_raw = float(-np.imag(force_per_displacement) / omega)
        damping_per_m = max(damping_per_m_raw, 0.0)
        clipped_force_per_displacement = complex(added_per_m * omega**2 - 1j * damping_per_m * omega)
        if not np.isclose(force_per_displacement, clipped_force_per_displacement, rtol=0.0, atol=1e-12):
            clipped_station_count += 1
        lever = float(x_rel[idx])
        row_projection = np.asarray([1.0, lever], dtype=float)
        section_displacement_map = np.asarray([1.0, lever + speed / (1j * omega)], dtype=complex)
        pressure_operator_raw += (
            -weights[idx]
            * force_per_displacement
            * row_projection[:, None]
            * section_displacement_map[None, :]
        )
        pressure_operator_clipped += (
            -weights[idx]
            * clipped_force_per_displacement
            * row_projection[:, None]
            * section_displacement_map[None, :]
        )
        active_station_count += 1
        max_pressure_abs = max(max_pressure_abs, float(np.max(np.abs(heave_pressure))))
        max_residual_norm = max(
            max_residual_norm,
            max(float(value) for value in pressure.radiation_residual_norm_by_mode.values()),
            float(pressure.diffraction_residual_norm),
        )
        max_condition_number = max(max_condition_number, float(pressure.condition_number))

    force_operator_parts, _, _, _ = _forward_speed_2p5d_operator_parts(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        speed_mps=speed,
        section_solver="collocation",
    )
    force_operator = force_operator_parts["main_radiation"]
    raw_difference_operator = pressure_operator_raw - force_operator
    clipped_difference_operator = pressure_operator_clipped - force_operator
    dofs = [("3", "heave", 2), ("5", "pitch", 4)]
    rows: list[dict[str, float | str]] = []
    for component, operator in (
        ("pressure_main_radiation_raw", pressure_operator_raw),
        ("pressure_main_radiation_clipped_like_force", pressure_operator_clipped),
        ("force_main_radiation", force_operator),
        ("pressure_raw_minus_force_main_radiation", raw_difference_operator),
        ("pressure_clipped_minus_force_main_radiation", clipped_difference_operator),
    ):
        added = -np.real(operator) / omega**2
        damping = np.imag(operator) / omega
        for local_i, (row_number, row_label, row_index) in enumerate(dofs):
            for local_j, (col_number, col_label, col_index) in enumerate(dofs):
                rows.append(
                    {
                        "component": component,
                        "omega_rad_s": float(omega),
                        "speed_mps": float(speed),
                        "row_dof": row_label,
                        "col_dof": col_label,
                        "row_index": row_index,
                        "col_index": col_index,
                        "added_mass_coefficient": f"A{row_number}{col_number}",
                        "damping_coefficient": f"B{row_number}{col_number}",
                        "added_mass_value": float(added[local_i, local_j]),
                        "damping_value": float(damping[local_i, local_j]),
                        "dynamic_operator_real": float(np.real(operator[local_i, local_j])),
                        "dynamic_operator_imag": float(np.imag(operator[local_i, local_j])),
                        "active_station_count": int(active_station_count),
                        "clipped_station_count": int(clipped_station_count),
                        "max_heave_radiation_pressure_abs_pa": float(max_pressure_abs),
                        "max_condition_number": float(max_condition_number),
                        "max_residual_norm": float(max_residual_norm),
                        "section_solver": "collocation_pressure_transfer",
                        "status": PRESSURE_TRANSFER_FORWARD_STATUS,
                    }
                )
    return rows


def forward_speed_pressure_gradient_diagnostics(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
) -> list[dict[str, float | str]]:
    """Return pressure-transfer diagnostics for the PDSTRIP-step gradient term.

    The diagnostic compares a pressure-derived section coefficient path with
    the existing force-integrated section-coefficient path using the same
    bow-to-stern step difference. The clipped pressure path applies the same
    nonnegative heave added-mass/damping clipping as the current scalar
    section-BEM path, so any remaining difference is assembly-related.
    """

    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    raw_added, raw_damping, clipped_added, clipped_damping, pressure_rows = _section_heave_pressure_transfer_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
    )
    force_added, force_damping, _ = _section_heave_radiation_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        section_solver="collocation",
    )
    raw_parts, omega, speed = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
        hull,
        omega_rad_s=omega,
        speed_mps=speed,
        section_added=raw_added,
        section_damping=raw_damping,
    )
    clipped_parts, _, _ = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
        hull,
        omega_rad_s=omega,
        speed_mps=speed,
        section_added=clipped_added,
        section_damping=clipped_damping,
    )
    force_parts, _, _ = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
        hull,
        omega_rad_s=omega,
        speed_mps=speed,
        section_added=force_added,
        section_damping=force_damping,
    )
    source_parts: list[tuple[str, dict[str, np.ndarray]]] = [
        ("pressure_raw_pdstrip_step", raw_parts),
        ("pressure_clipped_pdstrip_step", clipped_parts),
        ("force_pdstrip_step", force_parts),
        (
            "pressure_raw_minus_force_pdstrip_step",
            {key: raw_parts[key] - force_parts[key] for key in raw_parts},
        ),
        (
            "pressure_clipped_minus_force_pdstrip_step",
            {key: clipped_parts[key] - force_parts[key] for key in clipped_parts},
        ),
    ]
    clipped_station_count = int(sum(1 for row in pressure_rows if row.get("was_clipped") is True))
    max_added_clip = float(np.max(np.abs(raw_added - clipped_added))) if len(raw_added) else 0.0
    max_damping_clip = float(np.max(np.abs(raw_damping - clipped_damping))) if len(raw_damping) else 0.0
    max_condition_number = max(
        [float(row["condition_number"]) for row in pressure_rows if row.get("condition_number") != ""] or [0.0]
    )
    max_residual_norm = max(
        [float(row["residual_norm"]) for row in pressure_rows if row.get("residual_norm") != ""] or [0.0]
    )
    dofs = [("3", "heave", 2), ("5", "pitch", 4)]
    rows: list[dict[str, float | str]] = []
    for source, parts in source_parts:
        for operator_part, operator in parts.items():
            added = -np.real(operator) / omega**2
            damping = np.imag(operator) / omega
            for local_i, (row_number, row_label, row_index) in enumerate(dofs):
                for local_j, (col_number, col_label, col_index) in enumerate(dofs):
                    rows.append(
                        {
                            "source": source,
                            "operator_part": operator_part,
                            "omega_rad_s": float(omega),
                            "speed_mps": float(speed),
                            "row_dof": row_label,
                            "col_dof": col_label,
                            "row_index": row_index,
                            "col_index": col_index,
                            "added_mass_coefficient": f"A{row_number}{col_number}",
                            "damping_coefficient": f"B{row_number}{col_number}",
                            "added_mass_value": float(added[local_i, local_j]),
                            "damping_value": float(damping[local_i, local_j]),
                            "dynamic_operator_real": float(np.real(operator[local_i, local_j])),
                            "dynamic_operator_imag": float(np.imag(operator[local_i, local_j])),
                            "active_station_count": int(sum(raw_added != 0.0)),
                            "clipped_station_count": clipped_station_count,
                            "max_added_clip_per_m": max_added_clip,
                            "max_damping_clip_per_m": max_damping_clip,
                            "max_condition_number": max_condition_number,
                            "max_residual_norm": max_residual_norm,
                            "section_solver": "collocation_pressure_transfer_pdstrip_step",
                            "status": PRESSURE_TRANSFER_GRADIENT_STATUS,
                        }
                    )
    return rows


def forward_speed_coupling_station_contribution_diagnostics(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
    coefficients: tuple[str, ...] = ("B35", "B53"),
) -> list[dict[str, float | str | bool | int]]:
    """Return station-level longitudinal coefficient contribution diagnostics."""

    coefficient_filter = {str(coefficient).strip().upper() for coefficient in coefficients}
    valid_coefficients = {"A33", "A35", "A53", "A55", "B33", "B35", "B53", "B55"}
    unsupported = coefficient_filter - valid_coefficients
    if unsupported:
        raise ValueError(f"Unsupported longitudinal coefficients for station diagnostics: {sorted(unsupported)}")
    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    raw_added, raw_damping, clipped_added, clipped_damping, pressure_rows = _section_heave_pressure_transfer_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
    )
    force_added, force_damping, _ = _section_heave_radiation_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        section_solver="collocation",
    )
    pdstrip_added, pdstrip_damping, _ = _section_heave_radiation_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        section_solver="pdstrip_style",
    )
    pressure_by_station = {int(row["station_index"]): row for row in pressure_rows}
    sources = (
        ("force_collocation", force_added, force_damping, "collocation_force_integral"),
        ("force_pdstrip_style", pdstrip_added, pdstrip_damping, "pdstrip_style_force_integral"),
        ("pressure_raw", raw_added, raw_damping, "collocation_pressure_transfer_raw"),
        ("pressure_clipped", clipped_added, clipped_damping, "collocation_pressure_transfer_clipped"),
    )
    dofs = [("3", "heave", 2), ("5", "pitch", 4)]
    rows: list[dict[str, float | str | bool | int]] = []
    for source, added, damping, section_solver in sources:
        for assembly_method in ("continuous_gradient", "pdstrip_step"):
            station_contrib = _forward_speed_2p5d_station_operator_contributions_from_sections(
                hull,
                omega_rad_s=omega,
                speed_mps=speed,
                section_added=added,
                section_damping=damping,
                assembly_method=assembly_method,
            )
            for item in station_contrib:
                idx = int(item["station_index"])
                operator = np.asarray(item["operator"], dtype=complex)
                added_matrix = -np.real(operator) / omega**2
                damping_matrix = np.imag(operator) / omega
                pressure_meta = pressure_by_station.get(idx, {})
                for local_i, (row_number, row_label, row_index) in enumerate(dofs):
                    for local_j, (col_number, col_label, col_index) in enumerate(dofs):
                        added_coefficient = f"A{row_number}{col_number}"
                        damping_coefficient = f"B{row_number}{col_number}"
                        if added_coefficient in coefficient_filter:
                            rows.append(
                                {
                                    "source": source,
                                    "section_solver": section_solver,
                                    "assembly_method": assembly_method,
                                    "operator_part": str(item["operator_part"]),
                                    "station_index": idx,
                                    "x_m": float(item["x_m"]),
                                    "x_rel_from_cg_m": float(item["x_rel_from_cg_m"]),
                                    "strip_weight_m": float(item["strip_weight_m"]),
                                    "row_dof": row_label,
                                    "col_dof": col_label,
                                    "row_index": row_index,
                                    "col_index": col_index,
                                    "coefficient": added_coefficient,
                                    "coefficient_kind": "added_mass",
                                    "station_contribution_value": float(added_matrix[local_i, local_j]),
                                    "source_added_mass_per_m": float(added[idx]),
                                    "source_damping_per_m": float(damping[idx]),
                                    "dynamic_operator_real": float(np.real(operator[local_i, local_j])),
                                    "dynamic_operator_imag": float(np.imag(operator[local_i, local_j])),
                                    "omega_rad_s": float(omega),
                                    "speed_mps": float(speed),
                                    "pressure_was_clipped": bool(pressure_meta.get("was_clipped", False)),
                                    "pressure_condition_number": pressure_meta.get("condition_number", ""),
                                    "pressure_residual_norm": pressure_meta.get("residual_norm", ""),
                                    "status": "diagnostic_station_coupling_contribution_not_validated",
                                }
                            )
                        if damping_coefficient in coefficient_filter:
                            rows.append(
                                {
                                    "source": source,
                                    "section_solver": section_solver,
                                    "assembly_method": assembly_method,
                                    "operator_part": str(item["operator_part"]),
                                    "station_index": idx,
                                    "x_m": float(item["x_m"]),
                                    "x_rel_from_cg_m": float(item["x_rel_from_cg_m"]),
                                    "strip_weight_m": float(item["strip_weight_m"]),
                                    "row_dof": row_label,
                                    "col_dof": col_label,
                                    "row_index": row_index,
                                    "col_index": col_index,
                                    "coefficient": damping_coefficient,
                                    "coefficient_kind": "damping",
                                    "station_contribution_value": float(damping_matrix[local_i, local_j]),
                                    "source_added_mass_per_m": float(added[idx]),
                                    "source_damping_per_m": float(damping[idx]),
                                    "dynamic_operator_real": float(np.real(operator[local_i, local_j])),
                                    "dynamic_operator_imag": float(np.imag(operator[local_i, local_j])),
                                    "omega_rad_s": float(omega),
                                    "speed_mps": float(speed),
                                    "pressure_was_clipped": bool(pressure_meta.get("was_clipped", False)),
                                    "pressure_condition_number": pressure_meta.get("condition_number", ""),
                                    "pressure_residual_norm": pressure_meta.get("residual_norm", ""),
                                    "status": "diagnostic_station_coupling_contribution_not_validated",
                                }
                            )
    return rows


def forward_speed_coupling_variant_diagnostics(
    hull: StationHull,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    omega_rad_s: float = 1.0,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
    speed_mps: float = 0.0,
    section_solver: str = "pdstrip_style",
) -> list[dict[str, float | str]]:
    """Return sign/transpose variants for forward-speed coupling debugging.

    The variants are diagnostic only. They do not define accepted physics; they
    make Ma 2005 coupling failures attributable to a small set of sign,
    transpose, and gradient choices.
    """

    omega = max(abs(float(omega_rad_s)), 1e-9)
    speed = max(float(speed_mps), 0.0)
    section_added, section_damping, _ = _section_heave_radiation_arrays(
        hull,
        omega_rad_s=omega,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        section_solver=section_solver,
    )
    variant_specs = [
        ("current", "continuous_gradient", 1.0, 1.0, 1.0, -1.0, True),
        ("no_gradient", "continuous_gradient", 1.0, 1.0, 1.0, -1.0, False),
        ("reverse_gradient", "continuous_gradient", 1.0, 1.0, 1.0, 1.0, True),
        ("negative_speed_term", "continuous_gradient", 1.0, 1.0, -1.0, -1.0, True),
        ("negative_speed_reverse_gradient", "continuous_gradient", 1.0, 1.0, -1.0, 1.0, True),
        ("opposite_pitch_axis", "continuous_gradient", -1.0, -1.0, 1.0, -1.0, True),
        ("opposite_projection_only", "continuous_gradient", -1.0, 1.0, 1.0, -1.0, True),
        ("opposite_velocity_only", "continuous_gradient", 1.0, -1.0, 1.0, -1.0, True),
        ("pdstrip_step", "pdstrip_step", 1.0, 1.0, 1.0, 1.0, True),
        ("pdstrip_step_accumulator_sign", "pdstrip_step", 1.0, 1.0, 1.0, -1.0, True),
        ("pdstrip_step_negative_speed", "pdstrip_step", 1.0, 1.0, -1.0, 1.0, True),
        ("pdstrip_step_opposite_pitch_axis", "pdstrip_step", -1.0, -1.0, 1.0, 1.0, True),
    ]
    dofs = [("3", "heave", 2), ("5", "pitch", 4)]
    rows: list[dict[str, float | str]] = []
    for name, assembly_method, projection_sign, velocity_sign, speed_sign, gradient_sign, include_gradient in variant_specs:
        if assembly_method == "pdstrip_step":
            operator_parts, omega, speed = _forward_speed_2p5d_operator_parts_pdstrip_step_from_sections(
                hull,
                omega_rad_s=omega,
                speed_mps=speed,
                section_added=section_added,
                section_damping=section_damping,
                projection_pitch_sign=projection_sign,
                velocity_pitch_sign=velocity_sign,
                speed_term_sign=speed_sign,
                derivative_dynamic_sign=gradient_sign,
            )
        else:
            operator_parts, omega, speed = _forward_speed_2p5d_operator_parts_from_sections(
                hull,
                omega_rad_s=omega,
                speed_mps=speed,
                section_added=section_added,
                section_damping=section_damping,
                projection_pitch_sign=projection_sign,
                velocity_pitch_sign=velocity_sign,
                speed_term_sign=speed_sign,
                gradient_sign=gradient_sign,
                include_gradient=include_gradient,
            )
        added = -np.real(operator_parts["total"]) / omega**2
        damping = np.imag(operator_parts["total"]) / omega
        for transform, source_added, source_damping in (
            ("direct", added, damping),
            ("transpose_coupling", added.T, damping.T),
        ):
            variant_name = name if transform == "direct" else f"{name}_transpose"
            for local_i, (row_number, row_label, row_index) in enumerate(dofs):
                for local_j, (col_number, col_label, col_index) in enumerate(dofs):
                    rows.append(
                        {
                            "variant": variant_name,
                            "base_variant": name,
                            "transform": transform,
                            "omega_rad_s": float(omega),
                            "speed_mps": float(speed),
                            "row_dof": row_label,
                            "col_dof": col_label,
                            "row_index": row_index,
                            "col_index": col_index,
                            "added_mass_coefficient": f"A{row_number}{col_number}",
                            "damping_coefficient": f"B{row_number}{col_number}",
                            "added_mass_value": float(source_added[local_i, local_j]),
                            "damping_value": float(source_damping[local_i, local_j]),
                            "projection_pitch_sign": float(projection_sign),
                            "velocity_pitch_sign": float(velocity_sign),
                            "speed_term_sign": float(speed_sign),
                            "gradient_sign": float(gradient_sign),
                            "include_gradient": bool(include_gradient),
                            "assembly_method": assembly_method,
                            "section_solver": section_solver.strip().lower(),
                            "status": "diagnostic_forward_speed_coupling_variant_not_validated",
                        }
                    )
    return rows


def experimental_bem_wave_excitation_6dof(
    hull: StationHull,
    wave_amplitude_m: float,
    omega_rad_s: float,
    wavenumber_rad_m: float,
    heading_deg: float = 180.0,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 8,
    body_panel_count: int | None = None,
) -> np.ndarray:
    """Return an experimental section-BEM diffraction/Froude-Krylov excitation vector."""

    data = hull.arrays()
    x = data["x"]
    area = data["area"]
    x_rel = hull.lcg_m - x
    heading = math.radians(float(heading_deg) - 180.0)
    longitudinal = math.cos(heading)
    lateral = math.sin(heading)
    phase = np.exp(-1j * float(wavenumber_rad_m) * longitudinal * x_rel)
    transverse_wavenumber = float(wavenumber_rad_m) * lateral

    vertical = np.zeros_like(x, dtype=complex)
    lateral_force = np.zeros_like(x, dtype=complex)
    roll_moment = np.zeros_like(x, dtype=complex)
    for idx, station in enumerate(hull.stations):
        if data["beam"][idx] <= 1e-7 or data["draft"][idx] <= 1e-7:
            continue
        result = solve_wave_excitation(
            _station_offsets_for_bem(station),
            omega_rad_s=omega_rad_s,
            wave_amplitude_m=wave_amplitude_m,
            wavenumber_rad_m=wavenumber_rad_m,
            transverse_wavenumber_rad_m=transverse_wavenumber,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            free_surface_panel_count_per_side=free_surface_panel_count_per_side,
            body_panel_count=body_panel_count,
        )
        vertical[idx] = result.complex_vertical_force_per_m
        lateral_force[idx] = result.complex_lateral_force_per_m
        roll_moment[idx] = result.complex_roll_moment_per_m

    excitation = np.zeros(6, dtype=complex)
    section_phase_vertical = vertical * phase
    section_phase_lateral = lateral_force * phase
    section_phase_roll = roll_moment * phase
    excitation[0] = np.trapezoid(
        1j * float(wavenumber_rad_m) * longitudinal * rho_water_kg_m3 * gravity_m_s2 * area * wave_amplitude_m * phase,
        x,
    )
    excitation[1] = np.trapezoid(section_phase_lateral, x)
    excitation[2] = np.trapezoid(section_phase_vertical, x)
    excitation[3] = np.trapezoid(section_phase_roll, x)
    excitation[4] = np.trapezoid(section_phase_vertical * x_rel, x)
    excitation[5] = np.trapezoid(section_phase_lateral * x_rel, x)
    return excitation


def prototype_wave_excitation_6dof(
    hull: StationHull,
    wave_amplitude_m: float,
    wavenumber_rad_m: float,
    heading_deg: float = 180.0,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> np.ndarray:
    """Return a prototype complex Froude-Krylov excitation vector.

    Heading follows the package convention: 180 deg is head sea. The output is
    per the 6DOF order [surge, sway, heave, roll, pitch, yaw].
    """

    data = hull.arrays()
    x = data["x"]
    beam = data["beam"]
    draft = data["draft"]
    area = data["area"]
    x_rel = hull.lcg_m - x
    heading = math.radians(float(heading_deg) - 180.0)
    longitudinal = math.cos(heading)
    lateral = math.sin(heading)
    phase = np.exp(-1j * float(wavenumber_rad_m) * longitudinal * x_rel)
    eta = float(wave_amplitude_m) * phase

    excitation = np.zeros(6, dtype=complex)
    vertical_load = rho_water_kg_m3 * gravity_m_s2 * beam * eta
    lateral_load = rho_water_kg_m3 * gravity_m_s2 * draft * lateral * eta
    surge_load = 1j * float(wavenumber_rad_m) * longitudinal * rho_water_kg_m3 * gravity_m_s2 * area * eta
    excitation[0] = np.trapezoid(surge_load, x)
    excitation[1] = np.trapezoid(lateral_load, x)
    excitation[2] = np.trapezoid(vertical_load, x)
    excitation[3] = np.trapezoid(lateral_load * 0.5 * draft, x)
    excitation[4] = np.trapezoid(vertical_load * x_rel, x)
    excitation[5] = np.trapezoid(lateral_load * x_rel, x)
    return excitation


def solve_station_rao_6dof(
    matrices: Station6DOFMatrices,
    rigid_body: RigidBody6DOF,
    excitation: np.ndarray,
    encounter_omega_rad_s: float,
) -> np.ndarray:
    total_mass = rigid_body.matrix() + matrices.added_mass
    omega = float(encounter_omega_rad_s)
    dynamic = -omega**2 * total_mass + 1j * omega * matrices.damping + matrices.restoring
    return np.linalg.solve(dynamic.astype(complex), np.asarray(excitation, dtype=complex))


def _station_wave_frequency(period_s: float, speed_mps: float, heading_deg: float, gravity_m_s2: float) -> tuple[float, float, float]:
    omega0 = 2.0 * math.pi / float(period_s)
    wavenumber = omega0**2 / float(gravity_m_s2)
    heading = math.radians(float(heading_deg) - 180.0)
    omega_e = omega0 + wavenumber * float(speed_mps) * math.cos(heading)
    return float(omega0), float(omega_e), float(wavenumber)


def _assemble_station_matrices_for_model(
    hull: StationHull,
    model: str,
    omega_e_rad_s: float,
    speed_mps: float,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
    radiation_damping_ratio: float,
    bem_free_surface_panel_count_per_side: int,
    bem_body_panel_count: int | None,
) -> Station6DOFMatrices:
    omega = abs(float(omega_e_rad_s))
    speed = abs(float(speed_mps))
    if model in {"pressure_transfer_pdstrip_damping_forward", "pressure_transfer_pdstrip_damping_pdstrip_step"}:
        return assemble_pressure_transfer_pdstrip_damping_forward_speed_matrices(
            hull,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            omega_rad_s=omega,
            free_surface_panel_count_per_side=bem_free_surface_panel_count_per_side,
            body_panel_count=bem_body_panel_count,
            speed_mps=speed,
            assembly_method=(
                "pdstrip_step"
                if model == "pressure_transfer_pdstrip_damping_pdstrip_step"
                else "continuous_gradient"
            ),
        )
    if model in {"pressure_transfer_forward", "pressure_transfer_pdstrip_step"}:
        return assemble_pressure_transfer_forward_speed_matrices(
            hull,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            omega_rad_s=omega,
            free_surface_panel_count_per_side=bem_free_surface_panel_count_per_side,
            body_panel_count=bem_body_panel_count,
            speed_mps=speed,
            assembly_method="pdstrip_step" if model == "pressure_transfer_pdstrip_step" else "continuous_gradient",
        )
    if model in {"strip_2p5d_forward", "strip_2p5d_pdstrip_step"}:
        return assemble_forward_speed_2p5d_matrices(
            hull,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            omega_rad_s=omega,
            free_surface_panel_count_per_side=bem_free_surface_panel_count_per_side,
            body_panel_count=bem_body_panel_count,
            speed_mps=speed,
            section_solver="pdstrip_style",
            assembly_method="pdstrip_step" if model == "strip_2p5d_pdstrip_step" else "continuous_gradient",
        )
    if model == "hybrid_forward_coupling":
        return assemble_hybrid_forward_coupling_matrices(
            hull,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            omega_rad_s=omega,
            free_surface_panel_count_per_side=bem_free_surface_panel_count_per_side,
            body_panel_count=bem_body_panel_count,
            speed_mps=speed,
        )
    if model == "hybrid_pressure_damping_coupling":
        return assemble_hybrid_pressure_damping_coupling_matrices(
            hull,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            omega_rad_s=omega,
            free_surface_panel_count_per_side=bem_free_surface_panel_count_per_side,
            body_panel_count=bem_body_panel_count,
            speed_mps=speed,
        )
    if model in {"section_bem", "pdstrip_style"}:
        return assemble_experimental_bem_6dof_matrices(
            hull,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            omega_rad_s=omega,
            free_surface_panel_count_per_side=bem_free_surface_panel_count_per_side,
            body_panel_count=bem_body_panel_count,
            speed_mps=speed,
            section_solver="pdstrip_style" if model == "pdstrip_style" else "collocation",
        )
    return assemble_prototype_6dof_matrices(
        hull,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        omega_rad_s=omega,
        radiation_damping_ratio=radiation_damping_ratio,
        speed_mps=speed,
    )


def _station_excitation_for_model(
    hull: StationHull,
    model: str,
    omega0_rad_s: float,
    wavenumber_rad_m: float,
    heading_deg: float,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
    bem_free_surface_panel_count_per_side: int,
    bem_body_panel_count: int | None,
) -> tuple[np.ndarray, str]:
    if model in {
        "section_bem",
        "pdstrip_style",
        "strip_2p5d_forward",
        "strip_2p5d_pdstrip_step",
        "pressure_transfer_forward",
        "pressure_transfer_pdstrip_step",
        "pressure_transfer_pdstrip_damping_forward",
        "pressure_transfer_pdstrip_damping_pdstrip_step",
        "hybrid_forward_coupling",
        "hybrid_pressure_damping_coupling",
    }:
        return (
            experimental_bem_wave_excitation_6dof(
                hull,
                wave_amplitude_m=1.0,
                omega_rad_s=omega0_rad_s,
                wavenumber_rad_m=wavenumber_rad_m,
                heading_deg=heading_deg,
                rho_water_kg_m3=rho_water_kg_m3,
                gravity_m_s2=gravity_m_s2,
                free_surface_panel_count_per_side=bem_free_surface_panel_count_per_side,
                body_panel_count=bem_body_panel_count,
            ),
            "section_bem_incident_diffraction_experimental",
        )
    return (
        prototype_wave_excitation_6dof(
            hull,
            wave_amplitude_m=1.0,
            wavenumber_rad_m=wavenumber_rad_m,
            heading_deg=heading_deg,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
        ),
        "prototype_froude_krylov",
    )


def _station_model_name(radiation_model: str) -> str:
    model = radiation_model.strip().lower()
    if model not in {
        "prototype",
        "section_bem",
        "pdstrip_style",
        "strip_2p5d_forward",
        "strip_2p5d_pdstrip_step",
        "pressure_transfer_forward",
        "pressure_transfer_pdstrip_step",
        "pressure_transfer_pdstrip_damping_forward",
        "pressure_transfer_pdstrip_damping_pdstrip_step",
        "hybrid_forward_coupling",
        "hybrid_pressure_damping_coupling",
    }:
        raise ValueError(
            "radiation_model must be 'prototype', 'section_bem', 'pdstrip_style', "
            "'strip_2p5d_forward', 'strip_2p5d_pdstrip_step', 'pressure_transfer_forward', "
            "'pressure_transfer_pdstrip_step', 'pressure_transfer_pdstrip_damping_forward', "
            "'pressure_transfer_pdstrip_damping_pdstrip_step', 'hybrid_forward_coupling', or "
            "'hybrid_pressure_damping_coupling'."
        )
    return model


def station_rao_frequency_sweep(
    hull: StationHull,
    rigid_body: RigidBody6DOF,
    periods_s: np.ndarray,
    speed_mps: float = 0.0,
    heading_deg: float = 180.0,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    radiation_damping_ratio: float = 0.08,
    radiation_model: str = "prototype",
    bem_free_surface_panel_count_per_side: int = 8,
    bem_body_panel_count: int | None = None,
) -> list[dict[str, float]]:
    model = _station_model_name(radiation_model)
    rows: list[dict[str, float]] = []
    for period in np.asarray(periods_s, dtype=float):
        omega0, omega_e, wavenumber = _station_wave_frequency(period, speed_mps, heading_deg, gravity_m_s2)
        matrices = _assemble_station_matrices_for_model(
            hull,
            model,
            omega_e,
            speed_mps,
            rho_water_kg_m3,
            gravity_m_s2,
            radiation_damping_ratio,
            bem_free_surface_panel_count_per_side,
            bem_body_panel_count,
        )
        excitation, excitation_model = _station_excitation_for_model(
            hull,
            model,
            omega0,
            wavenumber,
            heading_deg,
            rho_water_kg_m3,
            gravity_m_s2,
            bem_free_surface_panel_count_per_side,
            bem_body_panel_count,
        )
        response = solve_station_rao_6dof(matrices, rigid_body, excitation, omega_e)
        row = {
            "wave_period_s": float(period),
            "omega0_rad_s": float(omega0),
            "omega_e_rad_s": float(omega_e),
            "wavenumber_rad_m": float(wavenumber),
            "radiation_model": model,
            "excitation_model": excitation_model,
            "matrix_status": matrices.status,
        }
        for label, value in zip(DOF_LABELS, excitation):
            row[f"{label}_excitation_abs_per_m"] = float(abs(value))
            row[f"{label}_excitation_phase_rad"] = float(np.angle(value))
        for label, value in zip(DOF_LABELS, response):
            row[f"{label}_rao_abs_per_m"] = float(abs(value))
            row[f"{label}_phase_rad"] = float(np.angle(value))
        rows.append(row)
    return rows


def station_frequency_matrices_long(
    hull: StationHull,
    periods_s: np.ndarray,
    speed_mps: float = 0.0,
    heading_deg: float = 180.0,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    radiation_damping_ratio: float = 0.08,
    radiation_model: str = "prototype",
    bem_free_surface_panel_count_per_side: int = 8,
    bem_body_panel_count: int | None = None,
) -> list[dict[str, float | str]]:
    model = _station_model_name(radiation_model)
    rows: list[dict[str, float | str]] = []
    for period in np.asarray(periods_s, dtype=float):
        omega0, omega_e, wavenumber = _station_wave_frequency(period, speed_mps, heading_deg, gravity_m_s2)
        matrices = _assemble_station_matrices_for_model(
            hull,
            model,
            omega_e,
            speed_mps,
            rho_water_kg_m3,
            gravity_m_s2,
            radiation_damping_ratio,
            bem_free_surface_panel_count_per_side,
            bem_body_panel_count,
        )
        for matrix_name, matrix in (
            ("added_mass", matrices.added_mass),
            ("damping", matrices.damping),
            ("restoring", matrices.restoring),
        ):
            for row_index, row_label in enumerate(DOF_LABELS):
                for col_index, col_label in enumerate(DOF_LABELS):
                    rows.append(
                        {
                            "wave_period_s": float(period),
                            "omega0_rad_s": float(omega0),
                            "omega_e_rad_s": float(omega_e),
                            "wavenumber_rad_m": float(wavenumber),
                            "radiation_model": model,
                            "matrix_status": matrices.status,
                            "matrix_type": matrix_name,
                            "row_dof": row_label,
                            "col_dof": col_label,
                            "row_index": row_index,
                            "col_index": col_index,
                            "value": float(matrix[row_index, col_index]),
                        }
                    )
    return rows
