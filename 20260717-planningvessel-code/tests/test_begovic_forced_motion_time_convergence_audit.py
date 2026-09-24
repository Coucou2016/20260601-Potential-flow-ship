from pathlib import Path

import pytest

from scripts.audit_begovic_forced_motion_time_convergence import _parse_runs


def test_parse_runs_orders_exact_doubling_refinement(tmp_path: Path) -> None:
    paths = {level: tmp_path / str(level) for level in (8, 16, 32)}
    for path in paths.values():
        path.mkdir()

    runs = _parse_runs(
        [
            f"32={paths[32]}",
            f"8={paths[8]}",
            f"16={paths[16]}",
        ]
    )

    assert [level for level, _ in runs] == [8, 16, 32]
    assert all(path.is_absolute() for _, path in runs)


def test_parse_runs_rejects_non_doubling_levels(tmp_path: Path) -> None:
    paths = {level: tmp_path / str(level) for level in (8, 12, 24)}
    for path in paths.values():
        path.mkdir()

    with pytest.raises(ValueError, match="double exactly"):
        _parse_runs([f"{level}={path}" for level, path in paths.items()])
