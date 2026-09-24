from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .station_2p5d import HardChineStation, StationHull, load_station_offsets_csv, make_sl7_surrogate_hull


@dataclass(frozen=True)
class GeometrySource:
    source_id: str
    source_type: str
    description: str
    usable_for_validation: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class HullComponent:
    name: str
    role: str
    hull: StationHull
    origin_from_vessel_ap_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    source: GeometrySource = GeometrySource(
        source_id="unspecified",
        source_type="unspecified",
        description="No geometry provenance supplied.",
        usable_for_validation=False,
    )


@dataclass(frozen=True)
class MultiBodySection:
    x_global_m: float
    components: tuple[str, ...]
    local_x_m: tuple[float, ...]

    @property
    def active_component_count(self) -> int:
        return len(self.components)


def _group_unified_offsets(rows: list[dict[str, str]]) -> dict[str, dict[str, list[dict[str, str]]]]:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = {}
    for row_index, row in enumerate(rows):
        component = (row.get("component") or "main").strip()
        station_id = (row.get("station_id") or row.get("x_from_ap_m") or "").strip()
        if station_id == "":
            raise ValueError(f"Unified offsets row {row_index + 2} lacks station_id or x_from_ap_m.")
        grouped.setdefault(component, {}).setdefault(station_id, []).append(row)
    return grouped


def load_unified_offsets_csv(
    path: str | Path,
    *,
    z_is_down: bool = True,
    scale: float = 1.0,
    length_by_component_m: dict[str, float] | None = None,
    lcg_by_component_m: dict[str, float] | None = None,
) -> dict[str, StationHull]:
    """Load the unified component/station/point CSV proposed in the implementation plan.

    Required columns are `component`, `station_id`, `x_from_ap_m`,
    `point_order`, `y_m`, and `z_m`. If an existing legacy
    `x_m,y_m,z_down_m` CSV is supplied, it is loaded as a single `main`
    component for backward compatibility.
    """

    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Offsets CSV must have a header row.")
        fields = {field.strip() for field in reader.fieldnames}
        if {"x_m", "y_m", "z_down_m"} <= fields and "component" not in fields:
            stations = load_station_offsets_csv(csv_path)
            length = max(station.x_m for station in stations)
            return {"main": StationHull(length_m=length, stations=stations)}
        required = {"component", "station_id", "x_from_ap_m", "point_order", "y_m", "z_m"}
        missing = required - fields
        if missing:
            raise ValueError(f"Unified offsets CSV is missing required columns: {sorted(missing)}")
        rows = list(reader)

    hulls: dict[str, StationHull] = {}
    length_by_component_m = length_by_component_m or {}
    lcg_by_component_m = lcg_by_component_m or {}
    for component, station_groups in _group_unified_offsets(rows).items():
        stations: list[HardChineStation] = []
        for station_rows in station_groups.values():
            ordered = sorted(station_rows, key=lambda row: float(row["point_order"]))
            x_m = float(ordered[0]["x_from_ap_m"]) * scale
            points = tuple(
                (
                    float(row["y_m"]) * scale,
                    (float(row["z_m"]) if z_is_down else -float(row["z_m"])) * scale,
                )
                for row in ordered
            )
            point_array = np.asarray(points, dtype=float)
            stations.append(
                HardChineStation(
                    x_m=x_m,
                    beam_m=float(np.max(point_array[:, 0]) - np.min(point_array[:, 0])),
                    draft_m=float(np.max(point_array[:, 1]) - np.min([0.0, np.min(point_array[:, 1])])),
                    deadrise_deg=90.0,
                    offset_points_m=points,
                )
            )
        length = float(length_by_component_m.get(component, max(station.x_m for station in stations)))
        hulls[component] = StationHull(
            length_m=length,
            stations=tuple(stations),
            lcg_from_transom_m=lcg_by_component_m.get(component),
        )
    return hulls


def make_delft372_demihull_from_offsets(offsets_csv_path: str | Path) -> HullComponent:
    """Load the audited Delft 372 demihull offsets extracted from B2.

    The returned component is marked as validation-ready at the geometry level:
    hydrodynamic and motion validation still require the B1/B2 benchmark curves
    and the appropriate catamaran interaction model.
    """

    hull = StationHull(
        length_m=3.0,
        stations=load_station_offsets_csv(offsets_csv_path),
        lcg_from_transom_m=1.41,
    )
    return HullComponent(
        name="delft372_demihull",
        role="demihull",
        hull=hull,
        source=GeometrySource(
            source_id="delft372_b2_page14_offsets",
            source_type="digitized_offsets",
            description="Delft 372 demihull offsets extracted from B2 TABLE OF OFFSETS.",
            usable_for_validation=True,
            notes=(
                "Geometry-level audit should reproduce the reported 87.07 kg total displacement within 2%.",
                "Hydrodynamic validation still needs B1/B2 digitized RAO and load curves.",
            ),
        ),
    )


