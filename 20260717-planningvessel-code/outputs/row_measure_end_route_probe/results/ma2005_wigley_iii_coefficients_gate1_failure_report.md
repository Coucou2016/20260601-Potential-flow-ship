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
| closure_residual_below_1e-9 | 0 | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| finite_numeric_outputs | finite=True | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| current_default_gate | pass=0/8; failures=forward_speed_pressure_gradient_station_mapping,heave_time_derivative_body_potential_scale,mixed_component_cancellation | PENDING | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| diagnostic_candidate_exclusion | best=gradient_flipped_keep_time_end; pass=0/8; max_gate=68.1587; median_gate=29.7261; improved=3; worsened=3 | PASS | ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary.csv |
| global_scale_fit_exclusion | best=least_squares_time_only; components=time_derivative; pass=2/8; max_gate=6.66667; time_scale=0.0904154; gradient_scale=0; stokes_scale=0; end_scale=0 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| full_four_component_scale_fit_exclusion | full_four_component_fit=least_squares_time_gradient_stokes_end; pass=4/8; max_gate=9.25131; median_gate=0.846055; time_scale=0.0938153; gradient_scale=0.312385; stokes_scale=-0.0855609; end_scale=-1.31141 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| coefficient_family_scale_fit_exclusion | best=column_and_ab_family_scale; groups=4; pass=5/8; max_gate=5.39515; median_gate=0.296615; group_scale_spread=10.3994 | PASS | ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary.csv |
| eq31_eq32_forward_identity_exclusion | best_equation_route=eq31_direct_time_plus_gradient; pass=0/8; max_gate=149.252; median_gate=34.1844; identity_max_residual_over_tol=141.613; identity_pass=2/8 | PASS | ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary.csv |
| complex_forward_identity_audit | pairable=2/4; unpairable=2; identity_pass=0; identity_fail=2; max_identity_norm=0.872132; median_identity_norm=0.842112; max_closure_norm=1.29541e-17; scale_abs_range=[0.127868, 0.609669]; phase_range=[-54.2613, 0]; paired_cells=53;55; unpaired_cells=33;35; conclusion=complex_identity_partially_evaluable_and_not_closed_frequency_pair_gap | PASS | ma2005_wigley_iii_coefficients_complex_forward_identity_summary.csv |
| projection_derivative_balance_audit | same_frequency=4/8; frequency_gap_or_missing=4; G_vs_D_pass=2; G_vs_SE_pass=2; D_vs_SE_pass=2; max_G_D_norm=1.4767; max_G_SE_norm=0.942154; max_D_SE_norm=1.26824; conclusion=same_frequency_projection_balance_does_not_close | PASS | ma2005_wigley_iii_coefficients_projection_derivative_balance_summary.csv |
| projection_transport_audit | same_frequency=4/8; max_G_T_norm=1.4767; max_T_endpoint_norm=0.743066; max_G_SE_norm=0.872132; max_T_SE_norm=1.26824; conclusions=direct_gradient_matches_projection_transport:1;projection_transport_difference_distributed_along_station_sweep:3;projection_transport_weakened_by_ab_frequency_gap:4 | PASS | ma2005_wigley_iii_coefficients_projection_transport_summary.csv |
| geometry_transport_balance_audit | same_frequency=4/8; pass=1; fail=3; opposite_sign=2; wrong_magnitude=0; max_norm=1.45418; max_abs_inferred=1.51951; max_abs_required=3.3456; conclusion=same_frequency_geometry_transport_opposes_required_balance | PASS | ma2005_wigley_iii_coefficients_geometry_transport_balance_summary.csv |
| eq30_component_contribution_audit | pass=0/8; max_gate=164.377; max_closure=0; dominant_current=forward_speed_pressure_gradient:5;time_derivative_pressure:3; failure_sources=forward_speed_pressure_gradient_station_mapping:5;mixed_component_cancellation:1;time_derivative_body_potential_scale:2; conclusion=Gate 1 remains PENDING: time-derivative body-potential scale dominates A33/A53, while forward-speed pressure-gradient/station mapping dominates most remaining failed damping/coupling rows. | PASS | ma2005_wigley_iii_coefficients_eq30_component_contribution_summary.csv |
| station_mapping_gradient_audit | forward_gradient_failures=5; high_mapping_risk=5; peak_near_aft_startup=8; max_body_jump=1.07917; max_panel_y_jump=0.484868; max_beam_jump=0.486842; max_gradient_gain_L=105.02; conclusion=Forward-gradient-dominant failures coincide with large body-potential, panel, or station-geometry jumps at the pressure-gradient peak. | PASS | ma2005_wigley_iii_coefficients_station_mapping_gradient_summary.csv |
| station_marching_direction_audit | a1_match=8/8; mismatch=0; aft_peak=8; bow_start_peak=0; march_start_peak=0; first_x_over_l_range=[0.975, 0.975]; last_x_over_l_range=[0.025, 0.025]; conclusion=a1_bow_to_aft_marching_confirmed_aft_terminal_gradient_peak_remains | PASS | ma2005_wigley_iii_coefficients_station_marching_direction_summary.csv |
| aft_terminal_end_closure_audit | finite_end_scale=6/8; scale_abs_range=[2.08372, 17.2874]; scale_abs_spread=8.29644; terminal_10pct_high_share=0/8; terminal_10pct_share_range=[0, 0.367848]; end_endpoint_ratio_range=[0.438853, 0.801548]; decisions=end_scale_not_evaluable:2;finite_required_end_scale_but_needs_shared_trace:6; conclusion=end_scale_not_finite_for_all_rows_terminal_band_not_sufficient | PASS | ma2005_wigley_iii_coefficients_aft_terminal_end_closure_summary.csv |
| stokes_end_lever_consistency_audit | identity_pass=2/8; identity_fail=6; heave_m3_zero_pass=4/4; end_lever_pass=8/8; max_identity_residual_over_tol=141.613; end_ratio_abs_range=[0.438853, 0.801548]; conclusion=eq31_eq32_stokes_end_identity_not_closed | PASS | ma2005_wigley_iii_coefficients_stokes_end_lever_consistency_summary.csv |
| free_surface_marching_time_step_exclusion | best=free_surface_marching_disabled; time_step_scale=1; use_marching=False; velocity_scale=1; history_rhs_scale=1; pass=1/8; max_gate=21.4786; median_gate=5.55242; improved=7; worsened=1; best_time_step=free_surface_time_step_quarter; time_step_scale=0.25; pass=0/8; max_gate=61.1746; median_gate=10.388 | PASS | ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary.csv |
| local_time_pressure_free_surface_cross_probe | best=local_phase_chain_no_free_surface_marching; use_marching=False; apply_local_time_phase=True; chain_gradient=True; pass=1/8; max_gate=21.1078; median_gate=5.706; worst=B35; A33_status=PASS; A33_gate=0.313116; conclusion=local_time_chain_closes_a33_only | PASS | ma2005_wigley_iii_coefficients_local_time_free_surface_cross_probe_summary.csv |
| rhs_source_decomposition | rows=8; reconstruction_statuses=PASS; max_source_sum_relative_residual=9.65634e-16; dominant_sources=inner_free_surface_potential:8; worst_coefficient=B35; worst_dominant=inner_free_surface_potential; worst_body_ratios=inner_free_surface_potential:0.921713;body_normal_velocity:0.12671;outer_control_history:0.000159525; worst_rhs_ratios=inner_free_surface_potential:0.778909;body_normal_velocity:0.407325;outer_control_history:0.00138389; conclusion=rhs_source_decomposition_identifies_inner_free_surface_potential_as_body_potential_dominant | PASS | ma2005_wigley_iii_coefficients_rhs_source_decomposition_summary.csv |
| inner_free_surface_state_marching | rows=8; reconstruction_statuses=PASS; max_update_relative_residual=0; max_transfer_relative_residual=0; worst_coefficient=B35; peak_x_over_l=0.342105; peak_potential_after_norm=3.19009; max_growth=5.06379; update_kinds=advance_eq19_20:38;initialize_eq21_22:1; conclusion=inner_free_surface_state_reconstructs_eq19_22_but_gate_row_still_fails | PASS | ma2005_wigley_iii_coefficients_inner_free_surface_state_marching_summary.csv |
| station_forward_identity_localization | worst_coefficient=B33; peak_station=2; peak_x_over_l=0.075; peak_share=0.101607; first_share=0.0336542; configured_end_share=0.0336542; centroid_x_over_l=0.345544; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=5.32907e-15 | PASS | ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv |
| section_force_derivative_path_localization | worst_coefficient=B33; matrix_cell=33; gradient_integral=8.67842; derivative_proxy_integral=1.84194; difference_integral=6.83648; peak_station=0; peak_x_over_l=0.025; centroid_x_over_l=0.255911; conclusion=difference_distributed_along_station_sweep; max_station_integral_closure=1.77636e-15 | PASS | ma2005_wigley_iii_coefficients_section_force_derivative_summary.csv |
| failure_source_identified | forward_speed_pressure_gradient_station_mapping,heave_time_derivative_body_potential_scale,mixed_component_cancellation | PASS | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| sl7_c1_data_discipline | surrogate/not-evaluated until machine-readable offsets are supplied | PASS | docs/next_phase_gate1_goal_acceptance_20260801.md |

