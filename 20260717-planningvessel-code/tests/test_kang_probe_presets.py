import pytest
from scripts.probe_kang_heave_excitation import PRESETS, run


def test_endpoint_experiment_changes_only_endpoint():
    assert PRESETS['endpoint_only'][:-1] == PRESETS['baseline'][:-1]
    assert PRESETS['endpoint_only'][-1] > PRESETS['baseline'][-1]


def test_history_experiment_preserves_spatial_discretization():
    base, changed = PRESETS['baseline'], PRESETS['history_only']
    assert base[:4] == changed[:4] and base[6:] == changed[6:]
    assert changed[4] == 2*base[4] and changed[5] == 2*base[5]


def test_boundary_dense_changes_only_free_surface_and_control_counts():
    base, dense = PRESETS['fine'], PRESETS['boundary_dense']
    assert base[:2] == dense[:2] and base[4:] == dense[4:]
    assert dense[2:4] == (2*base[2], 2*base[3])


def test_half_dt_preserves_boundary_resolution_and_history_duration():
    base, refined = PRESETS['boundary_dense'], PRESETS['boundary_dense_half_dt']
    assert refined[0]-1 == 2*(base[0]-1)
    assert refined[4] == 2*base[4]
    assert refined[1:4] == base[1:4] and refined[5:] == base[5:]


def test_quarter_dt_preserves_resolution_and_history_duration():
    base, refined = PRESETS['boundary_dense_half_dt'], PRESETS['boundary_dense_quarter_dt']
    assert refined[0]-1 == 2*(base[0]-1)
    assert refined[4] == 2*base[4]
    assert refined[1:4] == base[1:4] and refined[5:] == base[5:]


def test_unknown_preset_does_not_create_output(tmp_path):
    out = tmp_path/'unknown'
    with pytest.raises(ValueError, match='Unknown'):
        run(out, 'unknown')
    assert not out.exists()


def test_existing_output_rejected(tmp_path):
    with pytest.raises(FileExistsError):
        run(tmp_path)


@pytest.mark.parametrize('kwargs', [{'radius_beams': 1.}, {'radius_beams': float('nan')},
                                   {'k_max': 0.}, {'k_max': float('inf')}])
def test_invalid_domain_rejected_before_output(tmp_path, kwargs):
    out = tmp_path/'invalid'
    with pytest.raises(ValueError, match='Finite'):
        run(out, **kwargs)
    assert not out.exists()
