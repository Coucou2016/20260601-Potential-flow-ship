from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from scripts.postprocess_sun2007_forced_motion_checkpoint import (
    _coefficient_scale as checkpoint_coefficient_scale,
    _read_restoring_matrices,
)
from scripts.probe_sun2007_planing_forced_motion import (
    _coefficient_scale as probe_coefficient_scale,
    _ground_plane_event_diagnostics,
    _parser as probe_parser,
    _read_external_restoring_matrices,
)


@pytest.mark.parametrize(
    ("coefficient", "length_power", "uses_frequency_scale"),
    [
        ("A33", 3, False),
        ("A35", 4, False),
        ("A53", 4, False),
        ("A55", 5, False),
        ("B33", 3, True),
        ("B35", 4, True),
        ("B53", 4, True),
        ("B55", 5, True),
    ],
)
def test_sun2007_forced_motion_coefficient_scales(
    coefficient: str,
    length_power: int,
    uses_frequency_scale: bool,
) -> None:
    beam = 0.318
    rho = 1000.0
    gravity = 9.80665
    expected = rho * beam**length_power
    if uses_frequency_scale:
        expected *= math.sqrt(gravity / beam)

    for scale_function in (checkpoint_coefficient_scale, probe_coefficient_scale):
        assert scale_function(
            coefficient,
            beam=beam,
            rho=rho,
            gravity=gravity,
        ) == pytest.approx(expected)


@pytest.mark.parametrize(
    "scale_function",
    [checkpoint_coefficient_scale, probe_coefficient_scale],
)
def test_sun2007_forced_motion_coefficient_scale_rejects_unknown_labels(
    scale_function,
) -> None:
    with pytest.raises(ValueError, match="Unsupported forced-motion coefficient"):
        scale_function("A99", beam=0.318, rho=1000.0, gravity=9.80665)


def test_restoring_matrix_reader_accepts_utf8_bom(tmp_path) -> None:
    path = tmp_path / "restoring_matrices.csv"
    path.write_text(
        "component,row,column,value,units\n"
        "total,heave_force,heave,1.0,N/m\n"
        "total,heave_force,pitch,2.0,N/rad\n"
        "total,pitch_moment,heave,3.0,N\n"
        "total,pitch_moment,pitch,4.0,N m/rad\n",
        encoding="utf-8-sig",
    )

    matrices = _read_restoring_matrices(path)

    assert matrices["total"].tolist() == [[1.0, 2.0], [3.0, 4.0]]


def test_probe_exports_all_ground_plane_event_diagnostics() -> None:
    result = SimpleNamespace(
        metadata={
            "contact_exit_removal_count": 2,
            "transom_exit_removal_count": 3,
            "forward_interval_exit_removal_count": 4,
            "below_handoff_draft_removal_count": 5,
            "fixed_plane_deferred_creation_count": 6,
            "fixed_plane_expired_before_activation_count": 7,
            "fixed_plane_pending_count_at_end": 8,
            "fixed_plane_localized_activation_count": 9,
            "fixed_plane_maximum_removed_time_quantization_s": 0.001,
            "fixed_plane_activation_rule": "localized_actual_draft",
        }
    )

    assert _ground_plane_event_diagnostics("heave", result) == {
        "heave_contact_exit_removal_count": 2,
        "heave_transom_exit_removal_count": 3,
        "heave_forward_interval_exit_removal_count": 4,
        "heave_below_handoff_draft_removal_count": 5,
        "heave_fixed_plane_deferred_creation_count": 6,
        "heave_fixed_plane_expired_before_activation_count": 7,
        "heave_fixed_plane_pending_count_at_end": 8,
        "heave_fixed_plane_localized_activation_count": 9,
        "heave_fixed_plane_maximum_removed_time_quantization_s": 0.001,
        "heave_fixed_plane_activation_rule": "localized_actual_draft",
    }


def test_sun2007_probe_defaults_to_source_artificial_surface_separation() -> None:
    args = probe_parser().parse_args([])

    assert args.knuckle_separation_model == "artificial_surface"


def test_probe_reads_complete_external_restoring_matrix(tmp_path) -> None:
    path = tmp_path / "restoring_matrices.csv"
    path.write_text(
        "component,row,column,value,units\n"
        "total,heave_force,heave,1.0,N/m\n"
        "total,heave_force,pitch,2.0,N/rad\n"
        "total,pitch_moment,heave,3.0,N\n"
        "total,pitch_moment,pitch,4.0,N m/rad\n",
        encoding="utf-8-sig",
    )

    matrices = _read_external_restoring_matrices(path)

    assert matrices["total"].tolist() == [[1.0, 2.0], [3.0, 4.0]]


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        (
            "component,row,column,value\n"
            "total,heave_force,heave,1.0\n",
            "all four cells",
        ),
        (
            "component,row,column,value\n"
            "total,heave_force,heave,1.0\n"
            "total,heave_force,heave,2.0\n"
            "total,heave_force,pitch,3.0\n"
            "total,pitch_moment,heave,4.0\n"
            "total,pitch_moment,pitch,5.0\n",
            "Duplicate",
        ),
        (
            "component,row,column,value\n"
            "total,heave_force,heave,nan\n"
            "total,heave_force,pitch,2.0\n"
            "total,pitch_moment,heave,3.0\n"
            "total,pitch_moment,pitch,4.0\n",
            "finite",
        ),
    ],
)
def test_probe_rejects_invalid_external_restoring_matrix(
    tmp_path,
    contents: str,
    message: str,
) -> None:
    path = tmp_path / "restoring_matrices.csv"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        _read_external_restoring_matrices(path)


def test_probe_parser_accepts_external_restoring_source(tmp_path) -> None:
    path = tmp_path / "restoring_matrices.csv"
    args = probe_parser().parse_args(
        [
            "--restoring-mode",
            "external",
            "--restoring-matrix-file",
            str(path),
        ]
    )

    assert args.restoring_mode == "external"
    assert args.restoring_matrix_file == path
