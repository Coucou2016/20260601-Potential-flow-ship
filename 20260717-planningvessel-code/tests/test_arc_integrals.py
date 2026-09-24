from types import SimpleNamespace
import numpy as np
import pytest
from scipy.integrate import quad
from planing_seakeeping.kernels.linear_2p5d.formulation import build_control_surface_geometry
from planing_seakeeping.kernels.linear_2p5d.arc_integrals import circular_arc_integrals


@pytest.mark.parametrize('point',[(1.29,0.),(.1,.3),(-1.29,0.)])
def test_independent_arc_integrals(point):
    radius=1.3
    source=build_control_surface_geometry(radius,24)
    field=SimpleNamespace(mid_y_m=np.array([point[0]]),mid_z_down_m=np.array([point[1]]))
    p,a=circular_arc_integrals(field,source,order=64)
    for j in (0,12,23):
        lo,hi=j*np.pi/24,(j+1)*np.pi/24
        def potential(t):
            return radius*np.log(np.hypot(point[0]-radius*np.cos(t),point[1]-radius*np.sin(t)))
        def normal(t):
            dy,dz=point[0]-radius*np.cos(t),point[1]-radius*np.sin(t)
            return -radius*(dy*np.cos(t)+dz*np.sin(t))/(dy*dy+dz*dz)
        np.testing.assert_allclose([p[0,j],a[0,j]],
            [quad(potential,lo,hi,epsabs=1e-12)[0],quad(normal,lo,hi,epsabs=1e-12)[0]],atol=1e-10,rtol=1e-10)


def test_self_log_integral_and_curvature():
    source=build_control_surface_geometry(1.3,24)
    p,a=circular_arc_integrals(source,source,order=32,same_boundary=True)
    h=np.pi/48
    reference=2*1.3*quad(lambda t:np.log(2*1.3*np.sin(t/2)),0,h,epsabs=1e-12)[0]
    np.testing.assert_allclose(np.diag(p),reference,atol=1e-12)
    np.testing.assert_allclose(np.diag(a),-np.pi+h,atol=1e-12)


@pytest.mark.parametrize('order',[True,0,7,32.])
def test_bad_order_rejected(order):
    source=build_control_surface_geometry(1.3,24)
    with pytest.raises(ValueError,match='order'):
        circular_arc_integrals(source,source,order=order)


def test_bad_self_points_rejected():
    source=build_control_surface_geometry(1.3,24)
    field=SimpleNamespace(mid_y_m=source.mid_y_m+.01,mid_z_down_m=source.mid_z_down_m)
    with pytest.raises(ValueError,match='matching'):
        circular_arc_integrals(field,source,same_boundary=True)
