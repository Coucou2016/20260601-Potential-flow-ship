import numpy as np
import pytest
from planing_seakeeping.kernels.linear_2p5d.boundary_reconstruction import reconstruct_linear


def test_affine_complex_data_and_disconnected_traces():
    lengths=np.array([.2,.3,.4,.2,.3,.4])
    s=np.cumsum(lengths)-lengths/2
    values=(2+3j)*s+np.r_[np.ones(3)*20,np.ones(3)*-40]
    offsets=lengths[:,None]*np.array([-.4,0,.4])
    result=reconstruct_linear(lengths,values,offsets,breaks=(3,))
    np.testing.assert_allclose(result,values[:,None]+(2+3j)*offsets,atol=1e-12)


def test_invalid_trace_breaks_and_nonfinite_data():
    with pytest.raises(ValueError,match='two samples'):
        reconstruct_linear(np.ones(4),np.ones(4),np.zeros((4,2)),breaks=(1,))
    with pytest.raises(ValueError,match='Finite'):
        reconstruct_linear(np.ones(4),np.array([1,2,np.nan,4]),np.zeros((4,2)))


def test_sampled_integration_does_not_call_analytic_reference(monkeypatch):
    from scripts import audit_static_mixed_fields
    from scripts.harmonic_boundary_rhs import integrated_known_term
    from planing_seakeeping.kernels.linear_2p5d.formulation import build_control_surface_geometry
    source=build_control_surface_geometry(1.3,24)
    values=np.ones(24)
    def forbidden(*args):
        raise AssertionError('Analytic reference queried')
    monkeypatch.setattr(audit_static_mixed_fields,'harmonic',forbidden)
    actual=integrated_known_term(source,source,'not_available',kind='control_potential',
                                 self_boundary=True,sample_values=values)
    # A constant over the semicircle integrates to pi/2, less the pi jump.
    np.testing.assert_allclose(actual,-np.pi/2,atol=1e-11)
