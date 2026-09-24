"""Sample-only linear panel reconstruction, with explicit trace breaks."""
import numpy as np


def reconstruct_linear(length,values,offsets,*,breaks=()):
    length=np.asarray(length,float)
    values=np.asarray(values)
    offsets=np.asarray(offsets,float)
    n=len(length)
    if (length.ndim!=1 or values.shape!=(n,) or offsets.ndim!=2 or offsets.shape[0]!=n
            or not all(np.isfinite(v).all() for v in (length,values,offsets)) or np.any(length<=0)):
        raise ValueError('Finite matching panel lengths, samples and offsets required')
    cuts=tuple(breaks)
    if any(type(i) is not int or not 0<i<n for i in cuts) or list(cuts)!=sorted(set(cuts)):
        raise ValueError('Breaks must be sorted unique interior indices')
    s=np.cumsum(length)-length/2
    slopes=np.empty(n,dtype=np.result_type(values,float))
    bounds=(0,*cuts,n)
    for start,end in zip(bounds[:-1],bounds[1:]):
        if end-start<2:
            raise ValueError('Each trace needs two samples')
        slopes[start:end]=np.gradient(values[start:end],s[start:end],edge_order=2 if end-start>=3 else 1)
    return values[:,None]+slopes[:,None]*offsets
