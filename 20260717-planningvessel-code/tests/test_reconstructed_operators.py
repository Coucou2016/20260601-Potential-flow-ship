import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.reconstructed_operators import derivative_matrix,reconstructed_log_operators
from planing_seakeeping.kernels.linear_2p5d.formulation import build_control_surface_geometry,build_waterline_clipped_free_surface_geometry
from scripts.harmonic_boundary_rhs import integrated_known_term


def test_derivative_matrix_affine_complex_and_trace_isolation():
    length=np.array([.2,.3,.4,.2,.3,.4])
    s=np.cumsum(length)-length/2
    d=derivative_matrix(length,(3,))
    values=(2+3j)*s+np.r_[np.full(3,10.),np.full(3,-20.)]
    np.testing.assert_allclose(d@values,2+3j,atol=1e-12)
    np.testing.assert_array_equal(d[:3,3:],0.)
    np.testing.assert_array_equal(d[3:,:3],0.)


@pytest.mark.parametrize('kind',['free_potential','control_potential'])
def test_matrix_matches_sample_only_direct_integral(kind):
    source=(build_control_surface_geometry(1.3,24) if kind=='control_potential'
            else build_waterline_clipped_free_surface_geometry(-1.3,1.3,.2,24))
    values=np.sin(np.arange(24)*.3)+1j*np.cos(np.arange(24)*.2)
    p,a=reconstructed_log_operators(source,source,geometry_kind='circular' if kind=='control_potential' else 'straight',
        breaks=() if kind=='control_potential' else (12,),same_boundary=True,order=64)
    direct=integrated_known_term(source,source,'unavailable',kind=kind,self_boundary=True,order=64,sample_values=values)
    np.testing.assert_allclose(a@values,direct,atol=1e-10,rtol=1e-10)
    assert np.isfinite(p).all()


def test_disconnected_trace_requires_break():
    free=build_waterline_clipped_free_surface_geometry(-1.3,1.3,.2,24)
    with pytest.raises(ValueError,match='explicit break'):
        reconstructed_log_operators(free,free,geometry_kind='straight',same_boundary=True)


def test_body_flux_matrix_preserves_trace_orientation():
    from planing_seakeeping.kernels.linear_2p5d.formulation import InnerDomainPanelGeometry
    y=np.linspace(1,-1,25)
    z=.3*(1-np.abs(y))
    nodes=np.column_stack((y,z))
    delta=np.diff(nodes,axis=0)
    length=np.linalg.norm(delta,axis=1)
    normal=np.column_stack((-delta[:,1],delta[:,0]))/length[:,None]
    mid=(nodes[:-1]+nodes[1:])/2
    body=InnerDomainPanelGeometry(mid_y_m=mid[:,0],mid_z_down_m=mid[:,1],normal_y=normal[:,0],
        normal_z=normal[:,1],length_m=length,node_y_m=y,node_z_down_m=z)
    values=np.arange(24)*(.1+.2j)
    p,_=reconstructed_log_operators(body,body,geometry_kind='straight',breaks=(12,),same_boundary=True,order=64)
    direct=integrated_known_term(body,body,'unavailable',kind='body_flux',self_boundary=True,order=64,sample_values=values)
    np.testing.assert_allclose(p@values,direct,atol=1e-10,rtol=1e-10)


def test_mirrored_arc_against_explicit_reflected_point_quadrature():
    from numpy.polynomial.legendre import leggauss
    from planing_seakeeping.kernels.linear_2p5d.boundary_reconstruction import reconstruct_linear
    source=build_control_surface_geometry(1.3,24)
    field=build_control_surface_geometry(.7,12)
    values=np.sin(np.arange(24)*.3)+1j*np.cos(np.arange(24)*.2)
    p,a=reconstructed_log_operators(field,source,geometry_kind='circular',mirrored_source=True,order=64)
    xi,w=leggauss(64)
    offset=source.length_m[:,None]*xi/2
    theta=np.arctan2(source.mid_z_down_m,source.mid_y_m)[:,None]+offset/1.3
    # Explicit reflected source coordinates AND normals, independent of field reflection.
    ny,nz=np.cos(theta),-np.sin(theta)
    dy=field.mid_y_m[:,None,None]-1.3*ny
    dz=field.mid_z_down_m[:,None,None]-1.3*nz
    r2=dy*dy+dz*dz
    trace=reconstruct_linear(source.length_m,values,offset)
    weighted=trace*source.length_m[:,None]*w/2
    expected_p=np.sum(.5*np.log(r2)*weighted,axis=(1,2))
    expected_a=np.sum(-(dy*ny+dz*nz)/r2*weighted,axis=(1,2))
    np.testing.assert_allclose(p@values,expected_p,atol=1e-11,rtol=1e-11)
    np.testing.assert_allclose(a@values,expected_a,atol=1e-11,rtol=1e-11)
    with pytest.raises(ValueError,match='not a self'):
        reconstructed_log_operators(source,source,geometry_kind='circular',mirrored_source=True,same_boundary=True)
