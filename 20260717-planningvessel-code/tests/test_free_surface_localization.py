import numpy as np
import pytest
from scripts.localize_free_surface_error import region_weights


def test_nonuniform_partition_preserves_every_panel():
    nodes=np.array([.2,.25,.5,1.,2.,3.])
    y=(nodes[:-1]+nodes[1:])/2
    lengths=np.diff(nodes)
    weights=region_weights(np.r_[-y[::-1],y],np.r_[lengths[::-1],lengths])
    np.testing.assert_allclose(sum(weights.values()),np.r_[lengths[::-1],lengths])
    np.testing.assert_allclose([w.sum() for w in weights.values()],2*2.8*np.array([.1,.8,.1]))


def test_bad_lengths_rejected():
    with pytest.raises(ValueError,match='positive'):
        region_weights(np.array([-1.,1.]),np.array([1.,0.]))
