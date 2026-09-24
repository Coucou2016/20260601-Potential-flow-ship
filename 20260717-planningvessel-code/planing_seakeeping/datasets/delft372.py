from __future__ import annotations

import csv
from dataclasses import dataclass
from html.parser import HTMLParser
import re
from pathlib import Path

import numpy as np

from ..surface_mesh import TriangleMesh, combine_triangle_meshes, translated_mesh


DELFT372_LPP_M = 3.0
DELFT372_AP_TABLE_X = -15.0
DELFT372_TABLE_SCALE_M = 0.1
DELFT372_WATERLINE_Z_TABLE = 1.5


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            self._current_table = []
        elif tag == "tr" and self._current_table is not None:
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            text = " ".join("".join(self._current_cell).split())
            self._current_row.append(text)
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None


@dataclass(frozen=True)
class Delft372StationOffsets:
    station_id: str
    table_x: float
    x_from_ap_m: float
    raw_pairs_table: tuple[tuple[float, float], ...]
    wetted_points_m: tuple[tuple[float, float], ...]

    @property
    def full_positive_points_m(self) -> tuple[tuple[float, float], ...]:
        """Return positive-half-breadth points as (y, z-up), deck edge to keel."""

        return tuple(
            (float(y * DELFT372_TABLE_SCALE_M), float((z - DELFT372_WATERLINE_Z_TABLE) * DELFT372_TABLE_SCALE_M))
            for z, y in sorted(self.raw_pairs_table, key=lambda pair: pair[0], reverse=True)
        )

    @property
    def waterline_half_breadth_m(self) -> float:
        return float(max(abs(point[0]) for point in self.wetted_points_m if abs(point[1]) <= 1e-10))

    @property
    def draft_m(self) -> float:
        return float(max(point[1] for point in self.wetted_points_m))


@dataclass(frozen=True)
class Delft372OffsetExtraction:
    stations: tuple[Delft372StationOffsets, ...]
    source_markdown: str
    bow_profile_table: tuple[tuple[float, float], ...] = ()
    waterline_z_table: float = DELFT372_WATERLINE_Z_TABLE
    table_scale_m: float = DELFT372_TABLE_SCALE_M
    note: str = (
        "Coordinates extracted from B2 TABLE OF OFFSETS. Table coordinates are scaled by 0.1 m; "
        "x_from_ap_m=(x_table+15)*0.1, y_m=y_table*0.1, z_down_m=(1.5-z_table)*0.1."
    )


@dataclass(frozen=True)
class Delft372HeadSeaMotion:
    test_no: str
    froude_number: float
    speed_m_s: float
    omega_0_rad_s: float
    omega_encounter_rad_s: float
    wavelength_over_lpp: float
    wave_amplitude_cm: float
    surge_rao_cm_per_cm: float
    surge_phase_deg: float
    sway_rao_cm_per_cm: float
    sway_phase_deg: float
    heave_rao_cm_per_cm: float
    heave_phase_deg: float
    roll_rao_deg_per_cm: float
    roll_phase_deg: float
    pitch_rao_deg_per_cm: float
    pitch_phase_deg: float
    yaw_rao_deg_per_cm: float
    yaw_phase_deg: float


def _parse_float(text: str) -> float | None:
    clean = text.strip().replace("−", "-").replace("–", "-").replace("O", "0").replace("o", "0")
    if clean == "":
        return None
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", clean)
    if match is None:
        return None
    return float(match.group(0))


def _tables_after_offsets_heading(markdown_text: str) -> list[list[list[str]]]:
    marker = "## TABLE OF OFFSETS"
    start = markdown_text.find(marker)
    if start < 0:
        raise ValueError("B2 Markdown does not contain '## TABLE OF OFFSETS'.")
    end = markdown_text.find("FORWARD", start)
    if end < 0:
        end = len(markdown_text)
    parser = _TableParser()
    parser.feed(markdown_text[start:end])
    return parser.tables


def _all_html_tables(markdown_text: str) -> list[list[list[str]]]:
    parser = _TableParser()
    parser.feed(markdown_text)
    return parser.tables


