import numpy as np
import pytest
from planing_seakeeping.aircraft_mass import component_mass_properties


def box(m=12,p=(0,0,0)):
    return {"mass_kg":m,"center_m":p,"dimensions_m":[1,2,3],"assumption":"test cuboid"}


def test_exact_box():
    r=component_mass_properties([box()])
    np.testing.assert_allclose(r["inertia_cg_kg_m2"],np.diag([13,10,5]))


def test_parallel_axis_and_translation():
    r=component_mass_properties([box(p=(-1,0,0)),box(p=(1,0,0))])
    np.testing.assert_allclose(r["inertia_cg_kg_m2"],np.diag([26,44,34]))
    r2=component_mass_properties([box(p=(9,0,0)),box(p=(11,0,0))])
    np.testing.assert_allclose(r2["inertia_cg_kg_m2"],r["inertia_cg_kg_m2"])


@pytest.mark.parametrize("mass",[0,-1,float("nan"),float("inf")])
def test_reject_mass(mass):
    with pytest.raises(ValueError):
        component_mass_properties([box(mass)])


def test_requires_provenance():
    c=box()
    del c["assumption"]
    with pytest.raises(ValueError):
        component_mass_properties([c])
