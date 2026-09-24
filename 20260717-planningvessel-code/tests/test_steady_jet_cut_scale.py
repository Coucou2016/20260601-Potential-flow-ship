from dataclasses import replace
import math
import pytest
from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import MovingWedgeConfig, _jet_cut_threshold_m


@pytest.mark.parametrize('contact', [.02, .08, .159, .20])
def test_matched_cut_rule_independent_of_panel_count(contact):
    medium = MovingWedgeConfig(deadrise_rad=math.radians(20), mean_draft_m=.084588,
        chine_half_beam_m=.159, free_surface_extent_m=.954, water_depth_m=.795,
        body_panels_per_side=16, jet_cut_distance_fraction=.25)
    fine = replace(medium, body_panels_per_side=20, jet_cut_distance_fraction=.3125)
    assert _jet_cut_threshold_m(medium, contact_half_beam_m=contact) == pytest.approx(
        _jet_cut_threshold_m(fine, contact_half_beam_m=contact), rel=1e-14)
