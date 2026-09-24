import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.formulation import build_inner_domain_panel_geometry
from planing_seakeeping.section_bem import SectionOffsets
from planing_seakeeping.kernels.linear_2p5d.pressure_gradient import transverse_velocity, remove_geometry_chain_term
from scripts.probe_eulerian_diffraction import hull_outward_diffraction_derivative


def wedge(x=0):
    eta = np.linspace(-1,1,25)
    return build_inner_domain_panel_geometry(SectionOffsets((1+.2*x)*eta, (.3+.1*x)*abs(eta)))


@pytest.mark.parametrize("quadratic", [False, True])
def test_velocity_recovery_complex_harmonic_field_with_keel_corner(quadratic):
    b = wedge()
    y,z = b.mid_y_m,b.mid_z_down_m
    a,c = 1+.4j,-.3+.7j
    phi = a*y+c*z
    vy,vz = np.full(y.shape,a), np.full(y.shape,c)
    if quadratic:
        phi = phi + (y*y-z*z)*(1-.2j)
        vy += 2*y*(1-.2j)
        vz -= 2*z*(1-.2j)
    qn = vy*b.normal_y+vz*b.normal_z
    recovered = transverse_velocity(b,phi,qn,corner_nodes=(12,))
    np.testing.assert_allclose(recovered,[vy,vz],atol=2e-13)


def test_moving_geometry_term_is_removed_without_analytic_transverse_velocity():
    x = np.linspace(0,2,33)
    bodies = tuple(wedge(v) for v in x)
    a,c = 1+.4j,-.3+.7j
    phi=np.asarray([a*b.mid_y_m+c*b.mid_z_down_m for b in bodies])
    qn=np.asarray([a*b.normal_y+c*b.normal_z for b in bodies])
    material=np.gradient(phi,x,axis=0,edge_order=2)
    corrected,chain=remove_geometry_chain_term(x,bodies,material,phi,qn,corner_nodes=(12,))
    assert abs(chain).max() > .1
    np.testing.assert_allclose(corrected,0,atol=2e-13)


def test_insufficient_corner_trace_rejected():
    b=wedge()
    with pytest.raises(ValueError,match="at least two"):
        transverse_velocity(b,np.zeros(24),np.zeros(24),corner_nodes=(1,))


def test_fluid_boundary_derivative_converted_before_velocity_recovery():
    b = wedge()
    a, c = 1+.4j, -.3+.7j
    phi = a*b.mid_y_m+c*b.mid_z_down_m
    fluid_q = -(a*b.normal_y+c*b.normal_z)
    saved = fluid_q.copy()
    hull_q = hull_outward_diffraction_derivative(fluid_q)
    vy, vz = transverse_velocity(b, phi, hull_q, corner_nodes=(12,))
    np.testing.assert_allclose(vy, a, atol=2e-13)
    np.testing.assert_allclose(vz, c, atol=2e-13)
    wrong = transverse_velocity(b, phi, fluid_q, corner_nodes=(12,))
    assert np.linalg.norm(np.asarray(wrong)-np.asarray([vy,vz])) > 1
    np.testing.assert_array_equal(fluid_q, saved)


def test_nonfinite_fluid_derivative_rejected():
    with pytest.raises(ValueError, match='finite'):
        hull_outward_diffraction_derivative([complex(float('nan'), 0)])
