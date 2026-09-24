# Gate 1 Failure Audit

Benchmark: `ma2005_wigley_iii_coefficients`

Current Gate 1 status: `PENDING`.

This report is generated from the current `matched_bie_station_sweep` production route. It does not change the default solver; it only consolidates evidence for Eq.30 pressure recovery, Eq.32 forward-speed/end-contour assembly, candidate exclusion, and remaining blockers.

## Requirement Summary

| requirement | actual | requirement_status | source_file |
| --- | --- | --- | --- |
| provider_route_preserved | matched_bie_station_sweep | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| coefficient_output_complete | present=True; numeric_ok=True; rows=10 | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| eq30_component_split_complete | present=True; numeric_ok=True | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| closure_residual_below_1e-9 | 9.71445e-17 | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| finite_numeric_outputs | finite=True | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| current_default_gate | pass=9/10; failures=forward_speed_pressure_gradient_station_mapping | PENDING | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| diagnostic_candidate_exclusion | best=current_default; pass=9/10; max_gate=2.08327; median_gate=0.600784; improved=1; worsened=4 | PASS | ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary.csv |
| global_scale_fit_exclusion | best=least_squares_time_gradient_stokes_end; components=time_derivative+pressure_gradient+stokes_body_forward+end_term; pass=9/10; max_gate=1.64668; time_scale=1.16305; gradient_scale=0.262407; stokes_scale=0.954496; end_scale=0 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| full_four_component_scale_fit_exclusion | full_four_component_fit=least_squares_time_gradient_stokes_end; pass=9/10; max_gate=1.64668; median_gate=0.521887; time_scale=1.16305; gradient_scale=0.262407; stokes_scale=0.954496; end_scale=0 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| coefficient_family_scale_fit_exclusion | best=matrix_cell_shared_ab_scale; groups=4; pass=8/10; max_gate=1.12698; median_gate=0.373437; group_scale_spread=1.18681 | PASS | ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary.csv |
| eq31_eq32_forward_identity_exclusion | best_equation_route=eq32_stokes_time_plus_body_plus_end; pass=9/10; max_gate=2.08327; median_gate=0.600784; identity_max_residual_over_tol=3.26972; identity_pass=0/10 | PASS | ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary.csv |
| complex_forward_identity_audit | pairable=4/4; unpairable=2; identity_pass=0; identity_fail=4; max_identity_norm=1; median_identity_norm=0.951011; max_closure_norm=0.923981; scale_abs_range=[0.55079, 0.552828]; phase_range=[-63.6043, 24.9233]; paired_cells=33;35;53;55; unpaired_cells=33;53; conclusion=complex_identity_partially_evaluable_and_not_closed_frequency_pair_gap | PASS | ma2005_wigley_iii_coefficients_complex_forward_identity_summary.csv |
| projection_derivative_balance_audit | same_frequency=8/8; frequency_gap_or_missing=0; G_vs_D_pass=0; G_vs_SE_pass=0; D_vs_SE_pass=0; max_G_D_norm=1.10519; max_G_SE_norm=1.64283; max_D_SE_norm=1.19835; conclusion=same_frequency_projection_balance_does_not_close | PASS | ma2005_wigley_iii_coefficients_projection_derivative_balance_summary.csv |
| projection_transport_audit | same_frequency=4/8; max_G_T_norm=1.10519; max_T_endpoint_norm=1.11944; max_G_SE_norm=1.64283; max_T_SE_norm=1.19835; conclusions=projection_transport_difference_distributed_along_station_sweep:4;projection_transport_station_grid_mismatch:4 | PASS | ma2005_wigley_iii_coefficients_projection_transport_summary.csv |
| geometry_transport_balance_audit | same_frequency=4/8; pass=0; fail=4; opposite_sign=1; wrong_magnitude=1; max_norm=1.83834; max_abs_inferred=0.124371; max_abs_required=0.126312; conclusion=same_frequency_geometry_transport_opposes_required_balance | PASS | ma2005_wigley_iii_coefficients_geometry_transport_balance_summary.csv |
| eq30_component_contribution_audit | pass=9/10; max_gate=2.08327; max_closure=9.71445e-17; dominant_current=stokes_body_forward_speed:4;time_derivative_pressure:6; failure_sources=passed_current_default:9;stokes_body_forward_speed_eq32_mismatch:1; conclusion=The A33/A53 time-pressure/body-potential chain passes; the complete eight-coefficient Gate remains pending only for B55. | PASS | ma2005_wigley_iii_coefficients_eq30_component_contribution_summary.csv |
| station_mapping_gradient_audit | forward_gradient_failures=1; high_mapping_risk=1; peak_near_aft_startup=2; max_body_jump=0.301105; max_panel_y_jump=0.476039; max_beam_jump=0.478672; max_gradient_gain_L=14.9682; conclusion=Forward-gradient-dominant failures coincide with large body-potential, panel, or station-geometry jumps at the pressure-gradient peak. | PASS | ma2005_wigley_iii_coefficients_station_mapping_gradient_summary.csv |
| station_marching_direction_audit | a1_match=10/10; mismatch=0; aft_peak=3; bow_start_peak=0; march_start_peak=0; first_x_over_l_range=[0.975, 0.975]; last_x_over_l_range=[0.025, 0.025]; conclusion=a1_bow_to_aft_marching_confirmed_aft_terminal_gradient_peak_remains | PASS | ma2005_wigley_iii_coefficients_station_marching_direction_summary.csv |
| aft_terminal_end_closure_audit | finite_end_scale=0/10; scale_abs_range=[nan, nan]; scale_abs_spread=nan; terminal_10pct_high_share=0/10; terminal_10pct_share_range=[0.0287373, 0.0977889]; end_endpoint_ratio_range=[0, 0]; decisions=end_scale_not_evaluable:10; conclusion=end_scale_not_finite_for_all_rows_terminal_band_not_sufficient | PASS | ma2005_wigley_iii_coefficients_aft_terminal_end_closure_summary.csv |
| stokes_end_lever_consistency_audit | identity_pass=0/10; identity_fail=10; heave_m3_zero_pass=5/5; end_lever_pass=0/10; max_identity_residual_over_tol=3.26972; end_ratio_abs_range=[0, 0]; conclusion=eq31_eq32_stokes_end_identity_not_closed | PASS | ma2005_wigley_iii_coefficients_stokes_end_lever_consistency_summary.csv |
| free_surface_marching_time_step_exclusion | best=outer_history_rhs_disabled; time_step_scale=1; use_marching=True; velocity_scale=1; history_rhs_scale=0; pass=8/10; max_gate=1.67244; median_gate=0.386158; improved=5; worsened=5; best_time_step=free_surface_time_step_quarter; time_step_scale=0.25; pass=0/10; max_gate=7.001; median_gate=3.28952 | PASS | ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary.csv |
| local_time_pressure_free_surface_cross_probe | best=default; use_marching=True; apply_local_time_phase=True; chain_gradient=True; pass=9/10; max_gate=2.08327; median_gate=0.600784; worst=B55; A33_status=PASS; A33_gate=0.32305; conclusion=local_time_free_surface_cross_probe_recorded | PASS | ma2005_wigley_iii_coefficients_local_time_free_surface_cross_probe_summary.csv |
| rhs_source_decomposition | rows=8; reconstruction_statuses=PASS; max_source_sum_relative_residual=4.09442e-15; dominant_sources=body_normal_velocity:4;inner_free_surface_potential:4; worst_coefficient=B55; worst_dominant=body_normal_velocity; worst_body_ratios=body_normal_velocity:0.947251;inner_free_surface_potential:0.689201;outer_control_history:0.0352201; worst_rhs_ratios=body_normal_velocity:0.948042;inner_free_surface_potential:0.343429;outer_control_history:0.136889; conclusion=rhs_source_decomposition_identifies_body_normal_velocity_as_body_potential_dominant | PASS | ma2005_wigley_iii_coefficients_rhs_source_decomposition_summary.csv |
| inner_free_surface_state_marching | not available | NOT_EVALUATED | ma2005_wigley_iii_coefficients_inner_free_surface_state_marching_summary.csv |
| station_forward_identity_localization | worst_coefficient=B33; peak_station=10; peak_x_over_l=0.275; peak_share=0.040281; first_share=0.00140362; configured_end_share=0.00140362; centroid_x_over_l=0.477121; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=1.38778e-16 | PASS | ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv |
| section_force_derivative_path_localization | worst_coefficient=B35; matrix_cell=35; gradient_integral=0.126312; derivative_proxy_integral=0.00194131; difference_integral=0.124371; peak_station=33; peak_x_over_l=0.85; centroid_x_over_l=0.632855; conclusion=difference_distributed_along_station_sweep; max_station_integral_closure=2.77556e-17 | PASS | ma2005_wigley_iii_coefficients_section_force_derivative_summary.csv |
| failure_source_identified | forward_speed_pressure_gradient_station_mapping | PASS | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| sl7_c1_data_discipline | surrogate/not-evaluated until machine-readable offsets are supplied | PASS | docs/next_phase_gate1_goal_acceptance_20260801.md |

