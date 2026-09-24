import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from planing_seakeeping.kernels.linear_2p5d.baseflow_linearization import (
    rigid_motion_boundary_rhs, eulerian_pressure,
)


@pytest.mark.parametrize('mode', range(6))
def test_boundary_against_exact_rigid_surface_variation(mode):
    points = np.array([[.2,.3,.9], [.7,-.2,.5], [-.3,.8,.1]])
    normals = points/np.linalg.norm(points, axis=1)[:, None]
    # Symmetric trace-free Hessian gives an irrotational incompressible base field.
    jac = np.array([[.3,.2,-.1], [.2,-.1,.4], [-.1,.4,-.2]])
    uniform = np.array([-3., .1, -.2])
    velocity = points@jac.T+uniform
    translation, theta = np.zeros(3), np.zeros(3)
    (translation if mode < 3 else theta)[mode % 3] = 1.
    displacement = translation+np.cross(theta, points)
    result = rigid_motion_boundary_rhs(normals, velocity,
        np.broadcast_to(jac, (3,3,3)), displacement, theta, 2.3)

    def defect(epsilon):
        rotation = Rotation.from_rotvec(epsilon*theta).as_matrix()
        moved = points@rotation.T+epsilon*translation
        moved_normals = normals@rotation.T
        return np.sum((moved@jac.T+uniform)*moved_normals, axis=1)

    h = 1e-5
    derivative = (defect(h)-defect(-h))/(2*h)
    np.testing.assert_allclose(result['baseflow_sampling']+result['normal_rotation'],
                               -derivative, rtol=1e-8, atol=1e-9)
    np.testing.assert_allclose(result['rhs'], 2.3j*np.sum(normals*displacement, axis=1)-derivative,
                               rtol=1e-8, atol=1e-9)
    np.testing.assert_allclose(result['base_impermeability_residual'], defect(0))


def test_uniform_stream_pressure_reduces_to_current_formula():
    phi = np.array([1+2j, 3-.2j])
    grad = np.array([[.3+.4j, 2, 3], [.5j, 1, 4]])
    velocity = np.tile([-4.,0,0], (2,1))
    np.testing.assert_allclose(eulerian_pressure(phi, grad, velocity, 3., 1000.),
                               -1000*(3j*phi-4*grad[:,0]))


def test_nonunit_normals_rejected():
    with pytest.raises(ValueError, match='Unit normals'):
        rigid_motion_boundary_rhs(np.ones((2,3)), np.zeros((2,3)),
            np.zeros((2,3,3)), np.zeros((2,3)), np.zeros(3), 1.)
