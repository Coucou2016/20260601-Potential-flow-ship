# Fridsma Rough-Water Planing-Craft Benchmarks

Reference target:

- Fridsma systematic rough-water planing-craft experiments.
- Intended checks: heave, pitch, CG vertical acceleration, bow vertical acceleration, and added resistance trends.

Planned files:

- `regular_wave_motion_digitized.csv`
- `acceleration_digitized.csv`
- `added_resistance_digitized.csv`

Current data:

- `regular_wave_motion_digitized.csv` contains five development-grade points for Fridsma configuration A, as reported in Sun & Faltinsen 2010 Fig. 4 and Fig. 6.
- The source gives wave amplitude `zeta_a/B=0.0555`; the CSV stores `wave_height_over_b=0.111` because the validator expects wave height.
- Sun & Faltinsen state that the numerical comparisons use the measured calm-water attitude, so the CSV stores `running_trim_deg=4.0` and `running_lambda_w=3.6`; the validator applies these as a prescribed running state instead of solving a new calm-water equilibrium.
- The heave ordinate is `eta3a/zeta_a` and is stored directly as `heave_rao_m_per_m`.
- The pitch ordinate in Fig. 4 is `eta5a/(k*zeta_a)`; the CSV stores `pitch_rao_rad_per_m = eta5a/zeta_a = ordinate*k`.
- Bow acceleration is from the accelerometer 10 percent `L` aft of the stem, so `bow_x_from_cg_m` is set explicitly instead of using the stem default.
- The values are approximate parsed-figure points, not a final manual digitization of the original Fridsma report.

Minimum columns for motion validation:

- `case_id`
- `fn_b` or dimensional speed plus enough geometry to compute `Fn_B`
- `wave_height_over_b`
- `lambda_over_l` or `omega_e_sqrt_b_over_g`
- `heave_rao_m_per_m`
- `pitch_rao_rad_per_m`
- `cg_accel_g`
- `bow_accel_g`
- optional hull reconstruction columns: `length_m`, `beam_m`, `deadrise_deg`, `mass_kg`, `mass_over_rho_b3`, `lcg_from_transom_m`, `lcg_over_b`, `kg_above_keel_m`, `vcg_over_b`, `pitch_radius_gyration_m`, `r55_over_b`

Acceptance target for clearly non-jumping, low-wave cases:

- heave/pitch amplitude relative error <=25%
- acceleration relative error <=35%

Validation behavior:

- If `regular_wave_motion_digitized.csv` is missing, `validate --benchmark all` reports `NOT_EVALUATED`.
- If it is present, the validator reconstructs each regular-wave case, computes heave/pitch RAO and CG/bow acceleration, and writes `fridsma_regular_wave_amplitudes_comparison.csv`.
- The validator also writes `figures/fridsma_regular_wave_amplitudes_comparison.png` with the digitized experiment, current frequency-domain gate values, a time-domain diagnostic curve, and failed-tolerance points for each metric.
- The comparison CSV includes `time_domain_value`, `time_domain_rel_error`, `time_domain_status`, `time_domain_dryout_risk_flag`, and `time_domain_impact_accel_risk_flag`; these are supporting diagnostics and do not relax the hard Fridsma amplitude tolerances.
- The validator also writes `fridsma_regular_wave_amplitudes_response_model_comparison.csv`, `fridsma_regular_wave_amplitudes_response_model_summary.csv`, and `figures/fridsma_regular_wave_amplitudes_response_model_comparison.png`.
- The response-model diagnostic compares frequency-domain RAO, linear time-series reconstruction, and a short nonlinear time-domain path against the same source points. It reports model-limit/dryout/fallback flags so a nonlinear run cannot silently replace the hard experimental gate.
- If `running_trim_deg` plus `running_lambda_w` are present, the validator uses that source-backed prescribed state; the calm-force residual is reported as a diagnostic, not as a convergence failure.
- If hull reconstruction columns are omitted, documented development defaults are used; real Fridsma validation should provide the actual model geometry and mass properties.

Latest local status:

- `outputs/validation_current` reports `fridsma_regular_wave_amplitudes=FAIL` with 15 PASS and 12 FAIL checks.
- The 20 direct amplitude rows are 9 PASS / 11 FAIL; the five prescribed-running-state checks pass and document the source-backed `trim=4 deg`, `lambda_W=3.6`; the aggregate max-error row fails and points to the comparison figure.
- Long-wave points are closer to the experiment, while `lambda/L=1-3` and the bow acceleration at `lambda/L=6` still expose the limits of the current compact longitudinal model.

Do not add placeholder numeric data here. Add only digitized or tabulated values with a source note.
