# Verifiable 2.5D Planing-Craft Seakeeping Target

## Goal

Upgrade the current runnable longitudinal planing-craft model into a verifiable complete 2.5D seakeeping program. Results are considered credible only when they pass numerical sanity checks, physical trend checks, and published benchmark comparisons.

## Reasonableness Checks

1. Numerical checks: no NaN/Inf values, positive total mass determinant, stable time integration, and small changes in RMS when the time step or spectrum resolution is refined.
2. Physical checks: trim and wetted length remain in planing-craft ranges, RAO peaks occur near linear modal frequencies, vertical accelerations generally increase with speed and wave height, and nonlinear runs report model-limit events instead of silently diverging.
3. Benchmark checks: eigenvalues, RAO curves, motion RMS, accelerations, and jump/non-jump classification are compared against published cases.

## Benchmark Gates

### Gate 1: Faltinsen Ch. 9 Prescribed State

Reference state:

- `beta=20 deg`
- `lambda_W=4`
- `trim=4 deg`
- `Fn_B=3`
- `lcg/B=2.13`
- `vcg/B=0.25`
- `M/(rho B^3)=1.28`
- `r55/B=1.3`

Acceptance target:

- Table 9.2 nondimensional eigenvalue real and imaginary parts: <=10% relative error for the main modes.
- Figures 9.34/9.35 RAO peak location: <=10% relative error.
- Figures 9.34/9.35 RAO peak magnitude: <=20% relative error after the curves are digitized.
- The Table 9.2 check writes `faltinsen_ch9_eigenvalues.csv`, with one row per mode and explicit real/frequency error plus per-mode status.

Implemented command:

```powershell
python -m planing_seakeeping validate --benchmark all --out outputs/validation
```

