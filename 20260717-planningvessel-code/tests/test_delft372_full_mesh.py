from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from planing_seakeeping.datasets.delft372 import (
    build_delft372_catamaran_surface_mesh,
    extract_delft372_head_sea_motions_from_markdown,
    extract_delft372_offsets_from_markdown,
)
from planing_seakeeping.surface_mesh import audit_triangle_mesh


def _b2_markdown() -> Path:
    candidates = list(Path(__file__).resolve().parents[2].glob("20260729-*/md/B2.md"))
    if not candidates:
        raise RuntimeError("B2.md was not found next to the code workspace.")
    path = candidates[0]
    try:
        with path.open("rb"):
            pass
    except FileNotFoundError:
        pytest.skip(
            "This Python runtime cannot open an absolute path containing Chinese "
            "characters; run the source acceptance test from the B2.md directory."
        )
    return path


def test_delft372_full_catamaran_mesh_is_closed_and_has_reference_extents() -> None:
    extraction = extract_delft372_offsets_from_markdown(_b2_markdown())
    mesh = build_delft372_catamaran_surface_mesh(extraction)
    audit = audit_triangle_mesh(mesh)

    assert audit.is_watertight
    assert audit.connected_component_count == 2
    assert audit.enclosed_volume_m3 > 0.0
    assert np.min(mesh.vertices[:, 0]) == 0.0
    assert 3.0 < np.max(mesh.vertices[:, 0]) < 3.11
    assert np.isclose(np.max(np.abs(mesh.vertices[:, 1])), 0.47, atol=1e-6)
    assert np.min(mesh.vertices[:, 2]) < -0.11
    assert np.max(mesh.vertices[:, 2]) == 0.05


def test_delft372_motion_parser_recovers_published_test_8720() -> None:
    motions = extract_delft372_head_sea_motions_from_markdown(_b2_markdown())
    row = next(value for value in motions if value.test_no == "8720")

    assert len(motions) == 21
    assert {value.test_no for value in motions} == {
        "8706",
        "8710",
        "8711",
        "8712",
        "8713",
        "8714",
        "8715",
        "8716",
        "8717",
        "8718",
        "8719",
        "8720",
        "8721",
        "8722",
        "8723",
        "8724",
        "8725",
        "8726",
        "8727",
        "8728",
        "8729",
    }
    assert np.isclose(row.froude_number, 0.60)
    assert np.isclose(row.speed_m_s, 3.347)
    assert np.isclose(row.omega_encounter_rad_s, 7.964)
    assert np.isclose(row.wave_amplitude_cm, 1.79)
    assert np.isclose(row.heave_rao_cm_per_cm, 2.802)
    assert np.isclose(row.pitch_rao_deg_per_cm, 0.865)


def test_delft372_motion_parser_excludes_non_head_sea_group_in_mixed_table(tmp_path: Path) -> None:
    head_sea_ids = [f"{8700 + index:04d}" for index in range(21)]
    overview_rows = "".join(
        f"<tr><td>{test_no}00</td><td>3.0</td><td>4.0</td><td></td><td></td><td>1.5</td></tr>"
        for test_no in (*head_sea_ids, "8799")
    )
    motion_values = "".join("<td>1.0</td>" for _ in range(15))
    head_sea_rows = "".join(f"<tr><td>{test_no}</td>{motion_values}</tr>" for test_no in head_sea_ids)
    markdown = f"""
<table>
<tr><td>Marin test no.</td><td>speed</td><td>omega</td><td></td><td></td><td>amplitude</td></tr>
{overview_rows}
</table>
<table>
<tr><td colspan="16">MOTION RESULTS, 180 DEGREES</td></tr>
<tr><td>Test no.</td></tr>
<tr><td>Fn 0.60</td></tr>
{head_sea_rows}
<tr><td colspan="16">MOTION RESULTS, 195 DEGREES</td></tr>
<tr><td>Test no.</td></tr>
<tr><td>Fn 0.60</td></tr>
<tr><td>8799</td>{motion_values}</tr>
</table>
"""
    source = tmp_path / "mixed_motion_groups.md"
    source.write_text(markdown, encoding="utf-8")

    motions = extract_delft372_head_sea_motions_from_markdown(source)

    assert len(motions) == 21
    assert [motion.test_no for motion in motions] == head_sea_ids
    assert all(motion.test_no != "8799" for motion in motions)
