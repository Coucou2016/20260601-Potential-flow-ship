# Validation Report

## Objective

Build toward a verifiable complete 2.5D planing-craft seakeeping model. A prediction is treated as validated only when it reproduces published benchmark quantities, not merely when the solver runs.

## Current Benchmarks

- Faltinsen Ch. 9 prescribed running state: beta=20 deg, lambda_W=4, trim=4 deg, Fn_B=3, lcg/B=2.13, vcg/B=0.25, M/(rho B^3)=1.28, r55/B=1.3.
- Current gate checks prescribed-state reconstruction, Table 9.2 nondimensional eigenvalues, and RAO peak locations.
- Digitized Figures 9.34/9.35 curves are loaded from `benchmarks/faltinsen_ch9` when available; otherwise the curve-amplitude checks are marked NOT_EVALUATED.
- Katayama/Hinami/Ikeda Fig. 7 regular head-wave cases are loaded from `benchmarks/katayama` when available; the current gate checks only clear jumping/non-jumping classification.
- Katayama Fig. 9/Fig. 10 source-text qualitative trends are written to `katayama_qualitative_trends.csv`; this gate is intentionally separate from the missing digitized amplitude curves.
- `katayama_nonlinear_pilot_trends.csv` records a short RK4 nonlinear time-domain pilot around the high-speed peak; it is a development diagnostic for peak reduction/shift and dryout risk, not an amplitude acceptance gate.
- Fridsma/Katayama amplitude comparison CSVs include frequency-domain gate values plus time-domain diagnostic columns; the time-domain columns are supporting evidence and do not relax the published-reference tolerances. Matching residual-summary CSVs group the same amplitude errors by metric and wavelength band for blocker triage.
- Fridsma response-model diagnostics compare frequency-domain RAO, linear time-series reconstruction, and short nonlinear time-domain response against the same source points; model-limit, dryout, and impact-acceleration flags are diagnostic only.
- Numerical and physical sanity checks cover time-step convergence, spectral-component convergence, matrix positivity, solved-equilibrium residuals, finite RAOs, trim range, speed-trend behavior, and reported linear-stability/porpoising margin.
- Experimental section-BEM sanity checks cover free-surface-panel convergence, body-panel convergence, incident/diffraction excitation, linear-system residuals, and matrix conditioning; they do not count as Ma 2005 acceptance.
- Experimental multi-mode section radiation now writes a sway/heave/roll matrix audit, and the compact section-BEM path writes body-panel radiation/diffraction pressure-transfer diagnostics plus a PDSTRIP-step pressure-gradient/end-term audit. These pressure functions still need Ma/PDSTRIP-style validation before claiming complete 2.5D assembly.
- The optional Ma 2005 hydro-model diagnostics compare `matched_bie_provider`, `prototype`, `section_bem`, `pdstrip_style`, `strip_2p5d_forward`, `strip_2p5d_pdstrip_step`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, `hybrid_forward_coupling`, and `hybrid_pressure_damping_coupling`; when `--ma-compare-external-pdstrip` is supplied they also include `external_pdstrip_sections`, `external_pdstrip_forward`, and `external_pdstrip_pdstrip_step`. These diagnostics are for solver triage, not acceptance.
- For `matched_bie_provider`, the Ma 2005 comparison table also exports pressure-chain diagnostics: selected Eq. (30) time/forward formula ratios, body-potential x-gradient gains and characteristic lengths, adjacent-station body-potential jump/phase/alignment checks, station geometry normalization, central/forward/backward gradient comparisons, diagnostic-only phase-aligned gradient checks, panel-geometry continuity checks, force-density peak-location diagnostics, aft-active-station single-section audits, diagnostic-only end-station exclusion matrices, pressure-to-potential gains, pressure-to-force gains, and raw-coefficient-to-reference ratios. These columns help separate formula closure from upstream potential scaling, station-gradient amplification, station-to-station phase discontinuity, panel-index continuity, localized force-density spikes, end-station sensitivity, and downstream nondimensionalization errors.
- Ma 2005 comparison rows also include Eq. (34) normalization audits: the documented length power, documented scale, required scale to hit the reference, and `L^0/L^1/L^2` candidate gate ratios. Candidate length powers are diagnostic only; the hard gate remains tied to the documented Eq. (34) convention.
- Ma 2005 coefficient CSVs include `abs_error`, `rel_error`, `effective_abs_tolerance`, `gate_error_ratio`, and `error_metric`; nondimensional near-zero reference values use a conservative absolute tolerance for the gate.
- When hydro-model diagnostics are requested, Ma 2005 coupling-variant sweep CSVs compare forward-speed sign, transpose, pitch-axis, speed-term, gradient-term, and PDSTRIP-step variants for `A35/A53/B35/B53`; the sweep also writes a PDSTRIP-step sign audit comparing the current station convention with the accumulator-sign alternative. These diagnostics are informational and do not change the gate.
- When Ma 2005 panel convergence is requested, pressure-transfer forward-speed models are rerun at multiple section-BEM panel resolutions; the resulting mesh-sensitivity summary helps distinguish numerical resolution from missing 2.5D physics, but it still does not relax the Ma coefficient gate.
- When station-contribution diagnostics are requested, Ma 2005 station-contribution CSVs decompose longitudinal `A33/B33/A35/B35/A53/B53/A55/B55` pressure-transfer and force-integrated terms by station; these rows explain failures but do not change the gate.
- Goal-gap audit rows keep Fridsma/Katayama amplitude datasets, Ma 2005 coefficient datasets, and the station-based 2.5D solver visible until they are actually implemented and validated.