Digitized reference curves can be supplied with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation
```

The same prescribed state is also available as a normal run configuration:

```powershell
python -m planing_seakeeping run configs/faltinsen_ch9_prescribed.yml --out outputs/faltinsen_ch9_run
```

Current Faltinsen status:

- Table 9.2 eigenvalue checks: active.
- Figures 9.34/9.35 peak-location checks: active.
- Figures 9.34/9.35 digitized peak-amplitude and curve-shape checks: active using `benchmarks/faltinsen_ch9`.

### Gate 2: Fridsma / Katayama Regular-Wave Experiments

Acceptance target:

- Heave and pitch amplitude in non-jumping low-wave cases: <=25% relative error.
- CG and bow vertical acceleration: <=35% relative error.
- Clearly separated jumping/non-jumping cases classified correctly.

Implemented Katayama classification subset:

- Source-backed Table 1 / Fig. 7 cases are stored in `benchmarks/katayama/jumping_classification_digitized.csv`.
- Validation command computes the three published running conditions and classifies jumping by relative heave over transom draft.
- This is a screening gate for obvious jumping/non-jumping separation, not a full flight/re-entry model.
- A separate `katayama_regular_wave_qualitative_trends` gate records source-text Fig. 9/Fig. 10 trends in `katayama_qualitative_trends.csv`: low-speed response should increase with wavelength; high-speed response should show a peak; larger wave height should lower the peak and shift it to longer wavelength/period.
- The qualitative trend gate is intentionally not a substitute for digitized motion/amplitude curves. In the current linear RAO path, the wave-height-dependent trend rows are expected to fail and document the missing nonlinear amplitude-dependent mechanism.
- The same gate now writes `katayama_nonlinear_pilot_trends.csv`, a short RK4 nonlinear time-domain development probe around the high-speed peak. It evaluates medium-wave peak reduction/shift only on non-dryout points and separately reports large-wave dryout/model-limit risk. This pilot is useful evidence for solver development, not amplitude acceptance.
- The validation command compares Fridsma/Katayama motion and acceleration amplitude curves when their digitized CSV files are present; otherwise it emits NOT_EVALUATED rows.
- Fridsma configuration A development data are now active from Sun & Faltinsen 2010 parsed Fig. 4/Fig. 6 values; Katayama amplitude curves are still pending.
- Katayama pitch amplitude points can be supplied either as converted `pitch_rao_rad_per_m` or as the raw figure ordinate `pitch_rao_rad_per_wave_slope = theta/(K*zeta_w)`; the validator converts the latter using each row's wavelength and records `reference_source_column` in the comparison CSV.
- The same amplitude gate writes curve-shape audit files once a source-backed amplitude CSV is present. These compare reference and computed wavelength trends after best-fit scaling, so a failed gate can be classified as mostly a magnitude/tolerance issue or as a frequency-shape physics gap.

Required next data work:

- Digitize published heave, pitch, bow acceleration, and CG acceleration curves.
- Store the digitized data under a benchmark-data directory with source metadata.

### Gate 3: Complete Station-Based 2.5D Solver

Acceptance target:

- Read station sections and solve sectional radiation/diffraction terms rather than relying only on the current compact Faltinsen/Savitsky approximations.
- Validate added mass and damping against Ma 2005 Wigley III / SL-7 coefficient cases.
- Main diagonal coefficient errors: <=15%; important coupling terms: <=30%.
- Nondimensional near-zero Ma reference values are gated with a conservative absolute tolerance and reported through `gate_error_ratio`, while `rel_error` is still written for transparency.

Implemented status gate:

- `validate --benchmark all` writes `goal_gap_audit.csv`.
- The audit now evaluates the Wigley III Ma 2005 coefficient CSV and writes `ma2005_wigley_iii_coefficients_comparison.csv` plus a comparison plot. These rows are expected to fail with the current prototype coefficients.
- The same Ma 2005 audit can be run with `--ma-hydro-model section_bem` to compare the experimental section-BEM radiation path against the coefficient data. This is diagnostic and remains unvalidated until the Ma gates pass.
- The same audit can also be run with `--ma-hydro-model pdstrip_style` to compare a PDSTRIP-style sectional integral heave-radiation path against the coefficient data. This is also diagnostic and remains unvalidated until the Ma gates pass.
- The same audit can also be run with `--ma-hydro-model strip_2p5d_forward` to compare a PDSTRIP-like forward-speed station assembly. This path adds a section-velocity `W` map and a longitudinal-gradient term to the heave/pitch global operator, but remains diagnostic until the Ma gates pass.
- The same audit can also be run with `--ma-hydro-model strip_2p5d_pdstrip_step` to compare a bow-to-stern PDSTRIP-step station assembly that uses the same end-difference form as the pressure-gradient audit. This is diagnostic and remains unvalidated until the Ma gates pass.
- The same audit can also be run with `--ma-hydro-model pressure_transfer_forward` or `pressure_transfer_pdstrip_step` to derive sectional heave-radiation coefficients from body-panel pressure transfers before using the forward-speed or PDSTRIP-step station assembly. These paths make the pressure-to-operator route selectable for Ma 2005 triage; they remain diagnostic until the coefficient gates pass.
- The same audit can also be run with `--ma-hydro-model pressure_transfer_pdstrip_damping_forward` or `pressure_transfer_pdstrip_damping_pdstrip_step` to keep pressure-transfer sectional added mass but use `pdstrip_style` sectional damping. These paths are B35/B53 frequency-shape probes and remain diagnostic until the coefficient gates pass.
- The same audit can also be run with `--ma-hydro-model hybrid_forward_coupling` to keep the prototype diagonal terms while replacing only heave/pitch coupling terms with the forward-speed assembly. This is a diagnostic split, not an accepted hydrodynamic model.
- The same audit can also be run with `--ma-hydro-model hybrid_pressure_damping_coupling` to keep prototype diagonals, use forward-speed `A35/A53`, and use pressure-transfer PDSTRIP-step `B35/B53`. This isolates the highest-priority damping-coupling blockers and remains diagnostic until the Ma gates pass.
- The same audit can also be run with `--ma-hydro-model external_pdstrip_sections`, `external_pdstrip_forward`, or `external_pdstrip_pdstrip_step` to compile/run the local external PDSTRIP section solver for the Ma station hull, assemble zero-speed 6DOF matrices, or route external heave section radiation through the existing forward-speed station assemblies. These are opt-in diagnostics; they still lack the validated forward-speed pressure-gradient/diffraction mapping required for Ma acceptance.
- The Ma audit writes `ma2005_*_geometry_audit.csv` before coefficient comparison. Wigley III is treated as an analytic Ma Table 1 hull. SL-7 uses Ma 2005 Table 2 main particulars, including `LCG aft of amidship=11.7 m` converted to `lcg_from_transom_m=122.5 m`, `trim_by_stern_m=0.043`, and `pitch_radius_gyration_m=0.21 LBP`; without a source-backed `offsets_file`, SL-7 geometry remains `NOT_EVALUATED`.
- The optional `--ma-compare-hydro-models` switch writes side-by-side `prototype` / `section_bem` / `pdstrip_style` / `strip_2p5d_forward` / `strip_2p5d_pdstrip_step` / `pressure_transfer_forward` / `pressure_transfer_pdstrip_step` / `pressure_transfer_pdstrip_damping_forward` / `pressure_transfer_pdstrip_damping_pdstrip_step` / `hybrid_forward_coupling` / `hybrid_pressure_damping_coupling` coefficient diagnostics without changing the pass/fail gate. Use it to identify whether the next section-solver, pressure-transfer, or station-assembly change improves the right Ma 2005 coefficients.
- With `--ma-compare-hydro-models`, the audit also writes `ma2005_*_hydro_model_gap_summary.csv`, `ma2005_*_hydro_model_blocker_ranking.csv`, `ma2005_*_hydro_model_conflict_summary.csv`, `ma2005_*_hydro_model_scale_audit.csv`, `ma2005_*_hydro_model_scale_audit_summary.csv`, `ma2005_*_coefficient_frequency_shape_audit.csv`, `ma2005_*_coefficient_frequency_shape_summary.csv`, `ma2005_*_normalization_sensitivity.csv`, `ma2005_*_normalization_sensitivity_summary.csv`, `ma2005_*_pitch_axis_sensitivity.csv`, `ma2005_*_pitch_axis_sensitivity_summary.csv`, `ma2005_*_pdstrip_step_sign_audit.csv`, and matching `validation_report.md` sections. These name the best current diagnostic model, list the remaining blocking coefficients, rank coefficient-level blockers by remaining gate gap, report whether row-wise best models split by frequency/model family, quantify the multiplier needed to reach each Ma reference coefficient, test whether the reference-vs-computed coefficient curve shape survives best-fit scaling, test whether alternative nondimensional coefficient conventions could explain the mismatch, test whether `A55/B55` failures are sensitive to pitch-reference-axis shifts, classify uniform-scale versus frequency-shape gaps, record whether coupling rows support the current PDSTRIP-step station sign or the opposite accumulator-sign alternative, and keep the Ma gate failed until the full comparison actually passes.
- With `--ma-panel-convergence`, the audit writes `ma2005_*_panel_convergence.csv` and `ma2005_*_panel_convergence_summary.csv`. These rerun selected Ma rows across section-BEM panel refinements for pressure-transfer forward-speed models, so a failed Ma coefficient can be tagged as panel-converged or still mesh-sensitive before the next 2.5D formulation change.
- With `--ma-external-pdstrip-section-profiles`, the audit also writes `ma2005_*_external_section_frequency_shape_summary.csv`, comparing external PDSTRIP and local section-integral frequency slopes and ratio spread for B33/B35/B55 terms before vessel-level Ma coupling errors are interpreted.
- Add `--ma-compare-external-pdstrip` to include `external_pdstrip_sections`, `external_pdstrip_forward`, and `external_pdstrip_pdstrip_step` in the side-by-side hydro-model diagnostics.
- Add `--ma-coupling-station-contributions` to write the slower `ma2005_*_coupling_station_contributions.csv`, `ma2005_*_coupling_station_contribution_summary.csv`, and matching figures for station-level longitudinal `A33/B33/A35/B35/A53/B53/A55/B55` pressure-transfer and force-integrated contribution evidence. The summary compares each source/operator total with its Ma row and reports required multiplier, cancellation ratio, and absolute-contribution centroid. Use `--ma-compare-coefficients` and `--ma-compare-row-limit` for focused probes.
- Add `--ma-compare-coefficients A33 B33` and/or `--ma-compare-row-limit N` to run a small optional diagnostic subset, especially when including the slow external PDSTRIP adapter. These filters do not change the hard Ma 2005 comparison gate; `ma2005_*_comparison.csv` still uses the full dataset.
- With `--ma-compare-hydro-models`, the audit also writes a forward-speed coupling variant sweep for `A35/A53/B35/B53`. It scans simple sign, transpose, pitch-axis, speed-term, gradient-term, and PDSTRIP-step variants and is informational only.
- SL-7 digitized coefficients are now active using development digitization from the local parsed paper. They are expected to fail with the current surrogate-hull prototype until a validated boundary-integral section solver and better SL-7 offsets are connected.
- The audit also reports `experimental_pressure_gradient_end_term_diagnostic_available` so the pressure-gradient/end-term wiring remains visible as an experimental capability rather than an accepted Ma 2005 result.
- The audit reports the station-based solver as NOT_EVALUATED while `planing_seakeeping/station_2p5d.py` is only `frequency_forward_speed_prototype_not_validated`.
- The prototype can read hard-chine station files and assemble frequency-dependent 6DOF strip matrices/RAOs with a forward-speed heave/pitch coupling channel.
- An experimental `section_bem` module now solves a 2D free-surface source-panel heave-radiation problem, a zero-speed sway/heave/roll radiation-matrix audit, body-panel radiation/diffraction pressure-transfer diagnostics, pressure-based main-radiation and PDSTRIP-step pressure-gradient/end-term station-operator audits, and fixed-section incident/diffraction excitation. It can be selected in the station prototype CLI, but it is not yet the validated Ma 2005 matched boundary-integral 2.5D solver.
- A `pdstrip_style` diagnostic path now ports PDSTRIP-like panel-integral source influence coefficients for sectional heave radiation. Latest local diagnostics show it still fails Ma 2005 overall; use it to isolate sectional-radiation behavior from the global station assembly.
- A `strip_2p5d_forward` diagnostic path now uses the PDSTRIP-style sectional coefficients with a continuous-gradient forward-speed station assembly. A `strip_2p5d_pdstrip_step` diagnostic path exposes the bow-to-stern PDSTRIP-step end-term assembly as a selectable Ma hydro model. Latest local diagnostics show both forward-speed assembly paths improve some coupling trends relative to `pdstrip_style`, but still remain far below acceptance.
- A `pressure_transfer_forward` diagnostic path and a `pressure_transfer_pdstrip_step` diagnostic path now use body-panel pressure-transfer-derived sectional coefficients with the same two forward-speed station assemblies. Latest `outputs/validation_current` diagnostics show both pressure-transfer paths are finite and visible in Ma 2005 hydro-model comparisons: Wigley III is 16/55 PASS and SL-7 is 0/48 PASS. This is a pressure-path audit rather than a validation fix.
- `pressure_transfer_pdstrip_damping_forward` and `pressure_transfer_pdstrip_damping_pdstrip_step` now keep pressure-transfer-derived sectional added mass but use `pdstrip_style` sectional damping. They test whether the B35/B53 coupling blocker follows damping frequency shape; their status remains diagnostic/not validated.
- Focused probes at `outputs/validation_ma_b35_pdstrip_damping_probe` and `outputs/validation_ma_b35_b53_pdstrip_damping_probe` show the path is only partial evidence: Wigley III B35 improves to the current best diagnostic but still has 1/3 PASS, while Wigley III B53 ties the old pressure-transfer path at 4/8 PASS; SL-7 B35/B53 remain much worse than the best non-pressure-transfer diagnostics.
- A `hybrid_forward_coupling` diagnostic path now isolates diagonal coefficient behavior from heave/pitch coupling behavior. Latest local diagnostics preserve prototype diagonal passes but still fail coupling acceptance, especially `A35/B35`.
- A `hybrid_pressure_damping_coupling` diagnostic path now isolates pressure-transfer damping couplings by preserving prototype diagonals, keeping forward-speed added-mass couplings, and replacing only `B35/B53` with pressure-transfer PDSTRIP-step damping couplings.

## Current Status

The repository now has automated Faltinsen Ch. 9 and Katayama Fig. 7 validation entry points. It deliberately reports failing and not-yet-evaluated rows instead of smoothing over missing reference data. That makes the present model useful as a development baseline, but not yet a fully validated 2.5D solver.

The `benchmarks` directory now defines the expected data files for Faltinsen, Fridsma, Katayama, and Ma 2005. It contains source-backed Faltinsen RAO points, source-backed Katayama classification cases, Fridsma configuration A development amplitude points, Ma 2005 development coefficient digitizations, and templates for remaining amplitude datasets.

Fridsma configuration A rows now apply the source-backed prescribed running
state from Sun & Faltinsen 2010 (`trim=4 deg`, `lambda_W=3.6`). The validator
therefore reports prescribed-state application as a PASS and treats the
calm-force residual as diagnostic only; the hard Fridsma gate is decided by the
heave, pitch, CG-acceleration, and bow-acceleration amplitude rows. The
comparison CSV also includes time-domain diagnostic values, errors, statuses,
dryout-risk flags, and impact-acceleration risk flags so the regular-wave
response can be inspected without weakening the published-reference tolerances.
The validator now also writes `fridsma_regular_wave_amplitudes_response_model_comparison.csv`
and `fridsma_regular_wave_amplitudes_response_model_summary.csv`, comparing the
frequency-domain RAO, linear time-series reconstruction, and short nonlinear
time-domain response path against the same points. These diagnostics are for
solver triage and do not change the hard Fridsma 25%/35% amplitude tolerances.
It also writes `fridsma_regular_wave_amplitudes_shape_audit.csv` and
`fridsma_regular_wave_amplitudes_shape_summary.csv`, which test whether the
computed curve has the same wavelength trend as the reference after best-fit
scaling. This keeps the reasonableness judgment explicit: a curve with the
right shape but wrong scale asks for a different fix than a curve whose peak,
slope, or sign changes are in the wrong place.

The validation command also writes `sanity_checks.csv`, which currently checks regular-wave time-step convergence, irregular-wave spectral-component convergence, small-wave height linearity, explicit large-wave model-limit reporting, finite RAOs, mass/restoring-matrix positivity, solved-equilibrium residuals, trim range, reported linear-stability/porpoising margin, and the expected increase of peak bow-acceleration RAO with speed for a representative head-sea sweep. The spectrum check writes `sanity_spectrum_convergence.csv`, with each RMS metric compared between 64 and 128 irregular-wave components. The wave-height check writes `sanity_wave_height_response.csv`, comparing H=0.005/0.01/0.02 m RMS ratios against linear scaling and recording dryout/impact/integration-limit flags for larger waves. The matrix/equilibrium check writes `sanity_matrix_equilibrium.csv`, with per-speed total-mass eigenvalues, restoring eigenvalues, determinant, linear-stability eigenvalue real part, and normalized heave/pitch calm-force residuals. Positive maximum real eigenvalue parts are reported explicitly as a high-speed linearized porpoising/divergence risk instead of being hidden inside otherwise finite response curves.

The validation command also writes `section_bem_convergence.csv`, `section_bem_body_panel_convergence.csv`, `section_bem_excitation_sanity.csv`, `section_bem_multimode_radiation_sanity.csv`, `section_bem_pressure_transfer_sanity.csv`, `forward_speed_pressure_transfer_sanity.csv`, `forward_speed_pressure_gradient_sanity.csv`, and `section_bem_numerical_sanity.csv` for the experimental 2D free-surface source-panel section solver. These files check free-surface-panel refinement, body-panel refinement, fixed-section incident/diffraction excitation, multi-mode radiation matrix consistency, pressure-transfer integral closure, pressure-based forward-speed main-radiation reconstruction, pressure-based PDSTRIP-step pressure-gradient/end-term reconstruction, residual norm, and matrix conditioning. The latest local run at `outputs/validation_current` reports this group as 25/25 PASS; that supports numerical sanity of the development BEM path, not full Ma 2005 acceptance.

For Ma 2005 solver triage, a useful diagnostic command is:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_pdstrip_style --ma-hydro-model pdstrip_style --ma-bem-free-surface-panels 10 --ma-bem-body-panels 16 --ma-compare-hydro-models
```

