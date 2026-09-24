from scripts.audit_eulerian_diffraction_grid import compare


def test_complex_phase_difference_is_not_hidden_by_equal_amplitudes():
    assert not compare(1+0j, 0+1j, 1)[2]


def test_frozen_near_zero_absolute_limit():
    assert compare(.001, 0, 1)[2]
    assert not compare(.00101, 0, 1)[2]


def test_five_percent_limit_and_nonfinite_rejection():
    assert compare(.96, 1, 1)[2]
    assert not compare(.94, 1, 1)[2]
    assert not compare(float("nan"), 1, 1)[2]
