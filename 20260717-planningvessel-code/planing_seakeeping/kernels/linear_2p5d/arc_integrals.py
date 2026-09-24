"""Diagnostic Gauss integration for origin-centered circular source panels."""
import numpy as np
from numpy.polynomial.legendre import leggauss


def circular_arc_integrals(field,source,*,order=32,same_boundary=False,diagonal_sign=-1.):
    if type(order) is not int or order<8:
        raise ValueError('Arc quadrature order must be an integer >= 8')
    if not np.isfinite(diagonal_sign):
        raise ValueError('Finite diagonal sign required')
    y,z=np.asarray(source.mid_y_m),np.asarray(source.mid_z_down_m)
    radius=np.hypot(y,z)
    length=np.asarray(source.length_m)
    if (not np.isfinite(radius).all() or np.any(radius<=0) or not np.allclose(radius,radius[0],rtol=1e-12)
            or not np.isfinite(length).all() or np.any(length<=0)
            or np.any(length>2*np.pi*radius)
            or not np.allclose(source.normal_y,y/radius) or not np.allclose(source.normal_z,z/radius)):
        raise ValueError('Circular source with outward radial normals required')
    fy,fz=np.asarray(field.mid_y_m),np.asarray(field.mid_z_down_m)
    if not np.isfinite(fy).all() or not np.isfinite(fz).all():
        raise ValueError('Finite field points required')
    if same_boundary and not (np.array_equal(fy,y) and np.array_equal(fz,z)):
        raise ValueError('Self integration requires matching points')
    nodes,weights=leggauss(order)
    half=length/(2*radius)
    theta=np.arctan2(z,y)[:,None]+half[:,None]*nodes
    cosine,sine=np.cos(theta),np.sin(theta)
    dy=fy[:,None,None]-radius[None,:,None]*cosine[None,:,:]
    dz=fz[:,None,None]-radius[None,:,None]*sine[None,:,:]
    r2=dy*dy+dz*dz
    if same_boundary:
        # Singular self potential is replaced below, before it is used.
        r2[np.arange(len(y)),np.arange(len(y)),:]=1.
    if np.any(r2<=0):
        raise ValueError('Coincident quadrature and field points')
    weighted=length[:,None]*weights[None,:]/2
    potential=np.sum(.5*np.log(r2)*weighted[None,:,:],axis=2)
    normal=np.sum(-(dy*cosine[None,:,:]+dz*sine[None,:,:])/r2*weighted[None,:,:],axis=2)
    if same_boundary:
        t=half[:,None]*(nodes[None,:]+1)/2
        regular=np.sum(np.log(np.sinc(t/(2*np.pi)))*weights[None,:],axis=1)*half/2
        diagonal=2*radius*(half*(np.log(radius*half)-1)+regular)
        np.fill_diagonal(potential,diagonal)
        np.fill_diagonal(normal,float(diagonal_sign)*np.pi+half)
    return potential,normal
