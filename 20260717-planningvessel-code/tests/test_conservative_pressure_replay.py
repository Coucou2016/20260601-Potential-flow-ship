import numpy as np
import pytest
from scripts.audit_conservative_pressure_replay import recover_v_sweep


def fields():
    x = np.array([0., .2, .7, 1.])
    width = 2+.4*x
    y = width[:, None]*np.array([5, 3, 1, -1, -3, -5])[None, :]/12
    z = .3*(width[:, None]/2-abs(y))
    a, b, c = 1+.3j, .7-.2j, -.4+.5j
    phi = a*x[:, None]+b*y+c*z
    nz = 1/np.sqrt(1+.3**2)
    qn = b*np.sign(y)*.3*nz+c*nz
    material = a+b*np.gradient(y,x,axis=0)+c*np.gradient(z,x,axis=0)
    return x,y,z,phi,qn,material,-width[:,None]*np.ones((1,6))/6,a


def test_v_sweep_pressure_matches_affine_spatial_reference():
    x,y,z,phi,qn,material,j3,a = fields()
    result = recover_v_sweep(x,y,z,phi,qn,material,j3,rho=1025.,speed=8.,omega=4.)
    np.testing.assert_allclose(result,-1025*4j*phi+1025*8*a,rtol=1e-12,atol=1e-10)


def test_curved_sides_are_not_silently_treated_as_straight():
    x,y,z,phi,qn,material,j3,_ = fields()
    with pytest.raises(ValueError,match='straight'):
        recover_v_sweep(x,y,z+.1*y**2,phi,qn,material,j3,rho=1025.,speed=8.,omega=4.)