def _station_headers(table: list[list[str]]) -> list[float | None]:
    if not table:
        return []
    headers: list[float | None] = []
    for cell in table[0]:
        lower = cell.lower().replace(" ", "")
        if lower.startswith("x="):
            value = lower.split("=", 1)[1]
            if re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", value):
                headers.append(float(value))
            else:
                headers.append(None)
        else:
            headers.append(None)
    return headers


def _pairs_for_station(table: list[list[str]], station_pair_index: int) -> tuple[tuple[float, float], ...]:
    column = 2 * station_pair_index
    pairs: list[tuple[float, float]] = []
    for row in table[2:]:
        if column + 1 >= len(row):
            continue
        z = _parse_float(row[column])
        y = _parse_float(row[column + 1])
        if z is None or y is None:
            continue
        pairs.append((z, y))
    return tuple(pairs)


def _bow_profile_from_offsets_table(table: list[list[str]]) -> tuple[tuple[float, float], ...]:
    if not table or "bow" not in " ".join(table[0]).lower():
        return ()
    points: list[tuple[float, float]] = []
    for row in table[2:]:
        if len(row) < 12:
            continue
        x_value = _parse_float(row[10])
        z_value = _parse_float(row[11])
        if x_value is not None and z_value is not None:
            points.append((x_value, z_value))
    return tuple(points)


def _interpolate_y_at_waterline(raw_pairs: tuple[tuple[float, float], ...], waterline_z: float) -> float:
    by_z = sorted(raw_pairs, key=lambda pair: pair[0], reverse=True)
    for z, y in by_z:
        if abs(z - waterline_z) <= 1e-9:
            return y
    for (z0, y0), (z1, y1) in zip(by_z[:-1], by_z[1:]):
        if (z0 - waterline_z) * (z1 - waterline_z) <= 0.0 and abs(z0 - z1) > 1e-12:
            ratio = (waterline_z - z1) / (z0 - z1)
            return y1 + ratio * (y0 - y1)
    raise ValueError("Cannot interpolate Delft 372 waterline breadth for a station.")


def _wetted_points(
    raw_pairs: tuple[tuple[float, float], ...],
    *,
    waterline_z: float,
    scale_m: float,
) -> tuple[tuple[float, float], ...]:
    y_wl = _interpolate_y_at_waterline(raw_pairs, waterline_z)
    positive = [(y_wl * scale_m, 0.0)]
    for z, y in sorted(raw_pairs, key=lambda pair: pair[0], reverse=True):
        if z >= waterline_z - 1e-10:
            continue
        positive.append((y * scale_m, (waterline_z - z) * scale_m))
    if len(positive) < 2:
        raise ValueError("Delft 372 station has fewer than two submerged points.")
    if abs(positive[-1][0]) > 1e-5:
        positive.append((0.0, positive[-1][1]))
    mirrored = [(-y, z) for y, z in reversed(positive[:-1])]
    return tuple(positive + mirrored)


def extract_delft372_offsets_from_markdown(
    markdown_path: str | Path,
    *,
    waterline_z_table: float = DELFT372_WATERLINE_Z_TABLE,
    table_scale_m: float = DELFT372_TABLE_SCALE_M,
    ap_table_x: float = DELFT372_AP_TABLE_X,
) -> Delft372OffsetExtraction:
    path = Path(markdown_path)
    text = path.read_text(encoding="utf-8")
    tables = _tables_after_offsets_heading(text)
    bow_profile: tuple[tuple[float, float], ...] = ()
    stations: list[Delft372StationOffsets] = []
    for table in tables[:4]:
        candidate_bow = _bow_profile_from_offsets_table(table)
        if candidate_bow:
            bow_profile = candidate_bow
        headers = _station_headers(table)
        for pair_index, table_x in enumerate(headers):
            if table_x is None:
                continue
            raw_pairs = _pairs_for_station(table, pair_index)
            if not raw_pairs:
                continue
            station_id = f"S{len(stations):02d}"
            x_from_ap = (float(table_x) - ap_table_x) * table_scale_m
            try:
                wetted_points = _wetted_points(
                    raw_pairs,
                    waterline_z=waterline_z_table,
                    scale_m=table_scale_m,
                )
            except ValueError as exc:
                raise ValueError(
                    f"Cannot build Delft 372 wetted station at table x={table_x}: raw_pairs={raw_pairs!r}"
                ) from exc
            stations.append(
                Delft372StationOffsets(
                    station_id=station_id,
                    table_x=float(table_x),
                    x_from_ap_m=float(x_from_ap),
                    raw_pairs_table=raw_pairs,
                    wetted_points_m=wetted_points,
                )
            )
    if len(stations) < 20:
        raise ValueError(f"Only extracted {len(stations)} Delft 372 stations; expected the page-14 table.")
    return Delft372OffsetExtraction(
        stations=tuple(sorted(stations, key=lambda station: station.x_from_ap_m)),
        source_markdown=str(path),
        bow_profile_table=bow_profile,
        waterline_z_table=waterline_z_table,
        table_scale_m=table_scale_m,
    )


