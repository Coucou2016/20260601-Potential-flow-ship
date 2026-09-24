# Gate 1 Failure Audit

Benchmark: `ma2005_wigley_iii_coefficients`

Current Gate 1 status: `PASS`.

This report is generated from the current `matched_bie_station_sweep` production route. It does not change the default solver; it only consolidates evidence for Eq.30 pressure recovery, Eq.32 forward-speed/end-contour assembly, candidate exclusion, and remaining blockers.

## Requirement Summary

| requirement | actual | requirement_status | source_file |
| --- | --- | --- | --- |
| provider_route_preserved | matched_bie_station_sweep | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| coefficient_output_complete | present=True; numeric_ok=True; rows=1 | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| eq30_component_split_complete | present=True; numeric_ok=True | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| closure_residual_below_1e-9 | 0 | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| finite_numeric_outputs | finite=True | PASS | ma2005_wigley_iii_coefficients_comparison.csv |
| current_default_gate | pass=1/1; failures=none | PASS | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| diagnostic_candidate_exclusion | best=current_default; pass=1/1; max_gate=0; median_gate=0; improved=0; worsened=0 | PENDING | ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary.csv |
| global_scale_fit_exclusion | best=least_squares_time_only; components=time_derivative; pass=1/1; max_gate=9.03094e-16; time_scale=1; gradient_scale=0; stokes_scale=0; end_scale=0 | PENDING | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| full_four_component_scale_fit_exclusion | full_four_component_fit=least_squares_time_gradient_stokes_end; pass=0/1; max_gate=nan; median_gate=nan; time_scale=nan; gradient_scale=nan; stokes_scale=nan; end_scale=nan | PASS | ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv |
| coefficient_family_scale_fit_exclusion | best=current_default; groups=1; pass=1/1; max_gate=0; median_gate=0; group_scale_spread=1 | PASS | ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary.csv |
| eq31_eq32_forward_identity_exclusion | best_equation_route=eq31_direct_time_plus_gradient; pass=1/1; max_gate=0; median_gate=0; identity_max_residual_over_tol=0; identity_pass=1/1 | PENDING | ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary.csv |
| station_forward_identity_localization | worst_coefficient=A33; peak_station=0; peak_x_over_l=0.25; peak_share=nan; first_share=nan; configured_end_share=nan; centroid_x_over_l=nan; conclusion=forward_identity_residual_is_numerically_small; max_station_integral_closure=0 | PASS | ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv |
| failure_source_identified | none | PASS | ma2005_wigley_iii_coefficients_gate1_failure_audit.csv |
| sl7_c1_data_discipline | surrogate/not-evaluated until machine-readable offsets are supplied | PASS | docs/next_phase_gate1_goal_acceptance_20260801.md |

## Coefficient Evidence

| coefficient | reference_value | computed_value | gate_error_ratio | status | dominant_eq30_component | failure_source |
| --- | --- | --- | --- | --- | --- | --- |
| A33 | 6.55656 | 6.55656 | 0 | PASS | time_derivative_pressure | passed_current_default |

## Candidate Exclusion Evidence

- Pressure-balance candidates: best=current_default; pass=1/1; max_gate=0; median_gate=0; improved=0; worsened=0. Policy: candidate_passes_full_gate_requires_equation_trace_before_default.
- Global component-scale fits: best=least_squares_time_only; components=time_derivative; pass=1/1; max_gate=9.03094e-16; time_scale=1; gradient_scale=0; stokes_scale=0; end_scale=0. Policy: global_scale_fit_matches_full_gate_but_is_not_a_physical_correction.
- Full four-component scale fit: full_four_component_fit=least_squares_time_gradient_stokes_end; pass=0/1; max_gate=nan; median_gate=nan; time_scale=nan; gradient_scale=nan; stokes_scale=nan; end_scale=nan.
- Shared coefficient-family scale fits: best=current_default; groups=1; pass=1/1; max_gate=0; median_gate=0; group_scale_spread=1. Policy: coefficient_family_scale_excluded_because_full_gate_not_passed.
- Eq31/Eq32 forward-speed routes: best_equation_route=eq31_direct_time_plus_gradient; pass=1/1; max_gate=0; median_gate=0; identity_max_residual_over_tol=0; identity_pass=1/1. Policy: forward_speed_route_matches_full_gate_requires_equation_trace_before_default.
- Station-level forward identity localization: worst_coefficient=A33; peak_station=0; peak_x_over_l=0.25; peak_share=nan; first_share=nan; configured_end_share=nan; centroid_x_over_l=nan; conclusion=forward_identity_residual_is_numerically_small; max_station_integral_closure=0.

## Remaining Blockers

_No rows._
