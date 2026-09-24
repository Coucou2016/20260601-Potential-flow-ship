from unittest.mock import patch
import numpy as np
from planing_seakeeping.kernels.linear_2p5d.formulation import MatchedBoundarySystem, _CONDITION_CACHE
from planing_seakeeping.types import ValidityReport


def system(matrix):
    return MatchedBoundarySystem(matrix,np.ones(len(matrix)),(),ValidityReport(status='test'))


def test_identical_content_reuses_diagnostic_and_mutation_invalidates():
    _CONDITION_CACHE.clear()
    matrix=np.array([[2.+1j, .3], [.1, 3.]])
    expected=np.linalg.cond(matrix)
    original=np.linalg.cond
    with patch('numpy.linalg.cond',wraps=original) as cond:
        a=system(matrix)
        assert a.condition_number == expected
        assert a.condition_number == expected
        assert system(matrix.copy()).condition_number == expected
        assert cond.call_count == 1
        matrix[0,0] += 2
        assert a.condition_number == original(matrix)
        assert cond.call_count == 2
    _CONDITION_CACHE.clear()


def test_condition_cache_is_bounded():
    _CONDITION_CACHE.clear()
    for i in range(260):
        assert np.isfinite(system(np.diag([1.,i+2.])).condition_number)
    assert len(_CONDITION_CACHE)==256
    _CONDITION_CACHE.clear()
