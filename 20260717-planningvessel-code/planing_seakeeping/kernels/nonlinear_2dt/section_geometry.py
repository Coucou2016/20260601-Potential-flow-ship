from __future__ import annotations

import numpy as np

from .boundary_element import ClosedBoundary2D


def build_symmetric_wedge_fluid_boundary(
    *,
    half_beam_m: float,
    draft_m: float,
    free_surface_extent_m: float,
    water_depth_m: float,
    body_panels_per_side: int = 24,
    free_surface_panels_per_side: int = 32,
    side_wall_panels: int = 8,
    bottom_panels: int = 32,
) -> ClosedBoundary2D:
    """Build a closed fluid boundary around a surface-piercing V section.

    The free surface is initially flat at ``z=0`` and ``z`` is positive
    upward. Boundary traversal starts at the starboard waterline, follows the
    outer tank clockwise, then returns along the port-to-starboard wetted body.
    The resulting polygon interior is the fluid domain.
    """

    half_beam = float(half_beam_m)
    draft = float(draft_m)
    extent = float(free_surface_extent_m)
    depth = float(water_depth_m)
    if half_beam <= 0.0 or draft <= 0.0 or extent <= half_beam or depth <= draft:
        raise ValueError("Wedge dimensions require extent > half_beam > 0 and depth > draft > 0.")
    counts = {
        "body_panels_per_side": int(body_panels_per_side),
        "free_surface_panels_per_side": int(free_surface_panels_per_side),
        "side_wall_panels": int(side_wall_panels),
        "bottom_panels": int(bottom_panels),
    }
    if any(value < 2 for value in counts.values()):
        raise ValueError("Every wedge-domain boundary segment requires at least two panels.")

    nodes: list[tuple[float, float]] = [(half_beam, 0.0)]
    labels: list[str] = []

    def append_segment(end_y: float, end_z: float, panel_count: int, label: str) -> None:
        start_y, start_z = nodes[-1]
        y = np.linspace(start_y, float(end_y), int(panel_count) + 1)[1:]
        z = np.linspace(start_z, float(end_z), int(panel_count) + 1)[1:]
        nodes.extend((float(yi), float(zi)) for yi, zi in zip(y, z))
        labels.extend([label] * int(panel_count))

    append_segment(extent, 0.0, counts["free_surface_panels_per_side"], "free_surface")
    append_segment(extent, -depth, counts["side_wall_panels"], "wall")
    append_segment(-extent, -depth, counts["bottom_panels"], "bottom")
    append_segment(-extent, 0.0, counts["side_wall_panels"], "wall")
    append_segment(-half_beam, 0.0, counts["free_surface_panels_per_side"], "free_surface")
    append_segment(0.0, -draft, counts["body_panels_per_side"], "body")
    append_segment(half_beam, 0.0, counts["body_panels_per_side"], "body")
    coordinates = np.asarray(nodes, dtype=float)
    return ClosedBoundary2D(
        node_y_m=coordinates[:, 0],
        node_z_up_m=coordinates[:, 1],
        panel_labels=tuple(labels),
    )
