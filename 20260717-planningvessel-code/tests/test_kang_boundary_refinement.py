from copy import deepcopy
import pytest
from scripts.summarize_kang_boundary_refinement import validate_pair


def pair():
    base = dict(frequencies=[2, 3, 4], length=3., beam=.3, draft=.1875, froude_length=.2,
        rho=1000., gravity=9.80665, options={'history_steps':128}, input_points_per_side=161,
        endpoint_fraction=1e-6, moment_origin='geometric', preset='fine',
        config={'free_surface_inner_panels':64, 'free_surface_outer_panels':96,
                'hull_stations':81, 'control_surface_radius_beams':3.})
    dense = deepcopy(base)
    dense['preset'] = 'boundary_dense'
    dense['config']['free_surface_inner_panels'] *= 2
    dense['config']['free_surface_outer_panels'] *= 2
    return base, dense


def test_only_boundary_refinement_allowed():
    validate_pair(*pair())


@pytest.mark.parametrize('key', ['length', 'options', 'moment_origin'])
def test_changed_or_missing_fixed_input_rejected(key):
    base, dense = pair()
    del dense[key]
    with pytest.raises(ValueError):
        validate_pair(base, dense)


def test_radius_change_not_boundary_refinement():
    base, dense = pair()
    dense['config']['control_surface_radius_beams'] = 4.5
    with pytest.raises(ValueError):
        validate_pair(base, dense)
