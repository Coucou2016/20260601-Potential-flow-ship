"""Candidate Eulerian pressure-gradient recovery on moving section panels.

Explicit corners delimit smooth traces. This module is not a default solver
route; normals and normal derivatives must use the same boundary convention.
"""
from __future__ import annotations

import numpy as np


def transverse_velocity(body, potential, normal_derivative, *, corner_nodes=()):
    phi, qn = np.asarray(potential, complex), np.asarray(normal_derivative, complex)
    n = body.panel_count
    if phi.shape != (n,) or qn.shape != (n,) or n < 2:
        raise ValueError("Potential and normal derivative must match at least two panels")
    if not np.isfinite(phi).all() or not np.isfinite(qn).all():
        raise ValueError("Boundary data must be finite")
    nodes = np.column_stack((body.node_y_m, body.node_z_down_m))
    normals = np.column_stack((body.normal_y, body.normal_z))
    if nodes.shape != (n+1, 2) or normals.shape != (n, 2) or not np.isfinite(nodes).all():
        raise ValueError("Invalid panel geometry")
    delta = np.diff(nodes, axis=0)
    length = np.linalg.norm(delta, axis=1)
    if np.any(length <= 0) or not np.allclose(length, body.length_m, rtol=1e-10, atol=1e-12):
        raise ValueError("Invalid panel lengths")
    tangent = delta / length[:, None]
    if (not np.isfinite(normals).all() or not np.allclose(np.linalg.norm(normals, axis=1), 1)
            or not np.allclose(np.sum(normals*tangent, axis=1), 0, atol=1e-10)):
        raise ValueError("Normals must be unit and perpendicular to tangents")
    corners = tuple(corner_nodes)
    if any(type(i) is not int or not 0 < i < n for i in corners) or list(corners) != sorted(set(corners)):
        raise ValueError("corner_nodes must be sorted unique interior node indices")
    s = np.cumsum(length)-length/2
    derivative = np.empty(n, complex)
    bounds = (0, *corners, n)
    for start, end in zip(bounds[:-1], bounds[1:]):
        count = end-start
        if count < 2:
            raise ValueError("Each smooth trace needs at least two panels")
        derivative[start:end] = np.gradient(phi[start:end], s[start:end], edge_order=2 if count >= 3 else 1)
    velocity = derivative[:, None]*tangent + qn[:, None]*normals
    return velocity[:, 0], velocity[:, 1]


def remove_geometry_chain_term(x, bodies, material_gradient, potential, normal_derivative, *, corner_nodes=()):
    """Subtract phi_y*y_x + phi_z*z_x from a dephased panel-index derivative."""
    x = np.asarray(x, float)
    material = np.asarray(material_gradient, complex)
    phi, qn = np.asarray(potential, complex), np.asarray(normal_derivative, complex)
    if x.ndim != 1 or len(x) < 3 or not np.isfinite(x).all() or np.any(np.diff(x) <= 0):
        raise ValueError("At least three finite increasing stations are required")
    if len(bodies) != len(x) or material.ndim != 2 or material.shape[0] != len(x):
        raise ValueError("Station shapes do not match")
    if phi.shape != material.shape or qn.shape != phi.shape or not np.isfinite(material).all():
        raise ValueError("Potential, normal derivative and gradient shapes/data do not match")
    velocities = [transverse_velocity(b, p, q, corner_nodes=corner_nodes)
                  for b, p, q in zip(bodies, phi, qn, strict=True)]
    y = np.asarray([b.mid_y_m for b in bodies])
    z = np.asarray([b.mid_z_down_m for b in bodies])
    if y.shape != phi.shape or z.shape != phi.shape:
        raise ValueError("Panel correspondence requires equal panel counts")
    vy = np.asarray([v[0] for v in velocities])
    vz = np.asarray([v[1] for v in velocities])
    chain = vy*np.gradient(y,x,axis=0,edge_order=2)+vz*np.gradient(z,x,axis=0,edge_order=2)
    return material-chain, chain
