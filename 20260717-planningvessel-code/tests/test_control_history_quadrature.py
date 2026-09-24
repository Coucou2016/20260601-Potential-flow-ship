import pandas as pd
import pytest
from scripts.audit_control_history_quadrature import run
from scripts.compare_kang_history_quadrature import compare
import json


def test_finite_cutoff_kernel_converges_to_independent_integral(tmp_path):
    run(tmp_path/'audit')
    errors=pd.read_csv(tmp_path/'audit/max_errors.csv')
    for _,rows in errors.groupby('mode'):
        values=rows.sort_values('count').absolute_error.to_numpy()
        assert values[1] < values[0]/3
        assert values[2] < values[1]/3
    entries=pd.read_csv(tmp_path/'audit/entries.csv')
    assert entries.quad_error_estimate.max() < 1e-8


def test_missing_quadrature_contract_cannot_be_assumed(tmp_path):
    roots=[tmp_path/str(i) for i in range(3)]
    for root in roots:
        root.mkdir(); (root/'contract.json').write_text(json.dumps({}))
    with pytest.raises(ValueError,match='Explicit ordered'):
        compare(roots,tmp_path/'result')
    assert not (tmp_path/'result').exists()


def test_cutoff_comparison_rejects_coarse_quadrature(tmp_path):
    roots=[tmp_path/str(i) for i in range(3)]
    for root,cutoff in zip(roots,(25.,50.,100.)):
        root.mkdir(); (root/'contract.json').write_text(json.dumps(dict(
            history_k_max=cutoff,history_quadrature_count=64)))
    with pytest.raises(ValueError,match='512 quadrature'):
        compare(roots,tmp_path/'result',refinement='cutoff')
    assert not (tmp_path/'result').exists()
