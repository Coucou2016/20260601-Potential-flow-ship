# Gate 1 Failure Audit

Benchmark: `ma2005_wigley_iii_coefficients`

Current Gate 1 status: `PENDING`.

This report is generated from the current `matched_bie_station_sweep` production route. It does not change the default solver; it only consolidates evidence for Eq.30 pressure recovery, Eq.32 forward-speed/end-contour assembly, candidate exclusion, and remaining blockers.

## Requirement Summary

| requirement | actual | requirement_status | source_file |
| --- | --- | --- | --- |
| provider_route_preserved | matched_bie_station_sweep | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| coefficient_output_complete | present=True; numeric_ok=True; rows=8 | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| eq30_component_split_complete | present=True; numeric_ok=True | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| closure_residual_below_1e-9 | 1.54668e-15 | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| finite_numeric_outputs | finite=True | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| current_default_gate | pass=0/8; failures=forward_speed_pressure_gradient_station_mapping,heave_time_derivative_body_potential_scale,mixed_component_cancellation | PENDING | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| diagnostic_candidate_exclusion | best=all_terms_include_stokes; pass=0/8; max_gate=159.656; median_gate=94.3467; improved=3; worsened=3 | PASS | ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary.csv |
| global_scale_fit_exclusion | best=least_squares_time_gradient_stokes_end; components=time_derivative+pressure_gradient+stokes_body_forward+end_term; pass=5/8; max_gate=4.96617; time_scale=0.0573647; gradient_scale=0.106746; stokes_scale=0.0216868; end_scale=3.14968 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| full_four_component_scale_fit_exclusion | full_four_component_fit=least_squares_time_gradient_stokes_end; pass=5/8; max_gate=4.96617; median_gate=0.582001; time_scale=0.0573647; gradient_scale=0.106746; stokes_scale=0.0216868; end_scale=3.14968 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| coefficient_family_scale_fit_exclusion | best=force_row_family_scale; groups=2; pass=2/8; max_gate=6.78637; median_gate=3.26241; group_scale_spread=51.4165 | PASS | ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary.csv |
| eq31_eq32_forward_identity_exclusion | best_equation_route=eq32_stokes_time_plus_body_plus_end; pass=0/8; max_gate=243.278; median_gate=133.871; identity_max_residual_over_tol=550.968; identity_pass=2/8 | PASS | ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary.csv |
| complex_forward_identity_audit | pairable=2/4; unpairable=2; identity_pass=0; identity_fail=2; max_identity_norm=1.92534; median_identity_norm=1.89567; max_closure_norm=5.21317e-16; scale_abs_range=[0.878573, 0.925337]; phase_range=[-180, -166.705]; paired_cells=53;55; unpaired_cells=33;35; conclusion=complex_identity_partially_evaluable_and_not_closed_frequency_pair_gap | PASS | ma2005_wigley_iii_coefficients_complex_forward_identity_summary.csv |
| projection_derivative_balance_audit | same_frequency=4/8; frequency_gap_or_missing=4; G_vs_D_pass=2; G_vs_SE_pass=2; D_vs_SE_pass=2; max_G_D_norm=1.64968; max_G_SE_norm=1.92534; max_D_SE_norm=0.962159; conclusion=same_frequency_projection_balance_does_not_close | PASS | ma2005_wigley_iii_coefficients_projection_derivative_balance_summary.csv |
| projection_transport_audit | same_frequency=4/8; max_G_T_norm=1.64968; max_T_endpoint_norm=0.949602; max_G_SE_norm=1.92534; max_T_SE_norm=0.821703; conclusions=direct_gradient_matches_projection_transport:1;projection_transport_difference_biased_to_aft_startup_region:2;projection_transport_difference_distributed_along_station_sweep:1;projection_transport_weakened_by_ab_frequency_gap:4 | PASS | ma2005_wigley_iii_coefficients_projection_transport_summary.csv |
| geometry_transport_balance_audit | same_frequency=4/8; pass=1; fail=3; opposite_sign=0; wrong_magnitude=1; max_norm=0.644757; max_abs_inferred=8.93576; max_abs_required=13.0166; conclusion=same_frequency_geometry_transport_balance_does_not_close | PASS | ma2005_wigley_iii_coefficients_geometry_transport_balance_summary.csv |
| eq30_component_contribution_audit | pass=0/8; max_gate=299.101; max_closure=1.54668e-15; dominant_current=forward_speed_pressure_gradient:4;time_derivative_pressure:4; failure_sources=forward_speed_pressure_gradient_station_mapping:4;mixed_component_cancellation:2;time_derivative_body_potential_scale:2; conclusion=Gate 1 remains PENDING: time-derivative body-potential scale dominates A33/A53, while forward-speed pressure-gradient/station mapping dominates most remaining failed damping/coupling rows. | PASS | ma2005_wigley_iii_coefficients_eq30_component_contribution_summary.csv |
| station_mapping_gradient_audit | forward_gradient_failures=4; high_mapping_risk=4; peak_near_aft_startup=8; max_body_jump=1.15839; max_panel_y_jump=0.485422; max_beam_jump=0.486842; max_gradient_gain_L=78.6757; conclusion=Forward-gradient-dominant failures coincide with large body-potential, panel, or station-geometry jumps at the pressure-gradient peak. | PASS | ma2005_wigley_iii_coefficients_station_mapping_gradient_summary.csv |
| station_marching_direction_audit | a1_match=8/8; mismatch=0; aft_peak=8; bow_start_peak=0; march_start_peak=0; first_x_over_l_range=[0.975, 0.975]; last_x_over_l_range=[0.025, 0.025]; conclusion=a1_bow_to_aft_marching_confirmed_aft_terminal_gradient_peak_remains | PASS | ma2005_wigley_iii_coefficients_station_marching_direction_summary.csv |
| aft_terminal_end_closure_audit | finite_end_scale=6/8; scale_abs_range=[63.1501, 233.941]; scale_abs_spread=3.70453; terminal_10pct_high_share=0/8; terminal_10pct_share_range=[0, 0.619563]; end_endpoint_ratio_range=[0.0158281, 0.0408916]; decisions=end_scale_not_evaluable:2;required_end_scale_too_large_for_simple_default:6; conclusion=end_scale_not_finite_for_all_rows_terminal_band_not_sufficient | PASS | ma2005_wigley_iii_coefficients_aft_terminal_end_closure_summary.csv |
| stokes_end_lever_consistency_audit | identity_pass=2/8; identity_fail=6; heave_m3_zero_pass=4/4; end_lever_pass=8/8; max_identity_residual_over_tol=550.968; end_ratio_abs_range=[0.0158281, 0.0408916]; conclusion=eq31_eq32_stokes_end_identity_not_closed | PASS | ma2005_wigley_iii_coefficients_stokes_end_lever_consistency_summary.csv |
| free_surface_marching_time_step_exclusion | best=free_surface_marching_disabled; time_step_scale=1; use_marching=False; velocity_scale=1; history_rhs_scale=1; pass=2/8; max_gate=11.5361; median_gate=3.35285; improved=8; worsened=0; best_time_step=free_surface_time_step_quarter; time_step_scale=0.25; pass=2/8; max_gate=18.557; median_gate=6.60028 | PASS | ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary.csv |
| station_forward_identity_localization | worst_coefficient=B33; peak_station=3; peak_x_over_l=0.1; peak_share=0.20116; first_share=0.136596; configured_end_share=0.136596; centroid_x_over_l=0.152671; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=7.10543e-15 | PASS | ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv |
| section_force_derivative_path_localization | worst_coefficient=B33; matrix_cell=33; gradient_integral=31.7745; derivative_proxy_integral=-5.44099; difference_integral=37.2154; peak_station=2; peak_x_over_l=0.075; centroid_x_over_l=0.121014; conclusion=difference_biased_to_aft_startup_region; max_station_integral_closure=3.55271e-15 | PASS | ma2005_wigley_iii_coefficients_section_force_derivative_summary.csv |
| failure_source_identified | forward_speed_pressure_gradient_station_mapping,heave_time_derivative_body_potential_scale,mixed_component_cancellation | PASS | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| sl7_c1_data_discipline | surrogate/not-evaluated until machine-readable offsets are supplied | PASS | docs/next_phase_gate1_goal_acceptance_20260801.md |