The latest local run still reports `ma2005_wigley_iii_coefficients=FAIL`; `pdstrip_style` improved some damping-side diagnostics relative to the compact collocation BEM, but did not fix A33/A55 or the heave-pitch coupling coefficients. That keeps the full 2.5D goal open.

The forward-speed station-assembly diagnostic can be run with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_strip_2p5d_forward --ma-hydro-model strip_2p5d_forward --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12 --ma-compare-hydro-models
```

The PDSTRIP-step variant can be run with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_pdstrip_step_forward --ma-hydro-model strip_2p5d_pdstrip_step --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12
```

The pressure-transfer variant can be run with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_pressure_transfer --ma-hydro-model pressure_transfer_forward --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

Use `--ma-hydro-model pressure_transfer_pdstrip_step` to route the pressure-derived section coefficients through the bow-to-stern PDSTRIP-step assembly. Use `pressure_transfer_pdstrip_damping_forward` or `pressure_transfer_pdstrip_damping_pdstrip_step` for the shape-matched damping diagnostic.

The station-level longitudinal contribution probe can be run with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_station_contrib_probe --ma-compare-hydro-models --ma-coupling-station-contributions --ma-compare-coefficients B35 B55 --ma-compare-row-limit 1 --ma-bem-free-surface-panels 3 --ma-bem-body-panels 8
```

The latest local runs still report `ma2005_wigley_iii_coefficients=FAIL`. In `outputs/validation_compare_pdstrip_step`, `strip_2p5d_forward` and `strip_2p5d_pdstrip_step` both pass 17/55 side-by-side Ma rows. The step form slightly improves `B53` and slightly worsens `A53`, while both paths fail the diagonal coefficients. Treat this as evidence that the remaining blocker is the sectional radiation/pressure solution, not just the continuous-vs-step assembly choice.

The hybrid coupling-isolation diagnostic can be run with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_hybrid_forward_coupling --ma-hydro-model hybrid_forward_coupling --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12 --ma-compare-hydro-models
```

