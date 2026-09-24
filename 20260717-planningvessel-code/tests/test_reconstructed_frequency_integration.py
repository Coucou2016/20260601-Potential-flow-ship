import numpy as np
from planing_seakeeping.config import BoatConfig, PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.planing_frequency_correction import compute_matched_bie_frequency_correction
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


def test_real_radiation_and_diffraction_entry_with_grading():
    boat = BoatConfig(length_m=1.9, beam_m=.424, deadrise_deg=16.7, mass_kg=32.6,
                      lcg_m=.697, vcg_m=.143, pitch_radius_gyration_m=.583)
    eq = make_prescribed_equilibrium(boat, 3.4,
        PrescribedRunningStateConfig(enabled=True, trim_deg=4., lambda_w=3.))
    with panel_integration_route('reconstructed_symmetric'):
        result = compute_matched_bie_frequency_correction(boat, eq, np.array([5.,7.]),
            high_frequency_reference_rad_s=10., station_count=9, body_panels_per_section=12,
            free_surface_inner_panels=8, free_surface_outer_panels=12,
            history_steps=16, history_quadrature_count=16, waterline_grading_exponent=1.5,
            restoring_matrix=np.eye(2), head_sea_excitation_formulation='matched_domain_incident_diffraction',
            cutoff_quadrature='clipped_linear')
    assert result.metadata['waterline_grading_exponent'] == 1.5
    assert result.metadata['steady_perturbation_potential_solved'] is False
    assert 'not_solved_steady_planing_flow' in result.metadata['forward_speed_body_condition']
    assert np.isfinite(result.raw_added_mass).all()
    assert np.isfinite(result.raw_radiation_damping).all()
    assert np.isfinite(result.excitation_components['matched_domain_incident_plus_diffraction']).all()


def test_case_model_uses_same_explicit_kernel_for_steady_series():
    from planing_seakeeping.linear_case import build_case_model,steady_series
    from planing_seakeeping.kernels.linear_2p5d.panel_integrals import current_panel_integration_route
    boat = BoatConfig(length_m=1.9, beam_m=.424, deadrise_deg=16.7, mass_kg=32.6,
                      lcg_m=.697, vcg_m=.143, pitch_radius_gyration_m=.583)
    case = dict(speed_mps=3.4,trim_deg=4.,lambda_w=3.,
                encounter_omega_rad_s=[5.,6.,7.],wave_amplitude_m=[.005]*3)
    mesh = dict(station_count=9,body_panels_per_section=12,free_surface_inner_panels=8,
        free_surface_outer_panels=12,frequency_samples=3,frequency_sampling='case_frequencies',
        history_steps=16,history_quadrature_count=16,history_k_max=25.)
    model,correction,_,_ = build_case_model(boat,case,mesh,
        head_sea_excitation_formulation='matched_domain_incident_diffraction',cutoff_quadrature='clipped_linear',
        panel_route='reconstructed_symmetric',waterline_grading_exponent=1.5)
    assert current_panel_integration_route() == 'midpoint'
    assert correction.metadata['panel_integration_route'] == 'reconstructed_symmetric'
    assert correction.metadata['panel_route_physical_acceptance'] == 'NOT_VALIDATED'
    series = steady_series(model,0)
    omega = model.hydrodynamics.solver_omega_rad_s[0]
    np.testing.assert_allclose(series.cg_accel_mps2,-omega**2*series.heave_m,atol=1e-13)
    assert np.isfinite(series.to_numpy()).all()
