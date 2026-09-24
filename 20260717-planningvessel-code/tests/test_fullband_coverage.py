import numpy as np
import pandas as pd
import pytest
import hashlib
import json
from scripts.verify_fullband_coverage import verify_values, COMPONENTS
from scripts.verify_fullband_coverage import verify_input_scope


def test_original_input_scope_cannot_be_reduced(tmp_path):
    path=tmp_path/'run.json'
    expected={f'case{i}':list(range(1,9)) for i in range(3)}
    path.write_text(json.dumps({'cases':[{'id':k,'encounter_omega_rad_s':v} for k,v in expected.items()]}))
    contract=dict(input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),frequencies=expected,
                  selected_case_endpoint_diagnostic=None)
    assert verify_input_scope(contract,path)==expected
    with pytest.raises(ValueError,match='all original'):
        verify_input_scope(dict(contract,frequencies={'case0':[1,8]}),path)
    with pytest.raises(ValueError,match='all original'):
        verify_input_scope(dict(contract,selected_case_endpoint_diagnostic='case0'),path)
    with pytest.raises(ValueError,match='hash'):
        verify_input_scope(dict(contract,input_sha256='wrong'),path)


def fixture():
    contract = dict(frequencies={'case':[1.,2.]}, relative_limit=.05,
                    dimensionless_absolute_limit=.001, near_zero_dimensionless_threshold=.02)
    frame = pd.DataFrame([dict(level=l,case='case',omega=w,component=c,real=1.,imag=.5)
        for l in range(3) for w in (1.,2.) for c in COMPONENTS])
    return frame,contract


def test_all_records_required():
    frame,contract = fixture()
    assert verify_values(frame,contract).passed.all()
    for bad in (frame.iloc[1:],pd.concat([frame,frame.iloc[:1]]),frame.assign(component='unknown')):
        with pytest.raises(ValueError):
            verify_values(bad,contract)


def test_nonfinite_and_relaxed_threshold_rejected():
    frame,contract = fixture()
    with pytest.raises(ValueError):
        verify_values(frame.assign(real=np.nan),contract)
    with pytest.raises(ValueError):
        verify_values(frame,dict(contract,relative_limit=.1))
