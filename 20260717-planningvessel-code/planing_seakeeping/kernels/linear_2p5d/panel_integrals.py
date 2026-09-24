"""Exact log-kernel integrals for straight constant panels (candidate only)."""
import numpy as np
from contextlib import contextmanager
from contextvars import ContextVar
from collections import OrderedDict
import hashlib


_route = ContextVar('linear_2p5d_panel_integration', default='midpoint')
_operator_cache = ContextVar('linear_2p5d_reconstructed_cache', default=None)


@contextmanager
def panel_integration_route(route, *, cache_operators=True):
    """Explicit task-local diagnostic route; restore even when a solve fails."""
    if route not in ('midpoint', 'analytic_straight_midpoint_curved', 'reconstructed_symmetric'):
        raise ValueError('Unknown panel integration route')
    token = _route.set(route)
    cache_token = _operator_cache.set(OrderedDict() if cache_operators else None)
    try:
        yield
    finally:
        _operator_cache.reset(cache_token)
        _route.reset(token)


def current_panel_integration_route():
    return _route.get()


def reconstructed_candidate_operators(field, source, **kwargs):
    """Explicit symmetric-body/two-sided-free/circular-control candidate.

    Straight body and free traces are split at their symmetry index. This is
    deliberately not a general multi-body topology detector.
    """
    from .reconstructed_operators import reconstructed_log_operators
    cache = _operator_cache.get()
    key = None
    if cache is not None:
        digest = hashlib.sha256(repr(sorted(kwargs.items())).encode('ascii'))
        for geometry, names in ((field, ('mid_y_m','mid_z_down_m')),
                (source, ('mid_y_m','mid_z_down_m','normal_y','normal_z','length_m','node_y_m','node_z_down_m'))):
            for name in names:
                values = np.ascontiguousarray(getattr(geometry, name), dtype=float)
                digest.update(repr(values.shape).encode('ascii'))
                digest.update(values.tobytes())
        key = digest.digest()
        if key in cache:
            cache.move_to_end(key)
            return tuple(a.copy() for a in cache[key])
    straight = use_exact_straight_panels(source)
    n = len(source.length_m)
    if straight and (n < 4 or n % 2):
        raise ValueError('Reconstructed symmetric route requires even traces with >= 4 panels')
    result = reconstructed_log_operators(field, source,
        geometry_kind='straight' if straight else 'circular',
        breaks=(n//2,) if straight else (), **kwargs)
    if cache is not None:
        cache[key] = tuple(a.copy() for a in result)
        while len(cache) > 128:
            cache.popitem(last=False)
    return result


def use_exact_straight_panels(source):
    if _route.get() == 'midpoint':
        return False
    nodes = np.column_stack((source.node_y_m, source.node_z_down_m))
    count = len(source.length_m)
    starts, ends = nodes[:-1], nodes[1:]
    if len(nodes) == count+2:
        # Two disconnected free-surface sides have one inter-body gap.
        starts = np.delete(starts,count//2,axis=0)
        ends = np.delete(ends,count//2,axis=0)
    if len(starts) != count:
        raise ValueError('Unsupported panel-node topology')
    centers = np.column_stack((source.mid_y_m,source.mid_z_down_m))
    normals = np.column_stack((source.normal_y,source.normal_z))
    delta = ends-starts
    return (np.allclose((starts+ends)/2,centers,rtol=1e-10,atol=1e-12)
            and np.allclose(np.linalg.norm(delta,axis=1),source.length_m,rtol=1e-10,atol=1e-12)
            and np.allclose(np.sum(delta*normals,axis=1),0,atol=1e-12))


def straight_log_integrals(field, source, *, mirrored_source=False,
                           same_boundary=False, diagonal_sign=1.):
    """Return raw integral(log r) and integral(d log r / d n_source).

    Tangent orientation is immaterial for a centered constant panel. Reflection
    applies to both source location and normal. The direct self normal entry
    retains the caller's BIE jump convention, not a pointwise singular value.
    """
    def coordinates(geometry):
        return np.column_stack((geometry.mid_y_m, geometry.mid_z_down_m)).astype(float)

    target, center = coordinates(field), coordinates(source)
    normal = np.column_stack((source.normal_y, source.normal_z)).astype(float)
    length = np.asarray(source.length_m, float)
    if (target.ndim != 2 or target.shape[1] != 2 or center.shape != normal.shape
            or length.shape != (len(center),) or not np.isfinite(target).all()
            or not np.isfinite(center).all() or not np.isfinite(normal).all()
            or not np.isfinite(length).all() or np.any(length <= 0)
            or not np.allclose(np.linalg.norm(normal, axis=1), 1, atol=1e-12, rtol=1e-12)):
        raise ValueError('Finite geometry, positive lengths and unit normals required')
    if not np.isfinite(diagonal_sign):
        raise ValueError('diagonal_sign must be finite')
    if same_boundary and not (target.shape == center.shape and np.array_equal(target, center)):
        raise ValueError('same_boundary requires coincident collocation points')
    if mirrored_source:
        center[:, 1] *= -1
        normal[:, 1] *= -1
    tangent = np.column_stack((-normal[:, 1], normal[:, 0]))
    relative = target[:, None, :] - center[None, :, :]
    q = np.sum(relative*tangent[None, :, :], axis=2)
    h = np.sum(relative*normal[None, :, :], axis=2)
    lo, hi = -length[None, :]/2-q, length[None, :]/2-q
    height = np.abs(h)

    def primitive(u):
        radius = np.hypot(u, height)
        log_radius = np.log(np.maximum(radius, np.finfo(float).tiny))
        return u*log_radius-u+height*np.arctan2(u, height)

    potential = primitive(hi)-primitive(lo)
    normal_integral = -np.sign(h)*(np.arctan2(hi, height)-np.arctan2(lo, height))
    if same_boundary and not mirrored_source:
        np.fill_diagonal(potential, length*(np.log(length/2)-1))
        np.fill_diagonal(normal_integral, float(diagonal_sign)*np.pi)
    return potential, normal_integral
