"""Conservative straight-trace transport candidate, not a production route."""
import numpy as np


def integrate_trace_transport(nodes, potential, weight):
    """Integrate phi'*w and phi*w' using one continuous linear reconstruction.

    Inputs phi and w are midpoint samples, NOT cell averages. The first/last
    two midpoint samples extrapolate to the endpoints. Each cell is split at
    its midpoint; linear products are integrated exactly on both halves.
    Call separately on each smooth trace, never across a chine or keel.
    """
    nodes = np.asarray(nodes, float)
    phi, w = np.asarray(potential, complex), np.asarray(weight, float)
    if (nodes.ndim != 1 or len(nodes) < 3 or phi.shape != (len(nodes)-1,)
            or w.shape != phi.shape or not all(np.isfinite(a).all() for a in (nodes, phi, w))
            or np.any(np.diff(nodes) <= 0)):
        raise ValueError('Finite increasing nodes and matching midpoint samples required')
    centers = (nodes[:-1]+nodes[1:])/2
    dphi = np.diff(phi)/np.diff(centers)
    dw = np.diff(w)/np.diff(centers)

    def evaluate(s):
        j = np.clip(np.searchsorted(centers, s, side='right')-1, 0, len(phi)-2)
        return phi[j]+dphi[j]*(s-centers[j]), w[j]+dw[j]*(s-centers[j])

    phi_integral, derivative_weight, potential_weight_derivative, product_integral = (
        np.zeros_like(phi) for _ in range(4))
    for i in range(len(phi)):
        for lo, hi in ((nodes[i], centers[i]), (centers[i], nodes[i+1])):
            p0, w0 = evaluate(lo)
            p1, w1 = evaluate(hi)
            h = hi-lo
            phi_integral[i] += h*(p0+p1)/2
            product_integral[i] += h*(2*p0*w0+p0*w1+p1*w0+2*p1*w1)/6
            derivative_weight[i] += (p1-p0)*(w0+w1)/2
            potential_weight_derivative[i] += (w1-w0)*(p0+p1)/2
    faces_phi, faces_w = evaluate(nodes)
    flux = np.diff(faces_phi*faces_w)
    return dict(potential_integral=phi_integral,
                potential_weight_integral=product_integral,
                potential_average=phi_integral/np.diff(nodes),
                derivative_weight_integral=derivative_weight,
                potential_weight_derivative_integral=potential_weight_derivative,
                face_potential=faces_phi, face_weight=faces_w, flux_difference=flux,
                residual=derivative_weight+potential_weight_derivative-flux)


def recover_straight_trace_pressure(nodes, potential, normal_derivative, material_gradient,
                                   mesh_tangent, mesh_normal, *, rho, speed, omega):
    """Return cell-averaged Eq. (30) pressure on ONE straight smooth trace.

    nodes are arc-length coordinates. Midpoint samples use a common, dephased
    harmonic convention. mesh_tangent/normal are the projections of transverse
    mesh displacement per unit longitudinal coordinate, not velocities in time.
    Normal and tangent must match those used for the boundary condition.
    This candidate is not wired into the production whole-ship force route.
    """
    if not np.isfinite([rho, speed, omega]).all() or rho <= 0 or speed < 0 or omega <= 0:
        raise ValueError('Positive density/frequency and nonnegative speed required')
    tangent = integrate_trace_transport(nodes, potential, mesh_tangent)
    normal = integrate_trace_transport(nodes, normal_derivative, mesh_normal)
    material = integrate_trace_transport(nodes, material_gradient, np.zeros_like(mesh_normal))
    chain = tangent['derivative_weight_integral']+normal['potential_weight_integral']
    time = -rho*1j*omega*tangent['potential_integral']
    forward = rho*speed*(material['potential_integral']-chain)
    return dict(pressure_average=(time+forward)/np.diff(nodes),
                time_pressure_average=time/np.diff(nodes),
                forward_pressure_average=forward/np.diff(nodes),
                chain_integral=chain, potential_average=tangent['potential_average'])
