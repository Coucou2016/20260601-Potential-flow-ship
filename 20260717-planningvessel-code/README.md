# Planing Seakeeping

2.5D/Savitsky-Faltinsen based motion predictor for a high-speed planing craft in waves.

The first version is intentionally focused: it solves the longitudinal planing-craft problem, especially heave, pitch, and vertical accelerations, then exports a unified 6DOF table. In head sea, surge/sway/roll/yaw are emitted as zero placeholders by symmetry and by model scope.

## Run The Example

```powershell
cd D:\Projects\20260601-Potential-flow-ship\20260717-planningvessel-code
python -m planing_seakeeping run configs\example_planing.yml --out outputs\example
```

Main outputs:

- `summary.csv`: speed-by-speed equilibrium, stability, and RMS metrics.
- `rao.csv`: frequency-domain heave, pitch, bow-motion, and acceleration RAOs.
- `timeseries_regular_speed_*.csv`: regular-wave 6DOF time histories.
- `timeseries_irregular_speed_*.csv`: irregular-sea 6DOF time histories.
- `figures/*.png`: RAO, RMS, and time-series plots.
- `run_report.md`: concise method and run summary.

## Run Validation

The concrete target for judging whether results are physically reasonable and whether the solver has reached a complete verifiable 2.5D implementation is documented in [verifiable_2p5d_concrete_goal.md](docs/verifiable_2p5d_concrete_goal.md), with longer supporting notes in [complete_2p5d_verification_goal.md](docs/complete_2p5d_verification_goal.md). A shorter acceptance card is available in [verification_acceptance_target.md](docs/verification_acceptance_target.md).

```powershell
python -m planing_seakeeping validate --benchmark all --out outputs\validation
```

Use a custom directory of digitized reference curves:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation
```

Run the Ma 2005 coefficient comparison through the experimental section-BEM path:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_bem --ma-hydro-model section_bem --ma-bem-free-surface-panels 4
```

Run the same Ma 2005 comparison through the PDSTRIP-style sectional integral diagnostic:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_pdstrip_style --ma-hydro-model pdstrip_style --ma-bem-free-surface-panels 10 --ma-bem-body-panels 16
```

Run the Ma 2005 comparison through the PDSTRIP-like forward-speed station-assembly diagnostic:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_strip_2p5d_forward --ma-hydro-model strip_2p5d_forward --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12
```

Run the Ma 2005 comparison through the bow-to-stern PDSTRIP-step station-assembly diagnostic:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_pdstrip_step_forward --ma-hydro-model strip_2p5d_pdstrip_step --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12
```

Run the Ma 2005 comparison through the body-panel pressure-transfer forward-speed diagnostic:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_pressure_transfer --ma-hydro-model pressure_transfer_forward --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

Use `--ma-hydro-model pressure_transfer_pdstrip_step` for the same pressure-derived section coefficients routed through the bow-to-stern PDSTRIP-step assembly. Use `pressure_transfer_pdstrip_damping_forward` or `pressure_transfer_pdstrip_damping_pdstrip_step` to keep the pressure-transfer added-mass channel but replace sectional damping with the local `pdstrip_style` section solver; those two paths are diagnostic probes for Ma `B35/B53` frequency-shape blockers, not validated hydrodynamic models.

Run the Ma 2005 comparison through the hybrid diagnostic that keeps prototype diagonal terms and uses forward-speed couplings:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_hybrid_forward_coupling --ma-hydro-model hybrid_forward_coupling --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12 --ma-compare-hydro-models
```

Run the Ma 2005 comparison through the hybrid damping-coupling diagnostic that keeps prototype diagonals, uses forward-speed added-mass couplings, and uses pressure-transfer damping couplings:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_hybrid_pressure_damping_coupling --ma-hydro-model hybrid_pressure_damping_coupling --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12 --ma-compare-hydro-models
```

This is a diagnostic comparison against the same Ma 2005 data. It does not mark the complete 2.5D solver validated unless the Ma gates and the explicit complete-solver gate pass.
Use `--ma-bem-body-panels N` to arclength-resample each section before the Ma section-BEM comparison.

Run the Ma 2005 comparison through the external PDSTRIP section-radiation adapter:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_external_pdstrip_sections --ma-hydro-model external_pdstrip_sections
```

This path compiles/runs the local PDSTRIP source for the Ma station hull and assembles zero-speed 6DOF matrices from the external section radiation data. It is slow and remains diagnostic because it does not include the validated forward-speed pressure-gradient/diffraction mapping needed for Ma 2005 acceptance.

Write side-by-side Ma 2005 diagnostics for the default station prototype, experimental section-BEM path, PDSTRIP-style sectional integral path, forward-speed station-assembly path, pressure-transfer path, and hybrid coupling paths:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_compare --ma-compare-hydro-models --ma-bem-free-surface-panels 4
```

This adds `ma2005_*_hydro_model_diagnostics.csv`, `ma2005_*_hydro_model_status.csv`, and `ma2005_*_hydro_model_status_by_coefficient.csv` without changing the benchmark gate criteria.
Add `--ma-compare-external-pdstrip` only when you also want the slow external PDSTRIP section adapter included in the side-by-side model sweep.

Run the local open-source PDSTRIP compile/run smoke diagnostic:

```powershell
python -m planing_seakeeping pdstrip-smoke --out outputs\pdstrip_external_cli
```

Run external PDSTRIP section hydrodynamics directly for a station-hull YAML/JSON file:

```powershell
python -m planing_seakeeping pdstrip-station-sections configs\example_station_hull.yml --out outputs\pdstrip_station_sections_example --compare-section-bem --bem-free-surface-panels 4 --bem-body-panels 8 --omega 1.0
```

Parse any existing PDSTRIP `sectionresults` file into long-form radiation and excitation coefficients:

```powershell
python -m planing_seakeeping pdstrip-sectionresults outputs\pdstrip_external_cli\pdstrip_external_smoke\sectionresults --out outputs\pdstrip_sectionresults_parse
```

Compare parsed external PDSTRIP section radiation matrices with the local compact section-BEM solver on the same geometry:

```powershell
python -m planing_seakeeping pdstrip-compare-section-bem outputs\pdstrip_external_cli\pdstrip_external_smoke\sectionresults outputs\pdstrip_external_cli\pdstrip_external_smoke\geomet.out --out outputs\pdstrip_section_bem_compare --frequency-indices 1 26 52 --bem-free-surface-panels 4 --bem-body-panels 8
```

Include that external-code smoke diagnostic in the validation summary:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_with_pdstrip_external --pdstrip-external-smoke
```

