import numpy as np
from scipy.integrate import quad
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    InnerDomainPanelGeometry, _inner_a_matrix)
from scripts.audit_static_mixed_fields import harmonic
from scripts.audit_static_mixed_fields import subdivide_body
import pytest


def test_circular_self_regular_part_and_constant_identity():
    radius,count=1.3,64
    edges=np.linspace(0,2*np.pi,count+1)
    t=(edges[:-1]+edges[1:])/2
    g=InnerDomainPanelGeometry(mid_y_m=radius*np.cos(t),mid_z_down_m=radius*np.sin(t),
        normal_y=np.cos(t),normal_z=np.sin(t),length_m=np.full(count,2*np.pi*radius/count),
        node_y_m=radius*np.cos(edges),node_z_down_m=radius*np.sin(edges))
    a=_inner_a_matrix(g,g,same_boundary=True)
    correction=g.length_m/(2*radius)
    np.testing.assert_allclose(a@np.ones(count),-correction,atol=1e-13)
    np.testing.assert_allclose((a+np.diag(correction))@np.ones(count),0,atol=1e-13)
    # On a circle the regular source-normal derivative is exactly 1/(2R).
    integral=quad(lambda s:1/(2*radius),-g.length_m[0]/2,g.length_m[0]/2)[0]
    np.testing.assert_allclose(integral,correction[0],atol=1e-15)
    phi,q=harmonic(g,'linear_z')
    np.testing.assert_allclose(phi,g.mid_z_down_m)
    np.testing.assert_allclose(q,g.normal_z)


def test_subdivision_preserves_corner_geometry():
    nodes=np.array([[1.,0.],[0.,.4],[-1.,0.]])
    delta=np.diff(nodes,axis=0)
    lengths=np.linalg.norm(delta,axis=1)
    normals=np.column_stack((-delta[:,1],delta[:,0]))/lengths[:,None]
    mids=(nodes[:-1]+nodes[1:])/2
    body=InnerDomainPanelGeometry(mid_y_m=mids[:,0],mid_z_down_m=mids[:,1],
        normal_y=normals[:,0],normal_z=normals[:,1],length_m=lengths,
        node_y_m=nodes[:,0],node_z_down_m=nodes[:,1])
    refined=subdivide_body(body,4)
    np.testing.assert_allclose(refined.node_y_m[::4],nodes[:,0])
    np.testing.assert_allclose(refined.node_z_down_m[::4],nodes[:,1])
    np.testing.assert_allclose(refined.length_m.sum(),body.length_m.sum())
    assert refined.panel_count==8
    with pytest.raises(ValueError,match='positive integer'):
        subdivide_body(body,True)