## Status By Benchmark

```text
                     benchmark gate_status  pass_checks  fail_checks  not_evaluated_checks  info_checks  total_checks
faltinsen_ch9_prescribed_state        PASS           19            0                     0            3            22
```

## Faltinsen Table 9.2 Eigenvalues

- Faltinsen Table 9.2 eigenvalue comparison: overall=PASS, max_real_error=0.053, max_frequency_error=0.00182; mode_1_high_frequency: real_err=0.053, imag_err=0.000485, status=PASS; mode_2_low_frequency: real_err=0.00657, imag_err=0.00182, status=PASS.

## Result

```text
                     benchmark                                         metric                                            expected                                    actual rel_error tolerance status                                                                                                                                    note
faltinsen_ch9_prescribed_state                                prescribed_fn_b                                                 3.0                                       3.0       0.0       0.0   PASS                                                                                                                                        
faltinsen_ch9_prescribed_state                            prescribed_trim_deg                                                 4.0                                       4.0       0.0       0.0   PASS                                                                                                                                        
faltinsen_ch9_prescribed_state                            prescribed_lambda_w                                                 4.0                                       4.0       0.0  0.000001   PASS                                                                                                                                        
faltinsen_ch9_prescribed_state      calm_force_heave_residual_weight_fraction                    near zero for solved equilibrium                                 -0.470495                       INFO        This benchmark prescribes the running state; this residual diagnoses consistency with the current Savitsky force implementation.
faltinsen_ch9_prescribed_state calm_force_pitch_residual_weight_beam_fraction                    near zero for solved equilibrium                                  0.062745                       INFO        This benchmark prescribes the running state; this residual diagnoses consistency with the current Savitsky force implementation.
faltinsen_ch9_prescribed_state         total_mass_matrix_determinant_positive                                            positive                           10190104.306151                       PASS                                                                                                           Basic numerical sanity check.
faltinsen_ch9_prescribed_state                mode_1_high_frequency_real_part                                               -0.12                                 -0.113639  0.053009       0.1   PASS                                                                               Nondimensional eigenvalue real part, scaled by sqrt(B/g).
faltinsen_ch9_prescribed_state           mode_1_high_frequency_imaginary_part                                                1.91                                  1.909074  0.000485       0.1   PASS                                                                                    Nondimensional modal frequency, scaled by sqrt(B/g).
faltinsen_ch9_prescribed_state                 mode_2_low_frequency_real_part                                               -0.86                                  -0.85435   0.00657       0.1   PASS                                                                               Nondimensional eigenvalue real part, scaled by sqrt(B/g).
faltinsen_ch9_prescribed_state            mode_2_low_frequency_imaginary_part                                                0.67                                  0.668781  0.001819       0.1   PASS                                                                                    Nondimensional modal frequency, scaled by sqrt(B/g).
faltinsen_ch9_prescribed_state                              rao_values_finite                                          all finite                                all finite                       PASS                                                                                                Frequency-domain numerical sanity check.
faltinsen_ch9_prescribed_state                      jump_or_dryout_assessment not applicable to linear frequency-domain benchmark not evaluated in Faltinsen Ch. 9 RAO gate                       INFO                                          Jumping/flight/dryout must be assessed with Fridsma/Katayama nonlinear time-domain benchmarks.
faltinsen_ch9_prescribed_state                        heave_rao_peak_location                                                1.91                                  1.911373  0.000719       0.1   PASS     Modal peak location checked against the nearest Table 9.2 modal frequency; digitized lambda/L curve checks are reported separately.
faltinsen_ch9_prescribed_state                        pitch_rao_peak_location                                                1.91                                  1.911373  0.000719       0.1   PASS     Modal peak location checked against the nearest Table 9.2 modal frequency; digitized lambda/L curve checks are reported separately.
faltinsen_ch9_prescribed_state                     heave_rao_digitized_points                                                 >=2                                        18                       PASS Loaded D:\Projects\20260601-Potential-flow-ship\20260717-planningvessel-code\benchmarks\faltinsen_ch9\fig_9_34_heave_rao_digitized.csv.
faltinsen_ch9_prescribed_state              heave_rao_digitized_peak_location                                                3.75                                  3.732217  0.004742       0.1   PASS                                                   Peak location compared against digitized Faltinsen RAO curve in lambda/L coordinates.
faltinsen_ch9_prescribed_state             heave_rao_digitized_peak_amplitude                                                5.05                                  5.058264  0.001636       0.2   PASS                                                                          Peak amplitude compared against digitized Faltinsen RAO curve.
faltinsen_ch9_prescribed_state                heave_rao_digitized_curve_nrmse                                                 0.0                                  0.012278  0.012278      0.25   PASS                                                                                   Normalized RMSE over 18 overlapping digitized points.
faltinsen_ch9_prescribed_state                     pitch_rao_digitized_points                                                 >=2                                        18                       PASS Loaded D:\Projects\20260601-Potential-flow-ship\20260717-planningvessel-code\benchmarks\faltinsen_ch9\fig_9_35_pitch_rao_digitized.csv.
faltinsen_ch9_prescribed_state              pitch_rao_digitized_peak_location                                                3.75                                  3.732217  0.004742       0.1   PASS                                                   Peak location compared against digitized Faltinsen RAO curve in lambda/L coordinates.
faltinsen_ch9_prescribed_state             pitch_rao_digitized_peak_amplitude                                                6.45                                  6.452174  0.000337       0.2   PASS                                                                          Peak amplitude compared against digitized Faltinsen RAO curve.
faltinsen_ch9_prescribed_state                pitch_rao_digitized_curve_nrmse                                                 0.0                                  0.008703  0.008703      0.25   PASS                                                                                   Normalized RMSE over 18 overlapping digitized points.
```

## Interpretation

- No hard FAIL rows were produced by the currently implemented checks.
- Calm-force diagnostic residuals: heave=-0.470495, pitch=0.0627449.

## Next Validation Targets

1. Independently audit or refine the Faltinsen Fig. 9.34/9.35 digitized curves; the current peak-amplitude checks are active.
2. Audit the active Fridsma configuration A amplitude points against the original report, improve the solver until this gate passes, and digitize Katayama regular-wave heave, pitch, CG acceleration, and bow acceleration curves.
3. Replace the prototype station solver with a validated 2.5D section pressure/radiation/diffraction solver, add real SL-7 offsets, and pass the active Ma 2005 Wigley III / SL-7 coefficient gates.
