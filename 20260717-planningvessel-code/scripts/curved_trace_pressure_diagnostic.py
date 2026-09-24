"""Diagnostic moving-curved-trace chain rule; not a conservative production replacement."""
import numpy as np


def recover_gradient(x, y, z, phi, normal_derivative, normal_y, normal_z):
    """Recover fixed-space x derivative using two separately differentiated hull sides.

    Midpoint arc distances approximate curved arc length. End derivatives are
    one-sided. The Neumann data must use the same geometric normal and physical
    harmonic phase as phi. Keel-side derivatives are never differenced across
    the corner. This is a consistency diagnostic, not validated pressure BEM.
    """
    x = np.asarray(x, float)
    arrays = [np.asarray(a) for a in (y, z, phi, normal_derivative, normal_y, normal_z)]
    y, z, phi, qn, ny, nz = arrays
    if (x.ndim != 1 or len(x) < 3 or not np.isfinite(x).all() or np.any(np.diff(x) <= 0)
            or y.ndim != 2 or y.shape[0] != len(x) or y.shape[1] < 6 or y.shape[1] % 2
            or any(a.shape != y.shape or not np.isfinite(a).all() for a in arrays)):
        raise ValueError('Matching finite two-sided traces and increasing stations required')
    if not np.allclose(ny**2+nz**2, 1., atol=1e-8, rtol=1e-8):
        raise ValueError('Unit geometric normals required')
    tangent_derivative = np.empty_like(phi, dtype=complex)
    half = y.shape[1]//2
    for start, end in ((0, half), (half, 2*half)):
        for i in range(len(x)):
            dy, dz = np.diff(y[i, start:end]), np.diff(z[i, start:end])
            ds = np.hypot(dy, dz)
            if np.any(ds <= 0):
                raise ValueError('Repeated trace midpoints')
            ty, tz = -nz[i, start:end], ny[i, start:end]
            if np.any(dy*(ty[:-1]+ty[1:])+dz*(tz[:-1]+tz[1:]) <= 0):
                raise ValueError('Trace ordering and normals disagree')
            s = np.r_[0., np.cumsum(ds)]
            tangent_derivative[i, start:end] = np.gradient(phi[i, start:end], s, edge_order=2)
    grad_y = -nz*tangent_derivative+ny*qn
    grad_z = ny*tangent_derivative+nz*qn
    yx = np.gradient(y, x, axis=0, edge_order=2)
    zx = np.gradient(z, x, axis=0, edge_order=2)
    material = np.gradient(phi, x, axis=0, edge_order=2)
    chain = yx*grad_y+zx*grad_z
    return dict(material=material, chain=chain, eulerian=material-chain,
                tangent_derivative=tangent_derivative, grad_y=grad_y, grad_z=grad_z)