def _resample_section(points_yz: tuple[tuple[float, float], ...], point_count: int) -> np.ndarray:
    points = np.asarray(points_yz, dtype=float)
    if point_count < 4:
        raise ValueError("At least four points are required along each Delft 372 half-section.")
    distance = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))))
    if distance[-1] <= 0.0:
        raise ValueError("Cannot resample a zero-length Delft 372 section.")
    target = np.linspace(0.0, distance[-1], point_count)
    return np.column_stack((np.interp(target, distance, points[:, 0]), np.interp(target, distance, points[:, 1])))


def build_delft372_demihull_surface_mesh(
    extraction: Delft372OffsetExtraction,
    *,
    half_section_point_count: int = 17,
) -> TriangleMesh:
    """Loft the public offsets into a closed full demihull shell.

    The source offsets contain the full vertical section up to z_table=2.0,
    not only the below-water polygon used for hydrostatics. The reported bow
    profile closes the final station and the transom is capped explicitly.
    """

    if not extraction.bow_profile_table:
        raise ValueError("Delft 372 bow profile was not found in the offsets table.")
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    rings: list[list[int]] = []
    positive_sections: list[np.ndarray] = []

    for station in extraction.stations:
        positive = _resample_section(station.full_positive_points_m, half_section_point_count)
        positive_sections.append(positive)
        ring: list[int] = []
        for y_m, z_m in positive:
            ring.append(len(vertices))
            vertices.append((station.x_from_ap_m, float(y_m), float(z_m)))
        for y_m, z_m in positive[-2::-1]:
            ring.append(len(vertices))
            vertices.append((station.x_from_ap_m, float(-y_m), float(z_m)))
        rings.append(ring)

    ring_size = len(rings[0])
    for aft, forward in zip(rings[:-1], rings[1:]):
        for index in range(ring_size):
            next_index = (index + 1) % ring_size
            faces.append((aft[index], forward[index], forward[next_index]))
            faces.append((aft[index], forward[next_index], aft[next_index]))

    transom_center = len(vertices)
    aft_coordinates = np.asarray([vertices[index] for index in rings[0]], dtype=float)
    vertices.append(tuple(np.mean(aft_coordinates, axis=0)))
    for index in range(ring_size):
        faces.append((rings[0][(index + 1) % ring_size], transom_center, rings[0][index]))

    last_station = extraction.stations[-1]
    last_positive = positive_sections[-1]
    bow_points = list(extraction.bow_profile_table)
    bow_points.append((last_station.table_x, float(np.min([pair[0] for pair in last_station.raw_pairs_table]))))
    bow_points = sorted(set(bow_points), key=lambda pair: pair[1])
    bow_z = np.asarray([pair[1] for pair in bow_points], dtype=float)
    bow_x = np.asarray([pair[0] for pair in bow_points], dtype=float)
    last_ring = rings[-1]
    profile_indices: list[int] = []
    for _, z_up_m in last_positive[:-1]:
        z_table = z_up_m / extraction.table_scale_m + extraction.waterline_z_table
        x_table = float(np.interp(z_table, bow_z, bow_x))
        profile_indices.append(len(vertices))
        vertices.append(((x_table - DELFT372_AP_TABLE_X) * extraction.table_scale_m, 0.0, float(z_up_m)))
    profile_indices.append(last_ring[half_section_point_count - 1])

    def port_index(depth_index: int) -> int:
        if depth_index == half_section_point_count - 1:
            return last_ring[half_section_point_count - 1]
        return last_ring[ring_size - 1 - depth_index]

    for depth_index in range(half_section_point_count - 1):
        star_0 = last_ring[depth_index]
        star_1 = last_ring[depth_index + 1]
        port_0 = port_index(depth_index)
        port_1 = port_index(depth_index + 1)
        bow_0 = profile_indices[depth_index]
        bow_1 = profile_indices[depth_index + 1]
        if depth_index == half_section_point_count - 2:
            faces.append((star_0, bow_0, star_1))
            faces.append((port_0, port_1, bow_0))
        else:
            faces.extend(((star_0, bow_0, bow_1), (star_0, bow_1, star_1)))
            faces.extend(((port_0, port_1, bow_1), (port_0, bow_1, bow_0)))
    faces.append((last_ring[0], last_ring[-1], profile_indices[0]))

    return TriangleMesh(np.asarray(vertices), np.asarray(faces), name="delft372_demihull_full")