This compiles the local `early_stage_materials\code\potential_flow_seakeeping\pdstrip\pdstrip.f90`, runs a generated full-section V-hull section-hydrodynamics case, checks that `sectionresults` contains 260 section-frequency blocks, and writes parsed section radiation/excitation rows when the file is complete. A PASS here proves the external PDSTRIP reference path is runnable and parseable on this machine; it does not replace Ma 2005 coefficient acceptance.

The station-hull command writes a generated PDSTRIP `geomet.out`, the external `sectionresults`, a parsed `pdstrip_station_sectionresults.csv`, zero-speed 6DOF matrices assembled from external section radiation, and optionally `pdstrip_station_section_bem_comparison.csv`. This is the bridge needed before external PDSTRIP coefficients can be mapped into the Ma 2005 Wigley III / SL-7 gates.

Ma 2005 comparison CSVs report both traditional `rel_error` and gate-oriented `gate_error_ratio`. For nondimensional reference coefficients near zero, the gate uses a conservative absolute tolerance so tiny absolute differences are not turned into unbounded relative errors.

With `--ma-compare-hydro-models`, the validator also writes `ma2005_*_coupling_variant_sweep.csv`, `ma2005_*_coupling_variant_status.csv`, `ma2005_*_coupling_variant_status_by_coefficient.csv`, and `ma2005_*_pdstrip_step_sign_audit.csv`. These files scan forward-speed coupling sign, transpose, pitch-axis, speed-term, gradient-term, and PDSTRIP-step variants for `A35/A53/B35/B53`; the sign audit compares the current station convention with the opposite accumulator-sign alternative. They are diagnostics only.

Use `--ma-panel-convergence` to rerun selected Ma 2005 rows with multiple section-BEM panel resolutions for the pressure-transfer forward-speed models:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_ma_panel_convergence --ma-panel-convergence --ma-compare-coefficients B35 B53 --ma-compare-row-limit 3 --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

This writes `ma2005_*_panel_convergence.csv` and `ma2005_*_panel_convergence_summary.csv`. These files are numerical-resolution diagnostics only; they help decide whether a Ma miss is mesh-sensitive before treating it as a missing pressure/radiation/forward-speed formulation term.

Run the same Faltinsen prescribed running state through the normal predictor:

```powershell
python -m planing_seakeeping run configs\faltinsen_ch9_prescribed.yml --out outputs\faltinsen_ch9_run
```

Validation outputs:

