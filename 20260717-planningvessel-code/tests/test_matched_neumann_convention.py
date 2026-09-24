"""The manufactured reference is independent of any experimental response."""
from scripts.audit_matched_neumann_convention import check


def test_inner_harmonic_field_requires_fluid_outward_body_derivative():
    coarse, wrong = check(64, 96)
    fine, _ = check(128, 192)
    assert coarse['body_potential_relative_error'] < 0.001
    assert fine['body_potential_relative_error'] < coarse['body_potential_relative_error'] / 3
    assert fine['free_normal_relative_error'] < 0.005
    assert wrong['body_potential_relative_error'] > 1.0
    assert max(row['algebra_residual'] for row in (coarse, fine, wrong)) < 1e-12