The focused pressure damping-coupling diagnostic can be run with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_hybrid_pressure_damping_coupling --ma-hydro-model hybrid_pressure_damping_coupling --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12 --ma-compare-hydro-models
```

The external PDSTRIP section-radiation adapter can be run explicitly with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_external_pdstrip_sections --ma-hydro-model external_pdstrip_sections
```

For faster external-PDSTRIP triage without changing acceptance gates:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_external_subset --ma-compare-hydro-models --ma-compare-external-pdstrip --ma-compare-coefficients A33 B33 --ma-compare-row-limit 2
```

Use a persistent cache when iterating on the external reference path:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_external_cached --ma-compare-hydro-models --ma-compare-external-pdstrip --ma-compare-coefficients A33 --ma-compare-row-limit 1 --ma-external-pdstrip-cache-dir outputs/pdstrip_ma_cache
```

Latest local subset evidence now includes eleven in-package models plus `external_pdstrip_sections`, `external_pdstrip_forward`, and `external_pdstrip_pdstrip_step` when external PDSTRIP is enabled. The external adapter filters zero-area Wigley end sections, runs the Fortran PDSTRIP path on 39 active sections, writes/reuses the cached `sectionresults`, and returns finite A33 values. The external forward A33 row still fails by overprediction (`1.3869` vs reference `1.0`). `outputs/validation_external_forward_b35` shows that the local `strip_2p5d_forward` B35 single point passes (`0.0949` vs reference `0.13`), while `external_pdstrip_forward` overpredicts (`0.2085`). The hard `ma2005_wigley_iii_coefficients_comparison.csv` remains the full 55-row dataset with 32 PASS / 26 FAIL.

