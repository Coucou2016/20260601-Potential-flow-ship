import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import audit_station_only_diffraction as audit


@pytest.mark.parametrize('axis,values,key', [
    ('stations', [57, 85, 113], 'stations_override'),
    ('free', [48, 72, 96], 'free_panels_override'),
])
def test_axis_freeze_and_coverage(tmp_path, monkeypatch, axis, values, key):
    config = Path(__file__).resolve().parents[1]/'benchmarks/longitudinal_refined_20260921/run.json'
    raw = json.loads(config.read_text())
    calls = []
    out = tmp_path/'audit'

    def fake_probe(path, destination, **kwargs):
        contract = json.loads((out/'contract.json').read_text())
        assert contract['axis'] == axis
        assert contract['values'] == values
        assert (out/'driver_hashes.json').exists()
        assert set(kwargs) == {'grid_level', key}
        assert kwargs['grid_level'] == 1
        calls.append(kwargs[key])
        destination.mkdir()
        rows = []
        for case in raw['cases']:
            for mode in (3, 5):
                row = dict(case=case['id'], omega=case['encounter_omega_rad_s'][4], mode=mode)
                for component in ('original', 'delta', 'candidate', 'normal', 'tangent'):
                    row[f'{component}_real'] = 1.
                    row[f'{component}_imag'] = 2.
                rows.append(row)
        pd.DataFrame(rows).to_csv(destination/'force_changes.csv', index=False)

    monkeypatch.setattr(audit, 'probe', fake_probe)
    audit.run(config, out, axis)
    assert calls == values
    result = json.loads((out/'results.json').read_text())
    assert result['checks'] == result['passed_count'] == 30
    assert result['physical_acceptance'] == 'NOT_PASSED'
    assert result['full_band_acceptance'] is False


def test_unknown_axis_rejected_before_files(tmp_path):
    with pytest.raises(ValueError, match='axis must'):
        audit.run(tmp_path/'missing.json', tmp_path/'out', 'response_fit')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('values', [[48,48,96],[96,72,48],[48,72],[48,73,96],[True,72,96],[48.,72,96]])
def test_invalid_grid_sequence_rejected(tmp_path,values):
    with pytest.raises(ValueError,match='Three increasing'):
        audit.run(tmp_path/'missing.json',tmp_path/'out','free',values=values)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('axis,value',[('free',192),('stations',True),('stations',193),('stations',0)])
def test_invalid_fixed_free_rejected(tmp_path,axis,value):
    with pytest.raises(ValueError,match='fixed_free requires'):
        audit.run(tmp_path/'missing.json',tmp_path/'out',axis,fixed_free=value)
    assert not (tmp_path/'out').exists()


def test_truncated_history_rejected_before_solve(tmp_path):
    with pytest.raises(ValueError,match='history_steps must cover'):
        audit.run(tmp_path/'missing.json',tmp_path/'out',values=[85,113,169],history_steps=128)
    assert not (tmp_path/'out').exists()
