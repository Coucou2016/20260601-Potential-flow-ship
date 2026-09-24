# Ma 2005 Station-Based 2.5D Coefficient Benchmarks

Reference targets:

- Ma 2005 Matched BIEM curves are implementation-reproduction references for the station-based 2.5D solver.
- Journee 1992 forced-motion table values are independent physical-experiment references.
- These two layers answer different questions and must never be merged into one reference truth: agreement with Ma verifies reproduction of Ma's numerical formulation; agreement with Journee measures physical predictive accuracy.

Files:

- `wigley_iii_coefficients_digitized.csv` (present; source-image digitization of the Matched BIEM theory curves in Ma Figs. 11-18)
- `sl7_coefficients_digitized.csv` (present; development digitization from parsed Fig. 19-26 tables)
- `journee1992_wigley_iii_forced_coefficients.csv` (present; audited integrated forced-motion table rows from Journee 1992 for cross-checking sparse Wigley III reference frequency/value pairing)

Minimum columns:

- `hull`
- `speed_case`
- `omega_e_sqrt_l_over_g` or another documented nondimensional frequency
- `coefficient`
- `reference_value`
- optional `normalization`
- optional `length_m`, `beam_m`, `draft_m`, `station_count`, `rho_water_kg_m3`, `gravity_m_s2`
- optional `geometry_source`, `offsets_file`, `lcg_from_transom_m`, `lcg_aft_of_amidship_m`, `trim_by_stern_m`, `pitch_radius_gyration_m`, `pitch_radius_gyration_over_lbp`

Geometry provenance:

- Wigley III uses the analytic parabolic station formula documented for the Ma 2005 Wigley III case.
- SL-7 currently uses a documented surrogate hull constrained by Ma 2005 Table 2 main particulars until real numeric station offsets are digitized.
- For SL-7 rows without `lcg_from_transom_m`, the validator applies Ma Table 2 `LCG aft of amidship=11.7 m`, so `lcg_from_transom_m = 0.5*LBP - 11.7 = 122.5 m` when `length_m=268.4`.
- For SL-7 rows without pitch/trim fields, the validator records `trim_by_stern_m=0.043` and `pitch_radius_gyration_m=0.21*LBP`.
- A real SL-7 geometry should be supplied through `offsets_file`, using the long-form station-offset CSV format documented in `docs/station_2p5d_api.md`. Until that file is present, `ma2005_sl7_coefficients_sl7_real_offsets_available` remains `NOT_EVALUATED`.

Recommended `coefficient` values:

- `A33`
- `A35`
- `A53`
- `A55`
- `B33`
- `B35`
- `B53`
- `B55`

Acceptance target:

- current A33/A53 implementation-reproduction gate: <=5% relative error at `omega_bar=2.00` and `2.23`
- main diagonal added-mass/damping terms <=15% relative error
- important coupling terms <=30% relative error
- for nondimensional reference coefficients with absolute value below `0.02`, validation also reports and gates against a conservative near-zero absolute tolerance (`0.005` for diagonal terms, `0.01` for coupling terms) to avoid treating tiny absolute differences as unbounded relative errors

Validation behavior:

- If a digitized CSV is missing, `validate --benchmark all` reports `NOT_EVALUATED`.
- If the CSV is present and has the required columns, the validator computes prototype station-based coefficients and writes `ma2005_*_comparison.csv` and `figures/ma2005_*_comparison.png`.
- The validator also writes `ma2005_*_geometry_audit.csv`, which records analytic/surrogate/offsets provenance, derived LCG, pitch radius, trim, station count, and computed hydrostatic volume.
- The default `normalization=auto` follows the Ma 2005/Journee convention:
  - `Aij = aij / (rho displacement_volume L^r)`
  - `Bij = bij / (rho displacement_volume L^r) sqrt(L/g)`
  - `r` is the number of rotational DOFs in the coefficient index.
- Use `normalization=dimensional` if `reference_value` is in SI units.
- Comparison CSVs include `abs_error`, `rel_error`, `effective_abs_tolerance`, `gate_error_ratio`, and `error_metric`. A row passes only when `gate_error_ratio <= 1.0`.
- When hydro-model comparison is requested, coupling-variant sweep CSVs compare simple sign/transpose/pitch-axis/speed-term/gradient-term and PDSTRIP-step alternatives for `A35`, `A53`, `B35`, and `B53`. The validator also writes `ma2005_*_pdstrip_step_sign_audit.csv`, which compares the current station-convention PDSTRIP-step sign against the opposite accumulator-sign variant. These sweeps are diagnostic and do not change acceptance criteria.
- Hydro-model comparison also writes `ma2005_*_hydro_model_scale_audit.csv` and `ma2005_*_hydro_model_scale_audit_summary.csv`. These files report `computed/reference`, the multiplier required to hit the digitized Ma value, sign agreement, and whether the remaining gap looks like a uniform scale error or a frequency-shape error.
- Hydro-model comparison also writes `ma2005_*_coefficient_frequency_shape_audit.csv` and `ma2005_*_coefficient_frequency_shape_summary.csv`. These files compare each reference/computed coefficient curve across encounter frequency after best-fit scaling, reporting signed correlation, log-slope mismatch, and scaled normalized RMSE so a Ma miss can be classified as a scale issue or a real frequency-shape issue.
- Hydro-model comparison also writes `ma2005_*_normalization_sensitivity.csv` and `ma2005_*_normalization_sensitivity_summary.csv`. These files reuse each raw coefficient and compare displacement-volume, box-volume, parabolic-volume, length-cubed, and beam-based nondimensional denominators to test whether a convention mismatch could explain a Ma failure. They are informational only and do not change the hard gate.
- Hydro-model comparison also writes `ma2005_*_pitch_axis_sensitivity.csv` and `ma2005_*_pitch_axis_sensitivity_summary.csv` when selected rows include `A55` or `B55`. These files shift the pitch reference axis relative to LCG and amidship using the 2x2 heave/pitch matrix transform to test whether pitch diagonal misses are coordinate-reference or lever-arm issues. They are informational only and do not change the hard gate.
- With `--ma-panel-convergence`, the validator writes `ma2005_*_panel_convergence.csv` and `ma2005_*_panel_convergence_summary.csv` for pressure-transfer forward-speed models. These files rerun selected rows over multiple section-BEM free-surface/body-panel settings and report whether the remaining Ma gap is panel-converged or still mesh-sensitive.
- With `--ma-external-pdstrip-section-profiles`, the validator also writes `ma2005_*_external_section_frequency_shape_summary.csv`, which compares external PDSTRIP and local section-integral frequency slopes and ratio spread for B33/B35/B55 terms.
- The production candidate for Wigley III is the `matched_bie_station_sweep` route. Compact or surrogate providers remain separate diagnostic paths.
- A pass against `wigley_iii_coefficients_digitized.csv` is a Ma numerical-method reproduction pass, not an experimental-validation pass.
- The Journee 1992 file is the independent integrated experimental cross-audit source. It does not provide open-section radiation pressure, body-potential scale, or pitch-moment component data, so a discrepancy cannot be localized from that table alone.
- SL-7 remains a geometry-limited development benchmark until real offsets or a separately qualified replacement geometry are supplied.

Do not add placeholder numeric data here. Add only digitized or tabulated values with a source note.