Per-station A33 profile evidence can be generated with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_external_profiles_a33 --ma-compare-hydro-models --ma-compare-external-pdstrip --ma-external-pdstrip-section-profiles --ma-compare-coefficients A33 --ma-compare-row-limit 1 --ma-external-pdstrip-cache-dir outputs/pdstrip_ma_cache --ma-bem-free-surface-panels 3 --ma-bem-body-panels 8
```

The latest local profile writes both `ma2005_wigley_iii_coefficients_external_section_profiles.csv` and `ma2005_wigley_iii_coefficients_external_section_profile_summary.csv`. It shows the endpoint-closure weight correction is only `0.075 m` over `2.85 m` active-only weight, while integrated raw A33 contributions are `110.88` for external PDSTRIP, `26.33` for local collocation, and `14.15` for local `pdstrip_style`. This means the A33 disagreement is already present in the heave section-radiation/integration layer; it is not explained by endpoint weighting, final Ma normalization, or forward-speed coupling alone.

The latest Fridsma prescribed-state run at `outputs/validation_current` reports `fridsma_regular_wave_amplitudes=FAIL` with 15 PASS / 12 FAIL. The 20 direct amplitude comparisons are 9 PASS / 11 FAIL, and the aggregate max-error row points to `figures/fridsma_regular_wave_amplitudes_comparison.png`; the remaining mismatch is now tied to response amplitudes rather than to reconstructing the calm-water attitude.

The latest residual-summary probe at `outputs/validation_residual_summary_probe` writes `fridsma_regular_wave_amplitudes_residual_summary.csv`. It confirms the Fridsma failure is not one uniform scale error: short waves are underpredicted, mid-wave heave/pitch are overpredicted near resonance, and CG/bow accelerations are generally underpredicted. This diagnostic is informational only, but it makes the next amplitude-model work traceable by wavelength band and metric.

The paired shape-summary probe writes `fridsma_regular_wave_amplitudes_shape_summary.csv`. It adds a second view of the same failure by asking whether the curve shape survives after the best possible constant rescaling. That distinction matters because a pure scale mismatch can come from wave-height convention, nondimensionalization, or coordinate conversion, while a frequency-shape mismatch usually means the excitation, radiation, restoring, wetted-surface, or impact-acceleration physics is still incomplete.

The latest comprehensive local validation run at `outputs/validation_current` still reports `ma2005_wigley_iii_coefficients=FAIL` and `ma2005_sl7_coefficients=FAIL`. The geometry audit makes the SL-7 limitation explicit: the source-backed Table 2 LCG is now used, but real numeric station offsets are still missing. The gap summaries identify `hybrid_forward_coupling` as the best current diagnostic model, but still only 39/55 PASS for Wigley III and 11/48 PASS for SL-7. The blocker-ranking tables identify Wigley `B35/B53` as the highest-priority damping-coupling evidence, where pressure-transfer models are currently closest, while SL-7 remains dominated by geometry-sensitive `A35/A55/A53` blockers. The full validation summary is 120 PASS / 77 FAIL / 4 NOT_EVALUATED / 24 INFO, so the next technical target is still a validated Ma/PDSTRIP-style sectional pressure solution and real SL-7 offsets before claiming a complete 2.5D solver.

Latest focused hybrid damping-coupling run:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_hybrid_pressure_damping_model --ma-hydro-model hybrid_pressure_damping_coupling --ma-bem-free-surface-panels 3 --ma-bem-body-panels 8
```

