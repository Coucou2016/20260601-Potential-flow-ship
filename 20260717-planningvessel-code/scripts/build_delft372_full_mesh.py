from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from planing_seakeeping.datasets.delft372 import (
    DELFT372_LPP_M,
    build_delft372_catamaran_surface_mesh,
    extract_delft372_head_sea_motions_from_markdown,
    extract_delft372_offsets_from_markdown,
    write_delft372_offsets_dataset,
)
from planing_seakeeping.surface_mesh import audit_triangle_mesh, write_triangle_mesh


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_motions(rows, path: Path) -> None:
    fieldnames = list(asdict(rows[0]).keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _write_harmonic_timeseries(row, path: Path, *, cycle_count: float = 3.0, sample_count: int = 361) -> None:
    period = 2.0 * np.pi / row.omega_encounter_rad_s
    time = np.linspace(0.0, cycle_count * period, sample_count)
    wave_phase = row.omega_encounter_rad_s * time

    def harmonic(rao: float, phase_deg: float, scale: float) -> np.ndarray:
        return row.wave_amplitude_cm * rao * scale * np.cos(wave_phase + np.deg2rad(phase_deg))

    columns = {
        "time_s": time,
        "wave_elevation_at_cg_m": 0.01 * row.wave_amplitude_cm * np.cos(wave_phase),
        "surge_m": harmonic(row.surge_rao_cm_per_cm, row.surge_phase_deg, 0.01),
        "sway_m": harmonic(row.sway_rao_cm_per_cm, row.sway_phase_deg, 0.01),
        "heave_m": harmonic(row.heave_rao_cm_per_cm, row.heave_phase_deg, 0.01),
        "roll_deg": harmonic(row.roll_rao_deg_per_cm, row.roll_phase_deg, 1.0),
        "pitch_deg": harmonic(row.pitch_rao_deg_per_cm, row.pitch_phase_deg, 1.0),
        "yaw_deg": harmonic(row.yaw_rao_deg_per_cm, row.yaw_phase_deg, 1.0),
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns.keys())
        for values in zip(*columns.values()):
            writer.writerow([f"{float(value):.10g}" for value in values])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the closed Delft 372 benchmark catamaran mesh from B2 offsets.")
    parser.add_argument("b2_markdown", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--half-section-points", type=int, default=17)
    parser.add_argument("--test-no", default="8720", help="B2 180-degree test used for the harmonic animation.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    extraction = extract_delft372_offsets_from_markdown(args.b2_markdown)
    write_delft372_offsets_dataset(extraction, args.out)
    mesh = build_delft372_catamaran_surface_mesh(
        extraction,
        half_section_point_count=args.half_section_points,
    )
    paths = write_triangle_mesh(mesh, args.out, stem="delft372_catamaran_full")
    audit = audit_triangle_mesh(mesh)
    audit_path = args.out / "delft372_catamaran_mesh_audit.json"
    audit_payload = asdict(audit) | {
        "is_watertight": audit.is_watertight,
        "coordinate_system": "x from aft perpendicular, y starboard, z upward from design waterline",
        "source_markdown": str(args.b2_markdown.resolve()),
        "source_sha256": _sha256(args.b2_markdown),
        "mesh_extent_m": {
            "x": [float(np.min(mesh.vertices[:, 0])), float(np.max(mesh.vertices[:, 0]))],
            "y": [float(np.min(mesh.vertices[:, 1])), float(np.max(mesh.vertices[:, 1]))],
            "z": [float(np.min(mesh.vertices[:, 2])), float(np.max(mesh.vertices[:, 2]))],
        },
        "reference_particulars": {
            "lpp_m": DELFT372_LPP_M,
            "demihull_centerline_spacing_m": 0.70,
            "overall_beam_m": 0.94,
            "design_draft_m": 0.15,
        },
        "mesh_files": {name: str(path.resolve()) for name, path in paths.items()},
    }
    audit_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")

    motions = extract_delft372_head_sea_motions_from_markdown(args.b2_markdown)
    motion_path = args.out / "delft372_head_sea_180deg_motions.csv"
    _write_motions(motions, motion_path)
    selected = next((row for row in motions if row.test_no == args.test_no), None)
    if selected is None:
        raise ValueError(f"Delft 372 test {args.test_no!r} was not found in the 180-degree motion table.")
    timeseries_path = args.out / f"delft372_test_{selected.test_no}_measured_first_harmonic.csv"
    _write_harmonic_timeseries(selected, timeseries_path)
    manifest = {
        "status": "PASS" if audit.is_watertight else "FAIL",
        "mesh_audit": str(audit_path.resolve()),
        "motion_table": str(motion_path.resolve()),
        "selected_test": asdict(selected),
        "timeseries": str(timeseries_path.resolve()),
        "interpretation": (
            "The time series is reconstructed from the published first-harmonic RAO and phase. "
            "It is not the original raw carriage time history and contains no unreported mean attitude."
        ),
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0 if audit.is_watertight else 2


if __name__ == "__main__":
    raise SystemExit(main())