## Coefficient Evidence

| coefficient | reference_value | computed_value | gate_error_ratio | status | dominant_eq30_component | failure_source |
| --- | --- | --- | --- | --- | --- | --- |
| A33 | 1 | 16.3945 | 102.63 | FAIL | time_derivative_pressure | heave_time_derivative_body_potential_scale |
| B33 | 2.1 | 31.3473 | 92.8485 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| A35 | -0.2 | -7.91185 | 128.531 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| B35 | 0.13 | 3.86795 | 95.8449 | FAIL | time_derivative_pressure | mixed_component_cancellation |
| A53 | 0.15 | 3.90635 | 83.4744 | FAIL | time_derivative_pressure | heave_time_derivative_body_potential_scale |
| B53 | -0.1 | 6.05302 | 205.101 | FAIL | stokes_body_forward_speed | forward_speed_pressure_gradient_station_mapping |
| A55 | 0.063 | -2.76351 | 299.101 | FAIL | stokes_body_forward_speed | forward_speed_pressure_gradient_station_mapping |
| B55 | 0.09 | 1.30975 | 90.3521 | FAIL | time_derivative_pressure | mixed_component_cancellation |

## Candidate Exclusion Evidence

- Pressure-balance candidates: best=all_terms_include_stokes; pass=0/8; max_gate=159.656; median_gate=94.3467; improved=3; worsened=3. Policy: diagnostic_only_excluded_because_full_gate_not_passed.
- Global component-scale fits: best=least_squares_time_gradient_stokes_end; components=time_derivative+pressure_gradient+stokes_body_forward+end_term; pass=5/8; max_gate=4.96617; time_scale=0.0573647; gradient_scale=0.106746; stokes_scale=0.0216868; end_scale=3.14968. Policy: global_scale_fit_excluded_because_full_gate_not_passed.
- Full four-component scale fit: full_four_component_fit=least_squares_time_gradient_stokes_end; pass=5/8; max_gate=4.96617; median_gate=0.582001; time_scale=0.0573647; gradient_scale=0.106746; stokes_scale=0.0216868; end_scale=3.14968.
- Shared coefficient-family scale fits: best=force_row_family_scale; groups=2; pass=2/8; max_gate=6.78637; median_gate=3.26241; group_scale_spread=51.4165. Policy: coefficient_family_scale_excluded_because_full_gate_not_passed.
- Eq31/Eq32 forward-speed routes: best_equation_route=eq32_stokes_time_plus_body_plus_end; pass=0/8; max_gate=243.278; median_gate=133.871; identity_max_residual_over_tol=550.968; identity_pass=2/8. Policy: eq31_eq32_forward_routes_excluded_because_full_gate_not_passed_or_identity_not_closed.
- Eq30/Eq32 component contribution audit: pass=0/8; max_gate=299.101; max_closure=1.54668e-15; dominant_current=forward_speed_pressure_gradient:4;time_derivative_pressure:4; failure_sources=forward_speed_pressure_gradient_station_mapping:4;mixed_component_cancellation:2;time_derivative_body_potential_scale:2; conclusion=Gate 1 remains PENDING: time-derivative body-potential scale dominates A33/A53, while forward-speed pressure-gradient/station mapping dominates most remaining failed damping/coupling rows..
- Station-level forward identity localization: worst_coefficient=B33; peak_station=3; peak_x_over_l=0.1; peak_share=0.20116; first_share=0.136596; configured_end_share=0.136596; centroid_x_over_l=0.152671; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=7.10543e-15.
- Section-force derivative path localization: worst_coefficient=B33; matrix_cell=33; gradient_integral=31.7745; derivative_proxy_integral=-5.44099; difference_integral=37.2154; peak_station=2; peak_x_over_l=0.075; centroid_x_over_l=0.121014; conclusion=difference_biased_to_aft_startup_region; max_station_integral_closure=3.55271e-15.

## Remaining Blockers

| coefficient | remaining_blocker |
| --- | --- |
| A33 | Create an independent 2D section radiation pressure check for heave and align the body potential scale, pressure sign, and generalized force row. |
| B33 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| A35 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| B35 | Audit the time-pressure body-potential scale and the forward-speed station-mapping derivative in one complex-valued coefficient chain before accepting any default change. |
| A53 | Create an independent 2D section radiation pressure check for heave and align the body potential scale, pressure sign, and generalized force row. |
| B53 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| A55 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| B55 | Audit the time-pressure body-potential scale and the forward-speed station-mapping derivative in one complex-valued coefficient chain before accepting any default change. |
