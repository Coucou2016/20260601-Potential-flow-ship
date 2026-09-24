from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class TriangleMesh:
    """A small, dependency-free triangular surface mesh container."""

    vertices: np.ndarray
    faces: np.ndarray
    name: str = "mesh"

    def __post_init__(self) -> None:
        vertices = np.asarray(self.vertices, dtype=float)
        faces = np.asarray(self.faces, dtype=int)
        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise ValueError("TriangleMesh vertices must have shape (n, 3).")
        if faces.ndim != 2 or faces.shape[1] != 3:
            raise ValueError("TriangleMesh faces must have shape (m, 3).")
        if not np.all(np.isfinite(vertices)):
            raise ValueError("TriangleMesh vertices contain NaN or infinity.")
        if faces.size and (int(np.min(faces)) < 0 or int(np.max(faces)) >= vertices.shape[0]):
            raise ValueError("TriangleMesh face index lies outside the vertex array.")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)


@dataclass(frozen=True)
class MeshTopologyAudit:
    vertex_count: int
    face_count: int
    boundary_edge_count: int
    nonmanifold_edge_count: int
    degenerate_face_count: int
    connected_component_count: int
    surface_area_m2: float
    enclosed_volume_m3: float

    @property
    def is_watertight(self) -> bool:
        return (
            self.boundary_edge_count == 0
            and self.nonmanifold_edge_count == 0
            and self.degenerate_face_count == 0
        )


def _edge_counts(faces: np.ndarray) -> dict[tuple[int, int], int]:
    counts: dict[tuple[int, int], int] = {}
    for face in faces:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge = (int(min(a, b)), int(max(a, b)))
            counts[edge] = counts.get(edge, 0) + 1
    return counts


def audit_triangle_mesh(mesh: TriangleMesh, *, area_tolerance_m2: float = 1e-14) -> MeshTopologyAudit:
    triangles = mesh.vertices[mesh.faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    triangle_areas = 0.5 * np.linalg.norm(cross, axis=1)
    degenerate = int(np.count_nonzero(triangle_areas <= area_tolerance_m2))
    edge_counts = _edge_counts(mesh.faces)

    adjacency: list[set[int]] = [set() for _ in range(mesh.vertices.shape[0])]
    for a, b in edge_counts:
        adjacency[a].add(b)
        adjacency[b].add(a)
    active_vertices = set(int(value) for value in np.unique(mesh.faces))
    components = 0
    while active_vertices:
        components += 1
        stack = [active_vertices.pop()]
        while stack:
            current = stack.pop()
            for neighbour in adjacency[current]:
                if neighbour in active_vertices:
                    active_vertices.remove(neighbour)
                    stack.append(neighbour)

    signed_volume = np.sum(
        np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2]))
    ) / 6.0
    return MeshTopologyAudit(
        vertex_count=int(mesh.vertices.shape[0]),
        face_count=int(mesh.faces.shape[0]),
        boundary_edge_count=sum(count == 1 for count in edge_counts.values()),
        nonmanifold_edge_count=sum(count > 2 for count in edge_counts.values()),
        degenerate_face_count=degenerate,
        connected_component_count=components,
        surface_area_m2=float(np.sum(triangle_areas)),
        enclosed_volume_m3=float(abs(signed_volume)),
    )


def combine_triangle_meshes(
    meshes: Iterable[TriangleMesh],
    *,
    name: str = "combined_mesh",
) -> TriangleMesh:
    vertex_blocks: list[np.ndarray] = []
    face_blocks: list[np.ndarray] = []
    vertex_offset = 0
    for mesh in meshes:
        vertex_blocks.append(mesh.vertices)
        face_blocks.append(mesh.faces + vertex_offset)
        vertex_offset += mesh.vertices.shape[0]
    if not vertex_blocks:
        raise ValueError("At least one mesh is required.")
    return TriangleMesh(np.vstack(vertex_blocks), np.vstack(face_blocks), name=name)


def translated_mesh(mesh: TriangleMesh, translation_xyz: tuple[float, float, float], *, name: str | None = None) -> TriangleMesh:
    translation = np.asarray(translation_xyz, dtype=float)
    if translation.shape != (3,):
        raise ValueError("translation_xyz must contain exactly three values.")
    return TriangleMesh(mesh.vertices + translation, mesh.faces.copy(), name=name or mesh.name)


def write_triangle_mesh(mesh: TriangleMesh, out_dir: str | Path, *, stem: str | None = None) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = stem or mesh.name
    vertices_path = out / f"{base}_vertices.csv"
    faces_path = out / f"{base}_faces.csv"
    obj_path = out / f"{base}.obj"

    with vertices_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["vertex_id", "x_m", "y_m", "z_up_m"])
        for index, (x_m, y_m, z_m) in enumerate(mesh.vertices):
            writer.writerow([index, f"{x_m:.9f}", f"{y_m:.9f}", f"{z_m:.9f}"])

    with faces_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["face_id", "vertex_0", "vertex_1", "vertex_2"])
        for index, face in enumerate(mesh.faces):
            writer.writerow([index, int(face[0]), int(face[1]), int(face[2])])

    with obj_path.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(f"o {base}\n")
        for x_m, y_m, z_m in mesh.vertices:
            handle.write(f"v {x_m:.9f} {y_m:.9f} {z_m:.9f}\n")
        for face in mesh.faces:
            handle.write(f"f {int(face[0]) + 1} {int(face[1]) + 1} {int(face[2]) + 1}\n")

    return {"vertices": vertices_path, "faces": faces_path, "obj": obj_path}
