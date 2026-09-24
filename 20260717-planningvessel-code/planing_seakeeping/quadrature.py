"""Load integration on fixed physical support boundaries."""
import numpy as np


def clipped_piecewise_linear_integral(x, values, cutoff):
    """Integrate the station interpolant above cutoff without smearing its jump."""
    x, values = np.asarray(x, dtype=float), np.asarray(values)
    if x.ndim != 1 or len(x) < 2 or values.ndim < 1 or values.shape[0] != len(x):
        raise ValueError("Expected stations and matching leading value axis")
    if not np.isfinite(x).all() or not np.isfinite(values).all() or np.any(np.diff(x) <= 0):
        raise ValueError("Stations must increase and all values must be finite")
    if not np.isfinite(cutoff):
        raise ValueError("Cutoff must be finite")
    if cutoff >= x[-1]:
        return np.zeros(values.shape[1:], dtype=values.dtype)
    if cutoff <= x[0]:
        return np.trapezoid(values, x, axis=0)
    right = int(np.searchsorted(x, cutoff, side="right"))
    fraction = (cutoff-x[right-1])/(x[right]-x[right-1])
    edge = values[right-1] + fraction*(values[right]-values[right-1])
    return np.trapezoid(np.concatenate((edge[None], values[right:]), axis=0),
                        np.concatenate(([cutoff], x[right:])), axis=0)
