import pytest
from scripts.audit_history_startup_endpoint import evaluate


def test_nonzero_start_has_half_endpoint_excess():
    for n in (8,16,32):
        r=evaluate(n,False)
        assert r['original_error']==pytest.approx(.5/n)
        assert r['corrected_error']<1e-14


def test_zero_start_is_unaffected_and_second_order():
    a,b=evaluate(8,True),evaluate(16,True)
    assert a['original']==a['corrected']
    assert a['original_error']/b['original_error']==pytest.approx(4.)
