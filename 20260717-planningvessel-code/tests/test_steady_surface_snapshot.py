from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest
from scripts.steady_surface_snapshot import export_surface_history
from scripts.compare_steady_surface_history import run as compare
import pandas as pd


@dataclass
class Config:
    label: str = 'manufactured'
    chine_half_beam_m: float = .5
    body_panels_per_side: int = 4
    free_surface_panels_per_side: int = 5


def test_numeric_archive_preserves_coordinates_and_potential_locations(tmp_path):
    state = SimpleNamespace(time_s=0., jet_cut_count=2,
        right_free_y_m=np.array([1.,2.,3.]), right_free_z_up_m=np.array([.1,.2,.3]),
        left_free_y_m=np.array([-3.,-2.,-1.]), left_free_z_up_m=np.array([.3,.2,.1]),
        right_free_potential_m2_s=np.array([4.,5.]), left_free_potential_m2_s=np.array([5.,4.]))
    result = SimpleNamespace(states=[state], time_s=np.array([0.]), draft_m=np.array([.1]),
        vertical_force_per_length_n_m=np.array([20.]), reference_draft_m=.3)
    path = tmp_path/'state.npz'
    options = dict(speed=2., trim=.1, length=3., initial_draft=.1)
    export_surface_history(path, result, Config(), **options)
    with np.load(path, allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved['0_right_potential_m2_s'], [4.,5.])
        np.testing.assert_allclose(saved['x_from_transom_m'], [3.-.1/np.tan(.1)])
    with pytest.raises(FileExistsError):
        export_surface_history(path, result, Config(), **options)
    other = tmp_path/'other.npz'
    export_surface_history(other, result, Config(), **options)
    compare(path, other, tmp_path/'comparison')
    frame = pd.read_csv(tmp_path/'comparison/surface_comparison.csv')
    assert (frame.status == 'COMPARED').all()
    assert (frame.elevation_max_over_beam == 0).all()
    assert (frame.potential_rms_over_speed_beam == 0).all()
    finer = tmp_path/'finer.npz'
    export_surface_history(finer, result, Config(body_panels_per_side=8), **options)
    with pytest.raises(ValueError, match='configuration'):
        compare(path, finer, tmp_path/'not_time_refinement')
    compare(path, finer, tmp_path/'spatial', spatial_refinement=True)
    changed = tmp_path/'changed.npz'
    export_surface_history(changed, result, Config(chine_half_beam_m=.6), **options)
    with pytest.raises(ValueError, match='configuration'):
        compare(path, changed, tmp_path/'not_spatial_refinement', spatial_refinement=True)
    state.time_s = 1.
    with pytest.raises(ValueError, match='time'):
        export_surface_history(tmp_path/'bad.npz', result, Config(), **options)
    assert not (tmp_path/'bad.npz').exists()