This remains a failed validation run, but it is useful evidence: the global total becomes 129 PASS / 68 FAIL / 4 NOT_EVALUATED / 17 INFO. Wigley III improves to 42 PASS / 16 FAIL, while SL-7 remains 11 PASS / 40 FAIL plus one real-offsets `NOT_EVALUATED`. The B35/B53 subset runs show `hybrid_pressure_damping_coupling` follows the pressure-transfer damping values: for the first Wigley B35 point it gives `0.1254` versus reference `0.13` with gate ratio `0.117`, and for the first Wigley B53 point it gives `-0.1279` versus `-0.1` with gate ratio `0.929`. This confirms the pressure damping route is a real blocker-reduction path for Wigley coupling terms, not a complete solver fix.

Latest station-contribution diagnostic extension:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_station_b55_probe --ma-compare-hydro-models --ma-coupling-station-contributions --ma-compare-coefficients B55 --ma-compare-row-limit 1 --ma-bem-free-surface-panels 3 --ma-bem-body-panels 8
```

This run is also intentionally failed at the global gate, but it now writes `ma2005_wigley_iii_coefficients_coupling_station_contributions.csv` and `ma2005_wigley_iii_coefficients_coupling_station_contribution_summary.csv`. The long file contains force-collocation, force-`pdstrip_style`, pressure-raw, and pressure-clipped sources, each under continuous-gradient and PDSTRIP-step assemblies. The summary file turns those station rows into Ma-row totals with required multipliers, cancellation ratios, and contribution centroids, making the next Ma 2005 blocker audit station-local rather than just coefficient-level.

The pitch-axis sensitivity probe can be run with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_ma_b55_pitch_axis_probe --ma-compare-hydro-models --ma-compare-coefficients B55 --ma-bem-free-surface-panels 3 --ma-bem-body-panels 8
```