def build_delft372_catamaran_surface_mesh(
    extraction: Delft372OffsetExtraction,
    *,
    centerline_spacing_m: float = 0.70,
    half_section_point_count: int = 17,
) -> TriangleMesh:
    demihull = build_delft372_demihull_surface_mesh(
        extraction,
        half_section_point_count=half_section_point_count,
    )
    offset = 0.5 * centerline_spacing_m
    port = translated_mesh(demihull, (0.0, -offset, 0.0), name="delft372_port_demihull")
    starboard = translated_mesh(demihull, (0.0, offset, 0.0), name="delft372_starboard_demihull")
    return combine_triangle_meshes((port, starboard), name="delft372_catamaran_full")


def extract_delft372_head_sea_motions_from_markdown(markdown_path: str | Path) -> tuple[Delft372HeadSeaMotion, ...]:
    path = Path(markdown_path)
    text = path.read_text(encoding="utf-8")
    tables = _all_html_tables(text)
    overview: dict[str, tuple[float, float, float]] = {}
    for table in tables:
        if not table or not table[0] or "Marin test no." not in table[0][0]:
            continue
        for row in table[1:]:
            if len(row) < 6 or not re.fullmatch(r"\d{6}", row[0].strip()):
                continue
            speed = _parse_float(row[1])
            omega_0 = _parse_float(row[2])
            amplitude = _parse_float(row[5])
            if speed is not None and omega_0 is not None and amplitude is not None:
                overview[row[0].strip()[:4]] = (speed, omega_0, amplitude)

    motion_table = next(
        (
            table
            for table in tables
            if table and table[0] and "MOTION RESULTS, 180 DEGREES" in " ".join(table[0])
        ),
        None,
    )
    if motion_table is None:
        raise ValueError("B2 Markdown does not contain the 180-degree motion-results table.")

    current_fn: float | None = None
    in_head_sea_group = False
    motions: list[Delft372HeadSeaMotion] = []
    for row in motion_table:
        row_text = " ".join(row)
        heading = re.search(r"MOTION RESULTS,\s*(\d+)\s*DEGREES", row_text, flags=re.IGNORECASE)
        if heading is not None:
            in_head_sea_group = int(heading.group(1)) == 180
            current_fn = None
            continue
        if not in_head_sea_group:
            continue
        if row and row[0].startswith("Fn"):
            current_fn = _parse_float(row[0])
            continue
        if current_fn is None or len(row) < 16 or not re.fullmatch(r"\d{4}", row[0].strip()):
            continue
        values = [_parse_float(value) for value in row[1:16]]
        if any(value is None for value in values) or row[0].strip() not in overview:
            continue
        speed, overview_omega_0, wave_amplitude = overview[row[0].strip()]
        values_f = [float(value) for value in values if value is not None]
        motions.append(
            Delft372HeadSeaMotion(
                test_no=row[0].strip(),
                froude_number=float(current_fn),
                speed_m_s=float(speed),
                omega_0_rad_s=float(overview_omega_0),
                omega_encounter_rad_s=values_f[1],
                wavelength_over_lpp=values_f[2],
                wave_amplitude_cm=float(wave_amplitude),
                surge_rao_cm_per_cm=values_f[3],
                surge_phase_deg=values_f[4],
                sway_rao_cm_per_cm=values_f[5],
                sway_phase_deg=values_f[6],
                heave_rao_cm_per_cm=values_f[7],
                heave_phase_deg=values_f[8],
                roll_rao_deg_per_cm=values_f[9],
                roll_phase_deg=values_f[10],
                pitch_rao_deg_per_cm=values_f[11],
                pitch_phase_deg=values_f[12],
                yaw_rao_deg_per_cm=values_f[13],
                yaw_phase_deg=values_f[14],
            )
        )
    if len(motions) < 20:
        raise ValueError(f"Only extracted {len(motions)} Delft 372 head-sea motion rows; expected at least 20.")
    return tuple(motions)


