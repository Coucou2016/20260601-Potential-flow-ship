from __future__ import annotations

import pytest

from scripts.probe_sun2007_planing_forced_motion import _ground_plane_spacing_m, _parser


def test_source_bem_interval_spacing_places_nx_planes_from_handoff_to_transom() -> None:
    beam = 0.318
    spacing = _ground_plane_spacing_m(
        wetted_length_m=3.8 * beam,
        initial_leading_offset_m=0.8 * beam,
        section_planes=11,
        rule="bem_interval_over_nx_minus_one",
    )

    assert spacing / beam == pytest.approx(0.3)
    assert 0.8 * beam + 10.0 * spacing == pytest.approx(3.8 * beam)


def test_legacy_spacing_rule_preserves_frozen_production_grid() -> None:
    beam = 0.318
    spacing = _ground_plane_spacing_m(
        wetted_length_m=3.8 * beam,
        initial_leading_offset_m=(3.8 / 11.0) * beam,
        section_planes=11,
        rule="keel_over_nx",
    )

    assert spacing / beam == pytest.approx(3.8 / 11.0)


def test_parallel_worker_count_is_explicit_cli_input() -> None:
    arguments = _parser().parse_args(["--parallel-workers", "4"])

    assert arguments.parallel_workers == 4
