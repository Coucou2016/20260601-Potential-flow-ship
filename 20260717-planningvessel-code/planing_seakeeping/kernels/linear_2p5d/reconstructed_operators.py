"""Diagnostic log-kernel matrices for sample-only linear panel traces."""
import numpy as np
from dataclasses import replace
from numpy.polynomial.legendre import leggauss
from .panel_integrals import straight_log_integrals
from .arc_integrals import circular_arc_integrals


def derivative_matrix(length,breaks=()):
    length=np.asarray(length,float)
    if length.ndim!=1 or not np.isfinite(length).all() or np.any(length<=0):
        raise ValueError('Positive finite panel lengths required')
    n=len(length)
    if any(type(i) is not int or not 0<i<n for i in breaks) or list(breaks)!=sorted(set(breaks)):
        raise ValueError('Sorted unique interior breaks required')
    s=np.cumsum(length)-length/2
    result=np.zeros((n,n))
    identity=np.eye(n)
    bounds=(0,*breaks,n)
    for start,end in zip(bounds[:-1],bounds[1:]):
        if end-start<2:
            raise ValueError('Each trace requires at least two panels')
        result[start:end]=np.gradient(identity[start:end],s[start:end],axis=0,edge_order=2 if end-start>=3 else 1)
    return result


def reconstructed_log_operators(field,source,*,geometry_kind,breaks=(),same_boundary=False,order=32,diagonal_sign=-1.,mirrored_source=False):
    """Return (potential, source-normal) matrices including first moments.

    These are spatial operators only. No external history kernel is altered.
    """
    if type(order) is not int or order<8:
        raise ValueError('Quadrature order must be an integer >= 8')
    if mirrored_source:
        if same_boundary:
            raise ValueError('Mirrored source is not a self boundary')
        # Reflection preserves distance and the source-normal dot product.
        # Reflect the field instead so source arc ordering and slopes stay intact.
        field=replace(field,mid_z_down_m=-np.asarray(field.mid_z_down_m))
    length=np.asarray(source.length_m)
    d=derivative_matrix(length,breaks)
    xi,w=leggauss(order)
    offset=length[:,None]*xi/2
    weight=length[:,None]*w/2
    if geometry_kind=='circular':
        p0,a0=circular_arc_integrals(field,source,order=order,same_boundary=same_boundary,diagonal_sign=diagonal_sign)
        radius=np.hypot(source.mid_y_m,source.mid_z_down_m)
        theta=np.arctan2(source.mid_z_down_m,source.mid_y_m)[:,None]+offset/radius[:,None]
        ny,nz=np.cos(theta),np.sin(theta)
        y,z=radius[:,None]*ny,radius[:,None]*nz
    elif geometry_kind=='straight':
        nodes=np.column_stack((source.node_y_m,source.node_z_down_m))
        starts,ends=nodes[:-1],nodes[1:]
        if len(nodes)==len(length)+2:
            starts=np.delete(starts,len(length)//2,axis=0)
            ends=np.delete(ends,len(length)//2,axis=0)
            if len(length)//2 not in breaks:
                raise ValueError('Disconnected free-surface traces need an explicit break')
        delta=ends-starts
        centers=np.column_stack((source.mid_y_m,source.mid_z_down_m))
        if (delta.shape!=centers.shape or not np.allclose(np.linalg.norm(delta,axis=1),length,rtol=1e-10,atol=1e-12)
                or not np.allclose((starts+ends)/2,centers,rtol=1e-10,atol=1e-12)):
            raise ValueError('Straight geometry required')
        p0,a0=straight_log_integrals(field,source,same_boundary=same_boundary,diagonal_sign=diagonal_sign)
        tangent=delta/length[:,None]
        y=source.mid_y_m[:,None]+tangent[:,0,None]*offset
        z=source.mid_z_down_m[:,None]+tangent[:,1,None]*offset
        ny,nz=source.normal_y[:,None],source.normal_z[:,None]
    else:
        raise ValueError('Unknown geometry kind')
    dy=np.asarray(field.mid_y_m)[:,None,None]-y[None,:,:]
    dz=np.asarray(field.mid_z_down_m)[:,None,None]-z[None,:,:]
    r2=dy*dy+dz*dz
    if same_boundary:
        r2[np.arange(len(length)),np.arange(len(length)),:]=1.
    if np.any(r2<=0):
        raise ValueError('Coincident quadrature points')
    p1=np.sum(.5*np.log(r2)*(weight*offset)[None,:,:],axis=2)
    a1=np.sum(-(dy*ny[None,:,:]+dz*nz[None,:,:])/r2*(weight*offset)[None,:,:],axis=2)
    if same_boundary:
        # Odd first moments vanish on centered straight or circular self panels.
        np.fill_diagonal(p1,0.)
        np.fill_diagonal(a1,0.)
    return p0+p1@d,a0+a1@d
