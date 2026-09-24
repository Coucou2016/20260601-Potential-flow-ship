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
| current_default_gate | pass=1/8; failures=first_active_station_pressure_gradient_spike,heave_time_derivative_body_potential_scale | PENDING | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| diagnostic_candidate_exclusion | best=gradient_flipped_keep_time_end; pass=0/8; max_gate=70.405; median_gate=29.0371; improved=3; worsened=3 | PASS | ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary.csv |
| global_scale_fit_exclusion | best=least_squares_time_only; components=time_derivative; pass=2/8; max_gate=6.66667; time_scale=0.0894919; gradient_scale=0; stokes_scale=0; end_scale=0 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| full_four_component_scale_fit_exclusion | full_four_component_fit=least_squares_time_gradient_stokes_end; pass=4/8; max_gate=9.04476; median_gate=0.881189; time_scale=0.0927999; gradient_scale=0.313511; stokes_scale=-0.0907734; end_scale=-1.30218 | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| coefficient_family_scale_fit_exclusion | best=column_and_ab_family_scale; groups=4; pass=5/8; max_gate=5.98301; median_gate=0.283523; group_scale_spread=9.86681 | PASS | ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary.csv |
| eq31_eq32_forward_identity_exclusion | best_equation_route=eq31_direct_time_plus_gradient; pass=0/8; max_gate=148.955; median_gate=35.2765; identity_max_residual_over_tol=146.046; identity_pass=2/8 | PASS | ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary.csv |
| station_forward_identity_localization | worst_coefficient=B33; peak_station=2; peak_x_over_l=0.075; peak_share=0.105378; first_share=0.0347535; configured_end_share=0.0347535; centroid_x_over_l=0.343998; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=1.77636e-15 | PASS | ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv |
| failure_source_identified | first_active_station_pressure_gradient_spike,heave_time_derivative_body_potential_scale | PASS | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| sl7_c1_data_discipline | surrogate/not-evaluated until machine-readable offsets are supplied | PASS | docs/next_phase_gate1_goal_acceptance_20260801.md |

## Coefficient Evidence

| coefficient | reference_value | computed_value | gate_error_ratio | status | dominant_eq30_component | failure_source |
| --- | --- | --- | --- | --- | --- | --- |
| A33 | 1 | 10.29 | 61.9333 | FAIL | time_derivative_pressure | heave_time_derivative_body_potential_scale |
| B33 | 2.1 | 9.64648 | 23.9571 | FAIL | forward_speed_pressure_gradient | first_active_station_pressure_gradient_spike |
| A35 | -0.2 | -2.81379 | 43.5631 | FAIL | forward_speed_pressure_gradient | first_active_station_pressure_gradient_spike |
| B35 | 0.13 | 6.52228 | 163.904 | FAIL | time_derivative_pressure | first_active_station_pressure_gradient_spike |
| A53 | 0.15 | 1.44473 | 28.7718 | FAIL | time_derivative_pressure | heave_time_derivative_body_potential_scale |
| B53 | -0.1 | -0.0943132 | 0.189561 | PASS | stokes_body_forward_speed | passed_current_default |
| A55 | 0.063 | 0.0900779 | 2.86539 | FAIL | stokes_body_forward_speed | first_active_station_pressure_gradient_spike |
| B55 | 0.09 | 1.85893 | 131.032 | FAIL | forward_speed_pressure_gradient | first_active_station_pressure_gradient_spike |

## Candidate Exclusion Evidence

- Pressure-balance candidates: best=gradient_flipped_keep_time_end; pass=0/8; max_gate=70.405; median_gate=29.0371; improved=3; worsened=3. Policy: diagnostic_only_excluded_because_full_gate_not_passed.
- Global component-scale fits: best=least_squares_time_only; components=time_derivative; pass=2/8; max_gate=6.66667; time_scale=0.0894919; gradient_scale=0; stokes_scale=0; end_scale=0. Policy: global_scale_fit_excluded_because_full_gate_not_passed.
- Full four-component scale fit: full_four_component_fit=least_squares_time_gradient_stokes_end; pass=4/8; max_gate=9.04476; median_gate=0.881189; time_scale=0.0927999; gradient_scale=0.313511; stokes_scale=-0.0907734; end_scale=-1.30218.
- Shared coefficient-family scale fits: best=column_and_ab_family_scale; groups=4; pass=5/8; max_gate=5.98301; median_gate=0.283523; group_scale_spread=9.86681. Policy: coefficient_family_scale_excluded_because_full_gate_not_passed.
- Eq31/Eq32 forward-speed routes: best_equation_route=eq31_direct_time_plus_gradient; pass=0/8; max_gate=148.955; median_gate=35.2765; identity_max_residual_over_tol=146.046; identity_pass=2/8. Policy: eq31_eq32_forward_routes_excluded_because_full_gate_not_passed_or_identity_not_closed.
- Station-level forward identity localization: worst_coefficient=B33; peak_station=2; peak_x_over_l=0.075; peak_share=0.105378; first_share=0.0347535; configured_end_share=0.0347535; centroid_x_over_l=0.343998; conclusion=residual_distributed_along_station_sweep; max_station_integral_closure=1.77636e-15.

## Remaining Blockers

| coefficient | remaining_blocker |
| --- | --- |
| A33 | Create an independent 2D section radiation pressure check for heave and align the body potential scale, pressure sign, and generalized force row. |
| B33 | Audit the first active wet station, ghost/startup treatment, and longitudinal derivative used by the pressure-gradient term. |
| A35 | Audit the first active wet station, ghost/startup treatment, and longitudinal derivative used by the pressure-gradient term. |
| B35 | Audit the first active wet station, ghost/startup treatment, and longitudinal derivative used by the pressure-gradient term. |
| A53 | Create an independent 2D section radiation pressure check for heave and align the body potential scale, pressure sign, and generalized force row. |
| A55 | Audit the first active wet station, ghost/startup treatment, and longitudinal derivative used by the pressure-gradient term. |
| B55 | Audit the first active wet station, ghost/startup treatment, and longitudinal derivative used by the pressure-gradient term. |
