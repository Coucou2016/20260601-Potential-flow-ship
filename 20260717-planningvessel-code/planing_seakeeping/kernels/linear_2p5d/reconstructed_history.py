"""Candidate circular-control history operators; not a production backend."""
import numpy as np
from numpy.polynomial.legendre import leggauss

from .reconstructed_operators import derivative_matrix


def reconstructed_history_operators(field, source, lag_s, *, gravity=9.80665,
                                    spectral_count=96, k_max=25., order=32):
    """Integrate the existing finite-cutoff transient kernel with linear traces.

    Returns potential and source-normal arrays [lag, field, source]. Spatial
    first moments use the same arc-length derivative as the log operators.
    Temporal convolution weights and phase conventions remain the caller's job.
    """
    lag = np.asarray(lag_s, dtype=float)
    if lag.ndim != 1 or not len(lag) or not np.isfinite(lag).all() or np.any(lag <= 0):
        raise ValueError('Positive finite one-dimensional lags required')
    if not np.isfinite(gravity) or gravity <= 0 or not np.isfinite(k_max) or k_max <= 0:
        raise ValueError('Positive finite gravity and cutoff required')
    if type(order) is not int or order < 8 or type(spectral_count) is not int or spectral_count < 16:
        raise ValueError('Integer spatial order >= 8 and spectral count >= 16 required')
    y, z = np.asarray(source.mid_y_m), np.asarray(source.mid_z_down_m)
    length = np.asarray(source.length_m)
    radius = np.hypot(y, z)
    if (not np.isfinite(radius).all() or np.any(radius <= 0)
            or not np.allclose(radius, radius[0], rtol=1e-12)
            or not np.allclose(source.normal_y, y / radius)
            or not np.allclose(source.normal_z, z / radius)):
        raise ValueError('Circular source with outward radial normals required')
    d = derivative_matrix(length)
    fy, fz = np.asarray(field.mid_y_m), np.asarray(field.mid_z_down_m)
    if fy.ndim != 1 or fz.shape != fy.shape or not np.isfinite(fy).all() or not np.isfinite(fz).all() or np.any(fz < 0):
        raise ValueError('Finite submerged field points required')
    xi, w = leggauss(order)
    s = np.linspace(0., np.sqrt(k_max), spectral_count)
    k = s ** 2
    sw = np.zeros_like(s)
    sw[:-1] += np.diff(s) / 2
    sw[1:] += np.diff(s) / 2
    temporal = 4 * np.sqrt(gravity) * np.sin(np.sqrt(gravity) * lag[:, None] * s) * sw
    shape = (len(lag), len(fy), len(y))
    p0, p1, a0, a1 = (np.zeros(shape) for _ in range(4))
    # Integrate one source panel at a time to bound the spectral workspace.
    for j in range(len(y)):
        offset = length[j] * xi / 2
        theta = np.arctan2(z[j], y[j]) + offset / radius[j]
        ny, nz = np.cos(theta), np.sin(theta)
        if np.any(nz < -1e-13):
            raise ValueError('Source arcs must remain submerged')
        dy = fy[:, None, None] - radius[j] * ny[None, :, None]
        depth = fz[:, None, None] + radius[j] * nz[None, :, None]
        exponential = np.exp(-depth * k)
        cosine = np.cos(dy * k)
        potential = exponential * cosine
        normal = exponential * k * (np.sin(dy * k) * ny[None, :, None] - cosine * nz[None, :, None])
        weight = length[j] * w / 2
        for kernel, constant, moment in ((potential, p0, p1), (normal, a0, a1)):
            constant[:, :, j] = temporal @ np.sum(kernel * weight[None, :, None], axis=1).T
            moment[:, :, j] = temporal @ np.sum(kernel * (weight * offset)[None, :, None], axis=1).T
    return p0 + p1 @ d, a0 + a1 @ d
