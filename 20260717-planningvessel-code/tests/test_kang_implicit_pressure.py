import json
import numpy as np
import pytest
from scripts.audit_kang_implicit_pressure import run


def test_wrong_candidate_rejected_before_output(tmp_path):
    source=tmp_path/'source'; source.mkdir()
    (source/'contract.json').write_text(json.dumps(dict(exposure_policy='other')))
    out=tmp_path/'audit'
    with pytest.raises(ValueError,match='candidate'):
        run(source,out)
    assert not out.exists()


def test_legacy_normal_convention_rejected_before_output(tmp_path):
    source=tmp_path/'source'; source.mkdir()
    (source/'contract.json').write_text(json.dumps(dict(
        exposure_policy='bounded_nearest_unvalidated',history_policy='full',
        panel_integration='analytic_straight_midpoint_curved')))
    out=tmp_path/'audit'
    with pytest.raises(ValueError,match='Neumann convention'):
        run(source,out)
    assert not out.exists()


@pytest.mark.parametrize('corrupt',['pressure','phase','force'])
def test_corrupt_saved_fields_cannot_pass_replay(tmp_path,corrupt):
    source=tmp_path/'source'; source.mkdir()
    (source/'contract.json').write_text(json.dumps(dict(
        exposure_policy='bounded_nearest_unvalidated',history_policy='full',
        panel_integration='analytic_straight_midpoint_curved',
        body_neumann_convention='fluid_domain_outward_diffraction_minus_incident',
        speed_m_s=1.,omega_e_sqrt_L_g=3.)))
    zero=np.zeros((3,6),complex)
    fields=dict(x_m=np.linspace(0,3,3),phi=zero.copy(),psi=zero.copy(),
        pressure_gradient=zero.copy(),pressure=zero.copy(),
        normal_z=np.ones((3,6)),length=np.ones((3,6)),diffraction=np.zeros(2,complex))
    if corrupt=='pressure':
        fields['pressure'][:]=1.
    elif corrupt=='phase':
        fields['psi'][:]=1.
    else:
        fields['diffraction'][:]=1.
    np.savez(source/'fields.npz',**fields)
    out=tmp_path/'audit'
    with pytest.raises(ValueError,match='replay failed'):
        run(source,out)
    assert not (out/'summary.json').exists()
