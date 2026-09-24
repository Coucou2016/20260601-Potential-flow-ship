import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.baseflow_linearization import graph_free_surface_residuals


def test_nonuniform_flow_against_nonlinear_surface_first_variation():
    velocity = np.array([[-3., .2, .1], [-2.8, -.3, .2]])
    jac = np.broadcast_to(np.array([[.3,.2,-.1],[.2,-.1,.4],[-.1,.4,-.2]]), (2,3,3))
    height = np.array([.1,.2])
    slope = np.array([[.2,.3],[-.1,.2]])
    phi = np.array([1+.4j, .2-.3j])
    grad = np.array([[.2+.3j,.4,.5j], [.3j,.1-.2j,.7]])
    eta = np.array([.2+.1j,.3-.2j])
    eta_h = np.array([[.1+.2j,.2],[-.3j,.1]])
    omega, gravity, constant = 2., 9.81, 4.
    result = graph_free_surface_residuals(velocity, jac, height, slope,
        phi, grad, eta, eta_h, omega, gravity, constant)

    def exact(eps):
        # Affine potential velocity evaluated on the vertically displaced graph.
        displaced_base = velocity+eps*eta[:,None]*jac[:,:,2]
        total = displaced_base+eps*grad
        kin = eps*1j*omega*eta+np.sum(total[:,:2]*(slope+eps*eta_h), axis=1)-total[:,2]
        dyn = (eps*1j*omega*(phi+eps*eta*grad[:,2])+.5*np.sum(total**2,axis=1)
               +gravity*(height+eps*eta)-constant)
        return kin, dyn

    step = 1e-5
    plus, minus = exact(step), exact(-step)
    for i, name in enumerate(('kinematic','dynamic')):
        np.testing.assert_allclose(result[name], (plus[i]-minus[i])/(2*step), atol=1e-9, rtol=1e-9)
        np.testing.assert_allclose(result['base_'+name], exact(0)[i], atol=1e-12)


@pytest.mark.parametrize('speed', [0., 3.4, 5.75])
@pytest.mark.parametrize('k', [.2, 1.])
def test_flat_uniform_stream_deep_water_dispersion(speed, k):
    gravity = 9.80665
    intrinsic = np.sqrt(gravity*k)
    omega = intrinsic+speed*k
    phi = np.array([1+.3j])
    eta = -1j*intrinsic*phi/gravity
    result = graph_free_surface_residuals(np.array([[-speed,0.,0.]]), np.zeros((1,3,3)),
        np.zeros(1), np.zeros((1,2)), phi, np.column_stack((1j*k*phi, 0*phi, k*phi)),
        eta, np.column_stack((1j*k*eta, 0*eta)), omega, gravity, .5*speed**2)
    for value in result.values():
        np.testing.assert_allclose(value, 0, atol=2e-14)
