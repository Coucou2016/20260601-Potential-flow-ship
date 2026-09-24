from pathlib import Path

import pytest

from scripts.probe_eulerian_diffraction import run


@pytest.mark.parametrize('count', [True, 5, 7, 0, -2, 6.0])
def test_invalid_panel_override_rejected_before_output(tmp_path, count):
    config = Path(__file__).resolve().parents[1]/'benchmarks/longitudinal_refined_20260921/run.json'
    out = tmp_path/'invalid'
    with pytest.raises(ValueError, match='even integer'):
        run(config, out, grid_level=1, body_panels_override=count)
    assert not out.exists()


@pytest.mark.parametrize('count', [True, 2, 0, -2, 85.0])
def test_invalid_station_override_rejected_before_output(tmp_path, count):
    config = Path(__file__).resolve().parents[1]/'benchmarks/longitudinal_refined_20260921/run.json'
    out = tmp_path/'invalid'
    with pytest.raises(ValueError, match='integer >= 3'):
        run(config, out, grid_level=1, stations_override=count)
    assert not out.exists()


@pytest.mark.parametrize('count', [True, 2, 5, 0, -2, 72.0])
def test_invalid_free_override_rejected_before_output(tmp_path, count):
    config = Path(__file__).resolve().parents[1]/'benchmarks/longitudinal_refined_20260921/run.json'
    out = tmp_path/'invalid'
    with pytest.raises(ValueError, match='even integer >= 4'):
        run(config, out, grid_level=1, free_panels_override=count)
    assert not out.exists()
