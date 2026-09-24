import numpy as np
import pytest
from scripts.integrated_trace_transport import integrated_fixed_space_derivative


def test_moving_v_contour_transport_converges_to_fixed_space_integral():
    errors=[]
    # phi=x^2+z on z=d(x)*(1-|y|/a(x)); phi_x=2x at fixed y,z.
    # Exact heave integral is integral(-4*x*(1+.1*x)) dx on [0,2].
    exact_heave=-4*(2.+.1*8/3)
    # Moment arm is 1-x; integrate -4*(x-.9*x^2-.1*x^3).
    exact_pitch=-4*(2.-.9*8/3-.1*4)
    for n in (17,33,65):
        x=np.linspace(0,2,n); a=1+.1*x; d=1+.05*x
        section=-2*a*x*x-a*d
        edge=-.2*x*x
        shape=-.1*d-.05*a
        result=integrated_fixed_space_derivative(x,section,edge,shape,1.)
        errors.append(np.linalg.norm(result-[exact_heave,exact_pitch]))
    assert errors[1]<.26*errors[0] and errors[2]<.26*errors[1]
    assert errors[-1]<.001


def test_stationary_potential_geometry_change_does_not_create_force():
    x=np.linspace(0,2,17); a=1+.1*x
    result=integrated_fixed_space_derivative(x,-2*a,np.full_like(x,-.2),np.zeros_like(x),1.)
    np.testing.assert_allclose(result,0,atol=1e-14)


def test_nonfinite_and_unordered_traces_rejected():
    with pytest.raises(ValueError):
        integrated_fixed_space_derivative([0,2,1],[1,1,1],[0,0,0],[0,0,0],1.)