- `validation_summary.csv`: pass/fail/not-evaluated checks against published-reference targets.
- `validation_status_by_benchmark.csv`: grouped status counts, so Faltinsen, Katayama, Fridsma, Ma 2005, and complete-2.5D gaps can be judged separately.
- `sanity_checks.csv`: numerical convergence and physical trend checks.
- `sanity_spectrum_convergence.csv`: per-RMS-metric spectral-component refinement check comparing 64 and 128 irregular-wave components.
- `sanity_wave_height_response.csv`: regular-wave height sweep checking small-wave linear scaling and explicit large-wave model-limit reporting.
- `sanity_matrix_equilibrium.csv`: per-speed total-mass/restoring eigenvalues, normalized equilibrium residuals, and linear-stability/porpoising margin for the numerical sanity gate.
- `section_bem_convergence.csv`: experimental section-BEM free-surface-panel convergence sweep for a representative section.
- `section_bem_body_panel_convergence.csv`: experimental section-BEM body-panel convergence sweep for a representative section.
- `section_bem_excitation_sanity.csv`: experimental fixed-section incident/diffraction excitation sanity case.
- `section_bem_multimode_radiation_sanity.csv`: experimental sway/heave/roll section-radiation matrix audit for one representative section.
- `section_bem_pressure_transfer_sanity.csv`: experimental body-panel radiation/diffraction pressure-transfer audit for one representative section.
- `forward_speed_pressure_transfer_sanity.csv`: pressure-transfer reconstruction of the forward-speed main-radiation station operator.
- `forward_speed_pressure_gradient_sanity.csv`: pressure-transfer reconstruction of the PDSTRIP-step pressure-gradient/end-term station operator.
- `pdstrip_external_smoke.csv`: optional local external PDSTRIP compile/run smoke checks when `--pdstrip-external-smoke` is supplied.
- `pdstrip_external_sectionresults.csv`: optional parsed external PDSTRIP section radiation, diffraction, and Froude-Krylov rows when `--pdstrip-external-smoke` succeeds.
- `pdstrip_external_sectionresults_conventions.csv`: optional source-backed notes for how PDSTRIP stores `sectionresults` radiation data, matrix orientation, coordinate basis, and damping sign convention.
- `pdstrip_section_bem_comparison.csv`: diagnostic output from `pdstrip-compare-section-bem`; useful for isolating whether Ma 2005 disagreement originates in the section radiation solver or the vessel-level 2.5D assembly.
- `pdstrip_station_sectionresults.csv`: parsed external PDSTRIP section coefficients for a user-supplied station hull from `pdstrip-station-sections`.
- `pdstrip_station_sectionresults_conventions.csv`: source-backed convention notes written beside station-hull external PDSTRIP section coefficients.
- `pdstrip_external_added_mass_6dof.csv` and `pdstrip_external_damping_6dof.csv`: zero-speed station 6DOF matrices assembled from external PDSTRIP section radiation.
- `ma2005_*_geometry_audit.csv`: geometry provenance for Ma 2005 coefficient rows, including analytic Wigley III geometry, SL-7 Table 2 LCG/trim/pitch-radius defaults, and whether a real `offsets_file` is present.
- `ma2005_*_external_section_profiles.csv`, `ma2005_*_external_section_profile_summary.csv`, and `ma2005_*_external_section_frequency_shape_summary.csv`: optional per-station external/local section-radiation profiles and section-integral frequency-shape diagnostics when `--ma-external-pdstrip-section-profiles` is supplied with Ma hydro-model diagnostics.
- `ma2005_*_hydro_model_gap_summary.csv`: optional best-diagnostic-model and blocking-coefficient summary when `--ma-compare-hydro-models` is supplied.
- `ma2005_*_pdstrip_step_sign_audit.csv`: optional evidence table for whether Ma coupling rows support the current PDSTRIP-step station sign or the opposite accumulator-sign variant.
- `ma2005_*_panel_convergence.csv` / `ma2005_*_panel_convergence_summary.csv`: optional pressure-transfer model sensitivity to section-BEM panel refinement when `--ma-panel-convergence` is supplied.
- `ma2005_*_hydro_model_blocker_ranking.csv`: optional coefficient-priority table ranking Ma 2005 blockers by best available diagnostic model, pressure-transfer behavior, and remaining gate gap.
- `ma2005_*_hydro_model_conflict_summary.csv`: optional row-wise best-model conflict table showing whether a single diagnostic path passes a coefficient, or whether different frequency rows prefer different model families.
- `ma2005_*_hydro_model_scale_audit.csv` and `ma2005_*_hydro_model_scale_audit_summary.csv`: optional required-scale and frequency-shape diagnostics showing `computed/reference`, sign agreement, and whether a failed coefficient needs a uniform magnitude fix or a frequency-dependent pressure/gradient fix.
- `ma2005_*_coefficient_frequency_shape_audit.csv` and `ma2005_*_coefficient_frequency_shape_summary.csv`: optional direct curve-shape diagnostics comparing reference and computed coefficient trends across encounter frequency using best-fit scaling, signed correlation, log-slope mismatch, and scaled normalized RMSE.
- `ma2005_*_normalization_sensitivity.csv` and `ma2005_*_normalization_sensitivity_summary.csv`: optional convention audit comparing the same raw coefficient against displacement-volume, box-volume, parabolic-volume, length-cubed, and beam-based nondimensional denominators.
- `ma2005_*_pitch_axis_sensitivity.csv` and `ma2005_*_pitch_axis_sensitivity_summary.csv`: optional `A55/B55` audit that shifts the pitch reference axis around LCG and amidship using `M' = T^T M T`, to test whether pitch damping/added-mass misses are coordinate-reference issues.
- `ma2005_*_coupling_station_contributions.csv`: slow optional station-by-station longitudinal `A33/B33/A35/B35/A53/B53/A55/B55` pressure-transfer and force-integrated contribution decomposition when `--ma-coupling-station-contributions` is supplied with hydro-model diagnostics.
- `ma2005_*_coupling_station_contribution_summary.csv`: source/operator totals from the station decomposition, compared with each Ma row and annotated with required multiplier, cancellation ratio, and absolute-contribution centroid along the hull.
- `section_bem_numerical_sanity.csv`: pass/fail summary for section-BEM convergence, excitation, residuals, and conditioning.
- `goal_gap_audit.csv`: explicit NOT_EVALUATED rows for full-goal requirements that still lack data or implementation.
- `faltinsen_ch9_eigenvalues.csv`: Faltinsen Table 9.2 prescribed-state nondimensional eigenvalue comparison, with real/frequency errors and per-mode status.
- `faltinsen_ch9_rao.csv`: computed Faltinsen Ch. 9 prescribed-state RAO data.
- `fridsma_regular_wave_amplitudes_residual_summary.csv`: metric- and wavelength-band residual diagnostics for the Fridsma amplitude gate; this explains failures but does not change acceptance.
- `fridsma_regular_wave_amplitudes_shape_audit.csv` and `fridsma_regular_wave_amplitudes_shape_summary.csv`: reference-vs-predicted curve-shape diagnostics for the Fridsma amplitude gate, using best-fit scaling, signed correlation, wavelength-slope mismatch, and normalized shape RMSE to separate simple magnitude gaps from frequency-shape gaps.
- `fridsma_regular_wave_amplitudes_response_model_comparison.csv`: frequency-domain, linear time-series, and short nonlinear time-domain response-model comparison against the same Fridsma points.
- `fridsma_regular_wave_amplitudes_response_model_summary.csv`: pass/fail, median-error, max-error, and model-limit counts by response model and metric.
- `katayama_regular_wave_amplitudes_residual_summary.csv`, `katayama_regular_wave_amplitudes_shape_audit.csv`, and `katayama_regular_wave_amplitudes_shape_summary.csv`: the same residual and curve-shape diagnostic formats for Katayama amplitude rows once source-backed digitized response data are present.
- `katayama_classification.csv`: computed Katayama Fig. 7 jumping/non-jumping screening cases when the benchmark CSV is present.
- `katayama_qualitative_trends.csv`: source-text-backed Katayama Fig. 9/Fig. 10 qualitative trend probe for low-speed wavelength monotonicity, high-speed peak behavior, and wave-height-dependent peak shift.
- `katayama_nonlinear_pilot_trends.csv`: short deterministic nonlinear RK4 pilot near the Katayama high-speed peak; it checks whether the nonlinear time-domain path starts to show peak reduction/shift before dryout.
- `ma2005_*_status_by_coefficient.csv`: coefficient-level Ma 2005 pass/fail counts when coefficient benchmarks are present.
- `figures/faltinsen_ch9_rao.png`: RAO curves with reference modal-frequency markers.
- `figures/fridsma_regular_wave_amplitudes_comparison.png`: Fridsma heave, pitch, CG-acceleration, and bow-acceleration comparison curves with failed-tolerance points marked.
- `figures/fridsma_regular_wave_amplitudes_response_model_comparison.png`: Fridsma model-comparison plot; red open markers identify model-limit/dryout/fallback cases.
- `figures/katayama_regular_wave_amplitudes_comparison.png`: Katayama amplitude comparison curves when a source-backed amplitude CSV is present.
- `figures/katayama_classification.png`: observed/predicted jumping classification map.
- `figures/katayama_qualitative_trends.png`: qualitative Katayama trend probe curves, explicitly marked as a model-limitation diagnostic rather than an amplitude validation replacement.
- `figures/katayama_nonlinear_pilot_trends.png`: high-speed nonlinear pilot curves; square markers indicate pilot cases where dryout/model-limit risk appears.
- `validation_report.md`: interpretation, current failures, and next benchmark data needed.

