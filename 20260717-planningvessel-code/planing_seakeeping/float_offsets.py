"""Source offsets to an open bottom mesh; never invent deck or step faces."""
from dataclasses import dataclass
import csv
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class FloatStation:
    label: str
    x_aft_m: float
    halfbreadth_m: np.ndarray
    height_up_m: np.ndarray
    deck_height_m: float


def read_float_offsets(path: str | Path) -> list[FloatStation]:
    """Read full-size inch offsets. F/A are fore/aft limits of a step."""
    stations = []
    with Path(path).open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            label = row["station"]
            x = float(label.rstrip("FA")) * 0.0254
            breadth = [0.0]
            height = [float(row["keel_height"])]
            if bool(row["sister_halfbreadth"]) != bool(row["sister_height"]):
                raise ValueError("Incomplete sister-keelson coordinates")
            if row["sister_halfbreadth"]:
                breadth.append(float(row["sister_halfbreadth"]))
                height.append(float(row["sister_height"]))
            breadth.append(float(row["chine_halfbreadth"]))
            height.append(float(row["chine_height"]))
            b, z = np.asarray(breadth)*0.0254, np.asarray(height)*0.0254
            deck = float(row["deck_height"])*0.0254
            if not np.all(np.isfinite([x, deck, *b, *z])) or x < 0 or np.any(b < 0):
                raise ValueError("Nonfinite or negative geometry")
            if b[-1] > 0 and np.any(np.diff(b) <= 0):
                raise ValueError("Half breadth must increase from keel to chine")
            if deck < np.max(z):
                raise ValueError("Deck is below bottom offsets")
            if stations:
                previous = stations[-1]
                if x < previous.x_aft_m or (x == previous.x_aft_m and
                        not (previous.label.endswith("F") and label.endswith("A"))):
                    raise ValueError("Stations must increase, except explicit F/A step pairs")
            stations.append(FloatStation(label, x, b, z, deck))
    if len(stations) < 2:
        raise ValueError("At least two stations required")
    return stations


def bottom_mesh(stations: list[FloatStation], transverse_points: int = 17):
    """Piecewise-linear reconstruction, x aft, y transverse, z up, metres.

    Open chine boundaries and step breaks are intentional. This is geometry,
    not the instantaneous wetted surface or a computed free surface.
    """
    if transverse_points < 3 or transverse_points % 2 != 1:
        raise ValueError("Use an odd number of transverse points >= 3")
    vertices, faces = [], []
    for station in stations:
        y = np.linspace(-station.halfbreadth_m[-1], station.halfbreadth_m[-1], transverse_points)
        z = (np.full_like(y, station.height_up_m[0]) if station.halfbreadth_m[-1] == 0
             else np.interp(np.abs(y), station.halfbreadth_m, station.height_up_m))
        vertices.extend(zip(np.full_like(y, station.x_aft_m), y, z))
    vertices = np.asarray(vertices)
    for i in range(len(stations)-1):
        if stations[i].x_aft_m == stations[i+1].x_aft_m:
            continue
        for j in range(transverse_points-1):
            a = i*transverse_points+j
            b = a+transverse_points
            for face in ((a,b,a+1),(a+1,b,b+1)):
                p = vertices[list(face)]
                if np.linalg.norm(np.cross(p[1]-p[0],p[2]-p[0])) > 1e-14:
                    faces.append(face)
    return vertices, np.asarray(faces, dtype=int)


def assemble_float_layout(stations, translations_m, transverse_points=17):
    """Explicit user layout, not an assertion of a historical aircraft layout.

    Supports two or more floats without claiming hydrodynamic interference.
    Component IDs preserve separate bodies for a future joint boundary solve.
    """
    translations = np.asarray(translations_m, dtype=float)
    if translations.ndim != 2 or translations.shape[1] != 3 or len(translations) < 1:
        raise ValueError("Expected one or more three-vector translations")
    if not np.isfinite(translations).all():
        raise ValueError("Translations must be finite")
    v, f = bottom_mesh(stations, transverse_points)
    boxes = [(v.min(axis=0)+t, v.max(axis=0)+t) for t in translations]
    for i, (low, high) in enumerate(boxes):
        for low2, high2 in boxes[:i]:
            if np.all(high >= low2) and np.all(high2 >= low):
                raise ValueError("Overlapping bounding boxes require a dedicated geometry check")
    return (np.vstack([v+t for t in translations]),
            np.vstack([f+i*len(v) for i in range(len(translations))]),
            np.repeat(np.arange(len(translations)), len(f)))
