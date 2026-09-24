import numpy as np
import pytest
from scripts.audit_moving_free_surface_manufactured import exact_fields,simulate


def test_analytic_free_surface_equations():
    y=np.array([-.4,.4]); t=.3; h=1e-6
    state=exact_fields(y,t)
    derivative=(exact_fields(y,t+h)-exact_fields(y,t-h))/(2*h)
    np.testing.assert_allclose(derivative[:,0],-9.80665*state[:,1],rtol=1e-9)
    np.testing.assert_allclose(derivative[:,1],state[:,2],rtol=1e-9)


def test_variable_dimension_march_exercises_new_exposure():
    result=simulate(1)
    assert len(set(r['panels'] for r in result['rows']))>1
    assert sum(r['newly_exposed'] for r in result['rows'])>0
    assert result['maximum_equation_error']<1e-10
    assert np.isfinite(result['final_values']).all()


def test_invalid_refinement():
    with pytest.raises(ValueError):
        simulate(0)


def test_actual_bounded_policy_is_not_covered_by_exact_exposure_pass():
    exact=simulate(4,'exact_exposure')
    bounded=simulate(4,'bounded_nearest_unvalidated')
    exact_error=max(r['relative_phi_eta_error'] for r in exact['rows'])
    bounded_error=max(r['relative_phi_eta_error'] for r in bounded['rows'])
    assert exact_error < .01
    # This records a known candidate limitation, not successful ship validation.
    assert bounded_error > .01
    assert max(r['maximum_scaled_point_error'] for r in bounded['rows']) > .04
    assert bounded['maximum_equation_error'] < 1e-10


def test_unknown_contact_policy_rejected():
    with pytest.raises(ValueError,match='policy'):
        simulate(1,'auto')


def test_exposure_and_old_edge_factorial_remains_distinguishable():
    repaired_exposure=simulate(4,'exact_exposure_bounded_edges')
    repaired_edge=simulate(4,'bounded_exposure_linear_edges')
    a=max(r['relative_phi_eta_error'] for r in repaired_exposure['rows'])
    b=max(r['relative_phi_eta_error'] for r in repaired_edge['rows'])
    assert a < .001
    assert b > .01