Benchmark data templates live under `benchmarks\`. The Faltinsen RAO amplitude checks activate automatically when these files are present:

- `benchmarks\faltinsen_ch9\fig_9_34_heave_rao_digitized.csv`
- `benchmarks\faltinsen_ch9\fig_9_35_pitch_rao_digitized.csv`

The Katayama classification gate uses:

- `benchmarks\katayama\jumping_classification_digitized.csv`

This gate checks clear jump/non-jump separation only. Fridsma configuration A heave, pitch, CG-acceleration, and bow-acceleration development data are now active through `benchmarks\fridsma\regular_wave_motion_digitized.csv`; the Fridsma rows use Sun & Faltinsen's source-backed prescribed running state `trim=4 deg`, `lambda_W=3.6`. Full Katayama motion-amplitude validation still needs digitized heave and pitch curves, with CG/bow acceleration treated as pending unless a source-backed acceleration dataset is added. Katayama pitch points can be entered either as converted `pitch_rao_rad_per_m` or as the raw figure ordinate `pitch_rao_rad_per_wave_slope = theta/(K*zeta_w)`; comparison CSVs record the actual `reference_source_column`. A motion-only Katayama response CSV activates heave/pitch comparison while keeping missing acceleration rows `NOT_EVALUATED`. The validator also writes a separate `katayama_qualitative_trends.csv` gate from source-text statements: low-speed motion should increase with wavelength, high-speed response should show a peak, and larger wave height should reduce the peak and shift it longer. This qualitative gate is expected to expose the current linear RAO model's missing amplitude-dependent nonlinear mechanism; it does not replace source-backed Fig. 9/Fig. 10 digitized amplitude data. A companion `katayama_nonlinear_pilot_trends.csv` uses a short fixed-step RK4 nonlinear time-domain probe around the high-speed peak. It is only a triage tool, but it records whether the current nonlinear path begins to recover medium-wave peak reduction/shift and whether large-wave cases are flagged as dryout/model-limit risks. Amplitude comparison CSVs also include `time_domain_value`, `time_domain_rel_error`, `time_domain_status`, `time_domain_dryout_risk_flag`, and `time_domain_impact_accel_risk_flag` diagnostic columns; these help inspect regular-wave time-domain behavior but do not relax the published-reference hard gate. Residual-summary CSVs group the same amplitude errors by metric and wavelength band so failed Fridsma/Katayama gates point to a concrete model-development target.

`validate --benchmark all` also reports full-goal gaps until they are closed:

- Katayama regular-wave motion and acceleration amplitude curves.
- Fridsma development digitization audit against the original report figures.
- Manual audit of the Ma 2005 Wigley III / SL-7 development digitizations against the original figure images.
- A validated station-based `planing_seakeeping/station_2p5d.py` solver API, plus real SL-7 offsets connected through `offsets_file`, for complete 2.5D radiation/diffraction validation.

Latest Fridsma check in `outputs\validation_current` reports `fridsma_regular_wave_amplitudes=FAIL` with 15 PASS and 12 FAIL rows. The direct amplitude comparisons are 9 PASS / 11 FAIL after applying the source-backed prescribed running state; the additional failing row is the aggregate max-error gate. The run now writes `figures/fridsma_regular_wave_amplitudes_comparison.png`, making the short-wave and bow-acceleration mismatches visible as part of the automatic validation evidence, with a dashed time-domain diagnostic curve beside the frequency-domain gate values. It also writes `fridsma_regular_wave_amplitudes_response_model_comparison.csv`, which shows whether the current frequency-domain, linear time-series, or short nonlinear time-domain response path is closer to each source point. This is intentional evidence for the next implementation target: the present compact longitudinal model is useful as a baseline, but it is not yet the complete 2D+t/2.5D pressure-integration solver needed to match the planing-craft amplitude experiments.

A focused residual-summary run at `outputs\validation_residual_summary_probe` writes `fridsma_regular_wave_amplitudes_residual_summary.csv`. It keeps the global validation failed, but turns the mismatch into a blocker profile: short waves are underpredicted, mid-wave heave/pitch are overpredicted near resonance, and CG/bow accelerations are generally too soft. This is the next solver-development target for the planing-craft amplitude gate.

The Wigley III and SL-7 parts of Ma 2005 are now active using development digitization from the local parsed paper. Because the station solver is still a prototype and SL-7 uses a surrogate hull until offsets are digitized, `validate --benchmark all` is expected to report hard failures for those rows until the boundary-integral section method and benchmark hull geometry are implemented. The SL-7 geometry audit now applies Ma 2005 Table 2 main particulars: `LCG aft of amidship=11.7 m` is converted to `lcg_from_transom_m=122.5 m`, `trim_by_stern_m=0.043`, and `pitch_radius_gyration_m=0.21 LBP`; it remains `NOT_EVALUATED` until a real SL-7 `offsets_file` is supplied.

The Ma 2005 audit can compare the default `prototype` station model, the experimental `section_bem` station model, the `pdstrip_style` sectional integral diagnostic, the `strip_2p5d_forward` continuous-gradient forward-speed station assembly, the `strip_2p5d_pdstrip_step` bow-to-stern PDSTRIP-step assembly, the `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, and `pressure_transfer_pdstrip_damping_pdstrip_step` body-panel pressure-transfer diagnostics, the `hybrid_forward_coupling` and `hybrid_pressure_damping_coupling` diagnostics, the explicit zero-speed `external_pdstrip_sections` adapter, or the `external_pdstrip_forward` / `external_pdstrip_pdstrip_step` forward-speed adapters through `--ma-hydro-model`. The comparison CSV records the selected `hydro_model` and `solver_status` for each row.

