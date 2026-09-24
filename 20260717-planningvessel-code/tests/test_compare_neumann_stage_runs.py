import json

import pandas as pd
import pytest

from scripts.compare_neumann_stage_runs import compare


def fixture_runs(tmp_path):
    roots = [tmp_path/'before', tmp_path/'after']
    for index, root in enumerate(roots):
        (root/'case').mkdir(parents=True)
        (root/'input_snapshot.json').write_text(json.dumps({'cases':[{'id':'case'}]}))
        pd.DataFrame([dict(omega_e_rad_s=2., A=1., B=2., C=3., M=4.)]).to_csv(root/'case/matrices.csv', index=False)
        for name in ('excitation', 'excitation_component_matched_domain_froude_krylov',
                     'excitation_component_matched_domain_diffraction',
                     'excitation_component_matched_domain_incident_plus_diffraction'):
            value = -1. if index and name.endswith('_diffraction') else 1.
            pd.DataFrame([dict(omega_e_rad_s=2., F3_real=value, F3_imag=value,
                               M5_real=value, M5_imag=value)]).to_csv(root/f'case/{name}.csv', index=False)
    return roots


def test_exact_sign_change_is_audit_not_stage_acceptance(tmp_path):
    a,b=fixture_runs(tmp_path)
    compare(a,b,tmp_path/'audit')
    result=json.loads((tmp_path/'audit/audit.json').read_text())
    assert result['rows'][0]['controlled_sign_change_confirmed']
    assert result['stage_acceptance'] is False


def test_matrix_change_cannot_be_called_sign_only(tmp_path):
    a,b=fixture_runs(tmp_path)
    path=b/'case/matrices.csv'
    frame=pd.read_csv(path); frame['A']=20.; frame.to_csv(path,index=False)
    compare(a,b,tmp_path/'audit')
    assert not json.loads((tmp_path/'audit/audit.json').read_text())['rows'][0]['controlled_sign_change_confirmed']


def test_different_input_rejected(tmp_path):
    a,b=fixture_runs(tmp_path)
    (b/'input_snapshot.json').write_text('{}')
    with pytest.raises(ValueError,match='snapshots differ'):
        compare(a,b,tmp_path/'audit')
    assert not (tmp_path/'audit').exists()
