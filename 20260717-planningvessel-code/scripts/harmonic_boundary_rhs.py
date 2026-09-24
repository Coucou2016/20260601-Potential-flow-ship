"""Independent continuous known-data integration for harmonic audit only."""
from types import SimpleNamespace
import numpy as np
from numpy.polynomial.legendre import leggauss


def integrated_known_term(field,source,name,*,kind,self_boundary=False,order=64,sample_values=None):
    from scripts.audit_static_mixed_fields import harmonic
    if kind not in ('body_flux','free_potential','control_potential'):
        raise ValueError('Unknown known-boundary term')
    if type(order) is not int or order<8:
        raise ValueError('Quadrature order must be an integer >= 8')
    xi,w=leggauss(order)
    length=np.asarray(source.length_m)
    weights=length[:,None]*w[None,:]/2
    if kind=='control_potential':
        radius=np.hypot(source.mid_y_m,source.mid_z_down_m)
        theta=np.arctan2(source.mid_z_down_m,source.mid_y_m)[:,None]+length[:,None]/(2*radius[:,None])*xi
        ny,nz=np.cos(theta),np.sin(theta)
        y,z=radius[:,None]*ny,radius[:,None]*nz
    else:
        ny=np.broadcast_to(source.normal_y[:,None],weights.shape)
        nz=np.broadcast_to(source.normal_z[:,None],weights.shape)
        y=source.mid_y_m[:,None]-nz*length[:,None]*xi/2
        z=source.mid_z_down_m[:,None]+ny*length[:,None]*xi/2
    if sample_values is None:
        phi,q=harmonic(SimpleNamespace(mid_y_m=y,mid_z_down_m=z,normal_y=ny,normal_z=nz),name)
        center_phi,center_q=harmonic(source,name)
    else:
        from planing_seakeeping.kernels.linear_2p5d.boundary_reconstruction import reconstruct_linear
        offsets=length[:,None]*xi/2
        if kind=='body_flux':
            # Quadrature tangent derives from normals; offsets must follow
            # the original trace-node order used by the sampled derivative.
            delta=np.column_stack((np.diff(source.node_y_m),np.diff(source.node_z_down_m)))
            direction=delta/length[:,None]
            offsets=(y-source.mid_y_m[:,None])*direction[:,0,None]+(z-source.mid_z_down_m[:,None])*direction[:,1,None]
        values=reconstruct_linear(length,sample_values,offsets,
            breaks=() if kind=='control_potential' else (len(length)//2,))
        phi=q=values
        center_phi=center_q=np.asarray(sample_values)
    dy=np.asarray(field.mid_y_m)[:,None,None]-y[None,:,:]
    dz=np.asarray(field.mid_z_down_m)[:,None,None]-z[None,:,:]
    r2=dy*dy+dz*dz
    if np.any(r2<=0):
        raise ValueError('Coincident integration points')
    if kind=='body_flux':
        terms=np.sum(.5*np.log(r2)*q[None,:,:]*weights[None,:,:],axis=2)
        if self_boundary:
            # The flux of these degree <=2 harmonic fields is affine on a line;
            # its odd part integrates to zero against the centered self log.
            np.fill_diagonal(terms,length*(np.log(length/2)-1)*center_q)
    else:
        kernel=-(dy*ny[None,:,:]+dz*nz[None,:,:])/r2
        if self_boundary:
            idx=np.arange(len(length))
            kernel[idx,idx,:]=0. if kind=='free_potential' else 1/(2*radius[:,None])
        terms=np.sum(kernel*phi[None,:,:]*weights[None,:,:],axis=2)
        if self_boundary:
            terms[np.arange(len(length)),np.arange(len(length))]-=np.pi*center_phi
    return terms.sum(axis=1)
