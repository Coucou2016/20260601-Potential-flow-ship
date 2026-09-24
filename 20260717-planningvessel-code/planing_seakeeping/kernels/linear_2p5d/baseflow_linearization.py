"""Fixed-frame perturbation operators; no steady-flow solver is supplied here.

All vectors use one caller-declared Cartesian frame. Velocity includes the
uniform hull-frame stream. Its Jacobian is J[..., i, j] = dV_i/dx_j.
Pressure is Eulerian; moving-surface pressure and load variations are separate.
"""
import numpy as np


def _vectors(*values):
    arrays = [np.asarray(v) for v in values]
    if (not arrays or arrays[0].ndim != 2 or arrays[0].shape[1] != 3
            or any(a.shape != arrays[0].shape or not np.isfinite(a).all() for a in arrays)):
        raise ValueError('Matching finite arrays of shape (panels, 3) required')
    return arrays


def rigid_motion_boundary_rhs(normals, base_velocity, velocity_jacobian,
                              displacement, rotation, omega):
    """Linearized n.grad(phi) for rigid displacement about the mean surface.

    Does not enforce zero-order impermeability; returns its residual explicitly.
    Rotation is the small angular-displacement vector, not angular velocity.
    """
    n, velocity, d = _vectors(normals, base_velocity, displacement)
    jac = np.asarray(velocity_jacobian)
    theta = np.asarray(rotation)
    if (jac.shape != (len(n), 3, 3) or not np.isfinite(jac).all()
            or theta.shape != (3,) or not np.isfinite(theta).all()
            or not np.isfinite(omega) or omega <= 0):
        raise ValueError('Finite Jacobian, rotation vector and positive frequency required')
    if np.iscomplexobj(n) or np.iscomplexobj(velocity) or np.iscomplexobj(jac):
        raise ValueError('Mean geometry and steady velocity must be real')
    if not np.allclose(np.linalg.norm(n, axis=1), 1., rtol=1e-10, atol=1e-12):
        raise ValueError('Unit normals required')
    oscillatory = 1j*omega*np.sum(n*d, axis=1)
    sampling = -np.sum(n*np.einsum('nij,nj->ni', jac, d), axis=1)
    normal_rotation = -np.sum(np.cross(theta, n)*velocity, axis=1)
    return dict(rhs=oscillatory+sampling+normal_rotation,
                oscillatory=oscillatory, baseflow_sampling=sampling,
                normal_rotation=normal_rotation,
                base_impermeability_residual=np.sum(n*velocity, axis=1))


def eulerian_pressure(phi, gradient, base_velocity, omega, rho):
    """-rho*(i*omega*phi + V0.grad(phi)); not total moving-body pressure."""
    gradient, velocity = _vectors(gradient, base_velocity)
    phi = np.asarray(phi)
    if (phi.shape != (len(gradient),) or not np.isfinite(phi).all()
            or not np.isfinite([omega, rho]).all() or omega <= 0 or rho <= 0
            or np.iscomplexobj(velocity)):
        raise ValueError('Finite panel potentials, real base velocity, positive frequency/density required')
    return -rho*(1j*omega*phi+np.sum(velocity*gradient, axis=1))


def graph_free_surface_residuals(base_velocity, velocity_jacobian, mean_height,
                                mean_slope, phi, gradient, elevation,
                                elevation_gradient, omega, gravity, bernoulli_constant):
    """First variations at z=mean_height with z UP, constant atmospheric pressure.

    Spatial gradients of phi are Eulerian; elevation gradients are horizontal
    graph gradients. All base fields are evaluated on the mean free surface.
    Returns residuals, not solved boundary values. The Bernoulli gauge is explicit.
    """
    velocity, grad = _vectors(base_velocity, gradient)
    count = len(velocity)
    jac = np.asarray(velocity_jacobian)
    height, slope = np.asarray(mean_height), np.asarray(mean_slope)
    phi, eta, eta_h = np.asarray(phi), np.asarray(elevation), np.asarray(elevation_gradient)
    if (jac.shape != (count, 3, 3) or height.shape != (count,)
            or slope.shape != (count, 2) or phi.shape != (count,)
            or eta.shape != (count,) or eta_h.shape != (count, 2)
            or not all(np.isfinite(a).all() for a in (jac, height, slope, phi, eta, eta_h))
            or any(np.iscomplexobj(a) for a in (velocity, jac, height, slope))
            or not np.isfinite([omega, gravity, bernoulli_constant]).all()
            or omega <= 0 or gravity <= 0):
        raise ValueError('Matching finite surface fields, real base flow and positive frequency/gravity required')
    vertical_sampling = np.sum(jac[:, :2, 2]*slope, axis=1)-jac[:, 2, 2]
    kinematic = (1j*omega*eta+np.sum(velocity[:, :2]*eta_h, axis=1)
                 +np.sum(grad[:, :2]*slope, axis=1)-grad[:, 2]+eta*vertical_sampling)
    dynamic = (1j*omega*phi+np.sum(velocity*grad, axis=1)
               +eta*(gravity+np.sum(velocity*jac[:, :, 2], axis=1)))
    return dict(kinematic=kinematic, dynamic=dynamic,
        base_kinematic=np.sum(velocity[:, :2]*slope, axis=1)-velocity[:, 2],
        base_dynamic=.5*np.sum(velocity**2, axis=1)+gravity*height-bernoulli_constant)
