import pytest
import numpy as np
from dataclasses import dataclass
from scripts.probe_kang_implicit_marching import run
from scripts.probe_kang_implicit_marching import old_time_boundary_data


@pytest.mark.parametrize('count',[True,63,0,1024])
def test_unfrozen_history_quadrature_rejected_before_output(tmp_path,count):
    out=tmp_path/'case'
    with pytest.raises(ValueError,match='history quadrature'):
        run(out,321,'bounded_nearest_unvalidated',history_quadrature_count=count)
    assert not out.exists()


@pytest.mark.parametrize('cutoff',[True,0.,24.,float('nan')])
def test_unfrozen_history_cutoff_rejected_before_output(tmp_path,cutoff):
    out=tmp_path/'case'
    with pytest.raises(ValueError,match='history cutoff'):
        run(out,321,'bounded_nearest_unvalidated',history_k_max=cutoff)
    assert not out.exists()


@pytest.mark.parametrize('radius',[True,0.,2.,float('nan')])
def test_unfrozen_control_radius_rejected_before_output(tmp_path,radius):
    out=tmp_path/'case'
    with pytest.raises(ValueError,match='control radius'):
        run(out,321,'bounded_nearest_unvalidated',radius_beams=radius)
    assert not out.exists()


@pytest.mark.parametrize('stations,policy',[(40,'limited_linear_unvalidated'),(81,'auto')])
def test_unfrozen_or_implicit_policy_rejected_before_output(tmp_path,stations,policy):
    out=tmp_path/'case'
    with pytest.raises(ValueError):
        run(out,stations,policy)
    assert not out.exists()


def test_old_time_diagnostic_shifts_history_without_mutating_inputs():
    @dataclass
    class Data:
        free_surface_potential: np.ndarray
        body_normal_velocity: np.ndarray
        past_control_potential: np.ndarray
        past_control_normal_derivative: np.ndarray

    history=np.arange(12).reshape(3,4).astype(complex)
    data=Data(np.zeros(2),np.ones(2,dtype=complex),history,2*history)
    phi=np.array([1+2j,3+4j])
    old=old_time_boundary_data(data,phi,2.,.1)
    np.testing.assert_allclose(old.body_normal_velocity,np.exp(-.2j))
    np.testing.assert_array_equal(old.past_control_potential[:-1],history[1:])
    np.testing.assert_array_equal(old.past_control_normal_derivative[:-1],2*history[1:])
    np.testing.assert_array_equal(old.past_control_potential[-1],0)
    np.testing.assert_array_equal(data.past_control_potential,np.arange(12).reshape(3,4))
    old.free_surface_potential[0]=99
    assert phi[0]==1+2j


def test_unknown_velocity_policy_rejected_before_output(tmp_path):
    out=tmp_path/'case'
    with pytest.raises(ValueError,match='old-velocity policy'):
        run(out,161,'limited_linear_unvalidated',old_velocity_policy='auto')
    assert not out.exists()


def test_unknown_history_policy_rejected_before_output(tmp_path):
    out=tmp_path/'case'
    with pytest.raises(ValueError,match='history policy'):
        run(out,161,'limited_linear_unvalidated',history_policy='auto')
    assert not out.exists()


def test_unfrozen_frequency_rejected_before_output(tmp_path):
    out=tmp_path/'case'
    with pytest.raises(ValueError,match='frequency'):
        run(out,161,'bounded_nearest_unvalidated',frequency=9.)
    assert not out.exists()


@pytest.mark.parametrize('level',[0,3,True])
def test_unfrozen_transverse_refinement_rejected_before_output(tmp_path,level):
    out=tmp_path/'case'
    with pytest.raises(ValueError,match='transverse refinement'):
        run(out,641,'bounded_nearest_unvalidated',transverse_refinement=level)
    assert not out.exists()


@pytest.mark.parametrize('body,control',[(65,96),(64,100),(True,96)])
def test_unfrozen_body_control_counts_rejected_before_output(tmp_path,body,control):
    out=tmp_path/'case'
    with pytest.raises(ValueError,match='body/control'):
        run(out,321,'bounded_nearest_unvalidated',body_panel_count=body,control_panel_count=control)
    assert not out.exists()