For solver-development triage, `--ma-compare-hydro-models` writes optional side-by-side diagnostics for `prototype`, `section_bem`, `pdstrip_style`, `strip_2p5d_forward`, `strip_2p5d_pdstrip_step`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, `hybrid_forward_coupling`, and `hybrid_pressure_damping_coupling` so the next boundary-integral or station-assembly upgrade can be judged coefficient by coefficient. It also writes `ma2005_*_hydro_model_gap_summary.csv`, `ma2005_*_hydro_model_blocker_ranking.csv`, `ma2005_*_hydro_model_conflict_summary.csv`, `ma2005_*_hydro_model_scale_audit.csv`, `ma2005_*_hydro_model_scale_audit_summary.csv`, `ma2005_*_coefficient_frequency_shape_audit.csv`, `ma2005_*_coefficient_frequency_shape_summary.csv`, `ma2005_*_normalization_sensitivity.csv`, `ma2005_*_normalization_sensitivity_summary.csv`, `ma2005_*_pitch_axis_sensitivity.csv`, `ma2005_*_pitch_axis_sensitivity_summary.csv`, `ma2005_*_pdstrip_step_sign_audit.csv`, and matching `validation_report.md` sections, which name the current best diagnostic model, the remaining blocking coefficients, whether row-wise best models split by frequency, the required multiplier to reach each reference value, whether the gap is a uniform scale problem or a frequency-shape problem, whether the reference-vs-computed coefficient curve shape survives best-fit scaling, whether alternative coefficient normalizations could explain the mismatch, whether `A55/B55` are sensitive to pitch-reference-axis shifts, and whether coupling rows support the current PDSTRIP-step sign convention. With `--ma-panel-convergence`, it reruns selected Ma rows at multiple section-BEM panel resolutions and reports whether remaining misses are panel-converged or panel-sensitive. With `--ma-coupling-station-contributions`, it additionally decomposes longitudinal `A33/B33/A35/B35/A53/B53/A55/B55` station contributions from force and pressure-transfer sources and writes a source/operator summary with Ma-row error, cancellation, and contribution-centroid diagnostics. These summaries are diagnostic only; they do not change the hard Ma gate.
Use `--ma-compare-external-pdstrip` with that switch to include `external_pdstrip_sections`, `external_pdstrip_forward`, and `external_pdstrip_pdstrip_step`; it is kept opt-in because it can launch the external Fortran reference path.
Use `--ma-coupling-station-contributions` with `--ma-compare-hydro-models` when you want the slower station-level longitudinal contribution decomposition and plots:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_station_contrib_probe --ma-compare-hydro-models --ma-coupling-station-contributions --ma-compare-coefficients B35 --ma-compare-row-limit 1 --ma-bem-free-surface-panels 3 --ma-bem-body-panels 8
```

For fast external-PDSTRIP triage, the optional side-by-side diagnostics can be filtered without weakening the hard Ma gate:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_external_subset --ma-compare-hydro-models --ma-compare-external-pdstrip --ma-compare-coefficients A33 B33 --ma-compare-row-limit 2
```

`--ma-compare-coefficients` and `--ma-compare-row-limit` apply only to the optional `ma2005_*_hydro_model_diagnostics.csv` and coupling-variant diagnostics. The main `ma2005_*_comparison.csv` files still use the full benchmark dataset and still decide the pass/fail gate.

