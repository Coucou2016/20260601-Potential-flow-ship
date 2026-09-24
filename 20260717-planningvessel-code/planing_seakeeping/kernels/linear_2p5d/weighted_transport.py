"""Diagnostic weighted transport identity on a moving sectional mesh."""
import numpy as np


def clipped_transport_identity(x, potential, measure, chain, cutoff):
    """Integrate (material dphi/dx - chain)*measure on [cutoff,x[-1]].

    Potential/chain have shape [station,panel]; measure has shape
    [station,panel,row]. All traces are piecewise linear. Two-point Gauss
    integration is exact for their products; no pressure convention is imposed.
    """
    x = np.asarray(x,float)
    phi, j, chain = np.asarray(potential), np.asarray(measure), np.asarray(chain)
    if (x.ndim != 1 or len(x)<2 or phi.ndim != 2 or chain.shape != phi.shape
            or phi.shape[0] != len(x) or j.ndim != 3 or j.shape[:2] != phi.shape):
        raise ValueError('Matching station, panel and row dimensions required')
    if (not all(np.isfinite(a).all() for a in (x,phi,j,chain)) or np.any(np.diff(x)<=0)
            or not np.isfinite(cutoff) or not x[0] <= cutoff < x[-1]):
        raise ValueError('Finite traces and a cutoff within the increasing grid required')
    direct, bulk, chain_term, potential_measure = (np.zeros(j.shape[2],complex) for _ in range(4))
    for index,dx in enumerate(np.diff(x)):
        lo,hi = max(x[index],cutoff),x[index+1]
        if hi<=lo:
            continue
        position = (lo+hi)/2 + (hi-lo)/(2*np.sqrt(3))*np.array([-1.,1.])
        t = (position-x[index])/dx
        p = phi[index]+t[:,None]*(phi[index+1]-phi[index])
        m = j[index]+t[:,None,None]*(j[index+1]-j[index])
        c = chain[index]+t[:,None]*(chain[index+1]-chain[index])
        dp,dj = (phi[index+1]-phi[index])/dx,(j[index+1]-j[index])/dx
        factor = (hi-lo)/2
        potential_measure += factor*np.sum(p[:,:,None]*m,axis=(0,1))
        direct += factor*np.sum((dp[None,:,None]-c[:,:,None])*m,axis=(0,1))
        bulk -= factor*np.sum(p[:,:,None]*dj[None,:,:],axis=(0,1))
        chain_term -= factor*np.sum(c[:,:,None]*m,axis=(0,1))
    left = min(int(np.searchsorted(x,cutoff,side='right')-1),len(x)-2)
    t = (cutoff-x[left])/(x[left+1]-x[left])
    p_edge = phi[left]+t*(phi[left+1]-phi[left])
    j_edge = j[left]+t*(j[left+1]-j[left])
    lower_edge = -np.sum(p_edge[:,None]*j_edge,axis=0)
    upper_edge = np.sum(phi[-1,:,None]*j[-1],axis=0)
    transformed = bulk+chain_term+lower_edge+upper_edge
    return dict(direct=direct,bulk=bulk,chain=chain_term,lower_edge=lower_edge,
                upper_edge=upper_edge,transformed=transformed,residual=direct-transformed,
                potential_measure=potential_measure)


def clipped_pressure_identity(x, potential, measure, chain, cutoff, *, rho, speed, omega):
    """Diagnostic Eq. (30) pressure integral, before any forcing phase adapter.

    The supplied measure must already carry the force/moment sign convention.
    This is a consistency identity on interpolated fields, not a validated
    replacement for the production Eq. (32) radiation assembly.
    """
    if (not np.isfinite([rho, speed, omega]).all()
            or rho <= 0 or speed < 0 or omega <= 0):
        raise ValueError('Positive density/frequency and nonnegative speed required')
    terms = clipped_transport_identity(x, potential, measure, chain, cutoff)
    time = -rho*1j*omega*terms['potential_measure']
    result = {name: rho*speed*terms[name] for name in
              ('bulk', 'chain', 'lower_edge', 'upper_edge')}
    result['time'] = time
    result['direct'] = time + rho*speed*terms['direct']
    result['transformed'] = time + sum(result[name] for name in
                                     ('bulk', 'chain', 'lower_edge', 'upper_edge'))
    result['residual'] = result['direct'] - result['transformed']
    return result