def _polygon_area(points: tuple[tuple[float, float], ...]) -> float:
    values = np.asarray(points, dtype=float)
    y = values[:, 0]
    z = values[:, 1]
    return float(abs(0.5 * np.sum(y * np.roll(z, -1) - np.roll(y, -1) * z)))


def write_delft372_offsets_dataset(extraction: Delft372OffsetExtraction, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    offsets_path = out / "delft372_demihull_offsets.csv"
    raw_path = out / "delft372_demihull_offsets_raw.csv"
    audit_path = out / "delft372_demihull_geometry_audit.csv"

    with offsets_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "station_id",
                "x_m",
                "point_order",
                "y_m",
                "z_down_m",
                "feature",
                "source",
                "table_x",
                "waterline_z_table",
                "scale_m",
            ],
        )
        writer.writeheader()
        for station in extraction.stations:
            for point_order, (y_m, z_down_m) in enumerate(station.wetted_points_m):
                feature = "waterline" if abs(z_down_m) <= 1e-10 else "keel" if abs(y_m) <= 1e-10 else "wetted_offset"
                writer.writerow(
                    {
                        "station_id": station.station_id,
                        "x_m": f"{station.x_from_ap_m:.6f}",
                        "point_order": point_order,
                        "y_m": f"{y_m:.6f}",
                        "z_down_m": f"{z_down_m:.6f}",
                        "feature": feature,
                        "source": "B2.md TABLE OF OFFSETS",
                        "table_x": f"{station.table_x:.3f}",
                        "waterline_z_table": f"{extraction.waterline_z_table:.3f}",
                        "scale_m": f"{extraction.table_scale_m:.3f}",
                    }
                )

    with raw_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["station_id", "table_x", "x_m", "raw_order", "z_table", "y_table"])
        writer.writeheader()
        for station in extraction.stations:
            for raw_order, (z, y) in enumerate(station.raw_pairs_table):
                writer.writerow(
                    {
                        "station_id": station.station_id,
                        "table_x": f"{station.table_x:.3f}",
                        "x_m": f"{station.x_from_ap_m:.6f}",
                        "raw_order": raw_order,
                        "z_table": f"{z:.6f}",
                        "y_table": f"{y:.6f}",
                    }
                )

    with audit_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "station_id",
                "table_x",
                "x_m",
                "raw_pair_count",
                "wetted_point_count",
                "waterline_half_breadth_m",
                "draft_m",
                "submerged_area_m2",
                "status",
                "note",
            ],
        )
        writer.writeheader()
        for station in extraction.stations:
            area = _polygon_area(station.wetted_points_m)
            status = "PASS"
            notes: list[str] = []
            if area <= 0.0:
                status = "FAIL"
                notes.append("non-positive wetted polygon area")
            if station.x_from_ap_m < -1e-9 or station.x_from_ap_m > DELFT372_LPP_M + 1e-9:
                status = "WARN"
                notes.append("station lies outside LPP")
            writer.writerow(
                {
                    "station_id": station.station_id,
                    "table_x": f"{station.table_x:.3f}",
                    "x_m": f"{station.x_from_ap_m:.6f}",
                    "raw_pair_count": len(station.raw_pairs_table),
                    "wetted_point_count": len(station.wetted_points_m),
                    "waterline_half_breadth_m": f"{station.waterline_half_breadth_m:.6f}",
                    "draft_m": f"{station.draft_m:.6f}",
                    "submerged_area_m2": f"{area:.9f}",
                    "status": status,
                    "note": "; ".join(notes),
                }
            )

    return {"offsets": offsets_path, "raw": raw_path, "audit": audit_path}