Add a persistent cache when iterating on the external reference path:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_external_cached --ma-compare-hydro-models --ma-compare-external-pdstrip --ma-compare-coefficients A33 --ma-compare-row-limit 1 --ma-external-pdstrip-cache-dir outputs\pdstrip_ma_cache
```

`--ma-external-pdstrip-cache-dir` stores the generated `sectionresults`, `geomet.out`, `pdstrip.out`, and executable files under a hull-parameter hash. A later validation run with the same Ma hull parameters reuses parseable `sectionresults` instead of recompiling/rerunning PDSTRIP.

Latest local subset checks with the current model list write 14 A33 diagnostic rows when external PDSTRIP is included: eleven in-package models plus the three external adapters. The external adapter skips zero-area Wigley end sections before calling PDSTRIP, so the real Fortran path produces 39 sections and returns finite A33 diagnostics, but `external_pdstrip_forward` still overpredicts A33 (`1.3869` vs reference `1.0`). `outputs\validation_external_forward_b35` shows the B35 coupling single point: local `strip_2p5d_forward` passes (`0.0949` vs reference `0.13`), while `external_pdstrip_forward` overpredicts (`0.2085`). The current comprehensive run at `outputs\validation_current` keeps the full `ma2005_wigley_iii_coefficients_comparison.csv` hard gate at 32 PASS / 26 FAIL, reports `ma2005_sl7_coefficients` as 12 PASS / 39 FAIL plus one `NOT_EVALUATED` real-offsets row after applying the source-backed SL-7 LCG, and reports the full validation total as 120 PASS / 77 FAIL / 4 NOT_EVALUATED / 24 INFO.

`--ma-external-pdstrip-section-profiles` writes per-station section profiles, an integrated summary, and an external/local section-integral frequency-shape summary for the selected Ma rows. In the latest A33 profile run at `outputs\validation_external_profiles_a33`, the full-hull endpoint-closure weight correction is only `0.075 m` over `2.85 m` active-only weight, and the integrated raw A33 contributions are `110.88` for external PDSTRIP, `26.33` for local collocation, and `14.15` for local `pdstrip_style`. The external/local gap is therefore already present at the section-radiation integration level, before final nondimensional Ma normalization or forward-speed coupling terms are considered; endpoint weighting does not explain the A33 mismatch. The frequency-shape summary adds log-slope and ratio-spread diagnostics for B33/B35/B55 section-integral terms, which helps decide whether B35/B53 misses are traceable to local section-radiation shape rather than a single vessel-level scale.

The current `pdstrip_style` diagnostic is useful, but it still fails Ma 2005: in the latest local run it improved some damping diagnostics relative to the compact collocation BEM, while A33/A55 and the heave-pitch coupling terms remained outside acceptance. Treat this as evidence that the next work is the full 2.5D forward-speed/radiation-diffraction assembly, not a completed validation.

The current `strip_2p5d_forward` diagnostic adds a PDSTRIP-like section-velocity map and longitudinal-gradient term. The `strip_2p5d_pdstrip_step` diagnostic exposes the bow-to-stern end-difference form used by the PDSTRIP pressure-gradient audit as a selectable station model. In the latest local `--ma-compare-hydro-models` run, both forward-speed assembly paths passed 17/55 side-by-side Ma rows; the step path slightly improved `B53` and slightly worsened `A53`, so it is useful evidence but not a validation fix.

The current `pressure_transfer_forward` and `pressure_transfer_pdstrip_step` diagnostics derive the heave section radiation coefficients from body-panel pressure transfer data before applying the same forward-speed station assemblies. In `outputs\validation_current`, both pressure-transfer paths are finite and visible in the Ma hydro-model tables: Wigley III is 16/55 PASS and SL-7 is 0/48 PASS. They improve some Wigley coupling diagnostics (`B53`, `B35`) but fail the diagonal pressure/radiation terms, so this is a traceable pressure-path diagnostic rather than an acceptance improvement.

The `pressure_transfer_pdstrip_damping_forward` and `pressure_transfer_pdstrip_damping_pdstrip_step` candidates keep pressure-transfer-derived sectional added mass but use `pdstrip_style` sectional damping before the same continuous-gradient or PDSTRIP-step forward-speed assembly. They are designed to test whether the remaining Wigley `B35/B53` damping-coupling miss follows the local damping frequency shape. Their `solver_status` explicitly remains `diagnostic_*_not_validated`.

Focused Ma 2005 probes at `outputs\validation_ma_b35_pdstrip_damping_probe` and `outputs\validation_ma_b35_b53_pdstrip_damping_probe` show this is useful evidence but not a fix. For Wigley III, `pressure_transfer_pdstrip_damping_forward` is the best B35 diagnostic at 1/3 PASS with median gate ratio `1.43`, while B53 is tied with `pressure_transfer_forward` at 4/8 PASS with median gate ratio `1.21`. For SL-7, the same pressure-transfer damping candidates are much worse than `pdstrip_style` or `prototype`, so the route cannot be promoted to a general hydrodynamic model.

The current `hybrid_forward_coupling` diagnostic keeps the prototype diagonal coefficients and replaces only heave/pitch coupling coefficients with the forward-speed assembly. In the latest comprehensive run at `outputs\validation_current`, after near-zero reference handling and SL-7 Table 2 LCG conversion, it is the best current diagnostic model, but it still has 39/55 PASS for Wigley III and 11/48 PASS for SL-7. The gap summary shows Wigley blockers mainly in `B53`, `B35`, `B55`, `A35`, and `A53`; SL-7 additionally blocks on `A53`, `B53`, `A35`, `A55`, and real-offset-sensitive pitch terms. The coupling variant sweep found the existing sign convention and the PDSTRIP-step discretization are essentially tied, while accumulator-sign and transpose variants are worse. A pressure-transfer audit now reconstructs both the forward-speed main-radiation operator and the PDSTRIP-step pressure-gradient/end-term operator from body-panel pressure data. The next work is therefore not a simple sign, transpose, or step-difference fix; it is replacing the compact pressure transfer with a validated Ma/PDSTRIP-style sectional pressure solution and adding real SL-7 offsets.

The `hybrid_pressure_damping_coupling` diagnostic is a narrower split for the same Ma gap: it preserves prototype diagonals, keeps `A35/A53` from the forward-speed assembly, and replaces only `B35/B53` with the pressure-transfer PDSTRIP-step damping couplings. Use it to test whether the pressure route actually helps the highest-priority damping-coupling blockers before changing the base 2.5D assembly.

A focused hard-gate run at `outputs\validation_hybrid_pressure_damping_model` uses `--ma-hydro-model hybrid_pressure_damping_coupling` with a light panel setting. It remains a failed validation, but improves the global count to 129 PASS / 68 FAIL / 4 NOT_EVALUATED / 17 INFO and improves Wigley III to 42 PASS / 16 FAIL. SL-7 remains 11 PASS / 40 FAIL plus the real-offsets gap, so this is evidence for the Wigley damping-coupling path rather than completion.

The station-contribution diagnostic now covers the full longitudinal 2x2 coefficient set, not just B35/B53. A focused B55 probe at `outputs\validation_station_b55_probe` remains a failed global validation run, but writes 984 Wigley III station-contribution rows for `B55` across force-collocation, force-`pdstrip_style`, pressure-raw, and pressure-clipped sources under both continuous-gradient and PDSTRIP-step assemblies. Use this to localize pitch-damping blockers by station before changing the accepted 2.5D model.

The pitch-axis sensitivity probe at `outputs\validation_ma_b55_pitch_axis_probe` shows Wigley III `B55` is not primarily a pitch-reference-axis issue: the best small axis shift changes the median gate only from `0.8587` to `0.8560` and still leaves 3/6 PASS. SL-7 `B55` improves more under aft axis shifts, but still remains incomplete and is still limited by surrogate geometry and missing real offsets.

Interpret validation as separate gates rather than one blended score: Faltinsen Ch. 9 and Katayama classification passing means the current longitudinal model is behaving sensibly for its implemented scope; Ma 2005 failures mean the complete station-based 2.5D solver is not yet validated.

A prototype station-section API now exists at [station_2p5d.py](planing_seakeeping/station_2p5d.py), with an example hull in [example_station_hull.yml](configs/example_station_hull.yml). It now includes frequency-dependent longitudinal radiation kernels, forward-speed heave/pitch coupling, an experimental 2D section-BEM radiation plus incident/diffraction excitation path, an experimental sway/heave/roll section-radiation matrix audit in [section_bem.py](planing_seakeeping/section_bem.py), experimental body-panel radiation/diffraction pressure-transfer diagnostics, pressure-transfer reconstructions of the forward-speed main-radiation and PDSTRIP-step pressure-gradient/end-term station operators, selectable pressure-transfer forward-speed assembly diagnostics, a PDSTRIP-style sectional integral heave-radiation diagnostic, a PDSTRIP-like forward-speed station-assembly diagnostic, and a hybrid diagonal/coupling isolation diagnostic. It is still intentionally marked unvalidated; Ma 2005 pressure-function validation and coefficient acceptance remain open; see [station_2p5d_api.md](docs/station_2p5d_api.md).

Station hulls may now be described by `beam_m` / `draft_m` / `deadrise_deg`, by inline wetted-section offsets, or by a long-form offsets CSV. See [example_station_offsets.yml](configs/example_station_offsets.yml), [example_station_offsets_csv.yml](configs/example_station_offsets_csv.yml), and [example_station_offsets.csv](configs/example_station_offsets.csv).

Run the unvalidated station prototype:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_prototype
```

