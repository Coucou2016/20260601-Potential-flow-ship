from dataclasses import replace
import numpy as np
from planing_seakeeping.kernels.linear_2p5d.formulation import build_control_surface_geometry
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route, reconstructed_candidate_operators, _operator_cache


def test_cache_is_exact_and_protects_values_from_mutation():
    geometry = build_control_surface_geometry(1.3, 12)
    with panel_integration_route('reconstructed_symmetric', cache_operators=False):
        reference = reconstructed_candidate_operators(geometry, geometry, same_boundary=True)
    with panel_integration_route('reconstructed_symmetric'):
        first = reconstructed_candidate_operators(geometry, geometry, same_boundary=True)
        first[0][:] = 999
        second = reconstructed_candidate_operators(geometry, geometry, same_boundary=True)
        for a,b in zip(second,reference):
            np.testing.assert_array_equal(a,b)
        assert len(_operator_cache.get()) == 1
    assert _operator_cache.get() is None


def test_key_includes_geometry_and_jump_and_mirror():
    geometry = build_control_surface_geometry(1.3, 8)
    with panel_integration_route('reconstructed_symmetric'):
        for sign in (-1.,1.):
            reconstructed_candidate_operators(geometry,geometry,same_boundary=True,diagonal_sign=sign)
        reconstructed_candidate_operators(geometry,geometry,mirrored_source=True)
        field = replace(geometry,mid_z_down_m=geometry.mid_z_down_m+.01)
        reconstructed_candidate_operators(field,geometry)
        assert len(_operator_cache.get()) == 4
        with panel_integration_route('midpoint'):
            assert len(_operator_cache.get()) == 0
        assert len(_operator_cache.get()) == 4
