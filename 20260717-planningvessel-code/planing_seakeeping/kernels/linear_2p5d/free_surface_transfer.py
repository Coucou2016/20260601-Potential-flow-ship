"""Explicitly classified two-sided free-surface remap for experimental marching."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class FreeSurfaceTransfer:
    values: np.ndarray
    edge_extrapolated: np.ndarray
    newly_exposed: np.ndarray
    exposed_source: str | None


def limited_linear_exposure(source_y, target_y, fields, previous_half_beam, *, maximum_spacing_ratio):
    """Explicit unvalidated smooth-trace continuation, never an automatic fallback.

    Return new-region values only; NaNs elsewhere prevent accidental use as a
    complete state. Reject a release wider than the caller's frozen spacing limit.
    """
    x,y,v=np.asarray(source_y,float),np.asarray(target_y,float),np.asarray(fields,complex)
    if (x.ndim!=1 or y.ndim!=1 or v.ndim!=2 or v.shape[0]!=len(x)
            or any(not np.isfinite(a).all() for a in (x,y,v))
            or np.any(np.diff(x)<=0) or np.any(np.diff(y)<=0)
            or not np.isfinite([previous_half_beam,maximum_spacing_ratio]).all()
            or previous_half_beam<0 or maximum_spacing_ratio<=0):
        raise ValueError('Finite ordered traces and explicit positive continuation limit required')
    result=np.full((len(y),v.shape[1]),np.nan+1j*np.nan)
    maximum=0.
    for sign in (-1,1):
        selected=(sign*y>0)&(abs(y)<previous_half_beam)
        if not selected.any():
            continue
        candidates=np.flatnonzero(sign*x>0)
        if len(candidates)<2:
            raise ValueError('Two source points required on each exposed side')
        ordered=candidates[np.argsort(abs(x[candidates]))]
        a,b=ordered[:2]
        spacing=abs(x[b]-x[a])
        ratio=float(max(abs(y[selected]-x[a]))/spacing)
        if ratio>maximum_spacing_ratio:
            raise ValueError('New exposure exceeds frozen continuation distance; refine or supply a physical model')
        maximum=max(maximum,ratio)
        result[selected]=v[a]+(y[selected]-x[a])[:,None]*(v[b]-v[a])/(x[b]-x[a])
    return result,maximum


def transfer_fields(source_y, target_y, fields, *, previous_half_beam, control_radius,
                    exposed_values=None, exposed_source=None):
    """Linear remap on each side, never across the hull gap or silently into old solid.

    Old-free-surface edge bands outside midpoint coverage use labelled linear
    extrapolation. Points inside the previous hull require caller-supplied
    state and provenance; this function does not invent a contact-line model.
    """
    x, y, v = np.asarray(source_y,float), np.asarray(target_y,float), np.asarray(fields,complex)
    if (x.ndim!=1 or y.ndim!=1 or len(x)<4 or len(y)<1 or v.ndim!=2 or v.shape[0]!=len(x)
            or not v.shape[1] or not np.isfinite([previous_half_beam,control_radius]).all()
            or not 0<=previous_half_beam<control_radius
            or any(not np.isfinite(a).all() for a in (x,y,v))
            or np.any(np.diff(x)<=0) or np.any(np.diff(y)<=0)
            or np.any(abs(x)<=previous_half_beam) or np.any(abs(x)>=control_radius)
            or np.any(y==0) or np.any(abs(y)>=control_radius)):
        raise ValueError('Finite ordered two-sided free-surface grids inside explicit boundaries required')
    exposed=abs(y)<previous_half_beam
    if exposed.any():
        if exposed_values is None or not isinstance(exposed_source,str) or not exposed_source.strip():
            raise ValueError('Newly exposed free surface requires explicit state and provenance')
        fill=np.asarray(exposed_values,complex)
        if fill.shape!=(len(y),v.shape[1]) or not np.isfinite(fill[exposed]).all():
            raise ValueError('Finite matching state for all newly exposed points required')
    elif exposed_values is not None or exposed_source is not None:
        raise ValueError('Exposed-state data supplied when no new free surface exists')
    result=np.empty((len(y),v.shape[1]),complex)
    edge=np.zeros(len(y),bool)
    for sign in (-1,1):
        sx=x*sign>0
        selected=(y*sign>0)&~exposed
        if np.count_nonzero(sx)<2:
            raise ValueError('At least two source points on each side required')
        xx,vv=x[sx],v[sx]
        yy=y[selected]
        for j in range(v.shape[1]):
            result[selected,j]=np.interp(yy,xx,vv[:,j].real)+1j*np.interp(yy,xx,vv[:,j].imag)
        for mask,anchor,neighbor in ((selected&(y<xx[0]),0,1),(selected&(y>xx[-1]),-1,-2)):
            edge|=mask
            slope=(vv[neighbor]-vv[anchor])/(xx[neighbor]-xx[anchor])
            result[mask]=vv[anchor]+(y[mask]-xx[anchor])[:,None]*slope
    if exposed.any():
        result[exposed]=fill[exposed]
    return FreeSurfaceTransfer(result,edge,exposed,exposed_source)


def exposure_linear_bounded_edge_transfer(source_y,target_y,fields,*,previous_half_beam,
                                         control_radius,maximum_spacing_ratio):
    """Experimental smooth new-region continuation, NOT physical contact data.

    Only new exposure receives linear extrapolation; old-free edges retain the
    convex nearest rule. Unlike bounded_trace_transfer, this is not nonamplifying.
    """
    result=bounded_trace_transfer(source_y,target_y,fields,
        previous_half_beam=previous_half_beam,control_radius=control_radius,
        maximum_spacing_ratio=maximum_spacing_ratio)
    if result.newly_exposed.any():
        fill,_=limited_linear_exposure(source_y,target_y,fields,previous_half_beam,
            maximum_spacing_ratio=maximum_spacing_ratio)
        result.values[result.newly_exposed]=fill[result.newly_exposed]
    return FreeSurfaceTransfer(result.values,result.edge_extrapolated,result.newly_exposed,
        'linear_exposure_bounded_edges_unvalidated' if result.newly_exposed.any() else None)


def bounded_trace_transfer(source_y,target_y,fields,*,previous_half_beam,control_radius,
                           maximum_spacing_ratio):
    """Experimental convex remap, NOT a physical contact-line initialization.

    Interpolate supported points, hold nearest same-side values outside support.
    Retain the original explicit exposure-distance limit and classification.
    This avoids negative interpolation weights but loses affine exactness at edges.
    """
    x,y,v=np.asarray(source_y,float),np.asarray(target_y,float),np.asarray(fields,complex)
    if not np.isfinite(maximum_spacing_ratio) or maximum_spacing_ratio<=0:
        raise ValueError('Explicit positive continuation limit required')
    kwargs={}
    if np.any(abs(y)<previous_half_beam):
        fill,_=limited_linear_exposure(x,y,v,previous_half_beam,
                                      maximum_spacing_ratio=maximum_spacing_ratio)
        kwargs=dict(exposed_values=fill,exposed_source='bounded_nearest_unvalidated')
    checked=transfer_fields(x,y,v,previous_half_beam=previous_half_beam,
                           control_radius=control_radius,**kwargs)
    values=checked.values.copy()
    for sign in (-1,1):
        source=sign*x>0
        target=sign*y>0
        for j in range(v.shape[1]):
            values[target,j]=(np.interp(y[target],x[source],v[source,j].real)
                              +1j*np.interp(y[target],x[source],v[source,j].imag))
    return FreeSurfaceTransfer(values,checked.edge_extrapolated,checked.newly_exposed,
                               checked.exposed_source)