Run the same prototype from explicit station offsets:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_offsets.yml --out outputs\station_offsets --radiation-model section_bem --period-count 4 --bem-free-surface-panels 3
```

Run from a separate offsets CSV:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_offsets_csv.yml --out outputs\station_offsets_csv --radiation-model section_bem --period-count 4 --bem-free-surface-panels 3
```

Use `--bem-body-panels N` to resample each wetted section by arclength before the experimental section-BEM solve.

Run the experimental section-BEM diagnostic with a small period sweep:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_bem --radiation-model section_bem --period-count 5
```

Run the PDSTRIP-style sectional integral radiation diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_pdstrip_style --radiation-model pdstrip_style --period-count 5 --bem-free-surface-panels 10 --bem-body-panels 16
```

Run the forward-speed station-assembly diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_strip_2p5d_forward --radiation-model strip_2p5d_forward --period-count 5 --bem-free-surface-panels 8 --bem-body-panels 12 --speed-mps 2.0
```

Run the PDSTRIP-step station-assembly diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_pdstrip_step_forward --radiation-model strip_2p5d_pdstrip_step --period-count 5 --bem-free-surface-panels 8 --bem-body-panels 12 --speed-mps 2.0
```

Run the hybrid diagonal/coupling diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_hybrid_forward_coupling --radiation-model hybrid_forward_coupling --period-count 5 --bem-free-surface-panels 8 --bem-body-panels 12 --speed-mps 2.0
```

Run the hybrid pressure damping-coupling diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_hybrid_pressure_damping_coupling --radiation-model hybrid_pressure_damping_coupling --period-count 5 --bem-free-surface-panels 8 --bem-body-panels 12 --speed-mps 2.0
```

