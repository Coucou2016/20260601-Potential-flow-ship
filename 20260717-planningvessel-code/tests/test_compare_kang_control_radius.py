import json
import numpy as np
import pytest
from scripts.compare_kang_control_radius import compare


def make_runs(tmp_path):
    roots=[tmp_path/'base',tmp_path/'expanded']
    for i,root in enumerate(roots):
        root.mkdir()
        (root/'contract.json').write_text(json.dumps(dict(
            body_neumann_convention='fluid_domain_outward_diffraction_minus_incident',
            frequency=3.,radius_beams=3.+i,control_panels=96+32*i,
            outer_panels_per_side=44+18*i)))
        fields={k:np.ones(3) for k in ('x_m','y','z_down','normal_y','normal_z','length')}
        fields.update(incident=np.ones(2),diffraction=np.ones(2)*(1+1j*i),total=np.ones(2)*(2+1j*i))
        np.savez(root/'fields.npz',**fields)
    return roots


def test_complex_change_preserves_phase_information(tmp_path):
    a,b=make_runs(tmp_path)
    compare(a,b,tmp_path/'audit')
    result=json.loads((tmp_path/'audit/comparison.json').read_text())
    assert result['stage_acceptance'] is False
    np.testing.assert_allclose(result['results']['diffraction']['relative_complex_change'],1.)


def test_different_physical_setting_is_rejected(tmp_path):
    a,b=make_runs(tmp_path)
    path=b/'contract.json'; contract=json.loads(path.read_text()); contract['frequency']=4.
    path.write_text(json.dumps(contract))
    with pytest.raises(ValueError,match='Non-domain settings'):
        compare(a,b,tmp_path/'audit')
    assert not (tmp_path/'audit').exists()