## Coefficient Evidence

| coefficient | reference_value | computed_value | gate_error_ratio | status | dominant_eq30_component | failure_source |
| --- | --- | --- | --- | --- | --- | --- |
| A33 | 1.07 | 1.01815 | 0.32305 | PASS | time_derivative_pressure | passed_current_default |
| A33 | 0.941 | 0.895492 | 0.32241 | PASS | time_derivative_pressure | passed_current_default |
| B33 | 2.05 | 1.78618 | 0.857947 | PASS | time_derivative_pressure | passed_current_default |
| A53 | 0.19 | 0.155445 | 0.606224 | PASS | stokes_body_forward_speed | passed_current_default |
| A53 | 0.145 | 0.115501 | 0.678134 | PASS | stokes_body_forward_speed | passed_current_default |
| B53 | -0.106 | -0.124932 | 0.595345 | PASS | stokes_body_forward_speed | passed_current_default |
| A35 | -0.125 | -0.11323 | 0.313867 | PASS | time_derivative_pressure | passed_current_default |
| B35 | 0.163 | 0.140337 | 0.46345 | PASS | time_derivative_pressure | passed_current_default |
| A55 | 0.0458 | 0.0405595 | 0.762816 | PASS | time_derivative_pressure | passed_current_default |
| B55 | 0.0703 | 0.0483319 | 2.08327 | FAIL | stokes_body_forward_speed | forward_speed_pressure_gradient_station_mapping |

