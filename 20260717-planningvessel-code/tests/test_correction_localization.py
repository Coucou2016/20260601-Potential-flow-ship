import numpy as np
from scripts.localize_eulerian_correction import fraction_weights


def test_fractional_regions_partition_unequal_panels():
    lengths=np.array([[.1,.2,.3,.4],[.4,.3,.2,.1]])
    water=fraction_weights(lengths,[(0,.1),(.9,1)])
    keel=fraction_weights(lengths,[(.45,.55)])
    interior=1-water-keel
    assert np.all(interior >= -1e-14)
    np.testing.assert_allclose((water*lengths).sum(axis=1),.2)
    np.testing.assert_allclose((keel*lengths).sum(axis=1),.1)
    np.testing.assert_allclose(water+keel+interior,1)


def test_constant_density_region_integral_is_mesh_independent():
    for n in (12,36,60,72):
        lengths=np.full((2,n),1/n)
        weights=fraction_weights(lengths,[(0,.1),(.9,1)])
        np.testing.assert_allclose((weights*lengths).sum(axis=1),.2,atol=1e-14)
