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
| closure_residual_below_1e-9 | 4.17603e-15 | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| finite_numeric_outputs | finite=True | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| current_default_gate | pass=0/8; failures=forward_speed_pressure_gradient_station_mapping,heave_time_derivative_body_potential_scale | PENDING | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| diagnostic_candidate_exclusion | best=time_only_no_gradient_no_end; pass=0/8; max_gate=175.568; median_gate=68.7067; improved=5; worsened=1 | PASS | ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary.csv |
| global_scale_fit_exclusion | best=least_squares_time_gradient_end; components=time_derivative+pressure_gradient+end_term; pass=4/8; max_gate=5.1618; time_scale=0.0531267; gradient_scale=0.113175; stokes_scale=0; end_scale=-0.228162 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| full_four_component_scale_fit_exclusion | full_four_component_fit=least_squares_time_gradient_stokes_end; pass=5/8; max_gate=5.18107; median_gate=0.476273; time_scale=0.0536714; gradient_scale=0.187074; stokes_scale=-0.101368; end_scale=-0.424336 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| coefficient_family_scale_fit_exclusion | best=matrix_cell_shared_ab_scale; groups=4; pass=4/8; max_gate=6.0634; median_gate=2.24865; group_scale_spread=10.027 | PASS | ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary.csv |
| eq31_eq32_forward_identity_exclusion | best_equation_route=eq32_stokes_time_plus_body_plus_end; pass=0/8; max_gate=327.304; median_gate=109.149; identity_max_residual_over_tol=832.128; identity_pass=2/8 | PASS | ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary.csv |
| complex_forward_identity_audit | pairable=2/4; unpairable=2; identity_pass=0; identity_fail=2; max_identity_norm=0.760344; median_identity_norm=0.756059; max_closure_norm=1.14835e-16; scale_abs_range=[4.02859, 4.10946]; phase_range=[-8.69333, -0]; paired_cells=53;55; unpaired_cells=33;35; conclusion=complex_identity_partially_evaluable_and_not_closed_frequency_pair_gap | PASS | ma2005_wigley_iii_coefficients_complex_forward_identity_summary.csv |
| projection_derivative_balance_audit | same_frequency=4/8; frequency_gap_or_missing=4; G_vs_D_pass=2; G_vs_SE_pass=2; D_vs_SE_pass=2; max_G_D_norm=0.518447; max_G_SE_norm=0.935589; max_D_SE_norm=0.916519; conclusion=same_frequency_projection_balance_does_not_close | PASS | ma2005_wigley_iii_coefficients_projection_derivative_balance_summary.csv |
| projection_transport_audit | same_frequency=4/8; max_G_T_norm=0.29903; max_T_endpoint_norm=0.264265; max_G_SE_norm=0.935589; max_T_SE_norm=0.916519; conclusions=direct_gradient_matches_projection_transport:1;projection_transport_difference_biased_to_aft_startup_region:2;projection_transport_difference_distributed_along_station_sweep:1;projection_transport_weakened_by_ab_frequency_gap:4 | PASS | ma2005_wigley_iii_coefficients_projection_transport_summary.csv |
| geometry_transport_balance_audit | same_frequency=4/8; pass=1; fail=3; opposite_sign=0; wrong_magnitude=3; max_norm=0.755838; max_abs_inferred=7.81969; max_abs_required=19.659; conclusion=same_frequency_geometry_transport_balance_does_not_close | PASS | ma2005_wigley_iii_coefficients_geometry_transport_balance_summary.csv |
| eq30_component_contribution_audit | pass=0/8; max_gate=1729.52; max_closure=4.17603e-15; dominant_current=forward_speed_pressure_gradient:6;time_derivative_pressure:2; failure_sources=forward_speed_pressure_gradient_station_mapping:6;time_derivative_body_potential_scale:2; conclusion=Gate 1 remains PENDING: time-derivative body-potential scale dominates A33/A53, while forward-speed pressure-gradient/station mapping dominates most remaining failed damping/coupling rows. | PASS | ma2005_wigley_iii_coefficients_eq30_component_contribution_summary.csv |
| station_mapping_gradient_audit | forward_gradient_failures=6; high_mapping_risk=6; peak_near_aft_startup=8; max_body_jump=0.742956; max_panel_y_jump=0.48514; max_beam_jump=0.486842; max_gradient_gain_L=47.9484; conclusion=Forward-gradient-dominant failures coincide with large body-potential, panel, or station-geometry jumps at the pressure-gradient peak. | PASS | ma2005_wigley_iii_coefficients_station_mapping_gradient_summary.csv |
| station_marching_direction_audit | a1_match=8/8; mismatch=0; aft_peak=8; bow_start_peak=0; march_start_peak=0; first_x_over_l_range=[0.975, 0.975]; last_x_over_l_range=[0.025, 0.025]; conclusion=a1_bow_to_aft_marching_confirmed_aft_terminal_gradient_peak_remains | PASS | ma2005_wigley_iii_coefficients_station_marching_direction_summary.csv |
| aft_terminal_end_closure_audit | finite_end_scale=6/8; scale_abs_range=[2.45965, 2.77206]; scale_abs_spread=1.12701; terminal_10pct_high_share=0/8; terminal_10pct_share_range=[0, 0.571398]; end_endpoint_ratio_range=[1.30761, 1.33896]; decisions=end_scale_not_evaluable:2;finite_required_end_scale_but_needs_shared_trace:6; conclusion=end_scale_not_finite_for_all_rows_terminal_band_not_sufficient | PASS | ma2005_wigley_iii_coefficients_aft_terminal_end_closure_summary.csv |
| stokes_end_lever_consistency_audit | identity_pass=2/8; identity_fail=6; heave_m3_zero_pass=4/4; end_lever_pass=8/8; max_identity_residual_over_tol=832.128; end_ratio_abs_range=[1.30761, 1.33896]; conclusion=eq31_eq32_stokes_end_identity_not_closed | PASS | ma2005_wigley_iii_coefficients_stokes_end_lever_consistency_summary.csv |
| free_surface_marching_time_step_exclusion | best=free_surface_marching_disabled; time_step_scale=1; use_marching=False; velocity_scale=1; history_rhs_scale=1; pass=2/8; max_gate=14.5839; median_gate=3.27689; improved=8; worsened=0; best_time_step=free_surface_time_step_quarter; time_step_scale=0.25; pass=0/8; max_gate=84.328; median_gate=11.1358 | PASS | ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary.csv |
| station_forward_identity_localization | worst_coefficient=B33; peak_station=1; peak_x_over_l=0.05; peak_share=0.298096; first_share=0.095025; configured_end_share=0.095025; centroid_x_over_l=0.170492; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=7.10543e-15 | PASS | ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv |
| section_force_derivative_path_localization | worst_coefficient=B33; matrix_cell=33; gradient_integral=75.2448; derivative_proxy_integral=38.8035; difference_integral=36.4413; peak_station=1; peak_x_over_l=0.05; centroid_x_over_l=0.127321; conclusion=difference_biased_to_aft_startup_region; max_station_integral_closure=1.42109e-14 | PASS | ma2005_wigley_iii_coefficients_section_force_derivative_summary.csv |
| failure_source_identified | forward_speed_pressure_gradient_station_mapping,heave_time_derivative_body_potential_scale | PASS | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| sl7_c1_data_discipline | surrogate/not-evaluated until machine-readable offsets are supplied | PASS | docs/next_phase_gate1_goal_acceptance_20260801.md |

