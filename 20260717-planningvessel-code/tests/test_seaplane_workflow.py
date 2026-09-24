import copy
import json
from pathlib import Path

import numpy as np
import pytest

from planing_seakeeping.float_offsets import FloatStation, read_float_offsets
from planing_seakeeping.seaplane_workflow import (
    load_workflow,FloatHydrostatics,build_model,closed_assumed_mesh,mesh_audit,
    hydrostatic_pressure_check,refine_stations,simulate,transfer,run_workflow,
)

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def example():
    raw,base,path=load_workflow(ROOT/"configs/edo106k_workflow.json")
    stations=read_float_offsets(path)
    hydro=FloatHydrostatics(stations,8)
    return raw,base,stations,build_model(hydro,base,raw)


def test_analytic_rectangular_section():
    stations=[FloatStation(str(x),x,np.array([0.,1.]),np.array([0.,0.]),2.) for x in [0.,4.]]
    h=FloatHydrostatics(stations,8)
    area,moment,width=h.section_integrals(.5)
    np.testing.assert_allclose(area,1.)
    np.testing.assert_allclose(moment,.25)
    np.testing.assert_allclose(width,2.)
    np.testing.assert_allclose(h.evaluate([.5,0.],[2.,0.,1.],1000.,10.)["force"],[40000.,0.])


def test_section_dry_and_full():
    stations=[FloatStation(str(x),x,np.array([0.,1.]),np.array([0.,1.]),2.) for x in [0.,4.]]
    h=FloatHydrostatics(stations,4)
    area,_,width=h.section_integrals(-1.)
    np.testing.assert_allclose(area,0.)
    np.testing.assert_allclose(width,0.)
    area,first,width=h.section_integrals(3.)
    np.testing.assert_allclose(area,3.)
    np.testing.assert_allclose(first,11/3)
    np.testing.assert_allclose(width,0.)


def test_closed_mesh_pressure_and_equilibrium(example):
    raw,base,stations,m=example
    v,f,k=closed_assumed_mesh(refine_stations(stations,4))
    audit=mesh_audit(v,f)
    assert audit["boundary_edges"]==audit["nonmanifold_edges"]==audit["orientation_errors"]==0
    assert audit["volume_m3"]>0
    assert set(k)=={0,1}
    force,moment=hydrostatic_pressure_check(v,f,m["cg"],m["q0"],m["rho"],m["g"])
    weight=m["mass"]["mass_kg"]*m["g"]
    assert abs(force[2]/weight-1)<.002
    assert abs(moment)/(weight*m["hydro"].length)<.002
    assert np.linalg.norm(force[:2])/weight<.002
    assert m["static"]["volume"]==pytest.approx(m["mass"]["mass_kg"]/m["rho"],rel=1e-6)
    assert abs(m["static"]["force"][1])<1e-4
    assert np.linalg.eigvalsh(m["C"]).min()>0


def test_overloaded_mass_rejected(example):
    raw,base,stations,m=example
    overloaded=copy.deepcopy(base)
    for part in overloaded["mass_components"]:
        part["mass_kg"]*=10
    with pytest.raises(ValueError,match="equilibrium"):
        build_model(m["hydro"],overloaded,raw)


def test_equilibrium_stays_at_rest_and_decay_passive(example):
    *_,m=example
    t=np.linspace(0,10,201)
    rest=simulate(m,t,[],[],[])
    assert abs(rest.heave_m).max()==0
    assert abs(rest.pitch_rad).max()==0
    decay=simulate(m,t,[],[],[],initial=[.01,.002,0,0])
    assert np.diff(decay.energy_J).max()<1e-8


def test_long_wave_limit_and_sign(example):
    *_,m=example
    r,_=transfer(m,np.array([1e-5]))
    assert r[0,0].real==pytest.approx(1.,abs=1e-6)
    assert abs(r[0,1])<1e-6
    # Uniform upward displacement must reduce buoyancy.
    shifted=m["hydro"].evaluate(m["q0"]+[.001,0],m["cg"],m["rho"],m["g"])
    assert shifted["force"][0]<m["static"]["force"][0]


@pytest.mark.parametrize("key,value",[("speed_mps",10.),("modal_damping_ratio",float("nan")),
    ("added_mass_factor",-1.),("offsets_sha256","wrong"),("geometry_closure","unknown"),("output_step_s",1.)])
def test_bad_configuration_rejected(tmp_path,key,value):
    path=ROOT/"configs/edo106k_workflow.json"
    raw=json.loads(path.read_text())
    raw["base_parameters"]=str(ROOT/"configs/edo106k_synthetic_aircraft.json")
    raw[key]=value
    modified=tmp_path/"input.json"
    modified.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_workflow(modified)


def test_no_overwrite(tmp_path):
    (tmp_path/"existing.txt").write_text("evidence")
    with pytest.raises(ValueError,match="clean output"):
        run_workflow(ROOT/"configs/edo106k_workflow.json",tmp_path)
