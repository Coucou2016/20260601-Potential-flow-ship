"""Open-contour transport identity for integrated fixed-space pressure gradients."""
import numpy as np


def integrated_fixed_space_derivative(x,section_potential,waterline_flux,shape_flux,lcg):
    """Integrate phi_x dy without differencing phi in x.

    For a right-to-left body contour, I=integral(phi dy), E=[phi*y_x]_ends,
    H=integral(phi_z*(z_x*dy-y_x*dz)). Then integral(phi_x dy)=I_x-E-H.
    Caller is responsible for compatible orientation and contact trace accuracy.
    Returns whole-hull heave and (lcg-x)-weighted pitch integrals.
    """
    x=np.asarray(x,float)
    values=[np.asarray(a,complex) for a in (section_potential,waterline_flux,shape_flux)]
    if (x.ndim!=1 or len(x)<3 or not np.isfinite(x).all() or np.any(np.diff(x)<=0)
            or not np.isfinite(lcg) or any(a.shape!=x.shape or not np.isfinite(a).all() for a in values)):
        raise ValueError('Finite compatible section traces and ordered stations required')
    potential,edge,shape=values
    lever=lcg-x
    heave=potential[-1]-potential[0]-np.trapezoid(edge+shape,x)
    pitch=(lever[-1]*potential[-1]-lever[0]*potential[0]
           +np.trapezoid(potential,x)-np.trapezoid(lever*(edge+shape),x))
    return np.array([heave,pitch])