## Coefficient Evidence

| coefficient | reference_value | computed_value | gate_error_ratio | status | dominant_eq30_component | failure_source |
| --- | --- | --- | --- | --- | --- | --- |
| A33 | 1 | 17.4429 | 109.619 | FAIL | time_derivative_pressure | heave_time_derivative_body_potential_scale |
| B33 | 2.1 | 103.599 | 322.219 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| A35 | -0.2 | -21.1637 | 349.394 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| B35 | 0.13 | -2.86283 | 76.7392 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| A53 | 0.15 | 3.96904 | 84.8676 | FAIL | time_derivative_pressure | heave_time_derivative_body_potential_scale |
| B53 | -0.1 | 39.6185 | 1323.95 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| A55 | 0.063 | -16.281 | 1729.52 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |
| B55 | 0.09 | -1.83574 | 142.647 | FAIL | forward_speed_pressure_gradient | forward_speed_pressure_gradient_station_mapping |

## Candidate Exclusion Evidence

- Pressure-balance candidates: best=time_only_no_gradient_no_end; pass=0/8; max_gate=175.568; median_gate=68.7067; improved=5; worsened=1. Policy: diagnostic_only_excluded_because_full_gate_not_passed.
- Global component-scale fits: best=least_squares_time_gradient_end; components=time_derivative+pressure_gradient+end_term; pass=4/8; max_gate=5.1618; time_scale=0.0531267; gradient_scale=0.113175; stokes_scale=0; end_scale=-0.228162. Policy: global_scale_fit_excluded_because_full_gate_not_passed.
- Full four-component scale fit: full_four_component_fit=least_squares_time_gradient_stokes_end; pass=5/8; max_gate=5.18107; median_gate=0.476273; time_scale=0.0536714; gradient_scale=0.187074; stokes_scale=-0.101368; end_scale=-0.424336.
- Shared coefficient-family scale fits: best=matrix_cell_shared_ab_scale; groups=4; pass=4/8; max_gate=6.0634; median_gate=2.24865; group_scale_spread=10.027. Policy: coefficient_family_scale_excluded_because_full_gate_not_passed.
- Eq31/Eq32 forward-speed routes: best_equation_route=eq32_stokes_time_plus_body_plus_end; pass=0/8; max_gate=327.304; median_gate=109.149; identity_max_residual_over_tol=832.128; identity_pass=2/8. Policy: eq31_eq32_forward_routes_excluded_because_full_gate_not_passed_or_identity_not_closed.
- Eq30/Eq32 component contribution audit: pass=0/8; max_gate=1729.52; max_closure=4.17603e-15; dominant_current=forward_speed_pressure_gradient:6;time_derivative_pressure:2; failure_sources=forward_speed_pressure_gradient_station_mapping:6;time_derivative_body_potential_scale:2; conclusion=Gate 1 remains PENDING: time-derivative body-potential scale dominates A33/A53, while forward-speed pressure-gradient/station mapping dominates most remaining failed damping/coupling rows..
- Station-level forward identity localization: worst_coefficient=B33; peak_station=1; peak_x_over_l=0.05; peak_share=0.298096; first_share=0.095025; configured_end_share=0.095025; centroid_x_over_l=0.170492; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=7.10543e-15.
- Section-force derivative path localization: worst_coefficient=B33; matrix_cell=33; gradient_integral=75.2448; derivative_proxy_integral=38.8035; difference_integral=36.4413; peak_station=1; peak_x_over_l=0.05; centroid_x_over_l=0.127321; conclusion=difference_biased_to_aft_startup_region; max_station_integral_closure=1.42109e-14.

## Remaining Blockers

| coefficient | remaining_blocker |
| --- | --- |
| A33 | Create an independent 2D section radiation pressure check for heave and align the body potential scale, pressure sign, and generalized force row. |
| B33 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| A35 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| B35 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| A53 | Create an independent 2D section radiation pressure check for heave and align the body potential scale, pressure sign, and generalized force row. |
| B53 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| A55 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
| B55 | Derive and implement the fixed-surface station mapping for dphi/dx, then compare the result against Eq.32 Stokes body/end identity before changing the production default. |