Run the pressure-transfer station diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_pressure_transfer --radiation-model pressure_transfer_forward --period-count 5 --bem-free-surface-panels 4 --bem-body-panels 8 --speed-mps 2.0
```

Use `--radiation-model pressure_transfer_pdstrip_step` for the same pressure-derived section coefficients routed through the bow-to-stern PDSTRIP-step assembly. Use `pressure_transfer_pdstrip_damping_forward` or `pressure_transfer_pdstrip_damping_pdstrip_step` for the shape-matched damping diagnostic.

This writes `hydrostatics.csv`, single-frequency snapshot matrices (`added_mass_6dof.csv`, `damping_6dof.csv`, `restoring_6dof.csv`), frequency-sweep outputs (`station_frequency_matrices_long.csv`, `station_excitation.csv`, `station_rao.csv`), and `station_report.md`.
It also writes `station_geometry_audit.csv`, a station-by-station geometry quality check for beam, draft, area, centroid, offset orientation, and waterline endpoint consistency.
With `--radiation-model section_bem`, `pdstrip_style`, `strip_2p5d_forward`, `strip_2p5d_pdstrip_step`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, `hybrid_forward_coupling`, or `hybrid_pressure_damping_coupling`, it also writes `section_bem_diagnostics.csv` with station-by-station heave radiation coefficients, condition numbers, residuals, and a `section_solver` column.
With `--radiation-model section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, or `hybrid_pressure_damping_coupling`, it also writes `section_bem_multimode_radiation_diagnostics.csv` with station-by-station sway/heave/roll radiation matrix terms.
With `--radiation-model section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, or `hybrid_pressure_damping_coupling`, it also writes `section_bem_pressure_transfer_diagnostics.csv` with station-by-station body-panel radiation, incident, diffracted, and total pressure transfer functions.
With `--radiation-model section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, or `hybrid_pressure_damping_coupling`, it also writes `forward_speed_pressure_transfer_diagnostics.csv`, which reconstructs the forward-speed main-radiation heave/pitch operator from body-panel pressure transfer data and compares it with the force-integrated operator.
With `--radiation-model section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, or `hybrid_pressure_damping_coupling`, it also writes `forward_speed_pressure_gradient_diagnostics.csv`, which applies the same body-panel pressure transfer data to the PDSTRIP-step longitudinal-gradient/end-term assembly and compares it with the force-integrated section-coefficient path.
With `--radiation-model strip_2p5d_forward`, `strip_2p5d_pdstrip_step`, `hybrid_forward_coupling`, or `hybrid_pressure_damping_coupling`, it also writes `forward_speed_assembly_diagnostics.csv`, splitting the heave/pitch operator into `main_radiation`, `forward_gradient`, and `total` components.
It also writes `section_bem_excitation_diagnostics.csv` with station-by-station experimental incident/diffraction excitation magnitudes.

When Fridsma/Katayama digitized amplitude CSV files are present, `validate --benchmark all` reconstructs those cases and writes `fridsma_regular_wave_amplitudes_comparison.csv` or `katayama_regular_wave_amplitudes_comparison.csv`. Fridsma configuration A is now active; Katayama amplitude data are still pending. For Katayama, the pitch ordinate can be entered as `pitch_rao_rad_per_wave_slope` directly from Fig. 9/Fig. 10 and will be converted to `pitch_rao_rad_per_m`. A separate Katayama qualitative trend gate now checks source-text trends and intentionally fails the linear frequency-domain wave-height-dependent peak checks until the model includes a validated nonlinear amplitude-dependent response path. The accompanying nonlinear RK4 pilot is a fast development diagnostic, not a final acceptance gate.

## Self-Similar Wedge Pressure Diagnostic

The Iafrati/Zhao--Faltinsen self-similar wedge route is an independent Gate 2 prerequisite and remains explicitly unvalidated. Formal checkpoints preserve the frozen outer free surface, previous shape dipole, cumulative history, and SHA-256 evidence.

Resume one verified checkpoint while changing only the pseudo-time CFL:

```powershell
python scripts\resume_self_similar_wedge.py --checkpoint outputs\self_similar_wedge_20deg_coupled160_v61_checkpoint --out outputs\wedge_resume --additional-iterations 20 --pseudo-cfl 0.10
```

Analyze matched continuations at different pseudo-time steps:

```powershell
python scripts\analyze_self_similar_time_step_convergence.py --runs outputs\wedge_cfl020 outputs\wedge_cfl010 outputs\wedge_cfl005 --out outputs\wedge_time_convergence
```

Run an explicit spatial regrid and the diagnostic quadratic root-node recovery candidate:

```powershell
python scripts\resume_self_similar_wedge_regridded.py --checkpoint outputs\self_similar_wedge_20deg_coupled160_v61_checkpoint --out outputs\wedge_grid120 --outer-panels 120 --additional-iterations 13 --pseudo-cfl 0.10 --root-state-recovery quadratic_root_extrapolation
```

Compare matched spatial levels:

```powershell
python scripts\analyze_self_similar_grid_convergence.py --runs outputs\wedge_grid80 outputs\wedge_grid120 --out outputs\wedge_grid_convergence
```

A convergence `PASS` from these scripts proves only the declared time-step or grid scope. It does not pass the three-angle pressure benchmark or Gate 2; inspect `physical_validation_status` in the machine report.

## Model Notes

- Calm-water equilibrium uses Savitsky-style lift and center-of-pressure equations as summarized by Faltinsen.
- Heave/pitch matrices use Faltinsen Ch. 9 high-frequency/free-surface approximations.
- Frequency-domain wave excitation follows Faltinsen eqs. 9.108-9.120.
- Time-domain integration uses Faltinsen eqs. 9.121-9.125 with nonlinear quasi-steady restoring and linear diffraction/radiation residuals.
- Irregular seas are generated by component superposition from PM/JONSWAP spectra.

This is a preliminary-design engineering model, not a CFD or tank-test replacement.