## Coefficient Evidence

| coefficient | reference_value | computed_value | gate_error_ratio | status | dominant_eq30_component | failure_source |
| --- | --- | --- | --- | --- | --- | --- |
| A33 | 1 | 10.1864 | 61.2428 | FAIL | time_derivative_pressure | heave_time_derivative_body_potential_scale |
| B33 | 2.1 | 9.18043 | 22.4776 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| A35 | -0.2 | -2.70082 | 41.6804 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| B35 | 0.13 | 6.54072 | 164.377 | FAIL | time_derivative_pressure | mixed_component_cancellation |
| A53 | 0.15 | 1.41791 | 28.1759 | FAIL | time_derivative_pressure | heave_time_derivative_body_potential_scale |
| B53 | -0.1 | -0.252062 | 5.06873 | FAIL | stokes_body_forward_speed | forward_speed_pressure_gradient_station_mapping |
| A55 | 0.063 | 0.159851 | 10.2488 | FAIL | stokes_body_forward_speed | forward_speed_pressure_gradient_station_mapping |
| B55 | 0.09 | 1.85871 | 131.016 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |

## Candidate Exclusion Evidence

- Pressure-balance candidates: best=gradient_flipped_keep_time_end; pass=0/8; max_gate=68.1587; median_gate=29.7261; improved=3; worsened=3. Policy: diagnostic_only_excluded_because_full_gate_not_passed.
- Global component-scale fits: best=least_squares_time_only; components=time_derivative; pass=2/8; max_gate=6.66667; time_scale=0.0904154; gradient_scale=0; stokes_scale=0; end_scale=0. Policy: global_scale_fit_excluded_because_full_gate_not_passed.
- Full four-component scale fit: full_four_component_fit=least_squares_time_gradient_stokes_end; pass=4/8; max_gate=9.25131; median_gate=0.846055; time_scale=0.0938153; gradient_scale=0.312385; stokes_scale=-0.0855609; end_scale=-1.31141.
- Shared coefficient-family scale fits: best=column_and_ab_family_scale; groups=4; pass=5/8; max_gate=5.39515; median_gate=0.296615; group_scale_spread=10.3994. Policy: coefficient_family_scale_excluded_because_full_gate_not_passed.
- Eq31/Eq32 forward-speed routes: best_equation_route=eq31_direct_time_plus_gradient; pass=0/8; max_gate=149.252; median_gate=34.1844; identity_max_residual_over_tol=141.613; identity_pass=2/8. Policy: eq31_eq32_forward_routes_excluded_because_full_gate_not_passed_or_identity_not_closed.
- Eq30/Eq32 component contribution audit: pass=0/8; max_gate=164.377; max_closure=0; dominant_current=forward_speed_pressure_gradient:5;time_derivative_pressure:3; failure_sources=forward_speed_pressure_gradient_station_mapping:5;mixed_component_cancellation:1;time_derivative_body_potential_scale:2; conclusion=Gate 1 remains PENDING: time-derivative body-potential scale dominates A33/A53, while forward-speed pressure-gradient/station mapping dominates most remaining failed damping/coupling rows..
- Eq23/Eq24 RHS source decomposition: rows=8; reconstruction_statuses=PASS; max_source_sum_relative_residual=9.65634e-16; dominant_sources=inner_free_surface_potential:8; worst_coefficient=B35; worst_dominant=inner_free_surface_potential; worst_body_ratios=inner_free_surface_potential:0.921713;body_normal_velocity:0.12671;outer_control_history:0.000159525; worst_rhs_ratios=inner_free_surface_potential:0.778909;body_normal_velocity:0.407325;outer_control_history:0.00138389; conclusion=rhs_source_decomposition_identifies_inner_free_surface_potential_as_body_potential_dominant.
- Inner-free-surface state marching: rows=8; reconstruction_statuses=PASS; max_update_relative_residual=0; max_transfer_relative_residual=0; worst_coefficient=B35; peak_x_over_l=0.342105; peak_potential_after_norm=3.19009; max_growth=5.06379; update_kinds=advance_eq19_20:38;initialize_eq21_22:1; conclusion=inner_free_surface_state_reconstructs_eq19_22_but_gate_row_still_fails.
- Station-level forward identity localization: worst_coefficient=B33; peak_station=2; peak_x_over_l=0.075; peak_share=0.101607; first_share=0.0336542; configured_end_share=0.0336542; centroid_x_over_l=0.345544; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=5.32907e-15.
- Section-force derivative path localization: worst_coefficient=B33; matrix_cell=33; gradient_integral=8.67842; derivative_proxy_integral=1.84194; difference_integral=6.83648; peak_station=0; peak_x_over_l=0.025; centroid_x_over_l=0.255911; conclusion=difference_distributed_along_station_sweep; max_station_integral_closure=1.77636e-15.

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
| B55 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
