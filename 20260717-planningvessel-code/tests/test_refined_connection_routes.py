import pytest
from scripts.verify_refined_kernel_connection import verify_routes


def test_old_defaults_and_new_explicit_routes():
    hydro = dict(head_sea_excitation_formulation='matched_domain_incident_diffraction',cutoff_quadrature='clipped_linear')
    contract = dict(cutoff_quadrature='clipped_linear')
    verify_routes(hydro,contract)
    contract.update(panel_integration_route='reconstructed_symmetric',waterline_grading_exponent=1.5)
    with pytest.raises(ValueError,match='mismatch'):
        verify_routes(hydro,contract)
    hydro.update(panel_integration_route='reconstructed_symmetric',waterline_grading_exponent=1.5)
    verify_routes(hydro,contract)
    with pytest.raises(ValueError,match='mismatch'):
        verify_routes(dict(hydro,waterline_grading_exponent=1.),contract)
    with pytest.raises(ValueError,match='Unsupported panel'):
        verify_routes(dict(hydro,panel_integration_route='fake'),dict(contract,panel_integration_route='fake'))
