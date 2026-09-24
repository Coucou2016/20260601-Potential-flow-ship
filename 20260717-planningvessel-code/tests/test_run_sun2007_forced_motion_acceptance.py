from __future__ import annotations

from pathlib import Path

from scripts.aggregate_sun2007_forced_motion_acceptance import EXPECTED_SIGMAS
from scripts.run_sun2007_forced_motion_acceptance import production_command


def test_production_commands_cover_five_frequencies_and_source_configuration(tmp_path) -> None:
    restoring = tmp_path / "restoring_matrices.csv"
    commands = [
        production_command(
            sigma,
            tmp_path / f"sigma_{sigma}",
            restoring,
        )
        for sigma in EXPECTED_SIGMAS
    ]

    assert len(commands) == 5
    assert [float(command[command.index("--sigmas") + 1]) for command in commands] == list(
        EXPECTED_SIGMAS
    )
    for command in commands:
        assert command[command.index("--restoring-mode") + 1] == "external"
        assert Path(command[command.index("--restoring-matrix-file") + 1]) == restoring
        assert command[command.index("--knuckle-separation-model") + 1] == "artificial_surface"
        assert command[command.index("--ground-plane-spacing-rule") + 1] == "keel_over_nx"
        assert command[command.index("--free-surface-remesh-updates-per-plane") + 1] == "8"
        assert command[command.index("--free-surface-smoothing-updates-per-plane") + 1] == "8"
        assert "--transom-correction" not in command


def test_production_command_can_enable_source_transom_correction(tmp_path) -> None:
    command = production_command(
        1.4,
        tmp_path / "run",
        tmp_path / "restoring.csv",
        transom_correction=True,
    )

    assert "--transom-correction" in command


def test_production_command_can_enable_source_half_beam_keel_reduction(tmp_path) -> None:
    command = production_command(
        1.4,
        tmp_path / "run",
        tmp_path / "restoring.csv",
        transom_keel_reduction=True,
    )
    assert "--transom-keel-reduction" in command
    assert "--transom-correction" not in command


def test_production_command_can_select_source_front_interval_spacing(tmp_path) -> None:
    command = production_command(
        1.4,
        tmp_path / "run",
        tmp_path / "restoring.csv",
        ground_plane_spacing_rule="bem_interval_over_nx_minus_one",
        initial_leading_offset_beams=0.8,
    )

    assert command[command.index("--ground-plane-spacing-rule") + 1] == (
        "bem_interval_over_nx_minus_one"
    )
    assert float(command[command.index("--initial-leading-offset-beams") + 1]) == 0.8