def make_delft372_catamaran_from_offsets(
    offsets_csv_path: str | Path,
    *,
    demihull_centerline_spacing_m: float = 0.70,
) -> tuple[HullComponent, HullComponent]:
    """Load the Delft 372 catamaran as port/starboard demihull components."""

    if demihull_centerline_spacing_m <= 0.0:
        raise ValueError("demihull_centerline_spacing_m must be positive.")
    hull = StationHull(
        length_m=3.0,
        stations=load_station_offsets_csv(offsets_csv_path),
        lcg_from_transom_m=1.41,
    )
    half_spacing = 0.5 * float(demihull_centerline_spacing_m)
    source = GeometrySource(
        source_id="delft372_b2_page14_offsets",
        source_type="digitized_offsets",
        description="Delft 372 port/starboard demihulls assembled from B2 TABLE OF OFFSETS.",
        usable_for_validation=True,
        notes=(
            "Demihull centerline spacing is 0.70 m from B2 principal particulars.",
            "This is a geometry/topology gate; coupled multihull hydrodynamics still requires shared-section BIE.",
        ),
    )
    return (
        HullComponent(
            name="port_demihull",
            role="port_demihull",
            hull=hull,
            origin_from_vessel_ap_m=(0.0, -half_spacing, 0.0),
            source=source,
        ),
        HullComponent(
            name="starboard_demihull",
            role="starboard_demihull",
            hull=hull,
            origin_from_vessel_ap_m=(0.0, half_spacing, 0.0),
            source=source,
        ),
    )


def make_delft372_demihull_surrogate(station_count: int = 41) -> HullComponent:
    """Return a clearly marked Delft 372 demihull surrogate.

    The real Delft 372 offsets should be digitized from B2 page 14 before this
    geometry is used for validation. This surrogate only keeps principal
    dimensions and gives tests/configurations a stable geometry object.
    """

    hull = make_sl7_surrogate_hull(
        length_m=3.0,
        beam_m=0.24,
        draft_m=0.15,
        station_count=station_count,
        lcg_from_transom_m=1.41,
    )
    return HullComponent(
        name="delft372_demihull",
        role="demihull_surrogate",
        hull=hull,
        source=GeometrySource(
            source_id="delft372_b2_page14_surrogate",
            source_type="surrogate_from_principal_dimensions",
            description="Delft 372 demihull surrogate using B2 principal dimensions; not the page-14 offsets.",
            usable_for_validation=False,
            notes=(
                "Use only until the B2 page-14 table has been digitized and audited.",
                "Demihull length 3.00 m, beam 0.24 m, draft 0.15 m, LCG 1.41 m.",
            ),
        ),
    )


def make_trimaran2019_surrogate(layout_a_over_l: float = 0.0, layout_p_over_l: float = 0.096) -> tuple[HullComponent, ...]:
    """Build a C1-style trimaran surrogate from principal dimensions.

    C1 does not provide machine-readable offsets in the supplied material. The
    returned geometry is useful for workflow tests and interference API
    development, but not for C1 validation.
    """

    main_length = 3.0
    main = HullComponent(
        name="main",
        role="main_hull",
        hull=make_sl7_surrogate_hull(length_m=main_length, beam_m=0.240, draft_m=0.122, station_count=41),
        source=GeometrySource(
            source_id="trimaran2019_main_surrogate",
            source_type="surrogate_from_principal_dimensions",
            description="C1 trimaran main-hull surrogate from reported principal dimensions.",
            usable_for_validation=False,
        ),
    )
    side_length = 1.071
    x_offset = layout_a_over_l * main_length
    y_offset = layout_p_over_l * main_length
    side_hull = make_sl7_surrogate_hull(length_m=side_length, beam_m=0.051, draft_m=0.043, station_count=25)
    source = GeometrySource(
        source_id="trimaran2019_side_surrogate",
        source_type="surrogate_from_principal_dimensions",
        description="C1 trimaran side-hull surrogate from reported principal dimensions.",
        usable_for_validation=False,
        notes=("Real C1 offsets are still required for validation.",),
    )
    return (
        main,
        HullComponent("port_outrigger", "port_outrigger", side_hull, (x_offset, -y_offset, 0.0), source),
        HullComponent("starboard_outrigger", "starboard_outrigger", side_hull, (x_offset, y_offset, 0.0), source),
    )


def multibody_sections(components: tuple[HullComponent, ...], x_values_m: np.ndarray) -> tuple[MultiBodySection, ...]:
    sections: list[MultiBodySection] = []
    for x_global in np.asarray(x_values_m, dtype=float):
        names: list[str] = []
        local_x: list[float] = []
        for component in components:
            x_local = float(x_global - component.origin_from_vessel_ap_m[0])
            if -1e-9 <= x_local <= component.hull.length_m + 1e-9:
                names.append(component.name)
                local_x.append(x_local)
        sections.append(MultiBodySection(float(x_global), tuple(names), tuple(local_x)))
    return tuple(sections)


def geometry_source_audit(components: tuple[HullComponent, ...]) -> list[dict[str, object]]:
    rows = []
    for component in components:
        rows.append(
            {
                "component": component.name,
                "role": component.role,
                "source_id": component.source.source_id,
                "source_type": component.source.source_type,
                "usable_for_validation": component.source.usable_for_validation,
                "station_count": len(component.hull.stations),
                "length_m": component.hull.length_m,
                "note": " ".join(component.source.notes),
            }
        )
    return rows
