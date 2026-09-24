"""Experimental fixed lateral grid with waterline clipping (A1 section 3.3)."""
import numpy as np
from .formulation import InnerDomainPanelGeometry


def build_anchored_free_surface(radius, maximum_half_beam, half_beam, inner_count, outer_count):
    """Keep global lateral nodes fixed; only replace the cut-cell waterline endpoint.

    The number of panels changes with waterline position. No silent uniform-grid
    fallback is used. This geometry alone does not initialize newly exposed water.
    """
    if (not np.isfinite([radius,maximum_half_beam,half_beam]).all()
            or not 0<maximum_half_beam<radius or not 0<=half_beam<=maximum_half_beam
            or any(not isinstance(n,int) or n<2 for n in (inner_count,outer_count))):
        raise ValueError('Ordered finite geometry bounds and at least two panels per zone required')
    fixed=np.r_[np.linspace(0.,maximum_half_beam,inner_count+1),
        np.linspace(maximum_half_beam,radius,outer_count+1)[1:]]
    nodes=np.r_[half_beam,fixed[fixed>half_beam]]
    left=-nodes[::-1]
    lengths=np.r_[np.diff(left),np.diff(nodes)]
    if np.any(lengths<=64*np.finfo(float).eps*radius):
        raise ValueError('Clipped panel is nonpositive or below floating-point resolution; no silent snapping')
    y=np.r_[(left[1:]+left[:-1])/2,(nodes[1:]+nodes[:-1])/2]
    return InnerDomainPanelGeometry(mid_y_m=y,mid_z_down_m=np.zeros_like(y),
        normal_y=np.zeros_like(y),normal_z=-np.ones_like(y),length_m=lengths,
        node_y_m=np.r_[left,nodes],node_z_down_m=np.zeros(len(left)+len(nodes)))
