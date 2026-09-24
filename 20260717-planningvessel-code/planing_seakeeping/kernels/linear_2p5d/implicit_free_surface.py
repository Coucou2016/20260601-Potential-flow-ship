"""Experimental collocated trapezoidal BEM/free-surface coupling, not wired to production."""
import warnings
import numpy as np
from scipy.linalg import LinAlgWarning, lu_factor, lu_solve


class ImplicitFreeSurfaceStep:
    """Solve M u = R phi + h together with both new-time free-surface equations.

    q is a contiguous slice of u. History h must be evaluated at the NEW time
    using all known control states up to the old time. Geometry is frozen here;
    moving-section transfer and whole-ship applicability are not implemented.
    """

    def __init__(self, matrix, potential_rhs_map, q_start, dt, gravity=9.80665):
        self.matrix = np.array(matrix, dtype=complex, copy=True)
        self.rhs_map = np.array(potential_rhs_map, dtype=complex, copy=True)
        m, r = self.matrix, self.rhs_map
        if (m.ndim != 2 or m.shape[0] != m.shape[1] or not m.size or r.ndim != 2
                or r.shape[0] != len(m) or r.shape[1] < 1
                or not np.isfinite(m).all() or not np.isfinite(r).all()
                or not isinstance(q_start, int) or q_start < 0 or q_start+r.shape[1] > len(m)
                or not np.isfinite([dt, gravity]).all() or min(dt, gravity) <= 0):
            raise ValueError('Finite compatible matrix/map, valid q slice and positive timestep/gravity required')
        self.count = r.shape[1]
        self.q_slice = slice(q_start, q_start+self.count)
        self.dt, self.gravity = float(dt), float(gravity)
        self.alpha = gravity*dt**2/4
        coupled = m.copy()
        coupled[:, self.q_slice] += self.alpha*r
        with warnings.catch_warnings():
            warnings.simplefilter('error', LinAlgWarning)
            self.factorization = lu_factor(coupled)

    def advance(self, phi, eta, q_old, new_boundary_rhs):
        phi, eta, q_old, h = [np.asarray(a, complex) for a in (phi, eta, q_old, new_boundary_rhs)]
        if (any(a.shape != (self.count,) for a in (phi, eta, q_old))
                or h.shape != (len(self.matrix),)
                or any(not np.isfinite(a).all() for a in (phi, eta, q_old, h))):
            raise ValueError('Finite compatible state and new-time boundary RHS required')
        predictor = phi-self.gravity*self.dt*eta-self.alpha*q_old
        values = lu_solve(self.factorization, self.rhs_map@predictor+h)
        q_new = values[self.q_slice]
        phi_new = predictor-self.alpha*q_new
        eta_new = eta+self.dt/2*(q_old+q_new)
        reference_rhs = self.rhs_map@phi_new+h
        residual = np.linalg.norm(self.matrix@values-reference_rhs)/max(np.linalg.norm(reference_rhs), 1e-30)
        if not np.isfinite(values).all() or not np.isfinite(residual) or residual > 1e-10:
            raise ValueError('Implicit coupled solve failed finite/residual check')
        return dict(values=values, phi=phi_new, eta=eta_new, q=q_new, residual=float(residual))
