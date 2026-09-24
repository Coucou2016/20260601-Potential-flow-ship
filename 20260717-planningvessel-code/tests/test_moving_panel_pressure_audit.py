from scripts.audit_moving_panel_pressure_gradient import measure


def test_fixed_geometry_phase_derivative_converges():
    coarse, fine = measure(33, False), measure(129, False)
    assert fine["pressure_relative_error"] < .001
    assert fine["pressure_relative_error"] < coarse["pressure_relative_error"]/10


def test_manufactured_geometry_chain_term_explains_error():
    coarse, fine = measure(33), measure(129)
    assert fine["corrected_pressure_relative_error"] < .001
    assert fine["corrected_pressure_relative_error"] < coarse["corrected_pressure_relative_error"]/10
    # Exposes the present production derivative limitation; not an acceptance gate.
    assert fine["pressure_relative_error"] > .2
