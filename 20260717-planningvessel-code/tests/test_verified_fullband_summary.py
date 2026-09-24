import json
import pytest
import pandas as pd
from scripts.summarize_verified_fullband import summarize


@pytest.mark.parametrize('missing',['original_24_case_input_verified','source_hashes_verified'])
def test_unverified_scope_cannot_be_summarized_as_full(tmp_path,missing):
    source=tmp_path/'source'; source.mkdir()
    report={k:True for k in ('coverage_and_arithmetic_verified','source_hashes_verified',
                            'original_24_case_input_verified')}
    report.pop(missing)
    (source/'verification.json').write_text(json.dumps(report))
    with pytest.raises(ValueError,match='original full-case'):
        summarize(source,tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('failure_count', [0, 1, 240])
def test_numerical_summary_never_promotes_stage_acceptance(tmp_path, failure_count):
    source = tmp_path/'source'
    source.mkdir()
    report = {k: True for k in ('coverage_and_arithmetic_verified',
        'source_hashes_verified', 'original_24_case_input_verified')}
    report.update(records=720, fine_checks=240)
    (source/'verification.json').write_text(json.dumps(report))
    rows = []
    for case in ('fn167', 'fn226', 'fn282'):
        for omega in range(1, 9):
            for component in ('A33','A35','A53','A55','B33','B35','B53','B55','F3','F5'):
                failed = len(rows) < failure_count
                rows.append(dict(case=case, omega=omega, component=component,
                    absolute_change=.1 if failed else .01, tolerance=.05,
                    real_fine=1., imag_fine=0., passed=not failed))
    pd.DataFrame(rows).to_csv(source/'recomputed_checks.csv', index=False)
    out = tmp_path/'out'
    summarize(source, out)
    result = json.loads((out/'summary.json').read_text())
    assert result['stage_acceptance'] is False
    assert result['numerical_passed'] == 240-failure_count
    assert result['failed_checks'] == failure_count
    assert len(pd.read_csv(out/'failed_frequency_components.csv')) == failure_count
    assert pd.read_csv(out/'component_summary.csv').checks.sum() == 240