The latest probe shows Wigley III `B55` is not explained by a simple pitch-axis shift: the best small shift changes the median gate from `0.8587` to `0.8560` and still leaves 3/6 PASS. SL-7 `B55` benefits from aft axis shifts but remains incomplete, so real SL-7 offsets and sectional radiation/damping remain the technical target.

The validation command also writes `validation_status_by_benchmark.csv`, which groups the detailed rows by benchmark. Use that file as the first-pass reasonableness answer: a passing Faltinsen gate supports the implemented head-sea heave/pitch model, a passing Katayama classification gate supports the jump-risk screen, a failing Fridsma amplitude gate identifies planing-craft motion/amplitude mismatch, and failing Ma 2005 rows identify the still-unvalidated complete station-based 2.5D coefficient solver.

The validation command also writes `goal_gap_audit.csv`, which deliberately keeps remaining full-goal requirements visible even when the already-implemented benchmark subset passes. A run with NOT_EVALUATED rows is therefore not complete validation; it is an honest status report.

## External PDSTRIP Smoke

The repository can now compile and run the local open-source PDSTRIP source as an optional external reference diagnostic:

```powershell
python -m planing_seakeeping pdstrip-smoke --out outputs/pdstrip_external_cli
```

External PDSTRIP section hydrodynamics can now also be run from any station-hull
YAML/JSON file that the package can load:

```powershell
python -m planing_seakeeping pdstrip-station-sections configs/example_station_hull.yml --out outputs/pdstrip_station_sections_example --compare-section-bem --bem-free-surface-panels 4 --bem-body-panels 8 --omega 1.0
```

An existing PDSTRIP `sectionresults` file can also be converted to a long-form
coefficient table:

```powershell
python -m planing_seakeeping pdstrip-sectionresults outputs/pdstrip_external_cli/pdstrip_external_smoke/sectionresults --out outputs/pdstrip_sectionresults_parse
```

The same external section coefficients can be compared directly against the
local compact section-BEM solver on matching `geomet.out` sections:

```powershell
python -m planing_seakeeping pdstrip-compare-section-bem outputs/pdstrip_external_cli/pdstrip_external_smoke/sectionresults outputs/pdstrip_external_cli/pdstrip_external_smoke/geomet.out --out outputs/pdstrip_section_bem_compare --frequency-indices 1 26 52 --bem-free-surface-panels 4 --bem-body-panels 8
```

or as part of the validation summary:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_with_pdstrip_external --pdstrip-external-smoke
```

This generated case uses explicit full V sections because the bundled PDSTRIP example's symmetric half-sections trigger a section-suitability stop with the current compiler. The latest local smoke run reports `pdstrip_external_smoke=PASS`, with `compile=0`, `run=0`, and 260/260 section-frequency blocks in `sectionresults`. The parser infers 5 sections and 52 frequencies, recovers `A_complex = radiation_force / omega**2`, and writes radiation, diffraction, and Froude-Krylov rows. This proves PDSTRIP is available as a runnable and parseable external strip-theory reference path. It is still not Ma 2005 validation until its coefficients or pressure functions are mapped into the Ma benchmark comparison and pass the gates.

The latest local `pdstrip-compare-section-bem` run over stations 1-5 and
frequency indices 1/26/52 writes 135 matrix-entry comparisons. It shows the
current compact section-BEM still underpredicts external PDSTRIP added-mass
diagonals on the generated V sections, so remaining Ma 2005 error is likely not
only a forward-speed station-assembly issue.

The latest local station-hull external run for `configs/example_station_hull.yml`
reports `PASS`, `sections=6/6`, `nfre=52`, and 312 section-frequency blocks.
The parsed output has 7488 radiation/excitation rows plus an optional 162-row
section-BEM comparison. It also writes zero-speed `pdstrip_external_added_mass_6dof.csv`
and `pdstrip_external_damping_6dof.csv` assembled by integrating the external
sway/heave/roll section radiation matrices along the station hull. This closes
the infrastructure gap between package station geometry, external PDSTRIP
section coefficients, and package-level 6DOF matrix output; the remaining step
is adding the validated forward-speed pressure-gradient/diffraction mapping and
testing it against Ma 2005 acceptance.