## Candidate Exclusion Evidence

- Pressure-balance candidates: best=current_default; pass=9/10; max_gate=2.08327; median_gate=0.600784; improved=1; worsened=4. Policy: diagnostic_only_excluded_because_full_gate_not_passed.
- Global component-scale fits: best=least_squares_time_gradient_stokes_end; components=time_derivative+pressure_gradient+stokes_body_forward+end_term; pass=9/10; max_gate=1.64668; time_scale=1.16305; gradient_scale=0.262407; stokes_scale=0.954496; end_scale=0. Policy: global_scale_fit_excluded_because_full_gate_not_passed.
- Full four-component scale fit: full_four_component_fit=least_squares_time_gradient_stokes_end; pass=9/10; max_gate=1.64668; median_gate=0.521887; time_scale=1.16305; gradient_scale=0.262407; stokes_scale=0.954496; end_scale=0.
- Shared coefficient-family scale fits: best=matrix_cell_shared_ab_scale; groups=4; pass=8/10; max_gate=1.12698; median_gate=0.373437; group_scale_spread=1.18681. Policy: coefficient_family_scale_excluded_because_full_gate_not_passed.
- Eq31/Eq32 forward-speed routes: best_equation_route=eq32_stokes_time_plus_body_plus_end; pass=9/10; max_gate=2.08327; median_gate=0.600784; identity_max_residual_over_tol=3.26972; identity_pass=0/10. Policy: eq31_eq32_forward_routes_excluded_because_full_gate_not_passed_or_identity_not_closed.
- Eq30/Eq32 component contribution audit: pass=9/10; max_gate=2.08327; max_closure=9.71445e-17; dominant_current=stokes_body_forward_speed:4;time_derivative_pressure:6; failure_sources=passed_current_default:9;stokes_body_forward_speed_eq32_mismatch:1; conclusion=The A33/A53 time-pressure/body-potential chain passes; the complete eight-coefficient Gate remains pending only for B55..
- Eq23/Eq24 RHS source decomposition: rows=8; reconstruction_statuses=PASS; max_source_sum_relative_residual=4.09442e-15; dominant_sources=body_normal_velocity:4;inner_free_surface_potential:4; worst_coefficient=B55; worst_dominant=body_normal_velocity; worst_body_ratios=body_normal_velocity:0.947251;inner_free_surface_potential:0.689201;outer_control_history:0.0352201; worst_rhs_ratios=body_normal_velocity:0.948042;inner_free_surface_potential:0.343429;outer_control_history:0.136889; conclusion=rhs_source_decomposition_identifies_body_normal_velocity_as_body_potential_dominant.
- Inner-free-surface state marching: not available.
- Station-level forward identity localization: worst_coefficient=B33; peak_station=10; peak_x_over_l=0.275; peak_share=0.040281; first_share=0.00140362; configured_end_share=0.00140362; centroid_x_over_l=0.477121; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=1.38778e-16.
- Section-force derivative path localization: worst_coefficient=B35; matrix_cell=35; gradient_integral=0.126312; derivative_proxy_integral=0.00194131; difference_integral=0.124371; peak_station=33; peak_x_over_l=0.85; centroid_x_over_l=0.632855; conclusion=difference_distributed_along_station_sweep; max_station_integral_closure=2.77556e-17.

## Remaining Blockers

| coefficient | remaining_blocker |
| --- | --- |
| B55 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
